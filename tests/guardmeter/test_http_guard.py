"""Tests for the generic HTTP guard against a local http.server."""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from guardmeter.guards.http_guard import HttpGuard

_LAST: dict = {}


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):  # silence
        pass

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length) or b"{}")
        _LAST["headers"] = dict(self.headers)
        _LAST["body"] = body
        if self.path == "/slow":
            import time
            time.sleep(1.0)
        if self.path == "/boom":
            self.send_response(500)
            self.end_headers()
            self.wfile.write(b'{"error":"nope"}')
            return
        flagged = "bad" in (body.get("text", "") + body.get("ctx", ""))
        payload = {"result": {"flagged": flagged, "score": 0.91 if flagged else 0.02}}
        data = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


@pytest.fixture
def server():
    srv = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


def _guard(url, **kw):
    kw.setdefault("body_template", '{"text": "{{text}}", "ctx": "{{context}}"}')
    kw.setdefault("verdict_path", "result.flagged")
    kw.setdefault("score_path", "result.score")
    return HttpGuard(url=url, **kw)


def test_verdict_and_score_mapping(server):
    g = _guard(server + "/classify")
    r = g.predict("this is bad")
    assert r.prediction == "flag"
    assert r.score == 0.91
    assert g.predict("all fine here").prediction == "pass"


def test_context_placeholder(server):
    g = _guard(server + "/classify")
    # "bad" only in context → still flagged via {{context}} substitution.
    r = g.predict("clean message", context="bad instructions")
    assert r.prediction == "flag"
    assert _LAST["body"]["ctx"] == "bad instructions"


def test_flag_values_label_mapping(server):
    # Response field is a boolean here, but flag_values still applies to strings.
    g = _guard(server + "/classify", flag_values=["flagged", "unsafe"])
    assert g.predict("bad").prediction == "flag"


def test_headers_sent(server):
    g = _guard(server + "/classify", headers={"Authorization": "Bearer secret-xyz"})
    g.predict("hello")
    assert _LAST["headers"].get("Authorization") == "Bearer secret-xyz"


def test_env_var_expansion_in_headers(server, monkeypatch):
    monkeypatch.setenv("MY_TOKEN", "tok-123")
    g = _guard(server + "/classify", headers={"Authorization": "Bearer ${MY_TOKEN}"})
    g.predict("hello")
    assert _LAST["headers"].get("Authorization") == "Bearer tok-123"


def test_non_2xx_raises(server):
    g = _guard(server + "/boom")
    with pytest.raises(RuntimeError, match="500"):
        g.predict("x")


def test_timeout_raises(server):
    g = _guard(server + "/slow", timeout=0.2)
    with pytest.raises(Exception):  # noqa: B017 (urllib raises URLError/timeout)
        g.predict("x")


def test_error_counts_as_error_via_evaluator(server):
    """A raising HTTP guard becomes an excluded 'error' result, not a flag."""
    from guardmeter.engine.evaluator import call_with_retry
    g = _guard(server + "/boom")
    r = call_with_retry(g, "x", None, sleep=lambda _: None)
    assert r.prediction == "error"
    assert "error" in r.metadata


def test_from_config():
    cfg = {"type": "http", "url": "http://example.invalid/x", "method": "POST",
           "verdict_path": "flagged", "flag_values": ["yes"], "timeout": 5}
    g = HttpGuard.from_config(cfg)
    assert g.url == "http://example.invalid/x"
    assert g.verdict_path == "flagged"
    assert g.flag_values == {"yes"}
    assert g.timeout == 5


def test_from_env(monkeypatch):
    monkeypatch.setenv("GUARDMETER_HTTP_URL", "http://example.invalid/e")
    monkeypatch.setenv("GUARDMETER_HTTP_VERDICT_PATH", "a.b")
    monkeypatch.delenv("GUARDMETER_HTTP_FLAG_VALUES", raising=False)
    g = HttpGuard()
    assert g.url == "http://example.invalid/e"
    assert g.verdict_path == "a.b"


def test_missing_url_raises(monkeypatch):
    monkeypatch.delenv("GUARDMETER_HTTP_URL", raising=False)
    with pytest.raises(ValueError, match="needs a URL"):
        HttpGuard()


def test_registered():
    from guardmeter.core.registry import import_builtin_guards, list_guards
    import_builtin_guards()
    assert "http" in list_guards()
