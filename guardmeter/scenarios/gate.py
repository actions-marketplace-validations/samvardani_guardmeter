"""Gate a scenario run against ScenarioThresholds."""

from __future__ import annotations

from typing import Any

from guardmeter.gate.schema import ScenarioThresholds


def check_scenario_gate(aggregate: dict[str, Any], thr: ScenarioThresholds) -> tuple[str, list[str]]:
    """Return ``(verdict, reasons)`` for a scenario-run aggregate.

    ``verdict`` is ``"pass"``, ``"fail"`` or ``"inconclusive"``. Incomplete or
    untrustworthy evaluation is **inconclusive**, never a pass: no/low coverage,
    a required category that never ran, errors over threshold, or unresolved
    judge disputes over threshold. Threshold breaches on an otherwise complete
    run are **fail**. Only a complete, dispute-free, in-threshold run is a pass.
    """
    inconclusive: list[str] = []
    failures: list[str] = []

    # ── coverage / trust: these make the result inconclusive ──
    total = aggregate.get("total")
    pr = aggregate.get("pass_rate")
    if not total or total < thr.min_total or pr is None:
        # Errored/disputed scenarios are not evaluable, so don't count them as
        # coverage — the denominator that decides the verdict is the evaluable set.
        errored = aggregate.get("errored", 0) or 0
        disputed = aggregate.get("judge_disagree", 0) or 0
        evaluable = (total or 0) - errored - disputed
        detail = [f"{errored} errored"]
        if disputed:
            detail.append(f"{disputed} disputed")
        detail.append(f"min {thr.min_total}")
        inconclusive.append(
            f"insufficient coverage: {evaluable} evaluable of {total or 0} "
            f"({', '.join(detail)})")

    by_cat = aggregate.get("by_category") or {}
    for cat in thr.per_category:
        if cat not in by_cat or by_cat.get(cat) is None:
            inconclusive.append(f"required category {cat!r} was not evaluated")

    err = aggregate.get("error_rate", 0.0)
    if err > thr.max_error_rate:
        inconclusive.append(f"error_rate {err:.4f} > max_error_rate {thr.max_error_rate}")

    disagree = aggregate.get("judge_disagree_rate")
    if disagree is None and total:
        disagree = (aggregate.get("judge_disagree", 0) or 0) / total
    if disagree and disagree > thr.max_judge_disagree_rate:
        inconclusive.append(f"unresolved judge disputes {disagree:.4f} > "
                            f"max_judge_disagree_rate {thr.max_judge_disagree_rate}")

    # ── threshold breaches: these are failures ──
    if pr is not None and pr < thr.min_pass_rate:
        failures.append(f"pass_rate {pr:.4f} < min_pass_rate {thr.min_pass_rate}")
    for cat, min_pr in thr.per_category.items():
        cat_pr = by_cat.get(cat)
        if cat_pr is not None and cat_pr < min_pr:
            failures.append(f"category {cat}: pass_rate {cat_pr:.4f} < {min_pr}")
    flaky = aggregate.get("flaky_rate", 0.0)
    if flaky > thr.max_flaky_rate:
        failures.append(f"flaky_rate {flaky:.4f} > max_flaky_rate {thr.max_flaky_rate}")
    if thr.max_latency_p95_ms is not None:
        p95 = aggregate.get("latency_p95", 0.0)
        if p95 > thr.max_latency_p95_ms:
            failures.append(f"latency_p95 {p95:.0f}ms > max_latency_p95_ms {thr.max_latency_p95_ms}")

    if failures:
        return "fail", failures + inconclusive
    if inconclusive:
        return "inconclusive", inconclusive
    return "pass", []
