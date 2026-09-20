"""Tests for CI gate checker."""

from __future__ import annotations

from guardmeter.engine.evaluator import EvalConfig, Evaluator
from guardmeter.gate.checker import GateChecker
from guardmeter.gate.schema import ComparisonThresholds, GateConfig, GlobalThresholds


def _run(sample_records, guard):
    ev = Evaluator(guard, guard, sample_records, EvalConfig())
    return ev.run()


class TestPassCase:
    def test_gate_passes_with_lenient_thresholds(self, sample_records, regex_enhanced):
        """Gate should pass when thresholds are below actual metrics."""
        results = _run(sample_records, regex_enhanced)
        config = GateConfig(
            global_thresholds=GlobalThresholds(
                min_recall=0.0,
                max_fpr=1.0,
                max_latency_p99_ms=100000,
                min_f1=0.0,
            )
        )
        checker = GateChecker(config)
        result = checker.check(results)
        assert result.passed
        assert result.failures == []


class TestFailCase:
    def test_gate_fails_with_strict_recall_threshold(self, sample_records, regex_enhanced):
        """Gate should fail when recall threshold is impossibly high."""
        results = _run(sample_records, regex_enhanced)
        config = GateConfig(
            global_thresholds=GlobalThresholds(
                min_recall=1.0,  # impossible
                max_fpr=1.0,
                max_latency_p99_ms=100000,
                min_f1=0.0,
            )
        )
        checker = GateChecker(config)
        result = checker.check(results)
        assert not result.passed
        assert any("recall" in f for f in result.failures)


class TestAttackTypeSlices:
    def test_attack_override_applied_to_attack_family(self, sample_records, regex_enhanced):
        """An 'attack:<type>' override gates the matching attack-type slice."""
        from guardmeter.gate.schema import SliceThresholds
        results = _run(sample_records, regex_enhanced)
        assert "benign_adjacent" in {k[0] for k in results.candidate_attack_slices["strict"]}
        config = GateConfig(
            global_thresholds=GlobalThresholds(
                min_recall=0.0, max_fpr=1.0, max_latency_p99_ms=100000, min_f1=0.0,
            ),
            # benign_adjacent recall is 0.5 in the fixture; 0.9 must trip the gate.
            slices={"attack:benign_adjacent": SliceThresholds(min_recall=0.9)},
        )
        result = GateChecker(config).check(results)
        assert not result.passed
        assert any(f.startswith("attack:benign_adjacent") for f in result.failures)

    def test_attack_family_not_gated_without_override(self, sample_records, regex_enhanced):
        """Attack slices are opt-in: no 'attack:' override → they never fail the gate."""
        results = _run(sample_records, regex_enhanced)
        config = GateConfig(
            global_thresholds=GlobalThresholds(
                min_recall=0.0, max_fpr=1.0, max_latency_p99_ms=100000, min_f1=0.0,
            ),
        )
        result = GateChecker(config).check(results)
        assert result.passed
        assert not any(f.startswith("attack:") for f in result.failures)


class TestFnmatch:
    def test_wildcard_matches_language(self, sample_records, regex_enhanced):
        """'*/fa' pattern should match 'violence/fa' but not 'violence/en'."""
        import fnmatch
        assert fnmatch.fnmatch("violence/fa", "*/fa")
        assert not fnmatch.fnmatch("violence/en", "*/fa")

    def test_slice_override_applied(self, sample_records, regex_enhanced):
        """Slice override with glob pattern should be applied to matching slices."""
        from guardmeter.gate.checker import _effective_thresholds
        from guardmeter.gate.schema import GlobalThresholds, SliceThresholds
        global_thr = GlobalThresholds(min_recall=0.9)
        overrides = {"*/fa": SliceThresholds(min_recall=0.1)}
        thr = _effective_thresholds("violence/fa", global_thr, overrides)
        assert thr.min_recall == 0.1

    def test_slice_override_not_applied_to_non_match(self, sample_records, regex_enhanced):
        """Slice override should NOT be applied to non-matching slices."""
        from guardmeter.gate.checker import _effective_thresholds
        from guardmeter.gate.schema import GlobalThresholds, SliceThresholds
        global_thr = GlobalThresholds(min_recall=0.9)
        overrides = {"*/fa": SliceThresholds(min_recall=0.1)}
        thr = _effective_thresholds("violence/en", global_thr, overrides)
        assert thr.min_recall == 0.9


class TestWarnMode:
    def test_warn_mode_passes_despite_failure(self, sample_records, regex_enhanced):
        """on_failure='warn' should always produce passed=True even when thresholds breach."""
        results = _run(sample_records, regex_enhanced)
        config = GateConfig(
            on_failure="warn",
            global_thresholds=GlobalThresholds(
                min_recall=1.0,  # impossible
                max_fpr=0.0,
                max_latency_p99_ms=0,  # impossible
                min_f1=1.0,   # impossible
            )
        )
        checker = GateChecker(config)
        result = checker.check(results)
        assert result.passed
        assert result.failures == []  # moved to warnings
        assert len(result.warnings) > 0


class TestRegressionCheck:
    def test_recall_drop_fails(self, sample_records, regex_enhanced, tmp_db):
        """Recall regression > threshold should fail."""
        import copy

        from guardmeter.engine.metrics import MetricsBundle

        results = _run(sample_records, regex_enhanced)
        # Save a "previous" run with higher recall
        prev = copy.deepcopy(results)
        prev.run_id = "prev-run-000"
        # Artificially boost recall of the "previous" run
        prev.candidate_metrics["strict"] = MetricsBundle(
            tp=100, fn=0, fp=0, tn=10, recall=1.0, fpr=0.0, f1=1.0, precision=1.0
        )
        tmp_db.save_run(prev)
        # Now save the current (worse) run
        tmp_db.save_run(results)

        config = GateConfig(
            global_thresholds=GlobalThresholds(min_recall=0.0, max_fpr=1.0, max_latency_p99_ms=100000, min_f1=0.0),
            comparison=ComparisonThresholds(max_recall_regression=0.01),
        )
        checker = GateChecker(config, store=tmp_db)
        # Override latest_run to return prev as the baseline

        class MockStore:
            def latest_run(self):
                return prev

        checker.store = MockStore()
        result = checker.check(results)
        # If recall dropped more than 0.01, should fail
        prev_recall = 1.0
        curr_recall = results.candidate_metrics["strict"].recall
        if prev_recall - curr_recall > 0.01:
            assert not result.passed


class TestAgenticGateProfile:
    """The shipped gate.agentic.json is a real config with a `_comment` key."""

    PATH = "dataset/agentic/v1/gate.agentic.json"

    def test_loads_and_ignores_comment(self):
        from guardmeter.gate.config import load_gate_config

        cfg = load_gate_config(self.PATH)
        assert cfg.mode == "strict"
        assert not hasattr(cfg, "_comment")
        # Attack-family and language slices are present.
        assert "attack:direct_override" in cfg.slices
        assert "*/fa" in cfg.slices

    def test_aspirational_gate_fails_weak_baseline(self, agentic_records, injection_heuristic):
        from guardmeter.gate.config import load_gate_config

        results = Evaluator(injection_heuristic, injection_heuristic, agentic_records, EvalConfig()).run()
        result = GateChecker(load_gate_config(self.PATH)).check(results)
        assert not result.passed  # honest: the weak baseline is nowhere near the bar
