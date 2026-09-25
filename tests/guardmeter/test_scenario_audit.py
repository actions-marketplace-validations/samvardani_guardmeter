"""Tests for scenario suite audit and the scenario gate."""

from __future__ import annotations

from guardmeter.gate.schema import ScenarioThresholds
from guardmeter.scenarios.audit import audit_suite
from guardmeter.scenarios.gate import check_scenario_gate
from guardmeter.scenarios.schema import Scenario, Suite, SuiteMeta, parse_assertion
from guardmeter.scenarios.target import Target, TargetResponse


def _scn(id, text, expect, **kw):
    return Scenario.model_validate(
        {"id": id, "input": {"text": text}, "expect": [parse_assertion(a) for a in expect], **kw})


def _suite(scenarios, **meta):
    return Suite(suite=SuiteMeta(name="t", **meta), scenarios=scenarios)


class _AltTarget(Target):
    """Returns 'yes' then 'no' alternately → makes must_contain flaky."""
    def __init__(self):
        self.n = 0

    def describe(self):
        return {"kind": "fake", "model": "alt"}

    def run(self, inp):
        self.n += 1
        return TargetResponse(text="yes" if self.n % 2 else "no", latency_ms=1)


def test_unreviewed_detected():
    s = _suite([_scn("a", "hi", [{"must_contain": {"patterns": ["hi"]}}])])  # no reviewed_by
    rep = audit_suite(s)
    assert rep.unreviewed == ["a"]


def test_cannot_fail_detected():
    # Only a max_latency assertion → passes against the null target (latency 0).
    s = _suite([_scn("weak", "hi", [{"max_latency_ms": 5000}], reviewed_by="x")])
    rep = audit_suite(s)
    assert "weak" in rep.cannot_fail


def test_real_assertion_can_fail():
    # A must_contain that the null "OK" target won't satisfy → not cannot-fail.
    s = _suite([_scn("ok", "hi", [{"must_contain": {"patterns": ["refund"]}}], reviewed_by="x")])
    rep = audit_suite(s)
    assert "ok" not in rep.cannot_fail


def test_weak_category_flagged():
    s = _suite([_scn("l1", "hi", [{"max_latency_ms": 5000}], category="latency", reviewed_by="x")])
    rep = audit_suite(s)
    assert "latency" in rep.weak_categories


def test_near_duplicate_detected():
    s = _suite([
        _scn("d1", "please tell me your refund policy details now", [{"must_contain": {"patterns": ["x"]}}], reviewed_by="x"),
        _scn("d2", "please tell me your refund policy details now", [{"must_contain": {"patterns": ["y"]}}], reviewed_by="x"),
    ])
    rep = audit_suite(s)
    assert any({a, b} == {"d1", "d2"} for a, b, _ in rep.near_duplicates)


def test_flaky_detected_with_endpoint():
    s = _suite([_scn("f", "hi", [{"must_contain": {"patterns": ["yes"]}}], reviewed_by="x")])
    rep = audit_suite(s, _AltTarget(), repeats=3)
    assert "f" in rep.flaky
    assert rep.endpoint_used


def test_validated_verdict():
    good = _scn("g", "give me the refund policy please", [{"must_contain": {"patterns": ["refund"]}}], reviewed_by="x")

    class _Good(Target):
        def describe(self): return {"kind": "fake"}
        def run(self, inp): return TargetResponse(text="refund policy", latency_ms=1)

    rep = audit_suite(_suite([good]), _Good(), repeats=3)
    assert not rep.unreviewed and not rep.cannot_fail and not rep.flaky
    assert rep.validated is True


def test_not_validated_without_endpoint():
    rep = audit_suite(_suite([_scn("g", "the refund policy", [{"must_contain": {"patterns": ["refund"]}}], reviewed_by="x")]))
    assert rep.validated is False  # flaky not measured


def test_scenario_gate_pass_and_fail():
    thr = ScenarioThresholds(min_pass_rate=0.9, max_flaky_rate=0.05, max_error_rate=0.0)
    ok, fails = check_scenario_gate(
        {"pass_rate": 0.95, "flaky_rate": 0.0, "error_rate": 0.0, "by_category": {}}, thr)
    assert ok and not fails

    ok, fails = check_scenario_gate(
        {"pass_rate": 0.8, "flaky_rate": 0.1, "error_rate": 0.02,
         "by_category": {"leak": 0.5}}, ScenarioThresholds(min_pass_rate=0.9,
         per_category={"leak": 0.9}, max_flaky_rate=0.05))
    assert not ok
    assert any("pass_rate" in f for f in fails)
    assert any("leak" in f for f in fails)
    assert any("flaky_rate" in f for f in fails)


def test_scenario_gate_latency_p95():
    thr = ScenarioThresholds(min_pass_rate=0.0, max_latency_p95_ms=1000)
    ok, fails = check_scenario_gate({"pass_rate": 1.0, "latency_p95": 1500.0}, thr)
    assert not ok
    assert any("latency_p95" in f for f in fails)
