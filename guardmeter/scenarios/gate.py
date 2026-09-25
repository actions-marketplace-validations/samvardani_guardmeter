"""Gate a scenario run against ScenarioThresholds."""

from __future__ import annotations

from typing import Any

from guardmeter.gate.schema import ScenarioThresholds


def check_scenario_gate(aggregate: dict[str, Any], thr: ScenarioThresholds) -> tuple[bool, list[str]]:
    """Return (passed, failures) for a scenario-run aggregate against thresholds."""
    failures: list[str] = []

    pr = aggregate.get("pass_rate")
    if pr is not None and pr < thr.min_pass_rate:
        failures.append(f"pass_rate {pr:.4f} < min_pass_rate {thr.min_pass_rate}")

    for cat, min_pr in thr.per_category.items():
        cat_pr = (aggregate.get("by_category") or {}).get(cat)
        if cat_pr is not None and cat_pr < min_pr:
            failures.append(f"category {cat}: pass_rate {cat_pr:.4f} < {min_pr}")

    flaky = aggregate.get("flaky_rate", 0.0)
    if flaky > thr.max_flaky_rate:
        failures.append(f"flaky_rate {flaky:.4f} > max_flaky_rate {thr.max_flaky_rate}")

    err = aggregate.get("error_rate", 0.0)
    if err > thr.max_error_rate:
        failures.append(f"error_rate {err:.4f} > max_error_rate {thr.max_error_rate}")

    if thr.max_latency_p95_ms is not None:
        p95 = aggregate.get("latency_p95", 0.0)
        if p95 > thr.max_latency_p95_ms:
            failures.append(f"latency_p95 {p95:.0f}ms > max_latency_p95_ms {thr.max_latency_p95_ms}")

    return (not failures), failures
