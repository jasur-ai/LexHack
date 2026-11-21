"""Passport, PINFL, phone, Telegram handle, and Uzbekistan license plate extractors (§6.1, §6.5)."""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.config import get_settings

_CYR_TO_LAT = str.maketrans(
    {
        "А": "A", "В": "B", "Е": "E", "К": "K", "М": "M",
        "Н": "H", "О": "O", "Р": "P", "С": "C", "Т": "T", "Х": "X",
        "а": "a", "в": "b", "е": "e", "к": "k", "м": "m",
        "н": "h", "о": "o", "р": "p", "с": "c", "т": "t", "х": "x",
    }
)

_PASSPORT_RE = re.compile(r"\b([A-Z]{2})\s?(\d{7})\b")
_PINFL_RE = re.compile(r"\b(\d{14})\b")
_PHONE_RE = re.compile(r"(?:\+?998[\s\-()]*)?\b(\d{2})[\s\-()]*(\d{3})[\s\-]*(\d{2})[\s\-]*(\d{2})\b")
_TG_RE = re.compile(r"(?<![\w.])(@[A-Za-z0-9_]{5,32})\b")


@dataclass(frozen=True)
class IdMatch:
    kind: str  # "passport" | "pinfl" | "phone" | "telegram" | "plate"
    value: str
    display: str
    span: tuple[int, int]
    confidence: float
    sensitive: bool = False


def normalize_cyrillic_lookalikes(text: str) -> str:
    """Map Cyrillic uppercase/lowercase homoglyphs (А В Е К М Н О Р С Т Х) to Latin."""
    return text.translate(_CYR_TO_LAT)


def extract_passports(text: str) -> list[IdMatch]:
    norm = normalize_cyrillic_lookalikes(text).upper()
    out: list[IdMatch] = []
    for m in _PASSPORT_RE.finditer(norm):
        val = f"{m.group(1)}{m.group(2)}"
        out.append(IdMatch(kind="passport", value=val, display=f"{val[:2]}***{val[-4:]}", span=m.span(), confidence=0.95, sensitive=True))
    return out


def extract_pinfls(text: str) -> list[IdMatch]:
    out: list[IdMatch] = []
    for m in _PINFL_RE.finditer(text):
        val = m.group(1)
        out.append(
            IdMatch(
                kind="pinfl",
                value=val,
                display=f"{val[:3]}********{val[-3:]}",
                span=m.span(),
                confidence=0.94,
                sensitive=True,
            )
        )
    return out


def extract_phones(text: str) -> list[IdMatch]:
    out: list[IdMatch] = []
    for m in _PHONE_RE.finditer(text):
        raw = m.group(0)
        # Skip if part of a 14-digit PINFL or 9-digit STIR without +998/separators
        s, e = m.span()
        if (s > 0 and text[s - 1].isdigit()) or (e < len(text) and text[e].isdigit()):
            continue
        digits = f"{m.group(1)}{m.group(2)}{m.group(3)}{m.group(4)}"
        if "+998" not in raw and "998" not in raw and not re.search(r"[\s\-()]", raw):
            # 9 bare digits without prefix/separators could be a STIR/TIN
            continue
        norm_phone = f"+998{digits}"
        out.append(IdMatch(kind="phone", value=norm_phone, display=norm_phone, span=m.span(), confidence=0.92, sensitive=True))
    return out


def extract_telegram_handles(text: str) -> list[IdMatch]:
    out: list[IdMatch] = []
    for m in _TG_RE.finditer(text):
        val = m.group(1)
        out.append(IdMatch(kind="telegram", value=val, display=val, span=m.span(), confidence=0.95))
    return out


def extract_plates(text: str) -> list[IdMatch]:
    cfg = get_settings()
    norm = normalize_cyrillic_lookalikes(text).upper()
    out: list[IdMatch] = []
    seen: set[tuple[int, int]] = set()
    for pat in cfg.uz_plate_patterns:
        for m in re.finditer(pat, norm):
            if m.span() in seen:
                continue
            seen.add(m.span())
            cleaned = re.sub(r"\s+", " ", m.group(0)).strip()
            out.append(IdMatch(kind="plate", value=cleaned, display=cleaned, span=m.span(), confidence=0.94))
    return out


def extract_ids(text: str) -> dict[str, list[IdMatch]]:
    return {
        "passports": extract_passports(text),
        "pinfls": extract_pinfls(text),
        "phones": extract_phones(text),
        "telegrams": extract_telegram_handles(text),
        "plates": extract_plates(text),
    }
