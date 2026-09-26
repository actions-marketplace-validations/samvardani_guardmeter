"""Best-effort secret redaction for anything that might reach the logs."""

from __future__ import annotations

import re

_MASK = "***REDACTED***"

# Bidirectional control/isolate characters. Left raw, they silently reorder text
# in a terminal or a browser — a real attack surface. We render them as visible
# tokens (never strip them, so the evidence still shows they were present).
BIDI_CONTROLS: dict[str, str] = {
    "\u202a": "\u27e8LRE\u27e9", "\u202b": "\u27e8RLE\u27e9", "\u202c": "\u27e8PDF\u27e9",
    "\u202d": "\u27e8LRO\u27e9", "\u202e": "\u27e8RLO\u27e9",
    "\u2066": "\u27e8LRI\u27e9", "\u2067": "\u27e8RLI\u27e9", "\u2068": "\u27e8FSI\u27e9", "\u2069": "\u27e8PDI\u27e9",
    "\u200e": "\u27e8LRM\u27e9", "\u200f": "\u27e8RLM\u27e9",
}
_BIDI_RE = re.compile("[" + "".join(BIDI_CONTROLS) + "]")


def has_bidi_controls(text: str) -> bool:
    """True if the text contains any bidi control/isolate character."""
    return bool(text) and _BIDI_RE.search(text) is not None


def reveal_bidi(text: str) -> str:
    """Replace bidi control characters with visible ⟨RLO⟩-style tokens."""
    if not text:
        return text
    return _BIDI_RE.sub(lambda m: BIDI_CONTROLS[m.group()], text)

# Order matters: prefix-anchored provider tokens first, then generic long runs.
_SUBS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/-]{8,}=*"), "Bearer " + _MASK),
    (re.compile(r"\bsk-[A-Za-z0-9_-]{8,}"), _MASK),        # OpenAI-style keys
    (re.compile(r"\bkey-[A-Za-z0-9_-]{8,}"), _MASK),       # generic "key-" tokens
    (re.compile(r"\bAKIA[0-9A-Z]{12,}"), _MASK),           # AWS access key ids
    (re.compile(r"\b[A-Fa-f0-9]{32,}\b"), _MASK),          # long hex runs
    (re.compile(r"\b[A-Za-z0-9+/]{32,}={0,2}\b"), _MASK),  # long base64 runs
]


def redact(text: str) -> str:
    """Mask likely secrets (API keys, bearer tokens, long hex/base64 runs).

    Deliberately aggressive: this is for log lines, where masking a benign long
    token is far cheaper than leaking a real credential.
    """
    if not text:
        return text
    out = reveal_bidi(text)  # make bidi controls visible before anything else
    for pattern, replacement in _SUBS:
        out = pattern.sub(replacement, out)
    return out
