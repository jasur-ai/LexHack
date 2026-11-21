"""Numbers, money amounts, durations, dates and counts mentioned in a question (UZ / RU / EN).

"3 oydan beri 5 mln oylik bermayapti" -> amount 5 000 000, duration 3 months; "2 ta bolam bor" -> children 2;
"10 BHM jarima" -> bhm 10; "15.03.2026" -> date. Used by the calculators to fill their inputs and to decide what
to ask when something is missing.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date

from lex_agent.knowledge.lexicon import fold_ru, fold_uz

_NUM_WORDS = {
    # Uzbek (folded Latin)
    "bir": 1, "ikki": 2, "uch": 3, "tort": 4, "besh": 5, "olti": 6, "yetti": 7, "sakkiz": 8, "tokkiz": 9, "on": 10,
    "yigirma": 20, "ottiz": 30, "kirk": 40, "ellik": 50, "yuz": 100,
    # Russian
    "один": 1, "одна": 1, "одного": 1, "два": 2, "две": 2, "двух": 2, "три": 3, "трех": 3, "трёх": 3, "четыре": 4,
    "пять": 5, "шесть": 6, "семь": 7, "восемь": 8, "девять": 9, "десять": 10,
    # English
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
}

_SCALE = {
    "ming": 1_000, "тыс": 1_000, "тысяч": 1_000, "k": 1_000, "thousand": 1_000,
    "mln": 1_000_000, "million": 1_000_000, "millon": 1_000_000, "млн": 1_000_000, "миллион": 1_000_000,
    "mlrd": 1_000_000_000, "milliard": 1_000_000_000, "млрд": 1_000_000_000,
}

_NUMBER = r"(\d{1,3}(?:[ \u00a0.,]\d{3})+|\d+(?:[.,]\d+)?)"
_AMOUNT_RE = re.compile(
    _NUMBER + r"\s*(ming|mln|million|millon|mlrd|milliard|тыс\w*|млн|миллион\w*|млрд|thousand|k\b)?\s*"
    r"(som|so'm|сум|сўм|uzs|sum)?",
    re.I,
)
_DURATION_RE = re.compile(
    _NUMBER + r"\s*(?:-?\s*)(kun\w*|oy\w*|yil\w*|hafta\w*|кун\w*|ой\w*|йил\w*|день|дня|дней|месяц\w*|год|года|лет|"
    r"недел\w*|days?\b|months?\b|years?\b|weeks?\b)",
    re.I,
)
_DATE_RE = re.compile(r"\b(\d{1,2})[./-](\d{1,2})[./-](\d{4})\b|\b(\d{4})-(\d{2})-(\d{2})\b")
_CHILDREN_RE = re.compile(
    r"(\d+|bir|ikki|uch|tort|besh|один|одного|два|двух|три|трех|трёх|четыре|one|two|three|four)\s*(?:ta\s*)?"
    r"(?:bola|farzand|ребен|ребён|дет|child|kid)",
    re.I,
)
_BHM_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*(?:-?\s*)(?:barobar\w*|baravar\w*|karra\w*)?\s*(?:bhm|brv|брв|бҳм|bcа|bca)\b", re.I)
_PERCENT_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*(?:%|foiz|процент\w*|percent)", re.I)


def _to_float(raw: str) -> float:
    s = raw.replace("\u00a0", " ").strip()
    if re.fullmatch(r"\d{1,3}(?:[ .,]\d{3})+", s):
        return float(re.sub(r"[ .,]", "", s))
    return float(s.replace(",", "."))


@dataclass(slots=True)
class Entities:
    amounts: list[float] = field(default_factory=list)
    durations: list[tuple[float, str]] = field(default_factory=list)  # (value, unit: day|month|year|week)
    dates: list[date] = field(default_factory=list)
    children: int | None = None
    bhm_multiple: float | None = None
    percents: list[float] = field(default_factory=list)
    numbers: list[float] = field(default_factory=list)

    def duration_days(self) -> float | None:
        for value, unit in self.durations:
            return value * {"day": 1, "week": 7, "month": 30, "year": 365}[unit]
        return None

    def duration_years(self) -> float | None:
        for value, unit in self.durations:
            return value / {"day": 365, "week": 52, "month": 12, "year": 1}[unit]
        return None


def _unit(word: str) -> str:
    w = word.lower()
    if w.startswith(("kun", "кун", "ден", "дня", "дне", "day")):
        return "day"
    if w.startswith(("hafta", "ҳафта", "недел", "week")):
        return "week"
    if w.startswith(("oy", "ой", "месяц", "month")):
        return "month"
    return "year"


def extract(text: str, *, language: str = "uz_latn") -> Entities:
    """Pull calculator inputs out of a question."""
    view = fold_ru(text) if language == "ru" else fold_uz(text)
    raw = (text or "").lower()
    ent = Entities()

    for m in _DATE_RE.finditer(raw):
        try:
            if m.group(1):
                ent.dates.append(date(int(m.group(3)), int(m.group(2)), int(m.group(1))))
            else:
                ent.dates.append(date(int(m.group(4)), int(m.group(5)), int(m.group(6))))
        except ValueError:
            continue
    date_spans = [m.span() for m in _DATE_RE.finditer(raw)]

    def _inside_date(span: tuple[int, int]) -> bool:
        return any(a <= span[0] and span[1] <= b for a, b in date_spans)

    for m in _BHM_RE.finditer(raw):
        ent.bhm_multiple = _to_float(m.group(1))
        break
    for m in _PERCENT_RE.finditer(raw):
        ent.percents.append(_to_float(m.group(1)))
    for m in _DURATION_RE.finditer(raw):
        if _inside_date(m.span()):
            continue
        ent.durations.append((_to_float(m.group(1)), _unit(m.group(2))))
    m = _CHILDREN_RE.search(raw) or _CHILDREN_RE.search(view)
    if m:
        token = m.group(1).lower()
        ent.children = int(token) if token.isdigit() else _NUM_WORDS.get(token)

    used: list[tuple[int, int]] = list(date_spans)
    for m in list(_BHM_RE.finditer(raw)) + list(_PERCENT_RE.finditer(raw)) + list(_DURATION_RE.finditer(raw)):
        used.append(m.span())
    for m in _AMOUNT_RE.finditer(raw):
        span = m.span()
        if any(a <= span[0] < b for a, b in used):
            continue
        value = _to_float(m.group(1))
        scale = (m.group(2) or "").lower()
        mult = next((v for k, v in _SCALE.items() if scale.startswith(k)), 1)
        value *= mult
        is_money = bool(m.group(3)) or mult >= 1000 or value >= 10_000
        ent.numbers.append(value)
        if is_money:
            ent.amounts.append(value)
    if ent.children is None:
        for w in re.findall(r"[a-zа-яё']+", view):
            if w in ("bitta", "одного", "одним"):
                ent.children = 1
                break
    return ent
