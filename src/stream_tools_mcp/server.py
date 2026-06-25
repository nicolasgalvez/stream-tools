"""MCP server for YouTube operations via stream_tools library."""

import json

from mcp.server.fastmcp import FastMCP

from stream_tools.auth.oauth import OAuthManager
from stream_tools.client import YouTubeLiveClient
from stream_tools.exceptions import StreamToolsError

mcp = FastMCP("stream-tools")
_client: YouTubeLiveClient | None = None


def _get_client() -> YouTubeLiveClient:
    global _client
    if _client is None:
        auth = OAuthManager()
        auth.auto_authenticate()
        _client = YouTubeLiveClient(auth.credentials)
    return _client


def _ok(data) -> str:
    if hasattr(data, "to_dict"):
        return json.dumps(data.to_dict(), indent=2)
    return json.dumps(data, indent=2, default=str)


def _err(e: Exception) -> str:
    return f"Error: {e}"


# ── Videos ──────────────────────────────────────────────────────────────────

@mcp.tool()
def video_upload(
    file_path: str,
    title: str,
    description: str = "",
    tags: str = "",
    category_id: str = "",
    privacy_status: str = "private",
    publish_at: str = "",
    license: str = "youtube",
    made_for_kids: bool = False,
) -> str:
    """Upload a video file to YouTube. Tags are comma-separated."""
    try:
        tag_list = [t.strip() for t in tags.split(",")] if tags else []
        video = _get_client().videos.upload(
            file_path=file_path,
            title=title,
            description=description,
            tags=tag_list,
            category_id=category_id,
            privacy_status=privacy_status,
            publish_at=publish_at or None,
            license=license,
            made_for_kids=made_for_kids,
        )
        return _ok(video)
    except (StreamToolsError, Exception) as e:
        return _err(e)


@mcp.tool()
def video_list(limit: int = 25) -> str:
    """List your uploaded videos."""
    try:
        result = _get_client().videos.list(max_results=limit)
        return _ok([v.to_dict() for v in result.items])
    except (StreamToolsError, Exception) as e:
        return _err(e)


@mcp.tool()
def video_get(video_id: str) -> str:
    """Get details for a single video by ID."""
    try:
        return _ok(_get_client().videos.get(video_id))
    except (StreamToolsError, Exception) as e:
        return _err(e)


@mcp.tool()
def video_update(
    video_id: str,
    title: str = "",
    description: str = "",
    tags: str = "",
    category_id: str = "",
    privacy_status: str = "",
    publish_at: str = "",
) -> str:
    """Update video metadata. Only provided fields are changed. Tags are comma-separated."""
    try:
        tag_list = [t.strip() for t in tags.split(",")] if tags else None
        video = _get_client().videos.update(
            video_id=video_id,
            title=title or None,
            description=description or None,
            tags=tag_list,
            category_id=category_id or None,
            privacy_status=privacy_status or None,
            publish_at=publish_at or None,
        )
        return _ok(video)
    except (StreamToolsError, Exception) as e:
        return _err(e)


@mcp.tool()
def video_delete(video_id: str) -> str:
    """Delete a video permanently."""
    try:
        _get_client().videos.delete(video_id)
        return f"Video {video_id} deleted."
    except (StreamToolsError, Exception) as e:
        return _err(e)


@mcp.tool()
def video_categories(region_code: str = "US") -> str:
    """List available video categories for a region."""
    try:
        return _ok(_get_client().videos.list_categories(region_code=region_code))
    except (StreamToolsError, Exception) as e:
        return _err(e)


# ── Broadcasts ──────────────────────────────────────────────────────────────

@mcp.tool()
def broadcast_list(limit: int = 25, status: str = "all") -> str:
    """List broadcasts. Status: all, active, completed, upcoming."""
    try:
        result = _get_client().broadcasts.list(max_results=limit, status=status)
        return _ok([b.to_dict() for b in result.items])
    except (StreamToolsError, Exception) as e:
        return _err(e)


@mcp.tool()
def broadcast_get(broadcast_id: str) -> str:
    """Get details for a single broadcast."""
    try:
        return _ok(_get_client().broadcasts.get(broadcast_id))
    except (StreamToolsError, Exception) as e:
        return _err(e)


@mcp.tool()
def broadcast_create(
    title: str,
    start_time: str = "",
    privacy: str = "private",
    description: str = "",
) -> str:
    """Create a new broadcast. Start time is ISO 8601 (e.g. 2026-01-24T10:00:00Z)."""
    try:
        broadcast = _get_client().broadcasts.create(
            title=title,
            scheduled_start_time=start_time or None,
            privacy_status=privacy,
            description=description or None,
        )
        return _ok(broadcast)
    except (StreamToolsError, Exception) as e:
        return _err(e)


@mcp.tool()
def broadcast_update(broadcast_id: str, title: str = "", description: str = "") -> str:
    """Update a broadcast. Only provided fields are changed."""
    try:
        broadcast = _get_client().broadcasts.update(
            broadcast_id=broadcast_id,
            title=title or None,
            description=description or None,
        )
        return _ok(broadcast)
    except (StreamToolsError, Exception) as e:
        return _err(e)


@mcp.tool()
def broadcast_delete(broadcast_id: str) -> str:
    """Delete a broadcast."""
    try:
        _get_client().broadcasts.delete(broadcast_id)
        return f"Broadcast {broadcast_id} deleted."
    except (StreamToolsError, Exception) as e:
        return _err(e)


@mcp.tool()
def broadcast_bind(broadcast_id: str, stream_id: str) -> str:
    """Bind a stream to a broadcast."""
    try:
        broadcast = _get_client().broadcasts.bind(broadcast_id, stream_id)
        return _ok(broadcast)
    except (StreamToolsError, Exception) as e:
        return _err(e)


@mcp.tool()
def broadcast_transition(broadcast_id: str, status: str) -> str:
    """Transition broadcast status: testing, live, complete."""
    try:
        broadcast = _get_client().broadcasts.transition(broadcast_id, status)
        return _ok(broadcast)
    except (StreamToolsError, Exception) as e:
        return _err(e)


# ── Streams ─────────────────────────────────────────────────────────────────

@mcp.tool()
def stream_list(limit: int = 25) -> str:
    """List RTMP streams."""
    try:
        result = _get_client().streams.list(max_results=limit)
        return _ok([s.to_dict() for s in result.items])
    except (StreamToolsError, Exception) as e:
        return _err(e)


@mcp.tool()
def stream_get(stream_id: str) -> str:
    """Get details for a single stream."""
    try:
        return _ok(_get_client().streams.get(stream_id))
    except (StreamToolsError, Exception) as e:
        return _err(e)


@mcp.tool()
def stream_create(
    title: str,
    resolution: str = "variable",
    frame_rate: str = "variable",
) -> str:
    """Create a new RTMP stream. Resolution: 240p|360p|480p|720p|1080p|1440p|2160p|variable. Frame rate: 30fps|60fps|variable."""
    try:
        stream = _get_client().streams.create(
            title=title,
            resolution=resolution,
            frame_rate=frame_rate,
        )
        return _ok(stream)
    except (StreamToolsError, Exception) as e:
        return _err(e)


@mcp.tool()
def stream_update(stream_id: str, title: str) -> str:
    """Update a stream's title."""
    try:
        return _ok(_get_client().streams.update(stream_id, title))
    except (StreamToolsError, Exception) as e:
        return _err(e)


@mcp.tool()
def stream_delete(stream_id: str) -> str:
    """Delete a stream."""
    try:
        _get_client().streams.delete(stream_id)
        return f"Stream {stream_id} deleted."
    except (StreamToolsError, Exception) as e:
        return _err(e)


# ── Chat ────────────────────────────────────────────────────────────────────

@mcp.tool()
def chat_list(live_chat_id: str, limit: int = 200) -> str:
    """List messages from a live chat."""
    try:
        result = _get_client().chat.list_messages(live_chat_id, max_results=limit)
        return _ok([m.to_dict() for m in result.items])
    except (StreamToolsError, Exception) as e:
        return _err(e)


@mcp.tool()
def chat_send(live_chat_id: str, message: str) -> str:
    """Send a message to a live chat."""
    try:
        return _ok(_get_client().chat.send_message(live_chat_id, message))
    except (StreamToolsError, Exception) as e:
        return _err(e)


@mcp.tool()
def chat_delete_message(message_id: str) -> str:
    """Delete a chat message."""
    try:
        _get_client().chat.delete_message(message_id)
        return f"Message {message_id} deleted."
    except (StreamToolsError, Exception) as e:
        return _err(e)


# ── Moderators ──────────────────────────────────────────────────────────────

@mcp.tool()
def moderator_list(live_chat_id: str) -> str:
    """List moderators for a live chat."""
    try:
        result = _get_client().moderators.list(live_chat_id)
        return _ok([m.to_dict() for m in result.items])
    except (StreamToolsError, Exception) as e:
        return _err(e)


@mcp.tool()
def moderator_add(live_chat_id: str, channel_id: str) -> str:
    """Add a moderator to a live chat."""
    try:
        return _ok(_get_client().moderators.add(live_chat_id, channel_id))
    except (StreamToolsError, Exception) as e:
        return _err(e)


@mcp.tool()
def moderator_remove(moderator_id: str) -> str:
    """Remove a moderator."""
    try:
        _get_client().moderators.remove(moderator_id)
        return f"Moderator {moderator_id} removed."
    except (StreamToolsError, Exception) as e:
        return _err(e)


# ── Bans ────────────────────────────────────────────────────────────────────

@mcp.tool()
def ban_add(live_chat_id: str, channel_id: str, ban_type: str = "permanent", duration: int = 0) -> str:
    """Ban a user from live chat. ban_type: permanent|temporary. Duration in seconds for temporary bans."""
    try:
        return _ok(_get_client().bans.ban(live_chat_id, channel_id, ban_type, duration or None))
    except (StreamToolsError, Exception) as e:
        return _err(e)


@mcp.tool()
def ban_remove(ban_id: str) -> str:
    """Remove a ban."""
    try:
        _get_client().bans.unban(ban_id)
        return f"Ban {ban_id} removed."
    except (StreamToolsError, Exception) as e:
        return _err(e)


# ── Channel ─────────────────────────────────────────────────────────────────

@mcp.tool()
def channel_info() -> str:
    """Get info about the authenticated YouTube channel."""
    try:
        result = _get_client().channels.get_mine()
        return _ok([c.to_dict() for c in result.items])
    except (StreamToolsError, Exception) as e:
        return _err(e)


def main():
    mcp.run()


if __name__ == "__main__":
    main()
