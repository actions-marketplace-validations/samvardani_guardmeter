"""Click-free loading/parsing of gate configuration (shared by CLI and server)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from guardmeter.gate.schema import GateConfig


def parse_gate_config(raw: dict[str, Any]) -> GateConfig:
    """Validate a gate config dict, translating the legacy defaults/overrides format."""
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


def load_gate_config(config_path: str | Path) -> GateConfig:
    """Load and parse a gate config from a JSON file. Raises FileNotFoundError/ValueError."""
    p = Path(config_path)
    if not p.exists():
        raise FileNotFoundError(f"Gate config not found: {config_path}")
    return parse_gate_config(json.loads(p.read_text(encoding="utf-8")))
