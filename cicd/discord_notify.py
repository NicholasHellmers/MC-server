"""CI script to send release notifications to Discord via webhook."""

from __future__ import annotations

import argparse
import os
import sys
from typing import Any

import requests


def send_discord_notification(
    webhook_url: str,
    version_tag: str,
    release_url: str,
    changelog: str = "Bug fixes and performance improvements.",
    server_address: str = "play.cobblemon.xyz",
) -> dict[str, Any]:
    """Send a formatted Discord embed announcing a new modpack release."""
    if not webhook_url:
        return {"status": "error", "message": "Missing DISCORD_WEBHOOK URL."}

    payload = {
        "username": "Cobblemon Server Bot",
        "avatar_url": "https://cdn.modrinth.com/data/u6ne2mrh/icon.png",
        "embeds": [
            {
                "title": f"🚀 New Modpack Release: {version_tag}",
                "url": release_url,
                "description": (
                    f"A new update is available for **Cobblemon Adventure**!\n\n"
                    f"**Changelog:**\n{changelog}\n\n"
                    f"**Server Address:** `{server_address}`\n\n"
                    f"**How to Update:** Download the `.mrpack` below and drag & drop it into your Modrinth App."
                ),
                "color": 3447003,
                "fields": [
                    {"name": "Minecraft", "value": "1.21.1 (Fabric 0.19.3)", "inline": True},
                    {"name": "Download", "value": f"[GitHub Release]({release_url})", "inline": True},
                ],
                "footer": {"text": "Cobblemon Single Source of Truth CI/CD"},
            }
        ],
    }

    try:
        response = requests.post(webhook_url, json=payload, timeout=10)
        if response.status_code in (200, 204):
            return {"status": "success", "status_code": response.status_code}
        return {"status": "error", "status_code": response.status_code, "text": response.text}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def main() -> int:
    """CLI entrypoint."""
    parser = argparse.ArgumentParser(description="Send Discord release notification.")
    parser.add_argument("--version", default="v1.0.0", help="Release version tag")
    parser.add_argument("--release-url", default="", help="GitHub release URL")
    parser.add_argument("--changelog", default="Routine modpack and balance update.", help="Changelog description")
    parser.add_argument("--server-ip", default="play.cobblemon.xyz", help="Server hostname/IP")
    args = parser.parse_args()

    webhook_url = os.getenv("DISCORD_WEBHOOK", "")
    res = send_discord_notification(
        webhook_url=webhook_url,
        version_tag=args.version,
        release_url=args.release_url,
        changelog=args.changelog,
        server_address=args.server_ip,
    )
    print(f"Discord notification result: {res}")
    return 0 if res.get("status") == "success" else 1


if __name__ == "__main__":
    sys.exit(main())
