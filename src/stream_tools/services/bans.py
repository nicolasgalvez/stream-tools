"""Ban service for YouTube Live chat bans."""

from googleapiclient.errors import HttpError

from stream_tools.models.chat import ChatBan
from stream_tools.services.base import BaseService


class BanService(BaseService):
    """Operations for live chat bans.

    Wraps the `liveChatBans` resource of the YouTube Data API v3.
    Bans can be permanent or temporary (with a duration).
    """

    def ban(
        self,
        live_chat_id: str,
        channel_id: str,
        ban_type: str = "permanent",
        duration_seconds: int | None = None,
    ) -> ChatBan:
        """Ban a user from a live chat.

        Args:
            live_chat_id: The chat to ban the user from.
            channel_id: The YouTube channel ID of the user to ban.
            ban_type: Either "permanent" or "temporary".
            duration_seconds: Duration in seconds for temporary bans.
                Required when ban_type is "temporary".

        Returns:
            The created ChatBan.

        Raises:
            APIError: If the YouTube API request fails.
        """
        snippet: dict = {
            "liveChatId": live_chat_id,
            "type": ban_type,
            "bannedUserDetails": {
                "channelId": channel_id,
            },
        }

        if ban_type == "temporary" and duration_seconds is not None:
            snippet["banDurationSeconds"] = duration_seconds

        body = {"snippet": snippet}

        try:
            response = self.youtube.liveChatBans().insert(
                part="snippet",
                body=body,
            ).execute()
        except HttpError as e:
            self._handle_api_error(e, "Ban")

        return ChatBan.from_api_response(response)

    def unban(self, ban_id: str) -> None:
        """Remove a ban, restoring the user's chat access.

        Args:
            ban_id: The ban resource ID to remove.

        Raises:
            NotFoundError: If the ban does not exist.
            APIError: If the YouTube API request fails.
        """
        try:
            self.youtube.liveChatBans().delete(id=ban_id).execute()
        except HttpError as e:
            self._handle_api_error(e, "Ban")
