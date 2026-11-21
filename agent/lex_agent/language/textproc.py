"""Search-oriented text processing: script folding, tokenization and light stemming for UZ / RU / EN.

The index and every query go through the same functions, so the exact surface form a person types does not
matter:

* Uzbek Cyrillic is transliterated to Latin, all apostrophe variants are removed (``taʼtil`` == ``ta'til`` ==
  ``tatil``, ``boʻshatish`` == ``boshatish``) and inflectional suffixes are stripped (``ishdan``, ``ishga``,
  ``ishimni`` -> ``ish``; ``boʻshatishdi`` -> ``boshat``).
* Russian uses the Snowball stemmer (``уволили``, ``увольнение`` -> ``увол``); ``ё`` is folded to ``е``.
* English uses the Snowball (Porter2) stemmer; it only matters for the English lexicon, the corpus is UZ/RU.

The Uzbek stemmer is deliberately light: it removes case, plural, possessive and common verbal endings and
never shortens a stem below three letters (two for a small list of short roots such as ``uy`` and ``oy``).
Over-stemming is harmless here because queries and documents are stemmed identically; what matters is that
word families collapse to the same key.
"""

from __future__ import annotations

import re
import threading
import unicodedata
from functools import lru_cache

from lex_agent.language.transliterator import cyrillic_to_latin

try:  # pragma: no cover - import guard exercised implicitly
    import snowballstemmer
except Exception:  # pragma: no cover - the dependency is declared, this is only a safety net
    snowballstemmer = None

# Snowball stemmer objects keep the word being stemmed in instance state, so one shared instance used from the
# search worker threads corrupts stems (or raises IndexError). Every thread gets its own instances.
_STEMMERS = threading.local()


def _stemmer(language: str):
    stemmer = getattr(_STEMMERS, language, None)
    if stemmer is None and snowballstemmer is not None:
        stemmer = snowballstemmer.stemmer(language)
        setattr(_STEMMERS, language, stemmer)
    return stemmer

_APOS_RE = re.compile(r"[ʻʼ‘’`´ʹʽˈ'ʿ]")
_CYR_RE = re.compile(r"[\u0400-\u04ff]")
_UZ_CYR_ONLY = set("ўқғҳЎҚҒҲ")
_TOKEN_RE = re.compile(r"[0-9a-z\u0400-\u04ff]+")
_SPLIT_RE = re.compile(r"[^0-9a-zA-Z\u0400-\u04ffʻʼ‘’`´ʹʽˈ'ʿ]+")

# Short Uzbek roots that may legitimately stay at two letters after stripping (uy-im, oy-lik, ol-ish, et-ish)
_SHORT_ROOTS = {"uy", "oy", "er", "ol", "et", "ot", "ko", "yo"}
_VOWELS = set("aeiou")

# Inflectional endings (apostrophe-free Latin) grouped by their slot, counted from the end of the word:
# particle (0) < case (1) < possessive (2) < plural (3) < tense/person/negation (4) < verbal noun /
# participle / derivation (5). Stripping walks from the end and only moves to a strictly higher slot, which
# mirrors Uzbek morphology (uy-lar-imiz-dan, boʻshat-ish-di) and prevents over-stemming chains.
_SUFFIX_SLOTS: dict[str, int] = {
    **{s: 0 for s in ("mi", "ku", "dir", "u", "yu")},
    **{s: 1 for s in ("ning", "ni", "ga", "ka", "qa", "da", "dan", "gacha", "kacha", "qacha", "dagi", "dek", "day",
                      "cha")},
    **{s: 2 for s in ("imiz", "ingiz", "im", "ing", "i", "si", "miz", "ngiz", "m")},
    "lar": 3,
    **{s: 4 for s in ("di", "dim", "ding", "dik", "dingiz", "dilar", "ydi", "adi", "aydi", "yapti", "yapman",
                      "yapmiz", "yapsiz", "moqda", "moqchi", "moqchiman", "moqchimiz", "sa", "sam", "sang",
                      "sak", "sangiz", "salar", "maydi", "madi", "masdan", "mas", "aman", "ayman", "amiz", "aymiz",
                      "asiz", "aysiz", "ibdi", "ibdilar", "ishdi", "ishmoqda", "yotir", "gin", "ing", "inglar",
                      "maylik", "aylik", "ylik", "ay", "ayin", "aylik", "sin", "sinlar", "man", "san", "miz")},
    **{s: 5 for s in ("ish", "sh", "gan", "kan", "qan", "adigan", "ydigan", "digan", "moq", "ib", "ilgan",
                      "ilish", "ildi", "ilsa", "ilmagan", "ilmaydi", "inadi", "iladi", "ilishi", "magan",
                      "maslik", "yotgan", "ayotgan", "ishgan", "ishib", "v", "uv", "lik", "liq", "li", "siz",
                      "ma", "mas")},
}
_UZ_SUFFIXES: tuple[str, ...] = tuple(sorted(_SUFFIX_SLOTS, key=len, reverse=True))
# Verbal endings: once one of them is stripped the word is a verb form, so voice suffixes and the stem-final
# vowel are normalised too (haydash / haydadi / haydashdi -> hayd; toʻlov / toʻlash / toʻlanadi -> tol).
_VERBAL = {s for s, slot in _SUFFIX_SLOTS.items() if slot == 4} | {
    "ish", "sh", "gan", "kan", "qan", "adigan", "ydigan", "digan", "moq", "ib", "ilgan", "ilish", "ildi", "ilsa",
    "ilmagan", "ilmaydi", "inadi", "iladi", "ilishi", "magan", "maslik", "yotgan", "ayotgan", "ishgan", "ishib",
    "v", "uv", "ma",
}
# Endings that only make sense after a tense/person ending was removed (ber-ma-di, ber-ma-sa)
_ONLY_AFTER_VERBAL = {"ma", "mas"}
# Possessive/verbal endings whose shape depends on the stem-final sound (kodeks-i vs shartnoma-si)
_AFTER_VOWEL = {"si", "miz", "ngiz", "sh", "ydi", "ydigan", "aydi", "ayman", "aymiz", "aysiz", "v", "m", "ylik",
                "yapti", "yapman", "yapmiz", "yapsiz", "yotir", "yu"}
_AFTER_CONSONANT = {"i", "imiz", "ingiz", "im", "ing", "ish", "adi", "adigan", "aman", "amiz", "asiz", "ib", "uv",
                    "ishgan", "ishib", "li", "u", "ay", "ayin", "aylik", "inglar", "gin", "sin", "sinlar"}
# Voice suffixes (passive -il/-in/-l/-n, reciprocal -sh, causative -tir/-dir) stripped from verb stems only
_VOICE: tuple[tuple[str, str], ...] = (("tir", "c"), ("dir", "c"), ("il", "c"), ("in", "c"), ("sh", "v"),
                                        ("l", "v"), ("n", "v"))

# Words that look inflected but are roots (protected from stripping)
_UZ_PROTECTED = {
    "tatil", "nikoh", "qonun", "huquq", "aliment", "kodeks", "modda", "ariza", "sud", "ish", "pul", "boj",
    "jarima", "meros", "vasiyat", "shartnoma", "ijara", "qarz", "ota", "ona", "bola", "nafaqa", "pensiya",
    "soliq", "mulk", "yer", "uy", "oy", "kun", "yil", "soat", "davlat", "fuqaro", "xodim", "ishchi",
    "sotuvchi", "xaridor", "haydovchi", "notarius", "advokat", "prokuror", "militsiya", "politsiya", "bank",
    "kredit", "dalolatnoma", "ishonchnoma", "vasiyatnoma", "nizom", "tartib", "konstitutsiya", "respublika",
    "mehnat", "ozbekiston", "toshkent", "bhm", "mhtekm", "yhxx", "tibbiy", "sugurta", "tovar", "xizmat",
    "boshliq", "rahbar", "hokim", "hokimiyat", "mahalla", "kadastr", "notarial", "dalil", "guvoh", "ombudsman",
    "maosh", "bosh", "yosh", "tosh", "qosh", "qarindosh", "vatandosh", "garov", "olov", "kuyov", "birov",
    "majlis", "tashabbus", "status", "bonus", "korpus", "minus", "virus", "ishtirokchi", "saylov", "imtiyoz",
    "kafil", "kafolat", "litsenziya", "patent", "jinoyat", "sudya", "tergov", "bojxona", "aksiya", "dividend",
    "nasl", "farzand", "homila", "qamoq", "ozodlik", "muddat", "summa", "foiz", "penya", "neustoyka", "hisob",
    "javob", "talab", "kitob", "sabab", "maktab", "hukm", "ajrim", "qaror", "farmon", "buyruq", "nizo", "ziyon",
    "zarar", "tovon", "kompensatsiya", "vasiy", "homiy", "yetim", "nogiron", "nogironlik", "pasport", "viza",
    "propiska", "registratsiya", "avtomobil", "mashina", "transport", "yol", "piyoda", "chorraha", "svetofor",
    "uyali", "internet", "telefon", "sms", "kartochka", "plastik", "naqd", "valyuta", "dollar", "som",
    "ikki", "uch", "tort", "besh", "olti", "yetti", "sakkiz", "toqqiz", "on", "yuz", "ming", "million",
    "boshqa", "boshqarma", "boshqaruv", "hamma", "barcha", "kassa", "qoida", "soha", "masala", "hudud",
}
# Agent nouns (ish beruvchi, ijarachi, sotuvchi) are kept whole: they name parties, not actions
_AGENT_RE = re.compile(r"(?<!moq)(?<!mok)(?:uvchi|ovchi|vchi|chi)$")
_DOUBLE_RE = re.compile(r"([a-z])\1+")


# Bump whenever folding, stemming or tokenisation changes: indexes built with another analyzer are rebuilt.
ANALYZER_VERSION = "2026.11.21-5"

def fold_apostrophes(text: str) -> str:
    """Remove every apostrophe / okina variant (``oʻ`` -> ``o``, ``ta'til`` -> ``tatil``)."""
    return _APOS_RE.sub("", text)


def has_cyrillic(text: str) -> bool:
    return bool(_CYR_RE.search(text))


def is_uzbek_cyrillic(text: str) -> bool:
    return any(ch in _UZ_CYR_ONLY for ch in text)


def _nfkc_lower(text: str) -> str:
    return unicodedata.normalize("NFKC", text).lower()


def _ru_fold(text: str) -> str:
    return _nfkc_lower(text).replace("ё", "е")


# Verb stems whose intransitive and causative forms must share a key (boʻsha-moq "to quit" / boʻshat-moq "to
# dismiss"), checked before the final-vowel drop that would otherwise merge "boʻsha" with "bosh" (head).
_UZ_VERB_ALIASES = {"bosha": "boshat", "boshash": "boshat", "boshal": "boshat", "ajrasha": "ajr", "ajrash": "ajr"}


@lru_cache(maxsize=200_000)
def stem_uz(token: str) -> str:
    """Light Uzbek (Latin, apostrophe-free) stemmer: slot-ordered suffix stripping with sound harmony checks."""
    if not token.isalpha():
        return token
    return _DOUBLE_RE.sub(r"\1", _strip_uz(token))


def _rest_ok(rest: str) -> bool:
    if rest in _SHORT_ROOTS:
        return True
    if len(rest) < 3:
        return False
    # Native roots do not end in two vowels: "qoida" is not qoi-da, "foiz" stays whole
    return not (len(rest) <= 4 and rest[-1] in _VOWELS and rest[-2] in _VOWELS)


def _strip_uz(token: str) -> str:
    word = token
    if len(word) <= 2 or word in _UZ_PROTECTED:
        return word
    slot = -1
    verbal = False
    while True:
        if _AGENT_RE.search(word) and len(word) >= 6:
            return word
        candidates: list[tuple[str, str, int]] = []
        for suf in _UZ_SUFFIXES:
            suf_slot = _SUFFIX_SLOTS[suf]
            if suf_slot <= slot or not word.endswith(suf):
                continue
            if suf in _ONLY_AFTER_VERBAL and not verbal:
                continue
            rest = word[: -len(suf)]
            if not _rest_ok(rest):
                continue
            last = rest[-1]
            if suf in _AFTER_VOWEL and last not in _VOWELS:
                continue
            if suf in _AFTER_CONSONANT and last in _VOWELS:
                continue
            if suf_slot == 2 and suf.startswith("i") and rest.endswith("lig"):
                rest = rest[:-1] + "k"  # oylig-i -> oylik, javobgarlig-i -> javobgarlik
            candidates.append((suf, rest, suf_slot))
        if not candidates:
            break
        # Longest ending wins, unless a shorter one leaves a known root (majlis-i, not majli-si). Possessive
        # "-si" after o/u/i is rare in native words, so "asosi", "tashabbusi" are read as asos-i, tashabbus-i.
        suf, rest, suf_slot = next((c for c in candidates if c[2] == 2 and c[1] in _UZ_PROTECTED), candidates[0])
        if suf == "si" and rest[-1] in "oui":
            alt = next((c for c in candidates if c[0] == "i"), None)
            if alt is not None:
                suf, rest, suf_slot = alt
        word, slot = rest, suf_slot
        verbal = verbal or suf in _VERBAL
        if word in _UZ_PROTECTED:
            return word
        if slot >= 5:
            break
    if _AGENT_RE.search(word) and len(word) >= 6:
        return word
    if word in _UZ_VERB_ALIASES:
        return _UZ_VERB_ALIASES[word]
    if verbal and word not in _UZ_PROTECTED:
        for suf, kind in _VOICE:
            if word.endswith(suf):
                rest = word[: -len(suf)]
                if not _rest_ok(rest):
                    continue
                if kind == "c" and rest[-1] in _VOWELS:
                    continue
                if kind == "v" and rest[-1] not in _VOWELS:
                    continue
                word = rest
                break
        if len(word) >= 4 and word[-1] in "ao" and word[-2] not in _VOWELS:
            word = word[:-1]
    return word


_RU_DERIV = ("ован", "еван", "ыва", "ива", "ова", "ева", "ени", "ани", "ств", "ник", "ен", "ан", "ня")
_RU_VOWELS = set("аеёиоуыэюя")


@lru_cache(maxsize=200_000)
def stem_ru(token: str) -> str:
    """Snowball stem plus light derivational folding (увольнение / уволили / увольняют -> увол)."""
    stemmer = _stemmer("russian") if len(token) > 3 and token.isalpha() else None
    if stemmer is None:
        return token
    stem = stemmer.stemWord(token).replace("ь", "").replace("ъ", "")
    for _ in range(2):
        for suf in _RU_DERIV:
            if stem.endswith(suf) and len(stem) - len(suf) >= 4:
                stem = stem[: -len(suf)]
                break
        else:
            break
    if len(stem) >= 5 and stem[-1] in "ая" and stem[-2] not in _RU_VOWELS:
        stem = stem[:-1]
    if len(stem) >= 5 and stem[-1] == "н" and stem[-2] not in _RU_VOWELS:
        stem = stem[:-1]
    return stem


@lru_cache(maxsize=50_000)
def stem_en(token: str) -> str:
    stemmer = _stemmer("english") if len(token) > 3 and token.isalpha() else None
    if stemmer is None:
        return token
    return stemmer.stemWord(token)


def uz_latin_fold(text: str) -> str:
    """Uzbek text (either script) -> lowercase apostrophe-free Latin."""
    t = _nfkc_lower(text)
    if has_cyrillic(t):
        t = cyrillic_to_latin(t).lower()
    return fold_apostrophes(t)


def tokens(text: str) -> list[str]:
    """Lowercase alphanumeric tokens of an already folded string."""
    return _TOKEN_RE.findall(text)


def raw_words(text: str) -> list[str]:
    """Surface words as typed (lowercased, apostrophes kept) — used by intent rules and spelling."""
    return [w for w in _SPLIT_RE.split(_nfkc_lower(text)) if w]


def _is_ru_token(tok: str) -> bool:
    return bool(_CYR_RE.search(tok))


def surface_tokens(text: str, *, language: str) -> list[str]:
    """Folded words before stemming (spelling correction works on these): Uzbek in apostrophe-free Latin."""
    if not text:
        return []
    if language == "ru":
        return tokens(_ru_fold(fold_apostrophes(text)))
    if language == "en":
        return tokens(_nfkc_lower(fold_apostrophes(text)))
    return tokens(uz_latin_fold(text))


def stem_token(tok: str) -> str:
    """Stem one folded token with the analyzer of its script."""
    if _is_ru_token(tok):
        return stem_ru(tok)
    return stem_uz(tok)


def index_terms(text: str, *, language: str) -> list[str]:
    """Search terms for a document text. ``language`` is the chunk language value (uz_latn/uz_cyrl/ru/en)."""
    if not text:
        return []
    if language == "ru":
        out: list[str] = []
        for tok in tokens(_ru_fold(fold_apostrophes(text))):
            out.append(stem_ru(tok) if _is_ru_token(tok) else stem_uz(tok))
        return out
    if language == "en":
        return [stem_en(t) for t in tokens(_nfkc_lower(fold_apostrophes(text)))]
    return [stem_uz(t) for t in tokens(uz_latin_fold(text))]


def query_terms(text: str, *, language: str) -> list[str]:
    """Search terms for a question; Cyrillic questions of unclear language are expanded as both RU and UZ."""
    if not text:
        return []
    if language == "ru":
        terms = index_terms(text, language="ru")
        # Russian speakers in Uzbekistan mix in Uzbek words; a Latin mirror catches Uzbek-Cyrillic tokens too.
        if is_uzbek_cyrillic(text):
            terms += index_terms(text, language="uz_cyrl")
        return terms
    if language == "en":
        return [stem_en(t) for t in tokens(_nfkc_lower(fold_apostrophes(text)))]
    return index_terms(text, language="uz_latn")


def fold_for_match(text: str) -> str:
    """Comparison key for short phrases: folded Latin for Uzbek, lowercased Cyrillic for Russian."""
    t = _nfkc_lower(text)
    if has_cyrillic(t) and is_uzbek_cyrillic(t):
        t = cyrillic_to_latin(t).lower()
    return re.sub(r"\s+", " ", fold_apostrophes(t)).strip()
