#!/usr/bin/env python
import json
import os
import sys
import uuid
from pathlib import Path
from typing import List
from urllib import parse, request, error


def log(msg: str) -> None:
    print(msg, flush=True)


def ensure_project(server_url: str, project_id: str, token: str | None = None) -> None:
    """Ensure the Allure project exists, creating it if needed (best-effort).

    First checks if the project already exists via GET /projects/{id}.
    Only attempts creation if the project is not found (404).
    Non-fatal on any error — let the caller continue to `send-results`.
    """
    base = server_url.rstrip("/")
    headers: dict[str, str] = {}
    if token:
        headers["X-ALLURE-TOKEN"] = token

    # Check if project already exists
    get_req = request.Request(f"{base}/projects/{project_id}", headers=headers)
    try:
        with request.urlopen(get_req, timeout=10) as resp:
            resp.read()
            # Project exists — nothing to do
            return
    except error.HTTPError as exc:
        if exc.code != 404:
            log(f"⚠️ Failed to check Allure project '{project_id}': {exc}. Continuing anyway.")
            return
        # 404 → project does not exist, create it below
    except Exception as exc:  # noqa: BLE001
        log(f"⚠️ Failed to check Allure project '{project_id}': {exc}. Continuing anyway.")
        return

    # Project not found — create it
    create_headers = {"Content-Type": "application/json", **headers}
    payload = json.dumps({"id": project_id}).encode("utf-8")
    create_req = request.Request(f"{base}/projects", data=payload, headers=create_headers)
    try:
        with request.urlopen(create_req, timeout=10) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            log(f"✅ Allure project '{project_id}' created ({resp.status}): {body}")
    except Exception as exc:  # noqa: BLE001
        log(f"⚠️ Failed to create Allure project '{project_id}': {exc}. Continuing anyway.")


def generate_report(
    server_url: str,
    project_id: str,
    launch_name: str | None = None,
    token: str | None = None,
) -> None:
    """Trigger report generation for a project (best-effort).

    Calls `/generate-report?project_id=...` on the Allure server.
    Some setups might have auto-generation enabled; in that case this is harmless.
    """

    base_url = server_url.rstrip("/")
    params = f"project_id={project_id}"
    if launch_name:
        # Allure docker service supports optional execution metadata query params
        params += f"&execution_name={parse.quote(launch_name)}&execution_source=github-actions"
    url = f"{base_url}/generate-report?{params}"

    headers: dict[str, str] = {}
    if token:
        headers["X-ALLURE-TOKEN"] = token

    req = request.Request(url, headers=headers, method="GET")
    try:
        with request.urlopen(req, timeout=60) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            log(f"Allure generate-report response ({resp.status}): {body}")
    except Exception as exc:  # noqa: BLE001
        log(f"⚠️ Failed to generate Allure report for '{project_id}': {exc}. Continuing anyway.")


def build_multipart_body(results_dir: Path, launch_name: str | None = None) -> tuple[bytes, str]:
    """Build multipart/form-data body with files[] and optional launch_name.

    Returns (body_bytes, content_type_header).
    """

    boundary = "----allureboundary" + uuid.uuid4().hex
    boundary_bytes = boundary.encode("ascii")

    parts: List[bytes] = []

    # Optional text field for launch_name
    if launch_name:
        parts.append(b"--" + boundary_bytes)
        parts.append(b'Content-Disposition: form-data; name="launch_name"')
        parts.append(b"")
        parts.append(launch_name.encode("utf-8"))

    # Files as files[]
    for path in sorted(results_dir.glob("*")):
        if not path.is_file():
            continue
        parts.append(b"--" + boundary_bytes)
        dispo = f'Content-Disposition: form-data; name="files[]"; filename="{path.name}"'.encode(
            "utf-8"
        )
        parts.append(dispo)
        parts.append(b"Content-Type: application/octet-stream")
        parts.append(b"")
        parts.append(path.read_bytes())

    # Closing boundary
    parts.append(b"--" + boundary_bytes + b"--")
    parts.append(b"")

    body = b"\r\n".join(parts)
    content_type = f"multipart/form-data; boundary={boundary}"
    return body, content_type


def main() -> int:
    server_url = os.environ.get("ALLURE_SERVER_URL", "").strip()
    results_dir_env = os.environ.get("ALLURE_RESULTS_DIR", "").strip()
    project_id = os.environ.get("ALLURE_PROJECT_ID", "").strip()
    launch_name = os.environ.get("ALLURE_LAUNCH_NAME", "").strip()
    token = os.environ.get("ALLURE_TOKEN") or None

    if not server_url:
        log("⚠️ ALLURE_SERVER_URL not set. Skipping upload.")
        return 0

    if not project_id:
        log("⚠️ ALLURE_PROJECT_ID not set. Skipping upload.")
        return 0

    if not results_dir_env:
        log("⚠️ ALLURE_RESULTS_DIR not set. Skipping upload.")
        return 0

    results_dir = Path(results_dir_env)
    if not results_dir.is_dir():
        log(f"⚠️ Allure results directory '{results_dir}' not found. Skipping upload.")
        return 0

    # If no files, skip
    if not any(p.is_file() for p in results_dir.iterdir()):
        log(f"⚠️ Allure results directory '{results_dir}' is empty. Nothing to upload.")
        return 0

    log(f"Preparing to upload Allure results from '{results_dir}' to '{server_url}' for project '{project_id}'...")

    # Ensure project exists (best-effort)
    ensure_project(server_url, project_id, token)

    # Build multipart body with files[]
    body, content_type = build_multipart_body(results_dir, launch_name or None)

    base_url = server_url.rstrip("/")
    upload_url = base_url + f"/send-results?project_id={project_id}&force_update=true"
    headers = {"Content-Type": content_type}
    if token:
        headers["X-ALLURE-TOKEN"] = token

    req = request.Request(upload_url, data=body, headers=headers, method="POST")

    try:
        with request.urlopen(req, timeout=60) as resp:
            resp_body = resp.read().decode("utf-8", errors="replace")
            log(f"Allure upload response ({resp.status}): {resp_body}")
    except error.HTTPError as exc:
        err_body = exc.read().decode("utf-8", errors="replace")
        log(f"❌ Allure upload failed ({exc.code}): {err_body}")
        return 1
    except Exception as exc:  # noqa: BLE001
        log(f"❌ Allure upload failed: {exc}")
        return 1

    # After successful upload, trigger report generation so the UI can show it
    generate_report(base_url, project_id, launch_name or None, token)

    log("✅ Allure results upload finished.")
    return 0


if __name__ == "__main__":  # pragma: no cover - simple CLI wrapper
    raise SystemExit(main())
