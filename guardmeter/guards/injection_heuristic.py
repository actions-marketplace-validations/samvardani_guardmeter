"""InjectionHeuristicGuard: a deliberately weak, documented prompt-injection baseline.

This guard exists to give the agentic dataset an *honest* floor to measure
against — not to be good. It flags a message when it contains one of a small,
hand-written set of English injection markers (or a long base64-looking blob).
It is intentionally naive in ways that the agentic dataset is designed to expose:

  - **English-only markers.** It has no Farsi patterns, so it misses the entire
    `fa` half of the dataset. This is deliberate: it demonstrates why a keyword
    guard tuned on English data silently fails on other languages.
  - **Surface-string matching.** It looks for literal phrases like "ignore
    previous instructions". Paraphrases ("disregard what you were told
    earlier"), role-play framing, and authority-spoofing slip past.
  - **Shallow encoding check.** It flags a long base64-ish run but does not
    decode it, and knows nothing about hex/rot13/homoglyph/zero-width tricks.
  - **Context-aware but shallow.** It scans ``meta["context"]`` with the same
    markers, so it catches the most blatant indirect injections but misses ones
    phrased as ordinary document prose.

Use it as the `--baseline` when evaluating a candidate on the agentic dataset:
the gap between this floor and a real guard is the number that matters.
"""

from __future__ import annotations

import logging
import re
import time
from typing import Any, ClassVar

from guardmeter.core.guard import Guard, GuardResult
from guardmeter.core.registry import register
from guardmeter.core.text_norm import normalize

logger = logging.getLogger(__name__)


class InjectionHeuristicGuard(Guard):
    """A deliberately weak keyword baseline for prompt-injection detection.

    Flags on any literal injection marker below, or on a long base64-looking
    blob. English-only, surface-level, no real decoding — see the module
    docstring for the failure modes this is meant to expose.
    """

    name: str = "injection-heuristic"
    version: str = "1.0.0"

    # Literal English injection markers. Deliberately small and surface-level.
    MARKERS: ClassVar[list[str]] = [
        r"ignore (all )?(previous|prior|earlier) (instructions|prompts?)",
        r"disregard (the )?(above|previous|prior) (instructions|rules)",
        r"forget (your|the|all) (instructions|rules|guidelines)",
        r"system prompt",
        r"reveal (your|the) (system )?(prompt|instructions|rules)",
        r"you are now",
        r"developer mode",
        r"do anything now",
        r"\bdan\b",
        r"override (your|the|all|safety)",
        r"exfiltrate",
        r"send (all|the) (files?|data|contents?)",
        r"email (all|the|every) (files?|data|contents?)",
    ]

    # A long base64-ish run — flagged but not decoded (a real guard would decode).
    _B64 = re.compile(r"[A-Za-z0-9+/]{24,}={0,2}")

    def __init__(self) -> None:
        self._markers = [re.compile(p, re.IGNORECASE) for p in self.MARKERS]

    def _hits(self, text: str) -> list[str]:
        t = normalize(text)
        hits = [m.pattern for m in self._markers if m.search(t)]
        if self._B64.search(text):
            hits.append("base64-blob")
        return hits

    def predict(self, text: str, **meta: Any) -> GuardResult:
        """Flag if any injection marker appears in the text or its context."""
        start = time.perf_counter()
        hits = self._hits(text)
        context = meta.get("context")
        if context:
            hits += [h for h in self._hits(context) if h not in hits]
        prediction = "flag" if hits else "pass"
        score = min(1.0, 0.5 + 0.25 * len(hits)) if hits else 0.05
        latency_ms = int((time.perf_counter() - start) * 1000)
        return GuardResult(
            prediction=prediction,
            score=score,
            latency_ms=latency_ms,
            categories=["prompt_injection"] if hits else [],
            metadata={"markers": hits},
        )


register("injection-heuristic", InjectionHeuristicGuard)
