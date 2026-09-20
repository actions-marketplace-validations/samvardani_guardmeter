"""Tests for report chart data builders."""

from __future__ import annotations

from itertools import pairwise

from guardbench.engine.evaluator import EvalConfig, Evaluator
from guardbench.engine.results import EvalResults, SampleResult
from guardbench.report.charts import threshold_sweep_data


def _empty_results() -> EvalResults:
    return EvalResults(
        run_id="r", dataset_sha="s", git_commit="c", timestamp="t",
        baseline_name="b", candidate_name="c",
    )


def test_sweep_returns_empty_without_scores():
    """No candidate scores → {} so the template hides the chart."""
    results = _empty_results()
    results.sample_results = [
        SampleResult("t", "unsafe", "violence", "en", "flag", "flag", candidate_score=None)
    ]
    assert threshold_sweep_data(results) == {}


def test_sweep_recall_monotone_non_increasing(sample_records, regex_enhanced):
    """As the decision threshold rises, recall must not increase."""
    ev = Evaluator(regex_enhanced, regex_enhanced, sample_records, EvalConfig())
    results = ev.run()
    sweep = threshold_sweep_data(results)
    assert sweep, "expected real scores to produce a sweep"
    recalls = sweep["recall"]
    assert len(recalls) == len(sweep["thresholds"])
    for earlier, later in pairwise(recalls):
        assert later <= earlier + 1e-9, f"recall rose: {earlier} -> {later}"
