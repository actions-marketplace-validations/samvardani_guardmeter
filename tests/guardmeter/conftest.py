"""Shared fixtures for GuardMeter tests."""

from __future__ import annotations

import pathlib

import pytest

# Resolve builtin fixture path
_BUILTIN = pathlib.Path(__file__).parent.parent.parent / "guardmeter" / "data" / "builtin"


@pytest.fixture
def sample_records():
    """Load the built-in 10-row JSONL fixture."""
    from guardmeter.data.loader import load_dataset
    return load_dataset(_BUILTIN / "sample_10.jsonl")


@pytest.fixture
def tmp_db(tmp_path):
    """Return a SQLiteStore in a temp directory."""
    from guardmeter.store.sqlite import SQLiteStore
    return SQLiteStore(db_path=tmp_path / "test.db")


@pytest.fixture
def regex_baseline():
    """Return a RegexGuard with 'baseline' profile."""
    from guardmeter.guards.regex_guard import RegexGuard
    return RegexGuard(profile="baseline")


@pytest.fixture
def regex_enhanced():
    """Return a RegexGuard with 'enhanced' profile."""
    from guardmeter.guards.regex_guard import RegexGuard
    return RegexGuard(profile="enhanced")


@pytest.fixture
def injection_heuristic():
    """Return the deliberately-weak injection-heuristic baseline guard."""
    from guardmeter.guards.injection_heuristic import InjectionHeuristicGuard
    return InjectionHeuristicGuard()


@pytest.fixture
def agentic_records():
    """Load the agentic attack dataset (repo artifact, not bundled in the wheel)."""
    from guardmeter.data.loader import load_dataset
    root = pathlib.Path(__file__).parent.parent.parent
    return load_dataset(root / "dataset" / "agentic" / "v1" / "data.jsonl")
