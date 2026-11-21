"""Colloquial → statutory query expansion for Uzbek (Latin/Cyrillic), Russian and English legal questions.

People ask "ishdan haydashdi" ("they kicked me out of work"); the Labour Code says "mehnat shartnomasini ish
beruvchining tashabbusiga koʻra bekor qilish". Lexical retrieval cannot bridge that gap on its own, so every
question is additionally searched with the formal wording of the situations it describes. The wording comes
from the situation lexicon (:mod:`lex_agent.knowledge.lexicon`, several hundred curated situations with their
target articles). Russian questions are expanded in both languages because the Uzbek corpus is the
authoritative one.
"""

from __future__ import annotations

from lex_agent.knowledge.lexicon import ConceptMatch, get_lexicon
from lex_agent.language.transliterator import detect_language


def match_situations(
    query: str, *, language: str | None = None, corrected_terms: list[str] | None = None, limit: int = 3
) -> list[ConceptMatch]:
    """Lexicon situations described by the question (most specific first)."""
    if not query or not query.strip():
        return []
    return get_lexicon().match(query, language=language, corrected_terms=corrected_terms, limit=limit)


def expand_query(query: str, *, max_expansions: int = 2) -> list[str]:
    """Return up to ``max_expansions`` formal statutory phrasings for a colloquial legal question."""
    if not query or not query.strip():
        return []
    lang = detect_language(query).value
    matches = match_situations(query, language=lang)
    phrases = get_lexicon().formal_phrases(matches, language=lang)
    if lang == "en":
        phrases = phrases[:1]
    return phrases[:max_expansions]
