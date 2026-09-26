# GuardMeter Agentic Attack Dataset — v2 (multilingual)

A multilingual extension of [v1](../v1/): agentic prompt-injection attempts and
hard benign look-alikes, **authored in each language** (not translated from
English), across 14 attack families — the 8 v1 families plus 6 cross-lingual
families (see [../../../docs/ATTACK_FAMILIES.md](../../../docs/ATTACK_FAMILIES.md)).

> **Review status — read this first.** Authored so far: **en**, **es**, **pt**, **fr**, **de**, **ar**, **fa**, **hi**, **zh**, **ja**. Every row is `review_status: "authored"` and **none is native-reviewed yet** — no language is "released". The remaining 14 Tier-1 languages are staged in `MANIFEST.json` at "draft", awaiting authors and native reviewers.
> See [../../../docs/REVIEWER_GUIDE.md](../../../docs/REVIEWER_GUIDE.md)
> — reviewers are named here and credited under CC-BY-4.0.

## Composition (authored languages)

| Language | Rows | Unsafe | Benign | Borderline | Families | Status |
|---|---|---|---|---|---|---|
| en | 128 | 78 | 44 | 6 | 14/14 | authored |
| es | 122 | 73 | 44 | 5 | 14/14 | authored |
| pt | 131 | 84 | 42 | 5 | 14/14 | authored |
| fr | 131 | 84 | 42 | 5 | 14/14 | authored |
| de | 129 | 84 | 40 | 5 | 14/14 | authored |
| ar | 131 | 84 | 42 | 5 | 14/14 | authored |
| fa | 121 | 72 | 44 | 5 | 14/14 | authored |
| hi | 131 | 84 | 42 | 5 | 14/14 | authored |
| zh | 131 | 84 | 42 | 5 | 14/14 | authored |
| ja | 131 | 84 | 42 | 5 | 14/14 | authored |

**Total: 1286** · en 128 · es 122 · pt 131 · fr 131 · de 129 · ar 131 · fa 121 · hi 131 · zh 131 · ja 131

## Attack families

The 8 v1 families (direct_override, indirect_injection, exfiltration,
tool_misuse, authority_spoof, persona_jailbreak, encoded, multi_turn) and 6
cross-lingual families: script_mixing, transliteration, language_switch,
bidi_override, translate_then_follow, cultural_authority. Each family has benign
look-alikes that share its surface features.

## Collection process

Rows are authored per language (registers local to the language's main markets),
validated with `guardmeter dataset validate` (schema, per-language script
ratios, exact/near duplicates within a language, a cross-language template check,
decoded-payload sanity, label/target/context consistency), then read a second
time as a sceptical native-ish reader. No row is copied from external jailbreak
sources; no real people, companies, credentials, PII, working exploits, or
malware. Injection targets are generic tools.

## Reviewer status

| Language | Status | Rows | Native reviewers |
|---|---|---|---|
| en | authored — awaiting native review | 128 | — |
| es | authored — awaiting native review | 122 | — |
| pt | authored — awaiting native review | 131 | — |
| fr | authored — awaiting native review | 131 | — |
| de | authored — awaiting native review | 129 | — |
| ar | authored — awaiting native review | 131 | — |
| fa | authored — awaiting native review | 121 | — |
| hi | authored — awaiting native review | 131 | — |
| zh | authored — awaiting native review | 131 | — |
| ja | authored — awaiting native review | 131 | — |
| (14 others) | draft — awaiting authoring + review | 0 | — |

## Licence and versioning

CC-BY-4.0 (see LICENSE). v2 is a working, growing dataset: languages are added
and reviewed over time; v1 stays frozen and independently fetchable. Cite as
"GuardMeter Agentic Attack Dataset v2", https://github.com/samvardani/guardmeter.
