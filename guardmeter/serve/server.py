"""Stdlib-only HTTP playground server for GuardMeter.

No third-party dependencies: http.server, json, urllib only. The server is a
local developer tool — it binds loopback by default. Binding a non-loopback
interface requires a GUARDMETER_TOKEN, which every /api/* request must then
present as a Bearer token.
"""

from __future__ import annotations

import hmac
import http.server
import importlib.resources
import json
import logging
import math
import os
import sys
import tempfile
import threading
import time
import urllib.parse
import webbrowser
from pathlib import Path
from typing import Any, cast

logger = logging.getLogger(__name__)

# Cap on POST body size (the try-out text itself is further capped by run_try).
MAX_BODY_BYTES = 64 * 1024

# Per-client-IP token bucket for /api/try: 30 requests per 60 s.
RATE_CAPACITY = 30
RATE_WINDOW_S = 60.0
RATE_REFILL = RATE_CAPACITY / RATE_WINDOW_S  # tokens per second

_LOOPBACK = {"127.0.0.1", "localhost", "::1"}

_DEFAULT_GUARDS = ["regex-baseline", "regex-enhanced"]

_SECURITY_HEADERS = {
    "Content-Security-Policy": (
        "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'unsafe-inline'"
    ),
    "X-Content-Type-Options": "nosniff",
}


def _playground_html() -> str:
    return (
        importlib.resources.files("guardmeter.serve") / "templates" / "playground.html"
    ).read_text(encoding="utf-8")


def _render_dashboard() -> str:
    """Rebuild the dashboard from the default store and return its HTML."""
    from guardmeter.report.generator import DashboardGenerator
    from guardmeter.store.sqlite import SQLiteStore

    store = SQLiteStore()
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "dashboard.html"
        DashboardGenerator(store).build(out)
        return out.read_text(encoding="utf-8")


class PlaygroundServer(http.server.ThreadingHTTPServer):
    """ThreadingHTTPServer carrying config and per-IP rate-limit state."""

    daemon_threads = True
    default_guards: list[str]        # set per-instance in create_server()
    token: str | None                # optional Bearer token for /api/*
    rate_buckets: dict[str, tuple[float, float]]
    rate_lock: threading.Lock


class PlaygroundHandler(http.server.BaseHTTPRequestHandler):
    """Serves the playground page and the /api/* JSON endpoints."""

    server_version = "GuardMeter-serve"

    # ── low-level response helpers ──────────────────────────────────────────
    def _send(self, code: int, body: bytes, content_type: str,
              extra_headers: dict[str, str] | None = None) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        for key, value in _SECURITY_HEADERS.items():
            self.send_header(key, value)
        for key, value in (extra_headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _send_json(self, code: int, obj: Any, extra_headers: dict[str, str] | None = None) -> None:
        self._send(code, json.dumps(obj).encode("utf-8"),
                   "application/json; charset=utf-8", extra_headers)

    def _send_html(self, code: int, html: str) -> None:
        self._send(code, html.encode("utf-8"), "text/html; charset=utf-8")

    def log_message(self, fmt: str, *args: Any) -> None:  # one line per request → stderr
        logger.info("%s %s", self.address_string(), fmt % args)

    def _default_guards(self) -> list[str]:
        return list(getattr(self.server, "default_guards", _DEFAULT_GUARDS))

    # ── auth + rate limiting ────────────────────────────────────────────────
    def _authorized(self) -> bool:
        token = getattr(self.server, "token", None)
        if not token:
            return True
        header = self.headers.get("Authorization", "")
        prefix = "Bearer "
        if not header.startswith(prefix):
            return False
        return hmac.compare_digest(header[len(prefix):], token)

    def _rate_ok(self) -> tuple[bool, int]:
        server = cast("PlaygroundServer", self.server)
        buckets = server.rate_buckets
        ip = self.client_address[0]
        now = time.monotonic()
        with server.rate_lock:
            tokens, last = buckets.get(ip, (float(RATE_CAPACITY), now))
            tokens = min(float(RATE_CAPACITY), tokens + (now - last) * RATE_REFILL)
            if tokens >= 1.0:
                buckets[ip] = (tokens - 1.0, now)
                return True, 0
            buckets[ip] = (tokens, now)
            retry = math.ceil((1.0 - tokens) / RATE_REFILL)
            return False, max(retry, 1)

    # ── routing ─────────────────────────────────────────────────────────────
    def do_GET(self) -> None:
        path = urllib.parse.urlparse(self.path).path
        if path.startswith("/api/") and not self._authorized():
            self._send_json(401, {"error": "unauthorized"})
            return
        if path == "/":
            self._send_html(200, _playground_html())
        elif path == "/dashboard":
            self._send_html(200, _render_dashboard())
        elif path == "/api/guards":
            from guardmeter.core.registry import list_guards
            self._send_json(200, {"guards": list_guards(), "default": self._default_guards()})
        else:
            self._send_json(404, {"error": "not found"})

    def do_POST(self) -> None:
        path = urllib.parse.urlparse(self.path).path
        if path != "/api/try":
            self._send_json(404, {"error": "not found"})
            return
        if not self._authorized():
            self._send_json(401, {"error": "unauthorized"})
            return

        ok, retry_after = self._rate_ok()
        if not ok:
            self._send_json(429, {"error": "rate limit exceeded"},
                            extra_headers={"Retry-After": str(retry_after)})
            return

        length = int(self.headers.get("Content-Length") or 0)
        # Read the (loopback-only) body, then reject if it exceeds the cap, so
        # the client reliably receives the 413 rather than a reset mid-send.
        raw = self.rfile.read(length)
        if length > MAX_BODY_BYTES or len(raw) > MAX_BODY_BYTES:
            self._send_json(413, {"error": "request body too large"})
            return

        try:
            data = json.loads(raw.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            self._send_json(400, {"error": "invalid JSON"})
            return
        if not isinstance(data, dict) or not isinstance(data.get("text"), str) or not data["text"]:
            self._send_json(400, {"error": "missing 'text'"})
            return

        guards = data.get("guards") or self._default_guards()
        if not isinstance(guards, list) or not all(isinstance(g, str) for g in guards):
            self._send_json(400, {"error": "'guards' must be a list of strings"})
            return

        from guardmeter.core.tryout import run_try
        try:
            results = run_try(data["text"], guards)
        except ValueError as exc:
            self._send_json(400, {"error": str(exc)})
            return
        self._send_json(200, [r.to_dict() for r in results])


def create_server(
    host: str,
    port: int,
    default_guards: list[str] | None = None,
    token: str | None = None,
) -> PlaygroundServer:
    """Create (but do not start) a PlaygroundServer. Port 0 picks a free port."""
    httpd = PlaygroundServer((host, port), PlaygroundHandler)
    httpd.default_guards = list(default_guards) if default_guards else list(_DEFAULT_GUARDS)
    httpd.token = token
    httpd.rate_buckets = {}
    httpd.rate_lock = threading.Lock()
    return httpd


def run_server(
    host: str = "127.0.0.1",
    port: int = 8765,
    default_guards: list[str] | None = None,
    open_browser: bool = False,
    token: str | None = None,
) -> None:
    """Run the playground server until interrupted.

    Raises RuntimeError if asked to bind a non-loopback interface without a
    token (via the ``token`` argument or the GUARDMETER_TOKEN env var).
    """
    token = token or os.environ.get("GUARDMETER_TOKEN")
    if host not in _LOOPBACK and not token:
        raise RuntimeError(
            f"Refusing to bind non-loopback host {host!r} without authentication. "
            "Set GUARDMETER_TOKEN to require a Bearer token, or bind 127.0.0.1."
        )
    if host not in _LOOPBACK:
        logger.warning("GuardMeter serve is exposed on %s — token auth is required.", host)

    httpd = create_server(host, port, default_guards, token=token)
    actual_port = httpd.server_address[1]
    url = f"http://{host}:{actual_port}"
    auth_note = " (token required)" if token else ""
    print(f"GuardMeter playground on {url}{auth_note}  (Ctrl-C to stop)", file=sys.stderr)

    if open_browser:
        webbrowser.open(url)

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.", file=sys.stderr)
    finally:
        httpd.shutdown()
        httpd.server_close()
