# Site handoff — guard leaderboard (seatechone.com/guardmeter)

Copy and numbers for the **results strip** and the **Leaderboard** section on the
site. Source of truth: [LEADERBOARD.md](LEADERBOARD.md) + [FIELD_NOTE_NVIDIA.md](FIELD_NOTE_NVIDIA.md),
runs 2026-09-26, Agentic Attack Dataset, strict policy, no tuning.

## Results strip (25-word headline)

> Graded content-safety models as agent guardrails: on the same rows, Claude
> Sonnet 4.5 caught 92%, NVIDIA's Nemotron 62%, Llama Guard 17% — injection
> judgement beats a content taxonomy.

## Leaderboard section (Agentic v1, strict recall)

Full-v1 recall, **Answered** (scored/sent), and **Matched** = recall on exactly
the 263 rows NVIDIA's Nemotron answered — the apples-to-apples column.

| Model | Type | Answered | Full-v1 recall | Matched (263 rows) |
|---|---|---|---|---|
| Claude Sonnet 4.5 | chat model | 421/421 | 0.927 | **0.918** |
| Nemotron 3.5 Content Safety | content-safety (NVIDIA) | 263/421 | 0.615 | **0.615** |
| Llama Guard 3 (8B) | content-safety (local Ollama) | 421/421 | 0.177 | **0.174** |
| injection-heuristic | keyword baseline | 421/421 | 0.089 | 0.062 |
| regex-enhanced / regex-baseline | regex baseline | 421/421 | 0.003 / 0.000 | 0.005 / 0.000 |

**Matched-rows sentence.** Scored on the identical 263 rows, Nemotron (0.62)
keeps its lead over local Llama Guard 3 (0.17), but Claude Sonnet 4.5 (0.92) is
well ahead of both dedicated safety models — for agentic injection, injection
judgement beats a content-safety taxonomy.

**Local full 14-language run** (Llama Guard 3, Agentic v2): **1810/1810 scored,
zero errors**, recall 0.283, **parity gap 0.18** — strongest German (0.38),
weakest Japanese (0.20). The complete multilingual run NVIDIA's free tier
couldn't sustain.

Content-safety models (Llama Guard, NVIDIA NeMoGuard/Nemotron) are hate/violence
classifiers, not injection detectors; this measures them as agent guardrails,
how teams commonly deploy them.

### One paragraph per model

- **Llama Guard 3, local** — the result the framework is built to produce: it
  answered **every** row (0 errors, p99 ~1 s), and caught ~28% of the agentic
  attacks. As a content-safety classifier used as an agent guardrail, that's the
  measurement — per language and per family. Its cross-lingual range is wide:
  recall from 0.38 (German) to 0.20 (Japanese), a 0.18 parity gap.
- **Nemotron 3.5 Content Safety, NVIDIA** — the one hosted safety endpoint that
  answered, and it scored higher (0.615) — but only on the 63% of rows the free
  tier returned before timing out.
- **The other four NVIDIA safety endpoints** — hung, 500'd, or weren't hosted.
  `guardmeter probe nvidia` shows it in one line; run it before paying wall-clock.

### What this shows about GuardMeter

Point it at a **local** model (`ollama:<preset>`), a **hosted** one
(`nvidia:<preset>`), or your own guard over HTTP — same leaderboard, same
per-language/per-family recall, error rate, and latency. A flaky endpoint never
becomes a silent pass: it's an `error`, surfaced in the *Answered* column, with
`--resume` to fill it in when the endpoint recovers.

## Endpoint scenarios (bonus)

Local chat models on the 30-scenario agent-behaviour suite: `llama3.2:3b`
**48%** pass, `qwen3:8b` **58%** pass (`/no_think`). Both answered every scenario.

## Credit (required)

Results use the **GuardMeter Agentic Attack Dataset**, CC-BY-4.0. On the site,
credit: *"Evaluated on the GuardMeter Agentic Attack Dataset (CC-BY-4.0),
github.com/samvardani/guardmeter."* GuardMeter is MIT-licensed and built by
**SEATECHONE LLC**.
