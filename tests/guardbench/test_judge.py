"""Tests for judge module (no API calls)."""

from __future__ import annotations

import json

import pytest

from guardbench.core.guard import GuardResult
from guardbench.judge.base import JudgeVerdict
from guardbench.judge.consensus import agreement_rate, disagreement_analysis
from guardbench.judge.prompts import SAFETY_JUDGE_SYSTEM_PROMPT


class TestJudgeVerdict:
    def test_fields(self):
        v = JudgeVerdict(agrees=True, confidence=0.9, reasoning="ok", suggested_label="benign")
        assert v.agrees is True
        assert v.confidence == 0.9
        assert v.reasoning == "ok"
        assert v.suggested_label == "benign"

    def test_disagree(self):
        v = JudgeVerdict(agrees=False, confidence=0.7, reasoning="wrong", suggested_label="unsafe")
        assert v.agrees is False


class TestAgreementRate:
    def test_all_agree(self):
        verdicts = [JudgeVerdict(True, 0.9, "", "benign") for _ in range(5)]
        assert agreement_rate(verdicts) == 1.0

    def test_all_disagree(self):
        verdicts = [JudgeVerdict(False, 0.9, "", "unsafe") for _ in range(4)]
        assert agreement_rate(verdicts) == 0.0

    def test_half_agree(self):
        verdicts = (
            [JudgeVerdict(True, 0.9, "", "benign")] * 2 +
            [JudgeVerdict(False, 0.9, "", "unsafe")] * 2
        )
        assert agreement_rate(verdicts) == 0.5

    def test_empty_returns_zero(self):
        assert agreement_rate([]) == 0.0


class TestDisagreementAnalysis:
    def test_fp_candidates(self, sample_records, regex_enhanced):
        """Guard flagged, judge disagrees → fp_candidate."""
        from guardbench.engine.evaluator import EvalConfig, Evaluator
        ev = Evaluator(regex_enhanced, regex_enhanced, sample_records, EvalConfig())
        results = ev.run()
        # Build verdicts: disagree on every "flag" prediction
        verdicts = []
        for s in results.sample_results:
            if s.candidate_pred == "flag":
                verdicts.append(JudgeVerdict(False, 0.9, "disagree", "benign"))
            else:
                verdicts.append(JudgeVerdict(True, 0.9, "agree", "benign"))
        analysis = disagreement_analysis(results, verdicts)
        assert "fp_candidates" in analysis
        assert "fn_candidates" in analysis
        # All fp_candidates should have candidate_pred == "flag"
        for item in analysis["fp_candidates"]:
            assert item["candidate_pred"] == "flag"

    def test_fn_candidates(self, sample_records, regex_enhanced):
        """Guard passed, judge disagrees → fn_candidate."""
        from guardbench.engine.evaluator import EvalConfig, Evaluator
        ev = Evaluator(regex_enhanced, regex_enhanced, sample_records, EvalConfig())
        results = ev.run()
        verdicts = []
        for s in results.sample_results:
            if s.candidate_pred == "pass":
                verdicts.append(JudgeVerdict(False, 0.9, "disagree", "unsafe"))
            else:
                verdicts.append(JudgeVerdict(True, 0.9, "agree", "unsafe"))
        analysis = disagreement_analysis(results, verdicts)
        for item in analysis["fn_candidates"]:
            assert item["candidate_pred"] == "pass"

    def test_mismatch_raises(self, sample_records, regex_enhanced):
        """Mismatched lengths should raise ValueError."""
        from guardbench.engine.evaluator import EvalConfig, Evaluator
        ev = Evaluator(regex_enhanced, regex_enhanced, sample_records, EvalConfig())
        results = ev.run()
        with pytest.raises(ValueError, match="Mismatch"):
            disagreement_analysis(results, [])


class TestPrompts:
    def test_system_prompt_nonempty(self):
        assert len(SAFETY_JUDGE_SYSTEM_PROMPT) > 100

    def test_system_prompt_instructs_json(self):
        assert "JSON" in SAFETY_JUDGE_SYSTEM_PROMPT


class TestLLMJudgeInit:
    def test_claude_backend_detection(self):
        from guardbench.judge.llm_judge import LLMJudge
        j = LLMJudge(model="claude-sonnet-4-6")
        assert j._backend == "anthropic"

    def test_gpt_backend_detection(self):
        from guardbench.judge.llm_judge import LLMJudge
        j = LLMJudge(model="gpt-4o")
        assert j._backend == "openai"

    def test_default_backend_anthropic(self):
        from guardbench.judge.llm_judge import LLMJudge
        j = LLMJudge(model="some-unknown-model")
        assert j._backend == "anthropic"

    def test_parse_verdict_from_json(self):
        from guardbench.judge.llm_judge import LLMJudge
        j = LLMJudge()
        content = json.dumps({
            "agrees": True,
            "confidence": 0.85,
            "reasoning": "Clearly unsafe",
            "suggested_label": "unsafe",
        })
        verdict = j._parse_verdict(content)
        assert verdict.agrees is True
        assert verdict.confidence == 0.85
        assert verdict.suggested_label == "unsafe"

    def test_parse_verdict_with_code_fence(self):
        from guardbench.judge.llm_judge import LLMJudge
        j = LLMJudge()
        content = "```json\n{\"agrees\": false, \"confidence\": 0.7, \"reasoning\": \"ok\", \"suggested_label\": \"benign\"}\n```"
        verdict = j._parse_verdict(content)
        assert verdict.agrees is False

    def test_rate_limit_property(self):
        from guardbench.judge.llm_judge import LLMJudge
        j = LLMJudge(rate_rps=2.0)
        assert j._min_interval == 0.5

    def test_build_user_message(self):
        from guardbench.judge.llm_judge import LLMJudge
        j = LLMJudge()
        gr = GuardResult(prediction="flag", score=0.9, latency_ms=5)
        msg = j._build_user_message("test text", gr)
        assert "test text" in msg
        assert "flag" in msg


class TestEvaluateBatchErrors:
    def test_api_error_is_not_agreement(self):
        """A judge API error must record a None verdict and count as an error, not agrees=True."""
        from guardbench.judge.llm_judge import LLMJudge

        j = LLMJudge(rate_rps=0)  # no rate-limit sleeping in tests

        def _boom(text, guard_result):
            raise RuntimeError("api down")

        j.evaluate = _boom  # mock the client call path to always raise

        texts = ["a", "b", "c"]
        guard_results = [GuardResult(prediction="flag", score=0.9, latency_ms=1) for _ in texts]
        summary = j.evaluate_batch(texts, guard_results)

        assert summary.errors == 3
        assert summary.verdicts == [None, None, None]
        assert summary.agreement_rate is None
        # Critically, no error was silently turned into agreement.
        assert all(v is None or v.agrees is not True for v in summary.verdicts)
