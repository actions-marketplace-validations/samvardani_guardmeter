"""CI gate checker: evaluates EvalResults against GateConfig thresholds."""

from __future__ import annotations

import fnmatch
import logging
from dataclasses import dataclass, field
from typing import Any

from guardmeter.engine.metrics import MetricsBundle
from guardmeter.engine.results import EvalResults
from guardmeter.gate.schema import GateConfig, GlobalThresholds, SliceThresholds

logger = logging.getLogger(__name__)


@dataclass
class GateFailure:
    """A single structured gate violation, suitable for JSON output."""

    scope: str      # e.g. "global/candidate", "slice:self_harm/en", "attack:leetspeak"
    metric: str     # "recall" | "fpr" | "f1" | "latency_p99" | "recall_regression" | ...
    value: float
    threshold: float

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a JSON-compatible dict."""
        return {
            "scope": self.scope,
            "metric": self.metric,
            "value": self.value,
            "threshold": self.threshold,
        }


@dataclass
class GateCheck:
    """A single scope×metric check performed by the gate (passed or failed).

    Unlike GateFailure this records *every* comparison, so JUnit output can emit
    one <testcase> per check with an accurate tests/failures count.
    """

    scope: str       # clean scope, e.g. "global", "self_harm/en", "attack:leetspeak"
    metric: str      # threshold key, e.g. "min_recall", "max_fpr", "min_f1"
    value: float
    threshold: float
    passed: bool
    message: str = ""  # human-readable failure reason (empty when passed)


@dataclass
class GateCheckResult:
    """Result of running the CI gate checker."""

    passed: bool
    failures: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    # Machine-readable mirror of ``failures`` for --json output.
    structured_failures: list[GateFailure] = field(default_factory=list)
    # Every check performed (pass and fail) — used for JUnit output.
    checks: list[GateCheck] = field(default_factory=list)


def _scope_of(label: str) -> str:
    """Clean a checker label into a JUnit-friendly scope name."""
    if label == "global/candidate":
        return "global"
    if label.startswith("slice:"):
        return label[len("slice:"):]
    return label  # "attack:<name>" is already clean enough


def _effective_thresholds(
    slice_key: str,
    global_thr: GlobalThresholds,
    slice_overrides: dict[str, Any],
) -> GlobalThresholds:
    """Merge global thresholds with any matching slice override (fnmatch)."""
    merged = global_thr.model_copy()
    for pattern, override in slice_overrides.items():
        if fnmatch.fnmatch(slice_key, pattern):
            if isinstance(override, SliceThresholds):
                override_dict = override.model_dump(exclude_none=True)
            else:
                override_dict = dict(override)
            for attr, val in override_dict.items():
                if hasattr(merged, attr) and val is not None:
                    setattr(merged, attr, val)
    return merged


def _check_bundle(
    bundle: MetricsBundle,
    thr: GlobalThresholds,
    label: str,
    failures: list[str],
    structured: list[GateFailure] | None = None,
    checks: list[GateCheck] | None = None,
) -> None:
    """Record every threshold check (pass and fail) and append failures.

    Recall and F1 checks are skipped when there are no positive examples (tp+fn == 0).
    FPR check is skipped when there are no negative examples (fp+tn == 0).
    """
    has_positives = (bundle.tp + bundle.fn) > 0
    has_negatives = (bundle.fp + bundle.tn) > 0
    scope = _scope_of(label)

    def _eval(metric: str, key: str, value: float, threshold: float, ok: bool, short: str) -> None:
        if checks is not None:
            checks.append(GateCheck(scope=scope, metric=key, value=value,
                                    threshold=threshold, passed=ok, message="" if ok else short))
        if not ok:
            failures.append(f"{label}: {short}")
            if structured is not None:
                structured.append(GateFailure(scope=label, metric=metric, value=value, threshold=threshold))

    if has_positives:
        _eval("recall", "min_recall", bundle.recall, thr.min_recall,
              bundle.recall >= thr.min_recall,
              f"recall {bundle.recall:.4f} < min_recall {thr.min_recall}")
    if has_negatives:
        _eval("fpr", "max_fpr", bundle.fpr, thr.max_fpr,
              bundle.fpr <= thr.max_fpr,
              f"fpr {bundle.fpr:.4f} > max_fpr {thr.max_fpr}")
    _eval("latency_p99", "max_latency_p99_ms", bundle.latency_p99, float(thr.max_latency_p99_ms),
          bundle.latency_p99 <= thr.max_latency_p99_ms,
          f"latency_p99 {bundle.latency_p99:.1f} ms > max_latency_p99_ms {thr.max_latency_p99_ms}")
    _eval("hijack_rate", "max_hijack_rate", bundle.hijack_rate, thr.max_hijack_rate,
          bundle.hijack_rate <= thr.max_hijack_rate,
          f"hijack_rate {bundle.hijack_rate:.4f} > max_hijack_rate {thr.max_hijack_rate}")
    if has_positives:
        _eval("f1", "min_f1", bundle.f1, thr.min_f1,
              bundle.f1 >= thr.min_f1,
              f"f1 {bundle.f1:.4f} < min_f1 {thr.min_f1}")


class GateChecker:
    """Evaluates EvalResults against a GateConfig and returns a GateCheckResult."""

    def __init__(self, config: GateConfig, store: object = None) -> None:
        """Initialise with a gate config and optional store for comparison runs."""
        self.config = config
        self.store = store

    def check(self, results: EvalResults) -> GateCheckResult:
        """Run all gate checks and return a GateCheckResult."""
        failures: list[str] = []
        warnings: list[str] = []
        structured: list[GateFailure] = []
        checks: list[GateCheck] = []

        policy = self.config.mode
        cand_metrics = results.candidate_metrics.get(policy)
        if cand_metrics is None:
            # Fallback to strict
            cand_metrics = results.candidate_metrics.get("strict")

        if cand_metrics is None:
            failures.append("No candidate metrics found in results")
            structured.append(GateFailure(scope="global", metric="candidate_metrics", value=0.0, threshold=0.0))
            checks.append(GateCheck(scope="global", metric="candidate_metrics", value=0.0,
                                    threshold=0.0, passed=False, message="No candidate metrics found in results"))
            return GateCheckResult(passed=False, failures=failures,
                                   structured_failures=structured, checks=checks)

        # Global check
        global_thr = self.config.global_thresholds
        _check_bundle(cand_metrics, global_thr, "global/candidate", failures, structured, checks)

        # Split slice overrides: "attack:<glob>" keys target the attack-type family;
        # everything else targets the (category, language) family.
        cat_overrides = {
            k: v for k, v in self.config.slices.items() if not k.startswith("attack:")
        }
        attack_overrides = {
            k[len("attack:"):]: v
            for k, v in self.config.slices.items()
            if k.startswith("attack:")
        }

        # Per-slice checks (category, language)
        cand_slices = results.candidate_slices.get(policy, {})
        for key, bundle in cand_slices.items():
            slice_key = "/".join(str(k) for k in key)
            thr = _effective_thresholds(slice_key, global_thr, cat_overrides)
            _check_bundle(bundle, thr, f"slice:{slice_key}", failures, structured, checks)

        # Attack-type family — opt-in: only gated where an "attack:" override matches.
        cand_attack = results.candidate_attack_slices.get(policy, {})
        for key, bundle in cand_attack.items():
            attack_val = "/".join(str(k) for k in key)
            if not any(fnmatch.fnmatch(attack_val, pat) for pat in attack_overrides):
                continue
            thr = _effective_thresholds(attack_val, global_thr, attack_overrides)
            _check_bundle(bundle, thr, f"attack:{attack_val}", failures, structured, checks)

        # Regression check against previous run
        if self.config.comparison and self.store is not None:
            prev = None
            try:
                prev = self.store.latest_run()  # type: ignore[attr-defined]
            except Exception as exc:  # noqa: BLE001 (intentional resilience boundary)
                logger.warning("Could not load previous run for comparison: %s", exc)
            if prev is not None:
                prev_cand = prev.candidate_metrics.get(policy) or prev.candidate_metrics.get("strict")
                if prev_cand and cand_metrics:
                    recall_drop = prev_cand.recall - cand_metrics.recall
                    fpr_rise = cand_metrics.fpr - prev_cand.fpr
                    cmp = self.config.comparison
                    recall_ok = recall_drop <= cmp.max_recall_regression
                    checks.append(GateCheck(
                        scope="comparison", metric="max_recall_regression",
                        value=recall_drop, threshold=cmp.max_recall_regression, passed=recall_ok,
                        message="" if recall_ok else f"recall regression {recall_drop:.4f} > {cmp.max_recall_regression}",
                    ))
                    if not recall_ok:
                        failures.append(
                            f"Recall regression: dropped {recall_drop:.4f} (limit {cmp.max_recall_regression})"
                        )
                        structured.append(GateFailure(
                            scope="comparison", metric="recall_regression",
                            value=recall_drop, threshold=cmp.max_recall_regression,
                        ))
                    fpr_ok = fpr_rise <= cmp.max_fpr_increase
                    checks.append(GateCheck(
                        scope="comparison", metric="max_fpr_increase",
                        value=fpr_rise, threshold=cmp.max_fpr_increase, passed=fpr_ok,
                        message="" if fpr_ok else f"fpr increase {fpr_rise:.4f} > {cmp.max_fpr_increase}",
                    ))
                    if not fpr_ok:
                        failures.append(
                            f"FPR regression: rose {fpr_rise:.4f} (limit {cmp.max_fpr_increase})"
                        )
                        structured.append(GateFailure(
                            scope="comparison", metric="fpr_increase",
                            value=fpr_rise, threshold=cmp.max_fpr_increase,
                        ))

        passed = len(failures) == 0
        if self.config.on_failure == "warn" and not passed:
            warnings.extend(failures)
            failures = []
            structured = []  # warn mode: nothing counts as a hard failure
            passed = True  # warn mode always passes the gate

        return GateCheckResult(
            passed=passed, failures=failures, warnings=warnings,
            structured_failures=structured, checks=checks,
        )
