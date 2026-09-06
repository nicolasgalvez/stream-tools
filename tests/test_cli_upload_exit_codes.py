"""The CLI is a process boundary: typed exceptions do not survive it.

A caller that shells out to `yt` sees only an exit code and stdout, so the
distinction between "failed, safe to retry" and "committed, never retry" has to
be carried by the exit code. Collapsing both to 1 is how a batch caller creates
duplicates.
"""

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from stream_tools.exceptions import APIError, QuotaExceededError, UploadCommittedError
from stream_tools_cli.exit_codes import (
    EXIT_ERROR,
    EXIT_OK,
    EXIT_QUOTA_EXCEEDED,
    EXIT_UPLOAD_COMMITTED,
)
from stream_tools_cli.commands.videos import app

runner = CliRunner()


@pytest.fixture
def video_file(tmp_path):
    path = tmp_path / "clip.mp4"
    path.write_bytes(b"not-really-video")
    return str(path)


def invoke_upload(video_file, side_effect=None, return_value=None):
    client = MagicMock()
    if side_effect is not None:
        client.videos.upload.side_effect = side_effect
    else:
        video = MagicMock()
        video.id = return_value or "vid123"
        client.videos.upload.return_value = video
    with patch("stream_tools_cli.commands.videos.get_client", return_value=client):
        return runner.invoke(app, ["upload", video_file, "--title", "Loom (1990)"])


class TestExitCodes:
    def test_a_successful_upload_exits_zero(self, video_file):
        assert invoke_upload(video_file).exit_code == EXIT_OK

    def test_a_committed_upload_gets_its_own_exit_code(self, video_file):
        result = invoke_upload(
            video_file,
            side_effect=UploadCommittedError(title="Loom (1990)", video_id="abc123"),
        )

        assert result.exit_code == EXIT_UPLOAD_COMMITTED

    def test_a_committed_upload_is_not_reported_as_a_plain_failure(self, video_file):
        result = invoke_upload(
            video_file,
            side_effect=UploadCommittedError(title="Loom (1990)", video_id="abc123"),
        )

        assert result.exit_code != EXIT_ERROR

    def test_a_committed_upload_names_the_recovered_video_id(self, video_file):
        result = invoke_upload(
            video_file,
            side_effect=UploadCommittedError(title="Loom (1990)", video_id="abc123"),
        )

        assert "abc123" in result.output

    def test_a_committed_upload_says_not_to_retry(self, video_file):
        result = invoke_upload(
            video_file,
            side_effect=UploadCommittedError(title="Loom (1990)", video_id="abc123"),
        )

        assert "not retry" in result.output.lower() or "do not retry" in result.output.lower()

    def test_quota_exhaustion_gets_its_own_exit_code(self, video_file):
        result = invoke_upload(video_file, side_effect=QuotaExceededError())

        assert result.exit_code == EXIT_QUOTA_EXCEEDED

    def test_an_ordinary_api_error_still_exits_one(self, video_file):
        # Unchanged, so existing callers and scripts keep working.
        result = invoke_upload(video_file, side_effect=APIError("boom", status_code=500))

        assert result.exit_code == EXIT_ERROR

    def test_the_four_exit_codes_are_distinct(self):
        codes = {EXIT_OK, EXIT_ERROR, EXIT_UPLOAD_COMMITTED, EXIT_QUOTA_EXCEEDED}

        assert len(codes) == 4


class TestMachineReadableOutput:
    """The video_id line is a contract with callers, not display text."""

    @pytest.mark.parametrize(
        "video_id", ["abc123XYZ_-", "12345678901", "-1234567890", "0x12345678"]
    )
    def test_the_video_id_line_carries_no_escape_codes(self, video_file, video_id):
        # Rich highlights anything that looks numeric. A caller parsing the id
        # would capture the escape codes with it and store a corrupted id.
        result = invoke_upload(
            video_file,
            side_effect=UploadCommittedError(title="Loom (1990)", video_id=video_id),
        )

        line = next(l for l in result.output.splitlines() if l.startswith("video_id:"))
        assert "\x1b" not in line
        assert line == f"video_id: {video_id}"
