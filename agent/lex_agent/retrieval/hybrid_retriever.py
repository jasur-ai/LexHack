"""Hybrid legal retriever combining SQLite FTS5 BM25, Qdrant dense vectors, RRF fusion, reranking, and smart live Lex.uz fallback."""

from __future__ import annotations

import asyncio
import logging
import re
import time
from typing import TYPE_CHECKING

from lex_agent.config import Settings, get_settings
from lex_agent.language.transliterator import detect_language
from lex_agent.models import Language, RetrievalFilter, RetrievedChunk
from lex_agent.retrieval.bm25_store import BM25Store, chunk_matches_filter
from lex_agent.retrieval.query_expansion import expand_query
from lex_agent.retrieval.reranker import LegalReranker
from lex_agent.retrieval.vector_store import QdrantVectorStore

if TYPE_CHECKING:
    from lex_agent.ingestion.pipeline import IngestionPipeline

logger = logging.getLogger(__name__)

LIVE_CIRCUIT_COOLDOWN_SEC = 300


class HybridLegalRetriever:
    """Fast hybrid search: FTS5 BM25 + Qdrant Dense + RRF + Reranker + conditional Live Lex.uz fallback."""

    def __init__(
        self,
        *,
        bm25_store: BM25Store,
        vector_store: QdrantVectorStore,
        reranker: LegalReranker,
        ingestion_pipeline: IngestionPipeline | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.bm25_store = bm25_store
        self.vector_store = vector_store
        self.reranker = reranker
        self.ingestion_pipeline = ingestion_pipeline
        self._live_circuit_open_until = 0.0

    async def retrieve(
        self,
        query: str,
        *,
        top_k: int | None = None,
        rerank_top_k: int | None = None,
        filters: RetrievalFilter | None = None,
        hop: int = 1,
        enable_live_fallback: bool | None = None,
        live_fetch_limit: int = 2,
    ) -> tuple[list[RetrievedChunk], list[str]]:
        """Run fast hybrid search and conditionally augment live from Lex.uz only when local recall is genuinely weak."""
        top_k = top_k or self.settings.agent_top_k
        rerank_top_k = rerank_top_k or self.settings.agent_rerank_top_k
        # The global switch always wins: a request may opt out of live lookups but never force them on.
        use_live = self.settings.lex_uz_enable_live_fallback and (
            True if enable_live_fallback is None else enable_live_fallback
        )

        expansions = expand_query(query)
        fused = await self._hybrid_search_once(query, top_k=top_k, filters=filters, hop=hop, expansions=expansions)
        live_fetched_ids: list[str] = []

        # Only spend network time hitting live Lex.uz if local corpus has < 2 decent matches,
        # and cap live network lookup tightly so an external timeout never stalls answering.
        strong_local = [r for r in fused if r.bm25_score >= 1.5 or r.dense_score >= 0.45]
        should_try_live = (
            use_live
            and self.ingestion_pipeline is not None
            and len(strong_local) < 2
            and time.monotonic() >= self._live_circuit_open_until
        )
        if should_try_live:
            try:
                live_fetched_ids = await asyncio.wait_for(
                    self._augment_from_live_lex(query, filters=filters, limit=live_fetch_limit),
                    timeout=self.settings.lex_uz_live_fallback_timeout,
                )
            except Exception as exc:
                # Circuit breaker: when Lex.uz is slow/unreachable, stop paying the timeout on every question.
                self._live_circuit_open_until = time.monotonic() + LIVE_CIRCUIT_COOLDOWN_SEC
                logger.info(
                    "Live Lex.uz quick-fallback skipped (%s); local corpus only for the next %ss.",
                    exc.__class__.__name__,
                    LIVE_CIRCUIT_COOLDOWN_SEC,
                )
                live_fetched_ids = []
            if live_fetched_ids:
                fused = await self._hybrid_search_once(
                    query, top_k=top_k, filters=filters, hop=hop, expansions=expansions
                )

        rerank_query = " ".join([query, *expansions]) if expansions else query
        reranked = self.reranker.rerank(rerank_query, fused, top_k=max(rerank_top_k * 2, rerank_top_k + 4))
        ranked = self._prefer_language_and_dedupe(query, reranked)[:rerank_top_k]
        for item in ranked:
            item.retrieval_hop = hop
        return ranked, live_fetched_ids

    @staticmethod
    def _article_key(item: RetrievedChunk) -> tuple[str, str]:
        art = item.chunk.article or ""
        m = re.search(r"(\d+(?:[.-]\d+)?)", art)
        return item.chunk.canonical_id, (m.group(1) if m else art or item.chunk.chunk_id)

    def _prefer_language_and_dedupe(self, query: str, items: list[RetrievedChunk]) -> list[RetrievedChunk]:
        """Prefer norms in the asker's language and keep one chunk per (act, article) across editions."""
        if not items:
            return items
        q_lang = detect_language(query)
        for item in items:
            c_lang = item.chunk.language
            if q_lang == Language.RU:
                factor = 1.0 if c_lang == Language.RU else 0.82
            elif q_lang in (Language.UZ_LATN, Language.UZ_CYRL):
                factor = 1.0 if c_lang in (Language.UZ_LATN, Language.UZ_CYRL) else 0.8
            else:
                factor = 1.0
            item.final_score *= factor
        items.sort(key=lambda r: r.final_score, reverse=True)
        seen: set[tuple[str, str]] = set()
        out: list[RetrievedChunk] = []
        for item in items:
            key = self._article_key(item)
            if key in seen:
                continue
            seen.add(key)
            out.append(item)
        return out

    async def retrieve_exact_reference(
        self,
        *,
        doc_id: str | None = None,
        doc_number: str | None = None,
        doc_hint: str | None = None,
        article: str | None = None,
        filters: RetrievalFilter | None = None,
        hop: int = 2,
        enable_live_fallback: bool = True,
    ) -> tuple[list[RetrievedChunk], list[str]]:
        """Pinpoint retrieval for multi-hop cross-reference resolution (exact doc ID / act number / article)."""
        live_fetched: list[str] = []
        chunks = []

        if doc_id:
            chunks = self.bm25_store.get_chunks_by_doc(doc_id, article=article, limit=6)
            if not chunks and enable_live_fallback and self.ingestion_pipeline:
                try:
                    res = await self.ingestion_pipeline.ingest_lex_doc(doc_id, fetch_all_languages=False)
                    if res.get("chunks_indexed", 0) > 0:
                        live_fetched.append(doc_id)
                        chunks = self.bm25_store.get_chunks_by_doc(doc_id, article=article, limit=6)
                except Exception as exc:
                    logger.debug("Live cross-ref fetch for doc_id=%s failed: %s", doc_id, exc)

        if not chunks and doc_number:
            chunks = self.bm25_store.find_by_doc_number(doc_number, article=article, limit=6)

        if chunks:
            filtered = [c for c in chunks if chunk_matches_filter(c, filters)]
            if filtered:
                return (
                    [
                        RetrievedChunk(
                            chunk=c,
                            bm25_score=10.0,
                            rrf_score=0.5,
                            final_score=0.65,
                            retrieval_hop=hop,
                            retrieval_source="cross_ref_exact",
                        )
                        for c in filtered[:3]
                    ],
                    live_fetched,
                )

        # Fallback to targeted local FTS5 + hybrid query (disable live fetch on speculative hops for speed)
        q_parts = [p for p in (doc_number, doc_hint, f"{article}-modda" if article else None) if p]
        if not q_parts:
            return [], live_fetched
        query = " ".join(q_parts)
        return await self.retrieve(
            query,
            top_k=5,
            rerank_top_k=2,
            filters=filters,
            hop=hop,
            enable_live_fallback=False,
        )

    async def _hybrid_search_once(
        self,
        query: str,
        *,
        top_k: int,
        filters: RetrievalFilter | None,
        hop: int,
        expansions: list[str] | None = None,
    ) -> list[RetrievedChunk]:
        # 1. Instant SQLite FTS5 BM25 search for the question and its statutory re-phrasings
        lexical_lists = [self.bm25_store.search(query, top_k=top_k, filters=filters)]
        for exp in expansions or []:
            lexical_lists.append(self.bm25_store.search(exp, top_k=top_k, filters=filters))
        bm25_hits = self._fuse_lexical(lexical_lists) if len(lexical_lists) > 1 else lexical_lists[0]

        # 2. Dense vector search only when real neural embeddings are configured (hash vectors are noise)
        if self.vector_store.enabled:
            dense_hits = await self.vector_store.search(query, top_k=top_k, filters=filters)
        else:
            dense_hits = []

        return self._reciprocal_rank_fusion(
            dense_hits,
            bm25_hits,
            k=60,
            hop=hop,
            dense_weight=1.0,
            bm25_weight=1.4,
        )

    @staticmethod
    def _fuse_lexical(lists: list[list[RetrievedChunk]], k: int = 30) -> list[RetrievedChunk]:
        """Reciprocal-rank fuse several BM25 result lists (original question + expansions)."""
        merged: dict[str, tuple[float, RetrievedChunk]] = {}
        for weight, hits in zip([1.0] + [1.15] * (len(lists) - 1), lists):
            for rank, item in enumerate(hits, start=1):
                score = weight / (k + rank)
                cid = item.chunk.chunk_id
                if cid in merged:
                    prev_score, prev = merged[cid]
                    prev.bm25_score = max(prev.bm25_score, item.bm25_score)
                    merged[cid] = (prev_score + score, prev)
                else:
                    merged[cid] = (score, item)
        ordered = sorted(merged.values(), key=lambda x: x[0], reverse=True)
        return [item for _, item in ordered]

    @staticmethod
    def _reciprocal_rank_fusion(
        dense_hits: list[RetrievedChunk],
        bm25_hits: list[RetrievedChunk],
        *,
        k: int = 60,
        hop: int = 1,
        dense_weight: float = 1.0,
        bm25_weight: float = 1.4,
    ) -> list[RetrievedChunk]:
        merged: dict[str, RetrievedChunk] = {}

        for rank, item in enumerate(dense_hits, start=1):
            cid = item.chunk.chunk_id
            rrf = dense_weight / (k + rank)
            if cid not in merged:
                merged[cid] = item.model_copy(
                    update={"rrf_score": rrf, "final_score": rrf, "retrieval_hop": hop, "retrieval_source": "hybrid"}
                )
            else:
                merged[cid].dense_score = max(merged[cid].dense_score, item.dense_score)
                merged[cid].rrf_score += rrf
                merged[cid].final_score = merged[cid].rrf_score

        for rank, item in enumerate(bm25_hits, start=1):
            cid = item.chunk.chunk_id
            rrf = bm25_weight / (k + rank)
            if cid not in merged:
                merged[cid] = item.model_copy(
                    update={"rrf_score": rrf, "final_score": rrf, "retrieval_hop": hop, "retrieval_source": "hybrid"}
                )
            else:
                merged[cid].bm25_score = max(merged[cid].bm25_score, item.bm25_score)
                merged[cid].rrf_score += rrf
                merged[cid].final_score = merged[cid].rrf_score

        fused = list(merged.values())
        fused.sort(key=lambda r: r.rrf_score, reverse=True)
        return fused

    async def _augment_from_live_lex(
        self,
        query: str,
        *,
        filters: RetrievalFilter | None,
        limit: int = 2,
    ) -> list[str]:
        assert self.ingestion_pipeline is not None
        lang = detect_language(query)
        try:
            res = await self.ingestion_pipeline.ingest_lex_search(
                query,
                language=lang,
                limit=limit,
                fetch_all_languages=False,
            )
            return list(res.get("ingested_doc_ids", []))
        except Exception as exc:
            logger.warning("Live Lex.uz augmentation skipped for '%s': %s", query[:80], exc)
            return []
