"""Language registry — the single source of truth for GuardMeter's languages.

Holds each Tier-1 language's script, writing direction, Unicode ranges (for
script-ratio checks), romanization systems (Finglish, Arabizi, Pinyin…), and
market registers. Also a stdlib-only ``detect_language`` using script histograms
plus small per-language stopword tables to disambiguate same-script languages.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field

Range = tuple[int, int]

# ── Script Unicode ranges ────────────────────────────────────────────────────
SCRIPTS: dict[str, list[Range]] = {
    "Latin": [(0x41, 0x5A), (0x61, 0x7A), (0xC0, 0x24F), (0x1E00, 0x1EFF)],
    "Arabic": [(0x600, 0x6FF), (0x750, 0x77F), (0x8A0, 0x8FF), (0xFB50, 0xFDFF), (0xFE70, 0xFEFF)],
    "Cyrillic": [(0x400, 0x52F)],
    "Devanagari": [(0x900, 0x97F)],
    "Bengali": [(0x980, 0x9FF)],
    "Thai": [(0xE00, 0xE7F)],
    "Hebrew": [(0x590, 0x5FF)],
    "Han": [(0x3400, 0x4DBF), (0x4E00, 0x9FFF), (0xF900, 0xFAFF)],
    "Hiragana": [(0x3040, 0x309F)],
    "Katakana": [(0x30A0, 0x30FF)],
    "Hangul": [(0x1100, 0x11FF), (0x3130, 0x318F), (0xAC00, 0xD7A3)],
}


@dataclass(frozen=True)
class Language:
    """A registered language and everything GuardMeter needs to reason about it."""

    code: str
    name: str
    native_name: str
    script: str
    direction: str  # "ltr" | "rtl"
    family: str
    unicode_ranges: list[Range]
    romanization_systems: list[str] = field(default_factory=list)
    min_script_ratio: float = 0.5
    tokenizer_hint: str = "space"  # space | cjk | thai
    market_registers: list[str] = field(default_factory=list)

    @property
    def rtl(self) -> bool:
        return self.direction == "rtl"


def _lang(code, name, native, script, direction, family, **kw) -> Language:
    return Language(code=code, name=name, native_name=native, script=script,
                    direction=direction, family=family,
                    unicode_ranges=SCRIPTS[script], **kw)


# ── Tier-1 registry (24 languages) ───────────────────────────────────────────
LANGUAGES: dict[str, Language] = {
    la.code: la for la in [
        _lang("en", "English", "English", "Latin", "ltr", "Germanic",
              min_script_ratio=0.5, market_registers=["US", "UK", "IN", "NG"]),
        _lang("es", "Spanish", "Español", "Latin", "ltr", "Romance",
              min_script_ratio=0.5, market_registers=["MX", "ES", "AR", "CO"]),
        _lang("pt", "Portuguese", "Português", "Latin", "ltr", "Romance",
              min_script_ratio=0.5, market_registers=["BR", "PT"]),
        _lang("fr", "French", "Français", "Latin", "ltr", "Romance",
              min_script_ratio=0.5, market_registers=["FR", "CA", "BE"]),
        _lang("de", "German", "Deutsch", "Latin", "ltr", "Germanic",
              min_script_ratio=0.5, market_registers=["DE", "AT", "CH"]),
        _lang("it", "Italian", "Italiano", "Latin", "ltr", "Romance",
              min_script_ratio=0.5, market_registers=["IT"]),
        _lang("nl", "Dutch", "Nederlands", "Latin", "ltr", "Germanic",
              min_script_ratio=0.5, market_registers=["NL", "BE"]),
        _lang("pl", "Polish", "Polski", "Latin", "ltr", "Slavic",
              min_script_ratio=0.5, market_registers=["PL"]),
        _lang("ru", "Russian", "Русский", "Cyrillic", "ltr", "Slavic",
              romanization_systems=["translit"], min_script_ratio=0.6, market_registers=["RU"]),
        _lang("uk", "Ukrainian", "Українська", "Cyrillic", "ltr", "Slavic",
              romanization_systems=["translit"], min_script_ratio=0.6, market_registers=["UA"]),
        _lang("tr", "Turkish", "Türkçe", "Latin", "ltr", "Turkic",
              min_script_ratio=0.5, market_registers=["TR"]),
        _lang("ar", "Arabic", "العربية", "Arabic", "rtl", "Semitic",
              romanization_systems=["Arabizi", "Franco"], min_script_ratio=0.6,
              market_registers=["Gulf", "Levant", "Egypt", "Maghreb"]),
        _lang("fa", "Persian", "فارسی", "Arabic", "rtl", "Iranian",
              romanization_systems=["Finglish"], min_script_ratio=0.6, market_registers=["IR", "AF"]),
        _lang("he", "Hebrew", "עברית", "Hebrew", "rtl", "Semitic",
              min_script_ratio=0.6, market_registers=["IL"]),
        _lang("ur", "Urdu", "اردو", "Arabic", "rtl", "Indo-Aryan",
              romanization_systems=["Roman Urdu"], min_script_ratio=0.6, market_registers=["PK", "IN"]),
        _lang("hi", "Hindi", "हिन्दी", "Devanagari", "ltr", "Indo-Aryan",
              romanization_systems=["Hinglish"], min_script_ratio=0.55, market_registers=["IN"]),
        _lang("bn", "Bengali", "বাংলা", "Bengali", "ltr", "Indo-Aryan",
              romanization_systems=["Banglish"], min_script_ratio=0.55, market_registers=["BD", "IN"]),
        _lang("id", "Indonesian", "Bahasa Indonesia", "Latin", "ltr", "Austronesian",
              min_script_ratio=0.5, market_registers=["ID"]),
        _lang("vi", "Vietnamese", "Tiếng Việt", "Latin", "ltr", "Austroasiatic",
              min_script_ratio=0.5, market_registers=["VN"]),
        _lang("th", "Thai", "ไทย", "Thai", "ltr", "Kra-Dai",
              romanization_systems=["RTGS"], min_script_ratio=0.55, tokenizer_hint="thai",
              market_registers=["TH"]),
        _lang("zh", "Chinese", "中文", "Han", "ltr", "Sinitic",
              romanization_systems=["Pinyin"], min_script_ratio=0.5, tokenizer_hint="cjk",
              market_registers=["CN", "TW", "HK"]),
        _lang("ja", "Japanese", "日本語", "Han", "ltr", "Japonic",
              romanization_systems=["Romaji"], min_script_ratio=0.5, tokenizer_hint="cjk",
              market_registers=["JP"]),
        _lang("ko", "Korean", "한국어", "Hangul", "ltr", "Koreanic",
              romanization_systems=["Romaja"], min_script_ratio=0.5, market_registers=["KR"]),
        _lang("sw", "Swahili", "Kiswahili", "Latin", "ltr", "Bantu",
              min_script_ratio=0.5, market_registers=["KE", "TZ"]),
    ]
}

# Chinese Traditional is a variant of zh (Simplified is the registered form).
VARIANTS = {"zh-Hant": "zh"}


def _in_ranges(cp: int, ranges: list[Range]) -> bool:
    return any(lo <= cp <= hi for lo, hi in ranges)


def script_of(ch: str) -> str | None:
    """Return the script name of a single character, or None if not a letter."""
    if not ch.isalpha():
        return None
    cp = ord(ch)
    for name, ranges in SCRIPTS.items():
        if _in_ranges(cp, ranges):
            return name
    return "Other"


def script_ratio(text: str, script: str) -> float:
    """Fraction of the text's letters that belong to ``script``."""
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return 0.0
    hits = sum(1 for c in letters if script_of(c) == script)
    return hits / len(letters)


# ── Detection: script histogram + small stopword tables ──────────────────────
_STOPWORDS: dict[str, set[str]] = {
    "en": {"the", "and", "you", "your", "please", "this", "that", "with", "for"},
    "es": {"el", "la", "de", "que", "por", "para", "una", "los", "con", "favor"},
    "pt": {"de", "que", "para", "uma", "com", "não", "por", "seu", "você", "favor"},
    "fr": {"le", "la", "de", "et", "vous", "votre", "pour", "que", "s'il", "merci"},
    "de": {"der", "die", "das", "und", "ihre", "bitte", "nicht", "für", "mit", "ist"},
    "it": {"il", "la", "di", "che", "per", "una", "con", "non", "tuo", "grazie"},
    "nl": {"de", "het", "een", "en", "uw", "niet", "voor", "met", "alstublieft", "je"},
    "pl": {"nie", "się", "jest", "twoje", "proszę", "dla", "oraz", "który", "wszystkie"},
    "tr": {"ve", "bir", "için", "bu", "senin", "lütfen", "değil", "ile", "tüm"},
    "id": {"yang", "dan", "untuk", "ini", "anda", "tidak", "dengan", "semua", "tolong"},
    "vi": {"và", "của", "cho", "này", "bạn", "không", "với", "vui", "lòng", "tất"},
    "sw": {"na", "ya", "kwa", "wako", "tafadhali", "hii", "yote", "si", "kwenye"},
    "ru": {"и", "не", "все", "ваш", "пожалуйста", "это", "для", "что", "как"},
    "uk": {"і", "не", "всі", "ваш", "будь", "ласка", "це", "для", "що", "як"},
    "ar": {"من", "في", "على", "الى", "جميع", "لك", "هذا", "رجاء", "كل"},
    "fa": {"از", "به", "را", "همه", "لطفا", "این", "شما", "که", "خود"},
    "ur": {"سے", "کو", "تمام", "آپ", "برائے", "مہربانی", "یہ", "کہ", "اپنے"},
    "he": {"של", "את", "כל", "אתה", "בבקשה", "זה", "עם", "לא", "כדי"},
    "hi": {"और", "आप", "कृपया", "सभी", "यह", "के", "को", "अपने", "है"},
    "bn": {"এবং", "আপনার", "সব", "দয়া", "করে", "এই", "না", "আপনি", "সকল"},
    "th": {"และ", "คุณ", "โปรด", "ทั้งหมด", "นี้", "ไม่", "กับ", "ของ"},
    "zh": {"的", "请", "所有", "你", "和", "不", "这", "把", "我"},
    "ja": {"の", "を", "に", "してください", "すべて", "この", "です", "私"},
    "ko": {"의", "를", "모든", "주세요", "이", "그리고", "당신", "저"},
}
# Same-script candidate groups.
_SCRIPT_LANGS: dict[str, list[str]] = {
    "Latin": ["en", "es", "pt", "fr", "de", "it", "nl", "pl", "tr", "id", "vi", "sw"],
    "Cyrillic": ["ru", "uk"],
    "Arabic": ["ar", "fa", "ur"],
    "Devanagari": ["hi"],
    "Bengali": ["bn"],
    "Thai": ["th"],
    "Hebrew": ["he"],
}
# Distinctive letters that strongly imply one language within a shared script.
_HINTS: dict[str, str] = {
    "fa": "پچژگ", "ur": "ٹڈڑںے", "uk": "іїєґ", "pl": "łąężźćń", "tr": "ışğıİ",
    "de": "ß", "vi": "ăâđêôơư", "es": "ñ¿¡", "pt": "ãõç",
}


def _tokens(text: str) -> list[str]:
    import re
    return re.findall(r"\w+", text.lower(), flags=re.UNICODE)


def detect_language(text: str) -> tuple[str, float]:
    """Best-effort language detection → (code, confidence in 0..1).

    Uses the dominant script to narrow candidates, then distinctive letters and
    a small stopword table to disambiguate. CJK is resolved by kana/hangul
    presence. Returns ("und", 0.0) when there are no letters.
    """
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return "und", 0.0

    hist: dict[str, int] = {}
    for c in letters:
        s = script_of(c)
        if s:
            hist[s] = hist.get(s, 0) + 1

    # CJK: Hangul → ko; kana → ja; otherwise Han → zh.
    if hist.get("Hangul"):
        return "ko", round(hist["Hangul"] / len(letters), 3)
    if hist.get("Hiragana", 0) + hist.get("Katakana", 0) > 0:
        han_kana = hist.get("Han", 0) + hist.get("Hiragana", 0) + hist.get("Katakana", 0)
        return "ja", round(han_kana / len(letters), 3)
    if hist.get("Han"):
        return "zh", round(hist["Han"] / len(letters), 3)

    dominant = max(hist, key=lambda k: hist[k])
    dom_ratio = hist[dominant] / len(letters)
    candidates = _SCRIPT_LANGS.get(dominant, [])
    if len(candidates) == 1:
        return candidates[0], round(dom_ratio, 3)
    if not candidates:
        return "und", round(dom_ratio, 3)

    toks = set(_tokens(text))
    best, best_score = candidates[0], -1.0
    for code in candidates:
        hint_hits = sum(1 for ch in _HINTS.get(code, "") if ch in text)
        stop_hits = len(toks & _STOPWORDS.get(code, set()))
        score = hint_hits * 2 + stop_hits
        if score > best_score:
            best, best_score = code, score
    # Confidence blends script dominance with how decisively we disambiguated.
    conf = dom_ratio * (0.6 + 0.1 * min(4, best_score)) if best_score > 0 else dom_ratio * 0.5
    return best, round(min(1.0, conf), 3)


def get_language(code: str) -> Language | None:
    """Look up a language by code, resolving known variants (zh-Hant → zh)."""
    return LANGUAGES.get(VARIANTS.get(code, code))


def normalize_nfkc(text: str) -> str:
    """NFKC-normalise (fold compatibility forms, e.g. full-width → ASCII)."""
    return unicodedata.normalize("NFKC", text)
