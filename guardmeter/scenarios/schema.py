"""Pydantic schema for scenario suites.

A scenario tests what an endpoint *does* on one input — did it call the right
tool, refuse the right request, avoid leaking the system prompt, answer in valid
JSON, stay under a latency budget. Guardrail block/allow is one assertion kind
among many. A suite bundles reviewed scenarios with provenance.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

CATEGORIES = ("support", "coding", "agent-tools", "safety", "format", "latency", "leak", "custom")

# ── Assertions ───────────────────────────────────────────────────────────────
# Each is a small typed model with a ``type`` discriminator. The loader
# normalises the compact YAML spellings (bare string, or single-key mapping)
# into these before validation.


class Block(BaseModel):
    type: Literal["block"] = "block"


class Allow(BaseModel):
    type: Literal["allow"] = "allow"


class MustCallTool(BaseModel):
    type: Literal["must_call_tool"] = "must_call_tool"
    name: str
    args_match: dict[str, Any] | None = None  # subset of arguments that must match


class MustNotCallTool(BaseModel):
    type: Literal["must_not_call_tool"] = "must_not_call_tool"
    name: str | None = None  # None = must call no tool at all


class MustContain(BaseModel):
    type: Literal["must_contain"] = "must_contain"
    patterns: list[str]  # regexes; all must be present


class MustNotContain(BaseModel):
    type: Literal["must_not_contain"] = "must_not_contain"
    patterns: list[str]  # regexes; none may be present (leak checks)


class MustMatch(BaseModel):
    type: Literal["must_match"] = "must_match"
    regex: str  # the full response must match


class JsonValid(BaseModel):
    type: Literal["json_valid"] = "json_valid"
    schema_: dict[str, Any] | None = Field(default=None, alias="schema")

    model_config = {"populate_by_name": True}


class MaxLatencyMs(BaseModel):
    type: Literal["max_latency_ms"] = "max_latency_ms"
    value: int


class MaxTokens(BaseModel):
    type: Literal["max_tokens"] = "max_tokens"
    value: int


class Rubric(BaseModel):
    type: Literal["rubric"] = "rubric"
    criteria: str
    min_score: float = 0.5
    judge: str = "anthropic"  # anthropic | openai-chat | opod | <name>


class RefusalExpected(BaseModel):
    type: Literal["refusal_expected"] = "refusal_expected"
    value: bool = True


Assertion = (
    Block | Allow | MustCallTool | MustNotCallTool | MustContain | MustNotContain
    | MustMatch | JsonValid | MaxLatencyMs | MaxTokens | Rubric | RefusalExpected
)

_NOARG = {"block": Block, "allow": Allow}
_BY_TYPE: dict[str, type[BaseModel]] = {
    "block": Block, "allow": Allow, "must_call_tool": MustCallTool,
    "must_not_call_tool": MustNotCallTool, "must_contain": MustContain,
    "must_not_contain": MustNotContain, "must_match": MustMatch,
    "json_valid": JsonValid, "max_latency_ms": MaxLatencyMs, "max_tokens": MaxTokens,
    "rubric": Rubric, "refusal_expected": RefusalExpected,
}
# Assertions whose single-key mapping value is a scalar, not a params dict.
_SCALAR_VALUE = {"max_latency_ms": "value", "max_tokens": "value", "refusal_expected": "value",
                 "must_match": "regex"}


def parse_assertion(raw: Any) -> Assertion:
    """Normalise a compact assertion (str or single-key mapping) into a model.

    Accepted forms:
      - ``block`` / ``allow`` (bare string)
      - ``{must_contain: {patterns: [...]}}`` (single-key mapping → params dict)
      - ``{max_latency_ms: 1500}`` / ``{refusal_expected: true}`` (scalar value)
      - ``{type: must_contain, patterns: [...]}`` (explicit type key)
    """
    if isinstance(raw, str):
        if raw not in _NOARG:
            raise ValueError(f"unknown no-argument assertion {raw!r}")
        return _NOARG[raw]()  # type: ignore[return-value]
    if not isinstance(raw, dict):
        # ValueError (not TypeError): all suite-schema problems surface uniformly.
        raise ValueError(f"assertion must be a string or mapping, got {type(raw).__name__}")  # noqa: TRY004

    if "type" in raw:
        atype = raw["type"]
        params = {k: v for k, v in raw.items() if k != "type"}
    elif len(raw) == 1:
        (atype, value), = raw.items()
        if atype in _SCALAR_VALUE and not isinstance(value, dict):
            params = {_SCALAR_VALUE[atype]: value}
        elif isinstance(value, dict):
            params = value
        elif value is None:
            params = {}
        else:
            raise ValueError(f"assertion {atype!r} expects a mapping of parameters")
    else:
        raise ValueError(f"assertion mapping must have exactly one key or a 'type' key: {raw!r}")

    model = _BY_TYPE.get(atype)
    if model is None:
        raise ValueError(f"unknown assertion type {atype!r}; known: {', '.join(sorted(_BY_TYPE))}")
    return model.model_validate(params)  # type: ignore[return-value]


# ── Scenario + Suite ─────────────────────────────────────────────────────────


class ScenarioInput(BaseModel):
    """The request to send. Either ``text`` (single user turn) or ``messages``."""

    text: str | None = None
    messages: list[dict[str, Any]] | None = None
    system: str | None = None
    tools: list[dict[str, Any]] | None = None  # OpenAI tool specs
    tool_results: list[dict[str, Any]] | None = None  # injected fake tool-output turns
    context: str | None = None

    def model_post_init(self, _ctx: Any) -> None:
        if self.text is None and not self.messages:
            raise ValueError("scenario input needs either 'text' or 'messages'")


class Scenario(BaseModel):
    """A single behavioural test with one or more assertions."""

    id: str
    name: str = ""
    category: str = "custom"
    language: str = "en"
    tags: list[str] = Field(default_factory=list)
    difficulty: int = 1
    input: ScenarioInput
    expect: list[Assertion]
    repeat: int = 2
    reviewed_by: str | None = None
    review_note: str | None = None

    @field_validator("category")
    @classmethod
    def _known_category(cls, v: str) -> str:
        if v not in CATEGORIES:
            raise ValueError(f"unknown category {v!r}; known: {', '.join(CATEGORIES)}")
        return v

    @field_validator("difficulty")
    @classmethod
    def _difficulty_range(cls, v: int) -> int:
        if not 1 <= v <= 3:
            raise ValueError("difficulty must be 1, 2, or 3")
        return v

    @field_validator("repeat")
    @classmethod
    def _repeat_positive(cls, v: int) -> int:
        if v < 1:
            raise ValueError("repeat must be >= 1")
        return v


class SuiteMeta(BaseModel):
    """Provenance for a suite."""

    name: str
    version: str = "1.0"
    description: str = ""
    languages: list[str] = Field(default_factory=lambda: ["en"])
    reviewed_by: list[str] = Field(default_factory=list)
    reviewed_at: str | None = None
    tags: list[str] = Field(default_factory=list)


class Suite(BaseModel):
    """A full scenario suite: metadata + scenarios."""

    suite: SuiteMeta
    scenarios: list[Scenario]

    @field_validator("scenarios")
    @classmethod
    def _unique_ids(cls, v: list[Scenario]) -> list[Scenario]:
        seen: set[str] = set()
        for s in v:
            if s.id in seen:
                raise ValueError(f"duplicate scenario id: {s.id}")
            seen.add(s.id)
        return v
