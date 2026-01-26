"""Chat models for YouTube Live chat."""

from dataclasses import dataclass
from datetime import datetime


@dataclass
class ChatMessage:
    """A live chat message.

    Attributes:
        id: Unique message ID.
        author_channel_id: YouTube channel ID of the message author.
        author_display_name: Display name of the message author.
        message_text: The text content of the message.
        published_at: When the message was sent.
        type: Message type (e.g. "textMessageEvent", "superChatEvent").
    """

    id: str
    author_channel_id: str
    author_display_name: str
    message_text: str
    published_at: datetime
    type: str

    @classmethod
    def from_api_response(cls, data: dict) -> "ChatMessage":
        """Parse a ChatMessage from a YouTube API response dict.

        Args:
            data: A single item from the `liveChatMessages.list` API response.
        """
        snippet = data.get("snippet", {})
        author = data.get("authorDetails", {})
        message_details = snippet.get("textMessageDetails", {})

        published = snippet.get("publishedAt", "")
        return cls(
            id=data["id"],
            author_channel_id=author.get("channelId", ""),
            author_display_name=author.get("displayName", ""),
            message_text=message_details.get("messageText", ""),
            published_at=datetime.fromisoformat(published.replace("Z", "+00:00")) if published else datetime.min,
            type=snippet.get("type", "textMessageEvent"),
        )


@dataclass
class ChatModerator:
    """A live chat moderator.

    Attributes:
        id: The moderator resource ID (used for removal).
        channel_id: YouTube channel ID of the moderator.
        display_name: Display name of the moderator.
    """

    id: str
    channel_id: str
    display_name: str

    @classmethod
    def from_api_response(cls, data: dict) -> "ChatModerator":
        """Parse a ChatModerator from a YouTube API response dict.

        Args:
            data: A single item from the `liveChatModerators.list` API response.
        """
        snippet = data.get("snippet", {})
        moderator_details = snippet.get("moderatorDetails", {})
        return cls(
            id=data["id"],
            channel_id=moderator_details.get("channelId", ""),
            display_name=moderator_details.get("displayName", ""),
        )


@dataclass
class ChatBan:
    """A live chat ban.

    Attributes:
        id: The ban resource ID (used for removal).
        channel_id: YouTube channel ID of the banned user.
        ban_type: Either "permanent" or "temporary".
        ban_duration_seconds: Duration for temporary bans, or None for permanent.
    """

    id: str
    channel_id: str
    ban_type: str
    ban_duration_seconds: int | None

    @classmethod
    def from_api_response(cls, data: dict) -> "ChatBan":
        """Parse a ChatBan from a YouTube API response dict.

        Args:
            data: A single item from the `liveChatBans.insert` API response.
        """
        snippet = data.get("snippet", {})
        banned_user = snippet.get("bannedUserDetails", {})
        return cls(
            id=data["id"],
            channel_id=banned_user.get("channelId", ""),
            ban_type=snippet.get("type", "permanent"),
            ban_duration_seconds=snippet.get("banDurationSeconds"),
        )
