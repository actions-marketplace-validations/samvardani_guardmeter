# Site handoff — NVIDIA guard leaderboard (seatechone.com/guardmeter)

Copy and numbers for the **results strip** and a new **Leaderboard** section on
the site. Source of truth: [NVIDIA_RESULTS.md](NVIDIA_RESULTS.md), run 2026-09-26
on the free-tier NVIDIA endpoint, Agentic Attack Dataset v1 (English + Farsi),
strict policy, no tuning.

## Results strip (one line)

> **GuardMeter now grades NVIDIA-hosted safety models.** On NVIDIA's free tier,
> five of six named safety endpoints weren't reliably runnable; the one that ran,
> `nemotron-3.5-content-safety`, caught **62%** of injection attempts (recall
> 0.615, FPR 0.074) on the rows it returned. We grade the model, not the hosting.

## Leaderboard section

**Headline number:** `nemotron-3.5-content-safety` — recall **0.615**, FPR
**0.074**, F1 **0.75** (263 of 421 rows scored; 37.5% of calls errored out).
English/Farsi recall parity gap: **0.013**.

| Model | Verdict | Recall | FPR | F1 |
|---|---|---|---|---|
| Nemotron 3.5 Content Safety | Ran (partial) | 0.615 | 0.074 | 0.75 |
| Llama Guard 4 (12B) | Unavailable (timeout) | — | — | — |
| NeMoGuard Content Safety (8B) | Unavailable (timeout) | — | — | — |
| Nemotron Safety Guard 8B v3 | Unavailable (intermittent) | — | — | — |
| NeMoGuard Topic Control (8B) | Unavailable (500) | — | — | — |
| Llama Guard 3 (8B) | Not hosted | — | — | — |

### One paragraph per model

- **Nemotron 3.5 Content Safety** — the only NVIDIA safety endpoint that
  completed a real run. It flagged tool-misuse (0.79) and multi-turn build-ups
  (0.71) best, and struggled with persona-jailbreak (0.40) and exfiltration
  (0.50). Even so, roughly a third of calls timed out under a sustained 421-row
  load — a serving limit on the free tier, not a limit of the classifier.
- **Llama Guard 4 (12B)** — NVIDIA's flagship guard resolved in the model list
  but every call timed out (cold-start / eviction) across repeated attempts. Not
  gradable on the free tier today.
- **NeMoGuard Content Safety (8B)** — same story: listed, but chat-completions
  calls timed out. Returned valid JSON on a single earlier call, so the model is
  real; the hosting couldn't sustain a run.
- **Nemotron Safety Guard 8B v3** — intermittent: it returned well-formed
  `{"User Safety": …}` verdicts early in the day, then timed out under load. A
  clean run needs more reliable serving.
- **NeMoGuard Topic Control (8B)** — returned a server-side 500 (TensorRT-LLM
  CUDA error) on every attempt. Topic-control is also a different task (on-/off-
  topic) than content safety.
- **Llama Guard 3 (8B)** — not hosted at `integrate.api.nvidia.com` (only Llama
  Guard 4 is). GuardMeter fails it with a clear "not hosted" message.

### What this shows about GuardMeter

The point isn't the scores — it's that **GuardMeter turns "is this hosted guard
usable?" into a reproducible number**: per-family and per-language recall, error
rate, and latency, with a client-side rate cap and a resumable checkpoint so a
flaky endpoint doesn't cost a restart. Point it at any OpenAI-compatible guard
(`nvidia:<preset>`, `nvidia:chat:<model>`, or your own over HTTP) and get the
same table.

## Credit (required)

Results use the **GuardMeter Agentic Attack Dataset v1**, CC-BY-4.0. On the site,
credit: *"Evaluated on the GuardMeter Agentic Attack Dataset (CC-BY-4.0),
github.com/samvardani/guardmeter."* GuardMeter is MIT-licensed.
