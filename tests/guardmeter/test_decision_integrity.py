"""Reproduction tests for the 2026-09-26 independent review (§4 items 1–5, 9, 10).

Each test asserts the *correct* behaviour; before the fix it fails, reproducing
the reported defect. Defects that do not reproduce are noted and skipped.
"""
from __future__ import annotations

import pytest

from guardmeter.core.guard import GuardResult
from guardmeter.data.schema import DatasetRecord
from guardmeter.gate.schema import ScenarioThresholds
from guardmeter.scenarios.gate import check_scenario_gate


def _rec(label, text="x"):
    return DatasetRecord(id=None, text=text, language="en", label=label,
                         category="prompt_injection", attack_family=None)


def _gr(pred):
    return GuardResult(prediction=pred, score=None if pred == "error" else 0.5, latency_ms=1)


# ── review item 1: incomplete evaluation must not PASS ───────────────────────

def test_empty_suite_is_not_pass():
    """An empty run (no scored scenarios) must not be an unqualified PASS."""
    verdict, _reasons = check_scenario_gate(
        {"pass_rate": None, "total": 0, "by_category": {}}, ScenarioThresholds(min_pass_rate=0.9))
    assert verdict in ("inconclusive", "fail")  # → never an unqualified pass


def test_missing_required_category_is_not_pass():
    """A required category absent from the run must not silently PASS."""
    verdict, _ = check_scenario_gate(
        {"pass_rate": 1.0, "total": 5, "by_category": {"support": 1.0}},
        ScenarioThresholds(min_pass_rate=0.9, per_category={"leak": 0.9}))
    assert verdict in ("inconclusive", "fail")  # 'leak' never ran


def test_unresolved_disputes_are_not_pass():
    """Unresolved judge disputes over threshold → not an unqualified PASS."""
    verdict, _ = check_scenario_gate(
        {"pass_rate": 1.0, "total": 10, "by_category": {}, "judge_disagree_rate": 0.5},
        ScenarioThresholds(min_pass_rate=0.9))
    assert verdict in ("inconclusive", "fail")


# ── review item 1: all-error audit is not valid; audit bound to its suite ────

def test_all_error_audit_not_validated():
    from guardmeter.scenarios.audit import audit_suite
    from guardmeter.scenarios.schema import Scenario, Suite, SuiteMeta, parse_assertion
    from guardmeter.scenarios.target import Target, TargetResponse

    class _Boom(Target):
        def describe(self):
            return {"kind": "fake"}

        def run(self, inp):
            return TargetResponse(error="endpoint down")  # transport error, never a verdict

    scn = Scenario.model_validate({"id": "a", "input": {"text": "hi"},
                                   "expect": [parse_assertion({"must_contain": {"patterns": ["x"]}})],
                                   "reviewed_by": "r"})
    suite = Suite(suite=SuiteMeta(name="t"), scenarios=[scn])
    rep = audit_suite(suite, _Boom(), repeats=2)
    assert rep.verdict() == "not validated"  # every scenario errored → cannot be validated


# ── review item 3: McNemar must exclude errored pairs ────────────────────────

def test_mcnemar_excludes_errored_pairs():
    from guardmeter.engine.significance import mcnemar_test
    records = [_rec("unsafe")]
    a = [_gr("error")]   # errored
    b = [_gr("flag")]    # correct
    result = mcnemar_test(a, b, records)
    # An errored pair must not count as a (correct benign) result; it is excluded.
    excluded = result[2] if len(result) >= 3 else None
    assert excluded == 1, "errored pair should be excluded and counted"


# ── review item 2: unknown/unparseable verdicts are errors, not passes ───────

def test_http_guard_unknown_verdict_is_error():
    from guardmeter.guards.http_guard import HttpGuard
    g = HttpGuard(url="http://x", verdict_path="result.flagged", flag_values=["true"])
    # A verdict the mapping can't resolve (missing/None) must raise → recorded as error.
    with pytest.raises(ValueError):
        g._flagged(None)


def test_llamaguard_unparseable_reply_is_error():
    from guardmeter.guards.llamaguard import _parse_llamaguard_reply
    with pytest.raises(ValueError):
        _parse_llamaguard_reply("I'm sorry, I can't help with that.")


# ── review item 4: language slices survive the SQLite round trip ─────────────

def test_language_slices_survive_sqlite_roundtrip(tmp_path, sample_records, regex_baseline, regex_enhanced):
    from guardmeter.engine.evaluator import EvalConfig, Evaluator
    from guardmeter.store.sqlite import SQLiteStore

    store = SQLiteStore(db_path=str(tmp_path / "h.db"))
    results = Evaluator(regex_baseline, regex_enhanced, sample_records, EvalConfig()).run()
    assert results.candidate_language_slices, "run should compute language slices"
    store.save_run(results)
    loaded = store.get_run(results.run_id)
    assert loaded.candidate_language_slices == results.candidate_language_slices


# ── review item 3: a run must not be its own "previous" (gate self-comparison) ─

def test_latest_run_can_exclude_current(tmp_path, sample_records, regex_baseline, regex_enhanced):
    from guardmeter.engine.evaluator import EvalConfig, Evaluator
    from guardmeter.store.sqlite import SQLiteStore

    store = SQLiteStore(db_path=str(tmp_path / "h.db"))
    first = Evaluator(regex_baseline, regex_enhanced, sample_records, EvalConfig()).run()
    store.save_run(first)
    latest = Evaluator(regex_baseline, regex_enhanced, sample_records, EvalConfig()).run()
    store.save_run(latest)
    # Excluding the latest run yields the earlier one — never itself.
    prev = store.latest_run(exclude_run_id=latest.run_id)
    assert prev is not None and prev.run_id == first.run_id
    assert store.latest_run(exclude_run_id=first.run_id).run_id == latest.run_id
