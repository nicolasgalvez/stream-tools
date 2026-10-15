"""Taking back a scheduled publish time.

Updating a video keeps the publish time it already has, so a scheduled video
still goes public on its date even after the caller makes it private. There was
no way to clear it short of a one-off script against the API. These tests pin
the supported path at its three seams: the library, the `yt` command, and the
MCP tool.
"""

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from stream_tools.exceptions import ScheduleRefusedError
from stream_tools.services.videos import VideoService
from stream_tools_cli.commands.videos import app
from stream_tools_mcp import server
from tests.test_upload_contract import strip

WHEN = "2030-01-06T20:00:00Z"
LATER = "2031-02-03T04:05:06Z"


@pytest.fixture
def mock_youtube():
    return MagicMock()


@pytest.fixture
def videos(mock_youtube):
    return VideoService(mock_youtube)


def scheduled(mock_youtube, privacy="private", publish_at=WHEN):
    """A video on the channel that has a publish time."""
    mock_youtube.videos.return_value.list.return_value.execute.return_value = {
        "items": [
            {
                "id": "abc123",
                "snippet": {"title": "t", "description": "", "tags": []},
                "status": {"privacyStatus": privacy, "publishAt": publish_at},
            }
        ]
    }
    mock_youtube.videos.return_value.update.return_value.execute.return_value = {
        "id": "abc123",
        "snippet": {"title": "t"},
        "status": {"privacyStatus": privacy},
    }


def sent_body(mock_youtube):
    return mock_youtube.videos.return_value.update.call_args.kwargs["body"]


class TestLibrary:
    def test_clearing_leaves_no_publish_time_in_the_update(self, videos, mock_youtube):
        scheduled(mock_youtube)

        videos.update("abc123", clear_publish_at=True)

        assert "publishAt" not in sent_body(mock_youtube)["status"]

    def test_clearing_keeps_the_video_private(self, videos, mock_youtube):
        scheduled(mock_youtube)

        videos.update("abc123", clear_publish_at=True)

        assert sent_body(mock_youtube)["status"]["privacyStatus"] == "private"

    def test_clearing_and_setting_a_publish_time_is_refused(self, videos, mock_youtube):
        scheduled(mock_youtube)

        with pytest.raises(ScheduleRefusedError):
            videos.update("abc123", publish_at=LATER, clear_publish_at=True)

    def test_the_refusal_is_one_line(self, videos, mock_youtube):
        scheduled(mock_youtube)

        with pytest.raises(ScheduleRefusedError) as caught:
            videos.update("abc123", publish_at=LATER, clear_publish_at=True)

        assert "\n" not in str(caught.value)

    def test_the_refusal_sends_no_request_at_all(self, videos, mock_youtube):
        scheduled(mock_youtube)

        with pytest.raises(ScheduleRefusedError):
            videos.update("abc123", publish_at=LATER, clear_publish_at=True)

        assert mock_youtube.mock_calls == []

    def test_an_ordinary_update_still_carries_the_existing_publish_time(
        self, videos, mock_youtube
    ):
        scheduled(mock_youtube)

        videos.update("abc123", title="new title")

        assert sent_body(mock_youtube)["status"]["publishAt"] == WHEN


runner = CliRunner()


def invoke_update(*args, client=None):
    client = client or MagicMock()
    with patch("stream_tools_cli.commands.videos.get_client", return_value=client):
        return runner.invoke(app, ["update", "abc123", *args]), client


class TestCli:
    def test_the_option_reaches_the_library(self):
        result, client = invoke_update("--clear-publish-at")

        assert result.exit_code == 0, result.output
        assert client.videos.update.call_args.kwargs["clear_publish_at"] is True

    def test_it_is_off_unless_asked_for(self):
        _, client = invoke_update("--title", "x")

        assert client.videos.update.call_args.kwargs["clear_publish_at"] is False

    def test_the_combined_request_exits_1_with_the_error_line(self, mock_youtube):
        scheduled(mock_youtube)
        client = MagicMock()
        client.videos = VideoService(mock_youtube)

        result, _ = invoke_update(
            "--publish-at", LATER, "--clear-publish-at", client=client
        )

        assert result.exit_code == 1
        assert "Error: Cannot set a publish time and clear it" in strip(result.output)
        assert mock_youtube.mock_calls == []

    def test_the_option_is_documented_in_help(self):
        result = runner.invoke(app, ["update", "--help"])

        # CI forces color, and Rich splits the option name across escape codes.
        assert "--clear-publish-at" in strip(result.output)


class TestMcp:
    def test_the_tool_passes_the_option_through(self):
        client = MagicMock()
        client.videos.update.return_value = MagicMock(to_dict=lambda: {"id": "abc123"})
        with patch.object(server, "_get_client", return_value=client):
            server.video_update("abc123", clear_publish_at=True)

        assert client.videos.update.call_args.kwargs["clear_publish_at"] is True

    def test_it_is_off_unless_asked_for(self):
        client = MagicMock()
        client.videos.update.return_value = MagicMock(to_dict=lambda: {"id": "abc123"})
        with patch.object(server, "_get_client", return_value=client):
            server.video_update("abc123", title="x")

        assert client.videos.update.call_args.kwargs["clear_publish_at"] is False

    def test_the_combined_request_comes_back_as_an_error_and_sends_nothing(self, mock_youtube):
        scheduled(mock_youtube)
        client = MagicMock()
        client.videos = VideoService(mock_youtube)
        with patch.object(server, "_get_client", return_value=client):
            reply = server.video_update("abc123", publish_at=LATER, clear_publish_at=True)

        assert reply.startswith("Error: Cannot set a publish time and clear it")
        assert mock_youtube.mock_calls == []
