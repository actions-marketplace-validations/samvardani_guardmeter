"""Test the pure slice-metric cell model (undefined → null, not 0)."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

_METRICS = Path(__file__).parent.parent.parent / "guardmeter" / "serve" / "static" / "components" / "metrics.js"


def test_slice_metric_value_returns_null_for_undefined():
    node = shutil.which("node")
    if node is None:
        pytest.skip("node not available")
    script = f"""
    import {{ sliceMetricValue }} from "file://{_METRICS}";
    const ok = (c, v) => {{ if (c !== v) {{ console.error("FAIL", c, v); process.exit(1); }} }};
    // recall: no positives (tp+fn==0) → null, not 0
    ok(sliceMetricValue({{ tp: 0, fn: 0, fp: 4, tn: 4, recall: 0 }}, "recall"), null);
    // recall: has positives → the value
    ok(sliceMetricValue({{ tp: 3, fn: 1, fp: 0, tn: 5, recall: 0.75 }}, "recall"), 0.75);
    // fpr: no negatives (fp+tn==0) → null
    ok(sliceMetricValue({{ tp: 3, fn: 1, fp: 0, tn: 0, fpr: 0 }}, "fpr"), null);
    // fpr: has negatives → the value
    ok(sliceMetricValue({{ tp: 3, fn: 1, fp: 1, tn: 5, fpr: 0.1667 }}, "fpr"), 0.1667);
    console.log("OK");
    """
    result = subprocess.run([node, "--input-type=module", "-e", script],
                            capture_output=True, text=True, timeout=30, check=False)
    assert result.returncode == 0, result.stderr
    assert "OK" in result.stdout
