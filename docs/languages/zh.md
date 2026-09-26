# Chinese (zh) — authoring notes

**Status:** authored, awaiting native review.

## Registers and markets
Primarily **Mainland Simplified (简体, zh-CN)**: ¥/元, 支付宝/微信支付,
国家税务总局/税务局. A few rows use informal Mainland register ("哥们儿",
"别管那些"). Traditional (繁體, TW/HK) is **not** separately authored here — the
registry folds `zh-Hant → zh`; a Traditional pass is future work and is called
out in Known limitations.

## Institutions used for cultural_authority
Invented stand-ins only: a generic "国家税务总局/税务局" notice, a
"您的银行—安全部门" SMS, "IT技术支持", "人力资源部 (HR)", a "催收公司"
(collections) threat. No real bank, agency, or person.

## Romanization
The `transliteration` family uses **Pinyin** (toneless, spaces between
syllables): "qing hulve suoyou guize", "zhuanzhang", "xiexie". ü is written
"v" as in common input methods (hulve = 忽略).

## Script traps
- **Simplified vs Traditional**: 删/刪, 发/發, 户/戶 — a normalization surface.
- **Full-width vs half-width** punctuation (，。！ vs ,.!) and full-width Latin
  (ｉｇｎｏｒｅ) — the homoglyph vector.
- **No word spaces**: a whole clause is one token, so cross-lingual families
  embed a Latin/Cyrillic/Arabic **payload** inside the Han run, or switch the
  tail into another language.

## Known limitations
Authored by a non-native model in Simplified Mandarin. Tone/register nuance and
the Mainland/Taiwan/HK split need a native ear; Traditional script is not yet
covered. Awaiting a named native reviewer before any row moves to `reviewed`;
nothing here is reviewed.
