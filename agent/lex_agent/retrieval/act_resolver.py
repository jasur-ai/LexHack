"""Recognise which act (and article) a question names: "Mehnat kodeksining 217-moddasi", "ТК ст. 161",
"MJtK 128-modda", "shaxsga doir ma'lumotlar to'g'risidagi qonun", "O'RQ-547", "Labour Code article 217".

Titles come from the bundled act catalog (``data/corpus/catalog.json``) and are matched on analysed terms, so
inflected forms ("kodeksining", "qonunning", "кодекса") and both Uzbek scripts work. Codes also get the
abbreviations lawyers and citizens actually use (MK, JK, FK, MJtK, ТК, УК, ГК, КоАО…).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from lex_agent.language.textproc import fold_for_match, index_terms, query_terms
from lex_agent.language.transliterator import detect_language
from lex_agent.retrieval.bm25_store import number_tokens

# Canonical (Uzbek lex.uz) ids of the codes, with their customary abbreviations / alternative names.
# Patterns are matched against the *folded* question (Uzbek: apostrophe-free Latin; Russian: lowercase).
_CODE_ALIASES: dict[str, tuple[str, ...]] = {
    "6445145": (r"konstitutsiya\w*", r"asosiy qonun\w*", r"конституци\w*", r"constitution"),
    "6257288": (r"\bmk\b", r"mehnat kodeks\w*", r"\bтк\b(?!\s*рф)", r"трудов\w* кодекс\w*", r"labou?r code"),
    "111453": (r"\bjk\b", r"jinoyat kodeks\w*", r"\bук\b", r"уголовн\w* кодекс\w*", r"criminal code"),
    "111189": (r"\bfk\b", r"fuqarolik kodeks\w*", r"\bгк\b", r"гражданск\w* кодекс\w*", r"civil code"),
    "180552": (r"\bfk\b", r"fuqarolik kodeks\w*", r"\bгк\b", r"гражданск\w* кодекс\w*", r"civil code"),
    "97664": (
        r"\bmjtk\b", r"\bmjk\b", r"ma'?muriy javobgarlik\w*(?: togrisidagi)? kodeks\w*", r"\bкоап\b", r"\bкоао\b",
        r"кодекс\w* об административн\w* ответственност\w*", r"administrative (?:liability|responsibility|offen[cs]es?) code",
        r"code (?:on|of) administrative (?:liability|responsibility)",
    ),
    "104720": (r"oila kodeks\w*", r"семейн\w* кодекс\w*", r"family code"),
    "4674902": (r"soliq kodeks\w*", r"\bнк\b", r"налогов\w* кодекс\w*", r"tax code"),
    "106136": (r"uy-?joy kodeks\w*", r"\bжк\b", r"жилищн\w* кодекс\w*", r"housing code"),
    "152653": (r"yer kodeks\w*", r"\bзк\b", r"земельн\w* кодекс\w*", r"land code"),
    "3517337": (r"\bfpk\b", r"fuqarolik protsessual kodeks\w*", r"\bгпк\b", r"гражданск\w* процессуальн\w* кодекс\w*",
                r"civil procedure code"),
    "111460": (r"\bjpk\b", r"jinoyat-? ?protsessual kodeks\w*", r"\bупк\b", r"уголовно-? ?процессуальн\w* кодекс\w*",
               r"criminal procedure code"),
    "3523891": (r"\bipk\b", r"iqtisodiy protsessual kodeks\w*", r"\bэпк\b", r"экономическ\w* процессуальн\w* кодекс\w*",
                r"economic procedure code"),
    "3527353": (r"ma'?muriy sud ishlarini yuritish\w*", r"кодекс\w* об административн\w* судопроизводств\w*",
                r"administrative (?:court )?procedure code"),
    "163629": (r"jinoyat-? ?ijroiya kodeks\w*", r"\bуик\b", r"уголовно-? ?исполнительн\w* кодекс\w*",
               r"criminal enforcement code"),
    "2876354": (r"bojxona kodeks\w*", r"таможенн\w* кодекс\w*", r"customs code"),
    "2304138": (r"budjet kodeks\w*", r"byudjet kodeks\w*", r"бюджетн\w* кодекс\w*", r"budget code"),
    "4386848": (r"saylov kodeks\w*", r"избирательн\w* кодекс\w*", r"election code|electoral code"),
    "5307951": (r"shaharsozlik kodeks\w*", r"градостроительн\w* кодекс\w*", r"urban planning code"),
    "55594": (r"havo kodeks\w*", r"воздушн\w* кодекс\w*", r"air code"),
    "7655343": (r"suv kodeks\w*", r"водн\w* кодекс\w*", r"water code"),
}
_CIVIL_PARTS = ("111189", "180552")

_ARTICLE_RE = re.compile(
    r"(?<![\d.])(\d{1,4})(?:\s*[-.]\s*(\d{1,2})|\s*([¹²³⁴⁵⁶⁷⁸⁹]+))?\s*-?\s*(?:modda\w*|модда\w*)|"
    r"(?:\bст\.?|\bстать[яиеюё]\w*|\barticle|\bart\.?)\s*(\d{1,4})(?:[.-](\d{1,2})|([¹²³⁴⁵⁶⁷⁸⁹]+))?|"
    r"(?<![\d.])(\d{1,4})\s*-?\s*(?:я|ая|й)?\s+стать\w*",
    re.I,
)
_SUP = str.maketrans("¹²³⁴⁵⁶⁷⁸⁹", "123456789")
# Several articles at once. Only plural forms count, so "104-1-modda" (article 104¹) is never read as a range.
ARTICLE_RANGE_RE = re.compile(
    r"(?<![\d.])(\d{1,4})\s*(?:[-–—]|va|hamda|ва|ҳамда|,)\s*(\d{1,4})\s*-?\s*(?:moddalar\w*|моддалар\w*)|"
    r"(?:\bстать(?:и|ям|ями|ях)|\barticles|\bmoddalar\w*|\bмоддалар\w*)\s+(\d{1,4})\s*(?:[-–—]|и|and|&|,|va)\s*(\d{1,4})\b",
    re.I,
)


def range_articles(text: str) -> list[tuple[str, int, int]]:
    """Article numbers named as a range or list, with the span of the match: ("18", s, e), ("19", s, e)."""
    out: list[tuple[str, int, int]] = []
    for m in ARTICLE_RANGE_RE.finditer(text):
        a, b = int(m.group(1) or m.group(3)), int(m.group(2) or m.group(4))
        nums = list(range(a, b + 1)) if 0 < b - a <= 5 else [a, b]
        out.extend((str(n), m.start(), m.end()) for n in nums)
    return out
_NUMBER_RE = re.compile(
    r"(?:o['ʻ‘’`]?rq|ўрқ|зру|\bpf|пф|уп|\bpq|пқ|пп|vmq|вмқ|пкм)\s*[-№]?\s*(\d{1,5})|\b(\d{2,4})\s*-\s*([ivxlc]{1,4}|[іх]{1,4})\b",
    re.I,
)
_TITLE_STOP_WORDS = ("togrisida", "togrisidagi", "haqida", "haqidagi", "qonun", "qonuni", "qonunning", "ozbekiston",
                     "respublikasi", "respublikasining")
_TITLE_STOP_WORDS_RU = ("закон", "о", "об", "обо", "республики", "узбекистан")
_TITLE_STOP = frozenset(
    {t for w in _TITLE_STOP_WORDS for t in index_terms(w, language="uz_latn")}
    | {t for w in _TITLE_STOP_WORDS_RU for t in index_terms(w, language="ru")}
    | set(_TITLE_STOP_WORDS)
    | set(_TITLE_STOP_WORDS_RU)
)


@dataclass(frozen=True, slots=True)
class ActRef:
    canonical_id: str
    article: str | None = None  # canonical article id: "217", "104.1"
    via: str = "title"  # title | alias | number


@dataclass(slots=True)
class _Title:
    canonical_id: str
    terms: tuple[str, ...]


def _article_ids(text: str) -> list[str]:
    """Article ids in the order they appear: "217", "104.1" (¹ or -1), and every member of a range or list."""
    found: list[tuple[int, str]] = []
    for m in _ARTICLE_RE.finditer(text):
        base = m.group(1) or m.group(4) or m.group(7)
        sub = m.group(2) or m.group(5) or (m.group(3) or m.group(6) or "").translate(_SUP)
        found.append((m.start(), f"{base}.{sub}" if sub else base))
    found.extend((start, art) for art, start, _ in range_articles(text))
    out: list[str] = []
    for _, art in sorted(found, key=lambda x: x[0]):
        if art not in out:
            out.append(art)
    return out


class ActResolver:
    """Resolves act names, abbreviations, numbers and article numbers mentioned in a question."""

    def __init__(self, catalog: dict[str, dict]) -> None:
        self.catalog = catalog
        self._aliases = [
            (cid, re.compile(p, re.I)) for cid, pats in _CODE_ALIASES.items() for p in pats
        ]
        self._titles: list[_Title] = []
        self._by_number: dict[str, str] = {}
        for cid, d in catalog.items():
            for key in ("number_uz", "number_ru"):
                tok = number_tokens(d.get(key))
                if tok:
                    self._by_number.setdefault(tok, cid)
            if cid in _CODE_ALIASES:
                continue
            for title, lang in ((d.get("short_uz"), "uz_cyrl"), (d.get("short_ru"), "ru")):
                if not title:
                    continue
                terms = tuple(t for t in index_terms(title, language=lang) if t not in _TITLE_STOP)
                if len(terms) >= 2:
                    self._titles.append(_Title(cid, terms))
        # Longer titles first so "Bolalarni zo'ravonlikdan himoya qilish" wins over a two-word title it contains
        self._titles.sort(key=lambda t: len(t.terms), reverse=True)

    @classmethod
    def from_corpus(cls, corpus_dir: Path) -> ActResolver:
        return _load(str(corpus_dir))

    def resolve(self, question: str) -> list[ActRef]:
        """Acts named in the question (most specific first), each with the article number when one is given."""
        folded = fold_for_match(question)
        articles = _article_ids(question)
        found: list[tuple[str, str]] = []

        for m in _NUMBER_RE.finditer(question):
            raw = m.group(0)
            cid = self._by_number.get(number_tokens(raw))
            if cid and all(cid != f for f, _ in found):
                found.append((cid, "number"))

        for cid, rx in self._aliases:
            if rx.search(folded) and all(cid != f for f, _ in found):
                found.append((cid, "alias"))

        if len(found) < 3 and self._titles:
            lang = detect_language(question).value
            q_terms = query_terms(question, language=lang)
            joined = " " + " ".join(q_terms) + " "
            for t in self._titles:
                if " " + " ".join(t.terms) + " " in joined and all(t.canonical_id != f for f, _ in found):
                    found.append((t.canonical_id, "title"))
                    if len(found) >= 3:
                        break

        refs: list[ActRef] = []
        for cid, via in found:
            if articles:
                for art in articles[:3]:
                    refs.append(ActRef(cid, art, via))
            else:
                refs.append(ActRef(cid, None, via))
        return refs

    @staticmethod
    def civil_part_for(article: str | None) -> str | None:
        """The Civil Code is published in two parts: articles 1–385 (part I) and 386–1199 (part II)."""
        if not article:
            return None
        try:
            base = int(article.split(".")[0])
        except ValueError:
            return None
        return _CIVIL_PARTS[0] if base <= 385 else _CIVIL_PARTS[1]

    def mentioned_articles(self, question: str) -> list[str]:
        return _article_ids(question)


@lru_cache(maxsize=4)
def _load(corpus_dir: str) -> ActResolver:
    from lex_agent.ingestion.open_corpora import load_catalog

    try:
        catalog = load_catalog(Path(corpus_dir))
    except (OSError, ValueError, KeyError):
        catalog = {}
    return ActResolver(catalog)
