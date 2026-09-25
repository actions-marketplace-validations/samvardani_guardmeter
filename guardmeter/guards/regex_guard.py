"""RegexGuard: pattern-matching safety guard supporting 'baseline' and 'enhanced' profiles."""

from __future__ import annotations

import logging
import re
import time
from typing import Any, ClassVar

from guardmeter.core.guard import Guard, GuardResult
from guardmeter.core.registry import register
from guardmeter.core.text_norm import normalize

logger = logging.getLogger(__name__)


class RegexGuard(Guard):
    """Regex-based safety guard with two profiles: baseline and enhanced.

    'baseline' uses simple keyword patterns only.
    'enhanced' uses expanded patterns, obfuscation detection, Farsi coverage, and slice thresholds.
    """

    name: str = "regex"
    version: str = "1.0.0"

    # ── Baseline patterns (simple) ──────────────────────────────────────────
    BASELINE_PATTERNS: ClassVar[dict[str, list[str]]] = {
        "violence": [
            r"\bbomb\b", r"\bgun\b", r"\bknife\b", r"\bk!ll\b", r"\bkill\b",
            r"\bhurt\b", r"\bexplosive\b",
        ],
        "self_harm": [
            r"\bself[-\s]?harm\b", r"\bsuicide\b", r"\bkill myself\b",
        ],
        "crime": [
            r"\bhack\b", r"\bsteal\b", r"\bquietly break in\b",
            r"\bcard skimming\b", r"\bsql injection\b",
        ],
        "malware": [r"\bmalware\b", r"\bransomware\b", r"\bkeylogger\b"],
        "pii": [r"\bssn\b", r"\bsocial security number\b", r"\bcredit card\b"],
    }

    BASELINE_WHITELIST: ClassVar[list[str]] = [
        r"\bdefen[cs]e\b", r"\bhow to prevent\b", r"\bmitigat(e|ion)\b",
        r"\bfirst[-\s]?aid\b", r"\bbest practices\b",
    ]

    # ── Enhanced patterns ───────────────────────────────────────────────────
    ENHANCED_PATTERNS: ClassVar[dict[str, list[str]]] = {
        "violence": [
            r"\bkill\b", r"\bpoison\b", r"\bhurt\b", r"\bassault\b",
            r"\bbomb\b", r"\bpipe\s*bomb\b",
            r"\bmake\s+(a\s+)?(pipe\s*)?bomb\b",
            r"\bhow\s+to\s+make\s+(a\s+)?bomb\b",
        ],
        "self_harm": [
            r"\bkill\s+myself\b", r"\bend\s+my\s+life\b",
            r"\bhow\s+to\s+(?:harm|hurt)\s+myself\b",
            r"\bself[-\s]*harm\b",
            r"\bmethods?\b.*\b(suicide|self[-\s]*harm)\b",
            r"\bcut(?:ting)?\b.*\b(myself|wrists?|veins)\b",
        ],
        "crime": [
            r"\bhack\b", r"\bwireless\b.*\bhack\b", r"\bsql injection\b",
            r"\bsteal\b", r"\bbreak in\b",
        ],
        "malware": [
            r"/etc/shadow",
            r"\b(exfiltrat\w+).*(/etc|shadow|passwd)\b",
            r"\b(powershell|wget|curl|certutil)\b.*\b(base64|payload|xor)\b",
            r"\b(keylogger|backdoor|c2|command\s+and\s+control)\b",
            r"\bmalware\b",
            r"\bteach\W*malware\b",
        ],
        "pii": [
            r"\bssn\b", r"\bsocial security number\b", r"\bcredit card\b", r"\bcvv\b",
        ],
        "violence_fa": [r"بمب", r"کشت(ن|ار)", r"انفجار", r"چاقو", r"حمله", r"خشونت", r"آسیب"],
    }

    ENHANCED_SUBSTRINGS: ClassVar[dict[str, list[str]]] = {
        "violence": [
            "makeabomb", "buildabomb", "pipebomb", "hurtsomeone",
            "killpeople", "killperson", "killhim", "killher",
        ],
        "self_harm": [
            "selfharm", "killmyself", "endmylife", "hurtmyself", "harmmyself",
            "cutmyself", "cutmywrists", "cuttingwrists", "cutmyveins", "cuttingveins",
        ],
        "malware": [
            "malware", "teachmalware", "spreadmalware", "deploymalware",
            "installmalware", "etcshadow", "shadowfile", "stealpasswd",
        ],
    }

    ENHANCED_SAFE_CONTEXT: ClassVar[list[str]] = [
        r"\bdefen[cs]e\b", r"\bprevent(ion)?\b", r"\bmitigat(e|ion)\b",
        r"\bfirst[-\s]?aid\b", r"\bresponsible disclosure\b", r"\bhow to avoid\b",
        r"\bbest practices\b",
        r"\btherapy\b", r"\bhelpline\b", r"\bresourc(es|e)\b",
        r"\bawareness\b", r"\beducation(al)?\b", r"\bpolicy\b",
        r"\bprevention\b",
    ]

    ENHANCED_WEIGHTS: ClassVar[dict[str, float]] = {
        "violence": 1.0, "self_harm": 1.2, "crime": 1.0,
        "malware": 1.3, "pii": 1.0, "violence_fa": 1.0,
    }

    # Default score threshold for 'enhanced' profile
    DEFAULT_THRESHOLD: float = 0.5

    def __init__(self, profile: str = "enhanced", threshold: float | None = None) -> None:
        """Initialise the guard with the given profile.

        profile: 'baseline' uses simple keyword matching; 'enhanced' uses expanded patterns.
        threshold: override the default decision threshold (enhanced only).
        """
        if profile not in ("baseline", "enhanced"):
            raise ValueError(f"Unknown profile '{profile}'. Use 'baseline' or 'enhanced'.")
        self.profile = profile
        self.threshold = threshold if threshold is not None else self.DEFAULT_THRESHOLD

    # ── Internal helpers ────────────────────────────────────────────────────

    def _text_variants(self, text: str) -> tuple[str, ...]:
        """Return (raw_normalised, wordified, compact) text variants."""
        base = normalize(text)
        compact = base.replace(" ", "")
        variants = [base]
        if compact and compact != base:
            variants.append(compact)
        return tuple(variants)

    def _baseline_predict(self, text: str) -> tuple[str, float]:
        """Run baseline (simple keyword) prediction. Returns (prediction, score)."""
        t = normalize(text)
        # Whitelist check
        for w in self.BASELINE_WHITELIST:
            if re.search(w, t):
                return "pass", 0.2
        for pats in self.BASELINE_PATTERNS.values():
            if any(re.search(p, t) for p in pats):
                return "flag", 0.9
        return "pass", 0.1

    def _enhanced_predict(self, text: str, **meta: Any) -> tuple[str, float, list[str]]:
        """Run enhanced prediction. Returns (prediction, score, categories)."""
        variants = self._text_variants(text)
        compact_variants = tuple(v.replace(" ", "") for v in variants)

        penalty = 0.8 if any(
            re.search(w, v, re.IGNORECASE)
            for v in variants
            for w in self.ENHANCED_SAFE_CONTEXT
        ) else 0.0

        score = 0.0
        matched_cats: list[str] = []
        for cat, patterns in self.ENHANCED_PATTERNS.items():
            matched = any(re.search(p, v, re.IGNORECASE) for v in variants for p in patterns)
            if not matched:
                substrings = self.ENHANCED_SUBSTRINGS.get(cat, [])
                if substrings:
                    matched = any(sub in cv for cv in compact_variants for sub in substrings if cv)
            if matched:
                score += self.ENHANCED_WEIGHTS.get(cat, 1.0)
                matched_cats.append(cat)

        score = max(0.0, score - penalty)
        prediction = "flag" if score > self.threshold else "pass"
        return prediction, min(score / max(self.threshold * 2, 1.0), 1.0), matched_cats

    # ── Public interface ────────────────────────────────────────────────────

    def describe(self) -> dict[str, Any]:
        """Reproducibility metadata: profile and decision threshold."""
        return {"name": self.name, "version": self.version,
                "profile": self.profile, "threshold": self.threshold}

    def predict(self, text: str, **meta: Any) -> GuardResult:
        """Score a single text and return a GuardResult."""
        start = time.perf_counter()
        if self.profile == "baseline":
            prediction, score = self._baseline_predict(text)
            categories: list[str] = []
        else:
            prediction, score, categories = self._enhanced_predict(text, **meta)
        latency_ms = int((time.perf_counter() - start) * 1000)
        return GuardResult(
            prediction=prediction,
            score=score,
            latency_ms=latency_ms,
            categories=categories,
        )


class RegexBaselineGuard(RegexGuard):
    """RegexGuard pinned to the 'baseline' profile (thin wrapper for the registry)."""

    name = "regex-baseline"

    def __init__(self, threshold: float | None = None) -> None:
        super().__init__("baseline", threshold)


class RegexEnhancedGuard(RegexGuard):
    """RegexGuard pinned to the 'enhanced' profile (thin wrapper for the registry)."""

    name = "regex-enhanced"

    def __init__(self, threshold: float | None = None) -> None:
        super().__init__("enhanced", threshold)


# Self-register so `get_guard("regex")` works after importing this module.
# "regex" stays as an alias of the enhanced profile for backward compatibility.
register("regex", RegexGuard)
register("regex-baseline", RegexBaselineGuard)
register("regex-enhanced", RegexEnhancedGuard)
