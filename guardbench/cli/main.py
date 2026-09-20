"""GuardBench CLI — compare guards, generate reports, run CI gates."""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import Optional

import click

logger = logging.getLogger(__name__)


def _get_store(store_path: Optional[str] = None):
    """Return a SQLiteStore at the given path (or default)."""
    from guardbench.store.sqlite import SQLiteStore
    return SQLiteStore(db_path=store_path)


def _load_gate_config(config_path: str):
    """Load a GateConfig from a JSON file.

    Supports both the new guardbench format (global_thresholds / slices) and the
    legacy format (defaults / overrides) for backward compatibility.
    """
    from guardbench.gate.schema import GateConfig
    p = Path(config_path)
    if not p.exists():
        raise click.ClickException(f"Gate config not found: {config_path}")
    raw = json.loads(p.read_text(encoding="utf-8"))
    # Backward compatibility: translate legacy format
    if "defaults" in raw and "global_thresholds" not in raw:
        d = raw["defaults"]
        raw = {
            "mode": raw.get("mode", "strict"),
            "on_failure": raw.get("on_failure", "block"),
            "global_thresholds": {
                "min_recall": d.get("min_recall", 0.55),
                "max_fpr": d.get("max_fpr", 0.05),
                "max_latency_p99_ms": d.get("max_p99_ms", 500),
                "min_f1": d.get("min_f1", 0.0),
            },
            "slices": {
                f"{ov['category']}/{ov['language']}": {
                    k: v for k, v in ov.items()
                    if k not in ("category", "language")
                    and k in ("min_recall", "max_fpr", "max_latency_p99_ms", "min_f1")
                }
                for ov in raw.get("overrides", [])
                if "category" in ov and "language" in ov
            },
        }
    return GateConfig.model_validate(raw)


@click.group()
@click.version_option()
def cli() -> None:
    """GuardBench — benchmark, compare, and gate your AI safety guards."""
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")


# ─────────────────────────────────────────────────────────────────────────────
# guardbench compare
# ─────────────────────────────────────────────────────────────────────────────

@cli.command()
@click.option("--baseline", default="regex", show_default=True, help="Guard name or dotted class path")
@click.option("--candidate", required=True, help="Guard name or dotted class path")
@click.option("--dataset", required=True, type=click.Path(exists=True), help="CSV or JSONL dataset path")
@click.option("--policy", default="strict", show_default=True, help="strict | lenient")
@click.option("--config", "cfg_path", default="config.yaml", show_default=True, help="config.yaml path")
@click.option("--store", "store_path", default=None, help="Override DB path")
def compare(
    baseline: str,
    candidate: str,
    dataset: str,
    policy: str,
    cfg_path: str,
    store_path: Optional[str],
) -> None:
    """Run a full evaluation comparing BASELINE vs CANDIDATE on DATASET."""
    from guardbench.core.registry import get_guard
    from guardbench.data.loader import load_dataset
    from guardbench.engine.evaluator import EvalConfig, Evaluator

    # Import built-in guards to trigger self-registration
    import guardbench.guards.regex_guard  # noqa: F401

    click.echo(f"Loading dataset: {dataset}")
    records = load_dataset(dataset)
    click.echo(f"  {len(records)} records loaded")

    click.echo(f"Instantiating guards: baseline={baseline!r}, candidate={candidate!r}")
    base_guard = _resolve_guard(baseline)
    cand_guard = _resolve_guard(candidate)

    config = EvalConfig(policy=policy)
    evaluator = Evaluator(base_guard, cand_guard, records, config)

    click.echo("Running evaluation …")
    results = evaluator.run()

    store = _get_store(store_path)
    store.save_run(results)

    strict = results.candidate_metrics.get("strict")
    click.echo(f"\nRun ID: {results.run_id}")
    if strict:
        click.echo(
            f"Candidate (strict) — recall: {strict.recall:.4f} | "
            f"fpr: {strict.fpr:.4f} | f1: {strict.f1:.4f} | "
            f"p99: {strict.latency_p99:.1f} ms"
        )
    click.echo(f"Dataset SHA: {results.dataset_sha[:12]}")


# ─────────────────────────────────────────────────────────────────────────────
# guardbench report
# ─────────────────────────────────────────────────────────────────────────────

@cli.command()
@click.option("--run", "run_id", default="latest", show_default=True, help="run_id or 'latest'")
@click.option("--compare", "compare_id", default=None, help="run_id to diff against")
@click.option("--format", "fmt", default="html", show_default=True, help="html | pdf")
@click.option("--output", "output_path", default=None, help="Output path (auto-named if omitted)")
@click.option("--open", "open_browser", is_flag=True, help="Open report in browser after building")
@click.option("--config", "cfg_path", default=None, help="gate.json path for threshold colour-coding")
@click.option("--store", "store_path", default=None, help="Override DB path")
def report(
    run_id: str,
    compare_id: Optional[str],
    fmt: str,
    output_path: Optional[str],
    open_browser: bool,
    cfg_path: Optional[str],
    store_path: Optional[str],
) -> None:
    """Generate an HTML (or PDF) report for a stored run."""
    from guardbench.report.generator import ReportGenerator

    store = _get_store(store_path)

    if run_id == "latest":
        results = store.latest_run()
        if results is None:
            raise click.ClickException("No runs found in store. Run 'guardbench compare' first.")
    else:
        results = store.get_run(run_id)

    gate_config = None
    if cfg_path:
        gate_config_obj = _load_gate_config(cfg_path)
        gate_config = gate_config_obj.model_dump()

    out = Path(output_path) if output_path else Path("report") / "index.html"
    generator = ReportGenerator(results, gate_config=gate_config)
    out = generator.build(out)
    click.echo(f"Report written to {out}")

    if open_browser:
        import webbrowser
        webbrowser.open(out.as_uri())

    # Auto-rebuild dashboard so it always reflects the latest run
    try:
        from guardbench.report.generator import DashboardGenerator
        dash = DashboardGenerator(store, gate_config=gate_config)
        dash_path = dash.build()
        click.echo(f"Dashboard updated at {dash_path}")
    except Exception as _dash_exc:
        logger.debug("Dashboard auto-build failed: %s", _dash_exc)


# ─────────────────────────────────────────────────────────────────────────────
# guardbench gate
# ─────────────────────────────────────────────────────────────────────────────

@cli.command()
@click.option("--config", "cfg_path", default="gate.json", show_default=True, help="gate.json path")
@click.option("--run", "run_id", default="latest", show_default=True, help="run_id or 'latest'")
@click.option("--compare", "compare_id", default=None, help="Compare against this run_id for regression")
@click.option("--output", "output_path", default="report/ci_summary.md", show_default=True, help="Output md path")
@click.option("--store", "store_path", default=None, help="Override DB path")
def gate(
    cfg_path: str,
    run_id: str,
    compare_id: Optional[str],
    output_path: str,
    store_path: Optional[str],
) -> None:
    """Run the CI gate check. Exits 0 on pass, 1 on failure."""
    from guardbench.gate.checker import GateChecker
    from guardbench.gate.summary import write_markdown_summary

    store = _get_store(store_path)

    if run_id == "latest":
        results = store.latest_run()
        if results is None:
            raise click.ClickException("No runs found in store. Run 'guardbench compare' first.")
    else:
        results = store.get_run(run_id)

    gate_config = _load_gate_config(cfg_path)
    checker = GateChecker(gate_config, store=store)
    check_result = checker.check(results)

    write_markdown_summary(check_result, results, gate_config, Path(output_path))
    click.echo(f"CI summary written to {output_path}")

    if check_result.passed:
        click.echo("CI Gate: PASSED")
        sys.exit(0)
    else:
        click.echo("CI Gate: FAILED")
        for f in check_result.failures:
            click.echo(f"  ❌ {f}")
        sys.exit(1)


# ─────────────────────────────────────────────────────────────────────────────
# guardbench runs
# ─────────────────────────────────────────────────────────────────────────────

@cli.group()
def runs() -> None:
    """Manage and inspect stored evaluation runs."""


@runs.command("list")
@click.option("--store", "store_path", default=None, help="Override DB path")
@click.option("--limit", default=20, show_default=True, help="Number of runs to show")
def runs_list(store_path: Optional[str], limit: int) -> None:
    """List recent evaluation runs."""
    store = _get_store(store_path)
    run_list = store.list_runs(limit=limit)
    if not run_list:
        click.echo("No runs found.")
        return
    click.echo(f"{'Run ID':<38} {'Timestamp':<22} {'Baseline':<12} {'Candidate':<12} {'Recall':<8} {'FPR'}")
    click.echo("-" * 110)
    for r in run_list:
        recall = f"{r['recall']:.4f}" if r.get("recall") is not None else "—"
        fpr = f"{r['fpr']:.4f}" if r.get("fpr") is not None else "—"
        click.echo(
            f"{r['run_id']:<38} {r.get('timestamp', '—'):<22} "
            f"{r.get('baseline', '—'):<12} {r.get('candidate', '—'):<12} "
            f"{recall:<8} {fpr}"
        )


@runs.command("show")
@click.argument("run_id")
@click.option("--store", "store_path", default=None, help="Override DB path")
def runs_show(run_id: str, store_path: Optional[str]) -> None:
    """Show full metrics for a specific run."""
    store = _get_store(store_path)
    results = store.get_run(run_id)
    click.echo(json.dumps(results.to_dict(), indent=2))


# ─────────────────────────────────────────────────────────────────────────────
# guardbench dataset
# ─────────────────────────────────────────────────────────────────────────────

@cli.group()
def dataset() -> None:
    """Dataset utilities: validate, stats, augment."""


@dataset.command("validate")
@click.option("--dataset", "dataset_path", required=True, type=click.Path(exists=True))
def dataset_validate(dataset_path: str) -> None:
    """Validate a CSV or JSONL dataset file."""
    from guardbench.data.loader import load_dataset
    records = load_dataset(dataset_path)
    click.echo(f"✅ Valid dataset: {len(records)} records in {dataset_path}")


@dataset.command("stats")
@click.option("--dataset", "dataset_path", required=True, type=click.Path(exists=True))
def dataset_stats(dataset_path: str) -> None:
    """Print statistics about a dataset."""
    from guardbench.data.loader import load_dataset
    from collections import Counter
    records = load_dataset(dataset_path)
    labels = Counter(r.label for r in records)
    categories = Counter(r.category for r in records)
    languages = Counter(r.language for r in records)
    click.echo(f"Total records: {len(records)}")
    click.echo(f"Labels:     {dict(labels)}")
    click.echo(f"Categories: {dict(categories)}")
    click.echo(f"Languages:  {dict(languages)}")


@dataset.command("augment")
@click.option("--dataset", "dataset_path", required=True, type=click.Path(exists=True))
@click.option("--output", "output_path", required=True)
@click.option("--techniques", default="leetspeak,obfuscation", show_default=True)
@click.option("--multiplier", default=2, show_default=True, type=int)
def dataset_augment(dataset_path: str, output_path: str, techniques: str, multiplier: int) -> None:
    """Augment a dataset with adversarial transformations."""
    import csv
    from guardbench.data.loader import load_dataset
    from guardbench.data.augmentor import augment_dataset
    records = load_dataset(dataset_path)
    tech_list = [t.strip() for t in techniques.split(",")]
    augmented = augment_dataset(records, techniques=tech_list, multiplier=multiplier)
    out = Path(output_path)
    with open(out, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["text", "label", "category", "language", "source", "attack_type"])
        writer.writeheader()
        for r in records + augmented:
            writer.writerow(r.model_dump())
    click.echo(f"Wrote {len(records)} original + {len(augmented)} augmented = {len(records)+len(augmented)} → {out}")


# ─────────────────────────────────────────────────────────────────────────────
# guardbench dashboard
# ─────────────────────────────────────────────────────────────────────────────

@cli.command()
@click.option("--output", "output_path", default=None, help="Output path (default: report/dashboard.html)")
@click.option("--gate", "cfg_path", default=None, help="gate.json path for pass/fail badges")
@click.option("--store", "store_path", default=None, help="Override DB path")
@click.option("--open/--no-open", "open_browser", default=False,
              help="Open dashboard in browser after building")
def dashboard(
    output_path: Optional[str],
    cfg_path: Optional[str],
    store_path: Optional[str],
    open_browser: bool,
) -> None:
    """Build an interactive multi-run dashboard and open it in the browser."""
    from guardbench.report.generator import DashboardGenerator

    store = _get_store(store_path)

    gate_config = None
    if cfg_path:
        gate_config = _load_gate_config(cfg_path).model_dump()

    out = Path(output_path) if output_path else None
    gen = DashboardGenerator(store, gate_config=gate_config)
    out = gen.build(out)
    click.echo(f"Dashboard written to {out}")

    if open_browser:
        import webbrowser
        webbrowser.open(out.as_uri())


# ─────────────────────────────────────────────────────────────────────────────
# guardbench init
# ─────────────────────────────────────────────────────────────────────────────

@cli.command()
def init() -> None:
    """Scaffold a new GuardBench project in the current directory."""
    import shutil
    from pathlib import Path

    # config.yaml
    if not Path("config.yaml").exists():
        Path("config.yaml").write_text(
            "dataset_path: ./dataset/sample.jsonl\n"
            "policy_version: v0.1\n"
            "engines:\n"
            "  baseline:\n"
            "    name: regex-baseline\n"
            "  candidate:\n"
            "    name: regex-enhanced\n",
            encoding="utf-8",
        )
        click.echo("Created config.yaml")

    # gate.json
    if not Path("gate.json").exists():
        Path("gate.json").write_text(
            json.dumps(
                {
                    "mode": "strict",
                    "global_thresholds": {
                        "min_recall": 0.55,
                        "max_fpr": 0.05,
                        "max_latency_p99_ms": 500,
                        "min_f1": 0.0,
                    },
                    "on_failure": "block",
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        click.echo("Created gate.json")

    # dataset/sample.jsonl
    dataset_dir = Path("dataset")
    dataset_dir.mkdir(exist_ok=True)
    target = dataset_dir / "sample.jsonl"
    if not target.exists():
        import importlib.resources
        try:
            with importlib.resources.path("guardbench.data.builtin", "sample_10.jsonl") as src:
                shutil.copy(str(src), str(target))
        except Exception:
            # Fallback: locate relative to this file
            src_path = Path(__file__).parent.parent / "data" / "builtin" / "sample_10.jsonl"
            if src_path.exists():
                shutil.copy(str(src_path), str(target))
        click.echo(f"Created {target}")

    click.echo("\nGuardBench initialized. Run:")
    click.echo("  guardbench compare --candidate regex --dataset dataset/sample.jsonl")


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _resolve_guard(name: str):
    """Resolve a guard by registry name or dotted class path."""
    # Import built-in guards first
    import guardbench.guards.regex_guard  # noqa: F401
    from guardbench.core.registry import get_guard, list_guards

    if "." in name:
        # Dotted module path: e.g. mypackage.guards.MyGuard
        parts = name.rsplit(".", 1)
        import importlib
        mod = importlib.import_module(parts[0])
        cls = getattr(mod, parts[1])
        return cls()
    return get_guard(name)
