"""Stream service for YouTube Live streams (RTMP ingest)."""

from googleapiclient.errors import HttpError

from stream_tools.models.common import PageResult, StreamFrameRate, StreamResolution
from stream_tools.models.stream import LiveStream
from stream_tools.services.base import BaseService


class StreamService(BaseService):
    """CRUD operations for YouTube Live streams (RTMP ingest points).

    Wraps the `liveStreams` resource of the YouTube Data API v3.
    Each stream provides an RTMP URL that can be used with
    OBS, FFmpeg, or any streaming software.
    """

    def get(self, stream_id: str) -> LiveStream:
        """Get a single stream by ID.

        Args:
            stream_id: The ID of the stream to retrieve.

        Returns:
            The requested LiveStream.

        Raises:
            NotFoundError: If no stream exists with the given ID.
            APIError: If the YouTube API request fails.
        """
        try:
            response = self.youtube.liveStreams().list(
                part="snippet,cdn,status",
                id=stream_id,
            ).execute()
        except HttpError as e:
            self._handle_api_error(e, "Stream")

        items = response.get("items", [])
        if not items:
            from stream_tools.exceptions import NotFoundError
            raise NotFoundError("Stream", stream_id)

        return LiveStream.from_api_response(items[0])

    def list(
        self,
        max_results: int = 25,
        page_token: str | None = None,
    ) -> PageResult[LiveStream]:
        """List all live streams owned by the authenticated user.

        Args:
            max_results: Maximum number of items to return (1-50).
            page_token: Token for fetching the next page of results.

        Returns:
            A paginated result containing LiveStream objects.

        Raises:
            APIError: If the YouTube API request fails.
        """
        try:
            response = self.youtube.liveStreams().list(
                part="snippet,cdn,status",
                mine=True,
                maxResults=max_results,
                pageToken=page_token,
            ).execute()
        except HttpError as e:
            self._handle_api_error(e, "Stream")

        items = [LiveStream.from_api_response(item) for item in response.get("items", [])]
        page_info = response.get("pageInfo", {})

        return PageResult(
            items=items,
            next_page_token=response.get("nextPageToken"),
            prev_page_token=response.get("prevPageToken"),
            total_results=page_info.get("totalResults", len(items)),
        )

    def create(
        self,
        title: str,
        resolution: StreamResolution = StreamResolution.RES_1080P,
        frame_rate: StreamFrameRate = StreamFrameRate.FPS_30,
    ) -> LiveStream:
        """Create a new RTMP live stream.

        Args:
            title: Display title for the stream.
            resolution: Video resolution for the ingest (e.g. 1080p).
            frame_rate: Frame rate for the ingest (30fps or 60fps).

        Returns:
            The created LiveStream, including the RTMP URL for streaming software.

        Raises:
            APIError: If the YouTube API request fails.
        """
        body = {
            "snippet": {
                "title": title,
            },
            "cdn": {
                "ingestionType": "rtmp",
                "resolution": resolution.value,
                "frameRate": frame_rate.value,
            },
        }

        try:
            response = self.youtube.liveStreams().insert(
                part="snippet,cdn,status",
                body=body,
            ).execute()
        except HttpError as e:
            self._handle_api_error(e, "Stream")

        return LiveStream.from_api_response(response)

    def update(self, stream_id: str, title: str) -> LiveStream:
        """Update a stream's title.

        Fetches the current stream state first to preserve CDN settings.

        Args:
            stream_id: The ID of the stream to update.
            title: The new title for the stream.

        Returns:
            The updated LiveStream.

        Raises:
            NotFoundError: If no stream exists with the given ID.
            APIError: If the YouTube API request fails.
        """
        try:
            current = self.youtube.liveStreams().list(
                part="snippet,cdn,status",
                id=stream_id,
            ).execute()
        except HttpError as e:
            self._handle_api_error(e, "Stream")

        items = current.get("items", [])
        if not items:
            from stream_tools.exceptions import NotFoundError
            raise NotFoundError("Stream", stream_id)

        item = items[0]
        item["snippet"]["title"] = title

        try:
            response = self.youtube.liveStreams().update(
                part="snippet,cdn",
                body={"id": stream_id, "snippet": item["snippet"], "cdn": item["cdn"]},
            ).execute()
        except HttpError as e:
            self._handle_api_error(e, "Stream")

        return LiveStream.from_api_response(response)

    def delete(self, stream_id: str) -> None:
        """Delete a stream.

        Args:
            stream_id: The ID of the stream to delete.

        Raises:
            NotFoundError: If no stream exists with the given ID.
            APIError: If the YouTube API request fails.
        """
        try:
            self.youtube.liveStreams().delete(id=stream_id).execute()
        except HttpError as e:
            self._handle_api_error(e, "Stream")
