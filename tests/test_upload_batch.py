"""Tests for scripts/upload-batch (loaded by path — it has no .py extension)."""

import importlib.machinery
import importlib.util
import json
from pathlib import Path
from unittest.mock import MagicMock

from googleapiclient.errors import HttpError

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "upload-batch"
_loader = importlib.machinery.SourceFileLoader("upload_batch", str(_SCRIPT))
_spec = importlib.util.spec_from_loader("upload_batch", _loader)
ub = importlib.util.module_from_spec(_spec)
_loader.exec_module(ub)


def make_entry(rank, status="pending", publish="2999-01-01T12:00:00Z", tags=("#VGM", "#OPL3"), title=None):
    return {
        "rank": rank,
        "file": f"{rank:02d} - song.mp4",
        "title": title or f"Song {rank}",
        "description": "desc",
        "tags": list(tags),
        "upload": {"status": status, "publishAt": publish, "videoId": None, "url": None},
    }


def http_error(status, content):
    resp = MagicMock()
    resp.status = status
    return HttpError(resp, content)


def test_parse_args(monkeypatch):
    monkeypatch.delenv("VGM_BATCH", raising=False)
    assert ub.parse_args(["prog"]) == (4, False)
    assert ub.parse_args(["prog", "6"]) == (6, False)
    assert ub.parse_args(["prog", "--dry-run"]) == (4, True)
    assert ub.parse_args(["prog", "3", "--dry-run"]) == (3, True)
    monkeypatch.setenv("VGM_BATCH", "9")
    assert ub.parse_args(["prog"]) == (9, False)


def test_is_past():
    assert ub.is_past("2000-01-01T00:00:00Z") is True
    assert ub.is_past("2999-01-01T00:00:00Z") is False
    assert ub.is_past("") is False
    assert ub.is_past(None) is False


def test_pending_entries_excludes_uploaded_and_sorts():
    meta = [make_entry(3), make_entry(1, status="uploaded"), make_entry(2), make_entry(5)]
    pending = ub.pending_entries(meta)
    assert [e["rank"] for e in pending] == [2, 3, 5]
    assert [e["rank"] for e in pending[:2]] == [2, 3]  # next-N slice


def test_is_quota_error():
    assert ub.is_quota_error(http_error(403, b'{"error": "quotaExceeded"}')) is True
    assert ub.is_quota_error(http_error(403, b"some other 403")) is False
    assert ub.is_quota_error(http_error(404, b"quota")) is False
    assert ub.is_quota_error(ValueError("not an HttpError")) is False


def test_upload_one_builds_body_and_strips_tags(tmp_path):
    f = tmp_path / "v.mp4"
    f.write_bytes(b"\x00" * 2048)
    yt = MagicMock()
    request = MagicMock()
    request.next_chunk.return_value = (None, {"id": "VID123"})
    yt.videos.return_value.insert.return_value = request

    entry = make_entry(7, tags=["#VGM", "#OPL3"], publish="2999-01-01T12:00:00Z")
    vid = ub.upload_one(yt, entry, str(f))

    assert vid == "VID123"
    body = yt.videos.return_value.insert.call_args.kwargs["body"]
    assert body["snippet"]["tags"] == ["VGM", "OPL3"]  # leading '#' stripped
    assert body["snippet"]["categoryId"] == ub.CATEGORY_ID
    assert body["status"]["privacyStatus"] == "private"
    assert body["status"]["publishAt"] == "2999-01-01T12:00:00Z"


def test_upload_one_omits_past_publish_at(tmp_path):
    f = tmp_path / "v.mp4"
    f.write_bytes(b"\x00" * 2048)
    yt = MagicMock()
    request = MagicMock()
    request.next_chunk.return_value = (None, {"id": "X"})
    yt.videos.return_value.insert.return_value = request

    entry = make_entry(1, publish="2000-01-01T00:00:00Z")  # in the past
    ub.upload_one(yt, entry, str(f))

    body = yt.videos.return_value.insert.call_args.kwargs["body"]
    assert "publishAt" not in body["status"]  # never schedule in the past


def test_record_updates_entry_and_writes_file(tmp_path, monkeypatch):
    meta = [make_entry(1)]
    path = tmp_path / "meta.json"
    path.write_text(json.dumps(meta))
    monkeypatch.setattr(ub, "METADATA_PATH", str(path))

    ub.record(meta, meta[0], "VIDX")

    assert meta[0]["upload"] == {
        "status": "uploaded",
        "publishAt": "2999-01-01T12:00:00Z",
        "videoId": "VIDX",
        "url": "https://youtu.be/VIDX",
    }
    assert json.loads(path.read_text())[0]["upload"]["videoId"] == "VIDX"


def test_recover_id_by_title(monkeypatch):
    monkeypatch.setattr(ub.time, "sleep", lambda *_: None)
    yt = MagicMock()
    yt.search.return_value.list.return_value.execute.return_value = {
        "items": [
            {"snippet": {"title": "Other"}, "id": {"videoId": "a"}},
            {"snippet": {"title": "Wanted"}, "id": {"videoId": "WANT"}},
        ]
    }
    assert ub.recover_id_by_title(yt, "Wanted") == "WANT"


def test_recover_id_by_title_returns_none_when_absent(monkeypatch):
    monkeypatch.setattr(ub.time, "sleep", lambda *_: None)
    yt = MagicMock()
    yt.search.return_value.list.return_value.execute.return_value = {"items": []}
    assert ub.recover_id_by_title(yt, "Missing", attempts=2, delay=0) is None


def test_check_source_local(monkeypatch, tmp_path):
    monkeypatch.setattr(ub, "LOCAL_DIR", str(tmp_path))
    ok, desc = ub.check_source()
    assert ok is True
    assert ub.local_mode() is True
    assert str(tmp_path) in desc


def test_check_source_unconfigured(monkeypatch):
    monkeypatch.setattr(ub, "LOCAL_DIR", None)
    monkeypatch.setattr(ub, "SRC_HOST", None)
    monkeypatch.setattr(ub, "SRC_DIR", None)
    ok, msg = ub.check_source()
    assert ok is False
    assert "VGM_VIDEO_DIR" in msg
