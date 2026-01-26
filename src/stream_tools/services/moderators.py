"""Moderator service for YouTube Live chat moderators."""

from googleapiclient.errors import HttpError

from stream_tools.models.chat import ChatModerator
from stream_tools.models.common import PageResult
from stream_tools.services.base import BaseService


class ModeratorService(BaseService):
    """Operations for live chat moderators.

    Wraps the `liveChatModerators` resource of the YouTube Data API v3.
    Moderators can delete messages and ban users in a live chat.
    """

    def list(
        self,
        live_chat_id: str,
        max_results: int = 25,
        page_token: str | None = None,
    ) -> PageResult[ChatModerator]:
        """List moderators for a live chat.

        Args:
            live_chat_id: The chat ID to list moderators for.
            max_results: Maximum number of moderators to return (1-50).
            page_token: Token for fetching the next page of results.

        Returns:
            A paginated result containing ChatModerator objects.

        Raises:
            APIError: If the YouTube API request fails.
        """
        try:
            response = self.youtube.liveChatModerators().list(
                liveChatId=live_chat_id,
                part="snippet",
                maxResults=max_results,
                pageToken=page_token,
            ).execute()
        except HttpError as e:
            self._handle_api_error(e, "Moderator")

        items = [ChatModerator.from_api_response(item) for item in response.get("items", [])]
        page_info = response.get("pageInfo", {})

        return PageResult(
            items=items,
            next_page_token=response.get("nextPageToken"),
            total_results=page_info.get("totalResults", len(items)),
        )

    def add(self, live_chat_id: str, channel_id: str) -> ChatModerator:
        """Add a moderator to a live chat.

        Args:
            live_chat_id: The chat to add the moderator to.
            channel_id: The YouTube channel ID of the user to make moderator.

        Returns:
            The created ChatModerator.

        Raises:
            APIError: If the YouTube API request fails.
        """
        body = {
            "snippet": {
                "liveChatId": live_chat_id,
                "moderatorDetails": {
                    "channelId": channel_id,
                },
            },
        }

        try:
            response = self.youtube.liveChatModerators().insert(
                part="snippet",
                body=body,
            ).execute()
        except HttpError as e:
            self._handle_api_error(e, "Moderator")

        return ChatModerator.from_api_response(response)

    def remove(self, moderator_id: str) -> None:
        """Remove a moderator from a live chat.

        Args:
            moderator_id: The moderator resource ID (not the channel ID).

        Raises:
            NotFoundError: If the moderator does not exist.
            APIError: If the YouTube API request fails.
        """
        try:
            self.youtube.liveChatModerators().delete(id=moderator_id).execute()
        except HttpError as e:
            self._handle_api_error(e, "Moderator")
