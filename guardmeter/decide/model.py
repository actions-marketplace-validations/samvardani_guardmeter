"""Build a release decision (APPROVE / BLOCK / INCONCLUSIVE) from two scenario runs.

The pass/fail judgment comes from the canonical scenario gate
(``check_scenario_gate``) — this module never recomputes it a second way. On top
of that it layers the release semantics a buyer needs:

* a new failure on a ``critical`` case blocks approval even if the average rose;
* an error or dispute on a critical case makes the decision inconclusive;
* every changed case is preserved (not hidden inside a single drift score).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from guardmeter.gate.schema import ScenarioThresholds
from guardmeter.scenarios.gate import check_scenario_gate
from guardmeter.scenarios.results import ScenarioResult, ScenarioResults

# Statuses that count as "not a failure" when deciding whether a fail is *new*.
_NON_FAIL = {"pass", "flaky"}


@dataclass
class CaseChange:
    """One scenario's before→after result across the two runs."""

    id: str
    name: str
    category: str
    language: str
    critical: bool
    before: str | None  # None = absent from the baseline run (added)
    after: str | None    # None = absent from the candidate run (removed)
    failing: list[str] = field(default_factory=list)  # failing assertions (candidate)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id, "name": self.name, "category": self.category,
            "language": self.language, "critical": self.critical,
            "before": self.before, "after": self.after, "failing": self.failing,
        }


@dataclass
class DecisionReport:
    """Everything the one-page decision needs, computed once."""

    verdict: str  # APPROVE | BLOCK | INCONCLUSIVE
    reason: str
    suite_name: str
    suite_hash: str
    baseline_run_id: str
    candidate_run_id: str
    baseline_target: dict[str, Any]
    candidate_target: dict[str, Any]
    critical_regressions: list[CaseChange] = field(default_factory=list)
    improvements: list[CaseChange] = field(default_factory=list)
    other_regressions: list[CaseChange] = field(default_factory=list)
    added: list[CaseChange] = field(default_factory=list)
    removed: list[CaseChange] = field(default_factory=list)
    disputes: dict[str, int] = field(default_factory=dict)
    errors: dict[str, int] = field(default_factory=dict)
    coverage: list[dict[str, Any]] = field(default_factory=list)  # per category: evaluable/total
    latency: dict[str, float] = field(default_factory=dict)
    cost_per_successful_task: str = "unknown"
    policy_plain: list[str] = field(default_factory=list)
    rerun_command: str = ""
    gate_reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "verdict": self.verdict, "reason": self.reason,
            "suite_name": self.suite_name, "suite_hash": self.suite_hash,
            "baseline_run_id": self.baseline_run_id, "candidate_run_id": self.candidate_run_id,
            "baseline_target": self.baseline_target, "candidate_target": self.candidate_target,
            "critical_regressions": [c.to_dict() for c in self.critical_regressions],
            "improvements": [c.to_dict() for c in self.improvements],
            "other_regressions": [c.to_dict() for c in self.other_regressions],
            "added": [c.to_dict() for c in self.added],
            "removed": [c.to_dict() for c in self.removed],
            "disputes": self.disputes, "errors": self.errors,
            "coverage": self.coverage, "latency": self.latency,
            "cost_per_successful_task": self.cost_per_successful_task,
            "policy_plain": self.policy_plain, "rerun_command": self.rerun_command,
            "gate_reasons": self.gate_reasons,
        }


def _by_id(results: list[ScenarioResult]) -> dict[str, ScenarioResult]:
    return {r.id: r for r in results}


def _policy_plain(thr: ScenarioThresholds) -> list[str]:
    """The acceptance policy stated in plain words."""
    out = [
        f"At least {int(thr.min_pass_rate * 100)}% of evaluable cases must pass.",
        f"At least {thr.min_total} evaluable case(s) are required, or the result is inconclusive.",
    ]
    if thr.max_error_rate <= 0:
        out.append("No endpoint errors are allowed.")
    else:
        out.append(f"At most {thr.max_error_rate:.0%} of cases may error.")
    if thr.max_judge_disagree_rate <= 0:
        out.append("No unresolved judge disputes are allowed.")
    else:
        out.append(f"At most {thr.max_judge_disagree_rate:.0%} of cases may have unresolved disputes.")
    for cat, pr in sorted(thr.per_category.items()):
        out.append(f"Category '{cat}' must reach {int(pr * 100)}% pass rate.")
    out.append("A new failure on a critical case blocks approval even if the average improved.")
    out.append("An error or dispute on a critical case makes the decision inconclusive.")
    return out


def _cost_per_successful_task(candidate: ScenarioResults, prices: dict[str, Any] | None) -> str:
    """Output-token cost per passing case, only when both usage and a price exist.

    Never estimates: if no price is supplied for the candidate model, or the run
    carries no token usage, returns "unknown".
    """
    if not prices:
        return "unknown"
    model = str(candidate.target.get("model", ""))
    price = prices.get(model)
    if price is None:
        return "unknown"
    per_1k = float(price)
    passing = [r for r in candidate.results if r.status == "pass"]
    if not passing:
        return "unknown"
    tokens = 0
    have_usage = False
    for r in passing:
        for run in r.runs:
            if run.completion_tokens is not None:
                tokens += run.completion_tokens
                have_usage = True
    if not have_usage:
        return "unknown"
    cost = tokens / 1000.0 * per_1k
    return f"${cost / len(passing):.4f} (output tokens, {model} @ ${per_1k}/1k)"


def build_decision(
    baseline: ScenarioResults,
    candidate: ScenarioResults,
    thresholds: ScenarioThresholds,
    *,
    rerun_command: str = "",
    prices: dict[str, Any] | None = None,
) -> DecisionReport:
    """Compare two scenario runs and return a release decision."""
    cand_agg = candidate.aggregate()
    base_agg = baseline.aggregate()

    # Canonical verdict — the single source of pass/fail truth.
    canonical, gate_reasons = check_scenario_gate(cand_agg, thresholds)

    base_by = _by_id(baseline.results)
    cand_by = _by_id(candidate.results)

    critical_regressions: list[CaseChange] = []
    improvements: list[CaseChange] = []
    other_regressions: list[CaseChange] = []
    added: list[CaseChange] = []
    removed: list[CaseChange] = []

    for cid, cr in cand_by.items():
        before = base_by[cid].status if cid in base_by else None
        change = CaseChange(
            id=cid, name=cr.name, category=cr.category, language=cr.language,
            critical=cr.critical, before=before, after=cr.status, failing=cr.failing,
        )
        if before is None:
            added.append(change)
            if cr.status == "fail" and cr.critical:
                critical_regressions.append(change)
            elif cr.status == "fail":
                other_regressions.append(change)
            continue
        if cr.status == before:
            continue
        # Regression: was not-failing, now failing.
        if cr.status == "fail" and before in _NON_FAIL:
            (critical_regressions if cr.critical else other_regressions).append(change)
        # Improvement: was failing/erroring, now passing.
        elif before not in _NON_FAIL and cr.status == "pass":
            improvements.append(change)
        elif cr.status == "error" or before == "pass" and cr.status == "flaky":
            other_regressions.append(change)
        else:
            improvements.append(change)

    for cid, br in base_by.items():
        if cid not in cand_by:
            removed.append(CaseChange(
                id=cid, name=br.name, category=br.category, language=br.language,
                critical=br.critical, before=br.status, after=None))

    # Critical cases that errored or were disputed cannot be judged.
    critical_unjudgeable = [
        r for r in candidate.results if r.critical and (r.status == "error" or r.judge_disagree)
    ]

    # Verdict overlay: INCONCLUSIVE > BLOCK > APPROVE.
    if canonical == "inconclusive" or critical_unjudgeable:
        verdict = "INCONCLUSIVE"
        if critical_unjudgeable:
            ids = ", ".join(r.id for r in critical_unjudgeable)
            reason = f"Critical case(s) errored or were disputed and cannot be judged: {ids}."
        else:
            reason = gate_reasons[0] if gate_reasons else "Insufficient evaluable coverage."
    elif canonical == "fail" or critical_regressions:
        verdict = "BLOCK"
        if critical_regressions:
            ids = ", ".join(c.id for c in critical_regressions)
            reason = f"New failure on critical case(s): {ids}."
        else:
            reason = gate_reasons[0] if gate_reasons else "Acceptance policy not met."
    else:
        verdict = "APPROVE"
        changed = any([critical_regressions, improvements, other_regressions, added, removed])
        reason = "Acceptance policy met; no critical regressions." if changed else \
            "No changes between the two runs; acceptance policy met."

    # Coverage per category (evaluable / total).
    coverage: list[dict[str, Any]] = []
    cats = sorted({r.category for r in candidate.results})
    for cat in cats:
        rows = [r for r in candidate.results if r.category == cat]
        evaluable = [r for r in rows if r.status != "error" and not r.judge_disagree]
        coverage.append({"category": cat, "evaluable": len(evaluable), "total": len(rows)})

    return DecisionReport(
        verdict=verdict, reason=reason,
        suite_name=candidate.suite_name, suite_hash=candidate.suite_hash,
        baseline_run_id=baseline.run_id, candidate_run_id=candidate.run_id,
        baseline_target=baseline.target, candidate_target=candidate.target,
        critical_regressions=critical_regressions, improvements=improvements,
        other_regressions=other_regressions, added=added, removed=removed,
        disputes={"baseline": base_agg.get("judge_disagree", 0),
                  "candidate": cand_agg.get("judge_disagree", 0)},
        errors={"baseline": base_agg.get("errored", 0),
                "candidate": cand_agg.get("errored", 0)},
        coverage=coverage,
        latency={
            "baseline_p50": base_agg.get("latency_p50", 0.0),
            "baseline_p95": base_agg.get("latency_p95", 0.0),
            "candidate_p50": cand_agg.get("latency_p50", 0.0),
            "candidate_p95": cand_agg.get("latency_p95", 0.0),
        },
        cost_per_successful_task=_cost_per_successful_task(candidate, prices),
        policy_plain=_policy_plain(thresholds),
        rerun_command=rerun_command,
        gate_reasons=gate_reasons,
    )
