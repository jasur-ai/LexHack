"""Retail receipt / kvitansiya parser (§6.2) with STIR/TIN, line items, total consistency check -> himoya/consumer."""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal
from typing import Any

from app.engines.recognition.entities.dates import extract_dates
from app.engines.recognition.entities.money import extract_money
from app.engines.recognition.entities.numbers import extract_numbers
from app.engines.recognition.types import Field, RouteHint

_LEGAL_FORM_RE = re.compile(r"\b(mchj|ooo|ооо|мчж|xk|хк|yatt|ятт|ip|ип|aj|аж)\b", re.IGNORECASE)
_STIR_RE = re.compile(r"(?:stir|стир|inn|инн)\s*[:#№]?\s*(\d{9})\b", re.IGNORECASE)
_TOTAL_LINE_RE = re.compile(r"(?:jami|жами|итого|всего|total|to['ʻ’]?lov)\s*[:\-]?\s*(.+)", re.IGNORECASE)
_FISCAL_RE = re.compile(r"(?:fiskal|фискальн\w*|чек\s*№|chek\s*#|check\s*#)\s*[:#№]?\s*([A-Z0-9\-]{4,24})", re.IGNORECASE)
_ITEM_LINE_RE = re.compile(r"^(.{3,55}?)\s+(?:(\d+)\s*[xх*×]\s*)?(\d[\d\s\u00a0\u202f]{2,}(?:[.,]\d{2})?)\s*(?:so['ʻ’]?m|сум|сўм)?$", re.IGNORECASE)


def parse_receipt_v1(text: str, *, today: date | None = None, file_id: str | None = None) -> tuple[list[Field], RouteHint, list[str]]:
    """Parse retail check/kvitansiya with 1% item-sum vs total consistency verification."""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    fields: list[Field] = []
    warnings: list[str] = []

    # Seller: prefer first line containing a legal-form marker, otherwise first non-empty header line
    seller = next((ln for ln in lines[:4] if _LEGAL_FORM_RE.search(ln)), lines[0] if lines else None)
    if seller:
        fields.append(Field(key="seller", value=seller[:120], display=seller[:120], confidence=0.90 if _LEGAL_FORM_RE.search(seller) else 0.80, source="rule"))

    stir_m = _STIR_RE.search(text)
    if stir_m:
        fields.append(Field(key="sellerTin", value=stir_m.group(1), display=stir_m.group(1), confidence=0.96, source="rule", span=stir_m.span(1)))

    dates = extract_dates(text, today=today)
    pdate = dates[0] if dates else None
    if pdate:
        fields.append(Field(key="purchaseDate", value=pdate.value, display=pdate.value.isoformat(), confidence=pdate.confidence, source="rule", span=pdate.span))

    # Total: look near JAMI / ИТОГО / Total first, else largest extracted money amount
    total_val: Decimal | None = None
    total_conf = 0.88
    total_span: tuple[int, int] | None = None
    for m in _TOTAL_LINE_RE.finditer(text):
        nums = extract_numbers(m.group(1))
        if nums:
            cand = max(nums, key=lambda nm: nm.value)
            if total_val is None or cand.value > total_val:
                total_val = cand.value.quantize(Decimal("0.01"))
                total_conf = 0.95
                total_span = (m.start(1) + cand.span[0], m.start(1) + cand.span[1])

    if total_val is None:
        moneys = extract_money(text)
        if moneys:
            best = max(moneys, key=lambda mm: mm.amount)
            total_val = best.amount
            total_conf = best.confidence
            total_span = best.span

    # Line items & 1% sum consistency check (§6.2)
    items_sum = Decimal("0.00")
    item_count = 0
    for ln in lines[1:]:
        if _TOTAL_LINE_RE.search(ln) or re.search(r"\b(qqs|ндс|stir|инн|sana|дата)\b", ln, re.IGNORECASE):
            continue
        im = _ITEM_LINE_RE.match(ln)
        if im:
            qty = Decimal(im.group(2) or "1")
            price_nums = extract_numbers(im.group(3))
            if price_nums:
                items_sum += qty * price_nums[0].value
                item_count += 1

    if total_val is not None and item_count >= 2 and items_sum > 0:
        diff_ratio = abs(items_sum - total_val) / max(total_val, Decimal("1"))
        if diff_ratio > Decimal("0.01"):
            warnings.append("rec.warn.total_mismatch")
            total_conf = round(total_conf * 0.7, 2)

    if total_val is not None:
        fields.append(
            Field(
                key="totalUzs",
                value=total_val,
                display=str(total_val),
                confidence=total_conf,
                source="rule",
                span=total_span,
                needs_confirm=total_conf < 0.75,
            )
        )

    low = text.lower()
    if any(k in low for k in ("payme", "click", "uzum")):
        pay_method = next(k for k in ("payme", "click", "uzum") if k in low).capitalize()
    elif any(k in low for k in ("uzcard", "humo", "visa", "karta", "карт", "terminal")):
        pay_method = "card"
    else:
        pay_method = "cash"
    fields.append(Field(key="paymentMethod", value=pay_method, display=pay_method, confidence=0.88, source="rule"))

    fisc_m = _FISCAL_RE.search(text)
    if fisc_m:
        fields.append(Field(key="fiscalCheckNumber", value=fisc_m.group(1), display=fisc_m.group(1), confidence=0.92, source="rule", span=fisc_m.span(1)))

    prefill: dict[str, Any] = {
        "respondent_name": seller,
        "purchase_date": pdate.value.isoformat() if pdate else None,
        "amount_paid_uzs": str(total_val) if total_val is not None else None,
        "evidence_file_id": file_id,
    }
    route = RouteHint(target="himoya", category="consumer", prefill={k: v for k, v in prefill.items() if v is not None})
    return fields, route, warnings
