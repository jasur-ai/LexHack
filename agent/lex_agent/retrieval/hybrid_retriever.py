"""Hybrid legal retriever combining SQLite FTS5 BM25, Qdrant dense vectors, RRF fusion, reranking, and smart live Lex.uz fallback."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from lex_agent.config import Settings, get_settings
from lex_agent.language.transliterator import detect_language
from lex_agent.models import RetrievalFilter, RetrievedChunk
from lex_agent.retrieval.bm25_store import BM25Store, chunk_matches_filter
from lex_agent.retrieval.reranker import LegalReranker
from lex_agent.retrieval.vector_store import QdrantVectorStore

if TYPE_CHECKING:
    from lex_agent.ingestion.pipeline import IngestionPipeline

logger = logging.getLogger(__name__)


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
        use_live = (
            self.settings.lex_uz_enable_live_fallback
            if enable_live_fallback is None
            else enable_live_fallback
        )

        fused = await self._hybrid_search_once(query, top_k=top_k, filters=filters, hop=hop)
        live_fetched_ids: list[str] = []

        # Only spend network time hitting live Lex.uz if local corpus has < 2 decent matches,
        # and cap live network lookup tightly so an external timeout never stalls answering.
        strong_local = [r for r in fused if r.bm25_score >= 1.5 or r.dense_score >= 0.45]
        should_try_live = use_live and self.ingestion_pipeline is not None and len(strong_local) < 2
        if should_try_live:
            try:
                import asyncio

                live_fetched_ids = await asyncio.wait_for(
                    self._augment_from_live_lex(query, filters=filters, limit=live_fetch_limit),
                    timeout=7.0,
                )
            except Exception as exc:
                logger.info("Live Lex.uz quick-fallback skipped (%s); answering from local corpus.", exc)
                live_fetched_ids = []
            if live_fetched_ids:
                fused = await self._hybrid_search_once(query, top_k=top_k, filters=filters, hop=hop)

        reranked = self.reranker.rerank(query, fused, top_k=rerank_top_k)
        for item in reranked:
            item.retrieval_hop = hop
        return reranked, live_fetched_ids

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
    ) -> list[RetrievedChunk]:
        # 1. Instant SQLite FTS5 BM25 search (<5ms even on 100k chunks!)
        bm25_hits = self.bm25_store.search(query, top_k=top_k, filters=filters)

        # 2. Dense vector search: skip slow local-mode brute-force scan when using hash embeddings
        # and FTS5 already found strong exact matches; always run dense when real neural embeddings are active!
        use_hash = self.vector_store.embedder.is_hash_fallback
        skip_slow_hash_scan = (
            use_hash
            and self.settings.qdrant_mode == "local"
            and len(bm25_hits) >= min(top_k, 6)
        )
        if skip_slow_hash_scan:
            dense_hits: list[RetrievedChunk] = []
        else:
            dense_hits = await self.vector_store.search(query, top_k=top_k, filters=filters)

        return self._reciprocal_rank_fusion(
            dense_hits,
            bm25_hits,
            k=60,
            hop=hop,
            dense_weight=0.35 if use_hash else 1.0,
            bm25_weight=1.4,
        )

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
