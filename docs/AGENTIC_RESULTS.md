# Agentic Attack Dataset — Baseline Results

This is an **honest** baseline: it reports how the two guards that ship with
GuardMeter perform on the [agentic attack dataset](../dataset/agentic/v1/), and
shows that neither is a prompt-injection detector. The point of the dataset is
to make that gap measurable, not to flatter the shipped guards.

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
