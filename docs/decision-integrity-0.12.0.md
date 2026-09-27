# Decision integrity — response to the 2026-09-26 independent review

Release **0.12.0**. The review is at `GuardMeter-Independent-Review-2026-09-26.md`
(§4, items 1–10; its links pin files/lines at commit `6d1a30b`). Every defect
below was first reproduced with a failing test, then fixed. No new guards or
datasets were added in this release — it is entirely about not letting an
incomplete or untrustworthy evaluation read as a pass.

## Defects — reproduced, then fixed

Reproduction tests live in `tests/guardmeter/test_decision_integrity.py` unless
noted. Each asserts the *correct* behaviour, so it fails against the pre-fix code.

| # | Defect | Reproduced by | Fixed by |
|---|--------|---------------|----------|
| 1 | Empty scenario suite → PASS | `test_empty_suite_is_not_pass` | `3118149` |
| 2 | All-disputed run → PASS | `test_unresolved_disputes_are_not_pass` | `3118149` |
| 3 | Missing required category → PASS | `test_missing_required_category_is_not_pass` | `3118149` |
| 4 | All-error audit reported valid | `test_all_error_audit_not_validated` | `3118149` |
| 5 | Audit not bound to its suite | audit gains `suite_hash` / `audited_suite` | `3118149` |
| 6 | Language slices + case metadata lost in SQLite round trip | `test_language_slices_survive_sqlite_roundtrip`, `test_case_id_and_context_survive_sqlite_roundtrip` | `69500fe` (slices), `f30c9a4` (`case_id`/`context`) |
| 7 | UI badge renders `prediction='error'` as PASS | `VerdictChip` in `components/ui.js` | `e561ad0` |
| 8 | Unknown HTTP verdict / unparseable Llama Guard reply → not an error | `test_http_guard_unknown_verdict_is_error`, `test_llamaguard_unparseable_reply_is_error` | `c7ce91f` |
| 9 | McNemar counts an errored pair as a correct benign | `test_mcnemar_excludes_errored_pairs` | `69500fe`; count now reported `2b52174` |
| 10 | Gate can pick its own latest run as "previous" | `test_latest_run_can_exclude_current`, `test_compare_runs_rejects_self_comparison` | `e561ad0`, `2b52174` |
| 11 | Checkpoints keyed only by guard + row index | `test_resume_checkpoint_bound_to_dataset` | `fe2adbf` |
| 12 | Evidence/snapshot export leaks other projects' history | `test_snapshot_scoped_to_allowlist` | `ac8395f` |

None of the reported defects failed to reproduce; every one had a concrete
failing test before its fix.

## Review sections 1–5

| Section | What changed | Commit(s) |
|---------|--------------|-----------|
| §1 PASS/FAIL/INCONCLUSIVE everywhere | Three-state verdict in scenario gate, CLI, hook, dashboard, report, Action; insufficient coverage / errors over threshold / unresolved disputes → INCONCLUSIVE, never PASS | `3118149` |
| §2 Strict output validation | `jsonschema` (runtime dep, floor-pinned `>=4.0`) replaces the minimal checker; unknown/null verdicts, missing judge verdict, invalid enum, malformed tool-arg JSON, and missing token usage are errors | `b6ca594`, `c7ce91f` |
| §3 Explicit run identity | `--rows-from` keys on stable **case id + context hash** (legacy runs fall back to text matching, labelled "matched by text (legacy)", never mixed); self-comparison forbidden; resume checkpoint bound to the dataset fingerprint; significance reports excluded errored pairs | `f30c9a4`, `2b52174`, `fe2adbf` |
| §4 One canonical gate result | Report routes through `GateChecker` instead of recomputing a simplified pass/fail; all metrics (incl. language slices, `case_id`, `context`) round-trip through SQLite | `97980b9`, `69500fe`, `f30c9a4` |
| §5 Scoped export | Snapshot/evidence export takes an explicit run/dataset/scenario allowlist; verified with two synthetic customers (no cross-leak); "signed" → "hash-manifested" | `ac8395f`, `f0e042f` |

## §6 Claims removed / corrected

Commit `f0e042f` (plus README wording):

- **"Signed" evidence pack → "hash-manifested."** The bundle carries a SHA-256
  manifest, not a cryptographic signature; the docs no longer imply otherwise.
- **Language review status is honest.** `en` rows are **reviewed
  (non-native)**; **only `fa` carries native sign-off.** The dataset card and
  CHANGELOG state exactly that. 14 languages are authored; native sign-off = `fa`
  only.
- **Review workflow can't over-claim.** Packets no longer default to *accept*
  (rows are `pending` until an explicit decision); a non-native reviewer can no
  longer mark rows "native-reviewed".
- **Leaderboard prose** no longer contradicts its own scenario-error column.

## Note: NVIDIA v2 leaderboard job

The detached `nvidia-v2` scoring job against the free hosted tier was stopped
(`pkill -f nvidia-v2`) rather than run to completion — the free tier could not
sustain the full 14-language v2 sweep. Its **partial run file is left in place**
at `runs/nvidia-v2-nemotron35.jsonl` (not resumed, not published as a result).
No leaderboard number in this release depends on it.
