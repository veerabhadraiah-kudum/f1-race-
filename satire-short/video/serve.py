#!/usr/bin/env python3
"""Tiny static server with HTTP Range support, so the MP4 can seek/stream.

Python's http.server ignores Range headers (it always replies 200 with the whole
file), which breaks playback in Safari and some in-app browsers. This handles
206 Partial Content properly.
"""
from __future__ import annotations

import os
import re
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote, urlparse

ROOT = os.path.dirname(os.path.abspath(__file__))
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8080

MIME = {
    ".html": "text/html; charset=utf-8",
    ".mp4": "video/mp4",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".srt": "text/plain; charset=utf-8",
    ".md": "text/plain; charset=utf-8",
}

RANGE_RE = re.compile(r"bytes=(\d*)-(\d*)")


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _path(self) -> str | None:
        p = unquote(urlparse(self.path).path)
        if p in ("", "/"):
            p = "/index.html"
        full = os.path.normpath(os.path.join(ROOT, p.lstrip("/")))
        if not full.startswith(ROOT) or not os.path.isfile(full):
            return None
        return full

    def _base_headers(self, size: int, ctype: str, extra: dict | None = None) -> None:
        self.send_header("Content-Type", ctype)
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Access-Control-Allow-Origin", "*")
        if extra:
            for k, v in extra.items():
                self.send_header(k, v)
        self.send_header("Content-Length", str(size))

    def do_HEAD(self) -> None:  # noqa: N802
        full = self._path()
        if full is None:
            self.send_error(404)
            return
        ext = os.path.splitext(full)[1].lower()
        size = os.path.getsize(full)
        self.send_response(200)
        self._base_headers(size, MIME.get(ext, "application/octet-stream"))
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        full = self._path()
        if full is None:
            self.send_error(404)
            return
        ext = os.path.splitext(full)[1].lower()
        ctype = MIME.get(ext, "application/octet-stream")
        size = os.path.getsize(full)
        rng = self.headers.get("Range", "")

        if rng and (m := RANGE_RE.match(rng)):
            start_s, end_s = m.group(1), m.group(2)
            if start_s:
                start = int(start_s)
                end = int(end_s) if end_s else size - 1
            else:  # suffix range: bytes=-N
                length = int(end_s or 0)
                start = max(0, size - length)
                end = size - 1
            end = min(end, size - 1)
            if start > end or start >= size:
                self.send_response(416)
                self.send_header("Content-Range", f"bytes */{size}")
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            length = end - start + 1
            self.send_response(206)
            self._base_headers(length, ctype,
                               {"Content-Range": f"bytes {start}-{end}/{size}"})
            self.end_headers()
            with open(full, "rb") as f:
                f.seek(start)
                remaining = length
                while remaining > 0:
                    chunk = f.read(min(256 * 1024, remaining))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    remaining -= len(chunk)
            return

        self.send_response(200)
        self._base_headers(size, ctype)
        self.end_headers()
        with open(full, "rb") as f:
            while chunk := f.read(256 * 1024):
                self.wfile.write(chunk)

    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))


if __name__ == "__main__":
    srv = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print(f"serving {ROOT} on http://0.0.0.0:{PORT} (range enabled)", flush=True)
    srv.serve_forever()
