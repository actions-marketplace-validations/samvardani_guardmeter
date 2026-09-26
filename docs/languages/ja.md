# Japanese (ja) — authoring notes

**Status:** authored, awaiting native review.

## Registers and markets
Standard Japanese (Tokyo). Mixes polite ですます register (customer-facing,
cultural_authority notices) with casual だ/plain and spoken forms ("〜して",
"〜だろ", "なあ") for the informal attack rows. Currency 円.

## Institutions used for cultural_authority
Invented stand-ins only: a generic "税務署" (tax office) notice, a
"あなたの銀行 — セキュリティ" SMS, "ITヘルプデスク", "人事部 (HR)", a
"集金代行/督促" (collections) threat. No real bank, agency, or person.

## Romanization
The `transliteration` family uses **Rōmaji** (Hepburn-ish, spaced): "zenbu no
rule o mushi shite", "soukin", "arigatou". English tech loanwords stay in
Latin ("system prompt", "mail").

## Script traps
- **Three scripts at once**: kanji 漢字 + hiragana ひらがな + katakana カタカナ
  in every sentence — a natural row is only ~25–30 % kanji, so the validator
  counts Han+kana together (`native_script_ratio`); raw "Han" would reject it.
- **Full-width Latin/digits** (ｉｇｎｏｒｅ, ０９) — the homoglyph vector.
- **No word spaces**: cross-lingual families embed a Latin/Cyrillic/Arabic
  **payload** in the run, or switch the tail to another language.

## Known limitations
Authored by a non-native model. Keigo (敬語) levels, natural kanji/kana balance,
and casual sentence-final particles need a native ear. Awaiting a named native
reviewer before any row moves to `reviewed`; nothing here is reviewed.
