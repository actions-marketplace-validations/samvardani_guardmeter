"""Miscellaneous coverage tests for io_utils, significance, text_norm."""

from __future__ import annotations

from guardbench.core.text_norm import normalize


class TestTextNorm:
    def test_leetspeak_decode(self):
        assert normalize("b0mb") == "bomb"

    def test_spaced_chars_collapsed(self):
        assert normalize("b o m b") == "bomb"

    def test_zero_width_removed(self):
        assert normalize("bo\u200bmb") == "bomb"

    def test_tatweel_removed(self):
        assert normalize("بم\u0640ب") == "بمب"

    def test_lowercase(self):
        assert normalize("HELLO") == "hello"

    def test_empty_string(self):
        assert normalize("") == ""


class TestSignificance:
    def test_identical_predictions_returns_p1(self, sample_records, regex_enhanced):
        """Identical predictions → no discordant pairs → p_value = 1.0."""
        from guardbench.engine.significance import mcnemar_test
        preds = regex_enhanced.batch_predict([r.text for r in sample_records])
        _, p = mcnemar_test(preds, preds, sample_records)
        assert p == 1.0

    def test_returns_float_tuple(self, sample_records, regex_enhanced, regex_baseline):
        """mcnemar_test should return (float, float)."""
        from guardbench.engine.significance import mcnemar_test
        base_preds = regex_baseline.batch_predict([r.text for r in sample_records])
        cand_preds = regex_enhanced.batch_predict([r.text for r in sample_records])
        stat, p = mcnemar_test(base_preds, cand_preds, sample_records)
        assert isinstance(stat, float)
        assert isinstance(p, float)
        assert 0.0 <= p <= 1.0


class TestIOUtils:
    def test_hash_content(self):
        from guardbench.core.io_utils import hash_content
        h = hash_content(b"hello")
        assert len(h) == 64
        assert h == hash_content(b"hello")
        assert h != hash_content(b"world")

    def test_new_run_id_is_uuid(self):
        import uuid

        from guardbench.core.io_utils import new_run_id
        rid = new_run_id()
        uuid.UUID(rid)  # should not raise

    def test_new_run_ids_unique(self):
        from guardbench.core.io_utils import new_run_id
        assert new_run_id() != new_run_id()

    def test_git_commit_sha_returns_string(self):
        from guardbench.core.io_utils import git_commit_sha
        sha = git_commit_sha()
        assert isinstance(sha, str)
        assert len(sha) > 0
