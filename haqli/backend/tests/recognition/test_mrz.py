"""ICAO 9303 TD1 & TD3 MRZ parser tests + 50-fixture CI threshold verification (§6.4, §12)."""

from __future__ import annotations

from datetime import date

from app.engines.recognition.eval.fixtures import build_mrz_fixtures, make_td1, make_td3
from app.engines.recognition.parsers.mrz import parse_mrz, parse_mrz_td3


def test_td1_id_card_mrz_valid_and_ocr_cleanup() -> None:
    raw = make_td1("KARIMOVA", "MADINA", "ID3456789", "980514", "330514")
    noisy = raw.replace("<<<", "«KK", 1)
    res = parse_mrz(noisy, today=date(2026, 4, 15))
    assert res["valid"] is True
    assert res["format"] == "TD1"
    assert res["fields"]["documentNumber"] == "ID3456789"
    assert res["fields"]["surname"] == "KARIMOVA"
    assert res["fields"]["givenNames"] == "MADINA"
    assert res["fields"]["dob"] == "1998-05-14"


def test_td3_single_check_digit_warn_vs_double_failure_reject() -> None:
    one_err = make_td3("TESTER", "ALI", "AD1112223", "920310", "320310", corrupt_count=1)
    res_warn = parse_mrz_td3(one_err, today=date(2026, 4, 15))
    # Composite also fails when doc cd is corrupted -> 2 failures total -> rejected
    assert res_warn["valid"] is False
    assert "rec.warn.mrz_checksum" in res_warn["warnings"]

    two_err = make_td3("TESTER", "ALI", "AD1112223", "920310", "320310", corrupt_count=2)
    res_rej = parse_mrz_td3(two_err, today=date(2026, 4, 15))
    assert res_rej["valid"] is False
    assert res_rej["fields"] == {}


def test_mrz_50_fixture_ci_gates() -> None:
    fixtures = build_mrz_fixtures()
    valid_tot = valid_ok = inv_tot = inv_rej = 0
    for fx in fixtures:
        res = parse_mrz(fx["raw"], today=date(2026, 4, 15))
        if fx["expect_valid"]:
            valid_tot += 1
            if res["valid"] and res["fields"]["documentNumber"] == fx["doc_number"]:
                valid_ok += 1
        else:
            inv_tot += 1
            if not res["valid"]:
                inv_rej += 1
    assert valid_ok / valid_tot >= 0.99
    assert inv_rej / inv_tot == 1.0
