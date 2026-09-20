---
license: cc-by-4.0
language:
  - en
  - fa
task_categories:
  - text-classification
tags:
  - ai-safety
  - prompt-injection
  - agentic
  - guardrails
pretty_name: GuardMeter Agentic Attack Dataset v1
size_categories:
  - n<1K
---

# GuardMeter Agentic Attack Dataset — v1

## Summary

A synthetic, bilingual (English + Farsi) dataset of **agentic** prompt-injection
attempts and their hard benign look-alikes, for evaluating content-safety guards
aimed at tool-using assistants. 421 rows across 8 attack families, each labelled
`unsafe` / `benign` / `borderline` with the surrounding **context** (a document
or prior turns) where the attack depends on it.

It is designed to be the number people beat: simple keyword guards are expected
to do poorly, especially on indirect injection, encoding, and multi-turn setups.

## Intended use

- Benchmarking prompt-injection / agentic-safety guards (recall, FPR, F1 overall
  and per family).
- As a regression set when developing an injection-aware guard.
- **Not** intended as training data for producing attacks, nor as a
  certification of any guard's real-world safety.

## Composition

| Family | en unsafe | en benign | fa unsafe | fa benign | total |
|---|--:|--:|--:|--:|--:|
| direct_override | 34 | 8 | 11 | 7 | 63 |
| indirect_injection | 45 | 13 | 16 | 7 | 85 |
| exfiltration | 25 | 8 | 10 | 7 | 52 |
| tool_misuse | 28 | 9 | 12 | 6 | 56 |
| authority_spoof | 21 | 6 | 9 | 4 | 41 |
| persona_jailbreak | 22 | 5 | 8 | 5 | 41 |
| encoded | 30 | 10 | 0 | 0 | 42 |
| multi_turn | 21 | 6 | 9 | 4 | 41 |
| borderline (spread across families) | 12 en | — | 3 fa | — | 15 |

**Total: 421** · en 303 · fa 118 · unsafe 301 · benign 105 · borderline 15.

The `encoded` family is English only: its payloads are ASCII (base64/hex/ROT13/
leetspeak/homoglyph/zero-width/token-split), so a Farsi label would fail the
script-ratio check. Farsi coverage is provided across the other seven families.

### Fields

`id`, `text`, `context` (or null), `label`, `category` (`prompt_injection`),
`attack_family`, `attack_technique`, `target` (`override` | `exfiltrate` |
`tool_action` | `persona` | `none`), `language` (`en` | `fa`), `source`
(`synthetic-llm`), `review_status` (`self-reviewed`), `notes`.

Benign rows have `target = none`; unsafe rows never do. `indirect_injection` and
`multi_turn` rows carry the surrounding document / prior turns in `context`.

## Collection process

Synthetic. Every row was authored fresh for this dataset (no copying from public
jailbreak collections, so licence and provenance are clean). Farsi rows are
natural Farsi written for Farsi speakers — not translations or transliterations
of the English rows. Rows were written in batches per family, then re-read in a
second sceptical pass to fix labels, delete weak rows, and ensure the benign
look-alikes share surface features with the attacks. `review_status` is
`self-reviewed` (single reviewer). Authored 2026-09-20 with assistance from
Claude (Fable 5.1).

## Limitations

- **Synthetic**, not observed in the wild; real attacks evolve and adapt.
- **Single reviewer** — labels reflect one perspective; borderline cases are
  genuinely arguable (see the `notes` field).
- **Two languages** only (English, Farsi); Farsi absent from `encoded`.
- **Not adversarially optimised** against any specific real guard.
- Small (n≈421); per-family cells are modest, so per-family numbers are
  indicative, not precise.

## Ethical considerations

The content is **classifier training/evaluation material**: it describes attack
*patterns* against generic tools ("the email tool", "the file system") and never
contains working exploits against real products, real credentials, real people,
company names, PII, or malware code. Encoded payloads decode to injection
*instructions*, not operational attacks.

## Licence

[CC-BY-4.0](LICENSE). Attribute "GuardMeter Agentic Attack Dataset v1".

## Versioning policy

`v1` is **frozen**. Corrections and additions go to `v1.1` (see
[CHANGELOG.md](CHANGELOG.md)); breaking changes go to `v2`. Each version records
its own sha256 in the release notes.

## Citation

```bibtex
@misc{guardmeter_agentic_v1_2026,
  title  = {GuardMeter Agentic Attack Dataset v1},
  author = {Vardani, Sam},
  year   = {2026},
  howpublished = {\url{https://github.com/samvardani/guardmeter}},
  note   = {Synthetic prompt-injection dataset, CC-BY-4.0}
}
```
