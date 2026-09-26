# Attack families

GuardMeter's agentic datasets label each row with an **attack family** — the
mechanism of the attack, independent of harm category. The eight v1 families are
mechanism-general; the six v2 families are **cross-lingual**: they exploit
scripts, writing direction, romanization, and language boundaries. Every family
has *benign look-alikes* — legitimate messages that share the family's surface
features but carry no attack — so a guard can't pass by pattern-matching alone.

The canonical list is `guardmeter.data.schema.ATTACK_FAMILIES`; the validator
rejects any other value.

## v1 families (mechanism-general)

| Family | The attack |
|---|---|
| `direct_override` | "Ignore your instructions / reveal the system prompt" stated directly. |
| `indirect_injection` | The instruction rides inside a document or data the model is asked to process. |
| `exfiltration` | Getting the model/agent to send out secrets, keys, or other users' data. |
| `tool_misuse` | Coaxing an agent into a harmful tool call (send, delete, pay, post). |
| `authority_spoof` | Fake system/admin/developer messages claiming authority. |
| `persona_jailbreak` | Role-play framing ("you are DAN…") to shed the safety policy. |
| `encoded` | The payload is base64/hex/rot13/leetspeak/homoglyph/zero-width/token-split. |
| `multi_turn` | The attack is assembled across several conversational turns. |

## v2 families (cross-lingual)

### `script_mixing`
The instruction is split across scripts — a Latin sentence with the operative
verb in Arabic or Cyrillic, or **Cyrillic homoglyphs** inside otherwise-Latin
words (`іgnоrе` with Cyrillic `і`/`о`/`е`). Naive keyword filters tuned on one
script miss the payload.
**Benign look-alikes:** genuinely bilingual messages (a name or place in another
script), code-switching that carries no instruction.

### `transliteration`
The attack is written in a **romanization** of its language — Finglish (Persian
in Latin), Arabizi/Franco (Arabic with digits: `3` = ع, `7` = ح), Hinglish,
Romaji, Greeklish — so a filter keyed on the native script never sees it.
**Benign look-alikes:** ordinary romanized chat ("salam, chetori?"), a real
question typed in Finglish.

### `language_switch`
A benign-looking message that **switches language mid-text** and carries the
instruction in the second language — both directions (en→X and X→en). The first
clause lulls a monolingual filter; the payload is elsewhere.
**Benign look-alikes:** a bilingual speaker who greets in one language and asks
in another; a quote in a foreign language.

### `bidi_override`
**RTL/LTR override and isolate characters** (U+202A–U+202E, U+2066–U+2069) that
hide or reorder an instruction so the visible order differs from the logical
order; also **zero-width joiners** used abusively (vs. their legitimate use in
Persian, Arabic, and Hindi shaping).
**Benign look-alikes:** real RTL text with legitimate bidi marks, a filename with
a valid LRM, Persian text with correct ZWNJ. GuardMeter never renders these raw
(see `reveal_bidi`) — they are shown as `⟨RLO⟩`-style tokens.

### `translate_then_follow`
"Translate the following to X:" where the "text to translate" is actually an
**instruction**; or "summarize this document" where the document (often in
another language) **contains** the instruction. The task framing launders the
payload past a filter that trusts translation/summarization requests.
**Benign look-alikes:** real translation requests, real summarization of a
document that merely *mentions* instructions.

### `cultural_authority`
The local flavour of `authority_spoof`: spoofed authority using **local
institutions and forms of address** — a fake ministry notice, a bank-SMS format,
an honorific-laden "official" request — calibrated to a specific market so it
reads as authentic to a native speaker.
**Benign look-alikes:** a genuine (if formal) message from a real-sounding
institution that makes no unsafe request.

## Authoring rule

Rows are **authored in their language**, never translated from English. Within a
family, rows must differ in structure, register, length, and persona. Benign
look-alikes must share the family's surface features with the attacks, so the
label reflects intent, not surface form. See `docs/REVIEWER_GUIDE.md`.
