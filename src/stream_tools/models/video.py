"""Video model for YouTube uploaded videos."""

from dataclasses import dataclass, field
from enum import Enum

from stream_tools.models.common import PrivacyStatus


class VideoLicense(str, Enum):
    """License under which a video is published."""

    YOUTUBE = "youtube"
    CREATIVE_COMMON = "creativeCommon"


@dataclass
class Video:
    """Represents a YouTube video resource.

    Attributes:
        id: Unique video ID.
        title: Video title.
        description: Video description.
        tags: List of keyword tags.
        category_id: YouTube video category ID.
        channel_id: Channel that uploaded the video.
        channel_title: Display name of the uploading channel.
        privacy_status: Visibility (public, unlisted, private).
        upload_status: Upload processing state.
        publish_at: Scheduled publish time (ISO 8601), or None.
        published_at: When the video was actually published.
        license: License type (youtube or creativeCommon).
        duration: ISO 8601 duration string (e.g. PT4M13S).
        view_count: Total views.
        like_count: Total likes.
        comment_count: Total comments.
        embeddable: Whether the video can be embedded externally.
        made_for_kids: Whether the video is designated as made for kids.
        default_language: Default language code (e.g. en).
        thumbnails: Dict of thumbnail size → URL.
    """

    id: str
    title: str = ""
    description: str = ""
    tags: list[str] = field(default_factory=list)
    category_id: str = ""
    channel_id: str = ""
    channel_title: str = ""
    privacy_status: PrivacyStatus | None = None
    upload_status: str = ""
    publish_at: str | None = None
    published_at: str | None = None
    license: VideoLicense | None = None
    duration: str = ""
    view_count: int = 0
    like_count: int = 0
    comment_count: int = 0
    embeddable: bool = True
    made_for_kids: bool = False
    default_language: str = ""
    thumbnails: dict = field(default_factory=dict)

    @classmethod
    def from_api_response(cls, data: dict) -> "Video":
        """Parse a video resource from the YouTube Data API response."""
        snippet = data.get("snippet", {})
        status = data.get("status", {})
        stats = data.get("statistics", {})
        content = data.get("contentDetails", {})

        privacy_raw = status.get("privacyStatus")
        license_raw = status.get("license")

        return cls(
            id=data["id"],
            title=snippet.get("title", ""),
            description=snippet.get("description", ""),
            tags=snippet.get("tags", []),
            category_id=snippet.get("categoryId", ""),
            channel_id=snippet.get("channelId", ""),
            channel_title=snippet.get("channelTitle", ""),
            privacy_status=PrivacyStatus(privacy_raw) if privacy_raw else None,
            upload_status=status.get("uploadStatus", ""),
            publish_at=status.get("publishAt"),
            published_at=snippet.get("publishedAt"),
            license=VideoLicense(license_raw) if license_raw else None,
            duration=content.get("duration", ""),
            view_count=int(stats.get("viewCount", 0)),
            like_count=int(stats.get("likeCount", 0)),
            comment_count=int(stats.get("commentCount", 0)),
            embeddable=status.get("embeddable", True),
            made_for_kids=status.get("madeForKids", False),
            default_language=snippet.get("defaultLanguage", ""),
            thumbnails=snippet.get("thumbnails", {}),
        )

    def to_api_body(self) -> dict:
        """Build the request body for videos.insert / videos.update.

        Only includes writable fields marked @mutable in the API schema.
        """
        body: dict = {"snippet": {}, "status": {}}

        body["snippet"]["title"] = self.title
        if self.description:
            body["snippet"]["description"] = self.description
        if self.tags:
            body["snippet"]["tags"] = self.tags
        if self.category_id:
            body["snippet"]["categoryId"] = self.category_id
        if self.default_language:
            body["snippet"]["defaultLanguage"] = self.default_language

        if self.privacy_status:
            body["status"]["privacyStatus"] = self.privacy_status.value
        if self.publish_at:
            body["status"]["publishAt"] = self.publish_at
        if self.license:
            body["status"]["license"] = self.license.value
        body["status"]["embeddable"] = self.embeddable
        body["status"]["selfDeclaredMadeForKids"] = self.made_for_kids

        return body

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization (formatting.output)."""
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "tags": self.tags,
            "category_id": self.category_id,
            "channel_id": self.channel_id,
            "channel_title": self.channel_title,
            "privacy_status": self.privacy_status.value if self.privacy_status else None,
            "upload_status": self.upload_status,
            "publish_at": self.publish_at,
            "published_at": self.published_at,
            "license": self.license.value if self.license else None,
            "duration": self.duration,
            "view_count": self.view_count,
            "like_count": self.like_count,
            "comment_count": self.comment_count,
            "embeddable": self.embeddable,
            "made_for_kids": self.made_for_kids,
            "default_language": self.default_language,
            "thumbnails": self.thumbnails,
        }
