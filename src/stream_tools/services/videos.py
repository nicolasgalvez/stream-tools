"""Video service for YouTube Data API video operations."""

from __future__ import annotations

from pathlib import Path

from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

from stream_tools.models.common import PageResult
from stream_tools.models.video import Video
from stream_tools.services.base import BaseService


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
                status, response = request.next_chunk()
            return Video.from_api_response(response)
        except HttpError as e:
            self._handle_api_error(e, "Video")

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
            kwargs: dict = {
                "part": "snippet,status,statistics,contentDetails",
                "mine": True,
                "maxResults": max_results,
            }
            if page_token:
                kwargs["pageToken"] = page_token

            response = self.youtube.videos().list(**kwargs).execute()

            videos = [Video.from_api_response(item) for item in response.get("items", [])]
            return PageResult(
                items=videos,
                next_page_token=response.get("nextPageToken"),
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
            if privacy_status is not None:
                body["status"]["privacyStatus"] = privacy_status
            if publish_at is not None:
                body["status"]["publishAt"] = publish_at

            response = (
                self.youtube.videos()
                .update(part="snippet,status", body=body)
                .execute()
            )
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
