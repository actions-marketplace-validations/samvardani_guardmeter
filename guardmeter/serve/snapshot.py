"""Build a single self-contained HTML snapshot of the app (offline, read-only).

Everything is inlined: styles, Chart.js, every app module (via an import map of
data: URLs), and a JSON blob of runs/details/gate/datasets. Opened from disk it
renders with no network and no server; window.__SNAPSHOT__ flips the app into
read-only mode.
"""

from __future__ import annotations

import base64
import datetime
import importlib.resources
import json
from pathlib import Path
from typing import Any

from guardmeter.serve import api as serve_api


def _static_dir() -> Path:
    return Path(str(importlib.resources.files("guardmeter.serve"))) / "static"


def _js_safe(obj: Any) -> str:
    """JSON safe to embed inside an inline <script> (no </script> breakout)."""
    return (
        json.dumps(obj)
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
    )


def _gather_data(store: Any) -> dict[str, Any]:
    from guardmeter.core.registry import list_guards

    runs = serve_api.runs_payload(store, limit=200)
    detail: dict[str, Any] = {}
    for r in runs:
        try:
            detail[r["run_id"]] = store.get_run(r["run_id"]).to_dict()
        except KeyError:
            continue

    gate = serve_api.current_gate_config()
    datasets = serve_api.datasets_list()
    stats = {d["name"]: serve_api.dataset_stats(d["name"]) for d in datasets}
    rows = {d["name"]: (serve_api.dataset_rows(d["name"], limit=100000) or {}).get("rows", []) for d in datasets}

    scenario_runs: list[dict[str, Any]] = []
    scenario_detail: dict[str, Any] = {}
    if hasattr(store, "list_scenario_runs"):
        scenario_runs = store.list_scenario_runs(limit=200)
        for sr in scenario_runs:
            try:
                scenario_detail[sr["run_id"]] = store.get_scenario_run(sr["run_id"])
            except KeyError:
                continue

    return {
        "runs": runs,
        "runDetail": detail,
        "guardsInfo": {"guards": list_guards(), "default": ["regex-baseline", "regex-enhanced"]},
        "gate": gate.model_dump() if gate else {},
        "datasets": datasets,
        "datasetStats": stats,
        "datasetRows": rows,
        "scenarioRuns": scenario_runs,
        "scenarioDetail": scenario_detail,
    }


def build_snapshot(store: Any) -> str:
    """Return a single self-contained HTML document embedding the app + data."""
    static = _static_dir()
    styles = (static / "styles.css").read_text(encoding="utf-8")
    chartjs = (
        importlib.resources.files("guardmeter.report") / "static" / "chart.umd.min.js"
    ).read_text(encoding="utf-8")

    # Import map: every app JS module → a data: URL (base64). We rewrite the
    # source's "/static/…" imports to a bare "gmmod/…" specifier: path-absolute
    # specifiers can't be resolved from within a data: URL module (data: is not
    # a valid base), whereas bare specifiers resolve purely via the import map.
    # chart.umd is a classic script (window.Chart), so it is excluded here.
    prefix = "gmmod/"
    imports: dict[str, str] = {}
    for path in sorted(static.rglob("*.js")):
        rel = path.relative_to(static).as_posix()
        if rel == "chart.umd.min.js":
            continue
        src = path.read_text(encoding="utf-8").replace('"/static/', '"' + prefix).replace("'/static/", "'" + prefix)
        b64 = base64.b64encode(src.encode("utf-8")).decode("ascii")
        imports[f"{prefix}{rel}"] = f"data:text/javascript;base64,{b64}"

    data = _gather_data(store)
    generated_at = datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%d %H:%M UTC")

    return f"""<!doctype html>
<html lang="en" data-theme="dark">
<head>
<meta charset="utf-8">
<title>GuardMeter — snapshot</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>{styles}</style>
<script>{chartjs}</script>
<script>
window.__SNAPSHOT__ = true;
window.__SNAPSHOT_AT__ = {_js_safe(generated_at)};
window.__SNAPSHOT_DATA__ = {_js_safe(data)};
</script>
<script type="importmap">{_js_safe({"imports": imports})}</script>
</head>
<body>
<div id="app" aria-live="polite"></div>
<div class="toasts" id="toasts"></div>
<script type="module">import "gmmod/app.js";</script>
</body>
</html>
"""
