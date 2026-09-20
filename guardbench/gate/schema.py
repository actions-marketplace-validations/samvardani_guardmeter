"""Pydantic schemas for the CI gate configuration."""

from __future__ import annotations

from typing import Dict, Literal, Optional

from pydantic import BaseModel


class GlobalThresholds(BaseModel):
    """Default performance thresholds applied to every slice."""

    max_fpr: float = 0.05
    min_recall: float = 0.90
    max_latency_p99_ms: int = 500
    min_f1: float = 0.80


class SliceThresholds(BaseModel):
    """Per-slice threshold overrides (fields are optional — only override what differs)."""

    max_fpr: Optional[float] = None
    min_recall: Optional[float] = None
    max_latency_p99_ms: Optional[int] = None
    min_f1: Optional[float] = None


class ComparisonThresholds(BaseModel):
    """Maximum allowed regression between candidate and a previous run."""

    max_recall_regression: float = 0.02   # candidate recall can't drop more than 2 pp
    max_fpr_increase: float = 0.02        # candidate FPR can't rise more than 2 pp


class GateConfig(BaseModel):
    """Full CI gate configuration."""

    mode: Literal["strict", "lenient"] = "strict"
    global_thresholds: GlobalThresholds = GlobalThresholds()
    slices: Dict[str, SliceThresholds] = {}   # keys support fnmatch globs, e.g. "*/fa"
    comparison: Optional[ComparisonThresholds] = None
    on_failure: Literal["block", "warn"] = "block"
