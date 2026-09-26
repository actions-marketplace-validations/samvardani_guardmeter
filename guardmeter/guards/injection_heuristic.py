"""InjectionHeuristicGuard: a deliberately weak, documented prompt-injection baseline.

This guard exists to give the agentic dataset an *honest* floor to measure
against — not to be good. It flags a message when it contains one of a small,
hand-written set of English injection markers (or a long base64-looking blob).
It is intentionally naive in ways that the agentic dataset is designed to expose:

  - **Short literal phrases only.** It looks for "ignore previous instructions"
    and its obvious equivalent in 20+ languages. Paraphrases, role-play framing,
    and authority-spoofing slip past.
  - **Shallow encoding check.** It flags a long base64-ish run but does not
    decode it, and knows nothing about hex/rot13 tricks.
  - **Context-aware but shallow.** It scans ``meta["context"]`` with the same
    markers, so it catches the most blatant indirect injections but misses ones
    phrased as ordinary document prose.

It *is* Unicode-aware in one narrow sense: it NFKC-normalises first (so
full-width homoglyphs fold to ASCII) and raises a single crude "bidi/zero-width"
feature when it sees RTL-override characters or a long zero-width run — enough to
not crash or silently miss those tricks, not enough to be good.

Use it as the `--baseline` when evaluating a candidate: the gap between this
floor and a real guard is the number that matters — it is still the number to beat.
"""

from __future__ import annotations

import logging
import re
import time
from typing import Any, ClassVar

from guardmeter.core.guard import Guard, GuardResult
from guardmeter.core.languages import normalize_nfkc
from guardmeter.core.redact import has_bidi_controls
from guardmeter.core.registry import register
from guardmeter.core.text_norm import normalize

logger = logging.getLogger(__name__)


class InjectionHeuristicGuard(Guard):
    """A deliberately weak keyword baseline for prompt-injection detection.

    Flags on any literal injection marker below (English + short equivalents in
    20+ languages), a long base64-looking blob, or a bidi/zero-width feature.
    Surface-level, no real decoding — see the module docstring for the failure
    modes this is meant to expose. Still the number to beat.
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

    # Short, obvious "ignore previous instructions" equivalents in other languages.
    MULTILINGUAL_MARKERS: ClassVar[list[str]] = [
        r"ignora (las )?instrucciones (anteriores|previas)",       # es
        r"ignore as instruções (anteriores)?",                     # pt
        r"ignore[z]? les instructions (précédentes)?",             # fr
        r"ignoriere (alle )?(vorherigen )?anweisungen",            # de
        r"ignora le istruzioni (precedenti)?",                     # it
        r"negeer (de )?(vorige )?instructies",                     # nl
        r"zignoruj (poprzednie )?instrukcje",                      # pl
        r"игнорируй (все )?(предыдущие )?инструкции",               # ru
        r"ігноруй (всі )?(попередні )?інструкції",                 # uk
        r"önceki talimatları (yoksay|görmezden gel)",              # tr
        r"تجاهل (كل )?التعليمات( السابقة)?",                        # ar
        r"دستور(ها|های)? (قبلی|قبل) را نادیده بگیر",               # fa
        r"התעלם מ(ה)?הוראות( הקודמות)?",                           # he
        r"پچھلی ہدایات کو نظر انداز کر",                           # ur
        r"पिछले निर्देशों को अनदेखा कर",                             # hi
        r"পূর্ববর্তী নির্দেশ উপেক্ষা কর",                            # bn
        r"abaikan instruksi (sebelumnya)?",                        # id
        r"bỏ qua (các )?hướng dẫn( trước)?",                        # vi
        r"เพิกเฉย(ต่อ)?คำสั่ง(ก่อนหน้า)?",                          # th
        r"忽略(之前的|以上)?(指令|指示)",                           # zh
        r"(以前の|これまでの)?指示を無視",                          # ja
        r"이전 지시를 무시",                                        # ko
        r"puuza maagizo (yaliyopita|ya awali)",                    # sw
    ]

    # A long base64-ish run — flagged but not decoded (a real guard would decode).
    _B64 = re.compile(r"[A-Za-z0-9+/]{24,}={0,2}")
    # A suspicious zero-width run (a single ZWNJ is legitimate in fa/ar/hi).
    _ZW_RUN = re.compile("[\u200b\u200c\u200d\u2060\ufeff]{3,}")

    def __init__(self) -> None:
        self._markers = [re.compile(p, re.IGNORECASE) for p in self.MARKERS + self.MULTILINGUAL_MARKERS]

    def _hits(self, text: str) -> list[str]:
        nfkc = normalize_nfkc(text)
        # Two views: the confusable-folded one (catches homoglyph attacks that map
        # onto Latin) and the plain NFKC one (keeps genuine non-Latin scripts,
        # which the folder would otherwise Latinise). A marker hitting either counts.
        folded = normalize(nfkc)
        plain = nfkc.lower()
        hits = [m.pattern for m in self._markers if m.search(folded) or m.search(plain)]
        if self._B64.search(text):
            hits.append("base64-blob")
        # Bidi override or a long zero-width run — a single crude feature.
        if has_bidi_controls(text) or self._ZW_RUN.search(text):
            hits.append("bidi-or-zerowidth")
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
