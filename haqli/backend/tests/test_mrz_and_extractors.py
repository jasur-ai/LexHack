"""Unit tests for ICAO 9303 MRZ parser, fine/receipt parsers, and Uzbek/Russian entity extractors (§7, §14)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from app.engines.intake import extract_amount_uzs, extract_date_uz_ru, parse_intake_text
from app.engines.recognition.parsers import (
    classify_document,
    mrz_check_digit,
    parse_mrz_td3,
    parse_receipt,
    parse_traffic_fine,
)


def _make_valid_td3(surname: str, given: str, doc_num: str, nat: str, dob: str, sex: str, exp: str) -> str:
    l1_body = f"P<{nat[:3]}{surname.upper()}<<{given.upper()}"
    line1 = l1_body.ljust(44, "<")[:44]

    doc_field = doc_num.upper().ljust(9, "<")[:9]
    cd_doc = mrz_check_digit(doc_field)
    cd_dob = mrz_check_digit(dob)
    cd_exp = mrz_check_digit(exp)
    opt = "<" * 14
    cd_opt = mrz_check_digit(opt)
    composite = doc_field + cd_doc + dob + cd_dob + exp + cd_exp + opt + cd_opt
    cd_final = mrz_check_digit(composite)
    line2 = f"{doc_field}{cd_doc}{nat[:3]}{dob}{cd_dob}{sex}{exp}{cd_exp}{opt}{cd_opt}{cd_final}"
    return f"{line1}\n{line2}"


def test_mrz_td3_valid_uzbek_passport() -> None:
    mrz = _make_valid_td3("KARIMOV", "AZIZBEK", "AD1234567", "UZB", "950412", "M", "320412")
    res = parse_mrz_td3(mrz)
    assert res["valid"] is True
    assert res["fields"]["surname"] == "KARIMOV"
    assert res["fields"]["givenNames"] == "AZIZBEK"
    assert res["fields"]["documentNumber"] == "AD1234567"
    assert res["fields"]["nationality"] == "UZB"
    assert res["fields"]["dob"] == "1995-04-12"
    assert res["fields"]["expiry"] == "2032-04-12"
    assert res["confidences"]["documentNumber"] >= 0.99


def test_mrz_td3_rejects_bad_check_digit() -> None:
    mrz = _make_valid_td3("KARIMOV", "AZIZBEK", "AD1234567", "UZB", "950412", "M", "320412")
    lines = mrz.splitlines()
    # Corrupt the document number check digit at index 9
    bad_cd = str((int(lines[1][9]) + 1) % 10)
    corrupted = f"{lines[0]}\n{lines[1][:9]}{bad_cd}{lines[1][10:]}"
    res = parse_mrz_td3(corrupted)
    assert res["valid"] is False
    assert res["error"] == "mrz_checksum_failed"
    assert res["checks"]["docNumber"] is False


def test_traffic_fine_and_receipt_parsers() -> None:
    fine_txt = (
        "Toshkent shahar IIBB YHXB\n"
        "Jarima qarori № YHX-2026-88412\n"
        "Sana: 14.04.2026\n"
        "MJtK 128-3-modda bo'yicha davlat raqami 01 A 777 AA avtomobil.\n"
        "Jarima summasi: 1 875 000 so'm"
    )
    cls = classify_document(fine_txt)
    assert cls["type"] == "jarima_qarori"
    parsed = parse_traffic_fine(fine_txt)
    assert parsed["fields"]["vehiclePlate"] == "01 A 777 AA"
    assert parsed["fields"]["fineAmountUzs"] == "1875000.00"
    assert parsed["fields"]["decisionDate"] == "2026-04-14"
    assert parsed["fields"]["articleRef"] == "128-3"

    receipt_txt = (
        "Texnomart Savdo MCHJ\n"
        "Kassa cheki #4421\n"
        "Sana: 2026-03-18\n"
        "To'lov turi: Uzcard terminal\n"
        "Jami: 4 200 000 so'm"
    )
    r_cls = classify_document(receipt_txt)
    assert r_cls["type"] == "chek_kvitansiya"
    r_parsed = parse_receipt(receipt_txt)
    assert r_parsed["fields"]["seller"] == "Texnomart Savdo MCHJ"
    assert r_parsed["fields"]["totalUzs"] == "4200000.00"
    assert r_parsed["fields"]["paymentMethod"] == "card"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Alisher 5 mln qarz oldi", Decimal("5000000.00")),
        ("Summa 3,5 million so'm", Decimal("3500000.00")),
        ("850 ming so'm to'landi", Decimal("850000.00")),
        ("Оклад 6 200 000 сум", Decimal("6200000.00")),
    ],
)
def test_extract_amount_uzs_variants(text: str, expected: Decimal) -> None:
    val, conf = extract_amount_uzs(text)
    assert val == expected
    assert conf >= 0.85


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("15.05.2026 kuni qaytaradi", date(2026, 5, 15)),
        ("2026-06-01 gacha", date(2026, 6, 1)),
        ("10 may 2026 yil", date(2026, 5, 10)),
        ("до 20 июня 2026 года", date(2026, 6, 20)),
    ],
)
def test_extract_date_uz_ru_variants(text: str, expected: date) -> None:
    dt, conf = extract_date_uz_ru(text)
    assert dt == expected
    assert conf >= 0.85


@pytest.mark.asyncio
async def test_parse_intake_text_natural_language() -> None:
    res = await parse_intake_text("Alisher Rahimovga 8 mln so'm qarz berdim, 25.08.2026 gacha qaytaradi, pasport AD4512987.")
    assert res["fields"]["amountUzs"] == "8000000.00"
    assert res["fields"]["dueDate"] == "2026-08-25"
    assert res["fields"]["passport"] == "AD4512987"
    assert res["engine"] == "deterministic"
