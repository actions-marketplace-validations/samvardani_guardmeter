"""Pydantic schema for a single dataset record."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

# Canonical harm-category vocabulary used across GuardMeter datasets. The
# DatasetRecord.category field holds one of these for unsafe/borderline rows
# (safe rows use "benign"). This is the single source of truth for adapters
# that need to emit categories — do not fork a different taxonomy.
CATEGORY_VOCABULARY: list[str] = [
    "crime",
    "malware",
    "pii",
    "self_harm",
    "violence",
    "prompt_injection",
]


class DatasetRecord(BaseModel):
    """A single labelled evaluation sample."""

    text: str
    label: Literal["benign", "borderline", "unsafe"]
    category: str
    language: str = "en"
    source: str = "unknown"
    attack_type: str | None = None
