# Agent Release Check — delivery playbook

One page to run a paid **$1,500 Agent Release Check**. The customer keeps their
keys, their staging environment, and the final decision. You deliver a reviewed
suite and a one-page decision they can rerun themselves.

## Scope (state this in the offer, hold this line)

- **≤ 30 scenarios**, one workflow.
- **3 repeats** per scenario.
- **1 rerun** of the candidate after fixes.
- **≤ 180 executions per version** (30 scenarios × 3 repeats × 2 = 180 with headroom).
- Deliverable: a reviewed suite + one decision report (APPROVE / BLOCK / INCONCLUSIVE).
- **Not** a safety certificate. The report states coverage, errors, and disputes plainly.

## Intake checklist (before you start)

- [ ] The one workflow under test is named and its business rules written down.
- [ ] A **staging** endpoint (OpenAI-compatible) that you can call, with the
      customer's own keys held by the customer (you never store their keys).
- [ ] **10–30 acceptance cases** drafted with the customer.
- [ ] **Critical cases agreed up front** — which failures must block a release.
- [ ] Baseline and candidate model/version identified.
- [ ] Native reviewer arranged for any non-English case (sign-off is per language).

## Day by day

**Day 1 — scope & scaffold.**
```bash
pip install guardmeter
guardmeter init --agent        # writes agent-release-check/{starter.yaml,gate.json,README.md}
```
Replace the starter scenarios with the customer's cases. Mark the agreed
critical cases `critical: true`. Set the gate policy in `gate.json`
(min pass rate, required categories, `max_error_rate: 0`, `max_judge_disagree_rate: 0`).

**Day 2 — author & audit.** Finish the suite. Every case must fail against a
do-nothing target (pair each negative check with a positive one). Confirm:
```bash
guardmeter scenarios audit agent-release-check/starter.yaml   # 0 cannot-fail, 0 unreviewed
```

**Day 3 — run both versions** against the customer's staging endpoint:
```bash
guardmeter scenarios run agent-release-check/starter.yaml \
  --endpoint <STAGING_URL> --model <BASELINE> --key-env CUSTOMER_KEY \
  --repeats 3 --store runs.db
guardmeter scenarios run agent-release-check/starter.yaml \
  --endpoint <STAGING_URL> --model <CANDIDATE> --key-env CUSTOMER_KEY \
  --repeats 3 --store runs.db
```

**Day 4 — decide & review.** Produce the one-page decision and read every
critical regression and dispute yourself before sending:
```bash
guardmeter decide --baseline <RUN_A> --candidate <RUN_B> \
  --policy agent-release-check/gate.json --out decision.html
```
Exit code: 0 APPROVE, 1 BLOCK, 2 INCONCLUSIVE. If INCONCLUSIVE (errors or
disputed critical cases), resolve the disputes or fix the endpoint and rerun —
never ship an inconclusive result as a pass.

**Day 5 — one rerun (if needed) & handoff.** After the customer's fix, rerun the
candidate once and regenerate the decision.

## What the customer keeps

- The **suite** (`starter.yaml`) and **gate policy** (`gate.json`) — theirs to rerun.
- The **decision report** (`decision.html`) — APPROVE/BLOCK/INCONCLUSIVE with the
  critical regressions, coverage, disputes, latency, the acceptance policy in
  plain words, and the exact rerun command + suite hash + both run ids.
- The **run evidence** (the two run JSONs), scoped to their project only.

You keep nothing of theirs: no keys, no traffic, no data beyond what they approve
for the handoff.

## Recurring checks in the customer's CI (optional)

Once the suite is theirs, the decision can run on every pull request. The
`.github/actions/scenarios` action decides from two **run artifacts** (baseline
vs candidate scenario-run JSON) — it never needs the customer's endpoint keys,
because the runs were already produced upstream.

```yaml
permissions:
  pull-requests: write   # to post the decision comment
jobs:
  release-decision:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      # ... produce baseline-run.json and candidate-run.json however you run the suite ...
      - uses: your-org/guardmeter/.github/actions/scenarios@v0.14.0
        with:
          baseline-run: baseline-run.json
          candidate-run: candidate-run.json
          policy: agent-release-check/gate.json
```

It posts **one** PR comment (found by a marker and edited in place on reruns)
with the verdict, failing critical case ids, INCONCLUSIVE reasons, and the rerun
command, and **fails the check on BLOCK or INCONCLUSIVE**. On fork PRs the comment
step is skipped (the token is read-only), but the check still fails on a bad
verdict.

## Boundaries to say out loud

- "Thirty cases don't prove your agent is safe. This checks agreed business
  behaviour on a stated scope and versions, and reports gaps, errors, and
  unresolved judgments."
- "Native sign-off is per language; today only Farsi is native-signed. Any other
  language is reviewed non-native unless you pay for a competent reviewer."
- Cost per successful task is shown only when token usage **and** a price are
  provided; otherwise it reads **unknown** and is never estimated.

See `docs/samples/decision-sample.html` for a sample decision (local open
models, not a customer).
