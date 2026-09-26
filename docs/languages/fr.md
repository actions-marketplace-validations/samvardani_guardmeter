# French (fr) — authoring notes

**Status:** authored, awaiting native review.

## Registers and markets
Split across France (FR), Belgium (BE), Québec (CA), and French-speaking
Switzerland (CH):
- **FR** — "vous"/"tu", € written `1 240,50 €`; everyday phrasing ("Peux-tu…",
  "Merci d'avance"). Institutions: le fisc / avis d'imposition, La Banque
  Postale-style, SNCF.
- **BE** — "septante/nonante", €, "GSM" for mobile.
- **CA (Québec)** — "courriel" not "e-mail", "magasiner", CAD, more "tu";
  anglicisms avoided on purpose.
- **CH** — CHF, "septante/huitante/nonante", "natel".

## Institutions used for cultural_authority
Invented stand-ins only: a generic "avis d'imposition" from le fisc, a "votre
banque — service sécurité" SMS, "support informatique / helpdesk", "service RH",
a "société de recouvrement" (dunning) threat. No real bank, agency, or person.

## Romanization
n/a (Latin). The `transliteration` family uses **txto/SMS French**: accents
dropped, "slt/stp/koi/pk/c/g", numbers-as-syllables ("koi 2 9" = "quoi de
neuf"), no capitals.

## Script traps
- **Accents and ligatures**: é è ê ë à â î ï ô û ù ç, and the ligature **œ**
  (cœur, œuvre) — a normalization/homoglyph trap.
- **Guillemets** « » and the apostrophe elision (l', d', j') — tokenizers that
  split on ASCII `'` behave differently on the French typographic apostrophe.
- Latin base, so cross-lingual families carry non-Latin **payloads** (Arabic/
  Cyrillic/Han) or switch the tail into another language.

## Known limitations
Authored by a non-native model. Belgian, Québécois, and Swiss-French registers
are approximated and may read as Metropolitan-French-with-swaps to a native ear;
Québec anglicism avoidance in particular needs a local eye. Awaiting a named
native reviewer before any row moves to `reviewed`; nothing here is reviewed.
