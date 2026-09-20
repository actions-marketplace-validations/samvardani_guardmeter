"""Regression test for the Try-page history model (0.5.0 'history stayed hidden' bug).

jsdom isn't available, so this exercises the pure history model with Node and
asserts two evaluations produce two entries — the value the Try page renders
declaratively (so the wrapper can't get stuck hidden).
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

_HISTORY = Path(__file__).parent.parent.parent / "guardmeter" / "serve" / "static" / "components" / "history.js"


def test_push_history_accumulates_two_entries():
    node = shutil.which("node")
    if node is None:
        pytest.skip("node not available")
    script = f"""
    import {{ pushHistory }} from "file://{_HISTORY}";
    let h = [];
    h = pushHistory(h, {{ text: "first" }});
    h = pushHistory(h, {{ text: "second" }});
    if (h.length !== 2) {{ console.error("expected 2, got " + h.length); process.exit(1); }}
    if (h[0].text !== "second") {{ console.error("newest not first"); process.exit(1); }}
    // cap at 20
    let big = [];
    for (let i = 0; i < 25; i++) big = pushHistory(big, {{ text: String(i) }});
    if (big.length !== 20) {{ console.error("cap failed: " + big.length); process.exit(1); }}
    console.log("OK");
    """
    result = subprocess.run([node, "--input-type=module", "-e", script],
                            capture_output=True, text=True, timeout=30, check=False)
    assert result.returncode == 0, result.stderr
    assert "OK" in result.stdout
