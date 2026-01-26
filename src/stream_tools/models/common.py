"""Common enums and types used across models."""

from dataclasses import dataclass, field
from enum import Enum
from typing import TypeVar, Generic

T = TypeVar("T")


class PrivacyStatus(str, Enum):
    """YouTube resource privacy setting."""

    PUBLIC = "public"
    UNLISTED = "unlisted"
    PRIVATE = "private"


class BroadcastStatus(str, Enum):
    """Filter for listing broadcasts by their current state."""

    ALL = "all"
    ACTIVE = "active"
    COMPLETED = "completed"
    UPCOMING = "upcoming"


class LifeCycleStatus(str, Enum):
    """Broadcast lifecycle states.

    Flow: created -> ready -> testStarting -> testing -> liveStarting -> live -> complete.
    """

    COMPLETE = "complete"
    CREATED = "created"
    LIVE = "live"
    LIVE_STARTING = "liveStarting"
    READY = "ready"
    REVOKED = "revoked"
    TEST_STARTING = "testStarting"
    TESTING = "testing"


class StreamResolution(str, Enum):
    """Video resolution for RTMP stream ingest."""

    RES_240P = "240p"
    RES_360P = "360p"
    RES_480P = "480p"
    RES_720P = "720p"
    RES_1080P = "1080p"
    RES_1440P = "1440p"
    RES_2160P = "2160p"
    VARIABLE = "variable"


class StreamFrameRate(str, Enum):
    """Frame rate for RTMP stream ingest."""

    FPS_30 = "30fps"
    FPS_60 = "60fps"
    VARIABLE = "variable"


class StreamHealthStatus(str, Enum):
    """Health status of an active stream's ingest."""

    GOOD = "good"
    OK = "ok"
    BAD = "bad"
    NO_DATA = "noData"


@dataclass
class PageResult(Generic[T]):
    """Paginated result from the YouTube API.

    Attributes:
        items: The list of items in this page.
        next_page_token: Token to fetch the next page, or None if this is the last.
        prev_page_token: Token to fetch the previous page, or None if this is the first.
        total_results: Total number of items across all pages.
    """

    items: list[T] = field(default_factory=list)
    next_page_token: str | None = None
    prev_page_token: str | None = None
    total_results: int = 0
