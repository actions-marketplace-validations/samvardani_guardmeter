"""Rate limiting + retry: 429/Retry-After, backoff, rpm pacing, terminal errors."""
from __future__ import annotations

import pytest

from guardmeter.guards._ratelimit import RateLimiter, call_with_retry


class _HTTPError(Exception):
    def __init__(self, code, retry_after=None):
        super().__init__(f"http {code}")
        self.status_code = code
        if retry_after is not None:
            self.response = type("R", (), {"headers": {"Retry-After": str(retry_after)}})()


def test_rate_limiter_interval():
    assert RateLimiter(60).min_interval == pytest.approx(1.0)
    assert RateLimiter(35).min_interval == pytest.approx(60 / 35)
    assert RateLimiter(None).min_interval == 0.0
    assert RateLimiter(0).min_interval == 0.0


def test_succeeds_first_try():
    slept = []
    out = call_with_retry(lambda: "ok", sleep=slept.append, rng=lambda: 0.0)
    assert out == "ok" and slept == []


def test_429_honors_retry_after():
    slept = []
    calls = {"n": 0}

    def fn():
        calls["n"] += 1
        if calls["n"] == 1:
            raise _HTTPError(429, retry_after=7)
        return "ok"

    out = call_with_retry(fn, sleep=slept.append, rng=lambda: 0.0, base_delay=2.0)
    assert out == "ok"
    assert slept == [7.0]  # used Retry-After, not exponential backoff


def test_retries_5xx_then_gives_up_and_reraises():
    slept = []
    with pytest.raises(_HTTPError):
        call_with_retry(lambda: (_ for _ in ()).throw(_HTTPError(503)),
                        max_attempts=3, base_delay=1.0, sleep=slept.append, rng=lambda: 0.0)
    assert len(slept) == 2  # two backoffs before the third (final) attempt raises


def test_non_retryable_raises_immediately():
    slept = []
    with pytest.raises(_HTTPError):
        call_with_retry(lambda: (_ for _ in ()).throw(_HTTPError(400)),
                        sleep=slept.append, rng=lambda: 0.0)
    assert slept == []  # 400 is terminal, no retry


def test_timeout_by_name_is_retried():
    class ConnectTimeout(Exception):
        status_code = None

    calls = {"n": 0}

    def fn():
        calls["n"] += 1
        if calls["n"] < 2:
            raise ConnectTimeout("timed out")
        return "ok"

    out = call_with_retry(fn, sleep=lambda _: None, rng=lambda: 0.0)
    assert out == "ok" and calls["n"] == 2
