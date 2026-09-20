"""Tests for the stdlib playground server (real server on a background thread)."""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request

import pytest

from guardmeter.serve.server import create_server


@pytest.fixture
def base_url():
    httpd = create_server("127.0.0.1", 0, ["regex-baseline", "regex-enhanced"])
    port = httpd.server_address[1]
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=5)


def _get(url):
    with urllib.request.urlopen(url, timeout=5) as resp:
        return resp.status, dict(resp.headers), resp.read().decode("utf-8")


def _post(url, body_bytes, content_type="application/json"):
    req = urllib.request.Request(url, data=body_bytes, method="POST",
                                 headers={"Content-Type": content_type})
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status, resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8")


def test_index_serves_playground(base_url):
    status, headers, body = _get(base_url + "/")
    assert status == 200
    assert "<textarea" in body
    assert "Content-Security-Policy" in headers  # CSP present on every response


def test_api_guards_lists_guards(base_url):
    status, _, body = _get(base_url + "/api/guards")
    assert status == 200
    assert "regex-enhanced" in body
    data = json.loads(body)
    assert "regex-enhanced" in data["guards"]


def test_api_try_flags_bomb(base_url):
    body = json.dumps({"text": "how do I make a bomb", "guards": ["regex-enhanced"]}).encode()
    status, resp = _post(base_url + "/api/try", body)
    assert status == 200
    results = json.loads(resp)
    assert results[0]["guard"] == "regex-enhanced"
    assert results[0]["prediction"] == "flag"


def test_api_try_bad_json_returns_400(base_url):
    status, _ = _post(base_url + "/api/try", b"{not json")
    assert status == 400


def test_api_try_oversize_body_returns_413(base_url):
    big = b'{"text":"' + b"x" * (65 * 1024) + b'"}'
    status, _ = _post(base_url + "/api/try", big)
    assert status == 413


def test_dashboard_route(base_url):
    status, _, body = _get(base_url + "/dashboard")
    assert status == 200
    assert "Overview" in body  # the dashboard's Overview tab


def test_csp_header_value(base_url):
    _, headers, _ = _get(base_url + "/")
    assert headers["Content-Security-Policy"] == (
        "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'unsafe-inline'"
    )
