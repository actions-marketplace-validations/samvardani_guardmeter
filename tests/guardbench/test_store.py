"""Tests for SQLite and JSON file store backends."""

from __future__ import annotations

import pytest

from guardbench.engine.evaluator import EvalConfig, Evaluator
from guardbench.store.json_store import JSONFileStore
from guardbench.store.sqlite import SQLiteStore


def _run(sample_records, regex_enhanced):
    ev = Evaluator(regex_enhanced, regex_enhanced, sample_records, EvalConfig())
    return ev.run()


class TestSQLiteStore:
    def test_save_get_round_trip(self, sample_records, regex_enhanced, tmp_db):
        """save_run then get_run should return the same run_id."""
        results = _run(sample_records, regex_enhanced)
        tmp_db.save_run(results)
        retrieved = tmp_db.get_run(results.run_id)
        assert retrieved.run_id == results.run_id

    def test_list_runs(self, sample_records, regex_enhanced, tmp_db):
        """list_runs should include the saved run."""
        results = _run(sample_records, regex_enhanced)
        tmp_db.save_run(results)
        runs = tmp_db.list_runs()
        run_ids = [r["run_id"] for r in runs]
        assert results.run_id in run_ids

    def test_latest_run(self, sample_records, regex_enhanced, tmp_db):
        """latest_run should return the most recently saved run."""
        results = _run(sample_records, regex_enhanced)
        tmp_db.save_run(results)
        latest = tmp_db.latest_run()
        assert latest is not None
        assert latest.run_id == results.run_id

    def test_latest_run_empty_store(self, tmp_path):
        """latest_run on an empty store should return None."""
        store = SQLiteStore(db_path=tmp_path / "empty.db")
        assert store.latest_run() is None

    def test_get_run_missing_raises_key_error(self, tmp_db):
        """get_run with unknown run_id should raise KeyError."""
        with pytest.raises(KeyError):
            tmp_db.get_run("nonexistent-run-id")

    def test_compare_runs(self, sample_records, regex_enhanced, tmp_db):
        """compare_runs should return a delta dict."""
        r1 = _run(sample_records, regex_enhanced)
        r2 = _run(sample_records, regex_enhanced)
        tmp_db.save_run(r1)
        tmp_db.save_run(r2)
        delta = tmp_db.compare_runs(r1.run_id, r2.run_id)
        assert "recall_delta" in delta
        assert "fpr_delta" in delta

    def test_sample_results_round_trip(self, sample_records, regex_enhanced, tmp_db):
        """get_run should read back the per-sample results, not drop them."""
        results = _run(sample_records[:5], regex_enhanced)
        assert len(results.sample_results) == 5
        tmp_db.save_run(results)
        retrieved = tmp_db.get_run(results.run_id)
        assert len(retrieved.sample_results) == 5
        for original, loaded in zip(results.sample_results, retrieved.sample_results):
            assert loaded.text == original.text
            assert loaded.label == original.label
            assert loaded.category == original.category
            assert loaded.language == original.language
            assert loaded.baseline_pred == original.baseline_pred
            assert loaded.candidate_pred == original.candidate_pred


class TestJSONFileStore:
    def test_save_get_round_trip(self, sample_records, regex_enhanced, tmp_path):
        """JSONFileStore save_run then get_run should return same run_id."""
        store = JSONFileStore(dir_path=tmp_path / "runs")
        results = _run(sample_records, regex_enhanced)
        store.save_run(results)
        retrieved = store.get_run(results.run_id)
        assert retrieved.run_id == results.run_id

    def test_list_runs(self, sample_records, regex_enhanced, tmp_path):
        """list_runs should include the saved run."""
        store = JSONFileStore(dir_path=tmp_path / "runs")
        results = _run(sample_records, regex_enhanced)
        store.save_run(results)
        runs = store.list_runs()
        run_ids = [r["run_id"] for r in runs]
        assert results.run_id in run_ids

    def test_latest_run_empty(self, tmp_path):
        """latest_run on empty store returns None."""
        store = JSONFileStore(dir_path=tmp_path / "empty")
        assert store.latest_run() is None

    def test_compare_runs(self, sample_records, regex_enhanced, tmp_path):
        """compare_runs should return a delta dict."""
        store = JSONFileStore(dir_path=tmp_path / "runs")
        r1 = _run(sample_records, regex_enhanced)
        r2 = _run(sample_records, regex_enhanced)
        store.save_run(r1)
        store.save_run(r2)
        delta = store.compare_runs(r1.run_id, r2.run_id)
        assert "recall_delta" in delta
