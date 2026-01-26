"""Chat service for YouTube Live chat messages."""

from googleapiclient.errors import HttpError

from stream_tools.models.chat import ChatMessage
from stream_tools.models.common import PageResult
from stream_tools.services.base import BaseService


class ChatService(BaseService):
    """Operations for live chat messages.

    Wraps the `liveChatMessages` resource of the YouTube Data API v3.
    Requires a `live_chat_id` which is obtained from a broadcast's
    `live_chat_id` field.
    """

    def list_messages(
        self,
        live_chat_id: str,
        max_results: int = 200,
        page_token: str | None = None,
    ) -> PageResult[ChatMessage]:
        """List messages in a live chat.

        Args:
            live_chat_id: The chat ID from a broadcast's `live_chat_id` field.
            max_results: Maximum number of messages to return (1-2000).
            page_token: Token for fetching the next page of results.

        Returns:
            A paginated result containing ChatMessage objects.

        Raises:
            APIError: If the YouTube API request fails.
        """
        try:
            response = self.youtube.liveChatMessages().list(
                liveChatId=live_chat_id,
                part="snippet,authorDetails",
                maxResults=max_results,
                pageToken=page_token,
            ).execute()
        except HttpError as e:
            self._handle_api_error(e, "ChatMessage")

        items = [ChatMessage.from_api_response(item) for item in response.get("items", [])]
        page_info = response.get("pageInfo", {})

        return PageResult(
            items=items,
            next_page_token=response.get("nextPageToken"),
            total_results=page_info.get("totalResults", len(items)),
        )

    def send_message(self, live_chat_id: str, message: str) -> ChatMessage:
        """Send a text message to a live chat.

        Args:
            live_chat_id: The chat to send the message to.
            message: The message text to send.

        Returns:
            The created ChatMessage as confirmed by the API.

        Raises:
            APIError: If the YouTube API request fails (e.g. chat is disabled).
        """
        body = {
            "snippet": {
                "liveChatId": live_chat_id,
                "type": "textMessageEvent",
                "textMessageDetails": {
                    "messageText": message,
                },
            },
        }

        try:
            response = self.youtube.liveChatMessages().insert(
                part="snippet,authorDetails",
                body=body,
            ).execute()
        except HttpError as e:
            self._handle_api_error(e, "ChatMessage")

        return ChatMessage.from_api_response(response)

    def delete_message(self, message_id: str) -> None:
        """Delete a chat message.

        Only messages sent by the authenticated user or in chats
        the user moderates can be deleted.

        Args:
            message_id: The ID of the message to delete.

        Raises:
            NotFoundError: If the message does not exist.
            APIError: If the YouTube API request fails.
        """
        try:
            self.youtube.liveChatMessages().delete(id=message_id).execute()
        except HttpError as e:
            self._handle_api_error(e, "ChatMessage")
