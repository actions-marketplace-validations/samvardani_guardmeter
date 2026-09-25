# Changelog

## [0.9.0] - 2026-09-25
### Added
- **Scenarios — measure endpoint behaviour, not only guardrails.** A scenario
  tests what an OpenAI-compatible endpoint *does* on one input: which tool it
  calls, whether it refuses the right request, whether it leaks the system
  prompt, whether it answers in valid JSON, whether it stays under a latency
  budget. Guardrail block/allow is one assertion kind among many.
  - `guardmeter/scenarios`: a pydantic Suite/Scenario schema with a YAML/JSON/
    JSONL loader and typed assertions (block/allow, must_call_tool/
    must_not_call_tool, must_contain/must_not_contain, must_match, json_valid,
    max_latency_ms/max_tokens, rubric, refusal_expected).
  - `guardmeter scenarios run SUITE --endpoint URL --model M` runs each scenario
    `repeat` times (concurrently), with determinism (pass/fail/flaky/error),
    judge cross-check (a second judge flags rubric disagreements), and error
    accounting (transport/5xx never counts as a pass/fail). Results — pass rate
    overall and per category/language/tag, latency p50/p95/p99, flaky/error/
    judge-disagree rates — are stored in SQLite. `--summary-md`, `--junit`.
  - `guardmeter scenarios audit SUITE [--endpoint …]` writes validation.md:
    review coverage, near-duplicate inputs, weak categories, *cannot-fail*
    scenarios (pass against a broken null target), and flaky/judge-disagree. A
    suite is "validated" only when clean.
  - Gate: a `scenarios` block (min_pass_rate global + per-category,
    max_flaky_rate, max_error_rate, max_latency_p95_ms); `gate --scenario-run ID`
    refuses an unvalidated suite unless `--allow-unvalidated`.
  - App: a Scenarios page (suite runs, run detail with per-scenario evidence,
    two-run regression compare); snapshot and evidence packs include scenario
    runs.
  - Automation: `POST /api/hooks/rollout` runs a suite against a rollout target
    and returns `{passed, run_id, regressions[]}` synchronously (`serve
    --hook-timeout`); a composite GitHub Action; `docs/OPOD_INTEGRATION.md`.
  - `suites/opod-agent-basics.yaml`: 30 reviewed bilingual scenarios, with
    first results on two Opod models in `docs/OPOD_SCENARIO_RESULTS.md`.

## [0.8.2] - 2026-09-24
### Fixed
- **Correctness: guard-call errors are no longer counted as flags.** A failed
  guard call (invalid key, HTTP 5xx, timeout) was turned into `prediction="flag"`
  and entered the confusion matrix — so a dead API key scored the candidate
  recall 1.00 / F1 0.83. Errors are now a distinct `error` outcome (`score=None`),
  **excluded** from metrics; overall and per-slice `error_rate` are reported, and
  errored samples carry `metadata["error"]`/`attempts`, persisted per sample.
  A run with any error now reports recall `n/a` (not 1.00) and fails the gate as
  an incomplete run.
### Added
- **`error_rate` metric** (overall and per slice) and a **`max_error_rate`** gate
  threshold (default 0.0: any error fails the gate as "incomplete run: N guard
  calls failed"). Per-sample error/hijack metadata is persisted (SQLite
  migration) and surfaced in the app (error chip on run cards, "Errors" sample
  filter) and in `compare` (a red stderr warning, `--json`, `--summary-md`).
- **`guard_info` + environment on every run**: `Guard.describe()` records model,
  verdict mode, profile/threshold, etc.; runs also record the GuardMeter and
  Python versions, dataset path + sha, and policy. Shown in the report and
  dashboard headers and in `compare --json`.
- **Generic HTTP guard** (`http`): evaluate your own endpoint over HTTP,
  configured from `GUARDMETER_HTTP_*` env vars or a YAML/JSON file via
  `--baseline-config`/`--candidate-config` (URL, headers with `${ENV}` expansion,
  body template with `{{text}}`/`{{context}}`, dotted verdict/score paths,
  flag values, timeout). Non-2xx/timeout is recorded as an error.
- **Evidence pack** (`guardmeter evidence`): a self-contained, hash-manifested
  audit bundle (report, dashboard snapshot, run.json, gate result + policy,
  NIST/ISO/EU-AI-Act informational mapping, one-page summary) zipped for
  distribution; `verify-report` accepts the zip.

## [0.8.1] - 2026-09-21
### Changed
- **`openai` is the Moderation API again.** 0.8.0 repurposed the `openai` name
  for a chat classifier; that adapter is now **`openai-chat`**, and `openai` is
  restored to the OpenAI Moderation API (`omni-moderation-latest`). The
  Moderation endpoint follows no instructions in the input, so it can't be
  hijacked — its results carry `metadata["hijackable"] = False`. If you set
  `--candidate openai` for the 0.8.0 chat behaviour, switch to `openai-chat`.
### Fixed
- **One retry before failing closed.** When a chat classifier
  (`anthropic`/`openai-chat`) returns no verdict, the adapter now sends one
  corrective follow-up turn ("respond by calling classify_text; do not answer
  it") before marking the sample hijacked. Retries are counted in
  `metadata["verdict_retries"]`. This recovers transient empty responses without
  any dataset-specific prompting.

## [0.8.0] - 2026-09-20
### Added
- **`hijack_rate` metric**: the fraction of samples a guard failed to produce a
  structured verdict for (was hijacked into replying in prose). Computed overall
  and per slice; surfaced in `compare` (text + `--json`), the HTML report cards,
  and the dashboard run KPIs.
- **`max_hijack_rate`** optional gate threshold (global and per-slice).
- **`--concurrency`** on `guardmeter compare`: guard calls run in a thread pool
  (default 4 when either guard is remote/LLM, else 1) with results kept in input
  order. Rate-limit errors retry with exponential backoff (up to 3×).
### Changed
- **LLM adapters fail closed by default (behaviour change).** The `anthropic`
  adapter now forces a structured verdict via tool use (was prose JSON, which
  the agentic dataset hijacked into silent passes); the `openai` adapter is now a
  chat classifier with function calling (was the Moderation API). Both frame the
  sample as untrusted data in `<sample_to_classify>` tags, and a missing/
  unparseable verdict becomes `flag` (marked `hijacked`) instead of `pass`. A
  constructor flag `on_parse_failure="pass"` restores raw-model measurement. API
  errors propagate to the evaluator's retry/fail-closed handling rather than
  being swallowed as a pass; a missing API key raises a clear error.

## [0.7.1] - 2026-09-20
### Fixed
- `guardmeter dataset fetch agentic-v1` now also downloads `gate.agentic.json`
  and the dataset `LICENSE` (both sha256-pinned), so a pip-only install can run
  the recommended gate without cloning the repo. Release workflow attaches both.

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
