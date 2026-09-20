"""Tests for the stdlib playground server (real server on a background thread)."""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request

import pytest

from guardmeter.serve.server import RATE_CAPACITY, create_server, run_server


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


def _post(url, body_bytes, content_type="application/json", headers=None):
    hdrs = {"Content-Type": content_type}
    hdrs.update(headers or {})
    req = urllib.request.Request(url, data=body_bytes, method="POST", headers=hdrs)
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status, dict(resp.headers), resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        return exc.code, dict(exc.headers), exc.read().decode("utf-8")


def _get_status(url, headers=None):
    req = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status
    except urllib.error.HTTPError as exc:
        return exc.code


def _start(httpd):
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    return thread


def test_index_serves_app_shell(base_url):
    status, headers, body = _get(base_url + "/")
    assert status == 200
    assert 'id="app"' in body and "app.js" in body
    assert "Content-Security-Policy" in headers  # CSP present on every response


def test_spa_fallback_deeplink(base_url):
    # A client-side route path returns the app shell (200), not a 404.
    status, _, body = _get(base_url + "/run/whatever")
    assert status == 200
    assert 'id="app"' in body


def test_api_guards_lists_guards(base_url):
    status, _, body = _get(base_url + "/api/guards")
    assert status == 200
    assert "regex-enhanced" in body
    data = json.loads(body)
    assert "regex-enhanced" in data["guards"]


def test_api_try_flags_bomb(base_url):
    body = json.dumps({"text": "how do I make a bomb", "guards": ["regex-enhanced"]}).encode()
    status, _, resp = _post(base_url + "/api/try", body)
    assert status == 200
    results = json.loads(resp)
    assert results[0]["guard"] == "regex-enhanced"
    assert results[0]["prediction"] == "flag"


def test_api_try_bad_json_returns_400(base_url):
    status, _, _ = _post(base_url + "/api/try", b"{not json")
    assert status == 400


def test_api_try_oversize_body_returns_413(base_url):
    big = b'{"text":"' + b"x" * (65 * 1024) + b'"}'
    status, _, _ = _post(base_url + "/api/try", big)
    assert status == 413


def test_unknown_api_route_404(base_url):
    assert _get_status(base_url + "/api/nope") == 404


def test_static_css_served(base_url):
    status, headers, body = _get(base_url + "/static/styles.css")
    assert status == 200
    assert headers["Content-Type"].startswith("text/css")
    assert "--accent" in body  # design tokens present


def test_static_js_module_served(base_url):
    status, headers, _ = _get(base_url + "/static/theme.js")
    assert status == 200
    assert "javascript" in headers["Content-Type"]


def test_read_static_rejects_traversal():
    from guardmeter.serve.server import read_static
    assert read_static("../server.py") is None
    assert read_static("/etc/passwd") is None
    assert read_static("styles.css") is not None


def test_styleguide_route(base_url):
    status, _, body = _get(base_url + "/styleguide")
    assert status == 200
    assert "Style Guide" in body


def test_chart_js_served_via_fallback(base_url):
    status, headers, _ = _get(base_url + "/static/chart.umd.min.js")
    assert status == 200
    assert "javascript" in headers["Content-Type"]


def test_csp_header_value(base_url):
    _, headers, _ = _get(base_url + "/")
    assert headers["Content-Security-Policy"] == (
        "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'"
    )


def test_token_required_for_api():
    """With a token set, /api/* needs a matching Bearer header."""
    httpd = create_server("127.0.0.1", 0, ["regex-enhanced"], token="s3cret")
    port = httpd.server_address[1]
    thread = _start(httpd)
    base = f"http://127.0.0.1:{port}"
    try:
        assert _get_status(base + "/api/guards") == 401
        assert _get_status(base + "/api/guards", {"Authorization": "Bearer s3cret"}) == 200
        assert _get_status(base + "/api/guards", {"Authorization": "Bearer wrong"}) == 401
        # The page itself (no /api) stays open so it can prompt for the token.
        assert _get_status(base + "/") == 200
        body = json.dumps({"text": "hi", "guards": ["regex-enhanced"]}).encode()
        status, _, _ = _post(base + "/api/try", body)
        assert status == 401
        status, _, _ = _post(base + "/api/try", body, headers={"Authorization": "Bearer s3cret"})
        assert status == 200
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=5)


def test_rate_limit_429_with_retry_after(base_url):
    """The 31st /api/try from one IP within the window is rate-limited."""
    body = json.dumps({"text": "hi", "guards": ["regex-baseline"]}).encode()
    statuses = []
    headers_429 = {}
    for _ in range(RATE_CAPACITY + 1):
        status, headers, _ = _post(base_url + "/api/try", body)
        statuses.append(status)
        if status == 429:
            headers_429 = headers
    assert statuses[:RATE_CAPACITY] == [200] * RATE_CAPACITY
    assert statuses[RATE_CAPACITY] == 429
    assert "Retry-After" in headers_429


def test_offloopback_without_token_refuses(monkeypatch):
    """Binding a non-loopback host with no token raises before serving."""
    monkeypatch.delenv("GUARDMETER_TOKEN", raising=False)
    with pytest.raises(RuntimeError, match="non-loopback"):
        run_server(host="0.0.0.0", port=0)
