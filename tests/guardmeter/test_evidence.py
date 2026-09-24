"""Evidence pack: contents, manifest verification, and tamper detection."""

from __future__ import annotations

import json
import zipfile

from guardmeter.core.guard import Guard, GuardResult
from guardmeter.data.schema import DatasetRecord
from guardmeter.engine.evaluator import EvalConfig, Evaluator
from guardmeter.report.evidence import build_evidence
from guardmeter.report.manifest import verify_manifest
from guardmeter.store.sqlite import SQLiteStore

_EXPECTED = {
    "report.html", "dashboard.html", "run.json", "gate-result.json",
    "gate-policy.json", "framework-mapping.md", "summary.md", "MANIFEST.json",
}


class _Guard(Guard):
    name = "g"

    def predict(self, text, **meta):
        return GuardResult(prediction="flag" if "bad" in text else "pass", score=0.9, latency_ms=2)


def _run_and_store(tmp_path):
    ds = [
        DatasetRecord(text="bad thing", label="unsafe", category="violence"),
        DatasetRecord(text="nice thing", label="benign", category="benign"),
    ]
    results = Evaluator(_Guard(), _Guard(), ds, EvalConfig(dataset_path="d.csv")).run()
    store = SQLiteStore(db_path=tmp_path / "runs.db")
    store.save_run(results)
    return store, results.run_id


def test_pack_contains_every_file(tmp_path):
    store, run_id = _run_and_store(tmp_path)
    out = tmp_path / "ev"
    zip_path = build_evidence(store, run_id, out)
    assert zip_path.exists()
    with zipfile.ZipFile(zip_path) as zf:
        names = set(zf.namelist())
    assert _EXPECTED <= names
    # zip name carries run id prefix
    assert zip_path.name.startswith(f"evidence-{run_id[:8]}-")


def test_run_json_has_guard_info_and_env(tmp_path):
    store, run_id = _run_and_store(tmp_path)
    out = tmp_path / "ev"
    build_evidence(store, run_id, out)
    run = json.loads((out / "run.json").read_text())
    assert run["guard_info"]["candidate"]["name"] == "g"
    assert run["environment"]["dataset_path"] == "d.csv"


def test_manifest_verifies(tmp_path):
    store, run_id = _run_and_store(tmp_path)
    out = tmp_path / "ev"
    build_evidence(store, run_id, out)
    ok, problems = verify_manifest(out)
    assert ok, problems


def test_tampering_fails_verification(tmp_path):
    store, run_id = _run_and_store(tmp_path)
    out = tmp_path / "ev"
    build_evidence(store, run_id, out)
    # Tamper with the summary after the manifest was written.
    (out / "summary.md").write_text("EDITED — not the audited content\n", encoding="utf-8")
    ok, problems = verify_manifest(out)
    assert not ok
    assert any("summary.md" in p for p in problems)


def test_framework_mapping_is_informational(tmp_path):
    store, run_id = _run_and_store(tmp_path)
    out = tmp_path / "ev"
    build_evidence(store, run_id, out)
    text = (out / "framework-mapping.md").read_text().lower()
    assert "informational mapping, not a certification" in text
    assert "nist ai rmf" in text and "iso/iec 42001" in text and "eu ai act" in text
