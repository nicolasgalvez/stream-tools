"""Broadcast model for YouTube Live broadcasts."""

from dataclasses import dataclass
from datetime import datetime

from stream_tools.models.common import LifeCycleStatus, PrivacyStatus


@dataclass
class Broadcast:
    """Represents a YouTube Live broadcast.

    A broadcast is the public-facing event that viewers see.
    It must be bound to a stream (RTMP ingest) to go live.

    Attributes:
        id: Unique broadcast ID assigned by YouTube.
        title: Display title of the broadcast.
        description: Broadcast description text.
        scheduled_start: Planned start time, or None.
        scheduled_end: Planned end time, or None.
        actual_start: Actual start time (set when broadcast goes live), or None.
        actual_end: Actual end time (set when broadcast completes), or None.
        privacy: Visibility setting (public, unlisted, private).
        life_cycle_status: Current state in the broadcast lifecycle.
        live_chat_id: Chat ID for this broadcast's live chat, or None.
        bound_stream_id: The ID of the bound RTMP stream, or None.
    """

    id: str
    title: str
    description: str
    scheduled_start: datetime | None
    scheduled_end: datetime | None
    actual_start: datetime | None
    actual_end: datetime | None
    privacy: PrivacyStatus
    life_cycle_status: LifeCycleStatus
    live_chat_id: str | None
    bound_stream_id: str | None

    @classmethod
    def from_api_response(cls, data: dict) -> "Broadcast":
        """Parse a broadcast resource from the YouTube API response.

        Args:
            data: A single item from the `liveBroadcasts.list` API response.

        Returns:
            A Broadcast instance populated from the API data.
        """
        snippet = data.get("snippet", {})
        status = data.get("status", {})
        content_details = data.get("contentDetails", {})

        return cls(
            id=data["id"],
            title=snippet.get("title", ""),
            description=snippet.get("description", ""),
            scheduled_start=_parse_datetime(snippet.get("scheduledStartTime")),
            scheduled_end=_parse_datetime(snippet.get("scheduledEndTime")),
            actual_start=_parse_datetime(snippet.get("actualStartTime")),
            actual_end=_parse_datetime(snippet.get("actualEndTime")),
            privacy=PrivacyStatus(status.get("privacyStatus", "private")),
            life_cycle_status=LifeCycleStatus(status.get("lifeCycleStatus", "created")),
            live_chat_id=snippet.get("liveChatId"),
            bound_stream_id=content_details.get("boundStreamId"),
        )


def _parse_datetime(value: str | None) -> datetime | None:
    """Parse an ISO 8601 datetime string from the YouTube API.

    Args:
        value: An RFC 3339 timestamp string, or None.

    Returns:
        A timezone-aware datetime, or None if the input is empty.
    """
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))
