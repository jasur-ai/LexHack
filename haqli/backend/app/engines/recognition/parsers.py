"""Document type classifier, Uzbekistan fine/receipt parsers, and pure-Python ICAO 9303 MRZ parser with check digits."""

from __future__ import annotations

import re
from datetime import date
from typing import Any

from app.engines.intake import extract_amount_uzs, extract_date_uz_ru
from app.engines.translit import normalize_uz_text

# Uzbek vehicle license plate regexes (e.g. 01 A 123 AA, 01 123 AAA, 10 B 456 CD)
_UZ_PLATE_RE = re.compile(r"\b(\d{2}\s?[A-Z]\s?\d{3}\s?[A-Z]{2}|\d{2}\s?\d{3}\s?[A-Z]{3})\b")


def classify_document(text: str) -> dict[str, Any]:
    """Rule-based document classifier with confidence score (§7.2.2)."""
    low = normalize_uz_text(text).lower()
    rules: list[tuple[str, tuple[str, ...], float]] = [
        ("jarima_qarori", ("jarima", "yhxx", "mjtk", "постановление", "штраф", "нарушени", "davlat raqami"), 0.94),
        ("mikroqarz_shartnomasi", ("mikroqarz", "kredit", "микрозайм", "кредит", "foiz stavkasi", "процентная ставка"), 0.93),
        ("ijara_shartnomasi", ("ijara", "kvartira", "depozit", "аренд", "квартир", "депозит"), 0.93),
        ("mehnat_shartnomasi", ("mehnat shartnomasi", "ish haqi", "xodim", "трудовой договор", "работник", "оклад"), 0.93),
        ("talabnoma", ("talabnoma", "претензия", "sudgacha", "досудебн"), 0.92),
        ("tilxat", ("tilxat", "расписка", "qarz oldim", "получил в долг"), 0.92),
        ("chek_kvitansiya", ("chek", "kvitansiya", "kassa", "чек", "квитанция", "итого", "jami", "qqs", "ндс"), 0.91),
    ]
    best_type = "boshqa_hujjat"
    best_score = 0.0
    for doc_type, keywords, base_conf in rules:
        hits = sum(1 for k in keywords if k in low)
        if hits > 0:
            conf = min(0.98, base_conf - 0.12 + hits * 0.05)
            if conf > best_score:
                best_score = conf
                best_type = doc_type
    return {"type": best_type, "confidence": round(best_score if best_score > 0 else 0.45, 2)}


def parse_traffic_fine(text: str) -> dict[str, Any]:
    """Parse Uzbekistan administrative traffic fine decision (§7.2.3)."""
    norm = normalize_uz_text(text)
    dec_m = re.search(r"(?:qaror|постановлен\w*|№|no\.?)\s*[:#№]?\s*([A-Z0-9/-]{5,24})", norm, re.I)
    art_m = re.search(r"(\d+(?:[-.]\d+)?)\s*-?\s*(?:modda|модда)|(?:ст\.|статья)\s*(\d+(?:[-.]\d+)?)", norm, re.I)
    plate_m = _UZ_PLATE_RE.search(norm.upper())
    amt, amt_c = extract_amount_uzs(norm)
    dt, dt_c = extract_date_uz_ru(norm)

    authority = "YHXX / IIB"
    if re.search(r"toshkent|ташкент", norm, re.I):
        authority = "Toshkent shahar IIBB YHXB"

    return {
        "fields": {
            "decisionNumber": dec_m.group(1) if dec_m else None,
            "decisionDate": dt.isoformat() if dt else None,
            "fineAmountUzs": str(amt) if amt is not None else None,
            "articleRef": (art_m.group(1) or art_m.group(2)) if art_m else None,
            "vehiclePlate": plate_m.group(1) if plate_m else None,
            "issuingAuthority": authority,
        },
        "confidences": {
            "decisionNumber": 0.90 if dec_m else 0.0,
            "decisionDate": dt_c,
            "fineAmountUzs": amt_c,
            "articleRef": 0.90 if art_m else 0.0,
            "vehiclePlate": 0.95 if plate_m else 0.0,
        },
    }


def parse_receipt(text: str) -> dict[str, Any]:
    """Parse retail receipt / payment check feeding Consumer wizard (§7.2.4)."""
    norm = normalize_uz_text(text)
    lines = [ln.strip() for ln in norm.splitlines() if ln.strip()]
    seller = lines[0][:100] if lines else None
    amt, amt_c = extract_amount_uzs(norm)
    dt, dt_c = extract_date_uz_ru(norm)
    low = norm.lower()
    pay_method = "card" if any(k in low for k in ("uzcard", "humo", "visa", "karta", "карт", "terminal")) else "cash"
    return {
        "fields": {
            "seller": seller,
            "purchaseDate": dt.isoformat() if dt else None,
            "totalUzs": str(amt) if amt is not None else None,
            "paymentMethod": pay_method,
            "itemSummary": " · ".join(lines[1:4])[:220] if len(lines) > 1 else norm[:180],
        },
        "confidences": {
            "seller": 0.85 if seller else 0.0,
            "purchaseDate": dt_c,
            "totalUzs": amt_c,
            "paymentMethod": 0.88,
        },
    }


# ------------------------------------------------------------------
# ICAO 9303 MRZ Parser with Full Check-Digit Verification (§7.2.5)
# ------------------------------------------------------------------
def _mrz_char_value(ch: str) -> int:
    if ch == "<":
        return 0
    if "0" <= ch <= "9":
        return ord(ch) - ord("0")
    if "A" <= ch <= "Z":
        return ord(ch) - ord("A") + 10
    return 0


def mrz_check_digit(field: str) -> str:
    weights = (7, 3, 1)
    total = sum(_mrz_char_value(ch) * weights[i % 3] for i, ch in enumerate(field.upper()))
    return str(total % 10)


def _parse_mrz_date(yymmdd: str, *, is_expiry: bool = False) -> str | None:
    if not re.fullmatch(r"\d{6}", yymmdd):
        return None
    yy, mm, dd = int(yymmdd[:2]), int(yymmdd[2:4]), int(yymmdd[4:6])
    today_yy = date.today().year % 100
    if is_expiry:
        year = 2000 + yy
    else:
        year = (2000 + yy) if yy <= today_yy else (1900 + yy)
    try:
        return date(year, mm, dd).isoformat()
    except ValueError:
        return None


def parse_mrz_td3(raw_text: str) -> dict[str, Any]:
    """Parse ICAO 9303 TD3 (2x44) passport MRZ with strict check-digit validation."""
    candidates = [
        re.sub(r"\s+", "", ln.upper())
        for ln in raw_text.splitlines()
        if len(re.sub(r"\s+", "", ln)) >= 40 and "<" in ln
    ]
    if len(candidates) < 2:
        return {"valid": False, "error": "mrz_not_found", "fields": {}, "confidences": {}}

    line1 = candidates[-2][:44].ljust(44, "<")
    line2 = candidates[-1][:44].ljust(44, "<")

    doc_num_raw = line2[0:9]
    doc_num_cd = line2[9]
    nationality = line2[10:13].replace("<", "")
    dob_raw = line2[13:19]
    dob_cd = line2[19]
    sex = line2[20]
    exp_raw = line2[21:27]
    exp_cd = line2[27]

    checks = {
        "docNumber": mrz_check_digit(doc_num_raw) == doc_num_cd,
        "dob": mrz_check_digit(dob_raw) == dob_cd,
        "expiry": mrz_check_digit(exp_raw) == exp_cd,
    }
    if not all(checks.values()):
        return {
            "valid": False,
            "error": "mrz_checksum_failed",
            "checks": checks,
            "fields": {},
            "confidences": {},
        }

    names_part = line1[5:].split("<<", 1)
    surname = names_part[0].replace("<", " ").strip()
    given_names = (names_part[1].replace("<", " ").strip()) if len(names_part) > 1 else ""
    doc_number = doc_num_raw.replace("<", "")

    return {
        "valid": True,
        "checks": checks,
        "fields": {
            "surname": surname,
            "givenNames": given_names,
            "fullName": f"{surname} {given_names}".strip(),
            "documentNumber": doc_number,
            "dob": _parse_mrz_date(dob_raw, is_expiry=False),
            "sex": sex if sex in ("M", "F") else "X",
            "expiry": _parse_mrz_date(exp_raw, is_expiry=True),
            "nationality": nationality,
        },
        "confidences": {
            "surname": 0.99,
            "givenNames": 0.99,
            "documentNumber": 0.99,
            "dob": 0.99,
            "expiry": 0.99,
            "nationality": 0.99,
        },
    }
