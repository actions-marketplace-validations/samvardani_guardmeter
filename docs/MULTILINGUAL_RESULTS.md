# Multilingual results — dataset v2

- Run: `80c63e2e-a688-4e47-8616-bafaab6f054e`
- Baseline: **injection-heuristic** · Candidate: **anthropic** (`claude-sonnet-4-5`)
- Dataset record-SHA: `afc8dcac3bec6b46…` · rows: **1810** · languages: **14** (ar, de, en, es, fa, fr, hi, id, ja, ko, pt, ru, tr, zh)
- Metric policy: **strict** (borderline counts as positive). Overall row also shows lenient. No threshold tuning.

## Overall

| Guard | Policy | Recall | FPR | F1 | Hijack rate | p50 ms | p95 ms |
|---|---|---|---|---|---|---|---|
| injection-heuristic | strict | 0.149 | 0.027 | 0.257 | 0.000 | 0 | 0 |
| anthropic | strict | 0.948 | 0.051 | 0.961 | 0.013 | 2552 | 3102 |
| anthropic | lenient | 0.971 | 0.107 | 0.955 | 0.013 | 2552 | 3102 |

## Per-language — anthropic, strict policy

| Lang | Reviewed | n | pos | Recall | FPR | F1 | Hijack rate | p50 ms |
|---|---|---|---|---|---|---|---|---|
| ar (Arabic) | ⚠️ authored-only | 131 | 89 | 0.966 | 0.048 | 0.972 | 0.008 | 2569 |
| de (German) | ⚠️ authored-only | 129 | 89 | 0.955 | 0.050 | 0.966 | 0.023 | 2542 |
| en (English) | ✅ reviewed | 128 | 84 | 0.905 | 0.023 | 0.944 | 0.023 | 2446 |
| es (Spanish) | ⚠️ authored-only | 122 | 78 | 0.910 | 0.045 | 0.940 | 0.016 | 2483 |
| fa (Persian) | ✅ reviewed | 121 | 77 | 0.935 | 0.068 | 0.947 | 0.000 | 2669 |
| fr (French) | ⚠️ authored-only | 131 | 89 | 0.966 | 0.024 | 0.977 | 0.008 | 2518 |
| hi (Hindi) | ⚠️ authored-only | 131 | 89 | 0.955 | 0.071 | 0.960 | 0.008 | 2558 |
| id (Indonesian) | ⚠️ authored-only | 131 | 89 | 0.944 | 0.071 | 0.955 | 0.031 | 2526 |
| ja (Japanese) | ⚠️ authored-only | 131 | 89 | 0.978 | 0.048 | 0.978 | 0.008 | 2574 |
| ko (Korean) | ⚠️ authored-only | 131 | 89 | 0.944 | 0.071 | 0.955 | 0.008 | 2559 |
| pt (Portuguese) | ⚠️ authored-only | 131 | 89 | 0.978 | 0.000 | 0.989 | 0.015 | 2537 |
| ru (Russian) | ⚠️ authored-only | 131 | 89 | 0.944 | 0.071 | 0.955 | 0.008 | 2586 |
| tr (Turkish) | ⚠️ authored-only | 131 | 89 | 0.944 | 0.071 | 0.955 | 0.015 | 2621 |
| zh (Chinese) | ⚠️ authored-only | 131 | 89 | 0.944 | 0.048 | 0.960 | 0.008 | 2466 |

## Recall parity

- Gap over **all 14 authored** languages (≥20 positives): **0.073** (best `ja` − worst `en`)
- Gap over **native-reviewed only** (en, fa): **0.030** — the only parity number that rests on reviewed rows
- Best 3: `ja` 0.978, `pt` 0.978, `ar` 0.966
- Worst 3: `fa` 0.935, `es` 0.910, `en` 0.905
- Awaiting native review (12): `ar`, `de`, `es`, `fr`, `hi`, `id`, `ja`, `ko`, `pt`, `ru`, `tr`, `zh`

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
Requires `ANTHROPIC_API_KEY`. The paid run (1810 rows) costs roughly $10–15; candidate model was `claude-sonnet-4-5`.
