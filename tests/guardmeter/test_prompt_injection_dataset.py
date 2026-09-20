"""Tests for the prompt-injection seed dataset."""

from __future__ import annotations

import pathlib
from collections import Counter

from guardmeter.data.loader import load_dataset

_SEED = (
    pathlib.Path(__file__).parent.parent.parent / "dataset" / "prompt_injection_seed.csv"
)


def test_seed_loads_with_expected_shape():
    """The seed set has 40 rows: 28 unsafe / 12 benign, 30 en / 10 fa, all prompt_injection."""
    recs = load_dataset(str(_SEED))
    assert len(recs) == 40

    labels = Counter(r.label for r in recs)
    assert labels["unsafe"] == 28
    assert labels["benign"] == 12

    languages = Counter(r.language for r in recs)
    assert languages["en"] == 30
    assert languages["fa"] == 10

    assert all(r.category == "prompt_injection" for r in recs)
    assert {r.attack_type for r in recs} <= {
        "direct", "indirect_tool_output", "multi_turn_setup", "encoded",
    }
