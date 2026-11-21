"""Deterministic Uzbek/Russian entity & intake extractor (amounts in words/digits, dates, names, passports) + optional LLM."""

from __future__ import annotations

import re
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from pydantic import BaseModel

from app.engines.llm.provider import ProviderUnavailable, get_llm_gateway, quote_untrusted_user_text
from app.engines.translit import normalize_uz_text

_WORD_NUMS_UZ_RU: dict[str, int] = {
    "bir": 1, "ikki": 2, "uch": 3, "to'rt": 4, "besh": 5, "olti": 6, "yetti": 7, "sakkiz": 8, "to'qqiz": 9,
    "o'n": 10, "yigirma": 20, "o'ttiz": 30, "qirq": 40, "ellik": 50, "oltmish": 60, "yetmish": 70, "sakson": 80, "to'qson": 90,
    "yuz": 100,
    "один": 1, "одна": 1, "два": 2, "две": 2, "три": 3, "четыре": 4, "пять": 5, "шесть": 6, "семь": 7, "восемь": 8, "девять": 9,
    "десять": 10, "двадцать": 20, "тридцать": 30, "сорок": 40, "пятьдесят": 50,
}

_MONTHS: dict[str, int] = {
    "yanvar": 1, "fevral": 2, "mart": 3, "aprel": 4, "may": 5, "iyun": 6,
    "iyul": 7, "avgust": 8, "sentabr": 9, "sentyabr": 9, "oktabr": 10, "oktyabr": 10, "noyabr": 11, "dekabr": 12,
    "января": 1, "февраля": 2, "марта": 3, "апреля": 4, "мая": 5, "июня": 6,
    "июля": 7, "августа": 8, "сентября": 9, "октября": 10, "ноября": 11, "декабря": 12,
}

_PASSPORT_RE = re.compile(r"\b([A-Z]{2}\s?\d{7})\b")


def extract_amount_uzs(text: str) -> tuple[Decimal | None, float]:
    """Extract monetary amount in UZS from digits ('5 mln', '4 500 000') or Uzbek/Russian words ('besh million')."""
    norm = normalize_uz_text(text).lower()

    # 1. Explicit million/ming numeric shorthand: "5 mln", "4.5 million", "500 ming"
    m_mln = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:mln|million|млн|миллион\w*)", norm)
    if m_mln:
        val = Decimal(m_mln.group(1).replace(",", ".")) * Decimal("1000000")
        return val.quantize(Decimal("0.01")), 0.94

    m_ming = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:ming|тыс|тысяч\w*)", norm)
    if m_ming:
        val = Decimal(m_ming.group(1).replace(",", ".")) * Decimal("1000")
        return val.quantize(Decimal("0.01")), 0.92

    # 2. Worded numbers: "besh million", "uch yuz ming", "пять миллионов"
    m_word = re.search(r"\b([a-z'а-яё]+(?:\s+[a-z'а-яё]+)?)\s+(million|ming|миллион\w*|тысяч\w*)\b", norm)
    if m_word:
        words = m_word.group(1).split()
        total = 0
        for w in words:
            if w in _WORD_NUMS_UZ_RU:
                v = _WORD_NUMS_UZ_RU[w]
                if v == 100 and total > 0:
                    total *= 100
                else:
                    total += v
        if total > 0:
            mult = 1_000_000 if m_word.group(2).startswith(("mill", "милл")) else 1_000
            return Decimal(total * mult).quantize(Decimal("0.01")), 0.88

    # 3. Raw grouped digits >= 4 digits: "4 500 000 so'm" or "12,345,678.90"
    m_num = re.search(r"\b(\d{1,3}(?:[\s,]\d{3})+(?:[.,]\d{1,2})?|\d{5,}(?:[.,]\d{1,2})?)\b", norm)
    if m_num:
        raw = m_num.group(1).replace(" ", "")
        # Distinguish thousands comma from decimal comma
        if raw.count(",") == 1 and len(raw.split(",")[1]) == 2:
            raw = raw.replace(",", ".")
        else:
            raw = raw.replace(",", "")
        try:
            return Decimal(raw).quantize(Decimal("0.01")), 0.93
        except Exception:
            pass

    return None, 0.0


def extract_date_uz_ru(text: str, *, today: date | None = None) -> tuple[date | None, float]:
    """Extract ISO, DD.MM.YYYY, '25-dekabr', or relative ('ertaga', 'o'tgan juma', 'завтра') dates."""
    ref = today or date.today()
    norm = normalize_uz_text(text).lower()

    m_iso = re.search(r"\b(\d{4})-(\d{2})-(\d{2})\b", norm)
    if m_iso:
        try:
            return date(int(m_iso.group(1)), int(m_iso.group(2)), int(m_iso.group(3))), 0.98
        except ValueError:
            pass

    m_dot = re.search(r"\b(\d{1,2})[./](\d{1,2})[./](\d{4})\b", norm)
    if m_dot:
        try:
            return date(int(m_dot.group(3)), int(m_dot.group(2)), int(m_dot.group(1))), 0.96
        except ValueError:
            pass

    m_month = re.search(r"\b(\d{1,2})\s*-?\s*(" + "|".join(_MONTHS.keys()) + r")(?:\s*,?\s*(\d{4}))?\b", norm)
    if m_month:
        day = int(m_month.group(1))
        month = _MONTHS[m_month.group(2)]
        year = int(m_month.group(3)) if m_month.group(3) else ref.year
        try:
            candidate = date(year, month, day)
            if not m_month.group(3) and candidate < ref - timedelta(days=30):
                candidate = date(year + 1, month, day)
            return candidate, 0.90
        except ValueError:
            pass

    if any(k in norm for k in ("ertaga", "завтра")):
        return ref + timedelta(days=1), 0.85
    if any(k in norm for k in ("kecha", "вчера")):
        return ref - timedelta(days=1), 0.85
    if any(k in norm for k in ("o'tgan juma", "прошлую пятницу")):
        delta = (ref.weekday() - 4) % 7 or 7
        return ref - timedelta(days=delta), 0.80
    if any(k in norm for k in ("bir oy", "1 oy", "через месяц")):
        return ref + timedelta(days=30), 0.78

    return None, 0.0


def extract_person_or_entity(text: str) -> tuple[str | None, float]:
    """Extract likely counterparty/person name (Capitalized Two-Word Uzbek/Russian name or LLC/MCHJ)."""
    m_org = re.search(r'(?:"([^"]{2,80})"|([A-ZА-ЯЎҚҒҲ][\w\s-]{2,40}\s+(?:MCHJ|МЧЖ|OOO|ООО|XK|AJ)))', text)
    if m_org:
        return (m_org.group(1) or m_org.group(2)).strip(), 0.86

    # Two capitalized words representing Surname + First name (e.g., Karimov Alisher)
    m_person = re.search(
        r"\b([A-ZА-ЯЎҚҒҲ][a-zа-яўқғҳ']{2,20}\s+[A-ZА-ЯЎҚҒҲ][a-zа-яўқғҳ']{2,20})\b",
        text,
    )
    if m_person:
        return m_person.group(1).strip(), 0.82
    return None, 0.0


def extract_passport(text: str) -> tuple[str | None, float]:
    m = _PASSPORT_RE.search(text.upper())
    if m:
        return re.sub(r"\s+", "", m.group(1)), 0.95
    return None, 0.0


def extract_entities_deterministic(text: str, *, today: date | None = None) -> dict[str, Any]:
    """Run deterministic entity extraction returning fields + per-field confidence scores."""
    amount, amt_c = extract_amount_uzs(text)
    dt, dt_c = extract_date_uz_ru(text, today=today)
    party, party_c = extract_person_or_entity(text)
    passport, pass_c = extract_passport(text)

    low = normalize_uz_text(text).lower()
    doc_type = "loan"
    if any(k in low for k in ("zaklad", "avans", "задаток", "аванс", "depozit")):
        doc_type = "deposit"
    elif any(k in low for k in ("xizmat", "ijara", "услуг", "аренд", "ta'mir")):
        doc_type = "service"

    fields: dict[str, Any] = {
        "docType": doc_type,
        "amountUzs": str(amount) if amount is not None else None,
        "dueDate": dt.isoformat() if dt is not None else None,
        "partyBName": party,
        "passportNumber": passport,
        "termsSummary": text.strip()[:300],
    }
    confidences = {
        "amountUzs": amt_c,
        "dueDate": dt_c,
        "partyBName": party_c,
        "passportNumber": pass_c,
    }
    overall = round(
        sum(v for v in confidences.values() if v > 0) / max(1, sum(1 for v in confidences.values() if v > 0)),
        2,
    )
    return {
        "fields": fields,
        "confidences": confidences,
        "overallConfidence": overall,
        "engine": "deterministic",
    }


class _LLMIntakeSchema(BaseModel):
    partyBName: str | None = None
    termsSummary: str | None = None


async def parse_intake_text(text: str, *, today: date | None = None) -> dict[str, Any]:
    """Deterministic entity extraction first, optionally enriched by LLM for prose/names (never overwrites numbers)."""
    base = extract_entities_deterministic(text, today=today)
    gateway = get_llm_gateway()
    try:
        prompt = (
            "Extract counterparty full name (partyBName) and concise 1-sentence summary (termsSummary) "
            "from the untrusted user utterance below. Do NOT invent numbers.\n"
            + quote_untrusted_user_text("utterance", text)
        )
        llm_res = await gateway.generate_structured(_LLMIntakeSchema, prompt)
        if not base["fields"]["partyBName"] and llm_res.partyBName:
            base["fields"]["partyBName"] = llm_res.partyBName
            base["confidences"]["partyBName"] = 0.72
        if llm_res.termsSummary:
            base["fields"]["termsSummary"] = llm_res.termsSummary
        base["engine"] = gateway.name
    except ProviderUnavailable:
        pass
    return base
