"""A multi-chunk upload runs end to end against a server that speaks YouTube's protocol (VGM-89).

`YouTubeLiveClient` -> `VideoService.upload` -> googleapiclient -> httplib2 ->
a real socket, with the default 100 MiB chunk size. The server answers every
chunk but the last with `308 Resume Incomplete` and no `Location`, as YouTube
does. Nothing between the service and the wire is mocked, so this is the
seam on which the bug lived: before the fix, the second chunk was never sent.
"""

import json
from datetime import UTC, datetime, timedelta

import pytest
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build_from_document
from googleapiclient.discovery_cache import get_static_doc
from typer.testing import CliRunner

import stream_tools.client as client_module
import stream_tools_cli.commands.videos as video_commands
from stream_tools import YouTubeLiveClient
from stream_tools.exceptions import APIError, QuotaExceededError, UploadCommittedError
from stream_tools_cli.app import app
from tests.fake_youtube import FakeYouTube

MIB = 1024 * 1024
CHUNK = 100 * MIB  # googleapiclient's default, which VideoService.upload relies on


@pytest.fixture
def youtube(monkeypatch):
    with FakeYouTube() as server:

        def build_against_server(_name, _version, http=None):
            doc = json.loads(get_static_doc("youtube", "v3"))
            doc["rootUrl"] = f"{server.base_url}/"
            return build_from_document(doc, http=http)

        monkeypatch.setattr(client_module, "build", build_against_server)
        yield server


@pytest.fixture
def client():
    expiry = datetime.now(UTC).replace(tzinfo=None) + timedelta(hours=1)
    return YouTubeLiveClient(Credentials(token="unused", expiry=expiry))


def video_of(tmp_path, size):
    """A sparse file: costs no disk, and the server discards what it reads."""
    path = tmp_path / "video.mp4"
    with path.open("wb") as f:
        f.truncate(size)
    return path


def test_a_file_over_one_chunk_is_sent_in_full(youtube, client, tmp_path):
    size = 2 * CHUNK + 50 * MIB
    video = client.videos.upload(video_of(tmp_path, size), title="Long")

    assert video.id == "fakeVideoId1"
    assert youtube.chunk_puts() == [
        f"bytes 0-{CHUNK - 1}/{size}",
        f"bytes {CHUNK}-{2 * CHUNK - 1}/{size}",
        f"bytes {2 * CHUNK}-{size - 1}/{size}",
    ]


@pytest.mark.parametrize("size", [CHUNK - MIB, CHUNK])
def test_a_file_that_fits_in_one_chunk_is_a_single_put(youtube, client, tmp_path, size):
    client.videos.upload(video_of(tmp_path, size), title="Short")

    assert len(youtube.chunk_puts()) == 1


def test_the_cli_exits_zero_for_a_multi_chunk_upload(youtube, client, tmp_path, monkeypatch):
    """Exit 2 means "committed but unconfirmed"; it is what the 308 bug produced."""
    monkeypatch.setattr(video_commands, "get_client", lambda: client)
    path = video_of(tmp_path, CHUNK + MIB)

    result = CliRunner().invoke(app, ["video", "upload", str(path), "--title", "Contra"])

    assert result.exit_code == 0, result.output
    assert len(youtube.chunk_puts()) == 2


def test_a_failure_on_a_later_chunk_is_reported_as_itself(youtube, client, tmp_path):
    """Before the fix every failure after chunk one was masked as a committed upload."""
    body = {"error": {"code": 403, "message": "q", "errors": [{"reason": "quotaExceeded"}]}}
    youtube.on_chunk = lambda n: (403, json.dumps(body).encode()) if n == 2 else None

    with pytest.raises(QuotaExceededError):
        client.videos.upload(video_of(tmp_path, CHUNK + MIB), title="Long")


def test_a_server_error_on_a_later_chunk_is_not_called_committed(youtube, client, tmp_path):
    youtube.on_chunk = lambda n: (503, b'{"error": {"code": 503, "message": "x"}}') if n == 2 else None

    with pytest.raises(APIError) as raised:
        client.videos.upload(video_of(tmp_path, CHUNK + MIB), title="Long")

    assert not isinstance(raised.value, UploadCommittedError)
