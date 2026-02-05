"""LiveStream model for YouTube RTMP streams."""

from dataclasses import dataclass, field

from stream_tools.models.common import (
    ConfigurationIssue,
    IssueSeverity,
    StreamFrameRate,
    StreamHealthStatus,
    StreamResolution,
)


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
        backup_ingestion_address: Backup RTMP server URL for dual streaming, or None.
        rtmps_ingestion_address: Secure RTMPS server URL, or None.
        rtmps_backup_ingestion_address: Backup secure RTMPS URL, or None.
        stream_name: Stream key for the RTMP URL, or None.
        health_status: Current health of the ingest connection, or None.
        configuration_issues: List of detected configuration issues.
        is_reusable: Whether this stream can be reused across broadcasts.
    """

    id: str
    title: str
    description: str
    resolution: StreamResolution | None
    frame_rate: StreamFrameRate | None
    ingestion_address: str | None
    backup_ingestion_address: str | None
    rtmps_ingestion_address: str | None
    rtmps_backup_ingestion_address: str | None
    stream_name: str | None
    health_status: StreamHealthStatus | None
    configuration_issues: list[ConfigurationIssue] = field(default_factory=list)
    is_reusable: bool = False

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

        # Parse configuration issues
        issues = []
        for issue_data in health.get("configurationIssues", []):
            issues.append(ConfigurationIssue(
                type=issue_data.get("type", "unknown"),
                severity=IssueSeverity(issue_data.get("severity", "info")),
                reason=issue_data.get("reason", ""),
                description=issue_data.get("description", ""),
            ))

        return cls(
            id=data["id"],
            title=snippet.get("title", ""),
            description=snippet.get("description", ""),
            resolution=StreamResolution(resolution_raw) if resolution_raw else None,
            frame_rate=StreamFrameRate(frame_rate_raw) if frame_rate_raw else None,
            ingestion_address=ingestion_info.get("ingestionAddress"),
            backup_ingestion_address=ingestion_info.get("backupIngestionAddress"),
            rtmps_ingestion_address=ingestion_info.get("rtmpsIngestionAddress"),
            rtmps_backup_ingestion_address=ingestion_info.get("rtmpsBackupIngestionAddress"),
            stream_name=ingestion_info.get("streamName"),
            health_status=(
                StreamHealthStatus(health.get("status")) if health.get("status") else None
            ),
            configuration_issues=issues,
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

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "resolution": self.resolution.value if self.resolution else None,
            "frame_rate": self.frame_rate.value if self.frame_rate else None,
            "ingestion_address": self.ingestion_address,
            "backup_ingestion_address": self.backup_ingestion_address,
            "rtmps_ingestion_address": self.rtmps_ingestion_address,
            "rtmps_backup_ingestion_address": self.rtmps_backup_ingestion_address,
            "stream_name": self.stream_name,
            "rtmp_url": self.rtmp_url,
            "health_status": self.health_status.value if self.health_status else None,
            "configuration_issues": [issue.to_dict() for issue in self.configuration_issues],
            "is_reusable": self.is_reusable,
        }
