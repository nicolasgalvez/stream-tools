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


class QuotaExceededError(APIError):
    """Raised when the daily YouTube upload quota is spent.

    A subclass of `APIError` so existing blanket handlers keep working, but
    typed so a batch caller can stop the run cleanly instead of hammering an
    endpoint that will refuse every remaining item.
    """

    def __init__(
        self,
        message: str = "YouTube API quota exceeded",
        status_code: int | None = 403,
        reason: str | None = "quotaExceeded",
    ):
        super().__init__(message, status_code=status_code, reason=reason)


class UploadCommittedError(StreamToolsError):
    """Raised when an upload committed but the client never saw confirmation.

    Some environments intermittently fail with "Redirected but the response is
    missing a Location: header" *after* the insert has already succeeded. The
    video exists on the channel; retrying the insert creates a duplicate.

    Callers must treat this as "already uploaded, needs reconciling" — never as
    a failure to retry.

    Attributes:
        title: The title the upload was submitted with.
        video_id: The recovered video ID, or None if it could not be found.
        committed: Always True. The upload reached YouTube.
    """

    def __init__(self, title: str, video_id: str | None = None, message: str | None = None):
        self.title = title
        self.video_id = video_id
        self.committed = True
        super().__init__(
            message
            or (
                f"Upload of {title!r} committed but the response was lost"
                + (f"; recovered video id {video_id}" if video_id else "; video id not recovered")
                + ". Do not retry the insert - that creates a duplicate."
            )
        )
