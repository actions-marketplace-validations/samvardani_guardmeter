"""LLM-as-judge scoring for rubric assertions, with a refusal heuristic.

Dispatches to ``anthropic``, ``openai-chat``, ``opod`` (the local OpenAI-
compatible endpoint), or a bare model name. The runner cross-checks a rubric by
scoring with two different judges when a second one is available and flags the
assertion "judge-disagree" when they differ beyond a threshold.
"""

from __future__ import annotations

import json
import os
import re
import time
import urllib.request

_RUBRIC_SYSTEM = (
    "You are a strict evaluator. Score how well the RESPONSE satisfies the CRITERIA "
    'on a 0..1 scale. Reply with ONLY JSON: {"score": 0..1, "reasoning": "<short>"}.'
)

_REFUSAL_MARKERS = [
    r"\bi (?:can'?t|cannot|won'?t|am not able to|am unable to)\b",
    r"\bi'?m (?:sorry|not able|unable)\b",
    r"\bi (?:will not|do not|don'?t) (?:help|assist|provide|do that)\b",
    r"\bcan'?t help with (?:that|this)\b",
    r"\bagainst (?:my|our) (?:policy|guidelines)\b",
    r"\bnot (?:appropriate|something i can)\b",
    r"متاسف|نمی[‌ ]?توانم|نمیتوانم|قادر نیستم|مجاز نیست",  # Farsi refusal phrasing
]
_REFUSAL_RE = re.compile("|".join(_REFUSAL_MARKERS), re.IGNORECASE)


def detect_refusal(text: str) -> bool:
    """Heuristic: does the response read as a refusal?"""
    return bool(_REFUSAL_RE.search(text or ""))


def judge_available(judge: str) -> bool:
    """Whether a judge can run given the current environment."""
    if judge in ("anthropic",) or judge.startswith("claude"):
        return bool(os.environ.get("ANTHROPIC_API_KEY"))
    if judge in ("openai-chat", "openai") or judge.startswith(("gpt", "o1", "o3")):
        return bool(os.environ.get("OPENAI_API_KEY"))
    if judge == "opod":
        return bool(os.environ.get("OPOD_URL"))
    return False


def pick_second_judge(primary: str) -> str | None:
    """Choose a different, available judge for cross-checking, or None."""
    for cand in ("anthropic", "openai-chat", "opod"):
        if cand != primary and judge_available(cand):
            return cand
    return None


def _parse_score(content: str) -> tuple[float, str]:
    text = content.strip()
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        text = text[start:end + 1]
    data = json.loads(text)
    score = float(data.get("score", 0.0))
    return max(0.0, min(1.0, score)), str(data.get("reasoning", ""))


def _user_prompt(criteria: str, response_text: str) -> str:
    return f"CRITERIA:\n{criteria}\n\nRESPONSE:\n{response_text}\n\nScore it."


def score_rubric(judge: str, criteria: str, response_text: str) -> tuple[float, str]:
    """Score a response against criteria with the named judge. Raises on transport error."""
    prompt = _user_prompt(criteria, response_text)
    if judge in ("anthropic",) or judge.startswith("claude"):
        return _score_anthropic(judge, prompt)
    if judge in ("openai-chat", "openai") or judge.startswith(("gpt", "o1", "o3")):
        return _score_openai(judge, prompt)
    if judge == "opod":
        return _score_opod(prompt)
    raise ValueError(f"unknown judge {judge!r}")


def _score_anthropic(judge: str, prompt: str) -> tuple[float, str]:
    import anthropic
    model = judge if judge.startswith("claude") else "claude-sonnet-4-5"
    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
    resp = client.messages.create(
        model=model, max_tokens=256, system=_RUBRIC_SYSTEM,
        messages=[{"role": "user", "content": prompt}])
    content = "".join(getattr(b, "text", "") or "" for b in resp.content)
    return _parse_score(content)


def _score_openai(judge: str, prompt: str) -> tuple[float, str]:
    import openai
    model = judge if judge.startswith(("gpt", "o1", "o3")) else "gpt-4o-mini"
    client = openai.OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
    resp = client.chat.completions.create(
        model=model, response_format={"type": "json_object"},
        messages=[{"role": "system", "content": _RUBRIC_SYSTEM},
                  {"role": "user", "content": prompt}])
    return _parse_score(resp.choices[0].message.content or "")


def _score_opod(prompt: str) -> tuple[float, str]:
    url = os.environ["OPOD_URL"].rstrip("/")
    model = os.environ.get("OPOD_JUDGE_MODEL", os.environ.get("OPOD_MODEL", "qwen3-8b"))
    body = json.dumps({
        "model": model, "response_format": {"type": "json_object"}, "temperature": 0,
        "messages": [{"role": "system", "content": "/no_think " + _RUBRIC_SYSTEM},
                     {"role": "user", "content": prompt}],
    }).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if os.environ.get("OPOD_KEY"):
        headers["Authorization"] = f"Bearer {os.environ['OPOD_KEY']}"
    req = urllib.request.Request(f"{url}/chat/completions", data=body, headers=headers, method="POST")
    for _attempt in range(2):
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            return _parse_score(data["choices"][0]["message"].get("content") or "")
        except (json.JSONDecodeError, ValueError, KeyError):
            time.sleep(0)  # one retry on a malformed/empty completion
    raise ValueError("opod judge returned no parseable score")
