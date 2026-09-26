# German (de) — authoring notes

**Status:** authored, awaiting native review.

## Registers and markets
Split across Germany (DE), Austria (AT), and Switzerland (CH):
- **DE** — "Sie"/"du", € amounts written `1.240,50 €`; everyday phrasing
  ("Kannst du mir kurz…?", "Bitte überweise…"). Institutions: Finanzamt,
  Sparkasse/Volksbank, Deutsche Bahn.
- **AT** — "Servus"/"Grüß dich", €; Austrian words ("Erlagschein", "heuer",
  "Jänner"), FinanzOnline, ÖBB, "Bankomat".
- **CH** — "Grüezi", CHF; **no ß** (always `ss`: "Strasse", "grüssen"),
  Helvetisms ("Töff", "parkieren", "Natel"), PostFinance.

## Institutions used for cultural_authority
Invented stand-ins only: a generic "Finanzamt — Steuerbescheid" notice, an
"Ihre Bank — Sicherheitsteam" SMS, "IT-Helpdesk", "Personalabteilung (HR)",
an "Inkassobüro/Mahnung" legal threat. No real bank, agency, or person.

## Romanization
Umlauts and Eszett have a standard ASCII fallback used in SMS/chat:
`ä→ae, ö→oe, ü→ue, ß→ss` (e.g. "überweise" → "ueberweise", "löschen" →
"loeschen"). The `transliteration` family uses this romanized/abbreviated
netspeak register (no capitals, umlauts spelled out).

## Script traps
- **Eszett** ß vs ss (CH never uses ß) — a homoglyph/normalization trap.
- **Capitalized nouns**: every noun is capitalized; a lowercase noun reads as
  chat register, not as an attack tell.
- Latin base means the cross-lingual families carry non-Latin **payloads**
  (Arabic/Cyrillic/Han) inside German sentences (`script_mixing`), or switch
  the whole tail into another language (`language_switch`).

## Known limitations
Authored by a non-native model. Regional registers (esp. Austrian and Swiss
Helvetisms) are approximated and may read as Standard-German-with-swaps to a
native ear. Awaiting a named native reviewer before any row moves to
`reviewed`; nothing here is reviewed.
