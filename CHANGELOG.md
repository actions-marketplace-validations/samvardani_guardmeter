# Changelog

## [0.7.0] - 2026-09-20
### Added
- **Agentic Attack Dataset v1** (`dataset/agentic/v1/`): 421 hand-authored,
  bilingual prompt-injection attempts (303 English, 118 natively-written Farsi)
  across 8 families — direct override, indirect injection, exfiltration, tool
  misuse, authority spoof, persona jailbreak, encoded, multi-turn — plus hard
  benign look-alikes and borderline cases. Ships with a dataset card, changelog,
  and CC-BY-4.0 licence. No working exploits, credentials, PII, or real names;
  generic tool references only. A **repo artifact, not bundled in the wheel**.
- **`guardmeter dataset fetch agentic-v1`** downloads the dataset (data + card)
  from the tagged GitHub release assets into `./dataset/agentic/v1/` and verifies
  the sha256 against a constant baked into the package.
- **`guardmeter dataset validate/stats/info`**: `validate` enforces unique ids,
  no exact/near-duplicate rows within a family (token-set Jaccard ≥ 0.6),
  language script ratios, decoded-payload sanity for the `encoded` family, and
  label/target/context consistency (exits 1 on any problem). `stats` prints the
  composition (with `--markdown`); `info` prints rows/sha256/families/version.
  A CI job runs `validate` on both shipped datasets.
- **Context-aware records and guards**: `DatasetRecord` gains optional
  `context`, `attack_family`, `attack_technique`, `target`, `review_status`,
  `id`, and `notes`. `Guard.predict` receives `meta["context"]` (prior turns or
  the surrounding document); the anthropic guard uses it. Slice metrics now split
  by `attack_family` when present.
- **`injection-heuristic` guard**: a deliberately weak, documented keyword
  baseline (English-only, surface-string, shallow encoding check) that gives the
  agentic dataset an honest floor to measure against.
- **`dataset/agentic/v1/gate.agentic.json`**: an aspirational injection gate
  (per-family `attack:` slices + a `*/fa` bar), plus `docs/AGENTIC_RESULTS.md`
  documenting the shipped guards' honest (near-zero) numbers, and a non-required
  `agentic` CI job that keeps the gap visible without blocking merges.

### Fixed
- `sample.csv` was polluted by committed `dataset augment` output (exact- and
  near-duplicate rows, duplicate ids, Farsi rows with an English paraphrase
  prefix). Deduplicated to 110 clean rows and recalibrated the demo `gate.json`
  slice thresholds to the honest numbers; the quickstart still passes.

## [0.6.1] - 2026-09-20
### Fixed
- **Gate editor** no longer hides (and could drop) per-slice `min_f1` and
  `max_latency_p99_ms`: every threshold field is rendered (blank = inherit),
  unknown fields are preserved with a warning, and a round-trip test asserts
  the shipped `gate.json` survives load → save intact.
- Undefined slice metrics render as **n/a**, not `0` — recall for slices with
  no positives, FPR for slices with no negatives — in the run heatmap, the
  Compare delta heatmap, and the attack-type chart.
- Latency histogram uses the accent colour (Chart.js can't read CSS vars);
  sub-millisecond latencies now format with useful precision across the KPI
  card, run cards, Try table, and CLI `try`.
- KPI deltas show `0.0000 · no change` when a previous run exists and the
  metric is unchanged, reserving `—` for "no previous run".

## [0.6.0] - 2026-09-20
### Added
- **The dashboard is now a local app** served by `guardmeter serve`: a
  no-build Preact/htm SPA (two tiny vendored MIT libs) with Overview (KPIs +
  sparklines + filterable runs table), Run (confusion matrices, slice heatmap,
  attack bar, threshold-sweep + latency charts, sample explorer with drawer and
  Re-test), an interactive Gate editor with live pass/fail preview, Try, a
  Compare page (metric deltas + delta heatmap + changed samples), and a
  Datasets browser. Design system with a light/dark theme toggle and a hidden
  `/styleguide`.
- Full JSON API on `serve`: runs (with `gate_pass` per run), samples, gate
  get/evaluate/put, datasets, and background compare jobs. The store gains
  tag/note columns and per-sample attack_type.
- `guardmeter dashboard` exports a single self-contained, read-only HTML
  snapshot (JS/CSS inlined, data embedded) that renders offline for audits.
### Changed
- `guardmeter dashboard` now produces the app snapshot (was the old static
  viewer). Run summaries carry F1, latency p99, and gate_pass.
### Fixed
- Try history now renders reliably after every evaluation (0.5.0 could leave
  the list hidden after the second run); it is driven by a pure, tested model.
- The live/served dashboard's Gate column now shows PASS/FAIL (computed from
  the current `gate.json`) instead of "—".

## [0.5.0] - 2026-09-20
### Added
- `guardmeter try` — evaluate ad-hoc text against one or more guards, as an
  aligned table or `--json` (reads TEXT args, `--file PATH`, or stdin).
- `guardmeter serve` — a local, dependency-free playground: type text, pick
  guards, see verdicts live, with an always-fresh Dashboard link.
- `guardmeter.core.run_try` — the shared evaluation core behind try/serve.
- `gate --junit PATH` (JUnit XML, one testcase per checked scope×metric) and
  `gate --webhook URL` (JSON notification on failure; also
  `$GUARDMETER_WEBHOOK_URL`, with `--report-url`).
- `guardmeter verify-report` plus a `report/MANIFEST.json` of SHA-256 hashes
  for tamper detection; the GitHub Action verifies before uploading and now
  also uploads a JUnit artifact.
### Changed
- Built-in guard registration moved from the CLI into
  `guardmeter.core.registry` so non-click callers (the server) can use it.
### Security
- `serve` requires a `GUARDMETER_TOKEN` Bearer token on every `/api/*` request
  when bound off loopback (and refuses to start off loopback without one);
  `/api/try` is rate-limited per client IP; strict CSP + `nosniff` on every
  response.
- Log output passes through a secret redactor (API keys, bearer tokens, long
  hex/base64 runs) in the guard, judge, and try paths.
- Added CodeQL scanning and a `pip-audit` CI job; enabled GitHub private
  vulnerability reporting; rewrote SECURITY.md with an accurate policy and the
  serve threat model.

## [0.4.0] - 2026-09-20
### Added
- Machine-readable CLI output: `compare --json` and `gate --json` (structured
  `{scope, metric, value, threshold}` failures), plus `--summary-md` on both
  for a baseline/candidate/delta table suitable for `$GITHUB_STEP_SUMMARY`.
- Composite **GitHub Action** — compare → report → dashboard → gate, with a
  step summary, an uploaded report artifact, and `passed`/`run_id`/
  `report_path` outputs:

  ```yaml
  - uses: samvardani/guardmeter@v0.4.0
    with:
      candidate: regex-enhanced
      dataset: dataset/sample.csv
  ```

- Fully offline report and dashboard: Chart.js is vendored and inlined and the
  Tailwind CDN is replaced by a hand-written stylesheet — no network requests.
- Dashboard sample filter (text search) and a "mismatches only" checkbox.
- `anthropic` guard adapter: Claude as a JSON-verdict safety classifier over
  GuardMeter's category vocabulary, with defensive parsing.
- `dataset/prompt_injection_seed.csv`: a 40-row (en + fa) prompt-injection seed
  set for agent-facing guards (not part of the default gate).
### Changed
- CI runs a Python 3.11–3.13 matrix with an 80% coverage floor.
- Reports and dashboards no longer require network access to render.

## [0.3.0] - 2026-09-20
### Changed
- **Renamed** to GuardMeter: PyPI `guardmeter`, import `guardmeter`, CLI
  `guardmeter` (was sea-guard / guardbench). Run history migrates
  automatically from ~/.guardbench to ~/.guardmeter.
- Gate: native `global_thresholds` / `slices` schema with per-slice and
  attack-type overrides; enforces `min_f1` by default.
- README: verbatim-runnable quickstart demo and an honest, accurate
  feature list.
- CLI: `init` scaffolds a working project (calibrated `gate.json` +
  sample dataset) so the quickstart demo passes as written.
### Added
- Real charts in the report: candidate threshold-sweep and per-sample
  latency histograms computed from actual run scores.
- Attack-type slices across the evaluator, report, dashboard, and gate.
- Benign-adjacent dataset rows (en + fa) so false-positive rate is
  measurable.
- `ruff` and `mypy` gates enforced in CI (zero findings required).
### Fixed
- SQLite store now persists and reads back per-sample results instead of
  dropping them.
- `init` writes the calibrated `gate.json`, so the quickstart demo gates
  green verbatim.
### Security
- Report and dashboard now escape all user-originated values.

## [0.2.1] - 2026-09-20
### Fixed
- PyPI project page was blank (no readme in package metadata)

## [0.2.0] - 2026-09-20
### Added
- Interactive multi-run dashboard (`guardbench dashboard`): run history,
  per-run detail, trend charts, side-by-side run comparison
- `regex-baseline` / `regex-enhanced` guard names; built-in `openai` and
  `llamaguard` adapters now resolve by name
- Branding assets (logo, wordmark, social card)
### Changed
- Gate now enforces `min_f1` (default 0.80); the legacy gate.json
  translation layer silently disabled it
- `gate.json` uses the native `global_thresholds` / `slices` schema
- `guardbench dashboard` no longer opens a browser unless `--open`
### Fixed
- `guardbench dashboard` raised ImportError on fresh clones
- Deprecated `datetime.utcnow()` usage
- CI badge pointed at a non-existent workflow file

## [0.1.0] - 2026-04-12
Initial release: evaluation engine, regex guard, HTML report, CI gate.
