"""Absolute and relative Uzbek (Latin + Cyrillic) & Russian date parser resolved against Asia/Tashkent today (§6.5)."""

from __future__ import annotations

import calendar
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

_APOS_RE = re.compile(r"[‘’`ʻʼ´]")

_MONTHS: dict[str, int] = {
    # Uzbek Latin
    "yanvar": 1, "fevral": 2, "mart": 3, "aprel": 4, "may": 5, "iyun": 6,
    "iyul": 7, "avgust": 8, "sentabr": 9, "sentyabr": 9, "oktabr": 10, "oktyabr": 10,
    "noyabr": 11, "dekabr": 12,
    # Uzbek Cyrillic
    "январ": 1, "феврал": 2, "март": 3, "апрел": 4, "май": 5, "июн": 6,
    "июл": 7, "август": 8, "сентябр": 9, "сентабр": 9, "октябр": 10, "октабр": 10,
    "ноябр": 11, "декабр": 12,
    # Russian (nominative & genitive)
    "января": 1, "январь": 1, "февраля": 2, "февраль": 2, "марта": 3, "апреля": 4, "апрель": 4,
    "мая": 5, "июня": 6, "июнь": 6, "июля": 7, "июль": 7, "августа": 8,
    "сентября": 9, "сентябрь": 9, "октября": 10, "октябрь": 10, "ноября": 11, "ноябрь": 11,
    "декабря": 12, "декабрь": 12,
}

_WEEKDAYS: dict[str, int] = {
    "dushanba": 0, "душанба": 0, "понедельник": 0,
    "seshanba": 1, "сешанба": 1, "вторник": 1,
    "chorshanba": 2, "чоршанба": 2, "среда": 2, "среду": 2,
    "payshanba": 3, "пайшанба": 3, "четверг": 3,
    "juma": 4, "жума": 4, "пятница": 4, "пятницу": 4,
    "shanba": 5, "шанба": 5, "суббота": 5, "субботу": 5,
    "yakshanba": 6, "якшанба": 6, "воскресенье": 6,
}

_ISO_RE = re.compile(r"\b(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})\b")
_DMY_RE = re.compile(r"\b(\d{1,2})[./-](\d{1,2})[./-](\d{2,4})\b")
_MONTH_PATTERN = "|".join(sorted(_MONTHS.keys(), key=len, reverse=True))
_NAMED_DATE_RE = re.compile(
    rf"\b(\d{{1,2}})\s*[-]?\s*(?:chi\s+)?({_MONTH_PATTERN})(?:\s+(\d{{2,4}}))?(?:\s*(?:yil|y\.|г\.|года|kun|kuni|sana))?\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class DateMatch:
    value: date
    raw: str
    span: tuple[int, int]
    confidence: float
    is_relative: bool = False


def get_today(timezone_name: str = "Asia/Tashkent") -> date:
    try:
        return datetime.now(ZoneInfo(timezone_name)).date()
    except Exception:
        return date.today()


def _resolve_year(y_raw: str | None, ref_today: date) -> int:
    if not y_raw:
        return ref_today.year
    y = int(y_raw)
    if y < 100:
        century = (ref_today.year // 100) * 100
        return century + y
    return y


def _add_months(d: date, months: int) -> date:
    m = d.month - 1 + months
    y = d.year + m // 12
    m = m % 12 + 1
    day = min(d.day, calendar.monthrange(y, m)[1])
    return date(y, m, day)


def extract_dates(text: str, *, today: date | None = None, timezone_name: str = "Asia/Tashkent") -> list[DateMatch]:
    """Extract all absolute and relative dates in uz_lat, uz_cyr, and ru with character spans."""
    ref_today = today or get_today(timezone_name)
    norm = _APOS_RE.sub("'", text)
    results: list[DateMatch] = []
    used_spans: list[tuple[int, int]] = []

    def _overlaps(s: int, e: int) -> bool:
        return any(not (e <= us or s >= ue) for us, ue in used_spans)

    # 1. ISO YYYY-MM-DD
    for m in _ISO_RE.finditer(norm):
        s, e = m.span()
        if _overlaps(s, e):
            continue
        try:
            dt = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            results.append(DateMatch(value=dt, raw=text[s:e], span=(s, e), confidence=0.98))
            used_spans.append((s, e))
        except ValueError:
            continue

    # 2. DD.MM.YYYY / DD/MM/YY
    for m in _DMY_RE.finditer(norm):
        s, e = m.span()
        if _overlaps(s, e):
            continue
        try:
            year = _resolve_year(m.group(3), ref_today)
            dt = date(year, int(m.group(2)), int(m.group(1)))
            results.append(DateMatch(value=dt, raw=text[s:e], span=(s, e), confidence=0.96))
            used_spans.append((s, e))
        except ValueError:
            continue

    # 3. Named month dates ("25-dekabr", "25 dekabr 2026", "25 декабря")
    for m in _NAMED_DATE_RE.finditer(norm):
        s, e = m.span()
        if _overlaps(s, e):
            continue
        day = int(m.group(1))
        month = _MONTHS.get(m.group(2).lower())
        if not month:
            continue
        year = _resolve_year(m.group(3), ref_today)
        try:
            dt = date(year, month, day)
            results.append(DateMatch(value=dt, raw=text[s:e], span=(s, e), confidence=0.94 if m.group(3) else 0.88))
            used_spans.append((s, e))
        except ValueError:
            continue

    # 4. Relative phrases (Uzbek Latin/Cyrillic + Russian)
    low = norm.lower()

    # "3 kundan keyin", "через 3 дня", "5 kun oldin", "2 дня назад"
    for m in re.finditer(r"\b(\d+)\s*(?:kundan\s+keyin|кундан\s+кейин)\b|\bчерез\s+(\d+)\s*(?:день|дня|дней)\b", low):
        s, e = m.span()
        if _overlaps(s, e):
            continue
        days = int(m.group(1) or m.group(2))
        results.append(DateMatch(value=ref_today + timedelta(days=days), raw=text[s:e], span=(s, e), confidence=0.90, is_relative=True))
        used_spans.append((s, e))

    for m in re.finditer(r"\b(\d+)\s*(?:kun\s+oldin|кун\s+олдин)\b|\b(\d+)\s*(?:день|дня|дней)\s+назад\b", low):
        s, e = m.span()
        if _overlaps(s, e):
            continue
        days = int(m.group(1) or m.group(2))
        results.append(DateMatch(value=ref_today - timedelta(days=days), raw=text[s:e], span=(s, e), confidence=0.90, is_relative=True))
        used_spans.append((s, e))

    # Weekday relative: "o'tgan juma", "прошлую пятницу", "kelasi dushanba"
    wd_pat = "|".join(sorted(_WEEKDAYS.keys(), key=len, reverse=True))
    for m in re.finditer(rf"\b(o'tgan|ўтган|прошл\w*)\s+({wd_pat})\b", low):
        s, e = m.span()
        if _overlaps(s, e):
            continue
        target_wd = _WEEKDAYS[m.group(2)]
        delta = (ref_today.weekday() - target_wd) % 7
        delta = delta if delta > 0 else 7
        results.append(DateMatch(value=ref_today - timedelta(days=delta), raw=text[s:e], span=(s, e), confidence=0.86, is_relative=True))
        used_spans.append((s, e))

    for m in re.finditer(rf"\b(kelasi|кейинги|следующ\w*)\s+({wd_pat})\b", low):
        s, e = m.span()
        if _overlaps(s, e):
            continue
        target_wd = _WEEKDAYS[m.group(2)]
        delta = (target_wd - ref_today.weekday()) % 7
        delta = delta if delta > 0 else 7
        results.append(DateMatch(value=ref_today + timedelta(days=delta), raw=text[s:e], span=(s, e), confidence=0.86, is_relative=True))
        used_spans.append((s, e))

    # Fixed relative keywords
    fixed_rel: list[tuple[str, date]] = [
        (r"\b(?:indinga|индинга|послезавтра)\b", ref_today + timedelta(days=2)),
        (r"\b(?:ertaga|эртага|завтра)\b", ref_today + timedelta(days=1)),
        (r"\b(?:bugun|бугун|сегодня)\b", ref_today),
        (r"\b(?:kecha|кеча|вчера)\b", ref_today - timedelta(days=1)),
        (r"\b(?:o'tgan\s+hafta|ўтган\s+ҳафта|на\s+прошлой\s+неделе|прошлую\s+неделю)\b", ref_today - timedelta(days=7)),
        (r"\b(?:kelasi\s+hafta|келаси\s+ҳафта|на\s+следующей\s+неделе)\b", ref_today + timedelta(days=7)),
        (r"\b(?:kelasi\s+oy|келаси\s+ой|в\s+следующем\s+месяце|следующий\s+месяц)\b", _add_months(ref_today, 1)),
        (r"\b(?:o'tgan\s+oy|ўтган\s+ой|в\s+прошлом\s+месяце)\b", _add_months(ref_today, -1)),
    ]
    for pat, dt in fixed_rel:
        for m in re.finditer(pat, low):
            s, e = m.span()
            if _overlaps(s, e):
                continue
            results.append(DateMatch(value=dt, raw=text[s:e], span=(s, e), confidence=0.88, is_relative=True))
            used_spans.append((s, e))

    results.sort(key=lambda r: r.span[0])
    return results


def parse_date(text: str, *, today: date | None = None, timezone_name: str = "Asia/Tashkent") -> DateMatch | None:
    found = extract_dates(text, today=today, timezone_name=timezone_name)
    return found[0] if found else None
