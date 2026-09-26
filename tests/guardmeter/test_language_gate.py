"""Tests for per-language thresholds, parity gap, and required-language coverage."""

from __future__ import annotations

from guardmeter.core.guard import Guard, GuardResult
from guardmeter.data.schema import DatasetRecord
from guardmeter.engine.evaluator import EvalConfig, Evaluator
from guardmeter.gate.checker import GateChecker, parity_gap
from guardmeter.gate.schema import (
    GateConfig,
    GlobalThresholds,
    LanguageParity,
    LanguageThresholds,
)


class _LangGuard(Guard):
    """Flags unsafe rows except in a chosen 'weak' language (all missed there)."""
    name = "lang"

    def __init__(self, weak: str = ""):
        self.weak = weak

    def predict(self, text, **meta):
        # meta has no language; encode weakness via a marker in the text.
        weak = f"[{self.weak}]" in text
        unsafe = "BAD" in text
        return GuardResult(prediction="flag" if (unsafe and not weak) else "pass",
                           score=0.9, latency_ms=1)


def _dataset(langs, per_lang=25):
    rows = []
    for lang in langs:
        for i in range(per_lang):
            rows.append(DatasetRecord(text=f"BAD [{lang}] {i}", label="unsafe",
                                      category="violence", language=lang))
    return rows


def _lenient_global():
    return GlobalThresholds(min_recall=0.0, max_fpr=1.0, min_f1=0.0, max_latency_p99_ms=100000)


def test_language_slices_computed():
    results = Evaluator(_LangGuard(), _LangGuard(weak="fa"), _dataset(["en", "fa"]), EvalConfig()).run()
    ls = results.candidate_language_slices["strict"]
    by = {k[0]: b for k, b in ls.items()}
    assert by["en"].recall == 1.0
    assert by["fa"].recall == 0.0


def test_parity_gate_fails_on_regressed_language():
    results = Evaluator(_LangGuard(), _LangGuard(weak="fa"), _dataset(["en", "fa"]), EvalConfig()).run()
    cfg = GateConfig(global_thresholds=_lenient_global(),
                     language_parity=LanguageParity(max_recall_gap=0.15, reference="best"))
    result = GateChecker(cfg).check(results)
    assert not result.passed
    assert any("language_parity" in f for f in result.failures)


def test_parity_gate_passes_when_even():
    results = Evaluator(_LangGuard(), _LangGuard(), _dataset(["en", "fa"]), EvalConfig()).run()
    cfg = GateConfig(global_thresholds=_lenient_global(),
                     language_parity=LanguageParity(max_recall_gap=0.15))
    assert GateChecker(cfg).check(results).passed


def test_per_language_threshold():
    results = Evaluator(_LangGuard(), _LangGuard(weak="fa"), _dataset(["en", "fa"]), EvalConfig()).run()
    cfg = GateConfig(global_thresholds=_lenient_global(),
                     languages={"fa": LanguageThresholds(min_recall=0.5)})
    result = GateChecker(cfg).check(results)
    assert not result.passed
    assert any("lang:fa" in f and "recall" in f for f in result.failures)


def test_required_language_missing_fails():
    results = Evaluator(_LangGuard(), _LangGuard(), _dataset(["en"]), EvalConfig()).run()
    cfg = GateConfig(global_thresholds=_lenient_global(), required_languages=["en", "es"])
    result = GateChecker(cfg).check(results)
    assert not result.passed
    assert any("es not covered" in f for f in result.failures)


def test_parity_gap_helper_min_support():
    results = Evaluator(_LangGuard(), _LangGuard(weak="fa"),
                        _dataset(["en", "fa"], per_lang=10), EvalConfig()).run()
    # Only 10 positives per language < default min_support 20 → no parity computed.
    gap, _ = parity_gap(results.candidate_language_slices["strict"], min_support=20)
    assert gap is None
