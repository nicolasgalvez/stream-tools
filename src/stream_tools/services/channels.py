"""Channel service for listing YouTube channels."""

from dataclasses import dataclass

from googleapiclient.errors import HttpError

from stream_tools.services.base import BaseService


@dataclass
class Channel:
    """Represents a YouTube channel.

    Attributes:
        id: The channel's unique YouTube ID.
        title: Display name of the channel.
        description: Channel description text.
        custom_url: The channel's vanity URL handle (e.g. "@mychannel"), or None.
        is_live_streaming_enabled: Whether the channel has live streaming enabled.
    """

    id: str
    title: str
    description: str
    custom_url: str | None
    is_live_streaming_enabled: bool

    @classmethod
    def from_api_response(cls, data: dict) -> "Channel":
        """Parse a Channel from a YouTube API response dict.

        Args:
            data: A single item from the `channels.list` API response.
        """
        snippet = data.get("snippet", {})
        status = data.get("status", {})
        return cls(
            id=data["id"],
            title=snippet.get("title", ""),
            description=snippet.get("description", ""),
            custom_url=snippet.get("customUrl"),
            is_live_streaming_enabled=status.get("isLinked", False),
        )


class ChannelService(BaseService):
    """Operations for querying YouTube channels.

    Wraps the `channels` resource of the YouTube Data API v3.
    """

    def get_mine(self) -> Channel | None:
        """Get the authenticated user's own channel.

        Returns:
            The user's Channel, or None if no channel is linked to the account.

        Raises:
            APIError: If the YouTube API request fails.
        """
        try:
            response = self.youtube.channels().list(
                part="snippet,status",
                mine=True,
            ).execute()
        except HttpError as e:
            self._handle_api_error(e, "Channel")

        items = response.get("items", [])
        if not items:
            return None
        return Channel.from_api_response(items[0])

    def list_managed(self) -> list[Channel]:
        """List channels managed by the authenticated user.

        This includes brand account channels that the user has
        management access to.

        Returns:
            A list of Channel objects.

        Raises:
            APIError: If the YouTube API request fails.
        """
        try:
            response = self.youtube.channels().list(
                part="snippet,status",
                managedByMe=True,
                maxResults=50,
            ).execute()
        except HttpError as e:
            self._handle_api_error(e, "Channel")

        return [Channel.from_api_response(item) for item in response.get("items", [])]
