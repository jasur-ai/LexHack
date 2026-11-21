"""Query decomposition, legal branch classification, and temporal/multilingual intent extraction."""

from __future__ import annotations

import logging
import re
from datetime import date

from lex_agent.ingestion.parser import classify_branches, parse_date_string
from lex_agent.language.transliterator import (
    cyrillic_to_latin,
    detect_language,
    latin_to_cyrillic,
    normalize_uzbek_apostrophes,
)
from lex_agent.llm.client import LLMClient
from lex_agent.models import DocumentType, Language, LegalBranch, QueryPlan, SubQuery

logger = logging.getLogger(__name__)

_DATE_PATTERNS = [
    re.compile(r"(?:as\s+of|on|in|before|after)\s+(\d{4}-\d{2}-\d{2}|\d{2}\.\d{2}\.\d{4})", re.I),
    re.compile(r"(?:по\s+состоянию\s+на|на\s+дату|в)\s+(\d{2}\.\d{2}\.\d{4}|\d{4}-\d{2}-\d{2})", re.I),
    re.compile(r"(\d{2}\.\d{2}\.\d{4}|\d{4}-\d{2}-\d{2})\s*(?:holatiga|sanasiga|yilda|йилда)", re.I),
    re.compile(r"\b((?:199\d|20[0-2]\d))-?(?:yil|йил|год|year)\b", re.I),
]


class LegalQueryDecomposer:
    """Decomposes complex multi-issue legal queries into targeted UZ/RU/EN sub-queries and legal metadata."""

    def __init__(self, llm: LLMClient) -> None:
        self.llm = llm

    async def decompose(
        self,
        query: str,
        *,
        explicit_as_of_date: date | None = None,
        use_llm: bool = False,
    ) -> QueryPlan:
        detected_lang = detect_language(query)
        inferred_date = explicit_as_of_date or self._extract_date(query)
        rule_branches = classify_branches(query)
        suspected_articles = self._extract_articles(query)

        low = normalize_uzbek_apostrophes(query).lower()
        wants_compare = any(
            kw in low
            for kw in ("discrepanc", "translate", "translation", "tarjima", "farq", "расхожден", "перевод", "сравни")
        )
        wants_history = inferred_date is not None or any(
            kw in low for kw in ("before amendment", "historical", "used to be", "avvalgi tahrir", "ранее", "предыдущ")
        )

        # Instant deterministic decomposition (<2ms) avoids adding a 2-3s extra LLM roundtrip before retrieval
        if not use_llm or self.llm.is_mock:
            return self._fallback_plan(
                query=query,
                detected_lang=detected_lang,
                branches=rule_branches,
                as_of_date=inferred_date,
                suspected_articles=suspected_articles,
                wants_compare=wants_compare,
                wants_history=wants_history,
            )

        system_prompt = (
            "You are a Senior Uzbekistan Legal Architect. Decompose the user's legal question into discrete legal "
            "sub-issues and generate concise search queries across Uzbek (Latin), Russian, and English so the retrieval "
            "engine finds all relevant Constitution provisions, Codes, Laws, Presidential Decrees/Resolutions, "
            "Cabinet of Ministers Resolutions, departmental regulations, and Supreme Court Plenum resolutions on Lex.uz.\n"
            "Return STRICT JSON with keys:\n"
            "{\n"
            '  "sub_queries": [\n'
            "    {\n"
            '      "issue": "clear legal sub-issue",\n'
            '      "search_queries_uz": ["uzbek latin search query"],\n'
            '      "search_queries_ru": ["russian search query"],\n'
            '      "search_queries_en": ["english search query"],\n'
            '      "branches": ["civil" | "criminal" | "labor" | "tax" | ...],\n'
            '      "suspected_doc_types": ["code" | "law" | "presidential_decree" | "cabinet_resolution" | ...],\n'
            '      "suspected_articles": ["148", ...]\n'
            "    }\n"
            "  ],\n"
            '  "as_of_date": "YYYY-MM-DD or null",\n'
            '  "requires_translation_comparison": false,\n'
            '  "requires_historical_comparison": false,\n'
            '  "potential_norm_conflict": false\n'
            "}"
        )

        data = await self.llm.complete_json(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": query},
            ],
            fast=True,
            fallback=None,
        )

        if not isinstance(data, dict) or not data.get("sub_queries"):
            return self._fallback_plan(
                query=query,
                detected_lang=detected_lang,
                branches=rule_branches,
                as_of_date=inferred_date,
                suspected_articles=suspected_articles,
                wants_compare=wants_compare,
                wants_history=wants_history,
            )

        sub_queries: list[SubQuery] = []
        all_branches: set[LegalBranch] = set(rule_branches)

        for sq in data.get("sub_queries", [])[:5]:
            sq_branches = self._parse_branches(sq.get("branches", [])) or rule_branches
            all_branches.update(sq_branches)
            sq_doc_types = self._parse_doc_types(sq.get("suspected_doc_types", []))
            sq_articles = [str(a) for a in sq.get("suspected_articles", []) if a]
            sub_queries.append(
                SubQuery(
                    issue=str(sq.get("issue", query)),
                    search_queries_uz=[str(x) for x in sq.get("search_queries_uz", []) if x][:3],
                    search_queries_ru=[str(x) for x in sq.get("search_queries_ru", []) if x][:3],
                    search_queries_en=[str(x) for x in sq.get("search_queries_en", []) if x][:2],
                    branches=sq_branches,
                    suspected_doc_types=sq_doc_types,
                    suspected_articles=sq_articles or suspected_articles,
                )
            )

        llm_date = parse_date_string(data.get("as_of_date")) if not explicit_as_of_date else explicit_as_of_date

        return QueryPlan(
            original_query=query,
            detected_language=detected_lang,
            sub_queries=sub_queries,
            branches=list(all_branches),
            as_of_date=llm_date or inferred_date,
            requires_translation_comparison=bool(data.get("requires_translation_comparison", wants_compare)),
            requires_historical_comparison=bool(data.get("requires_historical_comparison", wants_history)),
            potential_norm_conflict=bool(data.get("potential_norm_conflict", False)),
        )

    def _fallback_plan(
        self,
        *,
        query: str,
        detected_lang: Language,
        branches: list[LegalBranch],
        as_of_date: date | None,
        suspected_articles: list[str],
        wants_compare: bool,
        wants_history: bool,
    ) -> QueryPlan:
        uz_queries: list[str] = []
        ru_queries: list[str] = []
        en_queries: list[str] = []

        if detected_lang == Language.UZ_LATN:
            uz_queries = [query, latin_to_cyrillic(query)]
        elif detected_lang == Language.UZ_CYRL:
            uz_queries = [cyrillic_to_latin(query), query]
        elif detected_lang == Language.RU:
            ru_queries = [query]
        else:
            en_queries = [query]

        return QueryPlan(
            original_query=query,
            detected_language=detected_lang,
            sub_queries=[
                SubQuery(
                    issue=query,
                    search_queries_uz=uz_queries,
                    search_queries_ru=ru_queries,
                    search_queries_en=en_queries,
                    branches=branches,
                    suspected_articles=suspected_articles,
                )
            ],
            branches=branches,
            as_of_date=as_of_date,
            requires_translation_comparison=wants_compare,
            requires_historical_comparison=wants_history,
            potential_norm_conflict=False,
        )

    @staticmethod
    def _extract_date(query: str) -> date | None:
        for pat in _DATE_PATTERNS:
            m = pat.search(query)
            if not m:
                continue
            raw = m.group(1)
            if re.fullmatch(r"\d{4}", raw):
                return date(int(raw), 1, 1)
            parsed = parse_date_string(raw)
            if parsed:
                return parsed
        return None

    @staticmethod
    def _extract_articles(query: str) -> list[str]:
        found = re.findall(
            r"\b(\d+(?:[-.]\d+)?)\s*-?\s*(?:modda|модда)|(?:ст\.|стать\w+|article)\s*(\d+(?:[-.]\d+)?)\b",
            query,
            re.I,
        )
        return sorted({a or b for a, b in found if (a or b)})

    @staticmethod
    def _parse_branches(raw_list: list[str]) -> list[LegalBranch]:
        out: list[LegalBranch] = []
        for item in raw_list:
            try:
                out.append(LegalBranch(str(item).lower().strip()))
            except ValueError:
                pass
        return out

    @staticmethod
    def _parse_doc_types(raw_list: list[str]) -> list[DocumentType]:
        out: list[DocumentType] = []
        for item in raw_list:
            try:
                out.append(DocumentType(str(item).lower().strip()))
            except ValueError:
                pass
        return out
