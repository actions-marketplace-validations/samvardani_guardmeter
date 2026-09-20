"""Stdlib-only HTTP playground server for GuardMeter.

No third-party dependencies: http.server, json, urllib only. The server is a
local developer tool — it binds loopback by default and has no authentication
(see the token support added for off-loopback binds).
"""

from __future__ import annotations

import http.server
import importlib.resources
import json
import logging
import sys
import tempfile
import urllib.parse
import webbrowser
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Cap on POST body size (the try-out text itself is further capped by run_try).
MAX_BODY_BYTES = 64 * 1024

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
    """ThreadingHTTPServer carrying the server's configured default guards."""

    daemon_threads = True
    default_guards: list[str]  # set per-instance in create_server()


class PlaygroundHandler(http.server.BaseHTTPRequestHandler):
    """Serves the playground page and the /api/* JSON endpoints."""

    server_version = "GuardMeter-serve"

    # ── low-level response helpers ──────────────────────────────────────────
    def _send(self, code: int, body: bytes, content_type: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        for key, value in _SECURITY_HEADERS.items():
            self.send_header(key, value)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _send_json(self, code: int, obj: Any) -> None:
        self._send(code, json.dumps(obj).encode("utf-8"), "application/json; charset=utf-8")

    def _send_html(self, code: int, html: str) -> None:
        self._send(code, html.encode("utf-8"), "text/html; charset=utf-8")

    def log_message(self, fmt: str, *args: Any) -> None:  # one line per request → stderr
        logger.info("%s %s", self.address_string(), fmt % args)

    def _default_guards(self) -> list[str]:
        return list(getattr(self.server, "default_guards", _DEFAULT_GUARDS))

    # ── routing ─────────────────────────────────────────────────────────────
    def do_GET(self) -> None:
        path = urllib.parse.urlparse(self.path).path
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


def create_server(host: str, port: int, default_guards: list[str] | None = None) -> PlaygroundServer:
    """Create (but do not start) a PlaygroundServer. Port 0 picks a free port."""
    httpd = PlaygroundServer((host, port), PlaygroundHandler)
    httpd.default_guards = list(default_guards) if default_guards else list(_DEFAULT_GUARDS)
    return httpd


def run_server(
    host: str = "127.0.0.1",
    port: int = 8765,
    default_guards: list[str] | None = None,
    open_browser: bool = False,
) -> None:
    """Run the playground server until interrupted."""
    if host not in _LOOPBACK:
        logger.warning(
            "GuardMeter serve has no authentication — do NOT expose %s publicly.", host
        )

    httpd = create_server(host, port, default_guards)
    actual_port = httpd.server_address[1]
    url = f"http://{host}:{actual_port}"
    print(f"GuardMeter playground on {url}  (Ctrl-C to stop)", file=sys.stderr)

    if open_browser:
        webbrowser.open(url)

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.", file=sys.stderr)
    finally:
        httpd.shutdown()
        httpd.server_close()
