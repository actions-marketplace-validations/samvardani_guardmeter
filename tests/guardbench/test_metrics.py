"""Tests for metrics computation."""

from __future__ import annotations

from guardbench.core.guard import GuardResult
from guardbench.data.schema import DatasetRecord
from guardbench.engine.metrics import (
    compute_confusion,
    compute_metrics,
    compute_slices,
    wilson_ci,
)


def _make_preds(predictions):
    """Build minimal GuardResult objects from prediction strings."""
    return [GuardResult(prediction=p, score=1.0 if p == "flag" else 0.0, latency_ms=i * 2)
            for i, p in enumerate(predictions)]


def _make_records(labels, categories=None, languages=None):
    """Build minimal DatasetRecord objects."""
    cats = categories or ["violence"] * len(labels)
    langs = languages or ["en"] * len(labels)
    return [
        DatasetRecord(text=f"text{i}", label=l, category=c, language=lang)
        for i, (l, c, lang) in enumerate(zip(labels, cats, langs))
    ]


class TestWilsonCI:
    def test_all_success(self):
        lo, hi = wilson_ci(10, 10)
        assert 0.0 <= lo <= hi <= 1.0

    def test_zero_total(self):
        lo, hi = wilson_ci(0, 0)
        assert lo == 0.0
        assert hi == 1.0

    def test_zero_successes(self):
        lo, hi = wilson_ci(0, 10)
        assert 0.0 <= lo <= hi <= 1.0

    def test_bounds_clamped(self):
        lo, hi = wilson_ci(5, 5)
        assert lo >= 0.0
        assert hi <= 1.0


class TestComputeMetrics:
    def test_all_tp_case(self):
        """Perfect detection: all unsafe flagged, all benign passed."""
        preds = _make_preds(["flag", "flag", "pass", "pass"])
        records = _make_records(["unsafe", "unsafe", "benign", "benign"])
        confusion = compute_confusion(preds, records)
        bundle = compute_metrics(confusion, [1, 2, 3, 4])
        assert bundle.precision == 1.0
        assert bundle.recall == 1.0
        assert bundle.fpr == 0.0

    def test_zero_division_handled(self):
        """All benign: tp=0, fn=0, fp=0, tn=N — no ZeroDivisionError."""
        preds = _make_preds(["pass", "pass"])
        records = _make_records(["benign", "benign"])
        confusion = compute_confusion(preds, records)
        bundle = compute_metrics(confusion, [1, 2])
        # Should return 0.0 without raising
        assert bundle.recall == 0.0
        assert bundle.precision == 0.0

    def test_latency_percentiles(self):
        """Percentiles computed correctly on known list."""
        latencies = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
        preds = _make_preds(["pass"] * 10)
        records = _make_records(["benign"] * 10)
        confusion = compute_confusion(preds, records)
        bundle = compute_metrics(confusion, latencies)
        # p50 should be around 50
        assert bundle.latency_p50 == 50.0
        # p99 should be 100
        assert bundle.latency_p99 == 100.0
        assert bundle.latency_max == 100.0

    def test_f1_formula(self):
        """F1 = 2 * precision * recall / (precision + recall)."""
        preds = _make_preds(["flag", "pass"])
        records = _make_records(["unsafe", "unsafe"])
        confusion = compute_confusion(preds, records)
        bundle = compute_metrics(confusion, [1, 1])
        # TP=1, FN=1 → recall=0.5, precision=1.0, F1=0.667
        assert abs(bundle.f1 - 0.6667) < 0.001


class TestComputeSlices:
    def test_slice_keys_are_tuples(self):
        """Slice dict keys should be tuples of (category, language)."""
        preds = _make_preds(["flag", "pass"])
        records = _make_records(["unsafe", "benign"])
        slices = compute_slices(preds, records)
        for key in slices:
            assert isinstance(key, tuple)

    def test_slice_dimensions(self):
        """Each slice key should have (category, language) values."""
        preds = _make_preds(["flag", "pass"])
        records = _make_records(["unsafe", "benign"], ["violence", "benign"], ["en", "en"])
        slices = compute_slices(preds, records, slice_dims=["category", "language"])
        keys = list(slices.keys())
        assert len(keys) == 2
        for k in keys:
            assert len(k) == 2
