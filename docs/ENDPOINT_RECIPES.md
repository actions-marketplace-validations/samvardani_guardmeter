# Endpoint recipes

How to point a GuardMeter scenario suite at your workflow. Every recipe below is
verified against a local stub server in
[`tests/guardmeter/test_endpoint_recipes.py`](../tests/guardmeter/test_endpoint_recipes.py).

## The one contract

The scenario target (`--endpoint`) speaks the **OpenAI chat-completions** shape.
For each scenario it POSTs to `<endpoint>/chat/completions`:

```json
{ "model": "<model>", "messages": [ ... ], "temperature": 0,
  "tools": [ ... ]  // present only when the scenario supplies tools
}
```

and reads this back:

```json
{ "choices": [ { "message": {
      "content": "the agent's final output (string, or null if it only called tools)",
      "tool_calls": [ { "function": { "name": "create_lead",
                                      "arguments": "{\"email\":\"a@b.com\"}" } } ]
  } } ],
  "usage": { "prompt_tokens": 12, "completion_tokens": 7 } }
```

What GuardMeter maps from the response:

| Scenario need | Response field |
|---|---|
| final output | `choices[0].message.content` |
| confirmed tool events | `choices[0].message.tool_calls[].function.{name,arguments}` |
| requested tools | sent in the request `tools` (the scenario's `input.tools`) |
| errors | any non-2xx HTTP status → recorded as an error, never a pass |
| usage | `usage.prompt_tokens` / `usage.completion_tokens` |

> **What's missing (by design, not built here):** GuardMeter does **not** remap
> response fields. A workflow that answers with its own schema (e.g.
> `{"output": "..."}`) is rejected with "no choices" — see
> `test_non_openai_shape_is_not_understood`. So every recipe below is really
> "make your workflow return the OpenAI shape above." Building a configurable
> response-mapping target is out of scope; if you need it, that's the gap.

## Recipe 1 — any OpenAI-compatible endpoint

Ollama, vLLM, LM Studio, OpenAI, Together, Groq, NVIDIA, Opod, … all already
speak this shape.

```bash
guardmeter scenarios run suite.yaml \
  --endpoint https://your-host/v1 --model your-model --key-env YOUR_KEY --repeats 3
```

## Recipe 2 — an n8n webhook workflow

1. **Webhook** node (POST), path e.g. `/chat/completions` → your agent → a
   **Respond to Webhook** node.
2. In the final node, build an OpenAI-shaped body: put the agent's answer in
   `choices[0].message.content`; if it called tools, add
   `choices[0].message.tool_calls`; include `usage` if you track tokens.
3. Point the suite at the webhook base URL:

```bash
guardmeter scenarios run suite.yaml --endpoint https://your-n8n/webhook --model n8n-agent
```

(The suite appends `/chat/completions`; set the Webhook path to match, or use a
base whose `/chat/completions` is your webhook.)

## Recipe 3 — a Make (Integromat) scenario webhook

1. **Custom webhook** trigger → your scenario → a **Webhook response** module.
2. In the response module, return the OpenAI-shaped JSON (same three fields:
   `choices[0].message.content`, optional `tool_calls`, optional `usage`) with
   `Content-Type: application/json`.
3. Run against the Make webhook URL as `--endpoint`.

## Recipe 4 — a generic HTTP endpoint

Any service works if it accepts the POST body above and returns the OpenAI-shaped
response above. The mapping to implement on your side:

- **final output** → `choices[0].message.content`
- **tool calls your agent made** → `choices[0].message.tool_calls[].function.{name,arguments}`
  (arguments is a JSON **string**)
- **errors** → return a non-2xx status; GuardMeter records it as an error and
  excludes it from pass/fail (never a silent pass)
- **usage** → `usage.prompt_tokens` / `usage.completion_tokens` (enables cost per
  successful task in `guardmeter decide`)

If your service can't emit this shape, put a thin translator in front of it (a
few lines in the same webhook/function that already runs your agent). GuardMeter
will not do that translation for you.
