"""Situation lexicon: maps the way people describe a legal problem to the norms that govern it.

People write "ishdan haydashdi", "алименты сколько", "tatil puli bermadi" or "I got fired"; statutes say
"mehnat shartnomasini ish beruvchining tashabbusiga koʻra bekor qilish". Each :class:`Concept` carries

* trigger patterns for Uzbek (Latin or Cyrillic input, matched on a folded Latin view), Russian and English,
* the formal Uzbek and Russian wording used to re-phrase the search,
* *target norms* — the articles that answer the situation, most important first,
* the domain, optional calculator and the facts worth asking about when they are missing.

The table lives in :mod:`lex_agent.knowledge.lexicon_data`. Matching is a set of small regular expressions
(well under a millisecond per question).
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from functools import lru_cache

from lex_agent.language.transliterator import cyrillic_to_latin, detect_language

_APOS_RE = re.compile(r"[ʻʼ‘’`´ʹʽˈ'ʿ]")
_SPACE_RE = re.compile(r"\s+")

DOMAINS: dict[str, tuple[str, str, str]] = {
    "labour": ("Mehnat huquqi", "Трудовое право", "Labour law"),
    "family": ("Oila huquqi", "Семейное право", "Family law"),
    "civil": ("Shartnomalar va zarar", "Договоры и возмещение вреда", "Contracts and damages"),
    "inheritance": ("Meros", "Наследство", "Inheritance"),
    "housing": ("Uy-joy", "Жильё", "Housing"),
    "consumer": ("Isteʼmolchi huquqlari", "Права потребителей", "Consumer rights"),
    "traffic": ("Yoʻl harakati", "Дорожное движение", "Road traffic"),
    "admin": ("Maʼmuriy javobgarlik", "Административная ответственность", "Administrative offences"),
    "criminal": ("Jinoyat huquqi", "Уголовное право", "Criminal law"),
    "procedure": ("Sud, ijro va yuridik yordam", "Суд, исполнение и юрпомощь", "Courts, enforcement and legal aid"),
    "tax": ("Soliqlar", "Налоги", "Taxes"),
    "business": ("Tadbirkorlik", "Предпринимательство", "Business"),
    "social": ("Pensiya va ijtimoiy himoya", "Пенсии и соцзащита", "Pensions and social protection"),
    "rights": ("Fuqarolar va davlat", "Граждане и государство", "Citizens and the state"),
    "property": ("Yer va koʻchmas mulk", "Земля и недвижимость", "Land and real estate"),
    "finance": ("Bank, kredit, sugʻurta", "Банки, кредиты, страхование", "Banking, credit and insurance"),
    "migration": ("Fuqarolik va roʻyxat", "Гражданство и регистрация", "Citizenship and residence"),
    "public": ("Taʼlim, sogʻliq, harbiy xizmat", "Образование, здоровье, армия", "Education, health and military"),
    "figures": ("Amaliy koʻrsatkichlar", "Практические показатели", "Practical figures"),
}


def fold_uz(text: str) -> str:
    """Matching view of Uzbek text: Latin script, lowercase, no apostrophes, x->h and q->k merged."""
    t = unicodedata.normalize("NFKC", text or "").lower()
    if any("\u0400" <= ch <= "\u04ff" for ch in t):
        t = cyrillic_to_latin(t).lower()
    t = _APOS_RE.sub("", t)
    t = t.replace("x", "h").replace("q", "k")
    return _SPACE_RE.sub(" ", t).strip()


def fold_ru(text: str) -> str:
    return _SPACE_RE.sub(" ", unicodedata.normalize("NFKC", text or "").lower().replace("ё", "е")).strip()


# "~" in a pattern = the rest of the current word plus up to four more words ("aliment~kamaytir" matches
# "aliment miqdorini kamaytirish").
_GAP = r"\w*(?:\W+\w+){0,4}?\W+"


def _compile_uz(pattern: str | None) -> re.Pattern[str] | None:
    if not pattern:
        return None
    # Patterns are written in natural spelling; the view merges x/h and q/k, so the pattern must too.
    src = _APOS_RE.sub("", pattern).replace("x", "h").replace("q", "k").replace("~", _GAP)
    return re.compile(src, re.I)


def _compile(pattern: str | None) -> re.Pattern[str] | None:
    return re.compile(pattern.replace("~", _GAP), re.I) if pattern else None


def parse_targets(spec: str) -> tuple[tuple[str, str], ...]:
    """'6257288:161,165;97664:49' -> (('6257288','161'), ('6257288','165'), ('97664','49'))."""
    out: list[tuple[str, str]] = []
    for part in spec.split(";"):
        part = part.strip()
        if not part:
            continue
        doc, _, arts = part.partition(":")
        for art in arts.split(","):
            art = art.strip()
            if art:
                out.append((doc.strip(), art))
    return tuple(out)


@dataclass(frozen=True, slots=True)
class Concept:
    id: str
    domain: str
    uz: re.Pattern[str] | None
    ru: re.Pattern[str] | None
    en: re.Pattern[str] | None
    formal_uz: str
    formal_ru: str
    targets: tuple[tuple[str, str], ...]
    generic: bool = False
    calc: str | None = None
    ask: tuple[str, ...] = ()
    follow_uz: tuple[str, ...] = ()
    follow_ru: tuple[str, ...] = ()
    unless_uz: re.Pattern[str] | None = None
    unless_ru: re.Pattern[str] | None = None

    @property
    def target_docs(self) -> set[str]:
        return {d for d, _ in self.targets}

    def trigger_words(self) -> set[str]:
        """Literal words used in the trigger patterns (protected from spelling "correction")."""
        out: set[str] = set()
        for pat in (self.uz, self.ru, self.en):
            if pat is not None:
                out.update(w.lower() for w in re.findall(r"[a-zа-яёўқғҳ]{4,}", pat.pattern, re.I))
        return out


def concept(
    cid: str,
    uz: str | None,
    ru: str | None,
    en: str | None,
    formal_uz: str,
    formal_ru: str,
    targets: str,
    *,
    generic: bool = False,
    calc: str | None = None,
    ask: tuple[str, ...] = (),
    follow_uz: tuple[str, ...] = (),
    follow_ru: tuple[str, ...] = (),
    unless_uz: str | None = None,
    unless_ru: str | None = None,
) -> Concept:
    domain = cid.split(".", 1)[0]
    if domain not in DOMAINS:
        raise ValueError(f"Unknown lexicon domain in {cid!r}")
    return Concept(
        id=cid,
        domain=domain,
        uz=_compile_uz(uz),
        ru=_compile(ru),
        en=_compile(en),
        formal_uz=formal_uz,
        formal_ru=formal_ru,
        targets=parse_targets(targets),
        generic=generic,
        calc=calc,
        ask=ask,
        follow_uz=follow_uz,
        follow_ru=follow_ru,
        unless_uz=_compile_uz(unless_uz),
        unless_ru=_compile(unless_ru),
    )


@dataclass(slots=True)
class ConceptMatch:
    concept: Concept
    span: int
    score: float = 0.0
    matched: str = ""

    @property
    def id(self) -> str:
        return self.concept.id


@dataclass(slots=True)
class LexiconView:
    """Pre-folded views of one question (built once, reused by every concept)."""

    language: str
    uz: str
    ru: str
    en: str
    extra_uz: list[str] = field(default_factory=list)


class Lexicon:
    def __init__(self, concepts: list[Concept]) -> None:
        ids = [c.id for c in concepts]
        dupes = {i for i in ids if ids.count(i) > 1}
        if dupes:
            raise ValueError(f"Duplicate lexicon ids: {sorted(dupes)}")
        self.concepts = concepts
        self.by_id = {c.id: c for c in concepts}

    def __len__(self) -> int:
        return len(self.concepts)

    @property
    def trigger_words(self) -> frozenset[str]:
        words = getattr(self, "_trigger_words", None)
        if words is None:
            words = frozenset(w for c in self.concepts for w in c.trigger_words())
            self._trigger_words = words
        return words

    @staticmethod
    def view(query: str, *, language: str | None = None, corrected_terms: list[str] | None = None) -> LexiconView:
        lang = language or detect_language(query).value
        uz = fold_uz(query) if lang != "ru" else ""
        ru = fold_ru(query) if lang == "ru" else ""
        en = fold_ru(query) if lang in ("en", "uz_latn") else ""
        extra: list[str] = []
        if corrected_terms:
            text = " ".join(corrected_terms)
            if lang == "ru":
                ru = f"{ru} | {fold_ru(text)}"
            else:
                extra = [fold_uz(text)]
        return LexiconView(language=lang, uz=uz, ru=ru, en=en, extra_uz=extra)

    def match(
        self,
        query: str,
        *,
        language: str | None = None,
        corrected_terms: list[str] | None = None,
        limit: int = 3,
    ) -> list[ConceptMatch]:
        """Concepts triggered by the question, most specific first (at most ``limit``)."""
        if not query or not query.strip():
            return []
        v = self.view(query, language=language, corrected_terms=corrected_terms)
        found: dict[str, ConceptMatch] = {}
        for c in self.concepts:
            best: re.Match[str] | None = None
            if v.language == "ru":
                if c.ru is not None and not (c.unless_ru is not None and c.unless_ru.search(v.ru)):
                    best = c.ru.search(v.ru)
            elif c.unless_uz is not None and (c.unless_uz.search(v.uz) or (v.en and c.unless_uz.search(v.en))):
                continue
            else:
                texts = [v.uz, *v.extra_uz]
                if c.uz is not None:
                    for t in texts:
                        m = c.uz.search(t)
                        if m and (best is None or len(m.group(0)) > len(best.group(0))):
                            best = m
                if best is None and c.en is not None and v.en:
                    best = c.en.search(v.en)
            if best is None:
                continue
            span = len(best.group(0))
            # Specific situations always outrank generic ones; among equals the longer matched wording wins.
            score = (0.0 if c.generic else 10.0) + min(span, 30) * 0.5 + min(len(c.targets), 4) * 0.05
            found[c.id] = ConceptMatch(concept=c, span=span, score=score, matched=best.group(0))
        ranked = sorted(found.values(), key=lambda m: (-m.score, m.concept.id))
        # A generic concept of a domain is kept only when no specific concept of that domain fired
        specific_domains = {m.concept.domain for m in ranked if not m.concept.generic}
        ranked = [m for m in ranked if not (m.concept.generic and m.concept.domain in specific_domains)] + [
            m for m in ranked if m.concept.generic and m.concept.domain in specific_domains
        ]
        return ranked[:limit]

    def formal_phrases(self, matches: list[ConceptMatch], *, language: str) -> list[str]:
        out: list[str] = []
        for m in matches:
            phrases = (m.concept.formal_ru, m.concept.formal_uz) if language == "ru" else (m.concept.formal_uz,)
            for p in phrases:
                if p and p not in out:
                    out.append(p)
        return out


@lru_cache(maxsize=1)
def get_lexicon() -> Lexicon:
    from lex_agent.knowledge.lexicon_data import CONCEPTS

    return Lexicon(CONCEPTS)
