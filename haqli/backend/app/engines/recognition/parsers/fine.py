"""Administrative decision / traffic fine parser (§6.1) feeding Himoya traffic wizard + `traffic_appeal_window`."""

from __future__ import annotations

import re
from datetime import date
from typing import Any

from app.engines.recognition.entities.dates import extract_dates
from app.engines.recognition.entities.ids import extract_plates
from app.engines.recognition.entities.money import extract_money
from app.engines.recognition.types import Field, RouteHint

_DECISION_NUM_RE = re.compile(r"(?:qaror[i]?|постановлен\w*|№|no\.?)\s*[:#№]?\s*([A-ZА-Я0-9/\-]{5,26})", re.IGNORECASE)
_ARTICLE_RE = re.compile(r"(\d+(?:[-.]\d+)?)\s*-?\s*(?:modda|модда)|(?:ст\.?|статья)\s*(\d+(?:[-.]\d+)?)", re.IGNORECASE)
_TIME_RE = re.compile(r"\b([01]?\d|2[0-3]):([0-5]\d)\b")
_DISCOUNT_RE = re.compile(r"((?:50%|30%|chegirma|скидк\w*)[^\n.]{0,80})", re.IGNORECASE)
_LOC_RE = re.compile(r"(?:manzil|joy|место|улица|ko['ʻ’]?cha\w*)\s*[:\-]?\s*([^\n]{5,90})", re.IGNORECASE)


def parse_fine(text: str, *, today: date | None = None) -> tuple[list[Field], RouteHint, list[str]]:
    """Extract structured traffic fine fields and build `himoya/traffic` RouteHint."""
    fields: list[Field] = []
    warnings: list[str] = []

    dec_m = _DECISION_NUM_RE.search(text)
    if dec_m:
        fields.append(Field(key="decisionNumber", value=dec_m.group(1), display=dec_m.group(1), confidence=0.92, source="rule", span=dec_m.span(1)))

    dates = extract_dates(text, today=today)
    decision_date = dates[0] if dates else None
    if decision_date:
        fields.append(
            Field(
                key="decisionDate",
                value=decision_date.value,
                display=decision_date.value.isoformat(),
                confidence=decision_date.confidence,
                source="rule",
                span=decision_date.span,
            )
        )

    moneys = extract_money(text)
    amount_m = max(moneys, key=lambda m: m.amount) if moneys else None
    if amount_m:
        fields.append(
            Field(
                key="fineAmountUzs",
                value=amount_m.amount,
                display=str(amount_m.amount),
                confidence=amount_m.confidence,
                source="rule",
                span=amount_m.span,
                needs_confirm=amount_m.needs_confirm,
            )
        )

    art_m = _ARTICLE_RE.search(text)
    article_val = (art_m.group(1) or art_m.group(2)) if art_m else None
    if art_m and article_val:
        fields.append(Field(key="articleRef", value=article_val, display=article_val, confidence=0.92, source="rule", span=art_m.span()))

    plates = extract_plates(text)
    plate = plates[0] if plates else None
    if plate:
        fields.append(Field(key="vehiclePlate", value=plate.value, display=plate.display, confidence=plate.confidence, source="rule", span=plate.span))

    authority = "YHXX / IIB"
    if re.search(r"toshkent|ташкент", text, re.IGNORECASE):
        authority = "Toshkent shahar IIBB YHXB"
    elif re.search(r"samarqand|самарканд", text, re.IGNORECASE):
        authority = "Samarqand viloyati IIB YHXB"
    fields.append(Field(key="issuingAuthority", value=authority, display=authority, confidence=0.88, source="rule"))

    loc_m = _LOC_RE.search(text)
    if loc_m:
        fields.append(Field(key="violationLocation", value=loc_m.group(1).strip(), display=loc_m.group(1).strip(), confidence=0.80, source="rule", span=loc_m.span(1)))

    time_m = _TIME_RE.search(text)
    if time_m:
        fields.append(Field(key="violationTime", value=time_m.group(0), display=time_m.group(0), confidence=0.90, source="rule", span=time_m.span()))

    disc_m = _DISCOUNT_RE.search(text)
    if disc_m:
        fields.append(Field(key="discountNotice", value=disc_m.group(1).strip(), display=disc_m.group(1).strip(), confidence=0.85, source="rule", span=disc_m.span(1)))

    prefill: dict[str, Any] = {
        "decision_date": decision_date.value.isoformat() if decision_date else None,
        "claim_amount_uzs": str(amount_m.amount) if amount_m else None,
        "respondent_name": authority,
        "article": article_val,
        "plate": plate.value if plate else None,
    }
    route = RouteHint(target="jarima", category="traffic", prefill={k: v for k, v in prefill.items() if v is not None})
    return fields, route, warnings
