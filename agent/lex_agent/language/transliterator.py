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

_UZ_CYRL_COMMON = {
    "неча", "нечта", "қанча", "канча", "керак", "керакми", "мумкин", "мумкинми", "нима", "нимага", "нега", "қандай",
    "кандай", "қачон", "качон", "қаерга", "каерга", "бўлса", "булса", "бўлади", "булади", "бўладими", "буладими",
    "ва", "ёки", "ҳам", "хам", "агар", "лекин", "эмас", "йўқ", "йук", "бор", "борми", "мен", "менга", "мени",
    "менинг", "сиз", "биз", "улар", "бу", "шу", "иш", "ишдан", "ишга", "ойлик", "маош", "йил", "ой", "кун", "ёш",
    "ёши", "жавоб", "беради", "берадими", "олади", "қилиш", "килиш", "қилса", "килса", "керакми", "бўлиш", "булиш",
    "ҳақида", "хакида", "учун", "билан", "бўйича", "буйича", "тўғрисида", "тугрисида", "муддати", "миқдори",
    "сен", "сени", "сенга", "сенинг", "ким", "кимсан", "кимсиз", "салом", "ассалому", "алайкум", "рахмат", "раҳмат",
    "яхши", "ёрдам", "қилсам", "килсам", "қиламан", "киламан", "нима", "нимани", "қилай", "килай", "эри", "хотини",
    "бола", "болам", "уй", "пул", "қарз", "карз", "суд", "судга", "ариза", "дейди", "деяпти", "айтди",
}
_RU_COMMON = {
    "что", "как", "какой", "какая", "какие", "если", "не", "ли", "можно", "нужно", "надо", "сколько", "когда",
    "где", "куда", "почему", "это", "мне", "меня", "мой", "моя", "мои", "я", "мы", "вы", "он", "она", "они",
    "в", "на", "по", "за", "из", "от", "до", "для", "при", "без", "через", "или", "и", "но", "уже", "ещё", "еще",
    "делать", "положено", "имеет", "право", "есть", "был", "была", "были", "будет",
}
_UZ_CYRL_SUFFIX_RE = re.compile(
    r"(?:нинг|ларни|лари|ларга|лардан|дан|ни|га|ка|қа|да|ми|миз|сиз|ман|сан|япти|япман|ади|ди|ган|иш|лик|чи|си)$"
)
_RU_SUFFIX_RE = re.compile(r"(?:ться|тся|ешь|ете|ют|ует|ый|ий|ая|яя|ое|ее|ого|его|ому|ему|ых|их|ами|ями|ов|ев|ией|ия|ие|ость|ение|ание)$")

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

# Everyday words people actually type in Uzbek (Latin) questions. Citizens rarely use legal vocabulary, and they
# often type a plain apostrophe or none at all ("tatil", "boshatishdi"), so legal markers alone misclassify
# questions such as "Yillik ta'til necha kun?" as English.
_UZ_LATN_COMMON = {
    "va", "ham", "yoki", "lekin", "agar", "bo'lsa", "emas", "yo'q", "ha", "kabi", "haqida", "uchun", "bilan",
    "men", "menga", "meni", "mening", "biz", "bizga", "siz", "sizga", "u", "unga", "ular", "o'zim", "o'z",
    "nima", "nimaga", "nega", "qanday", "qanaqa", "qancha", "necha", "nechta", "nechanchi", "qachon", "qayerga",
    "qayerda", "qaysi", "kim", "kimga", "kerak", "kerakmi", "mumkin", "mumkinmi", "shart", "shartmi", "bormi",
    "bo'ladi", "bo'ladimi", "beriladi", "beriladimi", "beradi", "olish", "olsam", "qilish", "qilishim", "qilaman",
    "qilsam", "qilishadi", "to'lash", "to'laydi", "to'lanadi", "ish", "ishdan", "ishga", "ishxona", "haqi",
    "maosh", "oylik", "kun", "kunlik", "kunga", "soat", "oy", "yil", "yillik", "muddat", "muddati", "ta'til",
    "ta'tili", "tatil", "jarima", "jarimasi", "sud", "sudga", "ariza", "shikoyat", "qarz", "qarzni", "pul",
    "pulni", "uy", "uyni", "ijara", "ijaraga", "ijarachi", "aliment", "ajrashish", "nikoh", "bola", "bolalar",
    "ota-ona", "meros", "vasiyat", "notarius", "ishonchnoma", "pensiya", "nafaqa", "kafolat", "tovar",
    "sotuvchi", "xaridor", "qaytarish", "qaytarib", "bo'shatish", "bo'shatishdi", "boshatishdi", "haydadi",
    "haydash", "ishlayman", "ishlash", "davlat", "boj", "xizmat", "haydovchi", "mashina", "yhxx", "bhm",
}

_EN_COMMON = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "am", "do", "does", "did", "can", "could",
    "should", "would", "will", "shall", "may", "must", "have", "has", "had", "i", "my", "me", "we", "our", "you",
    "your", "he", "she", "it", "they", "their", "this", "that", "these", "those", "what", "how", "why", "when",
    "where", "which", "who", "whom", "of", "to", "in", "on", "for", "with", "from", "by", "about", "and", "or",
    "not", "if", "many", "much", "there", "get", "leave", "annual", "salary", "employer", "employee", "days",
    "fine", "rent", "landlord", "tenant", "divorce", "alimony", "court", "appeal", "deadline", "penalty",
}

_UZ_SUFFIX_RE = re.compile(
    r"(?:ning|dagi|lari|larni|larga|lardan|moqda|yapti|ganda|gani|sangiz|ishim|ishdi|ilsa|ladimi|adimi|"
    r"mizni|ingiz|imiz|sizmi|asizmi|dimi|kerakmi|mumkinmi)$"
)
_EN_CONTRACTION_RE = re.compile(r"[a-z]'(?:t|s|m|re|ve|ll|d)\b")

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
        # Uzbek Cyrillic written without ў/қ/ғ/ҳ ("Ойлик маошни кечиктирса...", "Пенсия ёши неча ёш?") is common:
        # score Uzbek function words and agglutinative endings against Russian function words and inflections.
        uz_hits = len(words & _UZ_CYRL_LEGAL_MARKERS) + 2 * len(words & _UZ_CYRL_COMMON)
        uz_hits += sum(1 for w in words if len(w) > 3 and _UZ_CYRL_SUFFIX_RE.search(w))
        ru_hits = len(words & _RU_LEGAL_MARKERS) + 2 * len(words & _RU_COMMON)
        ru_hits += sum(1 for w in words if len(w) > 3 and _RU_SUFFIX_RE.search(w))
        if "ъ" in normalized and re.search(r"[аоуеи]ъ[а-я]", normalized.lower()):
            uz_hits += 2  # даъво, маъмурий, таътил: the Uzbek tutuq belgisi
        if uz_hits > ru_hits:
            return Language.UZ_CYRL
        return Language.RU

    # Latin script: Uzbek Latin vs English. This is an Uzbek-law assistant, so ties resolve to Uzbek.
    lower = normalized.lower()
    uz_score = len(words & _UZ_LATN_LEGAL_MARKERS) + len(words & _UZ_LATN_COMMON)
    uz_score += sum(1 for w in words if len(w) > 4 and _UZ_SUFFIX_RE.search(w))
    if re.search(r"(?:o'|g')[a-z]", lower):
        uz_score += 2
    # A letter-apostrophe-letter inside a word ("ta'til", "san'at") is the Uzbek tutuq belgisi, unless it is an
    # English contraction ("don't", "it's").
    if re.search(r"[a-z]'[a-z]", lower) and not _EN_CONTRACTION_RE.search(lower):
        uz_score += 1
    uz_score += min(2, len(re.findall(r"q(?!u)|x(?![aeiouy]?\b)", lower)))
    en_score = len(words & _EN_COMMON) + len(words & _EN_LEGAL_MARKERS)
    if _EN_CONTRACTION_RE.search(lower):
        en_score += 1
    return Language.EN if en_score > uz_score else Language.UZ_LATN
