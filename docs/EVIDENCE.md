# Evidence

> **Methods and evidence, not the reason to buy.** These are reproducible
> measurements on stated datasets, policies, hosting, and dates — not a vendor
> ranking and not a safety guarantee. The reason to buy is a reviewed suite and a
> release decision for *your* workflow (see the
> [release check playbook](RELEASE_CHECK_PLAYBOOK.md)). Every result below is a
> particular dataset × policy × hosting × date; change any of those and the
> numbers change.

## Guard leaderboard

Grading safety models as GuardMeter guards.

- **Dataset:** agentic v1, 421 rows (en/fa); "Matched" column uses the 263 rows
  `nemotron-3.5` answered.
- **Policy:** strict, baseline `injection-heuristic`, no tuning.
- **Hosting:** local (Ollama) and NVIDIA free tier — the *Answered* column is the
  endpoint's, the recall/FPR/F1 are the classifier's.
- **Date:** 2026-09.
- Read it: [`LEADERBOARD.md`](LEADERBOARD.md). Runs: [`evidence/leaderboard/`](evidence/leaderboard/).

A content-safety classifier's injection recall here is **not** a universal
ranking; it is how that model scored on this dataset under this policy.

## Field notes

Single-workflow probes, reported honestly including what failed. Each is a field
note, not a benchmark.

- **Opod scenarios** — `suites/opod-agent-basics` (30 reviewed scenarios, en/fa)
  against two locally-served Opod models, temperature 0, 2 repeats. Behavioural
  check (tool use, refusals, leak resistance, format, latency).
  Dataset: opod-agent-basics v1.0 · Hosting: Opod (OpenAI-compatible) · Date: 2026-09.
  [`OPOD_SCENARIO_RESULTS.md`](OPOD_SCENARIO_RESULTS.md).
- **Buildorado probe** — 10 hand-run probes against a lead-scoring workflow
  (Claude Sonnet 4.6) built by Buildorado's own builder; the model's judgement
  was good, the pipeline around it was not. Hosting: Buildorado (unpublished
  workflow) · Date: 2026-09-25. [`BUILDORADO_PROBE.md`](BUILDORADO_PROBE.md).
- **NVIDIA free-tier note** — what GuardMeter reported when the free-tier
  endpoints dropped most calls, instead of scoring silence as a pass. Hosting:
  NVIDIA free tier (`--rpm 35`) · Date: 2026-09-26.
  [`FIELD_NOTE_NVIDIA.md`](FIELD_NOTE_NVIDIA.md). Free-tier timeouts are an
  availability story, not a paid-service reliability study.

## Sample decision report

A one-page release decision on two local open models — **a sample, not a
customer**, and not tuned.

- **Suite:** the packaged agent-release-check starter (5 cases, en/fa).
- **Policy:** the starter `gate.json`. **Hosting:** local Ollama. **Date:** 2026-09-27.
- Baseline `llama3.2:3b` vs candidate `qwen3:8b`, 3 repeats: the candidate's
  average pass rate rose (0.6 → 0.8) but it newly failed the critical injection
  case, so the decision is **BLOCK**.
- Read it: [`samples/decision-sample.html`](samples/decision-sample.html)
  ([`.md`](samples/decision-sample.md)); evidence in
  [`samples/evidence/`](samples/evidence/).

## Closure of the independent review

Status of every review item (P1–P12), verified by running the code and the named
test: [`review-closure.md`](review-closure.md).
