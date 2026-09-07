"""YouTube upload quirks that belong in the library, not in a caller's fork.

`scripts/upload-batch` learned these the hard way; every future caller would
otherwise hit the same traps.
"""

import json
from unittest.mock import MagicMock

import pytest
from googleapiclient.errors import HttpError

from stream_tools.exceptions import APIError, QuotaExceededError, UploadCommittedError
from stream_tools.services.videos import VideoService

REDIRECT_MESSAGE = "Redirected but the response is missing a Location: header."


@pytest.fixture
def mock_youtube():
    return MagicMock()


@pytest.fixture
def videos(mock_youtube):
    return VideoService(mock_youtube)


@pytest.fixture
def video_file(tmp_path):
    path = tmp_path / "clip.mp4"
    path.write_bytes(b"not-really-video")
    return str(path)


def insert_raises(mock_youtube, error):
    """Make the resumable upload fail on next_chunk, as it does in the wild."""
    request = MagicMock()
    request.next_chunk.side_effect = error
    mock_youtube.videos.return_value.insert.return_value = request
    return request


def quota_error():
    resp = MagicMock()
    resp.status = 403
    content = json.dumps(
        {
            "error": {
                "code": 403,
                "message": "The request cannot be completed because you have exceeded your quota.",
                "errors": [{"reason": "quotaExceeded", "message": "quota"}],
            }
        }
    ).encode()
    return HttpError(resp, content)


def channel_lists(mock_youtube, titles):
    """The channel's existing videos, as the API really reports them.

    Through the uploads playlist, not `videos().list(mine=True)`. This helper
    used to mock the latter, which is why the recovery path passed its tests for
    months while raising TypeError against the real API on every call: there is
    no `mine` parameter on `videos.list`. A mock that accepts a call the service
    rejects tests nothing.
    """
    mock_youtube.channels.return_value.list.return_value.execute.return_value = {
        "items": [{"contentDetails": {"relatedPlaylists": {"uploads": "UUtest"}}}]
    }
    mock_youtube.playlistItems.return_value.list.return_value.execute.return_value = {
        "items": [{"contentDetails": {"videoId": f"id-{i}"}} for i, _ in enumerate(titles)]
    }
    mock_youtube.videos.return_value.list.return_value.execute.return_value = {
        "items": [
            {"id": f"id-{i}", "snippet": {"title": t}, "status": {"privacyStatus": "private"}}
            for i, t in enumerate(titles)
        ],
        "pageInfo": {"totalResults": len(titles)},
    }


class TestQuotaExceeded:
    def test_quota_failure_raises_a_typed_error(self, videos, mock_youtube, video_file):
        insert_raises(mock_youtube, quota_error())

        with pytest.raises(QuotaExceededError):
            videos.upload(video_file, title="Anything")

    def test_quota_error_is_still_an_api_error(self, videos, mock_youtube, video_file):
        # Existing callers catch APIError; typing it must not break them.
        insert_raises(mock_youtube, quota_error())

        with pytest.raises(APIError):
            videos.upload(video_file, title="Anything")

    def test_quota_error_keeps_the_reason(self, videos, mock_youtube, video_file):
        insert_raises(mock_youtube, quota_error())

        with pytest.raises(QuotaExceededError) as caught:
            videos.upload(video_file, title="Anything")
        assert caught.value.reason == "quotaExceeded"


class TestRedirectMissingLocation:
    """The upload COMMITS, then the client errors on the response."""

    def test_raises_upload_committed_not_a_generic_error(self, videos, mock_youtube, video_file):
        insert_raises(mock_youtube, Exception(REDIRECT_MESSAGE))
        channel_lists(mock_youtube, [])

        with pytest.raises(UploadCommittedError):
            videos.upload(video_file, title="Loom (1990)")

    def test_the_insert_is_not_retried(self, videos, mock_youtube, video_file):
        # Retrying is what creates duplicates. Exactly one insert, ever.
        request = insert_raises(mock_youtube, Exception(REDIRECT_MESSAGE))
        channel_lists(mock_youtube, [])

        with pytest.raises(UploadCommittedError):
            videos.upload(video_file, title="Loom (1990)")

        assert mock_youtube.videos.return_value.insert.call_count == 1
        assert request.next_chunk.call_count == 1

    def test_recovers_the_new_video_id_by_title(self, videos, mock_youtube, video_file):
        insert_raises(mock_youtube, Exception(REDIRECT_MESSAGE))
        channel_lists(mock_youtube, ["Something Else", "Loom (1990)"])

        with pytest.raises(UploadCommittedError) as caught:
            videos.upload(video_file, title="Loom (1990)")

        assert caught.value.video_id == "id-1"

    def test_says_it_committed_even_when_the_id_cannot_be_recovered(
        self, videos, mock_youtube, video_file
    ):
        insert_raises(mock_youtube, Exception(REDIRECT_MESSAGE))
        channel_lists(mock_youtube, [])

        with pytest.raises(UploadCommittedError) as caught:
            videos.upload(video_file, title="Loom (1990)")

        assert caught.value.video_id is None
        assert caught.value.committed is True

    def test_recovery_failure_does_not_mask_the_committed_signal(
        self, videos, mock_youtube, video_file
    ):
        # Even if looking the video up blows up, the caller must still learn
        # that the upload committed — that is the fact that prevents a retry.
        insert_raises(mock_youtube, Exception(REDIRECT_MESSAGE))
        mock_youtube.videos.return_value.list.side_effect = RuntimeError("network gone")

        with pytest.raises(UploadCommittedError) as caught:
            videos.upload(video_file, title="Loom (1990)")

        assert caught.value.committed is True

    def test_an_unrelated_error_is_not_misclassified_as_committed(
        self, videos, mock_youtube, video_file
    ):
        insert_raises(mock_youtube, ValueError("something else entirely"))

        with pytest.raises(ValueError):
            videos.upload(video_file, title="Loom (1990)")
