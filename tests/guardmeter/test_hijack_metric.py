"""hijack_rate flows from GuardResult.metadata through metrics into the gate."""

from __future__ import annotations

from guardmeter.core.guard import Guard, GuardResult
from guardmeter.data.schema import DatasetRecord
from guardmeter.engine.evaluator import EvalConfig, Evaluator
from guardmeter.engine.metrics import compute_metrics, count_hijacked
from guardmeter.gate.checker import GateChecker
from guardmeter.gate.schema import GateConfig, GlobalThresholds


def _pred(prediction, hijacked=False):
    meta = {"hijacked": True} if hijacked else {}
    return GuardResult(prediction=prediction, score=0.5, latency_ms=1, metadata=meta)


def test_count_and_rate():
    preds = [_pred("flag", hijacked=True), _pred("pass"), _pred("flag", hijacked=True), _pred("pass")]
    assert count_hijacked(preds) == 2
    conf = {"tp": 1, "fp": 1, "tn": 1, "fn": 1}
    m = compute_metrics(conf, [1, 1, 1, 1], count_hijacked(preds))
    assert m.hijacked == 2
    assert m.hijack_rate == 0.5


def test_zero_hijack_default():
    m = compute_metrics({"tp": 1, "fp": 0, "tn": 1, "fn": 0}, [1, 1])
    assert m.hijacked == 0
    assert m.hijack_rate == 0.0


class _HijackGuard(Guard):
    name = "always-hijacked"

    def predict(self, text, **meta):
        return _pred("flag", hijacked=True)


def test_gate_max_hijack_rate_fails():
    ds = [
        DatasetRecord(text="a", label="unsafe", category="violence"),
        DatasetRecord(text="b", label="benign", category="benign"),
    ]
    g = _HijackGuard()
    results = Evaluator(g, g, ds, EvalConfig()).run()
    assert results.candidate_metrics["strict"].hijack_rate == 1.0

    cfg = GateConfig(global_thresholds=GlobalThresholds(
        min_recall=0.0, max_fpr=1.0, min_f1=0.0, max_latency_p99_ms=100000, max_hijack_rate=0.1))
    result = GateChecker(cfg).check(results)
    assert not result.passed
    assert any("hijack_rate" in f for f in result.failures)


def test_gate_max_hijack_rate_passes_when_zero():
    ds = [DatasetRecord(text="a", label="unsafe", category="violence")]

    class _Clean(Guard):
        name = "clean"

        def predict(self, text, **meta):
            return GuardResult(prediction="flag", score=0.9, latency_ms=1)

    results = Evaluator(_Clean(), _Clean(), ds, EvalConfig()).run()
    cfg = GateConfig(global_thresholds=GlobalThresholds(
        min_recall=0.0, max_fpr=1.0, min_f1=0.0, max_latency_p99_ms=100000, max_hijack_rate=0.0))
    assert GateChecker(cfg).check(results).passed
