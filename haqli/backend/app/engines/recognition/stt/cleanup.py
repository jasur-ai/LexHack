"""Uzbek/Russian voice transcript cleanup, party role assignment, and Himoya category inference (§7)."""

from __future__ import annotations

import re

_FILLER_RE = re.compile(
    r"\b(?:ee+|mmm+|hmm+|ya['ʻ’]?ni|tipa|haligi|ну|вот|как\s+бы|короче|типа|ээ+|мм+)\b[\s,]*",
    re.IGNORECASE,
)
_STUTTER_RE = re.compile(r"\b(\w{2,})\s+\1\b", re.IGNORECASE)
_SUM_NORM_RE = re.compile(r"\b(?:sum|som)\b", re.IGNORECASE)

_LENDER_CUES = re.compile(
    r"\b(?:qarz\s+berdim|berdim|berib\s+turdim|одолжил|дал\s+в\s+долг|передал\s+в\s+долг|займодавец)\b",
    re.IGNORECASE,
)
_BORROWER_CUES = re.compile(
    r"\b(?:qarz\s+oldim|oldim|dan\s+oldim|взял\s+в\s+долг|получил\s+в\s+долг|занял\s+у|заемщик|заёмщик)\b",
    re.IGNORECASE,
)

_CATEGORY_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("labor", ("oylik", "maosh", "ish haqi", "ishdan", "bo'shat", "зарплат", "оклад", "увольнен", "работодател")),
    ("consumer", ("qaytarib bermadi", "nuqson", "nosoz", "kafolat", "do'kon", "брак", "возврат", "гаранти", "магазин", "товар")),
    ("rental", ("ijara", "kvartira", "zalog", "depozit", "uy egasi", "аренд", "квартир", "залог", "депозит")),
    ("traffic", ("jarima", "kamera", "yhxx", "radar", "штраф", "камер", "гаи", "сбдд", "пдд")),
    ("debt", ("qarz", "tilxat", "qaytarmayapti", "долг", "расписк", "одолжил", "взял в долг")),
]


def clean_transcript(raw_text: str) -> tuple[str, str]:
    """Return `(display_text, matching_text)` with fillers and stutter repeats removed (§7)."""
    if not raw_text:
        return "", ""
    cleaned = _FILLER_RE.sub("", raw_text)
    cleaned = _STUTTER_RE.sub(r"\1", cleaned)
    cleaned = _SUM_NORM_RE.sub("so'm", cleaned)
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip(" ,")
    return cleaned, cleaned.lower()


def assign_party_role(text: str) -> tuple[str | None, float]:
    """Infer whether the speaker (Party A) is `lender` or `borrower` with confidence (§7)."""
    lender = bool(_LENDER_CUES.search(text))
    borrower = bool(_BORROWER_CUES.search(text))
    if lender and not borrower:
        return "lender", 0.92
    if borrower and not lender:
        return "borrower", 0.92
    if lender and borrower:
        return "lender", 0.60
    return None, 0.0


def infer_himoya_category(text: str) -> tuple[str | None, float]:
    """Infer Himoya dispute category from voice transcript keywords (§7)."""
    low = text.replace("ʻ", "'").replace("’", "'").lower()
    best_cat: str | None = None
    best_hits = 0
    for cat, kws in _CATEGORY_RULES:
        hits = sum(1 for k in kws if k in low)
        if hits > best_hits:
            best_hits = hits
            best_cat = cat
    if best_cat is None:
        return None, 0.0
    return best_cat, min(0.95, 0.72 + best_hits * 0.08)
