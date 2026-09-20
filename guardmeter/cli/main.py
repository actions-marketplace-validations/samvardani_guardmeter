"""GuardMeter CLI — compare guards, generate reports, run CI gates."""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import click

if TYPE_CHECKING:
    from guardmeter.core.tryout import TryResult

logger = logging.getLogger(__name__)


def _get_store(store_path: str | None = None):
    """Return a SQLiteStore at the given path (or default)."""
    from guardmeter.store.sqlite import SQLiteStore
    return SQLiteStore(db_path=store_path)


def _import_builtin_guards() -> None:
    """Import all built-in guard modules so they self-register by name.

    Thin delegate to ``guardmeter.core.registry.import_builtin_guards`` — kept
    for backward compatibility with existing call sites and tests.
    """
    from guardmeter.core.registry import import_builtin_guards
    import_builtin_guards()


def _load_gate_config(config_path: str):
    """Load a GateConfig from a JSON file (legacy format supported).

    Thin click-aware wrapper over guardmeter.gate.config.load_gate_config.
    """
    from guardmeter.gate.config import load_gate_config
    try:
        return load_gate_config(config_path)
    except FileNotFoundError as exc:
        raise click.ClickException(str(exc)) from exc


@click.group()
@click.version_option()
def cli() -> None:
    """GuardMeter — benchmark, compare, and gate your AI safety guards."""
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")


# ─────────────────────────────────────────────────────────────────────────────
# guardmeter compare
# ─────────────────────────────────────────────────────────────────────────────

@cli.command()
@click.option("--baseline", default="regex", show_default=True, help="Guard name or dotted class path")
@click.option("--candidate", required=True, help="Guard name or dotted class path")
@click.option("--dataset", required=True, type=click.Path(exists=True), help="CSV or JSONL dataset path")
@click.option("--store", "store_path", default=None, help="Override DB path")
@click.option("--json", "json_out", is_flag=True, help="Print a JSON summary to stdout (human text goes to stderr)")
@click.option("--summary-md", "summary_md", default=None, help="Write a Markdown step-summary table to this path")
def compare(
    baseline: str,
    candidate: str,
    dataset: str,
    store_path: str | None,
    json_out: bool,
    summary_md: str | None,
) -> None:
    """Run a full evaluation comparing BASELINE vs CANDIDATE on DATASET."""
    from guardmeter.data.loader import load_dataset
    from guardmeter.engine.evaluator import EvalConfig, Evaluator

    # When --json is set, all human-readable text goes to stderr so stdout is pure JSON.
    def _log(msg: str) -> None:
        click.echo(msg, err=json_out)

    # Import built-in guards to trigger self-registration
    _import_builtin_guards()

    _log(f"Loading dataset: {dataset}")
    records = load_dataset(dataset)
    _log(f"  {len(records)} records loaded")

    _log(f"Instantiating guards: baseline={baseline!r}, candidate={candidate!r}")
    base_guard = _resolve_guard(baseline)
    cand_guard = _resolve_guard(candidate)

    # Both strict and lenient metrics are always computed; McNemar uses strict.
    config = EvalConfig()
    evaluator = Evaluator(base_guard, cand_guard, records, config)

    _log("Running evaluation …")
    results = evaluator.run()

    store = _get_store(store_path)
    store.save_run(results)

    if summary_md:
        from guardmeter.gate.summary import write_step_summary
        write_step_summary(Path(summary_md), results)
        _log(f"Step summary written to {summary_md}")

    strict = results.candidate_metrics.get("strict")
    _log(f"\nRun ID: {results.run_id}")
    if strict:
        line = (
            f"Candidate (strict) — recall: {strict.recall:.4f} | "
            f"fpr: {strict.fpr:.4f} | f1: {strict.f1:.4f} | "
            f"p99: {strict.latency_p99:.1f} ms"
        )
        if strict.hijacked:
            line += f" | hijacked: {strict.hijacked} ({strict.hijack_rate:.2%})"
        _log(line)
    _log(f"Dataset SHA: {results.dataset_sha[:12]}")

    if json_out:
        d = results.to_dict()
        payload = {
            "run_id": results.run_id,
            "baseline_name": results.baseline_name,
            "candidate_name": results.candidate_name,
            "dataset_sha": results.dataset_sha,
            "candidate_metrics": d["candidate_metrics"],
            "mcnemar_p": results.mcnemar_p,
        }
        click.echo(json.dumps(payload, indent=2))


# ─────────────────────────────────────────────────────────────────────────────
# guardmeter try
# ─────────────────────────────────────────────────────────────────────────────

@cli.command("try")
@click.argument("text_parts", nargs=-1)
@click.option("--guard", "guards", multiple=True,
              help="Guard name (repeatable); default: regex-baseline + regex-enhanced")
@click.option("--file", "file_path", default=None, help="Read text from a file ('-' for stdin)")
@click.option("--json", "json_out", is_flag=True, help="Print a JSON list of results to stdout")
def try_(text_parts: tuple[str, ...], guards: tuple[str, ...], file_path: str | None, json_out: bool) -> None:
    """Evaluate TEXT against one or more guards (informational; always exits 0)."""
    from guardmeter.core.tryout import run_try

    has_args = len(text_parts) > 0
    if has_args and file_path:
        raise click.UsageError("Provide either TEXT arguments or --file, not both.")
    if not has_args and not file_path:
        raise click.UsageError("Provide TEXT to evaluate, or --file PATH ('-' for stdin).")

    if file_path:
        if file_path == "-":
            text = sys.stdin.read()
        else:
            p = Path(file_path)
            if not p.exists():
                raise click.UsageError(f"File not found: {file_path}")
            text = p.read_text(encoding="utf-8")
    else:
        text = " ".join(text_parts)

    guard_names = list(guards) if guards else ["regex-baseline", "regex-enhanced"]

    try:
        results = run_try(text, guard_names)
    except ValueError as exc:
        raise click.UsageError(str(exc)) from exc

    if json_out:
        click.echo(json.dumps([r.to_dict() for r in results], indent=2))
        return

    _print_try_table(results)


def _fmt_latency(v: float) -> str:
    """Format latency, keeping sub-millisecond values readable."""
    if v < 10:
        return f"{v:.2f} ms"
    if v < 100:
        return f"{v:.1f} ms"
    return f"{round(v)} ms"


def _print_try_table(results: list[TryResult]) -> None:
    """Print an aligned Guard | Verdict | Score | Categories | Latency table."""
    headers = ("Guard", "Verdict", "Score", "Categories", "Latency")
    rows = []
    for r in results:
        verdict = "ERROR" if r.error else r.prediction.upper()
        score = "—" if r.score is None else f"{r.score:.2f}"
        cats = ", ".join(r.categories) if r.categories else "—"
        rows.append((r.guard, verdict, score, cats, _fmt_latency(r.latency_ms)))

    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(cell))

    def fmt(cells: tuple[str, ...]) -> str:
        return "  ".join(cell.ljust(widths[i]) for i, cell in enumerate(cells))

    click.echo(fmt(headers))
    click.echo("  ".join("-" * w for w in widths))
    for r, row in zip(results, rows):
        click.echo(fmt(row))
        if r.error:
            click.echo(f"    ERROR: {r.error}")


# ─────────────────────────────────────────────────────────────────────────────
# guardmeter serve
# ─────────────────────────────────────────────────────────────────────────────

@cli.command()
@click.option("--host", default="127.0.0.1", show_default=True, help="Interface to bind")
@click.option("--port", default=8765, show_default=True, type=int, help="Port to bind (0 = pick free)")
@click.option("--guard", "guards", multiple=True,
              help="Default guard to pre-check (repeatable); default: regex-baseline + regex-enhanced")
@click.option("--open", "open_browser", is_flag=True, help="Open the playground in a browser")
def serve(host: str, port: int, guards: tuple[str, ...], open_browser: bool) -> None:
    """Run a local playground: type text, pick guards, see verdicts live."""
    from guardmeter.serve.server import run_server

    default_guards = list(guards) if guards else ["regex-baseline", "regex-enhanced"]
    try:
        run_server(host=host, port=port, default_guards=default_guards, open_browser=open_browser)
    except RuntimeError as exc:
        raise click.ClickException(str(exc)) from exc


# ─────────────────────────────────────────────────────────────────────────────
# guardmeter report
# ─────────────────────────────────────────────────────────────────────────────

@cli.command()
@click.option("--run", "run_id", default="latest", show_default=True, help="run_id or 'latest'")
@click.option("--output", "output_path", default=None, help="Output path (auto-named if omitted)")
@click.option("--open", "open_browser", is_flag=True, help="Open report in browser after building")
@click.option("--config", "cfg_path", default=None, help="gate.json path for threshold colour-coding")
@click.option("--store", "store_path", default=None, help="Override DB path")
def report(
    run_id: str,
    output_path: str | None,
    open_browser: bool,
    cfg_path: str | None,
    store_path: str | None,
) -> None:
    """Generate an HTML report for a stored run."""
    from guardmeter.report.generator import ReportGenerator

    store = _get_store(store_path)

    if run_id == "latest":
        results = store.latest_run()
        if results is None:
            raise click.ClickException("No runs found in store. Run 'guardmeter compare' first.")
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

    # Auto-rebuild the dashboard snapshot so it always reflects the latest run
    try:
        from guardmeter.serve.snapshot import build_snapshot
        dash_path = out.parent / "dashboard.html"
        dash_path.write_text(build_snapshot(store), encoding="utf-8")
        click.echo(f"Dashboard snapshot updated at {dash_path}")
    except Exception as _dash_exc:  # noqa: BLE001 (intentional resilience boundary)
        logger.debug("Dashboard auto-build failed: %s", _dash_exc)

    # Integrity manifest over the generated HTML
    from guardmeter.report.manifest import write_manifest
    mpath = write_manifest(
        out.parent,
        run_id=results.run_id,
        dataset_sha=results.dataset_sha,
        git_commit=results.git_commit,
    )
    click.echo(f"Integrity manifest written to {mpath}")


# ─────────────────────────────────────────────────────────────────────────────
# guardmeter gate
# ─────────────────────────────────────────────────────────────────────────────

@cli.command()
@click.option("--config", "cfg_path", default="gate.json", show_default=True, help="gate.json path")
@click.option("--run", "run_id", default="latest", show_default=True, help="run_id or 'latest'")
@click.option("--output", "output_path", default="report/ci_summary.md", show_default=True, help="Output md path")
@click.option("--store", "store_path", default=None, help="Override DB path")
@click.option("--json", "json_out", is_flag=True, help="Print a JSON result to stdout (human text goes to stderr)")
@click.option("--summary-md", "summary_md", default=None, help="Write a Markdown step-summary table to this path")
@click.option("--junit", "junit_path", default=None, help="Write JUnit XML (one testcase per checked scope×metric)")
@click.option("--webhook", "webhook_url", default=None,
              help="POST JSON to this URL on failure (else $GUARDMETER_WEBHOOK_URL)")
@click.option("--report-url", "report_url", default=None, help="Report URL to include in the webhook payload")
def gate(
    cfg_path: str,
    run_id: str,
    output_path: str,
    store_path: str | None,
    json_out: bool,
    summary_md: str | None,
    junit_path: str | None,
    webhook_url: str | None,
    report_url: str | None,
) -> None:
    """Run the CI gate check. Exits 0 on pass, 1 on failure."""
    import os

    from guardmeter.gate.checker import GateChecker
    from guardmeter.gate.summary import (
        write_junit,
        write_markdown_summary,
        write_step_summary,
    )

    # When --json is set, all human-readable text goes to stderr so stdout is pure JSON.
    def _log(msg: str) -> None:
        click.echo(msg, err=json_out)

    store = _get_store(store_path)

    if run_id == "latest":
        results = store.latest_run()
        if results is None:
            raise click.ClickException("No runs found in store. Run 'guardmeter compare' first.")
    else:
        results = store.get_run(run_id)

    gate_config = _load_gate_config(cfg_path)
    checker = GateChecker(gate_config, store=store)
    check_result = checker.check(results)

    write_markdown_summary(check_result, results, gate_config, Path(output_path))
    _log(f"CI summary written to {output_path}")

    if summary_md:
        write_step_summary(Path(summary_md), results, config=gate_config, check_result=check_result)
        _log(f"Step summary written to {summary_md}")

    if junit_path:
        write_junit(Path(junit_path), check_result)
        _log(f"JUnit XML written to {junit_path}")

    hook = webhook_url or os.environ.get("GUARDMETER_WEBHOOK_URL")
    if hook and not check_result.passed:
        from guardmeter.gate.webhook import notify_webhook
        ok = notify_webhook(hook, {
            "passed": check_result.passed,
            "run_id": results.run_id,
            "failures": [f.to_dict() for f in check_result.structured_failures],
            "report_url": report_url,
            "dataset_sha": results.dataset_sha,
        })
        _log(f"Webhook {'delivered' if ok else 'failed'}")

    if json_out:
        payload = {
            "passed": check_result.passed,
            "failures": [f.to_dict() for f in check_result.structured_failures],
            "run_id": results.run_id,
        }
        click.echo(json.dumps(payload, indent=2))

    if check_result.passed:
        _log("CI Gate: PASSED")
        sys.exit(0)
    else:
        _log("CI Gate: FAILED")
        for f in check_result.failures:
            _log(f"  ❌ {f}")
        sys.exit(1)


# ─────────────────────────────────────────────────────────────────────────────
# guardmeter runs
# ─────────────────────────────────────────────────────────────────────────────

@cli.group()
def runs() -> None:
    """Manage and inspect stored evaluation runs."""


@runs.command("list")
@click.option("--store", "store_path", default=None, help="Override DB path")
@click.option("--limit", default=20, show_default=True, help="Number of runs to show")
def runs_list(store_path: str | None, limit: int) -> None:
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
def runs_show(run_id: str, store_path: str | None) -> None:
    """Show full metrics for a specific run."""
    store = _get_store(store_path)
    results = store.get_run(run_id)
    click.echo(json.dumps(results.to_dict(), indent=2))


# ─────────────────────────────────────────────────────────────────────────────
# guardmeter dataset
# ─────────────────────────────────────────────────────────────────────────────

@cli.group()
def dataset() -> None:
    """Dataset utilities: validate, stats, augment."""


@dataset.command("validate")
@click.argument("path", type=click.Path(exists=True))
def dataset_validate(path: str) -> None:
    """Validate a dataset (schema, duplicates, near-duplicates, language, decoded).

    Exits 1 on any problem. Rows without an attack_family (e.g. sample.csv) skip
    the family-specific checks.
    """
    from guardmeter.data.loader import load_dataset
    from guardmeter.data.validate import dataset_stats, validate_records

    records = load_dataset(path)
    problems = validate_records(records)
    st = dataset_stats(records)
    click.echo(f"Dataset: {path}")
    click.echo(f"  rows={st['total']} languages={st['languages']} labels={st['labels']}")
    click.echo(f"  families={st['families']}")
    if not problems:
        click.echo(f"✅ Valid: {st['total']} rows, no problems.")
        return
    click.echo(f"❌ {len(problems)} problem(s) found (showing first 20):")
    for p in problems[:20]:
        click.echo(f"  - {p}")
    sys.exit(1)


@dataset.command("stats")
@click.argument("path", type=click.Path(exists=True))
@click.option("--markdown", "as_markdown", is_flag=True, help="Emit the composition table as Markdown")
def dataset_stats_cmd(path: str, as_markdown: bool) -> None:
    """Print dataset statistics; --markdown emits the composition table."""
    from guardmeter.data.loader import load_dataset
    from guardmeter.data.validate import dataset_stats, stats_markdown

    records = load_dataset(path)
    if as_markdown:
        click.echo(stats_markdown(records))
        return
    st = dataset_stats(records)
    click.echo(f"Total records: {st['total']}")
    click.echo(f"Labels:     {st['labels']}")
    click.echo(f"Languages:  {st['languages']}")
    click.echo(f"Families:   {st['families']}")
    click.echo(f"With context: {st['with_context']}")
    click.echo(f"Text length p50/p90/p99: {st['text_len_p50']}/{st['text_len_p90']}/{st['text_len_p99']}")


@dataset.command("info")
@click.argument("path", type=click.Path(exists=True))
def dataset_info(path: str) -> None:
    """Print row count, sha256, families, and card version for a dataset."""
    from guardmeter.data.validate import dataset_info as _info
    info = _info(path)
    click.echo(f"path:     {info['path']}")
    click.echo(f"version:  {info['version']}")
    click.echo(f"rows:     {info['rows']}")
    click.echo(f"sha256:   {info['sha256']}")
    click.echo(f"families: {', '.join(info['families'])}")


@dataset.command("augment")
@click.option("--dataset", "dataset_path", required=True, type=click.Path(exists=True))
@click.option("--output", "output_path", required=True)
@click.option("--techniques", default="leetspeak,obfuscation", show_default=True)
@click.option("--multiplier", default=2, show_default=True, type=int)
def dataset_augment(dataset_path: str, output_path: str, techniques: str, multiplier: int) -> None:
    """Augment a dataset with adversarial transformations."""
    import csv

    from guardmeter.data.augmentor import augment_dataset
    from guardmeter.data.loader import load_dataset
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


@dataset.command("fetch")
@click.argument("name")
@click.option("--dest", default=".", show_default=True, help="Root directory to write the dataset under")
def dataset_fetch(name: str, dest: str) -> None:
    """Download a repo-artifact dataset (e.g. agentic-v1) from GitHub release assets.

    Verifies the data file against a sha256 baked into the package before writing.
    """
    from guardmeter.data.fetch import RELEASES, fetch_dataset

    if name not in RELEASES:
        raise click.BadParameter(f"Unknown dataset '{name}'. Known: {', '.join(sorted(RELEASES))}")
    click.echo(f"Fetching {name} (release {RELEASES[name].tag}) …")
    try:
        paths = fetch_dataset(name, dest)
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc
    for p in paths:
        click.echo(f"  ✓ {p}")
    click.echo(f"✅ Fetched {len(paths)} file(s), sha256 verified.")


# ─────────────────────────────────────────────────────────────────────────────
# guardmeter dashboard
# ─────────────────────────────────────────────────────────────────────────────

@cli.command()
@click.option("--output", "output_path", default=None, help="Output path (default: report/dashboard.html)")
@click.option("--gate", "cfg_path", default=None, help="gate.json path for pass/fail badges")
@click.option("--store", "store_path", default=None, help="Override DB path")
@click.option("--open/--no-open", "open_browser", default=False,
              help="Open dashboard in browser after building")
def dashboard(
    output_path: str | None,
    cfg_path: str | None,
    store_path: str | None,
    open_browser: bool,
) -> None:
    """Export the read-only, self-contained dashboard snapshot (single HTML file)."""
    from guardmeter.serve.snapshot import build_snapshot

    store = _get_store(store_path)
    # cfg_path is accepted for backwards compatibility; the snapshot reads the
    # gate policy from ./gate.json so its Gate column matches the live app.
    _ = cfg_path

    out = Path(output_path) if output_path else Path("report") / "dashboard.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(build_snapshot(store), encoding="utf-8")
    click.echo(f"Dashboard snapshot written to {out}")

    latest = store.latest_run()
    from guardmeter.report.manifest import write_manifest
    write_manifest(
        out.parent,
        run_id=latest.run_id if latest else None,
        dataset_sha=latest.dataset_sha if latest else None,
        git_commit=latest.git_commit if latest else None,
    )

    if open_browser:
        import webbrowser
        webbrowser.open(out.as_uri())


# ─────────────────────────────────────────────────────────────────────────────
# guardmeter verify-report
# ─────────────────────────────────────────────────────────────────────────────

@cli.command("verify-report")
@click.argument("report_dir", default="report", required=False)
def verify_report(report_dir: str) -> None:
    """Recompute report hashes against MANIFEST.json; exit 1 on any mismatch."""
    from guardmeter.report.manifest import verify_manifest

    ok, problems = verify_manifest(report_dir)
    if ok:
        click.echo(f"✅ Report integrity verified: {report_dir}")
        return
    click.echo(f"❌ Report integrity check FAILED for {report_dir}:")
    for p in problems:
        click.echo(f"  - {p}")
    sys.exit(1)


# ─────────────────────────────────────────────────────────────────────────────
# guardmeter init
# ─────────────────────────────────────────────────────────────────────────────

@cli.command()
def init() -> None:
    """Scaffold a new GuardMeter project in the current directory."""
    import shutil
    from pathlib import Path

    # gate.json
    if not Path("gate.json").exists():
        Path("gate.json").write_text(
            json.dumps(
                {
                    "mode": "strict",
                    "global_thresholds": {
                        "min_recall": 0.55,
                        "min_f1": 0.80,
                        "max_fpr": 0.01,
                        "max_latency_p99_ms": 20,
                    },
                    # Per-slice overrides calibrated for the built-in regex demo guard
                    # so the quick-start gate passes; tighten/remove for your own guard.
                    "slices": {
                        "self_harm/en": {"min_recall": 0.44, "min_f1": 0.60},
                        "crime/en": {"min_recall": 0.44, "min_f1": 0.60},
                        "malware/en": {"min_recall": 0.44},
                        "pii/en": {"min_f1": 0.65},
                    },
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        click.echo("Created gate.json")

    # dataset/sample.csv — matches every README example
    dataset_dir = Path("dataset")
    dataset_dir.mkdir(exist_ok=True)
    target = dataset_dir / "sample.csv"
    if not target.exists():
        import importlib.resources
        try:
            with importlib.resources.path("guardmeter.data.builtin", "sample.csv") as src:
                shutil.copy(str(src), str(target))
        except Exception:  # noqa: BLE001 (intentional resilience boundary)
            # Fallback: locate relative to this file
            src_path = Path(__file__).parent.parent / "data" / "builtin" / "sample.csv"
            if src_path.exists():
                shutil.copy(str(src_path), str(target))
        click.echo(f"Created {target}")

    click.echo("\nGuardMeter initialized. Run:")
    click.echo(
        "  guardmeter compare --baseline regex-baseline --candidate regex-enhanced "
        "--dataset dataset/sample.csv"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _resolve_guard(name: str):
    """Resolve a guard by registry name or dotted class path."""
    # Import built-in guards first
    _import_builtin_guards()
    from guardmeter.core.registry import get_guard

    if "." in name:
        # Dotted module path: e.g. mypackage.guards.MyGuard
        parts = name.rsplit(".", 1)
        import importlib
        mod = importlib.import_module(parts[0])
        cls = getattr(mod, parts[1])
        return cls()
    return get_guard(name)
