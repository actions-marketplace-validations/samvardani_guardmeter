"""Dataset validation, stats, and info for agentic-style datasets.

Enforces the invariants that make the agentic dataset a usable research
artifact: unique ids, no exact or near-duplicate rows within a family
(anti-template-stamping), sane language script ratios, decoded-payload sanity
for the encoded family, and label/target/context consistency. Rows with no
attack_family (e.g. sample.csv) skip the family-specific checks.
"""

from __future__ import annotations

import base64
import codecs
import hashlib
import re
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any

from guardmeter.data.loader import load_dataset
from guardmeter.data.schema import DatasetRecord

_ZERO_WIDTH = "\u200b‌‍⁠﻿"
_TARGETS = {"override", "exfiltrate", "tool_action", "persona", "none"}
_LABELS = {"unsafe", "benign", "borderline"}
_ENC_TECHNIQUES = {
    "base64", "hex", "rot13", "leetspeak", "homoglyph", "zero_width", "token_split",
}
NEAR_DUP_JACCARD = 0.6


def _norm(text: str) -> str:
    text = (text or "").translate({ord(c): None for c in _ZERO_WIDTH})
    return re.sub(r"\s+", " ", text.strip().lower())


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"\w+", _norm(text), flags=re.UNICODE))


def _arabic_ratio(text: str) -> float:
    letters = [c for c in text if not c.isspace() and unicodedata.category(c)[0] in ("L", "N")]
    if not letters:
        return 0.0
    arabic = sum(1 for c in letters if "؀" <= c <= "ۿ" or "ݐ" <= c <= "ݿ")
    return arabic / len(letters)


def _decoded_ok(text: str, technique: str) -> bool:
    """For base64/hex/rot13, check a decoded payload exists and is printable text."""
    candidates: list[str] = []
    try:
        if technique == "base64":
            for blob in re.findall(r"[A-Za-z0-9+/]{16,}={0,2}", text):
                candidates.append(base64.b64decode(blob).decode("utf-8", "ignore"))
        elif technique == "hex":
            for blob in re.findall(r"[0-9a-fA-F]{24,}", text):
                candidates.append(bytes.fromhex(blob).decode("utf-8", "ignore"))
        elif technique == "rot13":
            candidates.append(codecs.decode(text, "rot_13"))
        else:
            return True  # non-decodable techniques handled elsewhere
    except Exception:  # noqa: BLE001 (malformed encodings are a validation failure, not a crash)
        return False
    return any(d.strip() and d.isprintable() for d in candidates)


def validate_records(records: list[DatasetRecord]) -> list[str]:
    """Return a list of problem strings (empty = valid)."""
    problems: list[str] = []

    # id uniqueness + format
    seen_ids: dict[str, int] = {}
    for i, r in enumerate(records):
        if r.id is None:
            continue
        if not re.fullmatch(r"[A-Za-z0-9._-]+", r.id):
            problems.append(f"{r.id or f'row {i}'}: id has invalid characters")
        if r.id in seen_ids:
            problems.append(f"{r.id}: duplicate id")
        seen_ids[r.id] = i

    # schema-ish: label + target enums
    for r in records:
        rid = r.id or f"'{r.text[:30]}'"
        if r.label not in _LABELS:
            problems.append(f"{rid}: invalid label {r.label!r}")
        if r.target is not None and r.target not in _TARGETS:
            problems.append(f"{rid}: invalid target {r.target!r}")

    # exact duplicates (normalised text)
    seen_text: dict[str, str] = {}
    for r in records:
        nt = _norm(r.text)
        rid = r.id or nt[:30]
        if nt in seen_text:
            problems.append(f"{rid}: exact duplicate of {seen_text[nt]}")
        else:
            seen_text[nt] = str(rid)

    # near-duplicates within a family (skip rows with no family)
    by_family: dict[str, list[DatasetRecord]] = {}
    for r in records:
        if r.attack_family:
            by_family.setdefault(r.attack_family, []).append(r)
    for fam, rs in by_family.items():
        toks = [(_tokens(r.text), r) for r in rs]
        for i in range(len(toks)):
            a, ra = toks[i]
            for j in range(i + 1, len(toks)):
                b, rb = toks[j]
                if a and b:
                    jac = len(a & b) / len(a | b)
                    if jac >= NEAR_DUP_JACCARD:
                        problems.append(
                            f"near-duplicate {ra.id}~{rb.id} in {fam} (jaccard={jac:.2f})"
                        )

    # language script ratios
    for r in records:
        rid = r.id or _norm(r.text)[:30]
        ratio = _arabic_ratio(r.text)
        if r.language == "fa" and ratio < 0.60:
            problems.append(f"{rid}: language=fa but Arabic-script ratio {ratio:.2f} < 0.60")
        if r.language == "en" and ratio >= 0.10:
            problems.append(f"{rid}: language=en but Arabic-script ratio {ratio:.2f} >= 0.10")

    # label/target consistency (only when target is used)
    for r in records:
        rid = r.id or _norm(r.text)[:30]
        if r.target is not None:
            if r.label == "benign" and r.target != "none":
                problems.append(f"{rid}: benign row must have target 'none', got {r.target!r}")
            if r.label == "unsafe" and r.target == "none":
                problems.append(f"{rid}: unsafe row must not have target 'none'")

    # context presence for context-dependent families (borderline exempt)
    for r in records:
        rid = r.id or _norm(r.text)[:30]
        if r.attack_family in ("multi_turn", "indirect_injection") and r.label != "borderline" and not r.context:
            problems.append(f"{rid}: {r.attack_family} row must have non-null context")

    # encoded family: technique + decoded payload
    for r in records:
        if r.attack_family != "encoded":
            continue
        rid = r.id or _norm(r.text)[:30]
        # Technique is required only for unsafe encoded rows; benign concept
        # questions about encoding legitimately carry no technique.
        if r.label == "unsafe" and r.attack_technique not in _ENC_TECHNIQUES:
            problems.append(f"{rid}: unsafe encoded technique {r.attack_technique!r} not in {sorted(_ENC_TECHNIQUES)}")
        elif r.attack_technique is not None and r.attack_technique not in _ENC_TECHNIQUES:
            problems.append(f"{rid}: encoded technique {r.attack_technique!r} not in {sorted(_ENC_TECHNIQUES)}")
        if r.label == "unsafe" and r.attack_technique in ("base64", "hex", "rot13") and not _decoded_ok(r.text, r.attack_technique):
            problems.append(f"{rid}: encoded {r.attack_technique} payload does not decode to printable text")

    return problems


def dataset_stats(records: list[DatasetRecord]) -> dict[str, Any]:
    """Counts by family × language × label, length percentiles, context presence."""
    lengths = sorted(len(r.text) for r in records)

    def pct(p: float) -> int:
        if not lengths:
            return 0
        return lengths[min(len(lengths) - 1, int(p / 100 * len(lengths)))]

    families = sorted({r.attack_family or "n/a" for r in records})
    cells: dict[str, dict[str, dict[str, int]]] = {}
    for fam in families:
        cells[fam] = {}
        fr = [r for r in records if (r.attack_family or "n/a") == fam]
        for lang in sorted({r.language for r in fr}):
            cells[fam][lang] = dict(Counter(r.label for r in fr if r.language == lang))
    return {
        "total": len(records),
        "languages": dict(Counter(r.language for r in records)),
        "labels": dict(Counter(r.label for r in records)),
        "families": dict(Counter(r.attack_family or "n/a" for r in records)),
        "with_context": sum(1 for r in records if r.context),
        "text_len_p50": pct(50), "text_len_p90": pct(90), "text_len_p99": pct(99),
        "cells": cells,
    }


def stats_markdown(records: list[DatasetRecord]) -> str:
    """Composition table (family × language × label) as Markdown."""
    st = dataset_stats(records)
    langs = sorted(st["languages"].keys())
    labels = ["unsafe", "benign", "borderline"]
    header = "| Family | " + " | ".join(f"{lang} {lab}" for lang in langs for lab in labels) + " | total |"
    sep = "|---" * (1 + len(langs) * len(labels) + 1) + "|"
    lines = [header, sep]
    for fam in sorted(st["cells"]):
        row = [fam]
        total = 0
        for lang in langs:
            for lab in labels:
                n = st["cells"][fam].get(lang, {}).get(lab, 0)
                total += n
                row.append(str(n))
        row.append(str(total))
        lines.append("| " + " | ".join(row) + " |")
    lines.append(f"\n**Total: {st['total']}** · " + " · ".join(f"{k} {v}" for k, v in st["languages"].items()))
    return "\n".join(lines)


def dataset_info(path: str | Path) -> dict[str, Any]:
    """Row count, sha256, families, and card version for a dataset file."""
    path = Path(path)
    data = path.read_bytes()
    records = load_dataset(path)
    version = "unknown"
    card = path.parent / "DATASET_CARD.md"
    if card.exists():
        m = re.search(r"—\s*v(\d+(?:\.\d+)?)", card.read_text(encoding="utf-8"))
        if m:
            version = "v" + m.group(1)
    return {
        "path": str(path),
        "sha256": hashlib.sha256(data).hexdigest(),
        "rows": len(records),
        "families": sorted({r.attack_family or "n/a" for r in records}),
        "version": version,
    }
