"""Abstract base class and result type for all guards."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class GuardResult:
    """Result produced by a guard's predict call.

    ``prediction`` is "pass", "flag", or "error". An "error" result means the
    guard call itself failed (after retries) and could not produce a verdict;
    it has ``score=None`` and is excluded from metrics rather than counted as a
    flag. See ``guardmeter.engine.evaluator.call_with_retry``.
    """

    prediction: str  # "pass" | "flag" | "error"
    score: float | None  # 0.0 – 1.0, or None for an "error" result
    latency_ms: int
    categories: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class Guard(ABC):
    """Abstract base class that every guard must implement."""

    name: str = "unnamed"
    version: str = "0.0.0"
    # True for guards that make a network call per prediction (LLM adapters).
    # The evaluator/CLI default to concurrent evaluation for these.
    is_remote: bool = False

    @abstractmethod
    def predict(self, text: str, **meta: Any) -> GuardResult:
        """Score a single text and return a GuardResult.

        Per-record metadata arrives via ``**meta``. Notably ``meta["context"]``
        (a str or None) carries prior turns or the surrounding document for
        multi-turn and indirect-injection datasets; context-aware guards should
        use it, and simple guards may ignore it.
        """
        ...

    def batch_predict(self, texts: list[str], **meta: Any) -> list[GuardResult]:
        """Score a list of texts; defaults to sequential predict calls."""
        return [self.predict(t, **meta) for t in texts]
