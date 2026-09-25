"""Tests for the rollout webhook (run_rollout_hook + POST /api/hooks/rollout)."""

from __future__ import annotations

import json
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from guardmeter.serve.api import run_rollout_hook
from guardmeter.store.sqlite import SQLiteStore

_MODE = {"answer": "refund within 30 days", "slow": False}


class _FakeOpenAI(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_POST(self):
        self.rfile.read(int(self.headers.get("Content-Length", 0)))
        if _MODE["slow"]:
            time.sleep(2)
        payload = {"choices": [{"message": {"role": "assistant", "content": _MODE["answer"]}}],
                   "usage": {"completion_tokens": 5}}
        data = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


@pytest.fixture
def openai():
    _MODE["answer"] = "refund within 30 days"
    _MODE["slow"] = False
    srv = ThreadingHTTPServer(("127.0.0.1", 0), _FakeOpenAI)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}/v1"
    srv.shutdown()


_SUITE = """\
suite: {name: hooktest, version: "1.0", reviewed_by: [x]}
scenarios:
  - id: s1
    category: support
    reviewed_by: x
    input: {text: "refund policy?"}
    expect: [{must_contain: {patterns: ["refund"]}}]
"""


def _write_suite(tmp_path):
    p = tmp_path / "suite.yaml"
    p.write_text(_SUITE, encoding="utf-8")
    return p


def test_hook_passes(openai, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    suite = _write_suite(tmp_path)
    store = SQLiteStore(db_path=tmp_path / "h.db")
    out = run_rollout_hook(store, {"suite": str(suite), "endpoint": openai, "model": "m"}, 30.0)
    assert out["passed"] is True
    assert out["pass_rate"] == 1.0
    assert out["regressions"] == []


def test_hook_detects_regression(openai, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    suite = _write_suite(tmp_path)
    store = SQLiteStore(db_path=tmp_path / "h.db")
    # First run passes.
    run_rollout_hook(store, {"suite": str(suite), "endpoint": openai, "model": "m"}, 30.0)
    # Second run: the model now answers wrong → s1 regresses from pass.
    _MODE["answer"] = "no idea"
    out = run_rollout_hook(store, {"suite": str(suite), "endpoint": openai, "model": "m"}, 30.0)
    assert out["passed"] is False
    assert "s1" in out["regressions"]


def test_hook_timeout(openai, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    suite = _write_suite(tmp_path)
    store = SQLiteStore(db_path=tmp_path / "h.db")
    _MODE["slow"] = True
    with pytest.raises(TimeoutError):
        run_rollout_hook(store, {"suite": str(suite), "endpoint": openai, "model": "m"}, 0.3)


def test_hook_missing_suite(tmp_path):
    store = SQLiteStore(db_path=tmp_path / "h.db")
    with pytest.raises(FileNotFoundError):
        run_rollout_hook(store, {"suite": str(tmp_path / "nope.yaml"),
                                 "endpoint": "http://x/v1", "model": "m"}, 5.0)


def test_hook_endpoint_via_server(openai, tmp_path, monkeypatch):
    from guardmeter.serve.server import create_server
    monkeypatch.chdir(tmp_path)
    suite = _write_suite(tmp_path)
    db = tmp_path / "h.db"
    SQLiteStore(db_path=db)
    httpd = create_server("127.0.0.1", 0, store_path=str(db))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        base = f"http://127.0.0.1:{httpd.server_address[1]}"
        body = json.dumps({"suite": str(suite), "endpoint": openai, "model": "m"}).encode()
        req = urllib.request.Request(base + "/api/hooks/rollout", data=body,
                                     headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=30) as resp:
            out = json.loads(resp.read())
        assert out["passed"] is True
        assert out["run_id"]
    finally:
        httpd.shutdown(); httpd.server_close()
