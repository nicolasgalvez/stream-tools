"""A local HTTP server that speaks YouTube's resumable-upload protocol.

Only what `videos.insert` with `uploadType=resumable` needs:

* the initiating POST answers 200 with a `Location` session URI;
* each chunk PUT but the last answers `308 Resume Incomplete` with a `Range`
  header and **no `Location`**, exactly as YouTube does;
* the final chunk PUT answers 200 with the video resource.

Every other GET answers an empty `items` list, which is what the id-recovery
lookup after a "committed" upload needs to degrade to "id not recovered".
"""

from __future__ import annotations

import json
import re
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

_CONTENT_RANGE = re.compile(r"bytes (\d+)-(\d+)/(\d+)")
_DRAIN = 1024 * 1024


class _Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server: FakeYouTube

    def log_message(self, format: str, *args: object) -> None:
        pass

    def _drain(self) -> int:
        remaining = total = int(self.headers.get("Content-Length", 0))
        while remaining:
            remaining -= len(self.rfile.read(min(_DRAIN, remaining)))
        return total

    def _reply(self, status: int, headers: dict[str, str] | None = None, body: bytes = b"") -> None:
        self.send_response(status)
        for name, value in (headers or {}).items():
            self.send_header(name, value)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:
        self._drain()
        self.server.requests.append(("POST", self.path, None))
        self._reply(200, {"Location": f"{self.server.base_url}/session/1"})

    def do_PUT(self) -> None:
        content_range = self.headers.get("Content-Range", "")
        self._drain()
        self.server.requests.append(("PUT", self.path, content_range))
        match = _CONTENT_RANGE.fullmatch(content_range)
        if not match:
            self._reply(400)
            return
        _first, last, total = (int(g) for g in match.groups())
        override = self.server.on_chunk(len(self.server.chunk_puts()))
        if override:
            status, body = override
            self._reply(status, {"Content-Type": "application/json"}, body)
            return
        if last + 1 < total:
            self._reply(308, {"Range": f"bytes=0-{last}"})
            return
        video = {
            "id": "fakeVideoId1",
            "snippet": {"title": "t", "description": "", "channelId": "c"},
            "status": {"privacyStatus": "private", "uploadStatus": "uploaded"},
        }
        self._reply(200, {"Content-Type": "application/json"}, json.dumps(video).encode())

    def do_GET(self) -> None:
        self.server.requests.append(("GET", self.path, None))
        self._reply(200, {"Content-Type": "application/json"}, b'{"items": []}')


class FakeYouTube(ThreadingHTTPServer):
    """Run with `with FakeYouTube() as yt:`; `yt.requests` records what arrived."""

    daemon_threads = True

    def __init__(self) -> None:
        super().__init__(("127.0.0.1", 0), _Handler)
        self.requests: list[tuple[str, str, str | None]] = []
        # Called with the 1-based number of the chunk PUT; return (status, body) to
        # answer it with something other than the protocol's normal reply.
        self.on_chunk: Callable[[int], tuple[int, bytes] | None] = lambda _n: None

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.server_address[1]}"

    def chunk_puts(self) -> list[str | None]:
        return [content_range for method, _path, content_range in self.requests if method == "PUT"]

    def __enter__(self) -> FakeYouTube:
        threading.Thread(target=self.serve_forever, daemon=True).start()
        return self

    def __exit__(self, *exc: object) -> None:
        self.shutdown()
        self.server_close()
