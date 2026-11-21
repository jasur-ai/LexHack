"""Deterministic Uzbek/Russian entity extractors (§6.5)."""

from app.engines.recognition.entities.dates import extract_dates, parse_date
from app.engines.recognition.entities.ids import (
    extract_ids,
    extract_passports,
    extract_phones,
    extract_pinfls,
    extract_plates,
    extract_telegram_handles,
    normalize_cyrillic_lookalikes,
)
from app.engines.recognition.entities.money import MoneyMatch, extract_money
from app.engines.recognition.entities.names import NameCandidate, extract_names
from app.engines.recognition.entities.numbers import NumberMatch, extract_numbers, parse_number_phrase

__all__ = [
    "MoneyMatch",
    "NameCandidate",
    "NumberMatch",
    "extract_dates",
    "extract_ids",
    "extract_money",
    "extract_names",
    "extract_numbers",
    "extract_passports",
    "extract_phones",
    "extract_pinfls",
    "extract_plates",
    "extract_telegram_handles",
    "normalize_cyrillic_lookalikes",
    "parse_date",
    "parse_number_phrase",
]
