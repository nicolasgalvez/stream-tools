"""Base service class with shared YouTube API resource access."""

from googleapiclient.discovery import Resource
from googleapiclient.errors import HttpError
from loguru import logger

from stream_tools.exceptions import APIError, NotFoundError


class BaseService:
    """Base class for all YouTube API services.

    Provides shared access to the YouTube API Resource and
    common error handling for HTTP errors.

    Args:
        youtube: A pre-built YouTube API Resource, decoupled from
            any specific auth strategy.
    """

    def __init__(self, youtube: Resource):
        self._youtube = youtube

    @property
    def youtube(self) -> Resource:
        """The underlying YouTube API Resource object."""
        return self._youtube

    def _handle_api_error(self, error: HttpError, resource_type: str = "Resource") -> None:
        """Convert an HttpError to the appropriate stream_tools exception.

        Args:
            error: The HttpError from the Google API client.
            resource_type: Human-readable name of the resource being accessed,
                used in error messages (e.g. "Broadcast", "Stream").

        Raises:
            NotFoundError: If the HTTP status is 404.
            APIError: For all other HTTP error statuses.
        """
        status = error.resp.status
        reason = error._get_reason()
        logger.debug("API error: status={}, reason={}, resource={}", status, reason, resource_type)

        if status == 404:
            raise NotFoundError(resource_type, "unknown") from error
        raise APIError(
            f"YouTube API error: {reason}",
            status_code=status,
            reason=reason,
        ) from error
