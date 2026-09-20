"""Text normalization: leetspeak decoding, Unicode cleanup, obfuscation collapse."""

from __future__ import annotations

import re
import unicodedata

LEETSPEAK = {"0": "o", "1": "i", "3": "e", "4": "a", "5": "s", "7": "t", "!": "i", "$": "s"}

ZERO_WIDTH = {"\u200b", "\u200c", "\u200d", "\ufeff"}
TATWEEL = "\u0640"
CONFUSABLES_REV = {
    "а": "a", "е": "e", "ο": "o", "р": "p", "с": "c", "х": "x", "у": "y",
    "Н": "H", "Κ": "K", "М": "M",
}
LEET_REV = str.maketrans(
    {"4": "a", "3": "e", "1": "i", "0": "o", "5": "s", "7": "t",
     "8": "b", "9": "g", "!": "i", "@": "a", "$": "s"}
)


def normalize(text: str) -> str:
    """Normalize text: NFKC → zero-width removal → confusables → leetspeak → spacing.

    Collapses spaced-out characters like 'b o m b' → 'bomb'.
    """
    t = unicodedata.normalize("NFKC", text or "")
    # Remove zero-width characters and Arabic tatweel
    t = "".join(ch for ch in t if ch not in ZERO_WIDTH)
    t = t.replace(TATWEEL, "")
    # Replace confusable Unicode lookalikes with ASCII equivalents
    t = "".join(CONFUSABLES_REV.get(ch, ch) for ch in t)
    # Decode leetspeak digits/symbols
    t = t.translate(LEET_REV)
    # Collapse 'b o m b' → 'bomb' (4+ spaced single chars)
    def _join(m: re.Match[str]) -> str:
        return m.group(0).replace(" ", "")

    t = re.sub(r"(?:[a-zA-Z]\s){3,}[a-zA-Z]", _join, t)
    # Normalise separators and whitespace
    t = re.sub(r"[\\/_]+", " ", t)
    t = re.sub(r"-+", " ", t)
    t = re.sub(r"\s+", " ", t)
    return t.lower().strip()
