"""Exception hierarchy for stream_tools."""


class StreamToolsError(Exception):
    """Base exception for all stream_tools errors.

    All exceptions raised by this library inherit from this class,
    so callers can catch `StreamToolsError` for blanket handling.
    """


class AuthenticationError(StreamToolsError):
    """Raised when authentication fails or credentials are missing.

    Common causes:
        - No cached token and no environment variables set.
        - Refresh token is expired or revoked.
        - Client secret file is missing.
    """


class APIError(StreamToolsError):
    """Raised when the YouTube API returns an error response.

    Attributes:
        status_code: HTTP status code from the API (e.g. 403, 500).
        reason: Machine-readable error reason from Google (e.g. "quotaExceeded").
    """

    def __init__(self, message: str, status_code: int | None = None, reason: str | None = None):
        self.status_code = status_code
        self.reason = reason
        super().__init__(message)


class SetupError(StreamToolsError):
    """Raised when project setup operations fail.

    This includes GCP project creation, API enablement,
    and OAuth credential configuration.
    """


class NotFoundError(APIError):
    """Raised when a requested resource is not found (HTTP 404).

    Attributes:
        resource_type: The type of resource (e.g. "Broadcast", "Stream").
        resource_id: The ID that was looked up.
    """

    def __init__(self, resource_type: str, resource_id: str):
        super().__init__(
            f"{resource_type} '{resource_id}' not found",
            status_code=404,
            reason="notFound",
        )
