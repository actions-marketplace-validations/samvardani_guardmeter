"""Guard-call errors are a third outcome: excluded from metrics, and they fail
the gate as an incomplete run. Regression test for the bug where a dead API key
scored the candidate recall 1.00 because every error was counted as a flag.
"""

from __future__ import annotations

from guardmeter.core.guard import Guard, GuardResult
from guardmeter.data.schema import DatasetRecord
from guardmeter.engine.evaluator import EvalConfig, Evaluator
from guardmeter.gate.checker import GateChecker
from guardmeter.gate.schema import GateConfig, GlobalThresholds


def _dataset():
    # 4 positives + 3 negatives — under the old bug (error→flag) recall would be 1.00.
    return [
        DatasetRecord(text=f"unsafe {i}", label="unsafe", category="violence") for i in range(4)
    ] + [
        DatasetRecord(text=f"benign {i}", label="benign", category="benign") for i in range(3)
    ]


class _DeadGuard(Guard):
    """Every call raises — simulates an invalid API key."""
    name = "dead"

    def predict(self, text, **meta):
        raise RuntimeError("401 invalid x-api-key")


class _FlakyGuard(Guard):
    """Errors on every 5th call (20%); otherwise flags positives, passes negatives."""
    name = "flaky"

    def predict(self, text, **meta):
        if text.endswith(("0", "5")):  # 2 of 10 texts below
            raise RuntimeError("connection reset")
        return GuardResult(prediction="flag" if "unsafe" in text else "pass", score=0.9, latency_ms=1)


def _lenient_but_errors_gate():
    return GateConfig(global_thresholds=GlobalThresholds(
        min_recall=0.0, max_fpr=1.0, min_f1=0.0, max_latency_p99_ms=1_000_000))


def test_dead_guard_recall_not_one_and_gate_fails():
    ds = _dataset()
    results = Evaluator(_DeadGuard(), _DeadGuard(), ds, EvalConfig()).run()
    cm = results.candidate_metrics["strict"]

    # The bug: recall was 1.00. Now every call errored → nothing evaluated.
    assert cm.error_count == len(ds)
    assert cm.error_rate == 1.0
    assert cm.tp == cm.fp == cm.tn == cm.fn == 0  # excluded, not counted as flags
    assert cm.recall != 1.0                       # undefined, not a perfect score

    # Default gate (max_error_rate=0.0) fails with the incomplete-run message.
    result = GateChecker(_lenient_but_errors_gate()).check(results)
    assert not result.passed
    assert any("incomplete run" in f for f in result.failures)


def test_partial_failure_metrics_computed_on_remainder():
    ds = [
        DatasetRecord(text=f"unsafe {i}", label="unsafe", category="violence") for i in range(5)
    ] + [
        DatasetRecord(text=f"benign {i}", label="benign", category="benign") for i in range(5)
    ]
    results = Evaluator(_FlakyGuard(), _FlakyGuard(), ds, EvalConfig()).run()
    cm = results.candidate_metrics["strict"]

    # texts ending in 0/5: "unsafe 0", "unsafe 5"(n/a, only 0-4), "benign 0", "benign 5"(n/a)
    # → "unsafe 0" and "benign 0" error = 2 of 10.
    assert cm.error_count == 2
    assert cm.error_rate == 0.2
    assert cm.tp + cm.fp + cm.tn + cm.fn == 8   # metrics over the 80% that ran
    assert cm.recall == 1.0                      # all evaluated positives flagged

    # A gate that would otherwise pass still fails on the error rate.
    cfg = _lenient_but_errors_gate()  # max_error_rate defaults to 0.0
    result = GateChecker(cfg).check(results)
    assert not result.passed
    assert any("incomplete run" in f for f in result.failures)

    # Raising max_error_rate above the observed rate lets it pass.
    cfg.global_thresholds.max_error_rate = 0.5
    assert GateChecker(cfg).check(results).passed


def test_error_metadata_persists_round_trip(tmp_path):
    from guardmeter.store.sqlite import SQLiteStore

    ds = _dataset()
    results = Evaluator(_DeadGuard(), _DeadGuard(), ds, EvalConfig()).run()
    store = SQLiteStore(db_path=tmp_path / "runs.db")
    store.save_run(results)

    loaded = store.get_run(results.run_id)
    assert loaded.candidate_metrics["strict"].error_count == len(ds)
    s0 = loaded.sample_results[0]
    assert s0.candidate_pred == "error"
    assert "error" in s0.candidate_meta
    assert s0.candidate_meta["attempts"] >= 1
