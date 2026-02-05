"""Broadcast service for YouTube Live broadcasts."""

from datetime import datetime, timedelta, timezone

from googleapiclient.errors import HttpError

from stream_tools.models.broadcast import Broadcast
from stream_tools.models.common import (
    BroadcastStatus,
    LifeCycleStatus,
    PageResult,
    PrivacyStatus,
)
from stream_tools.services.base import BaseService


class BroadcastService(BaseService):
    """CRUD operations for YouTube Live broadcasts.

    Wraps the `liveBroadcasts` resource of the YouTube Data API v3.
    """

    def get(self, broadcast_id: str) -> Broadcast:
        """Get a single broadcast by ID.

        Args:
            broadcast_id: The ID of the broadcast to retrieve.

        Returns:
            The requested Broadcast.

        Raises:
            NotFoundError: If no broadcast exists with the given ID.
            APIError: If the YouTube API request fails.
        """
        try:
            response = self.youtube.liveBroadcasts().list(
                part="snippet,status,contentDetails",
                id=broadcast_id,
            ).execute()
        except HttpError as e:
            self._handle_api_error(e, "Broadcast")

        items = response.get("items", [])
        if not items:
            from stream_tools.exceptions import NotFoundError
            raise NotFoundError("Broadcast", broadcast_id)

        return Broadcast.from_api_response(items[0])

    def list(
        self,
        status: BroadcastStatus = BroadcastStatus.ALL,
        max_results: int = 25,
        page_token: str | None = None,
    ) -> PageResult[Broadcast]:
        """List broadcasts filtered by status.

        Args:
            status: Filter broadcasts by lifecycle status.
            max_results: Maximum number of items to return (1-50).
            page_token: Token for fetching the next page of results.

        Returns:
            A paginated result containing Broadcast objects.

        Raises:
            APIError: If the YouTube API request fails.
        """
        try:
            request = self.youtube.liveBroadcasts().list(
                part="snippet,status,contentDetails",
                broadcastStatus=status.value,
                maxResults=max_results,
                pageToken=page_token,
            )
            response = request.execute()
        except HttpError as e:
            self._handle_api_error(e, "Broadcast")

        items = [Broadcast.from_api_response(item) for item in response.get("items", [])]
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
        scheduled_start: datetime | None = None,
        privacy: PrivacyStatus = PrivacyStatus.PRIVATE,
        description: str = "",
        enable_auto_start: bool = True,
        enable_auto_stop: bool = True,
        enable_dvr: bool = False,
        enable_embed: bool = True,
        enable_closed_captions: bool = False,
        closed_captions_type: str = "closedCaptionsDisabled",
        enable_low_latency: bool = False,
        latency_preference: str = "normal",
        projection: str = "rectangular",
        record_from_start: bool = True,
        made_for_kids: bool = False,
    ) -> Broadcast:
        """Create a new broadcast.

        Args:
            title: Display title for the broadcast.
            scheduled_start: When the broadcast is planned to go live.
                If None, defaults to now (immediately ready to go live).
            privacy: Visibility setting (public, unlisted, or private).
            description: Optional description text.
            enable_auto_start: Start broadcast when stream goes live (default True).
            enable_auto_stop: End broadcast when stream disconnects (default True).
                Set to False for long-running streams that may have brief disconnections.
            enable_dvr: Allow viewers to rewind/seek in the live stream (default False).
            enable_embed: Allow embedding on other sites (default True).
            enable_closed_captions: Enable closed captions (default False).
            closed_captions_type: Type of captions (closedCaptionsDisabled, closedCaptionsHttpPost, closedCaptionsEmbedded).
            enable_low_latency: Enable low latency mode (default False).
            latency_preference: Latency setting (normal, low, ultraLow).
            projection: Video projection (rectangular, 360).
            record_from_start: Record from the start (default True).
            made_for_kids: Whether the broadcast is made for kids (default False).

        Returns:
            The newly created Broadcast.

        Raises:
            APIError: If the YouTube API request fails.
        """
        # YouTube API requires scheduledStartTime to be in the future
        # Current time works - broadcast auto-starts when stream connects
        if scheduled_start is None:
            scheduled_start = datetime.now(timezone.utc)

        body = {
            "snippet": {
                "title": title,
                "description": description,
                "scheduledStartTime": scheduled_start.isoformat(),
            },
            "status": {
                "privacyStatus": privacy.value,
                "selfDeclaredMadeForKids": made_for_kids,
            },
            "contentDetails": {
                "enableAutoStart": enable_auto_start,
                "enableAutoStop": enable_auto_stop,
                "enableDvr": enable_dvr,
                "enableEmbed": enable_embed,
                "enableClosedCaptions": enable_closed_captions,
                "closedCaptionsType": closed_captions_type,
                "enableLowLatency": enable_low_latency,
                "latencyPreference": latency_preference,
                "projection": projection,
                "recordFromStart": record_from_start,
            },
        }

        try:
            response = self.youtube.liveBroadcasts().insert(
                part="snippet,status,contentDetails",
                body=body,
            ).execute()
        except HttpError as e:
            self._handle_api_error(e, "Broadcast")

        return Broadcast.from_api_response(response)

    def update(
        self,
        broadcast_id: str,
        title: str | None = None,
        description: str | None = None,
        privacy: PrivacyStatus | None = None,
    ) -> Broadcast:
        """Update an existing broadcast.

        Only the fields provided (non-None) are modified. The broadcast's
        current state is fetched first to preserve unchanged fields.

        Args:
            broadcast_id: The ID of the broadcast to update.
            title: New title, or None to keep current.
            description: New description, or None to keep current.
            privacy: New privacy status, or None to keep current.

        Returns:
            The updated Broadcast.

        Raises:
            NotFoundError: If no broadcast exists with the given ID.
            APIError: If the YouTube API request fails.
        """
        # Fetch current state first
        try:
            current = self.youtube.liveBroadcasts().list(
                part="snippet,status,contentDetails",
                id=broadcast_id,
            ).execute()
        except HttpError as e:
            self._handle_api_error(e, "Broadcast")

        items = current.get("items", [])
        if not items:
            from stream_tools.exceptions import NotFoundError
            raise NotFoundError("Broadcast", broadcast_id)

        item = items[0]
        snippet = item["snippet"]
        status = item["status"]

        if title is not None:
            snippet["title"] = title
        if description is not None:
            snippet["description"] = description
        if privacy is not None:
            status["privacyStatus"] = privacy.value

        body = {"id": broadcast_id, "snippet": snippet, "status": status}

        try:
            response = self.youtube.liveBroadcasts().update(
                part="snippet,status",
                body=body,
            ).execute()
        except HttpError as e:
            self._handle_api_error(e, "Broadcast")

        return Broadcast.from_api_response(response)

    def delete(self, broadcast_id: str) -> None:
        """Delete a broadcast.

        Args:
            broadcast_id: The ID of the broadcast to delete.

        Raises:
            NotFoundError: If no broadcast exists with the given ID.
            APIError: If the YouTube API request fails.
        """
        try:
            self.youtube.liveBroadcasts().delete(id=broadcast_id).execute()
        except HttpError as e:
            self._handle_api_error(e, "Broadcast")

    def bind(self, broadcast_id: str, stream_id: str) -> Broadcast:
        """Bind an RTMP stream to a broadcast.

        Once bound, the stream's video feed will be used for the broadcast.

        Args:
            broadcast_id: The broadcast to bind to.
            stream_id: The stream to use as the video source.

        Returns:
            The updated Broadcast with `bound_stream_id` set.

        Raises:
            APIError: If the YouTube API request fails.
        """
        try:
            response = self.youtube.liveBroadcasts().bind(
                part="snippet,status,contentDetails",
                id=broadcast_id,
                streamId=stream_id,
            ).execute()
        except HttpError as e:
            self._handle_api_error(e, "Broadcast")

        return Broadcast.from_api_response(response)

    def transition(self, broadcast_id: str, status: LifeCycleStatus) -> Broadcast:
        """Transition a broadcast to a new lifecycle status.

        Valid transitions: created -> testing -> live -> complete.

        Args:
            broadcast_id: The broadcast to transition.
            status: The target lifecycle status.

        Returns:
            The updated Broadcast reflecting the new status.

        Raises:
            APIError: If the transition is invalid or the API request fails.
        """
        try:
            response = self.youtube.liveBroadcasts().transition(
                part="snippet,status,contentDetails",
                id=broadcast_id,
                broadcastStatus=status.value,
            ).execute()
        except HttpError as e:
            self._handle_api_error(e, "Broadcast")

        return Broadcast.from_api_response(response)

    def set_thumbnail(self, broadcast_id: str, image_path: str) -> None:
        """Set a custom thumbnail for a broadcast.

        Args:
            broadcast_id: The broadcast to set the thumbnail for.
            image_path: Path to the image file (JPEG, PNG, GIF, BMP).

        Raises:
            APIError: If the YouTube API request fails.
        """
        from googleapiclient.http import MediaFileUpload

        media = MediaFileUpload(image_path, mimetype="image/jpeg", resumable=True)

        try:
            self.youtube.thumbnails().set(
                videoId=broadcast_id,
                media_body=media,
            ).execute()
        except HttpError as e:
            self._handle_api_error(e, "Thumbnail")
