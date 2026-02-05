"""Notification services for stream monitoring."""

import os
from datetime import datetime

import requests


def send_discord_notification(
    webhook_url: str,
    title: str,
    message: str,
    color: int = 0x5865F2,  # Discord blurple
) -> bool:
    """Send a notification to Discord via webhook.

    Args:
        webhook_url: Discord webhook URL
        title: Embed title
        message: Embed description
        color: Embed color (hex int). Red=0xFF0000, Green=0x00FF00, Yellow=0xFFFF00

    Returns:
        True if successful, False otherwise
    """
    payload = {
        "embeds": [
            {
                "title": title,
                "description": message,
                "color": color,
                "timestamp": datetime.utcnow().isoformat(),
            }
        ]
    }

    try:
        response = requests.post(webhook_url, json=payload, timeout=10)
        return response.status_code == 204
    except Exception:
        return False


def get_discord_webhook_url() -> str | None:
    """Get Discord webhook URL from environment."""
    return os.environ.get("DISCORD_WEBHOOK_URL")


# Color constants for Discord embeds
DISCORD_RED = 0xFF0000
DISCORD_GREEN = 0x00FF00
DISCORD_YELLOW = 0xFFAA00
DISCORD_BLUE = 0x5865F2
