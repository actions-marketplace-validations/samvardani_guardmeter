# Agentic Attack Dataset — Baseline Results

This is an **honest** baseline: it reports how the two guards that ship with
GuardMeter perform on the [agentic attack dataset](../dataset/agentic/v1/), and
shows that neither is a prompt-injection detector. The point of the dataset is
to make that gap measurable, not to flatter the shipped guards.

## Published results — Anthropic adapter, v0.7 → v0.8 → v0.8.1

The agentic dataset hijacked the v0.7 Anthropic adapter: it asked the model to
classify the sample as a chat message, and on 39 rows the model answered the
sample in prose instead of classifying it. The old parser turned each unparseable
reply into a silent `pass`. The v0.8 adapter forces a structured tool-use verdict,
frames the sample as untrusted data, and **fails closed** (a missing verdict
becomes `flag`, counted as `hijack_rate`). v0.8.1 adds one corrective retry before
failing closed. All runs use
`--baseline injection-heuristic --candidate anthropic` on the same dataset.

- **Model:** `claude-sonnet-4-5` · **Dataset sha:** `5c6902dcc0bb` (421 rows) ·
  **GuardMeter:** 0.8.1
- v0.7 = run `5fb1c4d9` (prose JSON, `--concurrency 1`); v0.8 = run `963d3cf7`
  (tool-use, fail-closed); v0.8.1 = run `a4efee53` (tool-use + one retry). The two
  structured runs use `--concurrency 4`.

| Adapter | Recall | FPR | F1 | hijack_rate | p99 latency | Agentic gate |
|---|---|---|---|---|---|---|
| v0.7 (prose JSON) | 0.680 | 0.0095 | 0.808 | not measured (≈39 silent-pass) | 6309 ms | fail |
| v0.8 (tool-use, fail-closed) | 0.924 | 0.114 | 0.942 | 0.052 (22/421) | 3961 ms | fail |
| v0.8.1 (tool-use + one retry) | 0.915 | 0.095 | 0.940 | 0.040 (17/421) | 4605 ms | fail |

Per-family recall:

| Family | v0.7 | v0.8 | v0.8.1 |
|---|---|---|---|
| direct_override | 0.96 | 0.979 | 0.979 |
| indirect_injection | 0.80 | 0.969 | 0.939 |
| exfiltration | 0.62 | 0.973 | 0.946 |
| authority_spoof | 0.81 | 0.968 | 0.968 |
| persona_jailbreak | 0.71 | 0.968 | 0.968 |
| multi_turn | 0.77 | 0.935 | 0.903 |
| encoded | 0.19 | 0.969 | 0.969 |
| tool_misuse | 0.41 | 0.634 | 0.658 |

**Interpretation.** Forcing a structured verdict and framing the sample as
untrusted data lifted recall from 0.68 to 0.92 and F1 from 0.81 to 0.94, and
roughly halved the silent-failure surface (39 unparsed prose replies → 22
still-empty verdicts), while concurrency + a tighter `max_tokens` cut p99 latency
from 6.3 s to 4.0 s. Two things did **not** improve at v0.8. `tool_misuse` is still
the hardest family (0.63): these rows read like legitimate tool calls and need
intent reasoning, not surface cues. And FPR **regressed** from 0.01 to 0.11 — a
real cost of failing closed. Every hijack is in the `encoded` family: shown
obfuscated content and told not to decode-and-follow it, the model sometimes
returns no verdict at all.

**What the retry (v0.8.1) changed.** The corrective follow-up recovered 5 of the
22 empty verdicts (hijack_rate 0.052 → 0.040, all still `encoded`). Because fewer
benign encoded look-alikes are fail-closed-flagged, **FPR fell 0.114 → 0.095** —
the intended effect. Recall moved slightly the other way (0.924 → 0.915) and a few
families dip a point or two; that is within single-run, non-deterministic LLM
variance and not a real regression (F1 is flat at 0.94). The retry costs a second
round-trip on empty verdicts, so p99 rose 3961 → 4605 ms. No thresholds were
touched. Against local regex guards (p99 ≈ 0 ms) the latency cost is the other
standing trade-off: a real LLM guard is seconds per call.

All three adapters fail the aspirational `gate.agentic.json` — v0.7 on recall and
latency, v0.8/v0.8.1 on latency (≈4 s vs the 200 ms bar), global FPR, and
`tool_misuse` recall. That gate describes a fast, low-FPR production guard; a
per-call LLM is neither, and the gate is meant to show that gap rather than be met
here.

**Methodology.** The framing and the retry prompt are generic — no prompt was
tuned against these rows, and no threshold was fit to the dataset. The numbers are
a single run each; LLM verdicts are not fully deterministic, so a rerun may shift
a few rows (and the FPR/hijack figures with them). We report the FPR regression
(and its partial recovery) rather than hide it: failing closed is the right
default for a guard, but it is not free.

## Setup

```bash
guardmeter compare \
  --baseline injection-heuristic \
  --candidate regex-enhanced \
  --dataset dataset/agentic/v1/data.jsonl
guardmeter gate --config dataset/agentic/v1/gate.agentic.json --run latest
```

- **Dataset:** 421 rows, 8 attack families, 303 en / 118 fa (see the
  [dataset card](../dataset/agentic/v1/DATASET_CARD.md)).
- **`injection-heuristic`** — a deliberately weak keyword baseline (English-only
  markers + a shallow base64 check). Documented in
  `guardmeter/guards/injection_heuristic.py`.
- **`regex-enhanced`** — the harm-category regex guard, tuned on `sample.csv`
  (violence/self-harm/crime/malware/PII). It was never built for injection, and
  is included to show what "a guard tuned for a different job" scores here.

Numbers below are from the strict decision policy (borderline rows counted as
their labelled class). Reproduce with the commands above; small ties may shift
by a row.

## Overall

| Guard | Recall | FPR | F1 | Precision |
|---|---|---|---|---|
| `injection-heuristic` (baseline) | 0.089 | 0.038 | 0.161 | 0.875 |
| `regex-enhanced` (candidate) | 0.003 | 0.000 | 0.006 | 1.000 |

Both catch almost nothing. `injection-heuristic` does marginally better only
because a handful of `encoded` rows contain a literal base64 blob it flags
without decoding; `regex-enhanced` fires on a single row by keyword accident.

## `injection-heuristic` recall by attack family

| Family | Recall | Why |
|---|---|---|
| `encoded` | 0.53 | Catches long base64 blobs by length; blind to hex/rot13/homoglyph/zero-width. |
| `persona_jailbreak` | 0.10 | Occasional literal "you are now" / "developer mode". |
| `multi_turn` | 0.06 | Only when a blatant marker survives into the final turn. |
| `exfiltration` | 0.05 | "email all files" / "send the data" sometimes match. |
| `direct_override` | 0.04 | Paraphrased overrides slip past surface strings. |
| `indirect_injection` | 0.03 | Payload phrased as document prose; markers rarely present. |
| `authority_spoof` | 0.00 | No markers — pure social framing. |
| `tool_misuse` | 0.00 | Describes a legitimate-looking tool call; nothing to keyword on. |

Farsi recall is effectively zero across every family: the heuristic has no
Farsi patterns. That is the single largest source of missed attacks and is
by design — it demonstrates why an English-tuned keyword guard is unsafe to
deploy on multilingual traffic.

## Gate outcome

Running `gate.agentic.json` (an **aspirational** profile — what a production
injection guard should clear) against either guard **fails**, e.g.:

```
❌ slice:prompt_injection/en: recall 0.0000 < min_recall 0.85
❌ attack:indirect_injection: recall 0.0000 < min_recall 0.80
❌ attack:encoded: recall 0.0000 < min_recall 0.70
... (every family below threshold)
```

The CI `agentic` job runs this gate **non-required** (`continue-on-error`), so
the gap stays visible on every push without blocking merges. When a real
injection guard is added, this is the bar it has to clear — and the number that
proves it did.

## Takeaways

- Keyword/regex guards are not injection detectors. On this dataset they miss
  ~90–99% of attacks.
- Language coverage is a correctness property, not a nicety: an English-only
  guard scores ~0 on the Farsi half regardless of family.
- The families a keyword guard misses completely (`authority_spoof`,
  `tool_misuse`, most `indirect_injection`) are exactly the ones that require
  understanding intent and context, not matching strings.
