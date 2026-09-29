# Independent review — closure audit

Tracks the 12 product-plan items (P1–P12) from
`GuardMeter-Independent-Review-2026-09-26.md` §4. Status is verified by running
the code and the named test, not by reading commit messages.

Legend: **done** = closed and proven by a test; **partial** = closed in part,
remainder tracked to a 0.14.0 work package; **deferred** = intentionally not
built.

| # | Item | Status | Closed by | Proven by |
|---|------|--------|-----------|-----------|
| P1 | Incomplete evaluation is an explicit blocking outcome (PASS/FAIL/INCONCLUSIVE; empty/all-disputed/missing-category/all-error never pass; audit bound to suite) | **done** | `3118149`, `69500fe` | `test_decision_integrity.py::test_empty_suite_is_not_pass`, `::test_missing_required_category_is_not_pass`, `::test_unresolved_disputes_are_not_pass`, `::test_all_error_audit_not_validated` |
| P2 | Validate outputs before scoring (unknown/null verdicts, unparseable LlamaGuard, jsonschema, malformed tool JSON, missing usage → error) | **done** | `b6ca594`, `c7ce91f` | `test_decision_integrity.py::test_http_guard_unknown_verdict_is_error`, `::test_llamaguard_unparseable_reply_is_error`; `test_scenario_assertions` jsonschema paths |
| P3 | Explicit, reproducible comparison identity (case-id `--rows-from`, no self-comparison, checkpoint bound to dataset, McNemar excludes errored pairs and reports the count) | **done** | `f30c9a4`, `2b52174`, `fe2adbf`, `69500fe` | `test_cli.py::test_rows_from_matcher_prefers_case_id_else_text`; `test_decision_integrity.py::test_case_id_and_context_survive_sqlite_roundtrip`, `::test_compare_runs_rejects_self_comparison`, `::test_resume_checkpoint_bound_to_dataset`, `::test_mcnemar_excludes_errored_pairs`, `::test_compare_reports_excluded_pairs` |
| P4 | One authoritative result; preserve metrics; error badge not PASS; leaderboard prose matches its error column | **done** | `97980b9`, `69500fe`, `e561ad0`, `f0e042f` | `test_decision_integrity.py::test_language_slices_survive_sqlite_roundtrip`; report routes through `GateChecker`; `docs/LEADERBOARD.md` scenario table shows Errors 1/4 and the prose says "not counted as passes" (no contradiction) |
| P5 | Export only the selected customer's evidence (allowlist; no cross-leak; "hash-manifested" not "signed") | **done** | `ac8395f`, `f0e042f` | `test_decision_integrity.py::test_snapshot_scoped_to_allowlist` (two synthetic customers, neither sees the other) |
| P6 | Narrow onboarding path reusing the runner; starter ships in the wheel; thin endpoint mapping | **partial → done in 0.14.0 (WP4)** | `b41ea35` (starter + `init --agent`, clean-venv CI job) | `test_cli.py::test_init_agent_writes_starter`. **Remaining:** endpoint recipes doc → `docs/ENDPOINT_RECIPES.md` (WP4). |
| P7 | Turn comparison into a one-page decision with measured cost per successful task | **partial → done in 0.14.0 (WP1)** | `0750d21` (`guardmeter decide`) | `test_decide.py` (verdict/critical overlay/render). **Gap found by running code:** endpoint `prompt_tokens` are parsed but dropped in `RunRecord`; judge token usage and retries are never captured; `decide` cost uses completion tokens only and has no price input. WP1 captures usage (prompt+completion, judge, retries) and adds `--price-file`. |
| P8 | Complete PR delivery (fix Action version default; explicit baseline/candidate artifacts; one updateable PR comment; no fork-PR secrets) | **partial → done in 0.14.0 (WP2)** | scenario Action exists (`.github/actions/scenarios/action.yml`) | **Gaps found:** `version` default is `0.9.0`; no baseline/candidate artifacts; no PR comment; gate step doesn't use `decide`. WP2 closes all. |
| P9 | Auditable language review (per-language counts from the manifest; release refused without native sign-off) | **partial → done in 0.14.0 (WP1/WP5)** | `f0e042f` (packet no longer default-accepts; native flag recorded) | `test_review_workflow.py`. **Still true from the review (verified live):** `reviewed_fraction()` counts any `review_status == "reviewed"` row regardless of the reviewer's `native` flag, and `can_release()`'s message says "by a native reviewer" but never checks it — so `en` (native=false) is releasable today. No `languages status` command exists. WP1 enforces native sign-off and adds the command; WP5 documents the add-a-language flow. |
| P10 | Remove unsupported promises; keep the leaderboard as an evidence appendix, not the sales reason | **partial → done in 0.14.0 (WP3)** | `f0e042f` (dropped "only non-English", "signed", "certified"; fixed leaderboard prose) | claims audit in 0.12.0. **Remaining:** a consolidated evidence appendix → `docs/EVIDENCE.md` + `docs/site-handoff-evidence.md` (WP3). |
| P11 | Publish five runnable acceptance cases; asynchronous purchase flow | **done (repo side)** | `b41ea35` (starter suite = the five cases: valid structured lead, correct tool args, ignored injected instruction, human handoff, required-language task) | `test_cli.py::test_init_agent_writes_starter` asserts the five cases and the two critical ones. The purchase/checkout flow lives on the website (out of this repo). |
| P12 | Defer hosted SaaS/auth, dataset marketplace, broad compliance packaging | **deferred** | — | Intentionally not built (per the review and the 0.14.0 scope). No tenancy, auth, or marketplace code added. |

## Claims from the review that are still true today (pre-0.14.0)

- **P9 native enforcement is not real yet.** The release helper's threshold counts
  non-native reviews, and its own message ("reviewed by a native reviewer") is
  not enforced. Fixed in WP1.

Everything else the review flagged has been reproduced and closed as noted above.
