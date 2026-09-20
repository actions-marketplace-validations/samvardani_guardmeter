"""Best-effort secret redaction for anything that might reach the logs."""

from __future__ import annotations

import re

_MASK = "***REDACTED***"

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
    out = text
    for pattern, replacement in _SUBS:
        out = pattern.sub(replacement, out)
    return out
