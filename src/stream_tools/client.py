"""Facade client aggregating all YouTube Live API services."""

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import Resource, build

from stream_tools.services.bans import BanService
from stream_tools.services.broadcasts import BroadcastService
from stream_tools.services.channels import ChannelService
from stream_tools.services.chat import ChatService
from stream_tools.services.moderators import ModeratorService
from stream_tools.services.streams import StreamService


class YouTubeLiveClient:
    """Main entry point for the YouTube Live Streaming API.

    Accepts a `google.oauth2.credentials.Credentials` object directly,
    decoupled from any specific auth strategy (CLI, web, env vars, etc.).
    All service properties are lazily initialized on first access.

    Args:
        credentials: A valid Google OAuth2 Credentials object with
            YouTube scopes granted.

    Example:
        ```python
        from google.oauth2.credentials import Credentials
        from stream_tools import YouTubeLiveClient

        creds = Credentials(token=..., refresh_token=..., ...)
        client = YouTubeLiveClient(creds)
        broadcasts = client.broadcasts.list()
        ```
    """

    def __init__(self, credentials: Credentials):
        self._credentials = credentials
        self._resource: Resource | None = None
        self._channels: ChannelService | None = None
        self._broadcasts: BroadcastService | None = None
        self._streams: StreamService | None = None
        self._chat: ChatService | None = None
        self._moderators: ModeratorService | None = None
        self._bans: BanService | None = None

    @property
    def youtube(self) -> Resource:
        """Lazily build and cache the YouTube API resource."""
        if self._resource is None:
            self._resource = build("youtube", "v3", credentials=self._credentials)
        return self._resource

    @property
    def channels(self) -> ChannelService:
        """Access channel operations (get authenticated channel info)."""
        if self._channels is None:
            self._channels = ChannelService(self.youtube)
        return self._channels

    @property
    def broadcasts(self) -> BroadcastService:
        """Access broadcast CRUD operations."""
        if self._broadcasts is None:
            self._broadcasts = BroadcastService(self.youtube)
        return self._broadcasts

    @property
    def streams(self) -> StreamService:
        """Access RTMP stream CRUD operations."""
        if self._streams is None:
            self._streams = StreamService(self.youtube)
        return self._streams

    @property
    def chat(self) -> ChatService:
        """Access live chat message operations."""
        if self._chat is None:
            self._chat = ChatService(self.youtube)
        return self._chat

    @property
    def moderators(self) -> ModeratorService:
        """Access live chat moderator operations."""
        if self._moderators is None:
            self._moderators = ModeratorService(self.youtube)
        return self._moderators

    @property
    def bans(self) -> BanService:
        """Access live chat ban operations."""
        if self._bans is None:
            self._bans = BanService(self.youtube)
        return self._bans
