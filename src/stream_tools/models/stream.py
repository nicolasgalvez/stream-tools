"""LiveStream model for YouTube RTMP streams."""

from dataclasses import dataclass

from stream_tools.models.common import StreamFrameRate, StreamHealthStatus, StreamResolution


@dataclass
class LiveStream:
    """Represents a YouTube Live stream (RTMP ingest point).

    A stream provides the RTMP URL where streaming software sends video.
    It must be bound to a broadcast for the video to be visible to viewers.

    Attributes:
        id: Unique stream ID assigned by YouTube.
        title: Display title of the stream.
        description: Stream description text.
        resolution: Configured video resolution, or None.
        frame_rate: Configured frame rate, or None.
        ingestion_address: Base RTMP server URL, or None.
        stream_name: Stream key for the RTMP URL, or None.
        health_status: Current health of the ingest connection, or None.
        is_reusable: Whether this stream can be reused across broadcasts.
    """

    id: str
    title: str
    description: str
    resolution: StreamResolution | None
    frame_rate: StreamFrameRate | None
    ingestion_address: str | None
    stream_name: str | None
    health_status: StreamHealthStatus | None
    is_reusable: bool

    @classmethod
    def from_api_response(cls, data: dict) -> "LiveStream":
        """Parse a stream resource from the YouTube API response.

        Args:
            data: A single item from the `liveStreams.list` API response.

        Returns:
            A LiveStream instance populated from the API data.
        """
        snippet = data.get("snippet", {})
        cdn = data.get("cdn", {})
        ingestion_info = cdn.get("ingestionInfo", {})
        status = data.get("status", {})
        health = status.get("healthStatus", {})

        resolution_raw = cdn.get("resolution")
        frame_rate_raw = cdn.get("frameRate")

        return cls(
            id=data["id"],
            title=snippet.get("title", ""),
            description=snippet.get("description", ""),
            resolution=StreamResolution(resolution_raw) if resolution_raw else None,
            frame_rate=StreamFrameRate(frame_rate_raw) if frame_rate_raw else None,
            ingestion_address=ingestion_info.get("ingestionAddress"),
            stream_name=ingestion_info.get("streamName"),
            health_status=(
                StreamHealthStatus(health.get("status")) if health.get("status") else None
            ),
            is_reusable=cdn.get("isReusable", False),
        )

    @property
    def rtmp_url(self) -> str | None:
        """Full RTMP URL for OBS/streaming software.

        Combines the ingestion address and stream name into a complete URL.
        Returns None if either component is missing.
        """
        if self.ingestion_address and self.stream_name:
            return f"{self.ingestion_address}/{self.stream_name}"
        return None
