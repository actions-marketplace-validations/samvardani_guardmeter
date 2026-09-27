"""Statistical significance tests for comparing two guards."""

from __future__ import annotations

from guardmeter.core.guard import GuardResult
from guardmeter.data.schema import DatasetRecord


def mcnemar_test(
    preds_a: list[GuardResult],
    preds_b: list[GuardResult],
    records: list[DatasetRecord],
    policy: str = "strict",
) -> tuple[float, float, int]:
    """Compute McNemar's test comparing two guards' predictions.

    Returns ``(statistic, p_value, n_excluded)``. Pairs where either guard
    produced an ``error`` (no verdict) are **excluded** — an error is not a
    correct benign result — and counted in ``n_excluded``. p_value < 0.05
    indicates significance; continuity-corrected.
    """
    from scipy.stats import chi2  # type: ignore[import-untyped]

    # Count discordant pairs; skip any pair with an errored (verdict-less) guard.
    b = 0  # A correct, B wrong
    c = 0  # A wrong, B correct
    excluded = 0
    for pa, pb, rec in zip(preds_a, preds_b, records):
        if pa.prediction == "error" or pb.prediction == "error":
            excluded += 1
            continue
        label = rec.label
        gt_pos = (label != "benign") if policy == "strict" else (label == "unsafe")
        a_correct = (pa.prediction == "flag") == gt_pos
        b_correct = (pb.prediction == "flag") == gt_pos
        if a_correct and not b_correct:
            b += 1
        elif not a_correct and b_correct:
            c += 1

    n = b + c
    if n == 0:
        return 0.0, 1.0, excluded

    # McNemar's with continuity correction
    statistic = (abs(b - c) - 1.0) ** 2 / n
    p_value = float(1.0 - chi2.cdf(statistic, df=1))
    return round(statistic, 4), round(p_value, 4), excluded
