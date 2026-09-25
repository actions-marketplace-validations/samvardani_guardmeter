"""Load and validate a scenario suite from YAML, JSON, or JSONL."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from guardmeter.scenarios.schema import Scenario, Suite, SuiteMeta, parse_assertion


def _read_raw(path: Path) -> dict[str, Any]:
    """Return a ``{"suite": {...}, "scenarios": [...]}`` dict from any format."""
    text = path.read_text(encoding="utf-8")
    suffix = path.suffix.lower()
    if suffix in (".yaml", ".yml"):
        import yaml
        data = yaml.safe_load(text)
        if not isinstance(data, dict):
            raise ValueError("suite YAML must be a mapping with 'suite' and 'scenarios'")
        return data
    if suffix == ".jsonl":
        objs = [json.loads(line) for line in text.splitlines() if line.strip()]
        if not objs:
            raise ValueError("empty JSONL suite")
        first = objs[0]
        if "suite" in first:  # {"suite": {...}} header line
            return {"suite": first["suite"], "scenarios": objs[1:]}
        return {"suite": first, "scenarios": objs[1:]}  # header is the bare meta
    # .json (or anything else): a single object
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("suite JSON must be an object with 'suite' and 'scenarios'")  # noqa: TRY004
    return data


def load_suite(path: str | Path) -> Suite:
    """Load, normalise, and validate a suite. Raises on any schema error."""
    path = Path(path)
    raw = _read_raw(path)
    if "suite" not in raw:
        raise ValueError("suite file missing the 'suite' metadata block")

    scenarios: list[Scenario] = []
    for i, sc in enumerate(raw.get("scenarios") or []):
        sc = dict(sc)
        try:
            sc["expect"] = [parse_assertion(a) for a in (sc.get("expect") or [])]
            scenarios.append(Scenario.model_validate(sc))
        except Exception as exc:
            sid = sc.get("id", f"#{i}")
            raise ValueError(f"scenario {sid}: {exc}") from exc

    return Suite(suite=SuiteMeta.model_validate(raw["suite"]), scenarios=scenarios)
