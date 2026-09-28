# Agent release check — starter

Five reviewed acceptance cases for a support/sales agent, plus a gate policy.
This folder was written by `guardmeter init --agent`. You do **not** need to
clone the GuardMeter repo to use it.

## Files

- `starter.yaml` — five scenarios (en + fa): valid structured lead, correct
  tool arguments, ignored injected instruction, human handoff, and a
  Farsi task. Two are marked `critical: true`.
- `gate.json` — the acceptance policy (min pass rate, required categories,
  zero errors/disputes, ≥5 evaluable scenarios).
- this README.

## Run it

Point it at any OpenAI-compatible endpoint. Locally with Ollama:

```bash
# baseline and candidate are the two model versions you're deciding between
guardmeter scenarios run starter.yaml \
  --endpoint http://localhost:11434/v1 --model llama3.2:3b \
  --repeats 3 --store runs.db

guardmeter scenarios run starter.yaml \
  --endpoint http://localhost:11434/v1 --model qwen3:8b \
  --repeats 3 --store runs.db
```

Then turn the two runs into a one-page decision:

```bash
guardmeter decide --baseline <BASELINE_RUN_ID> --candidate <CANDIDATE_RUN_ID> \
  --policy gate.json --out decision.html
```

`decide` returns **APPROVE**, **BLOCK**, or **INCONCLUSIVE**. A new failure on a
critical case blocks approval even if the average went up; an error or dispute on
a critical case makes the decision inconclusive.

## Make it yours

Before you rely on this for a real release, replace the endpoints, tools, and
text with your own workflow's, agree the critical cases with the customer up
front, and confirm the suite still audits clean:

```bash
guardmeter scenarios audit starter.yaml
```
