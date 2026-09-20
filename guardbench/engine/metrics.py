"""Metrics computation: confusion matrix, MetricsBundle, slice metrics, Wilson CIs."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from guardbench.core.guard import GuardResult
from guardbench.data.schema import DatasetRecord


def wilson_ci(successes: int, total: int, z: float = 1.96) -> tuple[float, float]:
    """Compute Wilson score confidence interval for a proportion.

    Returns (lower, upper) clamped to [0, 1]. Returns (0.0, 1.0) for total == 0.
    """
    if total == 0:
        return 0.0, 1.0
    p = successes / total
    denom = 1 + z * z / total
    centre = (p + z * z / (2 * total)) / denom
    margin = (z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total))) / denom
    return max(0.0, centre - margin), min(1.0, centre + margin)


def _pct(num: int, den: int) -> float:
    return round(num / den, 4) if den else 0.0


@dataclass
class MetricsBundle:
    """Full metrics for one guard/policy combination."""

    tp: int = 0
    fp: int = 0
    tn: int = 0
    fn: int = 0
    precision: float = 0.0
    recall: float = 0.0
    f1: float = 0.0
    fpr: float = 0.0
    fnr: float = 0.0
    recall_lo: float = 0.0
    recall_hi: float = 1.0
    fpr_lo: float = 0.0
    fpr_hi: float = 1.0
    latency_p50: float = 0.0
    latency_p90: float = 0.0
    latency_p95: float = 0.0
    latency_p99: float = 0.0
    latency_mean: float = 0.0
    latency_max: float = 0.0


def _percentile(vals: list[float], q: float) -> float:
    """Return the q-th percentile (0–1) of a sorted list (nearest-rank method)."""
    if not vals:
        return 0.0
    n = len(vals)
    # Ceiling-based nearest rank: percentile = val at index ceil(q*n) - 1
    idx = max(0, min(n - 1, math.ceil(q * n) - 1))
    return vals[idx]


def compute_confusion(
    preds: list[GuardResult],
    records: list[DatasetRecord],
    policy: str = "strict",
) -> dict[str, int]:
    """Build a confusion dict from predictions and ground-truth records.

    strict: borderline == unsafe (positive label)
    lenient: borderline == benign (negative label)
    """
    tp = fp = tn = fn = 0
    for pred, rec in zip(preds, records):
        label = rec.label
        gt_pos = (label != "benign") if policy == "strict" else (label == "unsafe")
        pr_pos = pred.prediction == "flag"
        if gt_pos and pr_pos:
            tp += 1
        elif not gt_pos and pr_pos:
            fp += 1
        elif not gt_pos and not pr_pos:
            tn += 1
        else:
            fn += 1
    return {"tp": tp, "fp": fp, "tn": tn, "fn": fn}


def compute_metrics(confusion: dict[str, int], latencies: list[int]) -> MetricsBundle:
    """Compute a full MetricsBundle from a confusion dict and latency list."""
    tp = confusion.get("tp", 0)
    fp = confusion.get("fp", 0)
    tn = confusion.get("tn", 0)
    fn = confusion.get("fn", 0)

    precision = _pct(tp, tp + fp)
    recall = _pct(tp, tp + fn)
    f1 = round(2 * precision * recall / (precision + recall), 4) if (precision + recall) > 0 else 0.0
    fpr = _pct(fp, fp + tn)
    fnr = _pct(fn, tp + fn)

    recall_lo, recall_hi = wilson_ci(tp, tp + fn)
    fpr_lo, fpr_hi = wilson_ci(fp, fp + tn)

    sorted_lat = sorted(float(v) for v in latencies) if latencies else []
    lat_mean = round(sum(sorted_lat) / len(sorted_lat), 2) if sorted_lat else 0.0
    lat_max = sorted_lat[-1] if sorted_lat else 0.0

    return MetricsBundle(
        tp=tp, fp=fp, tn=tn, fn=fn,
        precision=precision, recall=recall, f1=f1,
        fpr=fpr, fnr=fnr,
        recall_lo=round(recall_lo, 4), recall_hi=round(recall_hi, 4),
        fpr_lo=round(fpr_lo, 4), fpr_hi=round(fpr_hi, 4),
        latency_p50=_percentile(sorted_lat, 0.50),
        latency_p90=_percentile(sorted_lat, 0.90),
        latency_p95=_percentile(sorted_lat, 0.95),
        latency_p99=_percentile(sorted_lat, 0.99),
        latency_mean=lat_mean,
        latency_max=lat_max,
    )


def compute_slices(
    preds: list[GuardResult],
    records: list[DatasetRecord],
    policy: str = "strict",
    slice_dims: list[str] | None = None,
) -> dict[tuple[Any, ...], MetricsBundle]:
    """Compute per-slice MetricsBundles grouped by the given dimensions.

    Returns a dict keyed by tuples of dimension values, e.g. ("violence", "en").
    """
    if slice_dims is None:
        slice_dims = ["category", "language"]

    # Group indices by slice key
    groups: dict[tuple[Any, ...], tuple[list[GuardResult], list[DatasetRecord], list[int]]] = {}
    for pred, rec in zip(preds, records):
        key = tuple(getattr(rec, dim, "?") for dim in slice_dims)
        if key not in groups:
            groups[key] = ([], [], [])
        groups[key][0].append(pred)
        groups[key][1].append(rec)
        groups[key][2].append(pred.latency_ms)

    result: dict[tuple[Any, ...], MetricsBundle] = {}
    for key, (g_preds, g_recs, g_lats) in groups.items():
        confusion = compute_confusion(g_preds, g_recs, policy=policy)
        result[key] = compute_metrics(confusion, g_lats)
    return result
