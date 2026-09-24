"""guard_info (Guard.describe) and environment metadata on every run."""

from __future__ import annotations

import sys
import types

from guardmeter.core.guard import Guard, GuardResult
from guardmeter.data.schema import DatasetRecord
from guardmeter.engine.evaluator import EvalConfig, Evaluator


def test_describe_regex():
    from guardmeter.guards.regex_guard import RegexGuard
    d = RegexGuard(profile="enhanced").describe()
    assert d["name"] == "regex"
    assert d["profile"] == "enhanced"
    assert "threshold" in d


def test_describe_injection_heuristic_default():
    from guardmeter.guards.injection_heuristic import InjectionHeuristicGuard
    d = InjectionHeuristicGuard().describe()
    assert d == {"name": "injection-heuristic", "version": InjectionHeuristicGuard.version}


def test_describe_anthropic_has_model(monkeypatch):
    mod = types.ModuleType("anthropic")
    mod.Anthropic = lambda api_key=None: types.SimpleNamespace(messages=None)
    monkeypatch.setitem(sys.modules, "anthropic", mod)
    from guardmeter.guards.anthropic_guard import AnthropicGuard
    d = AnthropicGuard(api_key="k", model="claude-x").describe()
    assert d["model"] == "claude-x"
    assert d["mode"] == "tool_use"
    assert d["on_parse_failure"] == "flag"


def test_describe_openai_chat_and_moderation(monkeypatch):
    mod = types.ModuleType("openai")
    mod.OpenAI = lambda api_key=None: types.SimpleNamespace(chat=None, moderations=None)
    monkeypatch.setitem(sys.modules, "openai", mod)
    from guardmeter.guards.openai_guard import OpenAIGuard
    from guardmeter.guards.openai_moderation import OpenAIModerationGuard
    assert OpenAIGuard(api_key="k").describe()["mode"] == "function_call"
    md = OpenAIModerationGuard(api_key="k").describe()
    assert md["mode"] == "moderation_api"
    assert md["model"] == "omni-moderation-latest"


def test_all_builtin_guards_describe():
    """Every registered, constructible built-in guard returns name+version."""
    from guardmeter.guards.injection_heuristic import InjectionHeuristicGuard
    from guardmeter.guards.regex_guard import RegexBaselineGuard, RegexEnhancedGuard
    for cls in (RegexBaselineGuard, RegexEnhancedGuard, InjectionHeuristicGuard):
        d = cls().describe()
        assert d["name"] and d["version"]


class _OK(Guard):
    name = "ok"
    version = "9.9"

    def predict(self, text, **meta):
        return GuardResult(prediction="pass", score=0.0, latency_ms=1)


def test_run_records_guard_info_and_environment():
    ds = [DatasetRecord(text="a", label="benign", category="benign")]
    results = Evaluator(_OK(), _OK(), ds, EvalConfig(dataset_path="foo.csv")).run()
    assert results.guard_info["baseline"]["name"] == "ok"
    assert results.guard_info["candidate"]["version"] == "9.9"
    env = results.environment
    assert env["python_version"]
    assert env["guardmeter_version"]
    assert env["policy"] == "strict"
    assert env["dataset_path"] == "foo.csv"


def test_guard_info_survives_store_round_trip(tmp_path):
    from guardmeter.store.sqlite import SQLiteStore
    ds = [DatasetRecord(text="a", label="benign", category="benign")]
    results = Evaluator(_OK(), _OK(), ds, EvalConfig(dataset_path="foo.csv")).run()
    store = SQLiteStore(db_path=tmp_path / "r.db")
    store.save_run(results)
    loaded = store.get_run(results.run_id)
    assert loaded.guard_info["candidate"]["name"] == "ok"
    assert loaded.environment["dataset_path"] == "foo.csv"
