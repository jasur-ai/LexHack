"""Multi-hop Agentic Legal Reasoning Orchestrator with parallel retrieval, live thinking progress, streaming, and citation guard."""

from __future__ import annotations

import asyncio
import logging
import re
import time
from collections.abc import AsyncIterator
from datetime import date
from typing import Any

from lex_agent.config import Settings, get_settings
from lex_agent.language.comparator import LegalLanguageComparator
from lex_agent.language.transliterator import to_searchable_uzbek_latin
from lex_agent.llm.client import LLMClient
from lex_agent.models import (
    AgentQueryRequest,
    AgentResponse,
    AnswerSections,
    HopTrace,
    Language,
    RetrievalFilter,
    RetrievedChunk,
    SourceItem,
    TranslationCompareRequest,
)
from lex_agent.reasoning.answer_cache import AnswerCache, normalize_question
from lex_agent.reasoning.answer_composer import (
    build_concise_messages,
    compose_extractive_answer,
    parse_answer_sections,
    source_items,
)
from lex_agent.reasoning.citation_guard import CitationVerificationGuard
from lex_agent.reasoning.decomposer import LegalQueryDecomposer
from lex_agent.reasoning.norm_resolver import NormConflictResolver
from lex_agent.retrieval.hybrid_retriever import HybridLegalRetriever

logger = logging.getLogger(__name__)

_LANGUAGE_NAMES: dict[Language, str] = {
    Language.UZ_LATN: "Uzbek (Latin script / O'zbek lotin yozuvi)",
    Language.UZ_CYRL: "Uzbek (Cyrillic script / Ўзбек кирилл ёзуви)",
    Language.RU: "Russian (Русский язык)",
    Language.EN: "English",
}

_AGENT_TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "search_uzbekistan_law",
            "description": (
                "Search all Uzbekistan legislation indexed from Lex.uz (Constitution, Codes, Laws, Presidential "
                "Decrees/Resolutions, Cabinet Resolutions, Departmental Acts, Supreme Court Plenum) with live fallback."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Targeted legal search query in UZ, RU, or EN"},
                    "article_number": {"type": "string", "description": "Optional specific article number e.g. '168'"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "fetch_lex_document_by_id",
            "description": "Fetch a specific Lex.uz document by numeric ID or act number (e.g. O'RQ-682, PF-158) and optional article.",
            "parameters": {
                "type": "object",
                "properties": {
                    "doc_id": {"type": "string", "description": "Lex.uz numeric doc_id if known"},
                    "doc_number": {"type": "string", "description": "Official act number e.g. O'RQ-682, PF-158, VMQ-123"},
                    "article": {"type": "string", "description": "Specific article number to extract"},
                },
            },
        },
    },
]


class LegalAgentOrchestrator:
    """End-to-end zero-hallucination Uzbekistan Legal AI Agent with parallel multi-hop retrieval & SSE streaming."""

    def __init__(
        self,
        *,
        llm: LLMClient,
        retriever: HybridLegalRetriever,
        comparator: LegalLanguageComparator | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.llm = llm
        self.retriever = retriever
        self.comparator = comparator
        self.decomposer = LegalQueryDecomposer(llm)
        self.norm_resolver = NormConflictResolver()
        self.citation_guard = CitationVerificationGuard()
        self.cache = AnswerCache(max_items=self.settings.answer_cache_size, ttl_sec=self.settings.answer_cache_ttl_sec)

    async def answer(self, request: AgentQueryRequest) -> AgentResponse:
        """Execute full multi-hop legal reasoning and return the complete verified `AgentResponse`."""
        final_resp: AgentResponse | None = None
        async for event in self.answer_stream(request):
            if event.get("type") == "done":
                final_resp = event["response"]
        if final_resp is None:  # pragma: no cover - answer_stream always ends with "done"
            raise RuntimeError("The answer pipeline finished without a result")
        return final_resp

    def _cache_key(self, request: AgentQueryRequest, style: str) -> str | None:
        if request.compare_translations:
            return None
        return "|".join(
            [
                normalize_question(request.query),
                normalize_question(self._follow_up_context(request) or ""),
                request.response_language.value if request.response_language else "auto",
                style,
                request.as_of_date.isoformat() if request.as_of_date else "today",
                "rep" if request.include_repealed else "cur",
                self.llm.active_mode_label,
            ]
        )

    @staticmethod
    def _follow_up_context(request: AgentQueryRequest) -> str | None:
        """The previous question, when the current one is a short follow-up that needs it to be understood."""
        context = (request.context or "").strip()
        if not context or normalize_question(context) == normalize_question(request.query):
            return None
        return context if len(request.query.split()) <= 8 else None

    def _attach_article_leads(self, evidence: list[RetrievedChunk]) -> None:
        """For continuation parts of long articles, attach the article's opening text (part 1) for summaries."""
        wanted: dict[str, RetrievedChunk] = {}
        for item in evidence:
            cid = item.chunk.chunk_id
            m = re.match(r"^(.*)#(\d+)$", cid)
            if m and m.group(2) != "1":
                wanted[f"{m.group(1)}#1"] = item
        if not wanted:
            return
        try:
            firsts = self.retriever.bm25_store.get_chunks_by_ids(list(wanted))
        except Exception as exc:  # pragma: no cover - defensive
            logger.debug("Lead lookup failed: %s", exc)
            return
        for first_id, item in wanted.items():
            first = firsts.get(first_id)
            if first is not None:
                item.chunk.extra = {**(item.chunk.extra or {}), "lead_text": first.text.partition("\n")[2] or first.text}

    async def _stream_llm(self, messages: list[dict[str, str]], *, max_tokens: int) -> AsyncIterator[str]:
        """Stream tokens with a first-token deadline and an overall deadline (raises asyncio.TimeoutError)."""
        loop = asyncio.get_running_loop()
        deadline = loop.time() + self.settings.llm_request_timeout
        agen = self.llm.stream_complete(messages, max_tokens=max_tokens).__aiter__()
        first = True
        try:
            while True:
                remaining = deadline - loop.time()
                if remaining <= 0:
                    raise asyncio.TimeoutError("LLM overall deadline exceeded")
                timeout = min(self.settings.llm_first_token_timeout, remaining) if first else remaining
                try:
                    token = await asyncio.wait_for(agen.__anext__(), timeout=timeout)
                except StopAsyncIteration:
                    return
                first = False
                yield token
        finally:
            try:
                await agen.aclose()
            except Exception:  # pragma: no cover - best effort cleanup
                pass

    async def answer_stream(self, request: AgentQueryRequest) -> AsyncIterator[dict[str, Any]]:
        """Execute multi-hop legal reasoning while yielding live thinking steps, sources, streamed tokens and result."""
        t0 = time.perf_counter()
        style = request.answer_style or self.settings.answer_style_default
        concise = style == "concise"
        max_hops = request.max_hops or self.settings.agent_max_hops
        if concise:
            max_hops = min(max_hops, 2)

        def _elapsed_ms() -> int:
            return int((time.perf_counter() - t0) * 1000)

        cache_key = self._cache_key(request, style)
        cached: AgentResponse | None = self.cache.get(cache_key)
        if cached is not None:
            for step_no, label in enumerate(
                ["Savol tahlil qilindi", "Mos normalar topildi", "Havolalar tekshirildi", "Normalar saralandi"],
                start=1,
            ):
                yield {"type": "step", "step": step_no, "total": 5, "status": "done", "label": label, "elapsed_ms": _elapsed_ms()}
            yield {"type": "sources", "sources": [src.model_dump() for src in cached.sources]}
            yield {"type": "token", "text": cached.answer}
            yield {"type": "step", "step": 5, "total": 5, "status": "done", "label": "Tayyor (keshdan)", "elapsed_ms": _elapsed_ms()}
            response = cached.model_copy(update={"mode": "cache", "elapsed_ms": _elapsed_ms()})
            yield {"type": "done", "response": response, "elapsed_ms": _elapsed_ms()}
            return

        # STEP 1: Decompose query & detect language/branches/dates
        yield {
            "type": "step",
            "step": 1,
            "total": 5,
            "status": "running",
            "label": "Savol tahlil qilinmoqda (til, soha va moddalar)...",
            "elapsed_ms": _elapsed_ms(),
        }
        plan = await self.decomposer.decompose(request.query, explicit_as_of_date=request.as_of_date)
        response_lang = request.response_language or plan.detected_language
        effective_as_of = request.as_of_date or plan.as_of_date

        branches_str = ", ".join(b.value for b in plan.branches[:4])
        yield {
            "type": "step",
            "step": 1,
            "total": 5,
            "status": "done",
            "label": f"Savol tahlil qilindi ({response_lang.value} · soha: {branches_str})",
            "elapsed_ms": _elapsed_ms(),
        }

        base_filter = RetrievalFilter(
            as_of_date=effective_as_of,
            include_repealed=request.include_repealed or (effective_as_of is not None),
        )

        evidence_map: dict[str, RetrievedChunk] = {}
        hop_traces: list[HopTrace] = []

        # STEP 2: Hop 1 — Parallel multi-lingual hybrid retrieval
        yield {
            "type": "step",
            "step": 2,
            "total": 5,
            "status": "running",
            "label": "Qonunchilik bazasidan qidiruv bajarilmoqda...",
            "elapsed_ms": _elapsed_ms(),
        }

        follow_up_context = self._follow_up_context(request)
        hop1_queries: list[str] = [request.query]
        if follow_up_context:
            # "Muddatlar qanday?" alone matches nothing useful; searched together with the previous question it
            # lands in the right act and article.
            hop1_queries.insert(0, f"{follow_up_context} {request.query}")
        for sq in plan.sub_queries[:2]:
            hop1_queries.extend(sq.search_queries_uz[:1])
            hop1_queries.extend(sq.search_queries_ru[:1])
            hop1_queries.extend(sq.search_queries_en[:1])
        # Drop pure script variants of the question: the retriever already matches Latin <-> Cyrillic itself.
        seen_forms: set[str] = set()
        unique_queries: list[str] = []
        for q in hop1_queries:
            q = q.strip()
            form = to_searchable_uzbek_latin(q).lower()
            if q and form not in seen_forms:
                seen_forms.add(form)
                unique_queries.append(q)
        hop1_queries = unique_queries[:4]

        hop1_results = await asyncio.gather(
            *[
                self.retriever.retrieve(
                    q,
                    top_k=self.settings.agent_top_k,
                    rerank_top_k=self.settings.agent_rerank_top_k,
                    filters=base_filter,
                    hop=1,
                    enable_live_fallback=request.enable_live_lex and idx == 0,
                )
                for idx, q in enumerate(hop1_queries)
            ]
        )

        hop1_live_fetched: list[str] = []
        hop1_added = 0
        for q_idx, (hits, live_ids) in enumerate(hop1_results):
            hop1_live_fetched.extend(live_ids)
            for h in hits:
                if q_idx > 0:
                    # Secondary (transliterated / translated) queries support but never outrank the original wording
                    h.final_score *= 0.92
                if h.chunk.chunk_id not in evidence_map or h.final_score > evidence_map[h.chunk.chunk_id].final_score:
                    if h.chunk.chunk_id not in evidence_map:
                        hop1_added += 1
                    evidence_map[h.chunk.chunk_id] = h

        hop_traces.append(
            HopTrace(
                hop=1,
                queries=hop1_queries,
                live_lex_fetched=list(dict.fromkeys(hop1_live_fetched)),
                chunks_added=hop1_added,
            )
        )

        top_preview = ", ".join(
            dict.fromkeys(
                f"{(r.chunk.extra or {}).get('short_title') or r.chunk.doc_title[:36]} ({r.chunk.article or 'umumiy'})"
                for r in sorted(evidence_map.values(), key=lambda x: x.final_score, reverse=True)[:3]
            )
        )
        yield {
            "type": "step",
            "step": 2,
            "total": 5,
            "status": "done",
            "label": f"{hop1_added} ta mos norma topildi" + (f": {top_preview}" if top_preview else ""),
            "elapsed_ms": _elapsed_ms(),
        }

        # STEP 3: Multi-hop automatic cross-reference traversal (Hops 2..N)
        yield {
            "type": "step",
            "step": 3,
            "total": 5,
            "status": "running",
            "label": "Moddalararo havolalar tekshirilmoqda...",
            "elapsed_ms": _elapsed_ms(),
        }

        followed_ref_keys: set[tuple[str | None, str | None, str | None, str | None]] = set()
        total_refs_followed = 0
        for hop in range(2, max_hops + 1):
            pending_refs = []
            ranked_so_far = sorted(evidence_map.values(), key=lambda x: x.final_score, reverse=True)[:6]
            for item in ranked_so_far:
                for ref in item.chunk.cross_references:
                    key = (ref.target_doc_id, ref.target_doc_number, ref.target_doc_hint, ref.target_article)
                    if key not in followed_ref_keys and any(key):
                        followed_ref_keys.add(key)
                        pending_refs.append(ref)

            if not pending_refs:
                break

            batch_refs = pending_refs[:3]
            hop_ref_labels = [
                f"{r.target_doc_number or r.target_doc_hint or r.target_doc_id} (Art. {r.target_article or '?'})"
                for r in batch_refs
            ]
            ref_results = await asyncio.gather(
                *[
                    self.retriever.retrieve_exact_reference(
                        doc_id=ref.target_doc_id,
                        doc_number=ref.target_doc_number,
                        doc_hint=ref.target_doc_hint,
                        article=ref.target_article,
                        filters=base_filter,
                        hop=hop,
                        enable_live_fallback=False,
                    )
                    for ref in batch_refs
                ]
            )

            hop_added = 0
            hop_live: list[str] = []
            for ref_hits, live_ids in ref_results:
                hop_live.extend(live_ids)
                for h in ref_hits:
                    if h.chunk.chunk_id not in evidence_map:
                        # Slightly discount secondary cross-ref chunks so primary direct hits remain #1
                        h.final_score = min(h.final_score, 0.55)
                        evidence_map[h.chunk.chunk_id] = h
                        hop_added += 1

            total_refs_followed += len(batch_refs)
            hop_traces.append(
                HopTrace(
                    hop=hop,
                    queries=[],
                    cross_refs_followed=hop_ref_labels,
                    live_lex_fetched=list(dict.fromkeys(hop_live)),
                    chunks_added=hop_added,
                )
            )
            if hop_added == 0:
                break

        # Optional LLM tool-calling supplement (detailed mode only, and only if evidence is still very sparse)
        if not concise and not self.llm.is_mock and len(evidence_map) < 4 and max_hops >= 2:
            try:
                tool_added = await asyncio.wait_for(
                    self._run_tool_calling_supplement(
                        query=request.query,
                        evidence_map=evidence_map,
                        filters=base_filter,
                        enable_live_lex=request.enable_live_lex,
                    ),
                    timeout=self.settings.llm_first_token_timeout,
                )
            except Exception as exc:
                logger.info("Tool-calling supplement skipped: %s", exc)
                tool_added = 0
            if tool_added > 0:
                hop_traces.append(
                    HopTrace(
                        hop=len(hop_traces) + 1,
                        queries=["[LLM tool-calling targeted statutory lookup]"],
                        chunks_added=tool_added,
                    )
                )

        yield {
            "type": "step",
            "step": 3,
            "total": 5,
            "status": "done",
            "label": f"Havolalar tahlili yakunlandi ({total_refs_followed} ta havola tekshirildi)",
            "elapsed_ms": _elapsed_ms(),
        }

        # STEP 4: Norm conflict & temporal resolution + optional UZ/RU/EN comparison
        yield {
            "type": "step",
            "step": 4,
            "total": 5,
            "status": "running",
            "label": "Qonunlar iyerarxiyasi va amal qilish holati tekshirilmoqda...",
            "elapsed_ms": _elapsed_ms(),
        }

        ordered_evidence, conflict_resolutions, temporal_warnings = self.norm_resolver.resolve(
            list(evidence_map.values()),
            as_of_date=effective_as_of,
        )
        top_evidence = ordered_evidence[: (5 if concise else 6)]
        self._attach_article_leads(top_evidence)

        translation_warnings: list[str] = []
        if (request.compare_translations or plan.requires_translation_comparison) and self.comparator and top_evidence:
            primary_doc_id = top_evidence[0].chunk.doc_id
            primary_article = top_evidence[0].chunk.article
            try:
                comp = await asyncio.wait_for(
                    self.comparator.translate_and_compare(
                        TranslationCompareRequest(
                            doc_id=primary_doc_id,
                            article=primary_article,
                            target_language=response_lang,
                            verify_against_uz_primary=True,
                        )
                    ),
                    timeout=self.settings.llm_request_timeout,
                )
                for disc in comp.discrepancies:
                    translation_warnings.append(
                        f"TRANSLATION DISCREPANCY ({disc.article_or_clause}, {disc.severity.value.upper()}): "
                        f"{disc.legal_impact} (Authoritative Uzbek text prevails under Law O'RQ-682)."
                    )
            except Exception as exc:
                logger.debug("Translation comparison skipped: %s", exc)

        sources = [SourceItem(**item) for item in source_items(top_evidence)]
        yield {
            "type": "step",
            "step": 4,
            "total": 5,
            "status": "done",
            "label": f"{len(top_evidence)} ta eng aniq norma saralandi ({len(conflict_resolutions)} ta iyerarxiya qoidasi)",
            "elapsed_ms": _elapsed_ms(),
        }
        yield {"type": "sources", "sources": [src.model_dump() for src in sources]}

        # STEP 5: Stream grounded legal answer (LLM) or compose an extractive answer, then verify citations
        yield {
            "type": "step",
            "step": 5,
            "total": 5,
            "status": "running",
            "label": "Javob tayyorlanmoqda...",
            "elapsed_ms": _elapsed_ms(),
        }

        mode = "llm"
        answer_text = ""
        if self.llm.is_mock or not top_evidence:
            mode = "extractive"
            answer_text = compose_extractive_answer(
                query=request.query, response_lang=response_lang, evidence=top_evidence, branches=plan.branches
            )
            yield {"type": "token", "text": answer_text}
        else:
            if concise:
                messages = build_concise_messages(
                    query=request.query,
                    response_lang=response_lang,
                    evidence=top_evidence,
                    warnings=temporal_warnings + translation_warnings,
                    as_of_date=effective_as_of,
                    context=follow_up_context,
                )
                max_tokens = 1100
            else:
                messages = self._build_synthesis_messages(
                    query=request.query,
                    response_lang=response_lang,
                    evidence=top_evidence,
                    conflicts=conflict_resolutions,
                    temporal_warnings=temporal_warnings,
                    translation_warnings=translation_warnings,
                    as_of_date=effective_as_of,
                )
                max_tokens = self.settings.llm_max_tokens
            chunks_out: list[str] = []
            try:
                async for token in self._stream_llm(messages, max_tokens=max_tokens):
                    chunks_out.append(token)
                    yield {"type": "token", "text": token}
                answer_text = "".join(chunks_out).strip()
                if not answer_text:
                    raise RuntimeError("LLM returned an empty answer")
            except Exception as exc:
                logger.warning("LLM synthesis failed (%s: %s); falling back to extractive answer.", type(exc).__name__, exc)
                mode = "extractive"
                answer_text = compose_extractive_answer(
                    query=request.query, response_lang=response_lang, evidence=top_evidence, branches=plan.branches
                )
                yield {"type": "replace_answer", "text": answer_text, "mode": "extractive"}

        verification = self.citation_guard.verify(
            answer_text,
            top_evidence,
            temporal_warnings=temporal_warnings,
            translation_warnings=translation_warnings,
        )

        # Only invoke a self-correction pass (detailed mode) when fabricated references exist
        if (
            not concise
            and mode == "llm"
            and self.settings.agent_strict_citation_mode
            and not verification.passed
            and verification.confidence_score < 0.75
            and verification.unverified_references
        ):
            yield {
                "type": "step",
                "step": 5,
                "total": 5,
                "status": "running",
                "label": "Sitata nazorati: tasdiqlanmagan havolalar tozalanmoqda...",
                "elapsed_ms": _elapsed_ms(),
            }
            try:
                corrected = await asyncio.wait_for(
                    self._self_correct_answer(
                        draft_answer=answer_text,
                        unverified_refs=verification.unverified_references,
                        evidence=top_evidence,
                        response_lang=response_lang,
                    ),
                    timeout=self.settings.llm_request_timeout,
                )
                if corrected.strip():
                    answer_text = corrected.strip()
                    verification = self.citation_guard.verify(
                        answer_text,
                        top_evidence,
                        temporal_warnings=temporal_warnings,
                        translation_warnings=translation_warnings,
                    )
                    yield {"type": "replace_answer", "text": answer_text}
            except Exception as exc:
                logger.info("Self-correction skipped: %s", exc)

        sections: AnswerSections | None = None
        if concise:
            parsed = parse_answer_sections(answer_text)
            if not parsed["structured"]:
                parsed["answer"] = answer_text
            sections = AnswerSections(**parsed)

        yield {
            "type": "step",
            "step": 5,
            "total": 5,
            "status": "done",
            "label": f"Tayyor! Manbalar tekshirildi ({_elapsed_ms() / 1000:.1f}s)",
            "elapsed_ms": _elapsed_ms(),
        }

        response = AgentResponse(
            answer=answer_text,
            response_language=response_lang,
            query_plan=plan,
            citations=verification.verified_citations,
            verification=verification,
            conflict_resolutions=conflict_resolutions,
            hop_traces=hop_traces,
            evidence_count=len(top_evidence),
            as_of_date=effective_as_of,
            answer_style=style,
            sections=sections,
            sources=sources,
            mode=mode,
            elapsed_ms=_elapsed_ms(),
        )
        # Never cache a fallback produced by a transient LLM failure
        if mode == "llm" or self.llm.is_mock:
            self.cache.put(cache_key, response)
        yield {"type": "done", "response": response, "elapsed_ms": _elapsed_ms()}

    async def _run_tool_calling_supplement(
        self,
        *,
        query: str,
        evidence_map: dict[str, RetrievedChunk],
        filters: RetrievalFilter,
        enable_live_lex: bool,
    ) -> int:
        """Allow the LLM to invoke targeted statutory lookup tools if crucial norms are still missing."""
        brief_titles = "\n".join(
            f"- {r.chunk.doc_title} | {r.chunk.article or 'General'} ({r.chunk.url})"
            for r in list(evidence_map.values())[:6]
        )
        messages = [
            {
                "role": "system",
                "content": (
                    "You are verifying completeness of retrieved Uzbekistan legal norms before writing an answer. "
                    "If a critical cross-referenced Code, Law, Decree, or Article is clearly missing, call a tool to fetch it. "
                    "If the retrieved evidence is already sufficient, do NOT call any tools and reply 'SUFFICIENT'."
                ),
            },
            {
                "role": "user",
                "content": f"User Question: {query}\n\nCurrently Retrieved Norms:\n{brief_titles or '(none)'}",
            },
        ]
        try:
            turn = await self.llm.complete_with_tools(messages, _AGENT_TOOLS, fast=True)
        except Exception as exc:
            logger.debug("Tool-calling supplement skipped: %s", exc)
            return 0

        added = 0
        for call in turn.get("tool_calls", [])[:2]:
            name = call["name"]
            args = call["arguments"]
            if name == "search_uzbekistan_law" and args.get("query"):
                sub_flt = filters.model_copy(update={"article_number": args.get("article_number")})
                hits, _ = await self.retriever.retrieve(
                    str(args["query"]),
                    top_k=6,
                    rerank_top_k=3,
                    filters=sub_flt,
                    hop=3,
                    enable_live_fallback=enable_live_lex,
                )
            elif name == "fetch_lex_document_by_id":
                hits, _ = await self.retriever.retrieve_exact_reference(
                    doc_id=args.get("doc_id"),
                    doc_number=args.get("doc_number"),
                    article=args.get("article"),
                    filters=filters,
                    hop=3,
                    enable_live_fallback=enable_live_lex,
                )
            else:
                hits = []

            for h in hits:
                if h.chunk.chunk_id not in evidence_map:
                    evidence_map[h.chunk.chunk_id] = h
                    added += 1
        return added

    def _build_synthesis_messages(
        self,
        *,
        query: str,
        response_lang: Language,
        evidence: list[RetrievedChunk],
        conflicts: list[Any],
        temporal_warnings: list[str],
        translation_warnings: list[str],
        as_of_date: date | None,
    ) -> list[dict[str, str]]:
        evidence_block = self._format_evidence_context(evidence)
        conflict_block = "\n".join(f"- [{c.principle_applied.upper()}] {c.explanation}" for c in conflicts)
        warnings_block = "\n".join(f"- {w}" for w in (temporal_warnings + translation_warnings))

        system_prompt = (
            "You are an authoritative Senior Legal Counsel and Uzbekistan Legislation AI Agent grounded strictly in Lex.uz.\n"
            f"Respond ONLY in: {_LANGUAGE_NAMES[response_lang]}.\n\n"
            "ABSOLUTE ZERO-HALLUCINATION RULES:\n"
            "1. Base EVERY legal claim exclusively on the RETRIEVED LEX.UZ EVIDENCE provided below. IGNORE any retrieved excerpt that is clearly unrelated to the user's legal question.\n"
            "2. NEVER invent, guess, or recall from memory any article number, act number, penalty amount, or Lex.uz URL "
            "that does not appear in the retrieved evidence.\n"
            "3. Every legal rule stated MUST cite: Document Title, Official Number (if present), Adoption Date (if present), "
            "exact Article/Clause, Status (In Force / Amended / Repealed), and direct Lex.uz URL.\n"
            "4. If the retrieved evidence is incomplete or lacks a specific act, explicitly state what is verified from Lex.uz "
            "and what requires fetching additional acts.\n"
            "5. If any norm is marked REPEALED or NOT YET EFFECTIVE, explicitly warn the user and do not apply it as current law.\n"
            "6. If norms conflict, explicitly explain resolution via Uzbekistan's legal hierarchy (Constitution > Constitutional Law > "
            "Code > Law > Presidential Decree/Resolution > Cabinet Resolution > Departmental Act, per O'RQ-682).\n"
            "7. Structure your answer clearly with short headings, bullet points, exact numbers/percentages, and a practical conclusion."
        )

        user_prompt = (
            f"USER QUESTION:\n{query}\n\n"
            f"AS-OF DATE: {as_of_date.isoformat() if as_of_date else 'Current (Today)'}\n\n"
            f"RETRIEVED LEX.UZ EVIDENCE ({len(evidence)} excerpts):\n{evidence_block}\n\n"
            + (f"NORM HIERARCHY & CONFLICT RESOLUTIONS:\n{conflict_block}\n\n" if conflict_block else "")
            + (f"LIFECYCLE / TRANSLATION WARNINGS:\n{warnings_block}\n\n" if warnings_block else "")
            + "Provide a clear, structured, directly relevant legal answer with exact Lex.uz citations."
        )

        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

    async def _self_correct_answer(
        self,
        *,
        draft_answer: str,
        unverified_refs: list[str],
        evidence: list[RetrievedChunk],
        response_lang: Language,
    ) -> str:
        evidence_block = self._format_evidence_context(evidence)
        issues = "\n".join(f"- {u}" for u in unverified_refs)
        prompt = (
            "The Citation Verification Guard detected UNVERIFIED references in your draft answer:\n"
            f"{issues}\n\n"
            f"Rewrite the answer in {_LANGUAGE_NAMES[response_lang]} so that EVERY cited article, act number, and URL "
            "appears verbatim in the RETRIEVED LEX.UZ EVIDENCE below. Remove any unverified article/act citations or "
            "explicitly note that the specific provision was not retrieved in the current evidence pool.\n\n"
            f"DRAFT ANSWER:\n{draft_answer}\n\n"
            f"RETRIEVED LEX.UZ EVIDENCE:\n{evidence_block}"
        )
        return await self.llm.complete(
            [
                {"role": "system", "content": "You enforce strict zero-hallucination citation compliance."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.0,
        )

    @staticmethod
    def _format_evidence_context(evidence: list[RetrievedChunk]) -> str:
        if not evidence:
            return "(No matching Lex.uz documents were found in the local index or live fetch.)"
        blocks: list[str] = []
        for idx, item in enumerate(evidence, start=1):
            c = item.chunk
            blocks.append(
                f"[EVIDENCE #{idx}]\n"
                f"Document: {c.doc_title}\n"
                f"Doc ID: {c.doc_id} | Act No: {c.doc_number or 'N/A'} | Type: {c.doc_type.value} (Rank {c.legal_force_rank})\n"
                f"Dates: Adopted={c.adoption_date or 'N/A'}, Effective={c.effective_date or 'N/A'}, Expiry={c.expiry_date or 'None'}\n"
                f"Status: {c.status.value.upper()} | Language: {c.language.value} | Path: {c.hierarchical_path}\n"
                f"URL: {c.citation_url}\n"
                f"Excerpt:\n{c.text[:1100]}\n"
            )
        return "\n---\n".join(blocks)
