"""HTML report generator for EvalResults, plus multi-run DashboardGenerator."""

from __future__ import annotations

import datetime
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from jinja2 import Environment, PackageLoader

from guardbench import __version__
from guardbench.engine.metrics import MetricsBundle
from guardbench.engine.results import EvalResults
from guardbench.report.charts import threshold_sweep_data
from guardbench.store.base import RunStore

logger = logging.getLogger(__name__)

_DEFAULT_GATE = {
    "global_thresholds": {"min_recall": 0.55, "max_fpr": 0.05}
}


def _slice_row(key: tuple, bundle: MetricsBundle, gate_config: Optional[dict]) -> dict:
    """Convert a slice key + MetricsBundle into a template-friendly dict."""
    cat = key[0] if len(key) > 0 else "?"
    lang = key[1] if len(key) > 1 else "?"
    n = bundle.tp + bundle.fp + bundle.tn + bundle.fn

    # Colour coding based on gate thresholds
    thresholds = {}
    if gate_config:
        thresholds = gate_config.get("global_thresholds", {})
    min_recall = thresholds.get("min_recall", 0.0)
    max_fpr = thresholds.get("max_fpr", 1.0)

    recall_class = ""
    if gate_config:
        recall_class = "pass-cell" if bundle.recall >= min_recall else "fail-cell"
    fpr_class = ""
    if gate_config:
        fpr_class = "pass-cell" if bundle.fpr <= max_fpr else "fail-cell"

    return {
        "category": cat,
        "language": lang,
        "n": n,
        "recall": bundle.recall,
        "recall_lo": bundle.recall_lo,
        "recall_hi": bundle.recall_hi,
        "fpr": bundle.fpr,
        "fpr_lo": bundle.fpr_lo,
        "fpr_hi": bundle.fpr_hi,
        "fnr": bundle.fnr,
        "recall_class": recall_class,
        "fpr_class": fpr_class,
    }


class ReportGenerator:
    """Renders an EvalResults object to an interactive HTML report."""

    def __init__(self, results: EvalResults, gate_config: Optional[dict] = None) -> None:
        """Initialise with evaluation results and optional gate config for colour coding."""
        self.results = results
        self.gate_config = gate_config

    def build(self, output_path: Optional[Path] = None) -> Path:
        """Render the HTML report and write it to output_path.

        Returns the path of the written file.
        """
        if output_path is None:
            output_path = Path("report") / "index.html"

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        env = Environment(loader=PackageLoader("guardbench.report", "templates"))
        template = env.get_template("report.html")

        results = self.results
        gate = self.gate_config

        # Extract metrics bundles
        strict_base = results.baseline_metrics.get("strict", MetricsBundle())
        strict_cand = results.candidate_metrics.get("strict", MetricsBundle())
        lenient_base = results.baseline_metrics.get("lenient", MetricsBundle())
        lenient_cand = results.candidate_metrics.get("lenient", MetricsBundle())

        # Slice rows sorted by category, language
        def _slice_rows(slices_dict: Dict) -> List[dict]:
            rows = []
            for key in sorted(slices_dict.keys(), key=lambda k: (str(k[0]), str(k[1]) if len(k) > 1 else "")):
                rows.append(_slice_row(key, slices_dict[key], gate))
            return rows

        strict_base_slices = _slice_rows(results.baseline_slices.get("strict", {}))
        strict_cand_slices = _slice_rows(results.candidate_slices.get("strict", {}))

        # Latency arrays for Chart.js: real per-sample latencies (one value per sample)
        base_latencies = [s.baseline_latency_ms for s in results.sample_results]
        cand_latencies = [s.candidate_latency_ms for s in results.sample_results]

        sweep = threshold_sweep_data(results)

        has_judge = any(s.judge_verdict is not None for s in results.sample_results)

        html = template.render(
            run_id=results.run_id,
            total_samples=len(results.sample_results),
            dataset_sha=results.dataset_sha,
            git_commit=results.git_commit,
            generated_at=datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            baseline_name=results.baseline_name,
            candidate_name=results.candidate_name,
            mcnemar_p=results.mcnemar_p,
            version=__version__,
            strict_base=strict_base,
            strict_cand=strict_cand,
            lenient_base=lenient_base,
            lenient_cand=lenient_cand,
            strict_base_slices=strict_base_slices,
            strict_cand_slices=strict_cand_slices,
            sample_results=results.sample_results[:200],  # cap at 200 for performance
            has_judge=has_judge,
            base_latencies_json=json.dumps(base_latencies),
            cand_latencies_json=json.dumps(cand_latencies),
            sweep_data=bool(sweep),
            sweep_data_json=json.dumps(sweep),
        )

        output_path.write_text(html, encoding="utf-8")
        logger.info("Report written to %s", output_path)
        return output_path


class DashboardGenerator:
    """Renders an interactive multi-run HTML dashboard from a RunStore."""

    def __init__(self, store: RunStore, gate_config: Optional[dict] = None) -> None:
        self.store = store
        self.gate_config = gate_config

    def build(self, output_path: Optional[Path] = None) -> Path:
        """Serialise all runs from the store and write dashboard.html."""
        if output_path is None:
            output_path = Path("report") / "dashboard.html"

        output_path = Path(output_path).resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)

        summaries = self.store.list_runs(limit=100)
        runs_data: List[dict] = []
        for summary in summaries:
            run_id = summary.get("run_id")
            if not run_id:
                continue
            try:
                results = self.store.get_run(run_id)
                runs_data.append(self._serialize_run(results))
            except Exception as exc:
                logger.warning("Dashboard: failed to load run %s: %s", run_id, exc)

        env = Environment(loader=PackageLoader("guardbench.report", "templates"))
        template = env.get_template("dashboard.html")
        html = template.render(
            runs_json=json.dumps(runs_data),
            generated_at=datetime.datetime.now(datetime.timezone.utc).strftime(
                "%Y-%m-%d %H:%M UTC"
            ),
        )
        output_path.write_text(html, encoding="utf-8")
        logger.info("Dashboard written to %s", output_path)
        return output_path

    def _serialize_run(self, results: EvalResults) -> dict:
        strict_base = results.baseline_metrics.get("strict", MetricsBundle())
        strict_cand = results.candidate_metrics.get("strict", MetricsBundle())
        lenient_base = results.baseline_metrics.get("lenient", MetricsBundle())
        lenient_cand = results.candidate_metrics.get("lenient", MetricsBundle())

        def bundle_dict(b: MetricsBundle) -> dict:
            return {
                "recall": b.recall, "recall_lo": b.recall_lo, "recall_hi": b.recall_hi,
                "precision": b.precision, "f1": b.f1,
                "fpr": b.fpr, "fpr_lo": b.fpr_lo, "fpr_hi": b.fpr_hi,
                "fnr": b.fnr,
                "tp": b.tp, "fp": b.fp, "tn": b.tn, "fn": b.fn,
                "latency_p50": b.latency_p50, "latency_p90": b.latency_p90,
                "latency_p99": b.latency_p99,
            }

        def slices_list(slices_dict: Dict[Tuple, MetricsBundle]) -> List[dict]:
            rows = []
            for key in sorted(
                slices_dict.keys(),
                key=lambda k: (str(k[0]), str(k[1]) if len(k) > 1 else ""),
            ):
                b = slices_dict[key]
                rows.append({
                    "category": key[0] if len(key) > 0 else "?",
                    "language": key[1] if len(key) > 1 else "?",
                    "n": b.tp + b.fp + b.tn + b.fn,
                    "recall": b.recall,
                    "fpr": b.fpr,
                })
            return rows

        try:
            dt = datetime.datetime.fromisoformat(results.timestamp.replace("Z", "+00:00"))
            date_str = dt.strftime("%Y-%m-%d %H:%M UTC")
        except Exception:
            date_str = results.timestamp

        gate_pass = None
        if self.gate_config:
            gt = self.gate_config.get("global_thresholds", {})
            min_recall = gt.get("min_recall", 0.0)
            max_fpr = gt.get("max_fpr", 1.0)
            min_f1 = gt.get("min_f1", 0.0)
            gate_pass = bool(
                strict_cand.recall >= min_recall
                and strict_cand.fpr <= max_fpr
                and (min_f1 == 0.0 or strict_cand.f1 >= min_f1)
            )

        return {
            "run_id": results.run_id,
            "date": date_str,
            "baseline_name": results.baseline_name,
            "candidate_name": results.candidate_name,
            "mcnemar_p": results.mcnemar_p,
            "gate_pass": gate_pass,
            "strict": {
                "baseline": bundle_dict(strict_base),
                "candidate": bundle_dict(strict_cand),
                "baseline_slices": slices_list(results.baseline_slices.get("strict", {})),
                "candidate_slices": slices_list(results.candidate_slices.get("strict", {})),
            },
            "lenient": {
                "baseline": bundle_dict(lenient_base),
                "candidate": bundle_dict(lenient_cand),
            },
            "sample_results": [
                {
                    "text": s.text[:200],
                    "label": s.label,
                    "category": s.category,
                    "language": s.language,
                    "baseline_pred": s.baseline_pred,
                    "candidate_pred": s.candidate_pred,
                }
                for s in results.sample_results[:200]
            ],
        }
