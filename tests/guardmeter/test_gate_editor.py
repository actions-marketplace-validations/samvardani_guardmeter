"""Round-trip test for the gate editor: load → edit → save must not drop fields.

Regression guard for the 0.6.0 editor, which only exposed recall+fpr and could
silently discard min_f1 on a loaded gate.json.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from guardmeter.gate.config import parse_gate_config

_ROOT = Path(__file__).parent.parent.parent
_GATE_JSON = _ROOT / "gate.json"
_GATEMODEL = _ROOT / "guardmeter" / "serve" / "static" / "components" / "gatemodel.js"


def test_shipped_gate_survives_editor_round_trip():
    node = shutil.which("node")
    if node is None:
        pytest.skip("node not available")

    raw = json.loads(_GATE_JSON.read_text(encoding="utf-8"))
    # What the server hands the editor: parsed config with all fields (nulls for unset).
    loaded = parse_gate_config(raw).model_dump()

    script = (
        f'import {{ serializeGate }} from "file://{_GATEMODEL}";\n'
        f"process.stdout.write(JSON.stringify(serializeGate({json.dumps(loaded)})));"
    )
    result = subprocess.run([node, "--input-type=module", "-e", script],
                            capture_output=True, text=True, timeout=30, check=False)
    assert result.returncode == 0, result.stderr
    out = json.loads(result.stdout)

    # Every threshold in the shipped file — including min_f1 — round-trips intact.
    assert out["slices"] == raw["slices"]
    assert out["global_thresholds"] == raw["global_thresholds"]
    assert out["slices"]["self_harm/en"]["min_f1"] == raw["slices"]["self_harm/en"]["min_f1"]
