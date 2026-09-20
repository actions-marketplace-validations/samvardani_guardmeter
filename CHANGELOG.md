# Changelog

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
