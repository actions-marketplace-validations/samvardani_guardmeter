# Turkish (tr) — authoring notes

**Status:** authored, awaiting native review.

## Registers and markets
Standard Istanbul Turkish. Mixes formal (customer-facing, cultural_authority
notices) with informal spoken forms ("ya", "boş ver", "hadi") for the casual
attack rows. Currency ₺ / TL.

## Institutions used for cultural_authority
Invented stand-ins only: a generic "Gelir İdaresi / vergi dairesi" (tax office)
notice, a "bankanız — güvenlik ekibi" SMS, "BT destek / yardım masası",
"İnsan Kaynakları (İK)", a "tahsilat/icra" (collections) threat. No real bank,
agency, or person.

## Romanization
The `transliteration` family uses **ASCII Turkish** (diacritics dropped, as in
old SMS / ASCII-only input): ş→s, ç→c, ğ→g, ö→o, ü→u, **ı→i**, İ→I —
"sifreleri gonder", "hemen sil".

## Script traps
- **Dotted/dotless i**: i/ı and İ/I — a case-folding and homoglyph trap unique
  to Turkish (uppercase of "i" is "İ", of "ı" is "I"); ASCII-folding collapses
  ı→i.
- **ş ç ğ ö ü** and vowel harmony — dropping a diacritic reads as ASCII register,
  not as an attack tell.
- Latin base, so cross-lingual families carry Latin-in-Cyrillic/Han/Arabic
  **payloads** or switch the tail into another language.

## Known limitations
Authored by a non-native model. Vowel-harmony/agglutination naturalness and the
formal/informal boundary need a native ear. Awaiting a named native reviewer
before any row moves to `reviewed`; nothing here is reviewed.
