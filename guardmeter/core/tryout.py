"""Shared guard try-out logic used by `guardmeter try` and `guardmeter serve`."""

from __future__ import annotations

import importlib
import logging
import time
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from guardmeter.core.redact import redact
from guardmeter.core.registry import get_guard, import_builtin_guards

logger = logging.getLogger(__name__)

# Upper bound on a single try-out text. Keeps interactive endpoints cheap and
# bounds the work a single request can trigger.
MAX_TEXT_CHARS = 20_000


@dataclass
class TryResult:
    """The outcome of running one guard against one text."""

    guard: str
    prediction: str
    score: float | None
    categories: list[str]
    latency_ms: float
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a JSON-compatible dict."""
        return {
            "guard": self.guard,
            "prediction": self.prediction,
            "score": self.score,
            "categories": self.categories,
            "latency_ms": self.latency_ms,
            "error": self.error,
        }


def _resolve(name: str) -> Any:
    """Resolve a guard by registry name or dotted class path."""
    if "." in name:
        module_path, cls_name = name.rsplit(".", 1)
        mod = importlib.import_module(module_path)
        cls = getattr(mod, cls_name)
        return cls()
    return get_guard(name)


def run_try(text: str, guard_names: Sequence[str]) -> list[TryResult]:
    """Run ``text`` against each named guard, returning one TryResult each.

    This never raises for a guard-level problem: a guard that cannot be
    constructed (missing package or API key) or that raises during predict
    yields a TryResult with ``error`` set, so one bad guard never hides the
    others. Raises ValueError only for input that is too long.
    """
    if len(text) > MAX_TEXT_CHARS:
        raise ValueError(f"text too long: {len(text)} chars (max {MAX_TEXT_CHARS})")

    import_builtin_guards()
    results: list[TryResult] = []
    for name in guard_names:
        start = time.perf_counter()
        try:
            guard = _resolve(name)
            result = guard.predict(text)
        except Exception as exc:  # noqa: BLE001 (one bad guard must not hide the rest)
            latency_ms = (time.perf_counter() - start) * 1000
            logger.warning("try: guard %r failed: %s", name, redact(str(exc)))
            results.append(
                TryResult(
                    guard=name,
                    prediction="error",
                    score=None,
                    categories=[],
                    latency_ms=latency_ms,
                    error=str(exc),
                )
            )
            continue
        results.append(
            TryResult(
                guard=name,
                prediction=result.prediction,
                score=float(result.score) if result.score is not None else None,
                categories=list(result.categories),
                latency_ms=float(result.latency_ms),
            )
        )
    return results
