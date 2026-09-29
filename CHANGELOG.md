# Changelog

## [0.14.1] - 2026-09-29
### Fixed
- **`guardmeter languages status` works from a `pip install`.** The default
  manifest path was repo-relative, so it errored anywhere else. It now resolves
  the fetched dataset's manifest under `./dataset/agentic/v2/` (where
  `guardmeter dataset fetch agentic-v2` writes it) and, when none is found,
  prints "no manifest here: run `guardmeter dataset fetch agentic-v2` or pass
  --manifest PATH" instead of a confusing path error.

## [0.14.0] - 2026-09-29
Closes the remaining items from the independent review (P6–P10). No new engine,
adapters, datasets, or languages. Full status: `docs/review-closure.md`.

### Added
- **Measured cost per successful task.** Scenario runs now capture the target's
  prompt tokens (previously parsed then dropped) and the judge's own
  prompt/completion tokens and retry count. `guardmeter decide` gains
  `--price-file` (dated prices: `model → {input_per_1k, output_per_1k, as_of}`)
  and prices prompt+completion per successful task, adding judge cost only when
  the judge model is priced. Without usage or a price it stays **unknown** —
  never estimated. (P7)
- **`guardmeter languages status`** — per-language authored / reviewed /
  native-signed counts from `MANIFEST.json`. Bare `guardmeter languages` still
  lists the registry. (P9)
- **PR release delivery.** `guardmeter decide` accepts run artifacts
  (`--baseline-file` / `--candidate-file`) and can write an updateable PR-comment
  body (`--pr-comment`). The `.github/actions/scenarios` action decides from two
  run artifacts, posts one PR comment (found by marker, edited in place) with the
  verdict, failing critical case ids, INCONCLUSIVE reasons and the rerun command,
  and fails the check on BLOCK or INCONCLUSIVE; the comment step is guarded to
  same-repo PRs. (P8)
- **Docs:** `docs/review-closure.md` (P1–P12 status), `docs/EVIDENCE.md` +
  `docs/site-handoff-evidence.md` (evidence appendix, "methods not the reason to
  buy"), `docs/ENDPOINT_RECIPES.md` (OpenAI/n8n/Make/generic, stub-tested),
  `docs/ADD_A_LANGUAGE.md`. (P6, P10)

### Changed
- **Language release now requires a native sign-off.** `can_release` counts only
  native-reviewed rows and refuses a language without a native reviewer sign-off
  covering ≥90% of rows — a fully-reviewed but non-native language (`en`) is
  refused; `fa` (native) is releasable. (P9)
- The scenario Action's install-version default was fixed (`0.9.0` → `0.14.0`).

## [0.13.1] - 2026-09-27
Docs only.

### Fixed
- The starter README written by `init --agent` told users to confirm the suite
  "audits clean" with `guardmeter scenarios audit starter.yaml`. Without an
  endpoint that always prints "NOT VALIDATED" (flakiness can't be measured), so
  a new user would think it was broken. The step now passes `--endpoint`/`--model`,
  and a line explains that without an endpoint the audit checks review coverage
  only and reporting "not validated" is expected.

## [0.13.0] - 2026-09-27
A starter kit and a one-page decision report, so an agent release check can be
scaffolded, run, and delivered. Reuses the existing runner, gate, and comparison
code — no new engine, integrations, or SaaS.

### Added
- **`guardmeter init --agent`** scaffolds an agent release check into
  `agent-release-check/`: a five-case reviewed starter suite (`starter.yaml`), a
  gate policy (`gate.json`), and a README. The suite ships **inside the wheel**,
  so a clean `pip install guardmeter` can run it without cloning the repo (proven
  by a clean-venv CI job). The regex compare demo is still there as
  `init --demo` (and remains the default).
- **`guardmeter decide --baseline RUN --candidate RUN --policy gate.json --out decision.{md,html}`**
  turns two scenario runs into a one-page release decision: **APPROVE / BLOCK /
  INCONCLUSIVE**, critical regressions (case id, before→after, failing
  assertion), improvements, other regressions, added/removed cases, disputes,
  errors, per-category coverage, latency p50/p95 before vs after, cost per
  successful task (or **unknown** — never estimated), the acceptance policy in
  plain words, and the exact rerun command with suite hash and both target
  configs. The HTML is a single offline, print-friendly file. The verdict comes
  from the canonical scenario gate; a new failure on a `critical` case blocks
  approval even if the average improved, and an error or dispute on a critical
  case is inconclusive. Exit code: 0 APPROVE, 1 BLOCK, 2 INCONCLUSIVE.
- **`critical: true`** on scenarios, and `--repeats` on `scenarios run` to
  override each scenario's repeat count.
- **Sample decision** (`docs/samples/decision-sample.{md,html}`) plus run
  evidence, on two local Ollama models (`llama3.2:3b` vs `qwen3:8b`) — a sample
  on local open models, **not a customer**, and not tuned: the candidate's
  average rose (0.6 → 0.8) but it newly failed the critical injection case, so
  the verdict is **BLOCK**.
- **`docs/RELEASE_CHECK_PLAYBOOK.md`** — the one-page delivery playbook (intake,
  day-by-day commands, scope limits, handoff).

### Changed
- Scenario runs now record a `suite_hash` (bound to the exact suite) and
  per-scenario `critical` flag; both round-trip through the store.

## [0.12.1] - 2026-09-27
Two small fixes, no new features.

### Fixed
- **Coverage message no longer contradicts itself.** Gating an all-error
  scenario run said "insufficient coverage: 2 evaluable scenarios (min 1)" — but
  errored scenarios aren't evaluable. It now reads "0 evaluable of 2 (2 errored,
  min 1)". (The verdict was already correct; only the wording was wrong.)
- **`scenarios run` explains a missing pass rate.** When every evaluable
  scenario errored, the run printed "Pass rate: None" and exited 0 with no
  pointer to the verdict. It now prints "n/a (no evaluable scenarios)" and a
  line directing you to `guardmeter gate --scenario-run <id>`.

### Changed
- **Honest parity label.** `docs/MULTILINGUAL_RESULTS.md` no longer calls the
  en+fa parity number "native-reviewed only" — en is reviewed (non-native), so
  it now reads "reviewed rows (en + fa; native sign-off `fa` only)". The number
  (0.030, the fa−en recall gap) is unchanged.

## [0.12.0] - 2026-09-27
Decision integrity. An incomplete or untrustworthy evaluation must never read as
a pass, every gate verdict comes from one engine, and every run identity is
explicit. No new guards or datasets — this release is entirely about not lying
to the person reading the result.

### Added
- **Three-state verdicts (PASS / FAIL / INCONCLUSIVE)** across the scenario gate,
  CLI, hook, dashboard, report, and Action. Insufficient coverage, an error rate
  over threshold, an unevaluated required category, or unresolved judge disputes
  now return **INCONCLUSIVE** — never PASS. (`ScenarioThresholds` gains
  `min_total` and `max_judge_disagree_rate`.)
- **Strict output validation** via `jsonschema` (now a runtime dependency,
  floor-pinned `>=4.0`). Unknown/null guard verdicts, an unparseable Llama Guard
  reply, a missing judge verdict, an invalid enum, malformed tool-arg JSON, and
  missing token usage are **errors**, not silent passes.
- **`compare` reports McNemar's excluded pairs.** Errored pairs are dropped from
  the paired test and the excluded count is printed and echoed in `--json`
  (`mcnemar_excluded_pairs`).

### Changed
- **Explicit run identity.** `--rows-from` matches on a stable **case id +
  context hash**, not normalised text. Runs stored before ids existed fall back
  to text matching, labelled **"matched by text (legacy)"**; the two modes are
  never mixed in one comparison. `compare_runs` refuses to compare a run against
  itself, and a gate never picks its own run as the "previous" baseline.
- **One canonical gate verdict.** The HTML report no longer recomputes a
  simplified recall/FPR/F1 pass/fail — it routes through the same `GateChecker`
  the CLI and Action use, so there is a single gate result everywhere. Language
  slices, `case_id`, and `context` now round-trip through the SQLite store.
- **Scoped evidence/snapshot export.** Export takes an explicit run / dataset /
  scenario allowlist so one customer's bundle can never include another's
  history. "Signed" evidence packs are renamed **"hash-manifested"** (a SHA-256
  manifest, not a cryptographic signature).
- **Honest review status.** The `en` rows are marked **reviewed (non-native)**;
  **only `fa` carries native sign-off.** The dataset card and this changelog say
  exactly that. The review workflow no longer defaults a packet to *accept*
  (rows are `pending` until an explicit decision) and a non-native reviewer can
  no longer mark rows "native-reviewed". Leaderboard prose no longer contradicts
  its own scenario-error column.

## [0.11.2] - 2026-09-27
### Added
- **`compare --rows-from RUN_ID`** — restrict a run to exactly the rows a prior
  run's candidate answered (non-error), matched by normalised text, so a partial
  hosted run becomes comparable. Used to re-score every v1 guard on NVIDIA
  nemotron's 263 answered rows.
### Changed
- **Comparable leaderboard.** `docs/LEADERBOARD.md` gains a "Recall on nemotron's
  263 rows" matched column and full-v1 context rows for the regex/keyword
  baselines and Claude Sonnet 4.5 (every number traces to a run file under
  `docs/evidence/leaderboard/`). Matched: Sonnet 4.5 0.918, nemotron-3.5 0.615,
  llama-guard3 0.174, injection-heuristic 0.062, regex ~0. Neutral framing added
  (content-safety classifiers measured as agent guardrails); site handoff updated.

## [0.11.1] - 2026-09-26
### Added
- **Ollama local guard family.** `ollama:<preset>` / `ollama:chat:<model>` over
  the local OpenAI-compatible endpoint (`http://localhost:11434/v1`) — no rate
  limit, no key. `ollama:llama-guard3` reuses the shared safety parsers
  (extracted to `guardmeter/guards/_hosted.py`, shared with the nvidia family).
- **`guardmeter probe nvidia`** — one call per NVIDIA safety preset (listed /
  answered / 404 / hung + latency) so you can see which endpoints answer before
  committing wall-clock. Schedules nothing.
- **Leaderboard rerun on endpoints that answer.** `docs/LEADERBOARD.md` gains
  Hosting (local / NVIDIA free tier) and Answered (scored/sent) columns.
  `ollama:llama-guard3` graded the **full 14-language v2 locally with zero
  errors** (recall 0.283, FPR 0.003, F1 0.441, parity gap 0.18) — the run
  NVIDIA's free tier couldn't sustain. NVIDIA outage detail moved to
  `docs/FIELD_NOTE_NVIDIA.md` (1 of 6 endpoints answered). Endpoint scenarios via
  local Ollama chat models (`llama3.2:3b`, `qwen3:8b` with `/no_think`).
### Notes
- Grading Llama Guard shows it's a *content* filter, not an injection detector:
  it answered every row but caught ~28% of agentic attacks (honestly reported),
  weakest on Japanese (0.20) vs German (0.38). The GGUF import for
  `nemotron-safety-guard-8b-v3` fits 18 GB but behaves as a chat model without
  its system prompt (skipped, documented); `nemoguard-content-safety` has no
  GGUF. The 0.11.0 detached NVIDIA v2 run was left untouched.

## [0.11.0] - 2026-09-26
### Added
- **NVIDIA-hosted guard family.** `nvidia:<preset>` grades NVIDIA's dedicated
  safety endpoints (Llama Guard 4, NeMoGuard content-safety/topic-control,
  Nemotron safety-guard-8b-v3, nemotron-3.5-content-safety) as GuardMeter
  guards, each with its own prompt/parse (unit-tested on real captured outputs);
  `nvidia:chat:<model>` runs any chat model as a JSON-mode classifier. Model ids
  are resolved from `GET /v1/models` at runtime with a clear "not hosted" error.
- **Adapters** gained `base_url` + `api_key_env` (openai-chat, llamaguard;
  defaults unchanged) so they target any OpenAI-compatible host.
- **Rate limiting & resume.** `compare --rpm` caps client-side request rate
  (default 35 for nvidia); 429/`Retry-After` + jittered backoff; API failures
  after retries become excluded `error` results, never a silent allow.
  `compare --resume PATH` checkpoints scored rows (keyed by guard × index) so a
  crash/sleep resumes instead of restarting — and retries only errored rows.
- **Leaderboard.** `docs/NVIDIA_RESULTS.md` grades the endpoints on Agentic v1
  (recall/FPR/F1/error-rate/parity + per-family heatmap), with a site handoff
  (`docs/site-handoff-nvidia.md`) and evidence under `docs/evidence/nvidia/`.
### Notes
- Free-tier reality (2026-09-26): five of six named safety endpoints weren't
  reliably runnable (timeouts/500/not-hosted); `nemotron-3.5-content-safety`
  scored recall 0.615 / FPR 0.074 / F1 0.75 on the completed subset (37% of
  calls errored). We grade the model, not the hosting. The 14-language v2
  leaderboard and NVIDIA chat-model scenarios are deferred to 0.11.1.

## [0.10.2] - 2026-09-26
### Changed
- **en and fa recorded as native-reviewed.** Both languages were reviewed by
  samvardani (native Farsi; English reviewer) and signed off through the review
  workflow (`dataset review queue` → accept-all packet → `apply`), flipping them
  to status `reviewed` with a per-language sign-off sha256. `dataset review
  apply` now derives the manifest status from the reviewed fraction (`reviewed`
  ≥90%, else `in_review`, else `authored`) instead of always `in_review`.
- **Docs refresh.** README restructured top-down for 0.10.x (what-it-is, "three
  things it measures", results-at-a-glance table, field notes, native-reviewer
  call); added `docs/README.md` index, `docs/BUILDORADO_PROBE.md` field note, a
  CONTRIBUTING release checklist + new-language authoring guide, and a markdown
  link-checker test. Attribution normalized to **SEATECHONE LLC** everywhere;
  added `CITATION.cff` and project authors.
### Note
- No library behaviour changed. This release re-cuts the v2 dataset assets so
  `guardmeter dataset fetch agentic-v2` serves the review-signed `data.jsonl`
  (the fetch tag moves to v0.10.2).

## [0.10.1] - 2026-09-26
### Data
- **Agentic dataset v2 expanded to 14 authored languages (from 3), 1810 rows.**
  Added 11 languages — German, French, Portuguese, Arabic, Hindi, Chinese,
  Japanese, Russian, Turkish, Indonesian, Korean — each authored natively (not
  translated) across all 14 attack families (≥6 unsafe + ≥3 benign per family,
  ≥5 borderline; ~131 rows/language). Each ships an authoring note under
  `docs/languages/<code>.md` (registers, romanization, script traps). Every new
  row is `review_status: "authored"`; **only en and fa are native-reviewed
  (samvardani)** — the other 12 authored languages await native review, and 10
  Tier-1 languages remain draft.
- **Results on the full v2** (`docs/MULTILINGUAL_RESULTS.md`): injection-heuristic
  vs anthropic (`claude-sonnet-4-5`), no tuning. Strict: anthropic recall 0.948,
  FPR 0.051, F1 0.961, hijack 1.3%. Recall-parity gap 0.073 across all authored
  languages vs 0.030 across the native-reviewed subset (up from a 3-language gap
  of 0.018 in 0.10.0).
### Fixed
- `native_script_ratio` counts a language's auxiliary scripts (Han+kana for
  Japanese, Hangul+Han for Korean) so natural Japanese/Korean rows pass the
  per-language script-ratio check; the validator now uses it. zh/Latin/RTL
  languages are unaffected.

## [0.10.0] - 2026-09-26
### Added
- **Multilingual: language is a first-class dimension.**
  - `guardmeter/core/languages.py`: a registry of 24 Tier-1 languages (script,
    direction, family, Unicode ranges, market registers) with script-histogram
    language detection (`guardmeter languages`).
  - **Six cross-lingual attack families** — `script_mixing`, `transliteration`,
    `language_switch`, `bidi_override`, `translate_then_follow`,
    `cultural_authority` — alongside the eight monolingual ones. Bidi controls
    are revealed as `⟨RLO⟩`-style tokens (never stripped/rendered raw);
    zero-width runs and full-width homoglyphs are NFKC-folded before matching.
  - **Unicode-aware guards**: `injection-heuristic` carries markers for 20+
    languages and fires on bidi/zero-width abuse; LLM adapters use a
    language-agnostic system prompt.
  - **Per-language + parity gates**: `gate.json` accepts per-language
    `min_recall`/`max_fpr`/`min_f1`, `required_languages`, and a
    `language_parity` block (fails when best−worst recall gap exceeds a bound).
  - **RTL-correct reports**: HTML report/dashboard render RTL and CJK/Thai/
    Devanagari with `<bdi dir="auto">` and a broad font stack; per-language view.
  - **Native-reviewer workflow**: rows start `authored`; only a named native
    reviewer promotes to `reviewed`. Suites and datasets report *partial*
    validation by language (`validated: partial (languages: …)`).
  - **Agentic Attack Dataset v2 (multilingual)**: 371 rows in English, Spanish,
    and Farsi (128/122/121), authored natively, across all 14 families. Ships a
    card, changelog, CC-BY-4.0 licence, and a multilingual `gate.agentic.json`.
    Fetch with `guardmeter dataset fetch agentic-v2`. **en and fa are natively
    reviewed; es is authored-only (provisional).** The registry defines 24
    languages; the remaining 21 are scaffolded, awaiting native authors.
  - **`suites/multilingual-agent-basics.yaml`**: 54 scenarios across 6 languages
    (en/es/fa/pt/de/ru); en and fa reviewed, the rest awaiting native review.
  - **Results**: `docs/MULTILINGUAL_RESULTS.md` — injection-heuristic vs
    anthropic (`claude-sonnet-4-5`) on v2. Strict: anthropic recall 0.925,
    FPR 0.068, F1 0.942, hijack 1.3%; per-language recall en 0.917 / es 0.923 /
    fa 0.935, recall-parity gap 0.018. Baseline heuristic recall 0.172.

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
