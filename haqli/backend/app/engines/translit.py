"""Rule-based Uzbek Latin -> Cyrillic transliterator shared with PDFs and localized outputs."""

from __future__ import annotations

import re

_APOSTROPHES = re.compile(r"[ʻʼ‘’`´ʹʽˈ]")

# Loanwords where `ts` maps to Cyrillic `ц`
_TS_LOANWORDS = {
    "konstitutsiya", "kompensatsiya", "litsenziya", "notarial", "protsessual",
    "protsent", "sanksiya", "registratsiya", "operatsiya", "informatsiya",
    "kvalifikatsiya", "attestatsiya", "deklaratsiya", "korporatsiya",
    "investitsiya", "kredit", "akt", "ofitsial", "natsional",
}

_DIGRAPHS: list[tuple[str, str]] = [
    ("O'", "Ў"), ("o'", "ў"),
    ("G'", "Ғ"), ("g'", "ғ"),
    ("SH", "Ш"), ("Sh", "Ш"), ("sh", "ш"),
    ("CH", "Ч"), ("Ch", "Ч"), ("ch", "ч"),
    ("YO", "Ё"), ("Yo", "Ё"), ("yo", "ё"),
    ("YU", "Ю"), ("Yu", "Ю"), ("yu", "ю"),
    ("YA", "Я"), ("Ya", "Я"), ("ya", "я"),
    ("YE", "Е"), ("Ye", "Е"), ("ye", "е"),
]

_SINGLE: dict[str, str] = {
    "A": "А", "a": "а", "B": "Б", "b": "б", "D": "Д", "d": "д",
    "E": "Е", "e": "е", "F": "Ф", "f": "ф", "G": "Г", "g": "г",
    "H": "Ҳ", "h": "ҳ", "I": "И", "i": "и", "J": "Ж", "j": "ж",
    "K": "К", "k": "к", "L": "Л", "l": "л", "M": "М", "m": "м",
    "N": "Н", "n": "н", "O": "О", "o": "о", "P": "П", "p": "п",
    "Q": "Қ", "q": "қ", "R": "Р", "r": "р", "S": "С", "s": "с",
    "T": "Т", "t": "т", "U": "У", "u": "у", "V": "В", "v": "в",
    "X": "Х", "x": "х", "Y": "Й", "y": "й", "Z": "З", "z": "з",
    "'": "ъ",
}


def normalize_uz_text(text: str) -> str:
    return _APOSTROPHES.sub("'", text)


def _translit_word(word: str) -> str:
    norm = normalize_uz_text(word)
    low = norm.lower()
    use_ts = any(low.startswith(lw[:6]) for lw in _TS_LOANWORDS)

    out: list[str] = []
    i = 0
    n = len(norm)
    while i < n:
        if use_ts and i + 2 <= n and norm[i : i + 2].lower() == "ts":
            out.append("Ц" if norm[i].isupper() else "ц")
            i += 2
            continue
        matched = False
        if i + 2 <= n:
            pair = norm[i : i + 2]
            for lat, cyr in _DIGRAPHS:
                if pair == lat:
                    out.append(cyr)
                    i += 2
                    matched = True
                    break
        if matched:
            continue
        ch = norm[i]
        if ch in ("E", "e") and i == 0:
            out.append("Э" if ch == "E" else "э")
        else:
            out.append(_SINGLE.get(ch, ch))
        i += 1
    return "".join(out)


def latin_to_cyrillic(text: str) -> str:
    """Transliterate Uzbek Latin text to Uzbek Cyrillic preserving punctuation, numbers, and URLs."""
    if not text:
        return ""
    # Preserve URLs untouched
    parts = re.split(r"(https?://\S+)", text)
    rendered: list[str] = []
    for part in parts:
        if part.startswith(("http://", "https://")):
            rendered.append(part)
        else:
            rendered.append(re.sub(r"[A-Za-z'ʻʼ‘’]+", lambda m: _translit_word(m.group(0)), part))
    return "".join(rendered)


def localize_text(text_uz_lat: str, locale: str, text_ru: str | None = None) -> str:
    if locale == "ru" and text_ru is not None:
        return text_ru
    if locale == "uz_cyr":
        return latin_to_cyrillic(text_uz_lat)
    return text_uz_lat
