# Add a reviewed language

How to add **one** reviewed language for a paying customer, using only existing
commands. This matches what the tooling enforces: a language is not releasable
until a **native** reviewer has signed off (see
[`review-closure.md`](review-closure.md) P9). Sell the review, curation, and
updates — not a "certified safe language" badge.

## Prerequisites

- A competent **native** reviewer for the language (non-native review does not
  release a language).
- The dataset file (JSONL) and its `MANIFEST.json`.

## Steps

### 1. Author rows

Add rows for the new language (e.g. `de`) to the dataset with
`review_status: "authored"`. Then validate — the language-aware checks catch a
translation-of-English, low native-script ratio, and cross-language templates:

```bash
guardmeter dataset validate data.jsonl --language de
```

### 2. Queue a review packet

```bash
guardmeter dataset review queue data.jsonl --language de --reviewer "Reviewer Name" --out packets/
```

This writes a JSONL packet (every row `decision: "pending"`) and a Markdown
checklist. A row left `pending` is **not** reviewed — there is no default-accept.

### 3. The native reviewer fills in decisions

For each row the reviewer sets `decision` to `accept`, `relabel` (+`new_label`),
`rewrite` (+`new_text`), or `reject` (+`reason`).

### 4. Apply the decisions — record native sign-off

```bash
guardmeter dataset review apply packets/de.decisions.jsonl \
  --dataset-path data.jsonl --manifest MANIFEST.json \
  --reviewer "Reviewer Name" --handle reviewer-handle \
  --native --reviewed-at 2026-10-01
```

Pass `--native` **only** for an actual native speaker. This records a sign-off
row (`native: true`, `rows_reviewed`, `sign_off_sha`) in the manifest. Using
`--not-native` records the review but will **not** make the language releasable.

### 5. Check status

```bash
guardmeter languages status --manifest MANIFEST.json
guardmeter dataset review status --manifest MANIFEST.json --dataset-path data.jsonl
```

`languages status` shows per-language **authored / reviewed / native-signed**
counts. A language is release-eligible only when ≥ 90% of its rows are reviewed
**and** a native reviewer has signed off on ≥ 90% of them **and** the validator
passes — enforced by `can_release`. A fully-reviewed but non-native language
(as `en` is today) is refused.

## What the customer gets

The reviewed rows, the manifest sign-off record (auditable: reviewer, native
flag, date, rows, sign-off hash), and the per-language counts — evidence of a
real native review, not a badge.
