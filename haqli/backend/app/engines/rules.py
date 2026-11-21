"""Deterministic legal mathematics engine (§6) — pure functions, Decimal money, zero hardcoded legal constants."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any

from app.engines.translit import latin_to_cyrillic

TWO_DP = Decimal("0.01")


def _q2(val: Decimal) -> Decimal:
    return val.quantize(TWO_DP, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class ConstantEntry:
    key: str
    value: Decimal
    unit: str
    effective_from: str
    source_ref: str
    status: str
    legal_ref: str


@dataclass(frozen=True)
class ConstantsSnapshot:
    """Immutable versioned legal constants loaded from `backend/app/legal_data/constants.json`."""

    version: str
    entries: dict[str, ConstantEntry]

    def get(self, key: str) -> ConstantEntry:
        if key not in self.entries:
            raise KeyError(f"Missing legal constant '{key}' in constants snapshot {self.version}.")
        return self.entries[key]

    def val(self, key: str) -> Decimal:
        return self.get(key).value

    def has_unverified(self, keys: list[str]) -> bool:
        return any(self.get(k).status != "verified" for k in keys)


def load_constants(path: Path | None = None) -> ConstantsSnapshot:
    target = path or (Path(__file__).resolve().parent.parent / "legal_data" / "constants.json")
    raw = json.loads(target.read_text(encoding="utf-8"))
    parsed: dict[str, ConstantEntry] = {}
    for key, item in raw["entries"].items():
        parsed[key] = ConstantEntry(
            key=key,
            value=Decimal(str(item["value"])),
            unit=str(item.get("unit", "")),
            effective_from=str(item.get("effective_from", "")),
            source_ref=str(item.get("source_ref", "")),
            status=str(item.get("status", "needs_review")),
            legal_ref=str(item.get("legal_ref", "")),
        )
    return ConstantsSnapshot(version=str(raw["version"]), entries=parsed)


# ------------------------------------------------------------------
# 1. bhm_ratio
# ------------------------------------------------------------------
def bhm_ratio(amount: Decimal, c: ConstantsSnapshot) -> dict[str, Any]:
    amt = max(Decimal("0"), Decimal(str(amount)))
    bhm = c.get("bhm_uzs")
    ratio = _q2(amt / bhm.value) if bhm.value > 0 else Decimal("0.00")
    return {
        "ratio": ratio,
        "bhm_uzs": bhm.value,
        "status": bhm.status,
        "legal_refs": [bhm.legal_ref],
        "constants_version": c.version,
    }


# ------------------------------------------------------------------
# 2. check_written_form
# ------------------------------------------------------------------
def check_written_form(amount: Decimal, c: ConstantsSnapshot) -> dict[str, Any]:
    ratio_res = bhm_ratio(amount, c)
    thresh = c.get("civil_code.simple_written_form_threshold_bhm")
    mandatory = ratio_res["ratio"] > thresh.value
    return {
        "ratio": ratio_res["ratio"],
        "threshold_bhm": thresh.value,
        "threshold_uzs": _q2(thresh.value * c.val("bhm_uzs")),
        "mandatory_written": mandatory,
        "banner_level": "warning" if mandatory else "info",
        "needs_review": c.has_unverified(["bhm_uzs", "civil_code.simple_written_form_threshold_bhm"]),
        "legal_refs": list(dict.fromkeys([*ratio_res["legal_refs"], thresh.legal_ref])),
        "constants_version": c.version,
    }


# ------------------------------------------------------------------
# 3. consumer_penalty
# ------------------------------------------------------------------
def consumer_penalty(amount: Decimal, delay_days: int, c: ConstantsSnapshot) -> dict[str, Any]:
    amt = max(Decimal("0"), Decimal(str(amount)))
    days = max(0, int(delay_days))
    rate_e = c.get("consumer.daily_penalty_rate")
    cap_e = c.get("consumer.penalty_cap_ratio")

    raw_penalty = amt * rate_e.value * Decimal(days)
    cap_amount = amt * cap_e.value
    penalty = _q2(min(raw_penalty, cap_amount))
    capped = raw_penalty > cap_amount
    rate_pct = _q2(rate_e.value * Decimal("100"))

    return {
        "claim_amount_uzs": _q2(amt),
        "delay_days": days,
        "daily_rate": rate_e.value,
        "penalty_uzs": penalty,
        "total_uzs": _q2(amt + penalty),
        "capped": capped,
        "formula": f"{_q2(amt)} × {rate_pct}% × {days} kun" + (" (chegara 100%)" if capped else ""),
        "confidence": "low" if c.has_unverified(["consumer.daily_penalty_rate", "consumer.penalty_cap_ratio"]) else "high",
        "needs_review": c.has_unverified(["consumer.daily_penalty_rate", "consumer.penalty_cap_ratio"]),
        "legal_refs": list(dict.fromkeys([rate_e.legal_ref, cap_e.legal_ref])),
        "constants_version": c.version,
    }


# ------------------------------------------------------------------
# 4. labor_delay_compensation
# ------------------------------------------------------------------
def labor_delay_compensation(unpaid: Decimal, delay_days: int, c: ConstantsSnapshot) -> dict[str, Any]:
    amt = max(Decimal("0"), Decimal(str(unpaid)))
    days = max(0, int(delay_days))
    ann_e = c.get("labor.delay_annual_refinancing_rate")
    mult_e = c.get("labor.delay_rate_multiplier")

    # Daily compensation = unpaid * (refinancing_rate * multiplier / 365) * days
    daily_rate = (ann_e.value * mult_e.value) / Decimal("365")
    comp = _q2(amt * daily_rate * Decimal(days))
    needs_rev = c.has_unverified(["labor.delay_annual_refinancing_rate", "labor.delay_rate_multiplier"])

    return {
        "unpaid_uzs": _q2(amt),
        "delay_days": days,
        "compensation_uzs": comp,
        "total_uzs": _q2(amt + comp),
        "formula": f"{_q2(amt)} × ({_q2(ann_e.value * 100)}% × {_q2(mult_e.value * 100)}% / 365) × {days} kun",
        "confidence": "low" if needs_rev else "high",
        "needs_review": needs_rev,
        "legal_refs": list(dict.fromkeys([ann_e.legal_ref, mult_e.legal_ref])),
        "constants_version": c.version,
    }


# ------------------------------------------------------------------
# 5. limitation_deadline
# ------------------------------------------------------------------
def limitation_deadline(
    category: str,
    incident_date: date,
    c: ConstantsSnapshot,
    *,
    today: date | None = None,
) -> dict[str, Any]:
    ref_today = today or date.today()
    if category == "labor":
        entry = c.get("limitation.labor_days")
    elif category == "traffic":
        entry = c.get("limitation.traffic_appeal_days")
    else:
        entry = c.get("limitation.general_civil_days")

    window_days = int(entry.value)
    end_date = incident_date + timedelta(days=window_days)
    days_remaining = (end_date - ref_today).days

    if days_remaining < 0:
        status = "expired"
    elif days_remaining < 7:
        status = "urgent"
    else:
        status = "ok"

    return {
        "category": category,
        "window_days": window_days,
        "end_date": end_date.isoformat(),
        "days_remaining": days_remaining,
        "status": status,
        "needs_review": entry.status != "verified",
        "legal_refs": [entry.legal_ref],
        "constants_version": c.version,
    }


# ------------------------------------------------------------------
# 6. response_deadline
# ------------------------------------------------------------------
def response_deadline(doc_type: str, issue_date: date, c: ConstantsSnapshot) -> dict[str, Any]:
    key_map = {
        "consumer": "response_deadline.consumer_days",
        "complaint": "response_deadline.complaint_days",
        "talabnoma": "response_deadline.talabnoma_days",
    }
    entry = c.get(key_map.get(doc_type, "response_deadline.talabnoma_days"))
    days = int(entry.value)
    due = issue_date + timedelta(days=days)
    return {
        "doc_type": doc_type,
        "days": days,
        "deadline_date": due.isoformat(),
        "needs_review": entry.status != "verified",
        "legal_refs": [entry.legal_ref],
        "constants_version": c.version,
    }


# ------------------------------------------------------------------
# 7. traffic_appeal_window
# ------------------------------------------------------------------
def traffic_appeal_window(
    decision_date: date,
    c: ConstantsSnapshot,
    *,
    today: date | None = None,
) -> dict[str, Any]:
    ref_today = today or date.today()
    app_e = c.get("limitation.traffic_appeal_days")
    d50_e = c.get("traffic.discount_50_days")
    d30_e = c.get("traffic.discount_30_days")

    last_appeal = decision_date + timedelta(days=int(app_e.value))
    d50_until = decision_date + timedelta(days=int(d50_e.value))
    d30_until = decision_date + timedelta(days=int(d30_e.value))

    return {
        "decision_date": decision_date.isoformat(),
        "last_appeal_date": last_appeal.isoformat(),
        "appeal_days_remaining": (last_appeal - ref_today).days,
        "appeal_open": ref_today <= last_appeal,
        "discount_50_until": d50_until.isoformat(),
        "discount_50_open": ref_today <= d50_until,
        "discount_30_until": d30_until.isoformat(),
        "discount_30_open": ref_today <= d30_until,
        "needs_review": c.has_unverified(["limitation.traffic_appeal_days", "traffic.discount_50_days", "traffic.discount_30_days"]),
        "legal_refs": list(dict.fromkeys([app_e.legal_ref, d50_e.legal_ref, d30_e.legal_ref])),
        "constants_version": c.version,
    }


# ------------------------------------------------------------------
# 8. case_strength (explicit deterministic rubric, NEVER LLM-generated)
# ------------------------------------------------------------------
def case_strength(facts: dict[str, Any], c: ConstantsSnapshot) -> dict[str, Any]:
    breakdown: dict[str, int] = {}

    has_written = bool(facts.get("has_written_evidence") or facts.get("evidence_count", 0) > 0)
    breakdown["written_evidence"] = 25 if has_written else 5

    dates_ok = bool(facts.get("incident_date")) and int(facts.get("delay_days", 0)) >= 0
    breakdown["dates_consistent"] = 15 if dates_ok else 5

    amount_ok = Decimal(str(facts.get("claim_amount_uzs", 0))) > 0
    breakdown["amount_documented"] = 15 if amount_ok else 6

    lim_status = str(facts.get("limitation_status", "ok"))
    breakdown["within_limitation"] = 15 if lim_status == "ok" else (10 if lim_status == "urgent" else 0)

    has_basis = bool(facts.get("legal_refs"))
    breakdown["clear_statutory_basis"] = 20 if has_basis else 8

    counterparty_ok = len(str(facts.get("respondent_name", "")).strip()) >= 2
    breakdown["counterparty_identified"] = 10 if counterparty_ok else 0

    total = min(100, sum(breakdown.values()))
    return {
        "score": total,
        "breakdown": breakdown,
        "legal_refs": list(facts.get("legal_refs", [])),
        "constants_version": c.version,
    }


# ------------------------------------------------------------------
# 9. amount_in_words (uz_lat, uz_cyr, ru)
# ------------------------------------------------------------------
_UZ_ONES = ["", "bir", "ikki", "uch", "to'rt", "besh", "olti", "yetti", "sakkiz", "to'qqiz"]
_UZ_TENS = ["", "o'n", "yigirma", "o'ttiz", "qirq", "ellik", "oltmish", "yetmish", "sakson", "to'qson"]
_UZ_SCALES = ["", "ming", "million", "milliard", "trillion"]

_RU_ONES_M = ["", "один", "два", "три", "четыре", "пять", "шесть", "семь", "восемь", "девять"]
_RU_ONES_F = ["", "одна", "две", "три", "четыре", "пять", "шесть", "семь", "восемь", "девять"]
_RU_TEENS = ["десять", "одиннадцать", "двенадцать", "тринадцать", "четырнадцать", "пятнадцать", "шестнадцать", "семнадцать", "восемнадцать", "девятнадцать"]
_RU_TENS = ["", "", "двадцать", "тридцать", "сорок", "пятьдесят", "шестьдесят", "семьдесят", "восемьдесят", "девяносто"]
_RU_HUNDREDS = ["", "сто", "двести", "триста", "четыреста", "пятьсот", "шестьсот", "семьсот", "восемьсот", "девятьсот"]


def _ru_plural(n: int, form1: str, form2: str, form5: str) -> str:
    n100 = abs(n) % 100
    n10 = n100 % 10
    if 11 <= n100 <= 19:
        return form5
    if n10 == 1:
        return form1
    if 2 <= n10 <= 4:
        return form2
    return form5


def _uz_triplet(n: int) -> str:
    parts: list[str] = []
    h = n // 100
    rem = n % 100
    t = rem // 10
    o = rem % 10
    if h:
        parts.append(f"{_UZ_ONES[h]} yuz")
    if t:
        parts.append(_UZ_TENS[t])
    if o:
        parts.append(_UZ_ONES[o])
    return " ".join(parts)


def _ru_triplet(n: int, feminine: bool = False) -> str:
    parts: list[str] = []
    h = n // 100
    rem = n % 100
    if h:
        parts.append(_RU_HUNDREDS[h])
    if 10 <= rem <= 19:
        parts.append(_RU_TEENS[rem - 10])
    else:
        t = rem // 10
        o = rem % 10
        if t:
            parts.append(_RU_TENS[t])
        if o:
            parts.append(_RU_ONES_F[o] if feminine else _RU_ONES_M[o])
    return " ".join(parts)


def amount_in_words(amount: Decimal | int | float | str, lang: str = "uz_lat") -> str:
    """Spell out a UZS currency amount (including tiyin decimals) in uz_lat, uz_cyr, or ru."""
    dec = _q2(max(Decimal("0"), Decimal(str(amount))))
    whole = int(dec)
    tiyin = int((dec - Decimal(whole)) * 100)

    if lang == "ru":
        if whole == 0:
            whole_str = "ноль"
        else:
            scales = [
                ("", "", "", False),
                ("тысяча", "тысячи", "тысяч", True),
                ("миллион", "миллиона", "миллионов", False),
                ("миллиард", "миллиарда", "миллиардов", False),
                ("триллион", "триллиона", "триллионов", False),
            ]
            chunks: list[str] = []
            idx = 0
            n = whole
            while n > 0:
                trip = n % 1000
                if trip:
                    f1, f2, f5, fem = scales[idx]
                    w = _ru_triplet(trip, feminine=fem)
                    unit = _ru_plural(trip, f1, f2, f5) if idx > 0 else ""
                    chunks.append(f"{w} {unit}".strip())
                n //= 1000
                idx += 1
            whole_str = " ".join(reversed(chunks))
        cur = _ru_plural(whole, "сум", "сума", "сумов")
        if tiyin > 0:
            t_cur = _ru_plural(tiyin, "тийин", "тийина", "тийинов")
            return f"{whole_str} {cur} {tiyin:02d} {t_cur}"
        return f"{whole_str} {cur}"

    # Uzbek Latin (and Cyrillic via transliterator)
    if whole == 0:
        whole_str = "nol"
    else:
        chunks = []
        idx = 0
        n = whole
        while n > 0:
            trip = n % 1000
            if trip:
                w = _uz_triplet(trip)
                scale = _UZ_SCALES[idx]
                chunks.append(f"{w} {scale}".strip())
            n //= 1000
            idx += 1
        whole_str = " ".join(reversed(chunks))

    res_lat = f"{whole_str} so'm {tiyin:02d} tiyin" if tiyin > 0 else f"{whole_str} so'm"
    return latin_to_cyrillic(res_lat) if lang == "uz_cyr" else res_lat
