"""Dataset loader: reads CSV and JSONL files into DatasetRecord lists."""

from __future__ import annotations

import csv
import json
import logging
from pathlib import Path
from typing import Any

from guardmeter.data.schema import DatasetRecord

logger = logging.getLogger(__name__)

# Valid label values
_VALID_LABELS = {"benign", "borderline", "unsafe"}

# Canonical field names and their accepted aliases (case-insensitive)
_FIELD_ALIASES = {
    "text": {"text", "prompt", "question", "input", "content", "message", "utterance"},
    "label": {"label", "class", "ground_truth", "gt"},
    "category": {"category", "cat"},
    "language": {"language", "lang"},
    "source": {"source"},
    "attack_type": {"attack_type", "attack"},
    "context": {"context"},
    "attack_family": {"attack_family", "family"},
    "attack_technique": {"attack_technique", "technique"},
    "target": {"target"},
    "review_status": {"review_status"},
    "id": {"id"},
    "notes": {"notes", "note"},
}


def _normalise_row(raw: dict[str, Any], row_num: int) -> dict[str, Any]:
    """Map raw row keys (case-insensitive aliases) to canonical field names."""
    lower_raw = {k.lower().strip(): v for k, v in raw.items()}
    out = {}
    for canonical, aliases in _FIELD_ALIASES.items():
        for alias in aliases:
            if alias in lower_raw:
                out[canonical] = lower_raw[alias]
                break
    # Verify required fields
    for required in ("text", "label", "category"):
        if required not in out or not out[required]:
            raise ValueError(
                f"Row {row_num}: missing or empty required field '{required}'. "
                f"Available columns: {list(raw.keys())}"
            )
    # Validate label
    label_val = (out["label"] or "").strip().lower()
    if label_val not in _VALID_LABELS:
        raise ValueError(
            f"Row {row_num}: invalid label '{out['label']}'. "
            f"Must be one of: {sorted(_VALID_LABELS)}"
        )
    out["label"] = label_val
    return out


def load_dataset(path: str | Path) -> list[DatasetRecord]:
    """Load a CSV or JSONL file and return a list of validated DatasetRecords.

    Raises ValueError with a row number and message on any validation failure.
    """
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return _load_csv(path)
    elif suffix in (".jsonl", ".ndjson"):
        return _load_jsonl(path)
    else:
        raise ValueError(f"Unsupported file extension '{suffix}'. Use .csv or .jsonl")


def _load_csv(path: Path) -> list[DatasetRecord]:
    """Load a CSV file, validate rows, and return DatasetRecords."""
    records: list[DatasetRecord] = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row_num, raw in enumerate(reader, start=2):  # 1 = header
            normalised = _normalise_row(dict(raw), row_num)
            records.append(DatasetRecord.model_validate(normalised))
    return records


def _load_jsonl(path: Path) -> list[DatasetRecord]:
    """Load a JSONL file, validate rows, and return DatasetRecords."""
    records: list[DatasetRecord] = []
    with open(path, encoding="utf-8") as f:
        for row_num, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                raw = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Row {row_num}: invalid JSON — {exc}") from exc
            if not isinstance(raw, dict):
                # ValueError (not TypeError) for parse-consistency with other row errors.
                raise ValueError(f"Row {row_num}: expected JSON object, got {type(raw).__name__}")  # noqa: TRY004
            normalised = _normalise_row(raw, row_num)
            records.append(DatasetRecord.model_validate(normalised))
    return records
