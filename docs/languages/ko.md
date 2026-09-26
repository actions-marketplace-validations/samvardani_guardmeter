# Korean (ko) — authoring notes

**Status:** authored, awaiting native review.

## Registers and markets
Standard Korean (South Korea). Mixes formal 합쇼체/해요체 (customer-facing,
cultural_authority notices) with 반말 (해체) for the casual attack rows. Currency
₩ / 원.

## Institutions used for cultural_authority
Invented stand-ins only: a generic "국세청" (National Tax Service) notice, a
"고객님의 은행 — 보안팀" SMS, "IT 헬프데스크", "인사팀 (HR)", a "채권추심업체"
(collections) threat. No real bank, agency, or person.

## Romanization
The `transliteration` family uses **Romaja** (revised-romanization-ish, spaced):
"modeun gyuchik-eul musihago", "isiche", "gomawo". English tech loanwords stay
in Latin ("system prompt", "email").

## Script traps
- **Hangul syllable blocks**: composed 가/각 vs decomposed jamo ㄱㅏ — an NFC/NFD
  normalization surface; the validator counts Hangul (+Han) via
  `native_script_ratio`.
- **Full-width Latin/digits** (ｉｇｎｏｒｅ) — the homoglyph vector.
- Korean **does** use word spaces (unlike zh/ja); cross-lingual families embed a
  Latin/Cyrillic/Han/Arabic **payload** or switch the tail into another language.

## Known limitations
Authored by a non-native model. Honorific speech levels (존댓말/반말), particle
choice, and spacing (띄어쓰기) need a native ear. Awaiting a named native
reviewer before any row moves to `reviewed`; nothing here is reviewed.
