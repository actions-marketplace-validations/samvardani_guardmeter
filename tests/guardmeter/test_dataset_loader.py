"""Tests for dataset loading (CSV and JSONL)."""

from __future__ import annotations

import pytest

from guardmeter.data.loader import load_dataset
from guardmeter.data.schema import DatasetRecord


@pytest.fixture
def sample_csv(tmp_path):
    p = tmp_path / "test.csv"
    p.write_text(
        "text,label,category,language\n"
        "hello,benign,benign,en\n"
        "make a bomb,unsafe,violence,en\n"
        "borderline text,borderline,self_harm,en\n",
        encoding="utf-8",
    )
    return p


@pytest.fixture
def sample_jsonl(tmp_path):
    p = tmp_path / "test.jsonl"
    p.write_text(
        '{"text":"hello","label":"benign","category":"benign","language":"en"}\n'
        '{"text":"make a bomb","label":"unsafe","category":"violence","language":"en"}\n',
        encoding="utf-8",
    )
    return p


def test_csv_load(sample_csv):
    """CSV loading returns DatasetRecord objects."""
    records = load_dataset(sample_csv)
    assert len(records) == 3
    assert all(isinstance(r, DatasetRecord) for r in records)


def test_jsonl_load(sample_jsonl):
    """JSONL loading returns DatasetRecord objects."""
    records = load_dataset(sample_jsonl)
    assert len(records) == 2
    assert all(isinstance(r, DatasetRecord) for r in records)


def test_csv_labels(sample_csv):
    """CSV loading correctly maps label values."""
    records = load_dataset(sample_csv)
    labels = [r.label for r in records]
    assert "benign" in labels
    assert "unsafe" in labels
    assert "borderline" in labels


def test_case_insensitive_columns(tmp_path):
    """Column names should be matched case-insensitively."""
    p = tmp_path / "upper.csv"
    p.write_text(
        "TEXT,LABEL,CATEGORY,LANGUAGE\n"
        "hello,benign,benign,en\n",
        encoding="utf-8",
    )
    records = load_dataset(p)
    assert len(records) == 1
    assert records[0].text == "hello"


def test_missing_label_raises(tmp_path):
    """Missing 'label' field should raise ValueError with row number."""
    p = tmp_path / "bad.csv"
    p.write_text(
        "text,category,language\n"
        "hello,benign,en\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="label"):
        load_dataset(p)


def test_invalid_label_raises(tmp_path):
    """Invalid label value should raise ValueError."""
    p = tmp_path / "bad_label.csv"
    p.write_text(
        "text,label,category,language\n"
        "hello,invalid_label,benign,en\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="invalid label"):
        load_dataset(p)


def test_missing_text_raises(tmp_path):
    """Missing 'text' field should raise ValueError."""
    p = tmp_path / "notext.csv"
    p.write_text(
        "label,category,language\n"
        "benign,benign,en\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="text"):
        load_dataset(p)


def test_unsupported_extension_raises(tmp_path):
    """Unsupported file extension should raise ValueError."""
    p = tmp_path / "data.parquet"
    p.write_text("fake", encoding="utf-8")
    with pytest.raises(ValueError, match="Unsupported"):
        load_dataset(p)


def test_builtin_sample_loads():
    """Built-in sample_10.jsonl fixture should load without errors."""
    import pathlib
    builtin = (
        pathlib.Path(__file__).parent.parent.parent
        / "guardmeter" / "data" / "builtin" / "sample_10.jsonl"
    )
    records = load_dataset(builtin)
    assert len(records) == 10
