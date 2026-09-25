"""Result types for a scenario run, with aggregation and (de)serialisation."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any


def _pct(vals: list[float], q: float) -> float:
    if not vals:
        return 0.0
    s = sorted(vals)
    idx = max(0, min(len(s) - 1, math.ceil(q * len(s)) - 1))
    return s[idx]


@dataclass
class RunRecord:
    """One execution of a scenario."""

    latency_ms: int = 0
    completion_tokens: int | None = None
    error: str | None = None
    passed: bool = False  # all assertions passed on this run
    text: str = ""  # redacted
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    outcomes: list[dict[str, Any]] = field(default_factory=list)  # {type, passed, detail, judge_disagree}


@dataclass
class ScenarioResult:
    """Aggregated result for one scenario across its repeats."""

    id: str
    name: str
    category: str
    language: str
    tags: list[str]
    status: str  # pass | fail | flaky | error
    runs: list[RunRecord]
    judge_disagree: bool = False

    @property
    def failing(self) -> list[str]:
        """Evidence: failing assertion details from a representative failing run."""
        for r in self.runs:
            if r.error is None and not r.passed:
                return [f"{o['type']}: {o['detail']}" for o in r.outcomes if not o["passed"]]
        return []


def status_of(runs: list[RunRecord]) -> str:
    """Derive a scenario status from its runs. Any error → error (incomplete)."""
    if not runs or any(r.error for r in runs):
        return "error"
    passes = {r.passed for r in runs}
    if len(passes) > 1:
        return "flaky"
    return "pass" if passes == {True} else "fail"


@dataclass
class ScenarioResults:
    """Full results of running a suite against a target."""

    run_id: str
    timestamp: str
    suite_name: str
    suite_version: str
    target: dict[str, Any]
    environment: dict[str, Any]
    results: list[ScenarioResult] = field(default_factory=list)

    def aggregate(self) -> dict[str, Any]:
        """Pass rates (overall + per category/language/tag), latency, rates."""
        n = len(self.results)
        errored = [r for r in self.results if r.status == "error"]
        flaky = [r for r in self.results if r.status == "flaky"]
        disagree = [r for r in self.results if r.judge_disagree]
        # Gate denominator excludes error and judge-disagree scenarios.
        gate_set = [r for r in self.results if r.status != "error" and not r.judge_disagree]

        def rate(subset: list[ScenarioResult]) -> float | None:
            evaluable = [r for r in subset if r.status != "error" and not r.judge_disagree]
            if not evaluable:
                return None
            return round(sum(1 for r in evaluable if r.status == "pass") / len(evaluable), 4)

        def group(dim: str) -> dict[str, float | None]:
            keys = sorted({getattr(r, dim) for r in self.results})
            return {k: rate([r for r in self.results if getattr(r, dim) == k]) for k in keys}

        tag_keys = sorted({t for r in self.results for t in r.tags})
        by_tag = {t: rate([r for r in self.results if t in r.tags]) for t in tag_keys}

        lats = [run.latency_ms for r in self.results for run in r.runs if run.error is None]
        toks = [run.completion_tokens for r in self.results for run in r.runs
                if run.error is None and run.completion_tokens is not None]
        return {
            "total": n,
            "pass_rate": rate(self.results),
            "passed": sum(1 for r in gate_set if r.status == "pass"),
            "failed": sum(1 for r in gate_set if r.status == "fail"),
            "flaky": len(flaky),
            "errored": len(errored),
            "judge_disagree": len(disagree),
            "flaky_rate": round(len(flaky) / n, 4) if n else 0.0,
            "error_rate": round(len(errored) / n, 4) if n else 0.0,
            "judge_disagree_rate": round(len(disagree) / n, 4) if n else 0.0,
            "by_category": group("category"),
            "by_language": group("language"),
            "by_tag": by_tag,
            "latency_p50": _pct([float(x) for x in lats], 0.50),
            "latency_p95": _pct([float(x) for x in lats], 0.95),
            "latency_p99": _pct([float(x) for x in lats], 0.99),
            "token_p50": _pct([float(x) for x in toks], 0.50) if toks else None,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id, "timestamp": self.timestamp,
            "suite_name": self.suite_name, "suite_version": self.suite_version,
            "target": self.target, "environment": self.environment,
            "aggregate": self.aggregate(),
            "results": [
                {
                    "id": r.id, "name": r.name, "category": r.category, "language": r.language,
                    "tags": r.tags, "status": r.status, "judge_disagree": r.judge_disagree,
                    "failing": r.failing,
                    "runs": [
                        {"latency_ms": run.latency_ms, "completion_tokens": run.completion_tokens,
                         "error": run.error, "passed": run.passed, "text": run.text,
                         "tool_calls": run.tool_calls, "outcomes": run.outcomes}
                        for run in r.runs
                    ],
                }
                for r in self.results
            ],
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ScenarioResults:
        results = [
            ScenarioResult(
                id=r["id"], name=r.get("name", ""), category=r.get("category", "custom"),
                language=r.get("language", "en"), tags=r.get("tags", []), status=r["status"],
                judge_disagree=r.get("judge_disagree", False),
                runs=[RunRecord(**{k: run[k] for k in
                                   ("latency_ms", "completion_tokens", "error", "passed",
                                    "text", "tool_calls", "outcomes") if k in run})
                      for run in r.get("runs", [])],
            )
            for r in d.get("results", [])
        ]
        return cls(
            run_id=d["run_id"], timestamp=d["timestamp"], suite_name=d["suite_name"],
            suite_version=d.get("suite_version", ""), target=d.get("target", {}),
            environment=d.get("environment", {}), results=results,
        )
