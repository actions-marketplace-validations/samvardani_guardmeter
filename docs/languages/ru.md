# Russian (ru) — authoring notes

**Status:** authored, awaiting native review.

## Registers and markets
Standard Russian (Russia). Mixes formal вы (customer-facing, cultural_authority
notices) with informal ты and colloquial forms ("слушай", "забей", "скинь")
for the casual attack rows. Currency ₽ / рубли.

## Institutions used for cultural_authority
Invented stand-ins only: a generic "ФНС / налоговая" (tax service) notice, a
"ваш банк — служба безопасности" SMS, "ИТ-поддержка", "отдел кадров (HR)", a
"коллекторское агентство" (collections) threat. No real bank, agency, or person.

## Romanization
The `transliteration` family uses **translit** (romanized Russian, as typed
without a Cyrillic keyboard): "zabud vse pravila", "otpravь" → "otprav",
"sistemnyy prompt". Common chat translit, not strict GOST.

## Script traps
- **Cyrillic↔Latin homoglyphs**: а/a, е/e, о/o, р/p, с/c, х/x, у/y, к/k — a
  single Latin letter hidden in a Cyrillic word is the core `script_mixing`/
  homoglyph vector, and NFKC does **not** fold these (they're distinct letters).
- **ё vs е**: often written interchangeably; a normalization surface.
- Cyrillic base, so cross-lingual families embed a Latin/Han/Arabic **payload**
  or switch the tail into another language.

## Known limitations
Authored by a non-native model. Aspect/case naturalness and the formal/informal
boundary need a native ear. Awaiting a named native reviewer before any row
moves to `reviewed`; nothing here is reviewed.
