"""CLI command groups."""

from loguru import logger

from stream_tools.auth.oauth import OAuthManager
from stream_tools.client import YouTubeLiveClient


def get_client() -> YouTubeLiveClient:
    """Authenticate via OAuthManager and return a YouTubeLiveClient."""
    auth = OAuthManager()
    method = auth.auto_authenticate()
    logger.debug("Authenticated via {}", method.value)
    return YouTubeLiveClient(auth.credentials)
