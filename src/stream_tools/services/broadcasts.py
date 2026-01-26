"""Broadcast service for YouTube Live broadcasts."""

from datetime import datetime

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
        scheduled_start: datetime,
        privacy: PrivacyStatus = PrivacyStatus.PRIVATE,
        description: str = "",
    ) -> Broadcast:
        """Create a new broadcast.

        The broadcast is created with auto-start and auto-stop enabled.

        Args:
            title: Display title for the broadcast.
            scheduled_start: When the broadcast is planned to go live.
            privacy: Visibility setting (public, unlisted, or private).
            description: Optional description text.

        Returns:
            The newly created Broadcast.

        Raises:
            APIError: If the YouTube API request fails.
        """
        body = {
            "snippet": {
                "title": title,
                "description": description,
                "scheduledStartTime": scheduled_start.isoformat(),
            },
            "status": {
                "privacyStatus": privacy.value,
            },
            "contentDetails": {
                "enableAutoStart": True,
                "enableAutoStop": True,
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
