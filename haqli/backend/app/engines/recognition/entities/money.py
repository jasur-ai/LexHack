"""Money extractor wrapping `numbers.py` for UZS and foreign currencies (§6.5)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal

from app.engines.recognition.entities.numbers import extract_numbers

_UZS_RE = re.compile(r"^(?:\s*)(?:so['ʻ’]?m|sum|сум(?:ов|а)?|сўм|uzs)\b", re.IGNORECASE)
_USD_AFTER_RE = re.compile(r"^(?:\s*)(?:\$|usd|dollar(?:ga|dan|lik)?|доллар(?:ов|а|ы)?|бакс(?:ов)?|y\.e\.?|у\.е\.?)\b", re.IGNORECASE)
_EUR_AFTER_RE = re.compile(r"^(?:\s*)(?:€|eur|evro|евро)\b", re.IGNORECASE)
_USD_BEFORE_RE = re.compile(r"(?:\$|usd)\s*$", re.IGNORECASE)
_EUR_BEFORE_RE = re.compile(r"(?:€|eur)\s*$", re.IGNORECASE)


@dataclass(frozen=True)
class MoneyMatch:
    amount: Decimal
    currency: str  # "UZS" | "USD" | "EUR" | "UNKNOWN"
    raw: str
    span: tuple[int, int]
    confidence: float
    needs_confirm: bool


def extract_money(text: str) -> list[MoneyMatch]:
    """Extract currency amounts from Uzbek/Russian text. Foreign currencies are NEVER converted and get needs_confirm=True."""
    matches: list[MoneyMatch] = []
    for nm in extract_numbers(text):
        start, end = nm.span
        after = text[end : end + 24]
        before = text[max(0, start - 8) : start]

        currency = "UNKNOWN"
        full_start = start
        full_end = end

        if m := _UZS_RE.match(after):
            currency = "UZS"
            full_end = end + m.end()
        elif m := _USD_AFTER_RE.match(after):
            currency = "USD"
            full_end = end + m.end()
        elif m := _EUR_AFTER_RE.match(after):
            currency = "EUR"
            full_end = end + m.end()
        elif m := _USD_BEFORE_RE.search(before):
            currency = "USD"
            full_start = max(0, start - 8) + m.start()
        elif m := _EUR_BEFORE_RE.search(before):
            currency = "EUR"
            full_start = max(0, start - 8) + m.start()
        elif nm.value >= Decimal("10000") and nm.is_spoken:
            # Spoken large sums like "5 mln qarz berdim" imply UZS in Uzbekistan context
            currency = "UZS"
        elif nm.value >= Decimal("50000"):
            currency = "UZS"
        else:
            continue

        is_foreign = currency not in ("UZS",)
        conf = 0.95 if (currency == "UZS" and full_end > end) else (0.88 if currency == "UZS" else 0.72)
        matches.append(
            MoneyMatch(
                amount=nm.value.quantize(Decimal("0.01")),
                currency=currency,
                raw=text[full_start:full_end].strip(),
                span=(full_start, full_end),
                confidence=conf,
                needs_confirm=is_foreign or conf < 0.75,
            )
        )
    return matches
