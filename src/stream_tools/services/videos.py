"""Video service for YouTube Data API video operations."""

from __future__ import annotations

import json
from pathlib import Path

from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload
from loguru import logger

from stream_tools.exceptions import (
    QuotaExceededError,
    ScheduleRefusedError,
    UploadCommittedError,
)
from stream_tools.models.common import PageResult, PrivacyStatus
from stream_tools.models.video import Video
from stream_tools.services.base import BaseService


def _check_schedulable(
    publish_at: str | None, privacy_status: str | PrivacyStatus | None
) -> None:
    """Refuse a publish time the platform would not honor.

    `publishAt` only means anything on a private video. Both call sites below
    documented that in their own docstrings and neither looked: `upload` built
    the body from whatever privacy it was handed, and `update` wrote
    `publishAt` without consulting the video's current status at all — so a
    publish time could be set on a video that was already public, and read back
    as scheduled.

    In one place so the CLI and the MCP server both get it. Two copies of a
    rule is how one of them comes to be missing it.
    """
    if publish_at is None or privacy_status is None:
        return
    # PrivacyStatus is a str enum, so a caller may hand over either. Normalized
    # here so the message reads "public" rather than "PrivacyStatus.PUBLIC".
    privacy = (
        privacy_status.value
        if isinstance(privacy_status, PrivacyStatus)
        else str(privacy_status)
    )
    if privacy == PrivacyStatus.PRIVATE.value:
        return
    raise ScheduleRefusedError(
        f"A publish time only works on a private video, and this one is "
        f"{privacy}. YouTube ignores publishAt on anything else, so "
        f"{publish_at} would not be a schedule -- it would be a video that is "
        f"{privacy} now. Upload it private and let the publish time make it "
        f"public, or drop the publish time."
    )


class VideoService(BaseService):
    """Service for uploading and managing YouTube videos."""

    def upload(
        self,
        file_path: str | Path,
        title: str,
        description: str = "",
        tags: list[str] | None = None,
        category_id: str = "",
        privacy_status: str = "private",
        publish_at: str | None = None,
        license: str = "youtube",
        made_for_kids: bool = False,
        default_language: str = "",
    ) -> Video:
        """Upload a video file to YouTube.

        Args:
            file_path: Path to the video file.
            title: Video title (required, max 100 chars).
            description: Video description (max 5000 chars).
            tags: List of keyword tags (max 500 chars total).
            category_id: YouTube category ID (e.g. "22" for People & Blogs).
            privacy_status: "private", "public", or "unlisted".
            publish_at: ISO 8601 datetime for scheduled publish (requires private).
            license: "youtube" (standard) or "creativeCommon".
            made_for_kids: Whether the video is directed at children.
            default_language: Language code (e.g. "en").

        Returns:
            The uploaded Video with YouTube-assigned ID.
        """
        # Before the file is even looked at: an upload is minutes of work, and
        # refusing after it has run is refusing too late.
        _check_schedulable(publish_at, privacy_status)

        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Video file not found: {path}")

        snippet: dict = {"title": title, "description": description, "tags": tags or []}
        if category_id:
            snippet["categoryId"] = category_id
        if default_language:
            snippet["defaultLanguage"] = default_language

        body = {
            "snippet": snippet,
            "status": {
                "privacyStatus": privacy_status,
                "embeddable": True,
                "license": license,
                "selfDeclaredMadeForKids": made_for_kids,
            },
        }
        if publish_at:
            body["status"]["publishAt"] = publish_at

        media = MediaFileUpload(str(path), mimetype="video/*", resumable=True)

        try:
            request = self.youtube.videos().insert(
                part="snippet,status",
                body=body,
                media_body=media,
            )
            response = None
            while response is None:
                _status, response = request.next_chunk()
            return Video.from_api_response(response)
        except HttpError as e:
            if _is_redirect_missing_location(e):
                raise self._committed_without_confirmation(title) from e
            if _is_quota_exceeded(e):
                raise QuotaExceededError() from e
            self._handle_api_error(e, "Video")
        except Exception as e:
            if _is_redirect_missing_location(e):
                raise self._committed_without_confirmation(title) from e
            raise

    def _committed_without_confirmation(self, title: str) -> UploadCommittedError:
        """Build the committed-upload error, recovering the video id if we can.

        Recovery is best-effort: failing to find the id must never hide the fact
        that the upload committed, because that fact is what stops a caller
        retrying and creating a duplicate.
        """
        return UploadCommittedError(title=title, video_id=self._find_video_id_by_title(title))

    def _uploads_playlist_id(self) -> str | None:
        """The playlist YouTube keeps of this channel's own uploads.

        `videos.list` has no `mine` parameter — that belongs to `search.list`,
        and passing it raises TypeError before a request is ever made. The
        documented route to a channel's own videos is the uploads playlist that
        `channels.list` reports.
        """
        response = self.youtube.channels().list(part="contentDetails", mine=True).execute()
        items = response.get("items", [])
        if not items:
            return None
        return items[0].get("contentDetails", {}).get("relatedPlaylists", {}).get("uploads")

    def _own_video_ids(
        self, max_results: int = 50, page_token: str | None = None
    ) -> tuple[list[str], str | None]:
        """Ids of this channel's videos, newest first, and the next page token."""
        playlist_id = self._uploads_playlist_id()
        if not playlist_id:
            return [], None

        kwargs: dict = {
            "part": "contentDetails",
            "playlistId": playlist_id,
            "maxResults": max_results,
        }
        if page_token:
            kwargs["pageToken"] = page_token

        response = self.youtube.playlistItems().list(**kwargs).execute()
        ids = [
            item["contentDetails"]["videoId"]
            for item in response.get("items", [])
            if item.get("contentDetails", {}).get("videoId")
        ]
        return ids, response.get("nextPageToken")

    def _find_video_id_by_title(self, title: str) -> str | None:
        """Find a video on this channel by exact title.

        Newly uploaded videos can take a moment to appear, so a miss here means
        "not found yet", not "not uploaded".
        """
        try:
            ids, _ = self._own_video_ids(max_results=50)
            if not ids:
                return None
            response = self.youtube.videos().list(part="snippet", id=",".join(ids)).execute()
            for item in response.get("items", []):
                if item.get("snippet", {}).get("title") == title:
                    return item.get("id")
        except Exception:  # noqa: BLE001 - best-effort id lookup; must degrade to None
            logger.warning("Could not look up {!r} to recover its id", title)
            return None
        return None

    def list(
        self,
        max_results: int = 25,
        page_token: str | None = None,
    ) -> PageResult[Video]:
        """List videos owned by the authenticated channel.

        Args:
            max_results: Max items per page (1-50).
            page_token: Token for pagination.

        Returns:
            PageResult containing Video items and pagination tokens.
        """
        try:
            ids, next_page_token = self._own_video_ids(
                max_results=max_results, page_token=page_token
            )
            if not ids:
                return PageResult(items=[], next_page_token=next_page_token, prev_page_token=None)

            response = (
                self.youtube.videos()
                .list(part="snippet,status,statistics,contentDetails", id=",".join(ids))
                .execute()
            )

            videos = [Video.from_api_response(item) for item in response.get("items", [])]
            return PageResult(
                items=videos,
                next_page_token=next_page_token,
                prev_page_token=response.get("prevPageToken"),
                total_results=response.get("pageInfo", {}).get("totalResults", 0),
            )
        except HttpError as e:
            self._handle_api_error(e, "Video")

    def get(self, video_id: str) -> Video:
        """Get a single video by ID.

        Args:
            video_id: The YouTube video ID.

        Returns:
            Video with full details.
        """
        try:
            response = (
                self.youtube.videos()
                .list(
                    part="snippet,status,statistics,contentDetails",
                    id=video_id,
                )
                .execute()
            )
            items = response.get("items", [])
            if not items:
                from stream_tools.exceptions import NotFoundError

                raise NotFoundError("Video", video_id)
            return Video.from_api_response(items[0])
        except HttpError as e:
            self._handle_api_error(e, "Video")

    def update(
        self,
        video_id: str,
        title: str | None = None,
        description: str | None = None,
        tags: list[str] | None = None,
        category_id: str | None = None,
        privacy_status: str | None = None,
        publish_at: str | None = None,
    ) -> Video:
        """Update metadata for an existing video.

        Only provided arguments are changed; others remain as-is.

        Args:
            video_id: The YouTube video ID.
            title: New title (max 100 chars).
            description: New description (max 5000 chars).
            tags: New tag list (replaces existing).
            category_id: New category ID.
            privacy_status: "private", "public", or "unlisted".
            publish_at: ISO 8601 datetime (requires privacy=private).

        Returns:
            Updated Video.
        """
        try:
            current = self.get(video_id)
            body = current.to_api_body()
            body["id"] = video_id

            if title is not None:
                body["snippet"]["title"] = title
            if description is not None:
                body["snippet"]["description"] = description
            if tags is not None:
                body["snippet"]["tags"] = tags
            if category_id is not None:
                body["snippet"]["categoryId"] = category_id
            # Against the privacy the video will have, not the one this call
            # names: setting only a publish time on a video that is already
            # public is the quiet way to get an ignored schedule.
            _check_schedulable(
                publish_at,
                privacy_status if privacy_status is not None else current.privacy_status,
            )

            if privacy_status is not None:
                body["status"]["privacyStatus"] = privacy_status
            if publish_at is not None:
                body["status"]["publishAt"] = publish_at

            response = self.youtube.videos().update(part="snippet,status", body=body).execute()
            return Video.from_api_response(response)
        except HttpError as e:
            self._handle_api_error(e, "Video")

    def delete(self, video_id: str) -> None:
        """Delete a video permanently.

        Args:
            video_id: The YouTube video ID.
        """
        try:
            self.youtube.videos().delete(id=video_id).execute()
        except HttpError as e:
            self._handle_api_error(e, "Video")

    def list_categories(self, region_code: str = "US") -> list[dict]:
        """List available video categories for a region.

        Args:
            region_code: ISO 3166-1 alpha-2 country code (e.g. "US", "GB", "JP").

        Returns:
            List of {"id": str, "title": str, "assignable": bool} dicts.
        """
        try:
            response = (
                self.youtube.videoCategories()
                .list(part="snippet", regionCode=region_code)
                .execute()
            )
            return [
                {
                    "id": item["id"],
                    "title": item["snippet"]["title"],
                    "assignable": item["snippet"].get("assignable", False),
                }
                for item in response.get("items", [])
            ]
        except HttpError as e:
            self._handle_api_error(e, "VideoCategory")


_REDIRECT_SIGNATURE = "redirected but the response is missing a location"


def _is_redirect_missing_location(error: Exception) -> bool:
    """Detect the post-commit redirect failure by its message.

    Matched on text because the client raises it from several types depending on
    the transport in use.
    """
    return _REDIRECT_SIGNATURE in str(error).lower()


def _is_quota_exceeded(error: HttpError) -> bool:
    """Detect a quotaExceeded reason in an API error payload."""
    content = getattr(error, "content", b"") or b""
    try:
        text = content.decode() if isinstance(content, bytes) else str(content)
        data = json.loads(text)
        for item in data.get("error", {}).get("errors", []):
            if item.get("reason") == "quotaExceeded":
                return True
    except (ValueError, AttributeError):
        pass
    return "quotaExceeded" in str(error)
