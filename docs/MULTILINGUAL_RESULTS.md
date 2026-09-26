# Multilingual results — dataset v2

- Run: `3ce18ca9-bc43-437d-b320-1ff4d2591318`
- Baseline: **injection-heuristic** · Candidate: **anthropic** (`claude-sonnet-4-5`)
- Dataset record-SHA: `18b2e86d82e3d5f1…` · rows: **371** · languages: **3** (en, es, fa)
- Metric policy: **strict** (borderline counts as positive). Overall row also shows lenient. No threshold tuning.

## Overall

| Guard | Policy | Recall | FPR | F1 | Hijack rate | p50 ms | p95 ms |
|---|---|---|---|---|---|---|---|
| injection-heuristic | strict | 0.172 | 0.000 | 0.293 | 0.000 | 0 | 0 |
| anthropic | strict | 0.925 | 0.068 | 0.942 | 0.013 | 2545 | 3303 |
| anthropic | lenient | 0.969 | 0.095 | 0.954 | 0.013 | 2545 | 3303 |

## Per-language — anthropic, strict policy

| Lang | Reviewed | n | pos | Recall | FPR | F1 | Hijack rate | p50 ms |
|---|---|---|---|---|---|---|---|---|
| en (English) | ✅ reviewed | 128 | 84 | 0.917 | 0.045 | 0.945 | 0.023 | 2491 |
| es (Spanish) | ⚠️ authored-only | 122 | 78 | 0.923 | 0.068 | 0.941 | 0.016 | 2498 |
| fa (Persian) | ✅ reviewed | 121 | 77 | 0.935 | 0.091 | 0.941 | 0.000 | 2665 |

## Recall parity

- Gap (languages with ≥20 positives): **0.018** (best `fa` − worst `en`)
- Best 3: `fa` 0.935, `es` 0.923, `en` 0.917
- Worst 3: `fa` 0.935, `es` 0.923, `en` 0.917

## Methodology & caveats

- Numbers are recomputed from the run's stored per-row predictions using the same strict/lenient rule as `guardmeter.engine.metrics` (strict overall matches the run's stored metric bundle exactly). No thresholds were tuned.
- `Hijack rate` = fraction of rows where the candidate returned no usable verdict (counted fail-closed as a flag). Overall: 1.3%.
- **Only `en` and `fa` are reviewed by a named native reviewer (samvardani).** All other languages in dataset v2 are authored-only; treat their metrics as provisional until native review lands.
- Candidate error rate: 0.0% (0 rows).

## Reproduce

```
guardmeter compare --baseline injection-heuristic --candidate anthropic \
  --dataset dataset/agentic/v2/data.jsonl --concurrency 4
```
Requires `ANTHROPIC_API_KEY`. The paid run (~371 rows) costs a few dollars; candidate model was `claude-sonnet-4-5`.
