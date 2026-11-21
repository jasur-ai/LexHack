"""Spoken and written Uzbek (Latin + Cyrillic) and Russian numeral parser -> Decimal (§6.5)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

_APOS_RE = re.compile(r"[‘’`ʻʼ´]")


def _norm_token(tok: str) -> str:
    s = _APOS_RE.sub("'", tok.lower().strip(".,;:!?()[]\"«»"))
    # Strip common Uzbek/Russian suffixes attached to number words (e.g. "beshta", "millionlik")
    for suf in ("ta", "tacha", "lik", "dan", "ga", "ni", "da", "та", "лик"):
        if len(s) > len(suf) + 2 and s.endswith(suf) and s[:-len(suf)] in _ALL_WORD_KEYS:
            return s[:-len(suf)]
    return s


# Units, teens, tens, hundreds (Uzbek Latin, Uzbek Cyrillic, Russian with case/gender stems)
_SMALL_WORDS: dict[str, int] = {
    # Uzbek Latin
    "nol": 0, "bir": 1, "ikki": 2, "uch": 3, "to'rt": 4, "tort": 4, "besh": 5,
    "olti": 6, "yetti": 7, "sakkiz": 8, "to'qqiz": 9, "toqqiz": 9,
    "o'n": 10, "on": 10, "yigirma": 20, "o'ttiz": 30, "ottiz": 30, "qirq": 40,
    "ellik": 50, "oltmish": 60, "yetmish": 70, "sakson": 80, "to'qson": 90, "toqson": 90,
    # Uzbek Cyrillic
    "нол": 0, "бир": 1, "икки": 2, "уч": 3, "тўрт": 4, "беш": 5,
    "олти": 6, "етти": 7, "саккиз": 8, "тўққиз": 9,
    "ўн": 10, "йигирма": 20, "ўттиз": 30, "қирқ": 40,
    "эллик": 50, "олтмиш": 60, "етмиш": 70, "саксон": 80, "тўқсон": 90,
    # Russian units & gender/case forms
    "ноль": 0, "нуль": 0,
    "один": 1, "одна": 1, "одно": 1, "одного": 1, "одну": 1,
    "два": 2, "две": 2, "двух": 2,
    "три": 3, "трех": 3, "трёх": 3,
    "четыре": 4, "четырех": 4, "четырёх": 4,
    "пять": 5, "пяти": 5,
    "шесть": 6, "шести": 6,
    "семь": 7, "семи": 7,
    "восемь": 8, "восьми": 8,
    "девять": 9, "девяти": 9,
    "десять": 10, "десяти": 10,
    "одиннадцать": 11, "двенадцать": 12, "тринадцать": 13, "четырнадцать": 14,
    "пятнадцать": 15, "шестнадцать": 16, "семнадцать": 17, "восемнадцать": 18, "девятнадцать": 19,
    "двадцать": 20, "тридцать": 30, "сорок": 40, "пятьдесят": 50,
    "шестьдесят": 60, "семьдесят": 70, "восемьдесят": 80, "девяносто": 90,
    "сто": 100, "ста": 100, "двести": 200, "триста": 300, "четыреста": 400,
    "пятьсот": 500, "шестьсот": 600, "семьсот": 700, "восемьсот": 800, "девятьсот": 900,
}

_HUNDRED_WORDS: dict[str, int] = {
    "yuz": 100,
    "юз": 100,
}

_SCALE_WORDS: dict[str, Decimal] = {
    "ming": Decimal("1000"),
    "минг": Decimal("1000"),
    "tys": Decimal("1000"),
    "тыс": Decimal("1000"),
    "тысяча": Decimal("1000"),
    "тысячи": Decimal("1000"),
    "тысяч": Decimal("1000"),
    "тысячу": Decimal("1000"),
    "k": Decimal("1000"),
    "к": Decimal("1000"),
    "million": Decimal("1000000"),
    "mln": Decimal("1000000"),
    "миллион": Decimal("1000000"),
    "миллиона": Decimal("1000000"),
    "миллионов": Decimal("1000000"),
    "млн": Decimal("1000000"),
    "milliard": Decimal("1000000000"),
    "mlrd": Decimal("1000000000"),
    "миллиард": Decimal("1000000000"),
    "миллиарда": Decimal("1000000000"),
    "миллиардов": Decimal("1000000000"),
    "млрд": Decimal("1000000000"),
}

_HALF_WORDS = {"yarim", "ярим", "половиной", "половина"}
_ONE_AND_HALF_WORDS = {"полтора", "полторы", "полутора"}
_CONNECTORS = {"va", "ва", "и", "с", "s"}

_ALL_WORD_KEYS = (
    set(_SMALL_WORDS.keys())
    | set(_HUNDRED_WORDS.keys())
    | set(_SCALE_WORDS.keys())
    | _HALF_WORDS
    | _ONE_AND_HALF_WORDS
)

# Compact numeric token like "5mln", "5,5", "5.000.000", "5000k", "3.5млн"
_COMPACT_NUM_RE = re.compile(
    r"^(?P<num>\d+(?:[.,]\d{3})+|\d+(?:[.,]\d+)?)(?P<suf>mlrd|mln|ming|k|млрд|млн|тыс|к)?$",
    re.IGNORECASE,
)

# Token scanner keeping exact character spans
_TOKEN_RE = re.compile(r"\d+(?:[\s\u00a0\u202f.]\d{3})+(?:,\d+)?|\d+(?:[.,]\d+)?(?:mlrd|mln|ming|k|млрд|млн|тыс|к)?|[A-Za-zА-Яа-яЁёЎўҚқҒғҲҳ'‘’`ʻʼ´]+")


@dataclass(frozen=True)
class NumberMatch:
    value: Decimal
    raw: str
    span: tuple[int, int]
    is_spoken: bool = False


def _parse_numeric_str(raw: str) -> tuple[Decimal | None, Decimal | None]:
    """Parse numeric token (e.g. '5 000 000', '5.000.000', '5,5', '5000k', '5mln'). Returns (num, inline_scale)."""
    compact = re.sub(r"[\s\u00a0\u202f]+", "", raw)
    # Check grouped thousands with dots like 5.000.000 or 12.500.000
    if re.fullmatch(r"\d{1,3}(?:\.\d{3})+(?:,\d+)?", compact):
        cleaned = compact.replace(".", "").replace(",", ".")
        try:
            return Decimal(cleaned), None
        except InvalidOperation:
            return None, None
    # Check grouped thousands with commas like 5,000,000
    if re.fullmatch(r"\d{1,3}(?:,\d{3})+(?:\.\d+)?", compact):
        cleaned = compact.replace(",", "")
        try:
            return Decimal(cleaned), None
        except InvalidOperation:
            return None, None

    m = _COMPACT_NUM_RE.match(compact)
    if not m:
        return None, None
    num_s = m.group("num")
    # Handle single dot with 3 trailing digits like "5.000" only if clearly grouped? Keep decimal "5.500" cautious:
    # For 1.000 -> if dot followed by exact 3 digits and >= 1 leading digit, treat as thousand separator if value >= 1000?
    # Spec explicitly lists "5.000.000" (2+ groups) and "5,5 million". Single "5.5" or "5,5" is decimal.
    if "." in num_s and num_s.count(".") >= 2:
        num_s = num_s.replace(".", "")
    else:
        num_s = num_s.replace(",", ".")
    try:
        val = Decimal(num_s)
    except InvalidOperation:
        return None, None
    suf = (m.group("suf") or "").lower()
    scale = _SCALE_WORDS.get(suf) if suf else None
    return val, scale


def _evaluate_tokens(tokens: list[tuple[str, bool]]) -> Decimal | None:
    """Left-to-right accumulator with `current` and `total` supporting Uzbek, Russian, mixed, and `yarim`."""
    total = Decimal("0")
    current = Decimal("0")
    saw_value = False
    last_scale: Decimal | None = None

    for raw_tok, is_num_lit in tokens:
        tok = _norm_token(raw_tok)
        if tok in _CONNECTORS:
            continue

        if is_num_lit:
            val, inline_scale = _parse_numeric_str(raw_tok)
            if val is None:
                return None
            saw_value = True
            if inline_scale is not None:
                total += val * inline_scale
                current = Decimal("0")
                last_scale = inline_scale
            else:
                current += val
            continue

        if tok in _ONE_AND_HALF_WORDS:
            current += Decimal("1.5")
            saw_value = True
            continue

        if tok in _HALF_WORDS:
            saw_value = True
            if current > 0:
                current += Decimal("0.5")
            elif last_scale is not None:
                # e.g. "bir million yarim" -> 1,000,000 + 500,000
                total += last_scale * Decimal("0.5")
                last_scale = None
            else:
                # e.g. "yarim million" -> 0.5 * 1,000,000
                current = Decimal("0.5")
            continue

        if tok in _SMALL_WORDS:
            current += Decimal(_SMALL_WORDS[tok])
            saw_value = True
            continue

        if tok in _HUNDRED_WORDS:
            current = (current if current > 0 else Decimal("1")) * Decimal("100")
            saw_value = True
            continue

        if tok in _SCALE_WORDS:
            scale = _SCALE_WORDS[tok]
            mult = current if current > 0 else Decimal("1")
            total += mult * scale
            current = Decimal("0")
            last_scale = scale
            saw_value = True
            continue

        return None

    if not saw_value:
        return None
    res = total + current
    return res.to_integral_value() if res == res.to_integral_value() else res


def parse_number_phrase(phrase: str) -> Decimal | None:
    """Parse a standalone spoken or written Uzbek/Russian number phrase into Decimal."""
    matches = extract_numbers(phrase)
    if len(matches) == 1 and matches[0].raw.strip().lower() == phrase.strip().lower():
        return matches[0].value
    if not matches:
        return None
    # If the whole phrase consists only of number tokens & whitespace/punctuation
    toks = _tokenize_for_numbers(phrase)
    if toks and all(kind != "other" for _, _, _, kind in toks):
        seq = [(t, kind == "num") for t, _, _, kind in toks]
        val = _evaluate_tokens(seq)
        if val is not None:
            return val
    return matches[0].value


def _tokenize_for_numbers(text: str) -> list[tuple[str, int, int, str]]:
    out: list[tuple[str, int, int, str]] = []
    for m in _TOKEN_RE.finditer(text):
        raw = m.group(0)
        start, end = m.span()
        norm = _norm_token(raw)
        if raw[0].isdigit():
            # Avoid consuming date fragments like 25.12.2026 or phone numbers as grouped numbers
            val, _ = _parse_numeric_str(raw)
            if val is not None:
                out.append((raw, start, end, "num"))
            else:
                out.append((raw, start, end, "other"))
        elif norm in _ALL_WORD_KEYS:
            out.append((raw, start, end, "word"))
        elif norm in _CONNECTORS:
            out.append((raw, start, end, "conn"))
        else:
            out.append((raw, start, end, "other"))
    return out


def extract_numbers(text: str) -> list[NumberMatch]:
    """Extract all spoken and written numbers with exact character spans from Uzbek/Russian text."""
    tokens = _tokenize_for_numbers(text)
    results: list[NumberMatch] = []
    i = 0
    n = len(tokens)
    while i < n:
        raw, start, end, kind = tokens[i]
        if kind not in ("num", "word"):
            i += 1
            continue

        # Avoid matching numbers that are part of ISO/dotted dates like 25.12.2026 or 2026-05-01
        if kind == "num":
            after = text[end : end + 1]
            before = text[max(0, start - 1) : start]
            if (after == "." and re.match(r"^\.\d{2}\.\d{4}", text[end:])) or (
                before == "." and re.match(r"^\d{2}\.\d{2}\.$", text[max(0, start - 6) : start])
            ):
                i += 1
                continue
            if re.match(r"^-\d{2}-\d{2}", text[end:]) or re.match(r"^\d{4}-\d{2}-$", text[max(0, start - 8) : start]):
                i += 1
                continue

        seq: list[tuple[str, int, int, str]] = [(raw, start, end, kind)]
        j = i + 1
        while j < n:
            nraw, nstart, nend, nkind = tokens[j]
            gap = text[seq[-1][2] : nstart]
            if not re.fullmatch(r"[\s\-]*", gap):
                break
            if nkind in ("num", "word"):
                # Don't merge two standalone digit literals unless second has a scale word (handled via word)
                if seq[-1][3] == "num" and nkind == "num":
                    break
                seq.append((nraw, nstart, nend, nkind))
                j += 1
            elif nkind == "conn" and j + 1 < n and tokens[j + 1][3] in ("num", "word"):
                seq.append((nraw, nstart, nend, nkind))
                j += 1
            else:
                break

        # Trim trailing connectors
        while seq and seq[-1][3] == "conn":
            seq.pop()

        # Ignore lone connector or lone "yarim" without scale/context
        if len(seq) == 1 and seq[0][3] == "word" and _norm_token(seq[0][0]) in _HALF_WORDS:
            results.append(NumberMatch(value=Decimal("0.5"), raw=seq[0][0], span=(seq[0][1], seq[0][2]), is_spoken=True))
            i = j
            continue

        val = _evaluate_tokens([(t, k == "num") for t, _, _, k in seq])
        if val is not None:
            span = (seq[0][1], seq[-1][2])
            is_spoken = any(k == "word" for _, _, _, k in seq)
            results.append(NumberMatch(value=val, raw=text[span[0] : span[1]], span=span, is_spoken=is_spoken))
        i = j

    return results
