# Site handoff — guard leaderboard (seatechone.com/guardmeter)

Copy and numbers for the **results strip** and the **Leaderboard** section on the
site. Source of truth: [LEADERBOARD.md](LEADERBOARD.md) + [FIELD_NOTE_NVIDIA.md](FIELD_NOTE_NVIDIA.md),
runs 2026-09-26, Agentic Attack Dataset, strict policy, no tuning.

## Results strip (one line)

> **GuardMeter grades safety models — locally or hosted.** Running Llama Guard 3
> **locally** scored the full 14-language dataset with **zero errors** (recall
> 0.283, parity gap 0.18); on NVIDIA's free tier, five of six hosted safety
> endpoints wouldn't answer. We grade the model, not the hosting.

## Leaderboard section

| Model | Hosting | Answered | Recall | FPR | F1 |
|---|---|---|---|---|---|
| Llama Guard 3 (8B) | **local (Ollama)** | 1810/1810 | 0.283 | 0.003 | 0.441 |
| Llama Guard 3 (8B) | local, v1 (en/fa) | 421/421 | 0.177 | 0.029 | 0.299 |
| Nemotron 3.5 Content Safety | NVIDIA free tier | 263/421 | 0.615 | 0.074 | 0.750 |
| Llama Guard 4 / NeMoGuard / Nemotron-safety | NVIDIA free tier | 0 (hung/500) | — | — | — |

### One paragraph per model

- **Llama Guard 3, local** — the honest result the framework is built to produce:
  it answered **every** row (0 errors, p99 ~1 s), and it caught only ~28% of the
  agentic attacks. That's expected — Llama Guard is a *content* filter, not a
  prompt-injection detector — and it's the point: GuardMeter turns "wrong tool
  for the job" into a number, per language and per family. Its cross-lingual
  blind spot is real: recall ranges from 0.38 (German) to 0.20 (Japanese), a
  0.18 parity gap.
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
github.com/samvardani/guardmeter."* GuardMeter is MIT-licensed.
