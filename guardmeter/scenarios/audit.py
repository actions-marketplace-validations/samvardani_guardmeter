"""Suite audit: prove the tests can actually fail, are reviewed, and aren't flaky.

Static checks run offline. The "cannot fail" check runs the suite against a
NullTarget (always "OK", no tools). Flaky and judge-disagree need a real
endpoint (each scenario is run 3×). A suite is "validated" only when it has no
schema errors, no unreviewed scenarios, no cannot-fail scenarios, and flaky < 5%.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from guardmeter.data.validate import NEAR_DUP_JACCARD, _tokens
from guardmeter.scenarios.runner import run_suite
from guardmeter.scenarios.schema import Suite
from guardmeter.scenarios.target import NullTarget, Target

# Assertion kinds that can only pass, never distinguish a broken target on their
# own (a category built only from these is "weak").
_WEAK_ONLY = {"max_latency_ms", "max_tokens", "must_not_call_tool", "must_not_contain", "allow"}

FLAKY_MAX = 0.05


@dataclass
class AuditReport:
    suite_name: str
    total: int
    unreviewed: list[str] = field(default_factory=list)
    near_duplicates: list[tuple[str, str, float]] = field(default_factory=list)
    weak_categories: list[str] = field(default_factory=list)
    cannot_fail: list[str] = field(default_factory=list)
    flaky: list[str] = field(default_factory=list)
    judge_disagree: list[str] = field(default_factory=list)
    flaky_rate: float = 0.0
    endpoint_used: bool = False
    # id → language, for per-language partial validation.
    languages: dict[str, str] = field(default_factory=dict)

    @property
    def validated(self) -> bool:
        return (not self.unreviewed and not self.cannot_fail
                and self.endpoint_used and self.flaky_rate < FLAKY_MAX)

    def validated_languages(self) -> list[str]:
        """Languages whose scenarios are all reviewed, none cannot-fail, none flaky."""
        if not self.endpoint_used:
            return []
        by_lang: dict[str, list[str]] = {}
        for sid, lang in self.languages.items():
            by_lang.setdefault(lang, []).append(sid)
        bad = set(self.unreviewed) | set(self.cannot_fail) | set(self.flaky)
        return sorted(lang for lang, ids in by_lang.items()
                      if ids and not any(i in bad for i in ids))

    def verdict(self) -> str:
        """Overall verdict string, supporting partial validation by language."""
        if self.validated:
            return "validated"
        langs = self.validated_languages()
        if langs:
            return f"validated: partial (languages: {', '.join(langs)})"
        return "not validated"


def _scenario_text(scenario: Any) -> str:
    inp = scenario.input
    if inp.text:
        return inp.text
    if inp.messages:
        return " ".join(str(m.get("content") or "") for m in inp.messages)
    return ""


def audit_suite(suite: Suite, target: Target | None = None, *, repeats: int = 3) -> AuditReport:
    """Run the static and (if a target is given) dynamic audit checks."""
    rep = AuditReport(suite_name=suite.suite.name, total=len(suite.scenarios))
    rep.languages = {s.id: s.language for s in suite.scenarios}

    # Review coverage.
    rep.unreviewed = [s.id for s in suite.scenarios if not s.reviewed_by]

    # Near-duplicate inputs (token-set Jaccard), across the whole suite.
    toks = [(s.id, _tokens(_scenario_text(s))) for s in suite.scenarios]
    for i in range(len(toks)):
        for j in range(i + 1, len(toks)):
            a, b = toks[i][1], toks[j][1]
            if a and b:
                jac = len(a & b) / len(a | b)
                if jac >= NEAR_DUP_JACCARD:
                    rep.near_duplicates.append((toks[i][0], toks[j][0], round(jac, 2)))

    # Coverage weakness: a category whose scenarios only ever use weak assertions.
    by_cat: dict[str, set[str]] = {}
    for s in suite.scenarios:
        by_cat.setdefault(s.category, set()).update(a.type for a in s.expect)
    rep.weak_categories = sorted(c for c, kinds in by_cat.items() if kinds <= _WEAK_ONLY)

    # Cannot-fail: passes against the always-"OK" null target.
    null_run = run_suite(_with_repeat(suite, 1), NullTarget(), cross_check=False,
                         timestamp="1970-01-01T00:00:00Z")
    rep.cannot_fail = [r.id for r in null_run.results if r.status == "pass"]

    # Flaky + judge-disagree need a real endpoint.
    if target is not None:
        rep.endpoint_used = True
        dyn = run_suite(_with_repeat(suite, repeats), target, cross_check=True,
                        timestamp="1970-01-01T00:00:00Z")
        rep.flaky = [r.id for r in dyn.results if r.status == "flaky"]
        rep.judge_disagree = [r.id for r in dyn.results if r.judge_disagree]
        rep.flaky_rate = round(len(rep.flaky) / rep.total, 4) if rep.total else 0.0

    return rep


def _with_repeat(suite: Suite, repeat: int) -> Suite:
    return Suite(suite=suite.suite,
                 scenarios=[s.model_copy(update={"repeat": repeat}) for s in suite.scenarios])


def render_validation_md(rep: AuditReport) -> str:
    """Render the audit report as validation.md."""
    lines = [
        f"# Scenario suite audit — {rep.suite_name}",
        "",
        f"- Scenarios: **{rep.total}**",
        f"- Endpoint checks: {'run' if rep.endpoint_used else 'skipped (no --endpoint)'}",
        "",
        "## Verdict",
        "",
        f"**{rep.verdict()}**",
        "",
    ]
    if not rep.validated:
        reasons = []
        if rep.unreviewed:
            reasons.append(f"{len(rep.unreviewed)} unreviewed")
        if rep.cannot_fail:
            reasons.append(f"{len(rep.cannot_fail)} cannot-fail")
        if not rep.endpoint_used:
            reasons.append("flaky not measured (no endpoint)")
        elif rep.flaky_rate >= FLAKY_MAX:
            reasons.append(f"flaky rate {rep.flaky_rate:.1%} ≥ {FLAKY_MAX:.0%}")
        lines.append("Blocking: " + (", ".join(reasons) or "none") + "\n")

    def section(title: str, items: list[Any]) -> None:
        lines.append(f"## {title} ({len(items)})")
        lines.append("")
        if items:
            lines.extend(f"- {x}" for x in items)
        else:
            lines.append("_none_")
        lines.append("")

    section("Unreviewed scenarios", rep.unreviewed)
    section("Cannot-fail scenarios (pass on a broken null target)", rep.cannot_fail)
    section("Weak categories (only latency/negative assertions)", rep.weak_categories)
    section("Near-duplicate inputs", [f"{a} ~ {b} (jaccard {j})" for a, b, j in rep.near_duplicates])
    if rep.endpoint_used:
        section(f"Flaky scenarios (rate {rep.flaky_rate:.1%})", rep.flaky)
        section("Judge-disagree scenarios", rep.judge_disagree)
    return "\n".join(lines) + "\n"
