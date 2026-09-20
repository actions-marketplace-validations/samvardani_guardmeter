"""End-to-end tests for the Evaluator."""

from __future__ import annotations

import uuid

import pytest

from guardbench.engine.evaluator import EvalConfig, Evaluator
from guardbench.engine.results import EvalResults


def test_evaluator_returns_eval_results(sample_records, regex_baseline, regex_enhanced):
    """Evaluator.run() should return an EvalResults instance."""
    ev = Evaluator(regex_baseline, regex_enhanced, sample_records, EvalConfig())
    results = ev.run()
    assert isinstance(results, EvalResults)


def test_attack_slices_keyed_by_attack_type(sample_records, regex_enhanced):
    """The evaluator computes a parallel attack-type slice family."""
    ev = Evaluator(regex_enhanced, regex_enhanced, sample_records, EvalConfig())
    results = ev.run()
    attack = results.candidate_attack_slices.get("strict", {})
    assert attack, "expected attack-type slices"
    # Every key is a single-element (attack_type,) tuple.
    assert all(len(k) == 1 for k in attack)
    attack_types = {k[0] for k in attack}
    expected = {r.attack_type for r in sample_records}
    assert attack_types == expected
    # Category×language family is unchanged (2-tuples).
    cat = results.candidate_slices.get("strict", {})
    assert all(len(k) == 2 for k in cat)


def test_run_id_is_uuid(sample_records, regex_enhanced):
    """run_id should be a valid UUID string."""
    ev = Evaluator(regex_enhanced, regex_enhanced, sample_records, EvalConfig())
    results = ev.run()
    # Should not raise
    parsed = uuid.UUID(results.run_id)
    assert str(parsed) == results.run_id


def test_dataset_sha_nonempty(sample_records, regex_enhanced):
    """dataset_sha should be a non-empty hex string."""
    ev = Evaluator(regex_enhanced, regex_enhanced, sample_records, EvalConfig())
    results = ev.run()
    assert results.dataset_sha
    assert len(results.dataset_sha) == 64  # SHA-256


def test_both_policies_present(sample_records, regex_enhanced):
    """Both strict and lenient metrics should be in results."""
    ev = Evaluator(regex_enhanced, regex_enhanced, sample_records, EvalConfig())
    results = ev.run()
    assert "strict" in results.candidate_metrics
    assert "lenient" in results.candidate_metrics


def test_slice_keys_are_category_language_tuples(sample_records, regex_enhanced):
    """Slice keys should be (category, language) tuples."""
    ev = Evaluator(regex_enhanced, regex_enhanced, sample_records, EvalConfig())
    results = ev.run()
    for key in results.candidate_slices.get("strict", {}).keys():
        assert isinstance(key, tuple)
        assert len(key) == 2


def test_sample_results_count(sample_records, regex_enhanced):
    """sample_results should have one entry per dataset record."""
    ev = Evaluator(regex_enhanced, regex_enhanced, sample_records, EvalConfig())
    results = ev.run()
    assert len(results.sample_results) == len(sample_records)


def test_candidate_recall_positive(sample_records, regex_enhanced):
    """Enhanced guard should achieve recall > 0 on the test fixture."""
    ev = Evaluator(regex_enhanced, regex_enhanced, sample_records, EvalConfig())
    results = ev.run()
    strict = results.candidate_metrics["strict"]
    assert strict.recall > 0.0
