#!/usr/bin/env python3
"""
Send workflow status notifications to a Discord channel using a bot token.
Produces a well-formatted embed similar in spirit to the email template.
"""

import os
import sys
import json
import datetime
from urllib import request, error


DISCORD_API_BASE = "https://discord.com/api/v10"
DEFAULT_CHANNEL_ID = "1465354445113000032"


def build_status_style(workflow_status: str):
    """Return (color_int, emoji, text) based on workflow status.

    Colors mirror the email template:
      - success  -> #28a745 (green)
      - failure  -> #dc3545 (red)
      - cancelled-> #6c757d (gray)
      - default  -> #007bff (blue)
    """
    status = (workflow_status or "unknown").lower()

    if status == "success":
        return int("28a745", 16), "✅", "Successful"
    if status == "failure":
        return int("dc3545", 16), "❌", "Failed"
    if status == "cancelled":
        return int("6c757d", 16), "⚠️", "Cancelled"

    return int("007bff", 16), "ℹ️", "Completed"


def build_discord_embed(workflow_status, workflow_name, repository_name, run_url):
    """Build a rich Discord embed payload for the workflow notification."""
    color, status_emoji, status_text = build_status_style(workflow_status)

    safe_status = workflow_status or "Unknown"
    safe_workflow = workflow_name or "N/A"
    # Show only the repo name without the owner (e.g. "HomeAPI" instead of "922-Studio/HomeAPI")
    if repository_name and "/" in repository_name:
        safe_repo = repository_name.split("/", 1)[1]
    else:
        safe_repo = repository_name or "N/A"

    description_lines = [
        f"**Status:** {status_emoji} `{safe_status}`",
        f"**Workflow:** `{safe_workflow}`",
        f"**Repository:** `{safe_repo}`",
    ]

    if run_url:
        description_lines.append("")
        description_lines.append(f"[View Workflow Run]({run_url})")

    embed = {
        "title": f"{status_emoji} Workflow {status_text}",
        "description": "\n".join(description_lines),
        "color": color,
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        "fields": [
            {
                "name": "Status",
                "value": f"{status_emoji} `{safe_status}`",
                "inline": True,
            },
            {
                "name": "Workflow",
                "value": f"`{safe_workflow}`",
                "inline": True,
            },
        ],
    }

    if run_url:
        embed["url"] = run_url

    return embed


def send_discord_status_update(
    bot_token: str,
    channel_id: str,
    workflow_status: str | None,
    workflow_name: str | None,
    repository_name: str | None,
    run_url: str | None,
) -> bool:
    """Send a status update message with an embed to a Discord channel.

    Returns True on success, False otherwise.
    """
    embed = build_discord_embed(workflow_status, workflow_name, repository_name, run_url)

    payload: dict = {
        "content": "",
        "embeds": [embed],
    }

    data = json.dumps(payload).encode("utf-8")

    url = f"{DISCORD_API_BASE}/channels/{channel_id}/messages"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bot {bot_token}",
    }

    req = request.Request(url, data=data, headers=headers, method="POST")

    try:
        with request.urlopen(req) as resp:
            status_code = resp.getcode()
            if 200 <= status_code < 300:
                print("✅ Discord notification sent successfully.")
                return True
            else:
                body = resp.read().decode("utf-8", errors="replace")
                print(f"❌ Discord API returned status {status_code}: {body}")
                return False
    except error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        print(f"❌ HTTP error when calling Discord API: {e.code} - {body}")
        return False
    except error.URLError as e:
        print(f"❌ Failed to reach Discord API: {e.reason}")
        return False
    except Exception as e:  # noqa: BLE001
        print(f"❌ Unexpected error sending Discord notification: {e}")
        return False


def main():
    """Entry point when used as a GitHub Actions script."""
    bot_token = os.getenv("DISCORD_BOT_TOKEN")
    channel_id = os.getenv("DISCORD_CHANNEL_ID") or DEFAULT_CHANNEL_ID

    workflow_status = os.getenv("WORKFLOW_STATUS")
    workflow_name = os.getenv("WORKFLOW_NAME")
    repository_name = os.getenv("REPOSITORY_NAME")
    run_url = os.getenv("RUN_URL")

    if not bot_token:
        print("❌ ERROR: DISCORD_BOT_TOKEN is not set")
        sys.exit(1)

    if not channel_id:
        print("❌ ERROR: DISCORD_CHANNEL_ID is not set and no default is configured")
        sys.exit(1)

    print(f"🚀 Sending Discord workflow notification to channel {channel_id}...")

    success = send_discord_status_update(
        bot_token=bot_token,
        channel_id=channel_id,
        workflow_status=workflow_status,
        workflow_name=workflow_name,
        repository_name=repository_name,
        run_url=run_url,
    )

    if not success:
        print("❌ Discord notification failed")
        sys.exit(1)

    print("✅ Discord notification completed successfully")
    sys.exit(0)


if __name__ == "__main__":
    main()
