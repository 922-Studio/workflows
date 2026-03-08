#!/usr/bin/env python3
"""
Create, update, or auto-close GitHub issues for CI failures.

Operates in two modes based on WORKFLOW_STATUS:
  - failure: Create a new issue or add a comment to an existing one
  - success: Auto-close any open ci-failure issue for the same job

Uses only stdlib — no external dependencies.
"""

import os
import sys
import json
import re
from urllib import request, error


GITHUB_API_BASE = "https://api.github.com"


def github_api_request(token, method, url, body=None):
    """Make a GitHub API request and return parsed JSON response.

    Returns parsed JSON dict on success, None on failure.
    """
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "922-Studio-CI-Issue-Bot/1.0",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = request.Request(url, data=data, headers=headers, method=method)

    try:
        with request.urlopen(req) as resp:
            resp_body = resp.read().decode("utf-8", errors="replace")
            if resp_body:
                return json.loads(resp_body)
            return {}
    except error.HTTPError as e:
        resp_body = e.read().decode("utf-8", errors="replace")
        print(f"❌ GitHub API error ({method} {url}): {e.code} - {resp_body}")
        return None
    except error.URLError as e:
        print(f"❌ Failed to reach GitHub API: {e.reason}")
        return None
    except Exception as e:  # noqa: BLE001
        print(f"❌ Unexpected error calling GitHub API: {e}")
        return None


def parse_pytest_summary(log):
    """Parse pytest output to extract summary and relevant log portion.

    Returns (summary_line_or_None, relevant_log_portion).
    """
    if not log:
        return None, ""

    lines = log.splitlines()

    # Look for pytest summary markers
    summary_pattern = re.compile(r"^=+ .+ =+$")
    failed_pattern = re.compile(r"^FAILED ")
    result_line_pattern = re.compile(
        r"^=+ (?:.*\d+ (?:failed|error|passed).*)=+$"
    )

    # Find the short test summary or failures section
    marker_start = None
    for i, line in enumerate(lines):
        if summary_pattern.match(line.strip()) and any(
            kw in line.lower()
            for kw in ("failures", "errors", "short test summary")
        ):
            marker_start = i
            break

    if marker_start is None:
        # Check for any FAILED lines as fallback
        has_failed = any(failed_pattern.match(line.strip()) for line in lines)
        if not has_failed:
            return None, log

    # Extract the final result line (e.g. "= 3 failed, 10 passed =")
    summary_line = None
    for line in reversed(lines):
        stripped = line.strip()
        if result_line_pattern.match(stripped):
            # Clean up the = signs
            summary_line = re.sub(r"^=+\s*", "", stripped)
            summary_line = re.sub(r"\s*=+$", "", summary_line)
            break

    # Extract relevant portion from marker to end
    if marker_start is not None:
        relevant = "\n".join(lines[marker_start:])
    else:
        relevant = log

    return summary_line, relevant


def format_issue_body(
    job_name, branch, run_number, run_url, error_log, triggering_actor
):
    """Build a markdown issue body with failure context."""
    sections = []

    # Parse pytest summary if error log provided
    pytest_summary = None
    relevant_log = error_log or ""
    if error_log:
        pytest_summary, relevant_log = parse_pytest_summary(error_log)

    # Test count summary at top if available
    if pytest_summary:
        sections.append(f"**{pytest_summary}**\n")

    # Metadata
    sections.append(f"**Job:** `{job_name}`")
    sections.append(f"**Branch:** `{branch}`")
    sections.append(f"**Run:** [#{run_number}]({run_url})")

    if triggering_actor:
        sections.append(f"**Triggered by:** @{triggering_actor}")

    sections.append("")

    # Error log section
    if relevant_log:
        log_lines = relevant_log.splitlines()
        if len(log_lines) > 50:
            sections.append(
                "<details>\n<summary>Error Log</summary>\n\n"
                f"```\n{relevant_log}\n```\n\n</details>"
            )
        else:
            sections.append(f"```\n{relevant_log}\n```")

    return "\n".join(sections)


def find_open_issue(token, repo, job_name):
    """Find an existing open ci-failure issue for the given job.

    Returns the issue dict if found, None otherwise.
    """
    labels = f"ci-failure,job:{job_name}"
    url = (
        f"{GITHUB_API_BASE}/repos/{repo}/issues"
        f"?labels={labels}&state=open&per_page=1"
    )

    result = github_api_request(token, "GET", url)
    if result and isinstance(result, list) and len(result) > 0:
        return result[0]
    return None


def create_issue(token, repo, title, body, labels, assignee):
    """Create a new GitHub issue.

    Returns the created issue dict.
    """
    url = f"{GITHUB_API_BASE}/repos/{repo}/issues"

    payload = {
        "title": title,
        "body": body,
        "labels": labels,
    }

    if assignee:
        payload["assignees"] = [assignee]

    result = github_api_request(token, "POST", url, payload)
    return result


def add_comment(token, repo, issue_number, body):
    """Add a comment to an existing issue.

    Returns True on success, False otherwise.
    """
    url = f"{GITHUB_API_BASE}/repos/{repo}/issues/{issue_number}/comments"

    payload = {"body": body}
    result = github_api_request(token, "POST", url, payload)
    return result is not None


def close_issue(token, repo, issue_number, run_number, run_url):
    """Close an issue with a resolution comment.

    Returns True on success, False otherwise.
    """
    # Add resolution comment
    comment_body = (
        f"Resolved in run [#{run_number}]({run_url})"
    )
    comment_url = (
        f"{GITHUB_API_BASE}/repos/{repo}/issues/{issue_number}/comments"
    )
    github_api_request(token, "POST", comment_url, {"body": comment_body})

    # Close the issue
    url = f"{GITHUB_API_BASE}/repos/{repo}/issues/{issue_number}"
    payload = {
        "state": "closed",
        "state_reason": "completed",
    }
    result = github_api_request(token, "PATCH", url, payload)
    return result is not None


def set_output(name, value):
    """Set a GitHub Actions output variable (both legacy and modern format)."""
    # Legacy format
    print(f"::set-output name={name}::{value}")

    # Modern format
    github_output = os.getenv("GITHUB_OUTPUT")
    if github_output:
        try:
            with open(github_output, "a") as f:
                f.write(f"{name}={value}\n")
        except OSError as e:
            print(f"Warning: Could not write to GITHUB_OUTPUT: {e}")


def main():
    """Entry point when used as a GitHub Actions script."""
    # Read required env vars
    token = os.getenv("GITHUB_TOKEN")
    repo = os.getenv("REPO_FULL_NAME")
    job_name = os.getenv("JOB_NAME")
    branch = os.getenv("BRANCH_NAME")
    run_number = os.getenv("RUN_NUMBER")
    run_url = os.getenv("RUN_URL")
    workflow_status = os.getenv("WORKFLOW_STATUS")

    # Optional env vars
    error_log = os.getenv("ERROR_LOG", "")
    triggering_actor = os.getenv("TRIGGERING_ACTOR", "")

    # Validate required env vars
    required = {
        "GITHUB_TOKEN": token,
        "REPO_FULL_NAME": repo,
        "JOB_NAME": job_name,
        "BRANCH_NAME": branch,
        "RUN_NUMBER": run_number,
        "RUN_URL": run_url,
        "WORKFLOW_STATUS": workflow_status,
    }

    missing = [k for k, v in required.items() if not v]
    if missing:
        print(f"❌ ERROR: Missing required environment variables: {', '.join(missing)}")
        sys.exit(1)

    # Extract short repo name
    repo_short = repo.split("/", 1)[1] if "/" in repo else repo

    # Success mode: auto-close open issue
    if workflow_status.lower() == "success":
        print(f"🔍 Checking for open ci-failure issues for job '{job_name}'...")
        existing = find_open_issue(token, repo, job_name)

        if existing:
            issue_number = existing["number"]
            print(f"📋 Found open issue #{issue_number}, closing...")
            success = close_issue(token, repo, issue_number, run_number, run_url)
            if success:
                print(f"✅ Issue #{issue_number} closed — resolved in run #{run_number}")
                set_output("issue_url", existing["html_url"])
            else:
                print(f"❌ Failed to close issue #{issue_number}")
                sys.exit(1)
        else:
            print(f"✅ No open ci-failure issues found for job '{job_name}' — nothing to close")

        sys.exit(0)

    # Failure mode: create or update issue
    print(f"🔍 Checking for existing ci-failure issue for job '{job_name}'...")
    existing = find_open_issue(token, repo, job_name)

    if existing:
        # Add comment to existing issue
        issue_number = existing["number"]
        print(f"📋 Found existing issue #{issue_number}, adding comment...")

        body = format_issue_body(
            job_name, branch, run_number, run_url, error_log, triggering_actor
        )
        comment_body = (
            f"## Re-failure — Run #{run_number}\n\n{body}\n\n"
            f"[View run]({run_url})"
        )
        success = add_comment(token, repo, issue_number, comment_body)

        if success:
            issue_url = existing["html_url"]
            print(f"✅ Comment added to issue #{issue_number}: {issue_url}")
            set_output("issue_url", issue_url)
        else:
            print(f"❌ Failed to add comment to issue #{issue_number}")
            sys.exit(1)
    else:
        # Create new issue
        print(f"📝 Creating new ci-failure issue...")

        title = (
            f"CI Failure: {job_name} failed on {branch}"
            f" — {repo_short} #{run_number}"
        )
        labels = ["ci-failure", "automated", f"job:{job_name}"]
        body = format_issue_body(
            job_name, branch, run_number, run_url, error_log, triggering_actor
        )

        assignee = triggering_actor if triggering_actor else None
        result = create_issue(token, repo, title, body, labels, assignee)

        if result:
            issue_url = result.get("html_url", "")
            issue_number = result.get("number", "?")
            print(f"✅ Issue #{issue_number} created: {issue_url}")
            set_output("issue_url", issue_url)
        else:
            print("❌ Failed to create issue")
            sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()
