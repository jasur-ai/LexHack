"""Multi-language legal translation & UZ/RU/EN discrepancy verification against authoritative Uzbek texts."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from lex_agent.language.transliterator import detect_language
from lex_agent.llm.client import LLMClient
from lex_agent.models import (
    DiscrepancyItem,
    Language,
    RiskSeverity,
    TranslationCompareRequest,
    TranslationCompareResponse,
)

if TYPE_CHECKING:
    from lex_agent.ingestion.lex_fetcher import LexUzFetcher
    from lex_agent.retrieval.bm25_store import BM25Store

logger = logging.getLogger(__name__)

# Official Lex.uz institutional legal terminology glossary
OFFICIAL_LEGAL_GLOSSARY = """
Official Lex.uz UZ <-> RU <-> EN Legal Terminology:
- O'zbekiston Respublikasi Qonuni | Закон Республики Узбекистан | Law of the Republic of Uzbekistan
- O'zbekiston Respublikasi Prezidentining Farmoni (PF) | Указ Президента Республики Узбекистан (УП) | Decree of the President of the Republic of Uzbekistan
- O'zbekiston Respublikasi Prezidentining Qarori (PQ) | Постановление Президента Республики Узбекистан (ПП) | Resolution of the President of the Republic of Uzbekistan
- Vazirlar Mahkamasining Qarori (VMQ) | Постановление Кабинета Министров (ПКМ) | Resolution of the Cabinet of Ministers
- Oliy sud Plenumi qarori | Постановление Пленума Верховного суда | Resolution of the Plenum of the Supreme Court
- Normativ-huquqiy hujjat | Нормативно-правовой акт | Normative-legal act
- Modda / band / qism | Статья / пункт / часть | Article / clause / part
- Yuridik shaxs | Юридическое лицо | Legal entity
- Jismoniy shaxs | Физическое лицо | Individual / Natural person
- Mehnat shartnomasi | Трудовой договор | Employment contract
- Ma'muriy javobgarlik | Административная ответственность | Administrative liability
- Bazaviy hisoblash miqdori (BHM) | Базовая расчетная величина (БРВ) | Base Calculation Value (BCV)
- Kuchini yo'qotgan | Утратил силу | Repealed / Lost force
- Amalda | Действующий | In force
"""


class LegalLanguageComparator:
    """Translates legal provisions using official Lex.uz terminology and audits UZ vs RU/EN discrepancies."""

    def __init__(
        self,
        llm: LLMClient,
        fetcher: LexUzFetcher | None = None,
        bm25_store: BM25Store | None = None,
    ) -> None:
        self.llm = llm
        self.fetcher = fetcher
        self.bm25_store = bm25_store

    async def translate_and_compare(self, req: TranslationCompareRequest) -> TranslationCompareResponse:
        """Translate a provision and/or audit discrepancies across UZ, RU, and EN Lex.uz editions."""
        editions: dict[str, str] = {}
        urls_compared: dict[str, str] = {}

        if req.doc_id:
            editions, urls_compared = await self._load_multilingual_editions(req.doc_id, req.article)

        source_text = req.source_text
        source_lang = req.source_language

        if not source_text:
            # Pick best available edition as source
            if editions:
                preferred = next(
                    (k for k in ("uz_latn", "uz_cyrl", "ru", "en") if k in editions),
                    next(iter(editions.keys())),
                )
                source_text = editions[preferred]
                source_lang = Language(preferred)
            else:
                raise ValueError("Provide either `source_text` or a valid `doc_id` available on Lex.uz.")

        if source_lang is None:
            source_lang = detect_language(source_text)

        # Perform official-terminology legal translation
        translated_text = await self._translate_text(
            source_text=source_text,
            source_lang=source_lang,
            target_lang=req.target_language,
            official_target_edition=editions.get(req.target_language.value),
        )

        # Perform discrepancy audit against authoritative Uzbek text when multiple editions exist
        discrepancies: list[DiscrepancyItem] = []
        if req.verify_against_uz_primary:
            uz_text = editions.get("uz_latn") or editions.get("uz_cyrl")
            if not uz_text and source_lang in (Language.UZ_LATN, Language.UZ_CYRL):
                uz_text = source_text

            if uz_text:
                for lang_key in ("ru", "en"):
                    other_text = editions.get(lang_key)
                    if not other_text and req.target_language.value == lang_key:
                        other_text = translated_text
                    if other_text:
                        found = await self._audit_discrepancies(
                            uz_text=uz_text,
                            compared_text=other_text,
                            compared_lang=Language(lang_key),
                        )
                        discrepancies.extend(found)

        return TranslationCompareResponse(
            translated_text=translated_text,
            source_language=source_lang,
            target_language=req.target_language,
            doc_id=req.doc_id,
            urls_compared=urls_compared,
            discrepancies=discrepancies,
        )

    async def _load_multilingual_editions(
        self, doc_id: str, article: str | None = None
    ) -> tuple[dict[str, str], dict[str, str]]:
        """Retrieve UZ, RU, and EN text editions from local index and/or live Lex.uz."""
        editions: dict[str, str] = {}
        urls: dict[str, str] = {}

        if self.bm25_store:
            local_chunks = self.bm25_store.get_chunks_by_doc(doc_id, article=article)
            for chunk in local_chunks:
                lang_key = chunk.language.value
                editions[lang_key] = (editions.get(lang_key, "") + "\n\n" + chunk.text).strip()
                urls[lang_key] = chunk.url

        if self.fetcher:
            for lang in (Language.UZ_LATN, Language.RU, Language.EN):
                if lang.value in editions:
                    continue
                try:
                    fetched = await self.fetcher.fetch_document(doc_id, language=lang)
                    if fetched and fetched.raw_text:
                        text = self._extract_article_slice(fetched.raw_text, article) if article else fetched.raw_text
                        if text:
                            editions[fetched.metadata.language.value] = text[:12000]
                            urls[fetched.metadata.language.value] = fetched.metadata.url
                except Exception as exc:
                    logger.debug("Live fetch for doc %s (%s) skipped: %s", doc_id, lang.value, exc)

        return editions, urls

    @staticmethod
    def _extract_article_slice(full_text: str, article: str) -> str:
        import re

        num = re.sub(r"[^\d.-]", "", article)
        if not num:
            return full_text[:8000]
        pattern = re.compile(
            rf"(?:^|\n)\s*(?:{re.escape(num)}\s*-?\s*(?:modda|модда)|(?:Статья|Article)\s+{re.escape(num)})\b[\s\S]{{0,4500}}?(?=\n\s*(?:\d+\s*-?\s*(?:modda|модда)|(?:Статья|Article)\s+\d+)\b|\Z)",
            re.IGNORECASE,
        )
        m = pattern.search(full_text)
        return m.group(0).strip() if m else full_text[:6000]

    async def _translate_text(
        self,
        source_text: str,
        source_lang: Language,
        target_lang: Language,
        official_target_edition: str | None = None,
    ) -> str:
        if official_target_edition and not self.llm.is_mock:
            prompt = (
                f"You are an official legal translator for the Ministry of Justice of Uzbekistan (Lex.uz).\n"
                f"{OFFICIAL_LEGAL_GLOSSARY}\n"
                f"Source language: {source_lang.value}\nTarget language: {target_lang.value}\n\n"
                f"Source text:\n{source_text[:8000]}\n\n"
                f"Official Lex.uz target-language edition (for terminology alignment):\n{official_target_edition[:8000]}\n\n"
                "Provide an exact, faithful legal translation in the target language preserving article/clause numbering "
                "and using official Lex.uz terminology. Note any term where the official edition deviates from the source."
            )
        else:
            prompt = (
                f"You are an official legal translator specializing in Republic of Uzbekistan legislation (Lex.uz).\n"
                f"{OFFICIAL_LEGAL_GLOSSARY}\n"
                f"Translate the following legal text from {source_lang.value} to {target_lang.value}. "
                "Preserve exact article/clause numbering, legal modality (mandatory vs. permissive), "
                "deadlines, and monetary units (BHM/BCV/BRV). Never paraphrase away legal precision.\n\n"
                f"{source_text[:8000]}"
            )
        return await self.llm.complete(
            [
                {"role": "system", "content": "You produce authoritative legal translations of Uzbekistan statutes."},
                {"role": "user", "content": prompt},
            ]
        )

    async def _audit_discrepancies(
        self,
        uz_text: str,
        compared_text: str,
        compared_lang: Language,
    ) -> list[DiscrepancyItem]:
        if self.llm.is_mock:
            return []

        prompt = (
            "Compare the AUTHORITATIVE UZBEK legal text against the translated edition below.\n"
            "Identify ONLY genuine legal discrepancies (differences in obligations/shall vs may, "
            "deadlines, penalties, exceptions, defined scope, or missing clauses). Ignore pure stylistic wording.\n"
            "Return JSON: {\"discrepancies\": [{\"article_or_clause\": str, \"uzbek_authoritative_excerpt\": str, "
            "\"compared_excerpt\": str, \"severity\": \"critical|high|medium|low|info\", \"legal_impact\": str}]}\n\n"
            f"=== UZBEK AUTHORITATIVE TEXT ===\n{uz_text[:7000]}\n\n"
            f"=== {compared_lang.value.upper()} EDITION ===\n{compared_text[:7000]}"
        )
        data = await self.llm.complete_json(
            [
                {"role": "system", "content": "You are a comparative statutory interpretation expert in Uzbekistan law."},
                {"role": "user", "content": prompt},
            ],
            fallback={"discrepancies": []},
        )
        items: list[DiscrepancyItem] = []
        for raw in data.get("discrepancies", []):
            try:
                sev = RiskSeverity(str(raw.get("severity", "medium")).lower())
            except ValueError:
                sev = RiskSeverity.MEDIUM
            items.append(
                DiscrepancyItem(
                    article_or_clause=str(raw.get("article_or_clause", "General")),
                    uzbek_authoritative_excerpt=str(raw.get("uzbek_authoritative_excerpt", "")),
                    compared_language=compared_lang,
                    compared_excerpt=str(raw.get("compared_excerpt", "")),
                    severity=sev,
                    legal_impact=str(raw.get("legal_impact", "")),
                )
            )
        return items
