<p align="center"><img src="https://raw.githubusercontent.com/samvardani/guardmeter/main/branding/guardmeter-wordmark.svg" alt="GuardMeter" width="440"/></p>

<p align="center"><img src="https://raw.githubusercontent.com/samvardani/guardmeter/main/docs/images/dashboard.png" alt="GuardMeter dashboard" width="800"/></p>

# GuardMeter — AI Safety Guard Evaluation Framework

[![CI](https://github.com/samvardani/guardmeter/actions/workflows/ci.yml/badge.svg)](https://github.com/samvardani/guardmeter/actions)
[![PyPI](https://img.shields.io/pypi/v/guardmeter)](https://pypi.org/project/guardmeter/)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

GuardMeter compares two content-safety guards — a **baseline** and a **candidate** — on a labeled dataset and produces per-slice metrics, an HTML report, an interactive dashboard, and a pass/fail CI gate. It's for developers and ML engineers who ship a safety classifier and need to catch regressions — per category, language, and attack type — before they merge.

---

## 30-second demo

On a fresh `pip install guardmeter`, these commands run verbatim:

```bash
guardmeter init
guardmeter compare --baseline regex-baseline --candidate regex-enhanced --dataset dataset/sample.csv
guardmeter gate --config gate.json --run latest
guardmeter dashboard --open
```

`init` writes `gate.json` and `dataset/sample.csv` into the current directory. `compare` evaluates both guards and stores the run. `gate` checks the latest run against `gate.json` and exits non-zero on failure. `dashboard` builds `report/dashboard.html` (`--open` launches your browser; omit it or pass `--no-open` in CI).

---

## How it works

**Baseline vs candidate.** You give GuardMeter two guards. The baseline is your current behavior; the candidate is the change you're evaluating. Every metric is reported for both so you can see whether the candidate actually improved things.

**Strict vs lenient policy.** Each dataset row is labeled `benign`, `borderline`, or `unsafe`. Under the **strict** policy a `borderline` row counts as something the guard *should* flag (positive); under the **lenient** policy `borderline` counts as benign (negative). Both policies are always computed; the dashboard has a toggle, and the gate/McNemar test use strict by default.

**Slices.** Aggregate numbers hide regressions. GuardMeter computes recall, FPR, precision, F1 and latency for every `(category × language)` slice, and separately for every `attack_type` slice, so a drop confined to (say) Farsi violence or leetspeak-obfuscated prompts is visible.

**Significance and confidence.** A McNemar test on the paired predictions tells you whether the baseline↔candidate difference is real or noise. Recall and FPR come with Wilson score confidence intervals so small slices aren't over-interpreted.

---

## CI gate

`gate.json` is a machine-readable safety policy you check into version control. `guardmeter gate` loads a stored run and fails the build if any threshold is breached.

```json
{
  "mode": "strict",
  "global_thresholds": {
    "min_recall": 0.55,
    "min_f1": 0.80,
    "max_fpr": 0.01,
    "max_latency_p99_ms": 20
  },
  "slices": {
    "self_harm/en": { "min_recall": 0.44, "min_f1": 0.60 },
    "crime/en":     { "min_recall": 0.44, "min_f1": 0.60 },
    "malware/en":   { "min_recall": 0.44 },
    "pii/en":       { "min_f1": 0.65 }
  }
}
```

Fields:

- **`mode`** — `strict` or `lenient`; selects which policy's metrics the gate checks.
- **`global_thresholds`** — applied to the overall candidate metrics and, by default, to every `(category × language)` slice:
  - `min_recall` — minimum recall (skipped for slices with no positive examples).
  - `min_f1` — minimum F1 (default `0.80`; set `0.0` to disable).
  - `max_fpr` — maximum false-positive rate (skipped for slices with no negatives).
  - `max_latency_p99_ms` — maximum p99 latency in milliseconds.
- **`slices`** — per-slice overrides. Keys are fnmatch globs. A `"category/language"` key (e.g. `"self_harm/en"`, `"*/fa"`) targets the category×language family; an `"attack:<glob>"` key (e.g. `"attack:leetspeak"`) targets the attack-type family. Only the fields you set are overridden; the rest fall back to `global_thresholds`. Attack-type slices are opt-in — they're gated only where an `attack:` key matches.
- **`comparison`** *(optional)* — regression limits versus the previous stored run: `max_recall_regression`, `max_fpr_increase`.
- **`on_failure`** — `block` (fail the gate) or `warn` (report but pass).

The per-slice overrides in the shipped `gate.json` reflect the known limits of the built-in regex demo guard; tighten or remove them for your own guard.

GitHub Actions:

```yaml
- name: Install guardmeter
  run: pip install guardmeter
- name: Evaluate
  run: guardmeter compare --baseline regex-baseline --candidate ${{ env.CANDIDATE_GUARD }} --dataset dataset/sample.csv
- name: Report
  run: guardmeter report --run latest
- name: Safety gate
  run: guardmeter gate --config gate.json --run latest   # exits 1 on regression
- name: Upload report
  uses: actions/upload-artifact@v4
  with:
    name: safety-report
    path: report/
```

---

## Built-in guards

| Name | Requirements | Notes |
|------|--------------|-------|
| `regex-baseline` | built-in | Simple keyword-matching profile — the weak baseline to compare against |
| `regex-enhanced` | built-in | Expanded patterns, obfuscation detection, Farsi coverage |
| `regex` | built-in | Alias of `regex-enhanced` (kept for backward compatibility) |
| `openai` | `pip install guardmeter[llm]` + `OPENAI_API_KEY` | OpenAI Moderation API (experimental — see below) |
| `llamaguard` | HuggingFace `transformers` or an HTTP endpoint | Llama Guard 3, local pipeline or hosted API (experimental — see below) |

### Write your own guard

```python
from guardmeter.core.guard import Guard, GuardResult
from guardmeter.core.registry import register

class MyGuard(Guard):
    name = "my-guard"
    version = "1.0.0"

    def predict(self, text: str, **meta) -> GuardResult:
        is_unsafe = "bomb" in text.lower()
        return GuardResult(prediction="flag" if is_unsafe else "pass",
                           score=0.9 if is_unsafe else 0.1, latency_ms=5)

register("my-guard", MyGuard)  # now usable as --candidate my-guard
```

---

## Dashboard & report

`guardmeter report --run latest` writes an HTML report for a single run (baseline vs candidate cards with Wilson CIs, category×language and attack-type slice tables, a real candidate threshold-sweep chart, and per-sample latency charts). It also mentions an informational regulatory mapping — see the note under *Experimental*.

`guardmeter dashboard` builds an interactive multi-run dashboard (`report/dashboard.html`), also auto-rebuilt on every `report`. Four tabs:

- **Overview** — run history table with F1, recall, FPR, McNemar p-value and gate badges. Click a row to drill in.
- **Run Detail** — baseline vs candidate metric cards, category×language and attack-type slice tables, and a sample-results table (first 200 rows). Strict/Lenient toggle.
- **Trends** — recall, F1, FPR and McNemar p-value over all runs (p-value on a log scale with a p=0.05 reference line).
- **Compare** — pick any two runs and see a per-metric delta table with improvement/regression arrows.

---

## Experimental

These features work but require API keys or extra dependencies and have limited automated test coverage. Treat them as advisory:

- **LLM-as-judge** (`guardmeter/judge/`) — uses Claude or an OpenAI model as a second opinion on predictions. Available through the Python API only (no CLI subcommand); needs a provider API key.
- **`openai` guard** — calls the OpenAI Moderation API; needs `guardmeter[llm]` and `OPENAI_API_KEY`.
- **`llamaguard` guard** — runs Llama Guard 3 via a local `transformers` pipeline or an HTTP endpoint; needs `guardmeter[hf]` or a hosted endpoint and key.
- **Regulatory mapping (informational).** The HTML report includes a table mapping a run's metrics to regulatory themes (e.g. EU AI Act articles, NIST AI RMF). It is an informational aid for your own documentation, **not** a compliance certification or legal assessment.

---

## Development Setup

```bash
python3.13 -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
ruff check guardmeter tests
mypy guardmeter
pytest tests/guardmeter/ -q
```

> **Note:** macOS users with Homebrew Python must use a virtual environment (Homebrew enforces PEP 668).

---

## Not affiliated with

This project is unrelated to the JRC "GuardBench" toxicity-benchmark library at [github.com/AmenRa/guardbench](https://github.com/AmenRa/guardbench). Same name, different project.

Formerly published as `sea-guard` (versions 0.1–0.2, import name `guardbench`). Renamed in 0.3.0 to avoid confusion with the unrelated JRC GuardBench benchmark.

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Contributions welcome — new guard adapters, dataset/language coverage, and report improvements especially.

## License

MIT — see [LICENSE](LICENSE).

## Branding

Logo assets are in the `branding/` directory.

- `guardmeter-logo.svg` — shield mark (favicon, PyPI, GitHub avatar)
- `guardmeter-wordmark.svg` — full lockup with tagline
- `guardmeter-social-card.svg` — 1280×640 OG image for GitHub social preview

---

*Built by [SeaTechOne LLC](https://seatechone.com) · Seattle, WA*
