# Persian / Farsi (fa) — authoring notes

**Status:** authored, awaiting native review.

## Registers and markets
Iran (IR), with everyday spoken and semi-formal written registers. Uses Persian
digits (۰–۹) in some rows and Latin digits in others, ZWNJ (نیم‌فاصله) where
correct.

## Institutions used for cultural_authority
Invented generic stand-ins: a "سازمان امور مالیاتی"-style tax notice (generic),
a bank fraud-desk SMS, an "پشتیبانی فناوری اطلاعات". No real bank, agency, person.

## Romanization
Finglish (Persian in Latin) is used in the `transliteration` family.

## Script traps
Arabic script; ZWNJ is legitimate and frequent in Persian, so the heuristic's
zero-width feature must not treat a single ZWNJ as abusive. پ چ ژ گ distinguish
Persian from Arabic.

## Known limitations
Authored by a non-native model. Idiom and politeness registers, and the
naturalness of the `cultural_authority` notices, need a native reviewer.
