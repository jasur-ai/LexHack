"""Comprehensive unit tests for entities/* including the full 60-case numeral table (§6.5, §12)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from app.engines.recognition.entities.dates import extract_dates
from app.engines.recognition.entities.ids import (
    extract_passports,
    extract_phones,
    extract_pinfls,
    extract_plates,
    extract_telegram_handles,
)
from app.engines.recognition.entities.money import extract_money
from app.engines.recognition.entities.names import extract_names
from app.engines.recognition.entities.numbers import parse_number_phrase
from app.engines.recognition.eval.fixtures import NUMERAL_60_TABLE


@pytest.mark.parametrize(("phrase", "expected"), NUMERAL_60_TABLE)
def test_spoken_and_written_numerals_60_cases(phrase: str, expected: Decimal) -> None:
    assert parse_number_phrase(phrase) == expected


def test_money_extractor_uzs_and_foreign_currency_no_conversion() -> None:
    uzs = extract_money("Men 5,5 million so'm to'ladim")
    assert len(uzs) == 1
    assert uzs[0].amount == Decimal("5500000.00")
    assert uzs[0].currency == "UZS"
    assert uzs[0].needs_confirm is False

    usd = extract_money("Depozit 500 dollar berdim")
    assert len(usd) == 1
    assert usd[0].amount == Decimal("500.00")
    assert usd[0].currency == "USD"
    assert usd[0].needs_confirm is True


def test_dates_absolute_and_relative_with_tashkent_reference() -> None:
    ref = date(2026, 4, 15)  # Wednesday
    assert extract_dates("25-dekabr 2026 kuni", today=ref)[0].value == date(2026, 12, 25)
    assert extract_dates("25 декабря", today=ref)[0].value == date(2026, 12, 25)
    assert extract_dates("bugun to'layman", today=ref)[0].value == date(2026, 4, 15)
    assert extract_dates("ertaga qaytaraman", today=ref)[0].value == date(2026, 4, 16)
    assert extract_dates("indinga ko'rishamiz", today=ref)[0].value == date(2026, 4, 17)
    assert extract_dates("послезавтра", today=ref)[0].value == date(2026, 4, 17)
    assert extract_dates("3 kundan keyin", today=ref)[0].value == date(2026, 4, 18)
    assert extract_dates("через 3 дня", today=ref)[0].value == date(2026, 4, 18)
    assert extract_dates("o'tgan juma kuni", today=ref)[0].value == date(2026, 4, 10)
    assert extract_dates("kelasi oy", today=ref)[0].value == date(2026, 5, 15)


def test_names_extractor_patronymics_stoplist_and_cue_ranking() -> None:
    txt = "Toshkent Shartnoma bo'yicha qarz oluvchi: Karimov Azizbek Botir o'g'li va beruvchi Dilnoza Alimova."
    names = extract_names(txt)
    assert len(names) >= 2
    assert "Karimov Azizbek" in names[0].name
    assert names[0].cue_matched is True
    assert all("Toshkent" not in n.name and "Shartnoma" not in n.name for n in names)


def test_ids_extractors_cyrillic_homoglyphs_pinfl_phone_plate() -> None:
    # Cyrillic А, В lookalikes normalized to Latin AB
    p = extract_passports("Pasport АВ 1234567")
    assert len(p) == 1 and p[0].value == "AB1234567" and p[0].sensitive is True

    pinfl = extract_pinfls("JShShIR: 31204950120045")
    assert len(pinfl) == 1 and pinfl[0].value == "31204950120045" and pinfl[0].sensitive is True

    phones = extract_phones("Aloqa: +998 (90) 123-45-67")
    assert len(phones) == 1 and phones[0].value == "+998901234567"

    tgs = extract_telegram_handles("Telegram: @haqli_user_01")
    assert len(tgs) == 1 and tgs[0].value == "@haqli_user_01"

    # Cyrillic lookalikes in plate
    plates = extract_plates("Avtomobil 01 А 777 АА")
    assert len(plates) == 1 and plates[0].value == "01 A 777 AA"
