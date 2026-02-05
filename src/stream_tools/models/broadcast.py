"""Broadcast model for YouTube Live broadcasts."""

from dataclasses import dataclass, field
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
        recording_status: Whether broadcast is being recorded (recording, notRecording).
        made_for_kids: Whether the broadcast is designated as made for kids.
        self_declared_made_for_kids: Self-declared made for kids setting.
        live_chat_id: Chat ID for this broadcast's live chat, or None.
        bound_stream_id: The ID of the bound RTMP stream, or None.
        enable_auto_start: Whether broadcast starts when stream goes live.
        enable_auto_stop: Whether broadcast stops when stream ends.
        enable_dvr: Whether DVR (rewind) is enabled for viewers.
        enable_embed: Whether the broadcast can be embedded on other sites.
        enable_closed_captions: Whether closed captions are enabled.
        closed_captions_type: Type of closed captions (closedCaptionsDisabled, closedCaptionsHttpPost, closedCaptionsEmbedded).
        enable_low_latency: Whether low latency mode is enabled.
        latency_preference: Latency setting (normal, low, ultraLow).
        projection: Video projection type (rectangular, 360).
        record_from_start: Whether to record from the start.
        thumbnail_url: URL of the broadcast thumbnail (read-only, use thumbnail commands to change).
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
    recording_status: str | None
    made_for_kids: bool
    self_declared_made_for_kids: bool
    live_chat_id: str | None
    bound_stream_id: str | None
    enable_auto_start: bool
    enable_auto_stop: bool
    enable_dvr: bool
    enable_embed: bool
    enable_closed_captions: bool
    closed_captions_type: str | None
    enable_low_latency: bool
    latency_preference: str | None
    projection: str
    record_from_start: bool
    thumbnail_url: str | None = None

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
        thumbnails = snippet.get("thumbnails", {})

        # Get highest resolution thumbnail available
        thumbnail_url = None
        for size in ("maxres", "standard", "high", "medium", "default"):
            if size in thumbnails:
                thumbnail_url = thumbnails[size].get("url")
                break

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
            recording_status=status.get("recordingStatus"),
            made_for_kids=status.get("madeForKids", False),
            self_declared_made_for_kids=status.get("selfDeclaredMadeForKids", False),
            live_chat_id=snippet.get("liveChatId"),
            bound_stream_id=content_details.get("boundStreamId"),
            enable_auto_start=content_details.get("enableAutoStart", False),
            enable_auto_stop=content_details.get("enableAutoStop", False),
            enable_dvr=content_details.get("enableDvr", False),
            enable_embed=content_details.get("enableEmbed", True),
            enable_closed_captions=content_details.get("enableClosedCaptions", False),
            closed_captions_type=content_details.get("closedCaptionsType"),
            enable_low_latency=content_details.get("enableLowLatency", False),
            latency_preference=content_details.get("latencyPreference"),
            projection=content_details.get("projection", "rectangular"),
            record_from_start=content_details.get("recordFromStart", True),
            thumbnail_url=thumbnail_url,
        )

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "scheduled_start": self.scheduled_start.isoformat() if self.scheduled_start else None,
            "scheduled_end": self.scheduled_end.isoformat() if self.scheduled_end else None,
            "actual_start": self.actual_start.isoformat() if self.actual_start else None,
            "actual_end": self.actual_end.isoformat() if self.actual_end else None,
            "privacy": self.privacy.value,
            "life_cycle_status": self.life_cycle_status.value,
            "recording_status": self.recording_status,
            "made_for_kids": self.made_for_kids,
            "self_declared_made_for_kids": self.self_declared_made_for_kids,
            "live_chat_id": self.live_chat_id,
            "bound_stream_id": self.bound_stream_id,
            "enable_auto_start": self.enable_auto_start,
            "enable_auto_stop": self.enable_auto_stop,
            "enable_dvr": self.enable_dvr,
            "enable_embed": self.enable_embed,
            "enable_closed_captions": self.enable_closed_captions,
            "closed_captions_type": self.closed_captions_type,
            "enable_low_latency": self.enable_low_latency,
            "latency_preference": self.latency_preference,
            "projection": self.projection,
            "record_from_start": self.record_from_start,
            "thumbnail_url": self.thumbnail_url,
        }


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
