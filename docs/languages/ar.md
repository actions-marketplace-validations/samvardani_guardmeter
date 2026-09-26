# Arabic (ar) — authoring notes

**Status:** authored, awaiting native review.

## Registers and markets
Modern Standard Arabic (MSA / فصحى) as the formal base, with light dialect
markers across the main markets:
- **Gulf / Khaleeji** (SA, AE) — ريال/درهم, "أبغى", "الحين".
- **Levant / Shami** (LB, JO, SY) — "بدي", "هلق", "منيح".
- **Egyptian / Masri** (EG) — جنيه, "عايز", "دلوقتي", "كده".
Formal notices (cultural_authority) stay in MSA.

## Institutions used for cultural_authority
Invented stand-ins only: a generic "مصلحة الضرائب" (tax authority) notice, a
"البنك — قسم الأمان" SMS, "الدعم الفني", "الموارد البشرية (HR)", a "شركة تحصيل"
(collections) threat. No real bank, agency, or person.

## Romanization
The `transliteration` family uses **Arabizi / Franco-Arabic**: Latin letters +
numerals for sounds with no Latin equivalent — `3=ع, 7=ح, 2=همزة, 5=خ, 9=ص,
6=ط` (e.g. "3ala", "el-3omala2", "7awel"). Written left-to-right.

## Script traps
- **RTL**: the whole row is right-to-left; the `bidi_override` family adds
  genuine RLO/RLE/isolate/zero-width controls on top of the natural direction.
- **No ZWNJ** (that is Persian, not Arabic) — but Arabic-Indic digits `٠-٩`
  and Western digits both occur.
- Non-Latin base: `script_mixing` carries a **Latin/Cyrillic/Han payload**
  inside an Arabic sentence; `encoded` payloads are Latin/Arabizi (base64,
  ROT13, leet, homoglyph are ASCII operations by nature).

## Known limitations
Authored by a non-native model, MSA-leaning. Dialect markers (Gulf/Levant/
Egyptian) are approximated and a native ear will spot register mixing. Awaiting
a named native reviewer before any row moves to `reviewed`; nothing here is
reviewed.
