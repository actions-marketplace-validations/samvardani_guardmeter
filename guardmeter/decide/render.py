"""Render a DecisionReport to Markdown or a single-file, offline HTML page."""

from __future__ import annotations

import html
import json

from jinja2 import Environment, PackageLoader, select_autoescape

from guardmeter.decide.model import CaseChange, DecisionReport

_VERDICT_BLURB = {
    "APPROVE": "The candidate meets the acceptance policy with no critical regressions.",
    "BLOCK": "The candidate must not ship as-is.",
    "INCONCLUSIVE": "The evaluation is incomplete or untrustworthy; it cannot decide.",
}


def _case_line(c: CaseChange) -> str:
    before = c.before or "—"
    after = c.after or "—"
    mark = " ⚠️ critical" if c.critical else ""
    fail = f" — {'; '.join(c.failing)}" if c.failing else ""
    return f"`{c.id}` ({c.category}/{c.language}){mark}: {before} → {after}{fail}"


def render_markdown(r: DecisionReport) -> str:
    """A one-page Markdown decision."""
    lines: list[str] = []
    lines.append(f"# Release decision: {r.verdict}")
    lines.append("")
    lines.append(f"**{r.reason}** {_VERDICT_BLURB.get(r.verdict, '')}")
    lines.append("")
    lines.append(f"Suite `{r.suite_name}` (hash `{r.suite_hash}`) — "
                 f"baseline `{r.baseline_run_id[:12]}` vs candidate `{r.candidate_run_id[:12]}`.")
    lines.append("")

    lines.append("## Critical regressions")
    if r.critical_regressions:
        for c in r.critical_regressions:
            lines.append(f"- {_case_line(c)}")
    else:
        lines.append("- None.")
    lines.append("")

    def _section(title: str, cases: list[CaseChange]) -> None:
        lines.append(f"## {title}")
        if cases:
            for c in cases:
                lines.append(f"- {_case_line(c)}")
        else:
            lines.append("- None.")
        lines.append("")

    _section("Improvements", r.improvements)
    _section("Other regressions", r.other_regressions)
    _section("Added cases", r.added)
    _section("Removed cases", r.removed)

    lines.append("## Disputes, errors & coverage")
    lines.append(f"- Judge disputes — baseline {r.disputes.get('baseline', 0)}, "
                 f"candidate {r.disputes.get('candidate', 0)}")
    lines.append(f"- Errors — baseline {r.errors.get('baseline', 0)}, "
                 f"candidate {r.errors.get('candidate', 0)}")
    for cov in r.coverage:
        lines.append(f"- Coverage `{cov['category']}`: "
                     f"{cov['evaluable']}/{cov['total']} evaluable")
    lines.append("")

    lines.append("## Latency (ms)")
    lines.append(f"- p50 — baseline {r.latency.get('baseline_p50', 0):.0f}, "
                 f"candidate {r.latency.get('candidate_p50', 0):.0f}")
    lines.append(f"- p95 — baseline {r.latency.get('baseline_p95', 0):.0f}, "
                 f"candidate {r.latency.get('candidate_p95', 0):.0f}")
    lines.append("")

    lines.append("## Cost per successful task")
    lines.append(f"- {r.cost_per_successful_task}")
    lines.append("")

    lines.append("## Acceptance policy applied")
    for p in r.policy_plain:
        lines.append(f"- {p}")
    lines.append("")

    lines.append("## Reproduce")
    lines.append(f"- Suite hash: `{r.suite_hash}`")
    lines.append(f"- Baseline run: `{r.baseline_run_id}` — target `{json.dumps(r.baseline_target)}`")
    lines.append(f"- Candidate run: `{r.candidate_run_id}` — target `{json.dumps(r.candidate_target)}`")
    if r.rerun_command:
        lines.append("")
        lines.append("```bash")
        lines.append(r.rerun_command)
        lines.append("```")
    lines.append("")
    return "\n".join(lines)


def _env() -> Environment:
    return Environment(
        loader=PackageLoader("guardmeter.decide", "templates"),
        autoescape=select_autoescape(["html"]),
    )


def render_html(r: DecisionReport) -> str:
    """A single self-contained, offline, print-friendly HTML page."""
    tmpl = _env().get_template("decision.html")
    return tmpl.render(r=r, blurb=_VERDICT_BLURB.get(r.verdict, ""),
                       target_json=lambda t: html.escape(json.dumps(t)))
