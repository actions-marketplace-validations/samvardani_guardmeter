"""Shared client-side rate limiting and retry for hosted-guard adapters.

- ``RateLimiter`` paces calls to at most ``rpm`` requests per minute so a run
  never exceeds an account limit.
- ``call_with_retry`` honours HTTP 429 + ``Retry-After`` and retries transient
  5xx / timeouts with jittered exponential backoff. It re-raises the last error
  after ``max_attempts`` — callers turn that into a guard ``error`` prediction,
  never an ``allow``.
"""
from __future__ import annotations

import random
import time
from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")


class RateLimiter:
    """Spaces calls to at most ``rpm`` per minute (0/None = unlimited)."""

    def __init__(self, rpm: float | None) -> None:
        self.min_interval = 60.0 / rpm if rpm and rpm > 0 else 0.0
        self._last = 0.0

    def wait(self) -> None:
        if self.min_interval <= 0:
            return
        now = time.monotonic()
        gap = self.min_interval - (now - self._last)
        if gap > 0:
            time.sleep(gap)
        self._last = time.monotonic()


def _status_code(exc: Exception) -> int | None:
    return getattr(exc, "status_code", None)


def _retry_after(exc: Exception) -> float | None:
    """Seconds from a Retry-After header on a 429, if present."""
    resp = getattr(exc, "response", None)
    headers = getattr(resp, "headers", None)
    if not headers:
        return None
    val = headers.get("retry-after") or headers.get("Retry-After")
    try:
        return float(val) if val is not None else None
    except (TypeError, ValueError):
        return None


def call_with_retry(
    fn: Callable[[], T],
    *,
    max_attempts: int = 5,
    base_delay: float = 2.0,
    limiter: RateLimiter | None = None,
    retry_statuses: tuple[int, ...] = (429, 500, 502, 503, 504),
    sleep: Callable[[float], None] = time.sleep,
    rng: Callable[[], float] = random.random,
) -> T:
    """Call ``fn`` with rate limiting and retry. Re-raises after ``max_attempts``.

    ``sleep``/``rng`` are injectable for tests. 429 honours ``Retry-After``;
    other retryable statuses use jittered exponential backoff.
    """
    last: Exception | None = None
    for attempt in range(max_attempts):
        if limiter is not None:
            limiter.wait()
        try:
            return fn()
        except Exception as exc:
            code = _status_code(exc)
            retryable = code in retry_statuses or code is None and _is_timeout(exc)
            if not retryable or attempt == max_attempts - 1:
                raise
            last = exc
            if code == 429 and (ra := _retry_after(exc)) is not None:
                delay = ra
            else:
                delay = base_delay * (2 ** attempt)
            delay += rng() * base_delay  # jitter
            sleep(delay)
    assert last is not None
    raise last


def _is_timeout(exc: Exception) -> bool:
    name = type(exc).__name__.lower()
    return "timeout" in name or "connection" in name
