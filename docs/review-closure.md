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
| P6 | Narrow onboarding path reusing the runner; starter ships in the wheel; thin endpoint mapping | **done** | `b41ea35` (starter + `init --agent`, clean-venv CI job); `c7d7a77` (endpoint recipes) | `test_cli.py::test_init_agent_writes_starter`; `test_endpoint_recipes.py` (OpenAI-shaped webhook consumed; non-OpenAI shape rejected — the documented gap). |
| P7 | Turn comparison into a one-page decision with measured cost per successful task | **done** | `0750d21` (`guardmeter decide`); `feec25e` (usage + `--price-file`) | `test_decide.py::test_cost_uses_prompt_and_completion_with_dated_price`, `::test_judge_cost_excluded_when_judge_unpriced`, `::test_cost_unknown_without_prices`; `test_scenario_runner.py::test_judge_disagree` (judge usage captured). Target prompt+completion and judge prompt/completion/retries now round-trip; cost is "unknown" without usage or a price, never estimated. |
| P8 | Complete PR delivery (fix Action version default; explicit baseline/candidate artifacts; one updateable PR comment; no fork-PR secrets) | **done** | `544020c` | `test_action.py` (version default fixed; baseline/candidate artifact inputs; decide-driven; fork-PR guard on the comment step; marker matches the renderer); `test_decide.py::test_decide_from_run_files`, `::test_pr_comment_*`. Fails the check on BLOCK/INCONCLUSIVE. |
| P9 | Auditable language review (per-language counts from the manifest; release refused without native sign-off) | **done** | `f0e042f` (no default-accept; native flag recorded); `feec25e` (native enforcement + `languages status`) | `test_review_workflow.py::test_release_refused_without_native_signoff`, `::test_native_signoff_and_manifest_counts`; `test_cli.py::test_languages_status_reads_manifest`. `can_release` now requires a native sign-off covering ≥90% of rows (en refused, fa allowed). WP5 documents the add-a-language flow (`docs/ADD_A_LANGUAGE.md`). |
| P10 | Remove unsupported promises; keep the leaderboard as an evidence appendix, not the sales reason | **done** | `f0e042f` (dropped "only non-English", "signed", "certified"; fixed leaderboard prose); `8775ef1` (evidence appendix) | claims audit in 0.12.0; `docs/EVIDENCE.md` ("methods and evidence, not the reason to buy"; each result carries dataset/policy/hosting/date) + `docs/site-handoff-evidence.md`. |
| P11 | Publish five runnable acceptance cases; asynchronous purchase flow | **done (repo side)** | `b41ea35` (starter suite = the five cases: valid structured lead, correct tool args, ignored injected instruction, human handoff, required-language task) | `test_cli.py::test_init_agent_writes_starter` asserts the five cases and the two critical ones. The purchase/checkout flow lives on the website (out of this repo). |
| P12 | Defer hosted SaaS/auth, dataset marketplace, broad compliance packaging | **deferred** | — | Intentionally not built (per the review and the 0.14.0 scope). No tenancy, auth, or marketplace code added. |

## Claims from the review that were still true, now closed

- **P9 native enforcement** was not real before 0.14.0 (the release threshold
  counted non-native reviews). Closed in `feec25e`: `can_release` now requires a
  native reviewer sign-off, and `test_release_refused_without_native_signoff`
  proves a non-native language is refused.

As of 0.14.0, every item is **done** or **deferred** (P12). Nothing the review
flagged remains open.
