"""Run a scenario suite against a target with determinism and error accounting."""

from __future__ import annotations

import datetime
import platform
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from guardmeter.core.io_utils import new_run_id
from guardmeter.core.redact import redact
from guardmeter.scenarios.assertions import evaluate_assertion
from guardmeter.scenarios.results import (
    RunRecord,
    ScenarioResult,
    ScenarioResults,
    status_of,
)
from guardmeter.scenarios.schema import Scenario, Suite
from guardmeter.scenarios.target import Target, TargetResponse


def _guardmeter_version() -> str:
    try:
        from guardmeter import __version__
        return __version__
    except Exception:  # noqa: BLE001
        return "unknown"


def _run_once(scenario: Scenario, target: Target, *, cross_check: bool) -> RunRecord:
    resp: TargetResponse = target.run(scenario.input)
    if resp.error is not None:
        return RunRecord(latency_ms=resp.latency_ms, error=redact(resp.error), passed=False)

    outcomes: list[dict[str, Any]] = []
    all_pass = True
    for assertion in scenario.expect:
        try:
            oc = evaluate_assertion(assertion, resp, cross_check=cross_check)
        except Exception as exc:  # noqa: BLE001 (a judge/config failure errors the scenario, never crashes the run)
            return RunRecord(latency_ms=resp.latency_ms, error=redact(f"assertion error: {exc}"),
                             passed=False)
        outcomes.append({"type": oc.assertion_type, "passed": oc.passed,
                         "detail": oc.detail, "judge_disagree": oc.judge_disagree})
        # A judge-disagree assertion doesn't count toward pass/fail.
        if not oc.judge_disagree and not oc.passed:
            all_pass = False
    return RunRecord(
        latency_ms=resp.latency_ms, completion_tokens=resp.completion_tokens,
        passed=all_pass, text=redact(resp.text)[:2000],
        tool_calls=[{"name": tc.name, "arguments": tc.arguments} for tc in resp.tool_calls],
        outcomes=outcomes,
    )


def run_scenario(scenario: Scenario, target: Target, *, cross_check: bool = True) -> ScenarioResult:
    """Execute one scenario ``repeat`` times and aggregate its status."""
    runs = [_run_once(scenario, target, cross_check=cross_check) for _ in range(scenario.repeat)]
    judge_disagree = any(o["judge_disagree"] for r in runs for o in r.outcomes)
    return ScenarioResult(
        id=scenario.id, name=scenario.name, category=scenario.category,
        language=scenario.language, tags=scenario.tags, status=status_of(runs),
        runs=runs, judge_disagree=judge_disagree,
    )


def run_suite(
    suite: Suite,
    target: Target,
    *,
    concurrency: int = 1,
    cross_check: bool = True,
    run_id: str | None = None,
    timestamp: str | None = None,
) -> ScenarioResults:
    """Run every scenario (each ``repeat`` times) against the target.

    Scenarios run concurrently; results stay in suite order. ``timestamp`` is
    injected (the engine forbids wall-clock in some contexts); defaults to now.
    """
    ordered: list[ScenarioResult | None] = [None] * len(suite.scenarios)
    if concurrency > 1:
        with ThreadPoolExecutor(max_workers=concurrency) as ex:
            futs = {ex.submit(run_scenario, s, target, cross_check=cross_check): i
                    for i, s in enumerate(suite.scenarios)}
            for fut in as_completed(futs):
                ordered[futs[fut]] = fut.result()
    else:
        for i, s in enumerate(suite.scenarios):
            ordered[i] = run_scenario(s, target, cross_check=cross_check)

    ts = timestamp or datetime.datetime.now(datetime.UTC).isoformat().replace("+00:00", "Z")
    return ScenarioResults(
        run_id=run_id or new_run_id(),
        timestamp=ts,
        suite_name=suite.suite.name,
        suite_version=suite.suite.version,
        target=target.describe(),
        environment={"guardmeter_version": _guardmeter_version(),
                     "python_version": platform.python_version()},
        results=[r for r in ordered if r is not None],
    )
