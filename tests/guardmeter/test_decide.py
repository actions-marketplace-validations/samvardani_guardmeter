"""Tests for guardmeter decide — the one-page release decision."""

from __future__ import annotations

from guardmeter.decide.model import build_decision
from guardmeter.decide.render import render_html, render_markdown
from guardmeter.gate.schema import ScenarioThresholds
from guardmeter.scenarios.results import RunRecord, ScenarioResult, ScenarioResults


def _case(cid, status, *, critical=False, category="agent-tools", tokens=None, prompt=None,
          latency=10, disagree=False, judge_tokens=None, judge_model=None):
    return ScenarioResult(
        id=cid, name=cid, category=category, language="en", tags=[], status=status,
        judge_disagree=disagree, critical=critical,
        runs=[RunRecord(latency_ms=latency, completion_tokens=tokens, prompt_tokens=prompt,
                        passed=(status == "pass"),
                        judge_prompt_tokens=judge_tokens, judge_completion_tokens=judge_tokens,
                        judge_model=judge_model,
                        outcomes=[{"type": "must_call_tool", "passed": status == "pass",
                                   "detail": "wrong tool", "judge_disagree": disagree}])],
    )


def _run(run_id, cases, *, suite_hash="abc123", model="m"):
    return ScenarioResults(
        run_id=run_id, timestamp="2026-09-27T00:00:00Z", suite_name="starter",
        suite_version="1.0", target={"kind": "endpoint", "endpoint": "http://x/v1", "model": model},
        environment={}, results=cases, suite_hash=suite_hash,
    )


_THR = ScenarioThresholds(min_pass_rate=0.5, min_total=1, per_category={"agent-tools": 1.0})


def test_new_critical_failure_blocks_even_when_average_improves():
    """A faster candidate with a higher average but a new critical failure → BLOCK."""
    baseline = _run("base", [
        _case("crit", "pass", critical=True, latency=100),
        _case("a", "fail", latency=100),
        _case("b", "fail", latency=100),
    ])
    # Candidate: crit now fails (regression), but two others flipped to pass (higher average),
    # and latency dropped.
    candidate = _run("cand", [
        _case("crit", "fail", critical=True, latency=10),
        _case("a", "pass", latency=10),
        _case("b", "pass", latency=10),
    ])
    r = build_decision(baseline, candidate, ScenarioThresholds(min_pass_rate=0.1, min_total=1))
    assert r.verdict == "BLOCK"
    assert [c.id for c in r.critical_regressions] == ["crit"]
    assert "crit" in r.reason


def test_all_error_candidate_is_inconclusive():
    """Every candidate case errored → INCONCLUSIVE (no evaluable coverage)."""
    baseline = _run("base", [_case("crit", "pass", critical=True), _case("a", "pass")])
    candidate = _run("cand", [_case("crit", "error", critical=True), _case("a", "error")])
    r = build_decision(baseline, candidate, _THR)
    assert r.verdict == "INCONCLUSIVE"


def test_identical_runs_approve_no_changes():
    """Identical runs → APPROVE with a 'no changes' reason."""
    cases = [_case("crit", "pass", critical=True), _case("a", "pass"), _case("b", "pass")]
    baseline = _run("base", cases)
    candidate = _run("cand", [_case("crit", "pass", critical=True), _case("a", "pass"),
                              _case("b", "pass")])
    r = build_decision(baseline, candidate, _THR)
    assert r.verdict == "APPROVE"
    assert "no changes" in r.reason.lower()


def test_critical_dispute_is_inconclusive_not_block():
    """A disputed critical case can't be judged → INCONCLUSIVE even if others pass."""
    baseline = _run("base", [_case("crit", "pass", critical=True), _case("a", "pass")])
    candidate = _run("cand", [_case("crit", "pass", critical=True, disagree=True), _case("a", "pass")])
    r = build_decision(baseline, candidate, _THR)
    assert r.verdict == "INCONCLUSIVE"
    assert "crit" in r.reason


def test_cost_unknown_without_prices():
    """Cost per successful task is 'unknown' when no price is supplied — never estimated."""
    baseline = _run("base", [_case("a", "pass", tokens=100)])
    candidate = _run("cand", [_case("a", "pass", tokens=100)])
    r = build_decision(baseline, candidate, ScenarioThresholds(min_pass_rate=0.1, min_total=1))
    assert r.cost_per_successful_task == "unknown"


def test_cost_computed_with_prices_and_usage():
    """With a price and token usage, cost per successful task is a concrete number."""
    baseline = _run("base", [_case("a", "pass", tokens=1000)])
    candidate = _run("cand", [_case("a", "pass", tokens=1000)], model="qwen")
    r = build_decision(baseline, candidate, ScenarioThresholds(min_pass_rate=0.1, min_total=1),
                       prices={"qwen": 0.5})
    assert r.cost_per_successful_task.startswith("$")
    assert "unknown" not in r.cost_per_successful_task


def test_cost_uses_prompt_and_completion_with_dated_price():
    """A dict price (input+output) prices both prompt and completion tokens."""
    baseline = _run("base", [_case("a", "pass", tokens=200, prompt=1000)])
    candidate = _run("cand", [_case("a", "pass", tokens=200, prompt=1000)], model="qwen")
    r = build_decision(baseline, candidate, ScenarioThresholds(min_pass_rate=0.1, min_total=1),
                       prices={"qwen": {"input_per_1k": 0.1, "output_per_1k": 0.5, "as_of": "2026-09-01"}})
    # 1000/1k*0.1 + 200/1k*0.5 = 0.10 + 0.10 = $0.2000 per successful task
    assert r.cost_per_successful_task.startswith("$0.2000/successful task")
    assert "target qwen: 1000+200 tok" in r.cost_per_successful_task


def test_judge_cost_excluded_when_judge_unpriced():
    """Judge tokens are shown but excluded from cost when the judge model has no price."""
    baseline = _run("base", [_case("a", "pass", tokens=100)])
    candidate = _run("cand", [_case("a", "pass", tokens=100, judge_tokens=50, judge_model="claude")],
                     model="qwen")
    r = build_decision(baseline, candidate, ScenarioThresholds(min_pass_rate=0.1, min_total=1),
                       prices={"qwen": 0.5})
    assert "judge cost excluded (no price for claude)" in r.cost_per_successful_task


def test_decide_cli_end_to_end(tmp_path):
    """decide reads two stored runs, writes md+html, and exits 1 on BLOCK."""
    import json

    from click.testing import CliRunner

    from guardmeter.cli.main import cli
    from guardmeter.store.sqlite import SQLiteStore

    db = tmp_path / "runs.db"
    store = SQLiteStore(db_path=str(db))
    store.save_scenario_run(_run("baseAAA", [_case("crit", "pass", critical=True), _case("a", "pass")]))
    store.save_scenario_run(_run("candBBB", [_case("crit", "fail", critical=True), _case("a", "pass")]))

    policy = tmp_path / "gate.json"
    policy.write_text(json.dumps({"mode": "strict", "scenarios": {"min_pass_rate": 0.1, "min_total": 1}}),
                      encoding="utf-8")
    md, html = tmp_path / "decision.md", tmp_path / "decision.html"
    result = CliRunner().invoke(cli, [
        "decide", "--baseline", "baseAAA", "--candidate", "candBBB",
        "--policy", str(policy), "--out", str(md), "--out", str(html), "--store", str(db),
    ])
    assert result.exit_code == 1, result.output  # BLOCK
    assert "BLOCK" in result.output
    assert md.exists() and html.exists()
    assert "<!DOCTYPE html>" in html.read_text()


def test_decide_cli_rejects_self_comparison(tmp_path):
    """decide with the same run for baseline and candidate is a usage error."""
    import json

    from click.testing import CliRunner

    from guardmeter.cli.main import cli
    policy = tmp_path / "gate.json"
    policy.write_text(json.dumps({"scenarios": {"min_total": 1}}), encoding="utf-8")
    result = CliRunner().invoke(cli, [
        "decide", "--baseline", "x", "--candidate", "x", "--policy", str(policy),
    ])
    assert result.exit_code == 2  # usage error


def test_renders_md_and_html():
    """Both renderers produce non-empty output containing the verdict."""
    baseline = _run("base", [_case("a", "pass")])
    candidate = _run("cand", [_case("a", "fail")])
    r = build_decision(baseline, candidate, ScenarioThresholds(min_pass_rate=0.9, min_total=1))
    md = render_markdown(r)
    html = render_html(r)
    assert r.verdict in md and r.verdict in html
    assert "<!DOCTYPE html>" in html
    assert "Acceptance policy applied" in md
