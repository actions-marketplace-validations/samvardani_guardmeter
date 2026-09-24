"""Concurrency and retry/backoff for guard evaluation."""

from __future__ import annotations

import threading
import time

from guardmeter.core.guard import Guard, GuardResult
from guardmeter.data.schema import DatasetRecord
from guardmeter.engine.evaluator import EvalConfig, Evaluator, call_with_retry

FAKE_KEY = "sk-SECRET0000000000000000"


class _SleepGuard(Guard):
    """Guard that sleeps per call and records max concurrent in-flight calls."""

    name = "sleepy"

    def __init__(self, delay=0.05):
        self.delay = delay
        self._lock = threading.Lock()
        self.inflight = 0
        self.max_inflight = 0

    def predict(self, text, **meta):
        with self._lock:
            self.inflight += 1
            self.max_inflight = max(self.max_inflight, self.inflight)
        time.sleep(self.delay)
        with self._lock:
            self.inflight -= 1
        return GuardResult(prediction="flag" if "bad" in text else "pass", score=0.5, latency_ms=1)


def _dataset(n):
    return [DatasetRecord(text=f"bad {i}" if i % 2 else f"ok {i}",
                          label="unsafe" if i % 2 else "benign",
                          category="violence" if i % 2 else "benign") for i in range(n)]


def test_concurrency_runs_in_parallel():
    ds = _dataset(8)

    def run(concurrency):
        g = _SleepGuard(delay=0.05)
        t = time.perf_counter()
        Evaluator(g, g, ds, EvalConfig(concurrency=concurrency)).run()
        return time.perf_counter() - t, g.max_inflight

    serial, serial_inflight = run(1)
    parallel, parallel_inflight = run(4)
    # Concurrency 1 never overlaps; concurrency 4 clearly does and finishes faster.
    assert serial_inflight == 1
    assert parallel_inflight >= 3
    assert parallel < serial * 0.6


def test_ordering_is_deterministic():
    ds = _dataset(20)

    class _EchoGuard(Guard):
        name = "echo"

        def predict(self, text, **meta):
            # Randomised sleep so completion order != submission order.
            time.sleep(0.001 * (hash(text) % 7))
            return GuardResult(prediction="flag" if "bad" in text else "pass",
                               score=0.5, latency_ms=1, categories=[text])

    g = _EchoGuard()
    results = Evaluator(g, g, ds, EvalConfig(concurrency=8)).run()
    # sample_results must line up with the dataset order.
    assert [s.text for s in results.sample_results] == [r.text for r in ds]


def test_retry_then_success():
    calls = {"n": 0}

    class _FlakyGuard(Guard):
        name = "flaky"

        def predict(self, text, **meta):
            calls["n"] += 1
            if calls["n"] < 3:
                raise RuntimeError("429 Too Many Requests")
            return GuardResult(prediction="flag", score=0.9, latency_ms=1)

    slept: list[float] = []
    r = call_with_retry(_FlakyGuard(), "x", None, backoff_base=0.01, sleep=slept.append)
    assert r.prediction == "flag"
    assert calls["n"] == 3
    assert len(slept) == 2  # two retries before the third success


def test_retry_exhausted_fails_closed_with_error():
    class _AlwaysLimited(Guard):
        name = "limited"

        def predict(self, text, **meta):
            raise RuntimeError("rate limit exceeded")

    r = call_with_retry(_AlwaysLimited(), "x", None, max_retries=2, backoff_base=0.0, sleep=lambda _: None)
    assert r.prediction == "error"       # a failed call is not a verdict
    assert r.score is None
    assert "error" in r.metadata
    assert r.metadata["attempts"] == 3   # initial + 2 retries
    assert not r.metadata.get("hijacked")


def test_non_rate_limit_error_not_retried_and_redacted():
    calls = {"n": 0}

    class _AuthError(Guard):
        name = "auth"

        def predict(self, text, **meta):
            calls["n"] += 1
            raise RuntimeError(f"401 unauthorized token={FAKE_KEY}")

    r = call_with_retry(_AuthError(), "x", None, sleep=lambda _: None)
    assert calls["n"] == 1               # not a rate limit → no retry
    assert r.prediction == "error"
    assert r.metadata["attempts"] == 1
    assert FAKE_KEY not in r.metadata["error"]
    assert "REDACTED" in r.metadata["error"]
