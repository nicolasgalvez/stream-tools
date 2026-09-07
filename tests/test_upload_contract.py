"""The parts of the upload contract that are Click's behavior, not ours.

`tests/test_cli_upload_exit_codes.py` pins the exit codes this CLI chooses.
These pin two things it inherits, which is why nobody reviewing a change here
would think to check them.

schedule-tools' `YtCliPublisher` is the caller. It shells out, so all it gets is
an exit code and stdout.
"""

import json
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from stream_tools.exceptions import UploadCommittedError
from stream_tools_cli.commands.videos import app
from stream_tools_cli.exit_codes import EXIT_OK, EXIT_UPLOAD_COMMITTED
from stream_tools_cli.state import OutputFormat, config

runner = CliRunner()

# Click prints this on every usage error. schedule-tools looks for it to tell a
# rejected argument list apart from a committed upload, because both exit 2.
USAGE_MARKER = "Usage:"


@pytest.fixture
def video_file(tmp_path):
    path = tmp_path / "clip.mp4"
    path.write_bytes(b"not-really-video")
    return str(path)


@pytest.fixture(autouse=True)
def table_output():
    """Each test says its own format; none should leak into the next."""
    config.format = OutputFormat.table
    yield
    config.format = OutputFormat.table


def strip(text: str) -> str:
    """Rich colours its output; a caller strips escapes before matching."""
    import re

    return re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", text)


class TestExitTwoIsSharedWithClick:
    """`yt` chose exit 2 for "committed". Click uses it for every usage error.

    A caller cannot treat exit 2 as committed on its own, so the two cases have
    to stay distinguishable by output. If a change here stops Click printing its
    banner — a custom error handler, a friendlier message — a mistyped flag goes
    back to reading as "a video may already be on your channel", and the lane
    halts for an upload that never happened.

    Replacing `typer.rich_utils.rich_format_error` is enough to break these,
    which is how their failure was confirmed rather than assumed. Note that
    patching `click.exceptions.UsageError.show` is *not* enough — Typer renders
    its own errors — so the banner comes from further inside than it looks.
    """

    @pytest.mark.parametrize(
        "argv",
        [
            pytest.param(["upload", "FILE", "--title", "t", "--bogus", "1"], id="unknown option"),
            pytest.param(["upload"], id="missing required argument"),
            pytest.param(["upload", "FILE", "--title", "t", "--format", "nope"], id="bad option value"),
        ],
    )
    def test_a_usage_error_exits_two_and_says_so(self, video_file, argv):
        result = runner.invoke(app, [a.replace("FILE", video_file) for a in argv])

        assert result.exit_code == EXIT_UPLOAD_COMMITTED
        assert USAGE_MARKER in strip(result.output)

    def test_a_committed_upload_does_not_print_the_usage_banner(self, video_file):
        # The other direction: the discriminator has to be false here, or every
        # committed upload would be dismissed as a typo and retried.
        client = MagicMock()
        client.videos.upload.side_effect = UploadCommittedError("lost the response", video_id="abc123")
        with patch("stream_tools_cli.commands.videos.get_client", return_value=client):
            result = runner.invoke(app, ["upload", video_file, "--title", "Loom (1990)"])

        assert result.exit_code == EXIT_UPLOAD_COMMITTED
        assert USAGE_MARKER not in strip(result.output)


class TestTheJsonPayloadStaysParseable:
    """schedule-tools finds the payload at the first `[` and reads `id` from
    element zero, after the human status line the command prints first.

    `output()` writes JSON with the builtin `print`. Routing it through Rich
    instead would wrap a long description at the console width and corrupt it —
    and because the upload has already succeeded by then, the caller would fail
    to find the id and its retry would put the video up twice.

    Swapping that `print` for `console.print` fails the long-description case
    below with a JSONDecodeError and leaves the short ones passing, which is
    both how this was confirmed and why the long one is here.
    """

    def upload_json(self, video_file, description=""):
        config.format = OutputFormat.json
        client = MagicMock()
        client.videos.upload.return_value = _video("dQw4w9WgXcQ", description)
        with patch("stream_tools_cli.commands.videos.get_client", return_value=client):
            return runner.invoke(
                app,
                ["upload", video_file, "--title", "Loom (1990)", "--description", description,
                 "--format", "json"],
            )

    def test_a_successful_upload_exits_zero(self, video_file):
        assert self.upload_json(video_file).exit_code == EXIT_OK

    def test_the_payload_parses_from_the_first_bracket(self, video_file):
        out = strip(self.upload_json(video_file).output)

        payload = json.loads(out[out.index("[") :])
        assert isinstance(payload, list)
        assert payload[0]["id"] == "dQw4w9WgXcQ"

    def test_the_status_line_comes_first_and_holds_no_bracket(self, video_file):
        # The caller slices at the first `[`, so anything bracketed before the
        # payload would take the slice with it.
        out = strip(self.upload_json(video_file).output)

        assert out.index("Video uploaded") < out.index("[")

    def test_a_description_long_enough_to_wrap_does_not_corrupt_it(self, video_file):
        # 4000 characters on one line: well past any console width, and inside
        # YouTube's 5000-byte limit.
        out = strip(self.upload_json(video_file, description="x" * 4000).output)

        payload = json.loads(out[out.index("[") :])
        assert payload[0]["description"] == "x" * 4000


def _video(video_id: str, description: str = ""):
    from stream_tools.models.video import Video

    return Video.from_api_response(
        {
            "id": video_id,
            "snippet": {"title": "Loom (1990)", "description": description, "channelId": "UC1"},
            "status": {"privacyStatus": "private"},
        }
    )
