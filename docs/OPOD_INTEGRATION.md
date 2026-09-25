# Wiring GuardMeter scenarios into an Opod rollout

[Opod](https://github.com/opod-io/opod-core) serves OpenAI-compatible endpoints
and can do "verified rollouts". Its default health step only proves a completion
round-trips. A GuardMeter scenario suite is the step that proves the endpoint
still **behaves** — calls the right tools, refuses the right requests, doesn't
leak the system prompt, stays under a latency budget — and rolls back if it
regressed.

GuardMeter treats an Opod endpoint like any OpenAI-compatible target: it POSTs
to `{endpoint}/chat/completions` with a Bearer key. Nothing Opod-specific is
required.

## Option A — the rollout webhook (synchronous)

Run `guardmeter serve` next to Opod and point the rollout's verification step at
its hook. The hook runs the suite, stores the run, gates it, and returns
pass/fail plus the list of scenarios that regressed from `pass` — synchronously,
so the orchestrator can roll back on a non-2xx or `"passed": false`.

```bash
# 1. Start the server (token-protected off loopback; bound to localhost here).
guardmeter serve --host 127.0.0.1 --port 8765 --hook-timeout 180

# 2. From the rollout's verify step, call the hook against the new endpoint.
curl -sS -X POST http://127.0.0.1:8765/api/hooks/rollout \
  -H "Content-Type: application/json" \
  -d '{
        "suite":    "suites/opod-agent-basics.yaml",
        "endpoint": "http://localhost:8080/v1",
        "model":    "qwen3-8b",
        "key_env":  "OPOD_KEY"
      }'
# → {"passed": true, "run_id": "…", "pass_rate": 0.93, "regressions": [], "gate_failures": []}
```

The server reads the API key from the named environment variable (`key_env`) —
the key is never sent in the request body. Gate thresholds come from the
`scenarios` block of the server's `./gate.json` (or built-in defaults). Bind off
loopback only with `GUARDMETER_TOKEN` set; then every `/api/*` call — the hook
included — needs `Authorization: Bearer $GUARDMETER_TOKEN`.

An orchestrator step, in shape:

```bash
resp=$(curl -sS -X POST "$GM/api/hooks/rollout" -H "Content-Type: application/json" -d "$payload")
echo "$resp" | jq -e '.passed == true' >/dev/null || { echo "rollback: $resp"; opod rollout undo; }
```

## Option B — GitHub Action (pre-deploy gate)

Gate a suite in CI before a rollout is even cut. The composite action runs the
suite, writes the step summary + a JUnit report, and fails the job on the gate.

```yaml
- uses: samvardani/guardmeter/.github/actions/scenarios@v0.9.0
  with:
    suite: suites/opod-agent-basics.yaml
    endpoint: ${{ secrets.OPOD_URL }}
    model: qwen3-8b
    key-env: OPOD_KEY          # the key is read from env, not passed inline
    gate-config: gate.json     # a `scenarios` block sets min_pass_rate etc.
  env:
    OPOD_KEY: ${{ secrets.OPOD_KEY }}
```

## Validate the suite first

A suite should be **validated** before it gates a rollout — no unreviewed
scenarios, no scenarios that pass against a broken model, flaky < 5%:

```bash
guardmeter scenarios audit suites/opod-agent-basics.yaml \
  --endpoint http://localhost:8080/v1 --model llama-3.2-3b --key-env OPOD_KEY
# writes validation.md; exits 1 until the suite is validated
```

`guardmeter gate --scenario-run …` refuses to gate an unvalidated suite unless
you pass `--allow-unvalidated`.
