"""Markdown and JUnit renderings of a scenario run."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from xml.dom import minidom

from guardmeter.scenarios.results import ScenarioResults


def summary_md(results: ScenarioResults) -> str:
    """A GitHub-step-summary table for a scenario run."""
    agg = results.aggregate()
    t = results.target
    lines = [
        f"## Scenario run — {results.suite_name} v{results.suite_version}",
        "",
        f"**Target:** {t.get('kind', '?')} `{t.get('model') or t.get('name', '')}`"
        + (f" @ {t['endpoint']}" if t.get("endpoint") else ""),
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Pass rate | {_fmt(agg['pass_rate'])} |",
        f"| Passed / Failed | {agg['passed']} / {agg['failed']} |",
        f"| Flaky | {agg['flaky']} ({_pct(agg['flaky_rate'])}) |",
        f"| Errors | {agg['errored']} ({_pct(agg['error_rate'])}) |",
        f"| Judge-disagree | {agg['judge_disagree']} ({_pct(agg['judge_disagree_rate'])}) |",
        f"| Latency p50/p95/p99 | {agg['latency_p50']:.0f} / {agg['latency_p95']:.0f} / {agg['latency_p99']:.0f} ms |",
        "",
        "### Pass rate by category",
        "",
        "| Category | Pass rate |",
        "|----------|-----------|",
    ]
    for cat, rate in agg["by_category"].items():
        lines.append(f"| {cat} | {_fmt(rate)} |")
    failing = [r for r in results.results if r.status in ("fail", "flaky", "error")]
    if failing:
        lines += ["", "### Not passing", ""]
        for r in failing:
            evidence = "; ".join(r.failing) if r.failing else r.status
            lines.append(f"- **{r.id}** ({r.category}, {r.status}): {evidence}")
    return "\n".join(lines) + "\n"


def _fmt(rate: float | None) -> str:
    return "n/a" if rate is None else f"{rate:.1%}"


def _pct(rate: float) -> str:
    return f"{rate:.1%}"


def junit_xml(results: ScenarioResults) -> str:
    """One <testcase> per scenario; failures/errors carry the evidence."""
    total = len(results.results)
    failures = sum(1 for r in results.results if r.status in ("fail", "flaky"))
    errors = sum(1 for r in results.results if r.status == "error")
    suites = ET.Element("testsuites", tests=str(total), failures=str(failures), errors=str(errors))
    suite = ET.SubElement(suites, "testsuite", name=f"scenarios/{results.suite_name}",
                          tests=str(total), failures=str(failures), errors=str(errors))
    for r in results.results:
        tc = ET.SubElement(suite, "testcase", classname=r.category, name=r.id,
                           time=f"{(sum(run.latency_ms for run in r.runs) / 1000):.3f}")
        if r.status == "error":
            err = next((run.error for run in r.runs if run.error), "error")
            ET.SubElement(tc, "error", message=str(err))
        elif r.status in ("fail", "flaky"):
            msg = f"{r.status}: " + ("; ".join(r.failing) if r.failing else "runs disagree")
            ET.SubElement(tc, "failure", message=msg[:500])
        elif r.judge_disagree:
            ET.SubElement(tc, "skipped", message="judge-disagree (excluded from gate)")
    return minidom.parseString(ET.tostring(suites)).toprettyxml(indent="  ")
