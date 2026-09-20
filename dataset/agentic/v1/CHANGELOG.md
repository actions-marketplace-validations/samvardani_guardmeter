# Agentic Attack Dataset — Changelog

## [v1.0] - 2026-09-20
- Initial release: 421 rows across 8 attack families (direct_override,
  indirect_injection, exfiltration, tool_misuse, authority_spoof,
  persona_jailbreak, encoded, multi_turn) plus 15 borderline cases.
- Bilingual: 303 English, 118 Farsi (Farsi authored natively, not translated;
  absent from the ASCII-only `encoded` family).
- 301 unsafe, 105 benign look-alikes, 15 borderline.
- Every row authored fresh (no external jailbreak sources); single-reviewer
  ("self-reviewed"); validated with `guardmeter dataset validate` (schema,
  duplicates, near-duplicates, language ratios, decoded payloads, label/target
  and context consistency).

Versioning: v1 is frozen. Corrections go to v1.1; breaking changes to v2.
