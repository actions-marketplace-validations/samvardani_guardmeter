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
import threading
import time
import urllib.parse
import webbrowser
from pathlib import Path
from typing import Any, cast

from guardmeter.serve.jobs import JobManager

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
    # style-src includes 'self' so the app's linked /static/styles.css loads;
    # inline styles stay allowed for the vendored-JS render path.
    "Content-Security-Policy": (
        "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'"
    ),
    "X-Content-Type-Options": "nosniff",
}


def _app_html() -> str:
    return (
        importlib.resources.files("guardmeter.serve") / "templates" / "app.html"
    ).read_text(encoding="utf-8")


_STATIC_TYPES = {
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".html": "text/html; charset=utf-8",
    ".json": "application/json",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".txt": "text/plain; charset=utf-8",
    ".map": "application/json",
}


def _static_dir() -> Path:
    return Path(str(importlib.resources.files("guardmeter.serve"))) / "static"


def read_static(name: str) -> tuple[bytes, str] | None:
    """Return (bytes, content_type) for a file under serve/static, or None.

    Rejects path traversal. chart.umd.min.js falls back to the copy already
    vendored under report/static so it isn't duplicated.
    """
    if not name or name.startswith("/") or ".." in name.split("/"):
        return None
    base = _static_dir().resolve()
    target = (base / name).resolve()
    ctype = _STATIC_TYPES.get(target.suffix, "application/octet-stream")
    if (target == base or base in target.parents) and target.is_file():
        return target.read_bytes(), ctype
    if name == "chart.umd.min.js":
        alt = Path(str(importlib.resources.files("guardmeter.report"))) / "static" / name
        if alt.is_file():
            return alt.read_bytes(), _STATIC_TYPES[".js"]
    return None


class PlaygroundServer(http.server.ThreadingHTTPServer):
    """ThreadingHTTPServer carrying config, rate-limit state, and the job manager."""

    daemon_threads = True
    default_guards: list[str]        # set per-instance in create_server()
    token: str | None                # optional Bearer token for /api/*
    store_path: str | None           # SQLite path override (None → default store)
    rate_buckets: dict[str, tuple[float, float]]
    rate_lock: threading.Lock
    jobs: JobManager


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

    # ── request helpers ─────────────────────────────────────────────────────
    def _api_gate(self) -> bool:
        """Enforce auth for /api/* routes; sends 401 and returns False if denied."""
        if not self._authorized():
            self._send_json(401, {"error": "unauthorized"})
            return False
        return True

    def _read_json(self) -> Any:
        """Read and parse a JSON body; sends 413/400 and returns None on failure."""
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length)
        if length > MAX_BODY_BYTES or len(raw) > MAX_BODY_BYTES:
            self._send_json(413, {"error": "request body too large"})
            return None
        try:
            return json.loads(raw.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            self._send_json(400, {"error": "invalid JSON"})
            return None

    def _store(self) -> Any:
        from guardmeter.store.sqlite import SQLiteStore
        return SQLiteStore(db_path=getattr(self.server, "store_path", None))

    def _int(self, params: dict[str, list[str]], key: str, default: int) -> int:
        try:
            return int(params.get(key, [str(default)])[0])
        except (ValueError, TypeError):
            return default

    def _one(self, params: dict[str, list[str]], key: str, default: str = "") -> str:
        return params.get(key, [default])[0]

    # ── routing ─────────────────────────────────────────────────────────────
    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        params = urllib.parse.parse_qs(parsed.query)
        if path.startswith("/api/") and not self._api_gate():
            return
        seg = [s for s in path.split("/") if s]

        if path == "/styleguide":
            found = read_static("styleguide.html")
            self._send_html(200, found[0].decode("utf-8")) if found else self._send_json(404, {"error": "not found"})
        elif path.startswith("/static/"):
            found = read_static(path[len("/static/"):])
            self._send(200, found[0], found[1]) if found else self._send_json(404, {"error": "not found"})
        elif path == "/api/guards":
            from guardmeter.core.registry import list_guards
            self._send_json(200, {"guards": list_guards(), "default": self._default_guards()})
        elif path == "/api/gate":
            from guardmeter.serve.api import current_gate_config
            cfg = current_gate_config()
            self._send_json(200, cfg.model_dump() if cfg else {})
        elif path == "/api/runs":
            from guardmeter.serve.api import runs_payload
            self._send_json(200, runs_payload(
                self._store(), limit=self._int(params, "limit", 100),
                guard=self._one(params, "guard"), dataset=self._one(params, "dataset"),
                q=self._one(params, "q")))
        elif path == "/api/datasets":
            from guardmeter.serve.api import datasets_list
            self._send_json(200, {"datasets": datasets_list()})
        elif len(seg) == 4 and seg[:2] == ["api", "datasets"] and seg[3] == "stats":
            from guardmeter.serve.api import dataset_stats
            stats = dataset_stats(seg[2])
            self._send_json(200, stats) if stats else self._send_json(404, {"error": "not found"})
        elif len(seg) == 4 and seg[:2] == ["api", "datasets"] and seg[3] == "rows":
            from guardmeter.serve.api import dataset_rows
            rows = dataset_rows(seg[2], q=self._one(params, "q"),
                                offset=self._int(params, "offset", 0), limit=self._int(params, "limit", 100))
            self._send_json(200, rows) if rows else self._send_json(404, {"error": "not found"})
        elif len(seg) == 3 and seg[:2] == ["api", "jobs"]:
            job = cast("PlaygroundServer", self.server).jobs.get(seg[2])
            self._send_json(200, job) if job else self._send_json(404, {"error": "not found"})
        elif len(seg) >= 3 and seg[:2] == ["api", "runs"]:
            self._run_subroute_get(seg, params)
        elif path.startswith("/api/"):
            self._send_json(404, {"error": "not found"})
        else:
            # SPA fallback: /, /run/<id>, /gate, /compare, /try, /datasets, /dashboard …
            self._send_html(200, _app_html())

    def _run_subroute_get(self, seg: list[str], params: dict[str, list[str]]) -> None:
        run_id = seg[2]
        try:
            results = self._store().get_run(run_id)
        except KeyError:
            self._send_json(404, {"error": "run not found"})
            return
        if len(seg) == 3:
            self._send_json(200, results.to_dict())
        elif len(seg) == 4 and seg[3] == "samples":
            from guardmeter.serve.api import samples_payload
            self._send_json(200, samples_payload(
                results, filt=self._one(params, "filter", "all"), q=self._one(params, "q"),
                offset=self._int(params, "offset", 0), limit=self._int(params, "limit", 100),
                category=self._one(params, "category"), language=self._one(params, "language"),
                attack=self._one(params, "attack")))
        elif len(seg) == 4 and seg[3] == "export.csv":
            from guardmeter.serve.api import run_csv
            self._send(200, run_csv(results).encode("utf-8"), "text/csv; charset=utf-8",
                       extra_headers={"Content-Disposition": f'attachment; filename="{run_id}.csv"'})
        else:
            self._send_json(404, {"error": "not found"})

    def do_POST(self) -> None:
        path = urllib.parse.urlparse(self.path).path
        if not self._api_gate():
            return
        if path == "/api/try":
            self._post_try()
        elif path == "/api/compare":
            self._post_compare()
        elif path == "/api/gate/evaluate":
            self._post_gate_evaluate()
        else:
            self._send_json(404, {"error": "not found"})

    def _post_try(self) -> None:
        ok, retry_after = self._rate_ok()
        if not ok:
            self._send_json(429, {"error": "rate limit exceeded"},
                            extra_headers={"Retry-After": str(retry_after)})
            return
        data = self._read_json()
        if data is None:
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

    def _post_compare(self) -> None:
        ok, retry_after = self._rate_ok()
        if not ok:
            self._send_json(429, {"error": "rate limit exceeded"},
                            extra_headers={"Retry-After": str(retry_after)})
            return
        data = self._read_json()
        if data is None:
            return
        if not isinstance(data, dict) or not all(isinstance(data.get(k), str) and data.get(k)
                                                 for k in ("baseline", "candidate", "dataset")):
            self._send_json(400, {"error": "baseline, candidate and dataset are required"})
            return
        jobs = cast("PlaygroundServer", self.server).jobs
        job_id = jobs.start_compare(self._store(), data["baseline"], data["candidate"], data["dataset"])
        self._send_json(202, {"job_id": job_id})

    def _post_gate_evaluate(self) -> None:
        data = self._read_json()
        if data is None:
            return
        gate = data.get("gate") if isinstance(data, dict) else None
        run_id = data.get("run_id") if isinstance(data, dict) else None
        if not isinstance(gate, dict) or not isinstance(run_id, str):
            self._send_json(400, {"error": "'gate' (object) and 'run_id' are required"})
            return
        try:
            results = self._store().get_run(run_id)
        except KeyError:
            self._send_json(404, {"error": "run not found"})
            return
        from guardmeter.serve.api import gate_evaluate
        try:
            self._send_json(200, gate_evaluate(gate, results))
        except (ValueError, TypeError) as exc:
            self._send_json(400, {"error": f"invalid gate: {exc}"})

    def do_DELETE(self) -> None:
        path = urllib.parse.urlparse(self.path).path
        if not self._api_gate():
            return
        seg = [s for s in path.split("/") if s]
        if len(seg) == 3 and seg[:2] == ["api", "runs"]:
            removed = self._store().delete_run(seg[2])
            self._send_json(200 if removed else 404, {"deleted": removed})
        else:
            self._send_json(404, {"error": "not found"})

    def do_PATCH(self) -> None:
        path = urllib.parse.urlparse(self.path).path
        if not self._api_gate():
            return
        seg = [s for s in path.split("/") if s]
        if len(seg) == 3 and seg[:2] == ["api", "runs"]:
            data = self._read_json()
            if data is None:
                return
            if not isinstance(data, dict):
                self._send_json(400, {"error": "expected a JSON object"})
                return
            ok = self._store().update_run_meta(seg[2], tag=data.get("tag"), note=data.get("note"))
            self._send_json(200 if ok else 404, {"updated": ok})
        else:
            self._send_json(404, {"error": "not found"})

    def do_PUT(self) -> None:
        path = urllib.parse.urlparse(self.path).path
        if not self._api_gate():
            return
        if path == "/api/gate":
            data = self._read_json()
            if data is None:
                return
            gate = data.get("gate") if isinstance(data, dict) else None
            if not isinstance(gate, dict):
                self._send_json(400, {"error": "'gate' object required"})
                return
            from guardmeter.serve.api import write_gate
            try:
                write_gate(gate)
            except (ValueError, TypeError) as exc:
                self._send_json(400, {"error": f"invalid gate: {exc}"})
                return
            self._send_json(200, {"saved": True})
        else:
            self._send_json(404, {"error": "not found"})


def create_server(
    host: str,
    port: int,
    default_guards: list[str] | None = None,
    token: str | None = None,
    store_path: str | None = None,
) -> PlaygroundServer:
    """Create (but do not start) a PlaygroundServer. Port 0 picks a free port."""
    httpd = PlaygroundServer((host, port), PlaygroundHandler)
    httpd.default_guards = list(default_guards) if default_guards else list(_DEFAULT_GUARDS)
    httpd.token = token
    httpd.store_path = store_path
    httpd.rate_buckets = {}
    httpd.rate_lock = threading.Lock()
    httpd.jobs = JobManager()
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
