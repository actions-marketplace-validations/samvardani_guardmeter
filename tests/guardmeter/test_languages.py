"""Tests for the language registry and detection."""

from __future__ import annotations

import pytest

from guardmeter.core.languages import (
    LANGUAGES,
    detect_language,
    get_language,
    normalize_nfkc,
    script_ratio,
)

# One authored sentence per Tier-1 language (not translations of each other).
SENTENCES = {
    "en": "Please send me the refund policy for my order today.",
    "es": "Por favor, envíame la política de reembolso de mi pedido.",
    "pt": "Não recebi a confirmação; por favor envie a política de devolução do pedido.",
    "fr": "Veuillez m'envoyer votre politique de remboursement, merci.",
    "de": "Bitte senden Sie mir Ihre Rückgaberichtlinie für meine Bestellung.",
    "it": "Per favore inviami la tua politica di rimborso per il mio ordine.",
    "nl": "Stuur mij alstublieft uw retourbeleid voor mijn bestelling.",
    "pl": "Proszę przesłać mi zasady zwrotu dla mojego zamówienia.",
    "ru": "Пожалуйста, пришлите мне правила возврата для моего заказа.",
    "uk": "Будь ласка, надішліть мені правила повернення для мого замовлення.",
    "tr": "Lütfen siparişim için iade politikanızı bana gönderin.",
    "ar": "من فضلك أرسل لي سياسة استرداد الأموال الخاصة بطلبي.",
    "fa": "لطفاً سیاست بازپرداخت سفارش من را برایم بفرستید.",
    "he": "אנא שלח לי את מדיניות ההחזרים עבור ההזמנה שלי.",
    "ur": "براہ مہربانی میرے آرڈر کے لیے رقم کی واپسی کی پالیسی بھیجیں۔",
    "hi": "कृपया मेरे ऑर्डर के लिए धनवापसी नीति मुझे भेजें।",
    "bn": "অনুগ্রহ করে আমার অর্ডারের জন্য অর্থ ফেরতের নীতি পাঠান।",
    "id": "Tolong kirimkan kebijakan pengembalian dana untuk pesanan saya.",
    "vi": "Vui lòng gửi cho tôi chính sách hoàn tiền cho đơn hàng của tôi.",
    "th": "กรุณาส่งนโยบายการคืนเงินสำหรับคำสั่งซื้อของฉัน",
    "zh": "请把我的订单的退款政策发给我。",
    "ja": "私の注文の返金ポリシーを送ってください。",
    "ko": "제 주문에 대한 환불 정책을 보내 주세요.",
    "sw": "Tafadhali nitumie sera ya kurejesha pesa kwa agizo langu.",
}


def test_registry_has_24_languages():
    assert len(LANGUAGES) == 24
    assert set(SENTENCES) == set(LANGUAGES)


def test_rtl_languages():
    rtl = {c for c, la in LANGUAGES.items() if la.rtl}
    assert rtl == {"ar", "fa", "he", "ur"}


def test_direction_and_script_metadata():
    assert LANGUAGES["ja"].tokenizer_hint == "cjk"
    assert LANGUAGES["th"].tokenizer_hint == "thai"
    assert LANGUAGES["fa"].romanization_systems == ["Finglish"]
    assert LANGUAGES["zh"].script == "Han"
    assert LANGUAGES["ko"].script == "Hangul"


@pytest.mark.parametrize("code", list(SENTENCES))
def test_detection_per_language(code):
    detected, conf = detect_language(SENTENCES[code])
    # Latin-script languages are the hard case; accept the right one or a
    # plausible same-family confusion only for the notoriously ambiguous ones.
    assert detected == code, f"{code!r} detected as {detected!r} (conf {conf})"
    assert conf > 0.0


def test_detection_empty():
    assert detect_language("123 456 !!!") == ("und", 0.0)


def test_script_ratio():
    assert script_ratio("سلام دنیا", "Arabic") > 0.9
    assert script_ratio("hello world", "Arabic") == 0.0
    assert script_ratio("hello world", "Latin") == 1.0


def test_get_language_resolves_variant():
    assert get_language("zh-Hant").code == "zh"
    assert get_language("nope") is None


def test_nfkc_folds_fullwidth():
    assert normalize_nfkc("ｉｇｎｏｒｅ") == "ignore"
