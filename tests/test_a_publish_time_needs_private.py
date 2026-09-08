"""A scheduled publish time only means something on a private video.

YouTube honors `status.publishAt` while `status.privacyStatus` is `private` and
not otherwise. Both service methods said so in their own docstrings and neither
looked: `upload` built the body from whatever privacy it was handed, and
`update` wrote `publishAt` without consulting the video's current status at all.

Sent anyway it goes one of two ways, and neither is good: the request is
rejected and the caller gets an HttpError about a field they did not think they
were setting, or it is accepted and ignored and a video meant to go out on a
date is simply public now.
"""

from unittest.mock import MagicMock

import pytest

from stream_tools.exceptions import ScheduleRefusedError, StreamToolsError
from stream_tools.models.common import PrivacyStatus
from stream_tools.services.videos import VideoService

WHEN = "2030-01-06T20:00:00Z"


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


def uploaded(mock_youtube):
    """A successful resumable upload, so the happy path can be asserted on."""
    request = MagicMock()
    request.next_chunk.return_value = (
        None,
        {"id": "abc123", "snippet": {"title": "t"}, "status": {"privacyStatus": "private"}},
    )
    mock_youtube.videos.return_value.insert.return_value = request
    return request


def existing(mock_youtube, privacy):
    """A video already on the channel with the given privacy."""
    mock_youtube.videos.return_value.list.return_value.execute.return_value = {
        "items": [
            {
                "id": "abc123",
                "snippet": {"title": "t", "description": "", "tags": []},
                "status": {"privacyStatus": privacy},
            }
        ]
    }
    mock_youtube.videos.return_value.update.return_value.execute.return_value = {
        "id": "abc123",
        "snippet": {"title": "t"},
        "status": {"privacyStatus": privacy},
    }


class TestUploading:
    def test_a_publish_time_on_a_public_upload_is_refused(self, videos, video_file):
        with pytest.raises(ScheduleRefusedError):
            videos.upload(video_file, title="t", privacy_status="public", publish_at=WHEN)

    def test_the_message_names_both_things_the_caller_asked_for(self, videos, video_file):
        with pytest.raises(ScheduleRefusedError) as caught:
            videos.upload(video_file, title="t", privacy_status="public", publish_at=WHEN)

        assert WHEN in str(caught.value)
        assert "public" in str(caught.value)

    def test_and_says_which_of_the_two_to_change(self, videos, video_file):
        with pytest.raises(ScheduleRefusedError, match="Upload it private"):
            videos.upload(video_file, title="t", privacy_status="public", publish_at=WHEN)

    def test_unlisted_is_refused_too(self, videos, video_file):
        with pytest.raises(ScheduleRefusedError, match="unlisted"):
            videos.upload(video_file, title="t", privacy_status="unlisted", publish_at=WHEN)

    def test_nothing_is_uploaded_when_it_is_refused(self, videos, video_file, mock_youtube):
        # An upload is minutes of work. Refusing after it has run is refusing
        # too late, so this must happen before the file is even opened.
        with pytest.raises(ScheduleRefusedError):
            videos.upload(video_file, title="t", privacy_status="public", publish_at=WHEN)

        mock_youtube.videos.return_value.insert.assert_not_called()

    def test_a_private_upload_with_a_publish_time_carries_both(
        self, videos, video_file, mock_youtube
    ):
        # What the scheduler does on every single upload. If this ever fails,
        # the guard has eaten the thing it was meant to protect.
        uploaded(mock_youtube)

        videos.upload(video_file, title="t", privacy_status="private", publish_at=WHEN)

        body = mock_youtube.videos.return_value.insert.call_args.kwargs["body"]
        assert body["status"]["privacyStatus"] == "private"
        assert body["status"]["publishAt"] == WHEN

    def test_a_public_upload_with_no_publish_time_is_fine(
        self, videos, video_file, mock_youtube
    ):
        uploaded(mock_youtube)

        videos.upload(video_file, title="t", privacy_status="public")

        body = mock_youtube.videos.return_value.insert.call_args.kwargs["body"]
        assert "publishAt" not in body["status"]


class TestUpdating:
    def test_scheduling_while_going_public_in_the_same_call_is_refused(
        self, videos, mock_youtube
    ):
        existing(mock_youtube, "private")

        with pytest.raises(ScheduleRefusedError):
            videos.update("abc123", privacy_status="public", publish_at=WHEN)

    def test_scheduling_a_video_that_is_already_public_is_refused(self, videos, mock_youtube):
        # The quiet one. Nothing in the call says "public" — the video does —
        # and before this it went out and was ignored.
        existing(mock_youtube, "public")

        with pytest.raises(ScheduleRefusedError, match="public"):
            videos.update("abc123", publish_at=WHEN)

    def test_nothing_is_written_when_it_is_refused(self, videos, mock_youtube):
        existing(mock_youtube, "public")

        with pytest.raises(ScheduleRefusedError):
            videos.update("abc123", publish_at=WHEN)

        mock_youtube.videos.return_value.update.assert_not_called()

    def test_scheduling_a_private_video_still_works(self, videos, mock_youtube):
        existing(mock_youtube, "private")

        videos.update("abc123", publish_at=WHEN)

        body = mock_youtube.videos.return_value.update.call_args.kwargs["body"]
        assert body["status"]["publishAt"] == WHEN

    def test_making_a_video_public_without_scheduling_it_still_works(
        self, videos, mock_youtube
    ):
        existing(mock_youtube, "private")

        videos.update("abc123", privacy_status="public")

        body = mock_youtube.videos.return_value.update.call_args.kwargs["body"]
        assert body["status"]["privacyStatus"] == "public"


class TestTheRefusalItself:
    def test_it_is_a_stream_tools_error_so_the_cli_prints_it(self):
        # The CLI catches StreamToolsError and prints one red line. A plain
        # ValueError would reach the user as a traceback instead.
        assert issubclass(ScheduleRefusedError, StreamToolsError)

    def test_a_privacy_enum_reads_as_its_value_in_the_message(self, videos, video_file):
        # Callers hand over either a string or the enum; "PrivacyStatus.PUBLIC"
        # in an error message is a leak of how this is built.
        with pytest.raises(ScheduleRefusedError) as caught:
            videos.upload(
                video_file, title="t", privacy_status=PrivacyStatus.PUBLIC, publish_at=WHEN
            )

        assert "PrivacyStatus" not in str(caught.value)
