#!/usr/bin/env python
import json
import os
import sys
import uuid
from pathlib import Path
from typing import List
from urllib import request, error


def log(msg: str) -> None:
    print(msg, flush=True)


def ensure_project(server_url: str, project_id: str, token: str | None = None) -> None:
    """Best-effort project creation; non-fatal on error."""
    create_url = server_url.rstrip("/") + "/projects"
    payload = json.dumps({"id": project_id}).encode("utf-8")

    headers = {"Content-Type": "application/json"}
    if token:
        headers["X-ALLURE-TOKEN"] = token

    req = request.Request(create_url, data=payload, headers=headers, method="POST")
    try:
        with request.urlopen(req, timeout=10) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            log(f"Allure project create response ({resp.status}): {body}")
    except Exception as exc:  # noqa: BLE001
        log(f"⚠️ Failed to ensure Allure project '{project_id}': {exc}. Continuing anyway.")


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

    upload_url = server_url.rstrip("/") + f"/send-results?project_id={project_id}&force_update=true"
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

    log("✅ Allure results upload finished.")
    return 0


if __name__ == "__main__":  # pragma: no cover - simple CLI wrapper
    raise SystemExit(main())
