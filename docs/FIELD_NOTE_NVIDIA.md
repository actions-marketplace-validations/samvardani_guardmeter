# Field note — NVIDIA free-tier safety endpoints (2026-09-26)

A companion to the [leaderboard](LEADERBOARD.md): what happened when we tried to
grade NVIDIA's hosted safety models, and what GuardMeter reported instead of
scoring silence.

## What we tried

The six named NVIDIA safety presets (`nvidia:<preset>`) over the
OpenAI-compatible endpoint `https://integrate.api.nvidia.com/v1`, free tier,
`--rpm 35`.

## What answered

**One of six guard endpoints returned usable verdicts.** From
`guardmeter probe nvidia` (one call per preset, 60 s timeout;
[`evidence/leaderboard/nvidia-probe-2026-09-26.txt`](evidence/leaderboard/nvidia-probe-2026-09-26.txt)):

| preset | model | status |
|---|---|---|
| `llama-guard-3-8b` | `meta/llama-guard-3-8b` | **not listed** (only guard-4 is hosted) |
| `llama-guard-4` | `meta/llama-guard-4-12b` | **hung** (60 s timeout) |
| `nemoguard-content-safety` | `nvidia/llama-3.1-nemoguard-8b-content-safety` | **hung** |
| `nemoguard-topic-control` | `nvidia/llama-3.1-nemoguard-8b-topic-control` | **500** (TensorRT-LLM) |
| `nemotron-safety-guard-8b-v3` | `nvidia/llama-3.1-nemotron-safety-guard-8b-v3` | **hung** |
| `nemotron-3.5-content-safety` | `nvidia/nemotron-3.5-content-safety` | **429** (rate-limited by our own v2 run) |

Only `nemotron-3.5-content-safety` ever produced verdicts — and only for **263 of
421** rows in a full v1 run (37.5% of calls timed out under sustained load,
p99 85.6 s). The 429 above is honest: a background v2 run was consuming the same
35-rpm free-tier quota, so a second caller is simply starved.

## What GuardMeter reported instead of scoring silence

The point of the framework is that none of this becomes a silent pass:

- Each hung/5xx/429 call, after `--rpm` pacing and 429/`Retry-After` + backoff,
  becomes an **`error` result** — excluded from recall/FPR, never counted as a
  guard that "allowed" the input.
- The run's **error rate** and **Answered** (`scored / sent`) surface the outage
  as a number: `nemotron-3.5` reads `263/421`, the others `0/40`.
- `--resume` checkpoints only *scored* rows, so re-running retries the errored
  ones as the endpoint recovers (v1 completeness rose 187 → 222 → 263 across
  passes) — without re-paying for rows already done.

## The probe command

Run it off-peak before committing wall-clock to a full run — it schedules
nothing:

```
guardmeter probe nvidia            # one call per preset: listed / answered / 404 / hung + latency
```

Only guards that reliably answer a smoke are worth a full run. On this day, that
was the local Ollama guards — see the [leaderboard](LEADERBOARD.md).
