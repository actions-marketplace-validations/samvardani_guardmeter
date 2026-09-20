"""CI gate checker: evaluates EvalResults against GateConfig thresholds."""

from __future__ import annotations

import fnmatch
import logging
from dataclasses import dataclass, field
from typing import Any

from guardbench.engine.metrics import MetricsBundle
from guardbench.engine.results import EvalResults
from guardbench.gate.schema import GateConfig, GlobalThresholds, SliceThresholds

logger = logging.getLogger(__name__)


@dataclass
class GateCheckResult:
    """Result of running the CI gate checker."""

    passed: bool
    failures: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


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
) -> None:
    """Append failure strings to the list for any threshold violations.

    Recall and F1 checks are skipped when there are no positive examples (tp+fn == 0).
    FPR check is skipped when there are no negative examples (fp+tn == 0).
    """
    has_positives = (bundle.tp + bundle.fn) > 0
    has_negatives = (bundle.fp + bundle.tn) > 0

    if has_positives and bundle.recall < thr.min_recall:
        failures.append(
            f"{label}: recall {bundle.recall:.4f} < min_recall {thr.min_recall}"
        )
    if has_negatives and bundle.fpr > thr.max_fpr:
        failures.append(
            f"{label}: fpr {bundle.fpr:.4f} > max_fpr {thr.max_fpr}"
        )
    if bundle.latency_p99 > thr.max_latency_p99_ms:
        failures.append(
            f"{label}: latency_p99 {bundle.latency_p99:.1f} ms > max_latency_p99_ms {thr.max_latency_p99_ms}"
        )
    if has_positives and bundle.f1 < thr.min_f1:
        failures.append(
            f"{label}: f1 {bundle.f1:.4f} < min_f1 {thr.min_f1}"
        )


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

        policy = self.config.mode
        cand_metrics = results.candidate_metrics.get(policy)
        if cand_metrics is None:
            # Fallback to strict
            cand_metrics = results.candidate_metrics.get("strict")

        if cand_metrics is None:
            failures.append("No candidate metrics found in results")
            return GateCheckResult(passed=False, failures=failures)

        # Global check
        global_thr = self.config.global_thresholds
        _check_bundle(cand_metrics, global_thr, "global/candidate", failures)

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
            _check_bundle(bundle, thr, f"slice:{slice_key}", failures)

        # Attack-type family — opt-in: only gated where an "attack:" override matches.
        cand_attack = results.candidate_attack_slices.get(policy, {})
        for key, bundle in cand_attack.items():
            attack_val = "/".join(str(k) for k in key)
            if not any(fnmatch.fnmatch(attack_val, pat) for pat in attack_overrides):
                continue
            thr = _effective_thresholds(attack_val, global_thr, attack_overrides)
            _check_bundle(bundle, thr, f"attack:{attack_val}", failures)

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
                    if recall_drop > cmp.max_recall_regression:
                        failures.append(
                            f"Recall regression: dropped {recall_drop:.4f} (limit {cmp.max_recall_regression})"
                        )
                    if fpr_rise > cmp.max_fpr_increase:
                        failures.append(
                            f"FPR regression: rose {fpr_rise:.4f} (limit {cmp.max_fpr_increase})"
                        )

        passed = len(failures) == 0
        if self.config.on_failure == "warn" and not passed:
            warnings.extend(failures)
            failures = []
            passed = True  # warn mode always passes the gate

        return GateCheckResult(passed=passed, failures=failures, warnings=warnings)
