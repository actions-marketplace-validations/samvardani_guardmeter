"""Evaluator: orchestrates guard predictions, metrics, slices, and significance tests."""

from __future__ import annotations

import datetime
import json
import logging
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Any

from guardmeter.core.guard import Guard, GuardResult
from guardmeter.core.io_utils import git_commit_sha, hash_content, new_run_id
from guardmeter.core.redact import redact
from guardmeter.data.schema import DatasetRecord
from guardmeter.engine.metrics import (
    compute_confusion,
    compute_metrics,
    compute_slices,
    count_errors,
    count_hijacked,
)
from guardmeter.engine.results import EvalResults, SampleResult
from guardmeter.engine.significance import mcnemar_test

logger = logging.getLogger(__name__)

_RATE_LIMIT_MARKERS = ("rate limit", "ratelimit", "429", "too many requests")


def _is_rate_limit(exc: BaseException) -> bool:
    """Heuristically detect a rate-limit error across SDKs (by type name or message)."""
    if "ratelimit" in type(exc).__name__.lower():
        return True
    msg = str(exc).lower()
    return any(m in msg for m in _RATE_LIMIT_MARKERS)


def call_with_retry(
    guard: Guard,
    text: str,
    context: str | None,
    *,
    max_retries: int = 3,
    backoff_base: float = 0.5,
    sleep: Callable[[float], None] = time.sleep,
) -> GuardResult:
    """Call ``guard.predict`` with exponential backoff on rate-limit errors.

    Retries a rate-limited call up to ``max_retries`` times (sleeping
    ``backoff_base * 2**attempt`` seconds). Any error that survives retries — or
    any non-rate-limit error — becomes an ``"error"`` result (``score=None``,
    ``metadata["error"]`` redacted, ``metadata["attempts"]`` set). Error results
    are excluded from metrics, not counted as a flag: a guard call that never
    produced a verdict must not silently inflate recall or FPR.
    """
    attempt = 0
    while True:
        try:
            return guard.predict(text, context=context)
        except Exception as exc:  # noqa: BLE001 (resilience boundary: never abort a run)
            if _is_rate_limit(exc) and attempt < max_retries:
                sleep(backoff_base * (2 ** attempt))
                attempt += 1
                continue
            safe = redact(str(exc))
            logger.warning("guard %r call failed (error, excluded from metrics): %s",
                           guard.name, safe)
            return GuardResult(
                prediction="error", score=None, latency_ms=0,
                metadata={"error": safe, "attempts": attempt + 1},
            )


@dataclass
class EvalConfig:
    """Configuration for an evaluation run."""

    policy: str = "strict"
    slices: list[str] = field(default_factory=lambda: ["category", "language"])
    run_id: str | None = None  # auto-generated UUID if None
    include_lenient: bool = True  # also compute lenient-policy metrics
    concurrency: int = 1  # >1 evaluates guard calls in a thread pool


class Evaluator:
    """Orchestrates a full evaluation: both guards × both policies × per-slice metrics."""

    def __init__(
        self,
        baseline: Guard,
        candidate: Guard,
        dataset: list[DatasetRecord],
        config: EvalConfig | None = None,
        judge: Any = None,
        on_progress: Callable[[int, int], None] | None = None,
    ) -> None:
        """Initialise with two guards, a dataset, optional config, judge, progress cb."""
        self.baseline = baseline
        self.candidate = candidate
        self.dataset = dataset
        self.config = config or EvalConfig()
        self.judge = judge
        self.on_progress = on_progress

    def _predict_all(self, guard: Guard, records: list[DatasetRecord], done: int, total: int) -> list[Any]:
        """Predict all records; pass per-record context and report progress.

        Every call goes through ``call_with_retry`` so a raising guard (dead API
        key, transient network error, or a bug in a local guard) becomes an
        excluded ``"error"`` result rather than aborting the run or being
        miscounted. Results stay in input order regardless of completion order.
        """
        preds: list[Any] = [None] * len(records)

        def work(i: int, rec: DatasetRecord) -> tuple[int, GuardResult]:
            return i, call_with_retry(guard, rec.text, rec.context)

        if self.config.concurrency > 1:
            with ThreadPoolExecutor(max_workers=self.config.concurrency) as ex:
                futures = [ex.submit(work, i, rec) for i, rec in enumerate(records)]
                for n, fut in enumerate(as_completed(futures)):
                    i, res = fut.result()
                    preds[i] = res
                    if self.on_progress is not None:
                        self.on_progress(done + n + 1, total)
        else:
            for i, rec in enumerate(records):
                preds[i] = call_with_retry(guard, rec.text, rec.context)
                if self.on_progress is not None:
                    self.on_progress(done + i + 1, total)
        return preds

    def run(self) -> EvalResults:
        """Run the full evaluation and return EvalResults."""
        run_id = self.config.run_id or new_run_id()
        timestamp = datetime.datetime.now(datetime.UTC).isoformat().replace("+00:00", "Z")
        git_commit = git_commit_sha()

        # Hash the dataset for reproducibility
        serialised = json.dumps(
            [r.model_dump() for r in self.dataset], sort_keys=True
        ).encode("utf-8")
        dataset_sha = hash_content(serialised)

        texts = [r.text for r in self.dataset]

        total_steps = 2 * len(texts)
        logger.info("Running baseline (%s) on %d samples", self.baseline.name, len(texts))
        base_preds = self._predict_all(self.baseline, self.dataset, 0, total_steps)

        logger.info("Running candidate (%s) on %d samples", self.candidate.name, len(texts))
        cand_preds = self._predict_all(self.candidate, self.dataset, len(texts), total_steps)

        # Compute metrics for both policies
        policies = ["strict"]
        if self.config.include_lenient:
            policies.append("lenient")

        base_metrics = {}
        cand_metrics = {}
        base_slices = {}
        cand_slices = {}
        base_attack_slices = {}
        cand_attack_slices = {}

        # The attack slice family uses attack_family when the dataset provides it
        # (the agentic dataset), else attack_type (sample.csv). They coincide on
        # the agentic dataset where attack_type == attack_family.
        attack_dim = "attack_family" if any(r.attack_family for r in self.dataset) else "attack_type"

        for pol in policies:
            base_conf = compute_confusion(base_preds, self.dataset, pol)
            cand_conf = compute_confusion(cand_preds, self.dataset, pol)
            # Error results carry no meaningful latency; keep them out of percentiles.
            base_lats = [p.latency_ms for p in base_preds if p.prediction != "error"]
            cand_lats = [p.latency_ms for p in cand_preds if p.prediction != "error"]

            base_metrics[pol] = compute_metrics(base_conf, base_lats,
                                                count_hijacked(base_preds), count_errors(base_preds))
            cand_metrics[pol] = compute_metrics(cand_conf, cand_lats,
                                                count_hijacked(cand_preds), count_errors(cand_preds))
            base_slices[pol] = compute_slices(base_preds, self.dataset, pol, self.config.slices)
            cand_slices[pol] = compute_slices(cand_preds, self.dataset, pol, self.config.slices)
            base_attack_slices[pol] = compute_slices(base_preds, self.dataset, pol, [attack_dim])
            cand_attack_slices[pol] = compute_slices(cand_preds, self.dataset, pol, [attack_dim])

        # McNemar significance test on primary policy
        try:
            import scipy.stats  # noqa: F401  (availability check)
            _, mcnemar_p = mcnemar_test(base_preds, cand_preds, self.dataset, policy=self.config.policy)
        except ImportError:
            logger.warning("scipy not available; skipping McNemar test")
            mcnemar_p = None

        # Build per-sample results
        sample_results = []
        for pred_b, pred_c, rec in zip(base_preds, cand_preds, self.dataset):
            sample_results.append(
                SampleResult(
                    text=rec.text,
                    label=rec.label,
                    category=rec.category,
                    language=rec.language,
                    baseline_pred=pred_b.prediction,
                    candidate_pred=pred_c.prediction,
                    baseline_score=pred_b.score,
                    candidate_score=pred_c.score,
                    baseline_latency_ms=pred_b.latency_ms,
                    candidate_latency_ms=pred_c.latency_ms,
                    attack_type=rec.attack_type,
                    baseline_meta=dict(pred_b.metadata),
                    candidate_meta=dict(pred_c.metadata),
                )
            )

        # LLM-as-judge (optional)
        judge_agreement_rate = None
        if self.judge is not None:
            logger.info("Running judge on %d samples", len(texts))
            verdicts = []
            for pred_c, rec in zip(cand_preds, self.dataset):
                try:
                    verdict = self.judge.evaluate(rec.text, pred_c)
                    verdicts.append(verdict.agrees)
                    sample_results[len(verdicts) - 1].judge_verdict = (
                        "agree" if verdict.agrees else "disagree"
                    )
                except Exception as exc:  # noqa: BLE001 (intentional resilience boundary)
                    logger.warning("Judge failed on sample: %s", exc)
                    verdicts.append(None)
            valid = [v for v in verdicts if v is not None]
            if valid:
                judge_agreement_rate = round(sum(1 for v in valid if v) / len(valid), 4)

        return EvalResults(
            run_id=run_id,
            dataset_sha=dataset_sha,
            git_commit=git_commit,
            timestamp=timestamp,
            baseline_name=self.baseline.name,
            candidate_name=self.candidate.name,
            baseline_metrics=base_metrics,
            candidate_metrics=cand_metrics,
            baseline_slices=base_slices,
            candidate_slices=cand_slices,
            baseline_attack_slices=base_attack_slices,
            candidate_attack_slices=cand_attack_slices,
            sample_results=sample_results,
            mcnemar_p=mcnemar_p,
            judge_agreement_rate=judge_agreement_rate,
        )
