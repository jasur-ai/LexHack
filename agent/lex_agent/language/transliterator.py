"""Uzbek Latin <-> Cyrillic transliteration and UZ/RU/EN legal language & script detection."""

from __future__ import annotations

import re

from lex_agent.models import Language

# Uzbek-specific Cyrillic letters absent in Russian
_UZ_CYRL_UNIQUE = set("ўқғҳЎҚҒҲ")

# Common Uzbek words in Cyrillic vs Russian legal vocabulary for disambiguation
_UZ_CYRL_LEGAL_MARKERS = {
    "модда", "қонун", "қарор", "фармон", "кодекси", "республикаси", "ўзбекистон",
    "вазирлар", "маҳкамаси", "президенти", "банд", "боб", "бўлим", "ҳуқуқ",
    "мажбурият", "шартнома", "жавобгарлик", "солиқ", "меҳнат", "фуқаролик",
    "жиноят", "маъмурий", "билан", "учун", "бўйича", "тўғрисида",
}

_RU_LEGAL_MARKERS = {
    "статья", "закон", "постановление", "указ", "кодекс", "республики", "узбекистан",
    "кабинет", "министров", "президента", "пункт", "глава", "раздел", "право",
    "обязанность", "договор", "ответственность", "налог", "трудовой", "гражданский",
    "уголовный", "административный", "согласно", "настоящего", "порядке", "предусмотрено",
}

_UZ_LATN_LEGAL_MARKERS = {
    "modda", "qonun", "qaror", "farmon", "kodeksi", "respublikasi", "o'zbekiston",
    "vazirlar", "mahkamasi", "prezidenti", "band", "bob", "bo'lim", "huquq",
    "majburiyat", "shartnoma", "javobgarlik", "soliq", "mehnat", "fuqarolik",
    "jinoyat", "ma'muriy", "bilan", "uchun", "bo'yicha", "to'g'risida", "belgilangan",
    "nima", "qanday", "qancha", "kerak",
}

_EN_LEGAL_MARKERS = {
    "article", "law", "decree", "resolution", "code", "republic", "uzbekistan",
    "cabinet", "ministers", "president", "clause", "chapter", "section", "right",
    "obligation", "contract", "liability", "tax", "labor", "civil", "criminal",
    "administrative", "under", "pursuant", "accordance", "what", "does", "provide",
}

_APOSTROPHE_VARIANTS = re.compile(r"[ʻʼ‘’`´ʹʽˈ]")

_CYR_TO_LAT_MAP: dict[str, str] = {
    "А": "A", "а": "a",
    "Б": "B", "б": "b",
    "В": "V", "в": "v",
    "Г": "G", "г": "g",
    "Д": "D", "д": "d",
    "Ё": "Yo", "ё": "yo",
    "Ж": "J", "ж": "j",
    "З": "Z", "з": "z",
    "И": "I", "и": "i",
    "Й": "Y", "й": "y",
    "К": "K", "к": "k",
    "Л": "L", "л": "l",
    "М": "M", "м": "m",
    "Н": "N", "н": "n",
    "О": "O", "о": "o",
    "П": "P", "п": "p",
    "Р": "R", "р": "r",
    "С": "S", "с": "s",
    "Т": "T", "т": "t",
    "У": "U", "у": "u",
    "Ф": "F", "ф": "f",
    "Х": "X", "х": "x",
    "Ч": "Ch", "ч": "ch",
    "Ш": "Sh", "ш": "sh",
    "Ъ": "'", "ъ": "'",
    "Ь": "", "ь": "",
    "Э": "E", "э": "e",
    "Ю": "Yu", "ю": "yu",
    "Я": "Ya", "я": "ya",
    "Ў": "O'", "ў": "o'",
    "Қ": "Q", "қ": "q",
    "Ғ": "G'", "ғ": "g'",
    "Ҳ": "H", "ҳ": "h",
    "Щ": "Sh", "щ": "sh",
    "Ы": "I", "ы": "i",
}

_CYR_VOWELS = set("АЕЁИОУЭЮЯЎаеёиоуэюяў")


def normalize_uzbek_apostrophes(text: str) -> str:
    """Normalize all Unicode modifier apostrophe variants (oʻ, o‘, gʼ, maʼmuriy) to ASCII `'`."""
    return _APOSTROPHE_VARIANTS.sub("'", text)


def cyrillic_to_latin(text: str) -> str:
    """Convert Uzbek Cyrillic text to standard Uzbek Latin script."""
    if not text:
        return ""
    result: list[str] = []
    n = len(text)
    for i, ch in enumerate(text):
        prev_ch = text[i - 1] if i > 0 else ""
        next_ch = text[i + 1] if i + 1 < n else ""
        is_all_caps = ch.isupper() and (next_ch.isupper() or (prev_ch.isupper() and not next_ch.islower()))

        if ch in ("Е", "е"):
            at_word_start = i == 0 or not prev_ch.isalpha()
            after_vowel_or_sign = prev_ch in _CYR_VOWELS or prev_ch in ("ъ", "Ъ", "ь", "Ь")
            if at_word_start or after_vowel_or_sign:
                if ch == "Е":
                    result.append("YE" if is_all_caps else "Ye")
                else:
                    result.append("ye")
            else:
                result.append("E" if ch == "Е" else "e")
            continue

        if ch in ("Ц", "ц"):
            after_vowel = prev_ch in _CYR_VOWELS
            if after_vowel:
                if ch == "Ц":
                    result.append("TS" if is_all_caps else "Ts")
                else:
                    result.append("ts")
            else:
                result.append("S" if ch == "Ц" else "s")
            continue

        mapped = _CYR_TO_LAT_MAP.get(ch, ch)
        if is_all_caps and len(mapped) == 2 and mapped[1].isalpha():
            mapped = mapped.upper()
        result.append(mapped)

    return "".join(result)


_LAT_DIGRAPHS: list[tuple[str, str]] = [
    ("O'", "Ў"), ("o'", "ў"),
    ("G'", "Ғ"), ("g'", "ғ"),
    ("SH", "Ш"), ("Sh", "Ш"), ("sh", "ш"),
    ("CH", "Ч"), ("Ch", "Ч"), ("ch", "ч"),
    ("YO", "Ё"), ("Yo", "Ё"), ("yo", "ё"),
    ("YU", "Ю"), ("Yu", "Ю"), ("yu", "ю"),
    ("YA", "Я"), ("Ya", "Я"), ("ya", "я"),
    ("YE", "Е"), ("Ye", "Е"), ("ye", "е"),
    ("TS", "Ц"), ("Ts", "Ц"), ("ts", "ц"),
]

_LAT_SINGLE: dict[str, str] = {
    "A": "А", "a": "а",
    "B": "Б", "b": "б",
    "D": "Д", "d": "д",
    "E": "Е", "e": "е",
    "F": "Ф", "f": "ф",
    "G": "Г", "g": "г",
    "H": "Ҳ", "h": "ҳ",
    "I": "И", "i": "и",
    "J": "Ж", "j": "ж",
    "K": "К", "k": "к",
    "L": "Л", "l": "л",
    "M": "М", "m": "м",
    "N": "Н", "n": "н",
    "O": "О", "o": "о",
    "P": "П", "p": "п",
    "Q": "Қ", "q": "қ",
    "R": "Р", "r": "р",
    "S": "С", "s": "с",
    "T": "Т", "t": "т",
    "U": "У", "u": "у",
    "V": "В", "v": "в",
    "X": "Х", "x": "х",
    "Y": "Й", "y": "й",
    "Z": "З", "z": "з",
    "'": "ъ",
}


def latin_to_cyrillic(text: str) -> str:
    """Convert Uzbek Latin text to Uzbek Cyrillic script."""
    if not text:
        return ""
    norm = normalize_uzbek_apostrophes(text)
    out: list[str] = []
    i = 0
    n = len(norm)
    while i < n:
        matched = False
        if i + 2 <= n:
            pair = norm[i : i + 2]
            for lat, cyr in _LAT_DIGRAPHS:
                if pair == lat:
                    out.append(cyr)
                    i += 2
                    matched = True
                    break
        if matched:
            continue

        ch = norm[i]
        prev_ch = norm[i - 1] if i > 0 else ""
        if ch in ("E", "e") and (i == 0 or not prev_ch.isalpha()):
            out.append("Э" if ch == "E" else "э")
        else:
            out.append(_LAT_SINGLE.get(ch, ch))
        i += 1
    return "".join(out)


def to_searchable_uzbek_latin(text: str, language: Language | None = None) -> str:
    """Produce a normalized Latin string for cross-script matching (UZ Cyrillic -> UZ Latin)."""
    norm = normalize_uzbek_apostrophes(text)
    lang = language or detect_language(norm)
    if lang == Language.UZ_CYRL:
        return cyrillic_to_latin(norm)
    return norm


def detect_language(text: str) -> Language:
    """Accurately detect Uzbek Latin, Uzbek Cyrillic, Russian, or English."""
    if not text or not text.strip():
        return Language.UZ_LATN

    normalized = normalize_uzbek_apostrophes(text)
    cyr_count = sum(1 for c in normalized if "\u0400" <= c <= "\u04ff")
    lat_count = sum(1 for c in normalized if ("A" <= c <= "Z") or ("a" <= c <= "z"))
    words = set(re.findall(r"[a-zA-Z\u0400-\u04ff']+", normalized.lower()))

    if cyr_count >= lat_count and cyr_count > 0:
        if any(ch in _UZ_CYRL_UNIQUE for ch in normalized):
            return Language.UZ_CYRL
        uz_hits = len(words & _UZ_CYRL_LEGAL_MARKERS)
        ru_hits = len(words & _RU_LEGAL_MARKERS)
        if uz_hits > ru_hits:
            return Language.UZ_CYRL
        return Language.RU

    # Latin script: distinguish Uzbek Latin vs English
    has_uz_apostrophe_digraph = bool(re.search(r"(?:o'|g'|sh|ch)", normalized.lower()))
    uz_hits = len(words & _UZ_LATN_LEGAL_MARKERS)
    en_hits = len(words & _EN_LEGAL_MARKERS)

    if uz_hits > en_hits:
        return Language.UZ_LATN
    if en_hits > uz_hits:
        return Language.EN
    if re.search(r"\b(?:o'|g')", normalized.lower()) or re.search(r"qonun|modda|qaror|farmon", normalized.lower()):
        return Language.UZ_LATN
    if has_uz_apostrophe_digraph and any(w.endswith(("lar", "ning", "dagi", "ga", "dan")) for w in words):
        return Language.UZ_LATN
    return Language.EN
