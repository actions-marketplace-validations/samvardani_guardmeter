# GuardMeter docs

Index of everything under `docs/`. Start with the [project README](../README.md).

## Results & field notes
- [AGENTIC_RESULTS.md](AGENTIC_RESULTS.md) — shipped guards and the `anthropic` adapter on the Agentic Attack Dataset v1; the honest injection baseline and adapter evolution.
- [MULTILINGUAL_RESULTS.md](MULTILINGUAL_RESULTS.md) — `injection-heuristic` vs `anthropic` on the 14-language v2 dataset; per-language recall/FPR/F1, hijack rate, and the recall-parity gap (reviewed vs authored).
- [OPOD_SCENARIO_RESULTS.md](OPOD_SCENARIO_RESULTS.md) — endpoint-behaviour scenarios run against two locally-served Opod models (tool use, leak resistance, format, latency).
- [BUILDORADO_PROBE.md](BUILDORADO_PROBE.md) — field note: ten hand-run probes of an AI-built Buildorado workflow (unpublished, our own account).

## Reference
- [ATTACK_FAMILIES.md](ATTACK_FAMILIES.md) — the 14 attack families (8 monolingual + 6 cross-lingual) with definitions and examples.
- [REVIEWER_GUIDE.md](REVIEWER_GUIDE.md) — how a native reviewer signs off a language through the review workflow.
- [OPOD_INTEGRATION.md](OPOD_INTEGRATION.md) — wiring the gate's rollout webhook into an Opod (or any) deployment.
- [languages/](languages/) — per-language authoring notes (registers, romanization, script traps) — one file per authored language.

## Assets
- [images/](images/) — screenshots used in the README and reports.
