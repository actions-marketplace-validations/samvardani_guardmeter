# GuardMeter Agentic Attack Dataset — v2 (multilingual)

A multilingual extension of [v1](../v1/): agentic prompt-injection attempts and
hard benign look-alikes, **authored in each language** (not translated from
English), across 14 attack families — the 8 v1 families plus 6 cross-lingual
families (see [../../../docs/ATTACK_FAMILIES.md](../../../docs/ATTACK_FAMILIES.md)).

> **Review status — read this first.** Every row is `review_status: "authored"`.
> Authoring means the rows were composed by reasoning in the language; it does
> **not** mean they read as native. Only **en, es, fa** are authored so far, and
> **none is native-reviewed yet** — no language is "released". The remaining 21
> Tier-1 languages are staged in `MANIFEST.json` at "draft", awaiting authors
> and native reviewers. See [../../../docs/REVIEWER_GUIDE.md](../../../docs/REVIEWER_GUIDE.md)
> — reviewers are named here and credited under CC-BY-4.0.

## Composition (authored languages)

| Family | en unsafe | en benign | en borderline | es unsafe | es benign | es borderline | fa unsafe | fa benign | fa borderline | total |
|---|---|---|---|---|---|---|---|---|---|---|
| authority_spoof | 5 | 3 | 1 | 5 | 3 | 1 | 5 | 3 | 1 | 27 |
| bidi_override | 5 | 3 | 0 | 5 | 3 | 0 | 5 | 3 | 0 | 24 |
| cultural_authority | 5 | 3 | 0 | 5 | 3 | 0 | 5 | 3 | 0 | 24 |
| direct_override | 8 | 4 | 1 | 8 | 4 | 1 | 8 | 4 | 1 | 39 |
| encoded | 6 | 4 | 0 | 5 | 4 | 0 | 4 | 4 | 0 | 27 |
| exfiltration | 6 | 4 | 1 | 6 | 4 | 0 | 6 | 4 | 0 | 31 |
| indirect_injection | 5 | 2 | 1 | 4 | 2 | 1 | 4 | 2 | 1 | 22 |
| language_switch | 6 | 3 | 0 | 5 | 3 | 0 | 5 | 3 | 0 | 25 |
| multi_turn | 4 | 2 | 1 | 4 | 2 | 1 | 4 | 2 | 1 | 21 |
| persona_jailbreak | 5 | 3 | 1 | 5 | 3 | 1 | 5 | 3 | 1 | 27 |
| script_mixing | 6 | 3 | 0 | 5 | 3 | 0 | 5 | 3 | 0 | 25 |
| tool_misuse | 6 | 4 | 0 | 6 | 4 | 0 | 6 | 4 | 0 | 30 |
| translate_then_follow | 5 | 3 | 0 | 5 | 3 | 0 | 5 | 3 | 0 | 24 |
| transliteration | 6 | 3 | 0 | 5 | 3 | 0 | 5 | 3 | 0 | 25 |

**Total: 371** · en 128 · es 122 · fa 121

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
| fa | authored — awaiting native review | 121 | — |
| (21 others) | draft — awaiting authoring + review | 0 | — |

## Licence and versioning

CC-BY-4.0 (see LICENSE). v2 is a working, growing dataset: languages are added
and reviewed over time; v1 stays frozen and independently fetchable. Cite as
"GuardMeter Agentic Attack Dataset v2", https://github.com/samvardani/guardmeter.
