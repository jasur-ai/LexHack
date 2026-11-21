"""Unit & Hypothesis property tests for the deterministic legal mathematics engine (§6, §14)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from hypothesis import given, strategies as st

from app.engines.rules import (
    ConstantEntry,
    ConstantsSnapshot,
    amount_in_words,
    bhm_ratio,
    case_strength,
    check_written_form,
    consumer_penalty,
    labor_delay_compensation,
    limitation_deadline,
    load_constants,
    response_deadline,
    traffic_appeal_window,
)
from app.engines.translit import latin_to_cyrillic, normalize_uz_text


def _mutate_constant(snap: ConstantsSnapshot, key: str, new_value: Decimal) -> ConstantsSnapshot:
    entries = dict(snap.entries)
    orig = entries[key]
    entries[key] = ConstantEntry(
        key=orig.key,
        value=new_value,
        unit=orig.unit,
        effective_from=orig.effective_from,
        source_ref=orig.source_ref,
        status=orig.status,
        legal_ref=orig.legal_ref,
    )
    return ConstantsSnapshot(version=f"{snap.version}-mut", entries=entries)


@given(
    amount=st.decimals(min_value=Decimal("0"), max_value=Decimal("1000000000"), places=2, allow_nan=False, allow_infinity=False),
    days=st.integers(min_value=0, max_value=1000),
)
def test_consumer_penalty_properties(amount: Decimal, days: int) -> None:
    c = load_constants()
    res = consumer_penalty(amount, days, c)
    assert res["penalty_uzs"] >= Decimal("0.00")
    assert res["penalty_uzs"] <= (amount * c.val("consumer.penalty_cap_ratio")).quantize(Decimal("0.01")) + Decimal("0.01")
    assert res["total_uzs"] == (amount.quantize(Decimal("0.01")) + res["penalty_uzs"]).quantize(Decimal("0.01"))
    # Monotonicity wrt days
    res_more = consumer_penalty(amount, days + 1, c)
    assert res_more["penalty_uzs"] >= res["penalty_uzs"]


@given(
    unpaid=st.decimals(min_value=Decimal("0"), max_value=Decimal("500000000"), places=2, allow_nan=False, allow_infinity=False),
    days=st.integers(min_value=0, max_value=730),
)
def test_labor_delay_compensation_properties(unpaid: Decimal, days: int) -> None:
    c = load_constants()
    res = labor_delay_compensation(unpaid, days, c)
    assert res["compensation_uzs"] >= Decimal("0.00")
    res_more = labor_delay_compensation(unpaid, days + 5, c)
    assert res_more["compensation_uzs"] >= res["compensation_uzs"]


def test_no_hardcoded_constants_in_rules_engine() -> None:
    """Changing ConstantsSnapshot MUST change every calculated outcome — proving zero hardcoded legal constants."""
    base = load_constants()

    # 1. BHM ratio & Art. 108 threshold
    r1 = bhm_ratio(Decimal("3750000"), base)
    r2 = bhm_ratio(Decimal("3750000"), _mutate_constant(base, "bhm_uzs", Decimal("500000")))
    assert r1["ratio"] != r2["ratio"]

    wf1 = check_written_form(Decimal("3750000"), base)
    wf2 = check_written_form(Decimal("3750000"), _mutate_constant(base, "civil_code.simple_written_form_threshold_bhm", Decimal("5")))
    assert wf1["mandatory_written"] is False
    assert wf2["mandatory_written"] is True

    # 2. Consumer penalty rate
    cp1 = consumer_penalty(Decimal("1000000"), 10, base)
    cp2 = consumer_penalty(Decimal("1000000"), 10, _mutate_constant(base, "consumer.daily_penalty_rate", Decimal("0.02")))
    assert cp2["penalty_uzs"] == cp1["penalty_uzs"] * Decimal("2")

    # 3. Labor delay refinancing rate
    lb1 = labor_delay_compensation(Decimal("5000000"), 30, base)
    lb2 = labor_delay_compensation(Decimal("5000000"), 30, _mutate_constant(base, "labor.delay_annual_refinancing_rate", Decimal("0.27")))
    assert lb2["compensation_uzs"] > lb1["compensation_uzs"]

    # 4. Limitation window
    lm1 = limitation_deadline("labor", date(2026, 1, 1), base, today=date(2026, 2, 1))
    lm2 = limitation_deadline("labor", date(2026, 1, 1), _mutate_constant(base, "limitation.labor_days", Decimal("30")), today=date(2026, 2, 1))
    assert lm1["status"] == "ok"
    assert lm2["status"] == "expired"


def test_golden_table_all_rule_functions() -> None:
    c = load_constants()

    # consumer_penalty cap at 100%
    capped = consumer_penalty(Decimal("2000000"), 150, c)
    assert capped["penalty_uzs"] == Decimal("2000000.00")
    assert capped["capped"] is True
    assert capped["needs_review"] is True

    # response_deadline
    rd = response_deadline("consumer", date(2026, 3, 1), c)
    assert rd["days"] == 10
    assert rd["deadline_date"] == "2026-03-11"

    # traffic_appeal_window
    tw = traffic_appeal_window(date(2026, 5, 1), c, today=date(2026, 5, 8))
    assert tw["appeal_open"] is True
    assert tw["discount_50_open"] is True
    assert tw["discount_30_open"] is True

    tw_late = traffic_appeal_window(date(2026, 5, 1), c, today=date(2026, 5, 25))
    assert tw_late["appeal_open"] is False
    assert tw_late["discount_50_open"] is False
    assert tw_late["discount_30_open"] is True

    # case_strength
    strong = case_strength(
        {
            "has_written_evidence": True,
            "incident_date": date(2026, 5, 1),
            "delay_days": 14,
            "claim_amount_uzs": Decimal("4500000"),
            "limitation_status": "ok",
            "legal_refs": ["inst_consumer_19"],
            "respondent_name": "TechnoMart MCHJ",
        },
        c,
    )
    assert strong["score"] == 100
    assert sum(strong["breakdown"].values()) == 100

    weak = case_strength(
        {
            "has_written_evidence": False,
            "incident_date": None,
            "delay_days": 0,
            "claim_amount_uzs": Decimal("0"),
            "limitation_status": "expired",
            "legal_refs": [],
            "respondent_name": "",
        },
        c,
    )
    assert weak["score"] < 40


@pytest.mark.parametrize(
    ("amount", "lang", "expected_substr"),
    [
        (Decimal("0"), "uz_lat", "nol so'm"),
        (Decimal("0"), "uz_cyr", "нол сўм"),
        (Decimal("0"), "ru", "ноль сумов"),
        (Decimal("1000000"), "uz_lat", "bir million so'm"),
        (Decimal("1000000"), "uz_cyr", "бир миллион сўм"),
        (Decimal("1000000"), "ru", "один миллион сумов"),
        (Decimal("12345678.90"), "uz_lat", "o'n ikki million uch yuz qirq besh ming olti yuz yetmish sakkiz so'm 90 tiyin"),
        (Decimal("12345678.90"), "ru", "двенадцать миллионов триста сорок пять тысяч шестьсот семьдесят восемь сумов 90 тийинов"),
    ],
)
def test_amount_in_words_trilingual(amount: Decimal, lang: str, expected_substr: str) -> None:
    out = amount_in_words(amount, lang)
    assert expected_substr in out


def test_uzbek_transliterator_and_normalizer() -> None:
    assert "Ўзбекистон" in latin_to_cyrillic("O'zbekiston")
    assert "шартнома" in latin_to_cyrillic("shartnoma")
    assert "компенсация" in latin_to_cyrillic("kompensatsiya")
    assert normalize_uz_text("O‘zbekiston g‘oyasi") == "O'zbekiston g'oyasi"
