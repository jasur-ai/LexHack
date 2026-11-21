"""Qdrant dense vector store with metadata, hierarchy, and temporal filtering (local, memory, or remote)."""

from __future__ import annotations

import logging
import uuid
from datetime import date

from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

from lex_agent.config import Settings, get_settings
from lex_agent.llm.client import EmbeddingClient
from lex_agent.models import LegalChunk, NormStatus, RetrievalFilter, RetrievedChunk
from lex_agent.retrieval.bm25_store import chunk_matches_filter

logger = logging.getLogger(__name__)


def _date_to_ordinal(d: date | None) -> int | None:
    return d.toordinal() if d is not None else None


def _chunk_id_to_uuid(chunk_id: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"lex.uz:{chunk_id}"))


class QdrantVectorStore:
    """Dense semantic vector store backed by Qdrant with multilingual embeddings and legal metadata filters."""

    def __init__(
        self,
        embedder: EmbeddingClient,
        settings: Settings | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.embedder = embedder
        self.collection_name = self.settings.qdrant_collection
        self._client: QdrantClient | None = None
        self._initialized = False

    @property
    def enabled(self) -> bool:
        """Dense search is meaningful only with real neural embeddings (hash vectors are random noise)."""
        mode = self.settings.vector_search_mode
        if mode == "off":
            return False
        if mode == "on":
            return True
        return not self.embedder.is_hash_fallback

    def _get_client(self) -> QdrantClient:
        if self._client is None:
            mode = self.settings.qdrant_mode
            if mode == "memory":
                self._client = QdrantClient(":memory:")
            elif mode == "local":
                self.settings.qdrant_path.mkdir(parents=True, exist_ok=True)
                self._client = QdrantClient(path=str(self.settings.qdrant_path))
            else:
                self._client = QdrantClient(
                    url=self.settings.qdrant_url,
                    api_key=self.settings.qdrant_api_key or None,
                    timeout=30.0,
                )
        return self._client

    def _ensure_collection(self, vector_dim: int) -> None:
        client = self._get_client()
        if self._initialized:
            return
        if not client.collection_exists(self.collection_name):
            logger.info("Creating Qdrant collection '%s' (dim=%d)", self.collection_name, vector_dim)
            client.create_collection(
                collection_name=self.collection_name,
                vectors_config=qmodels.VectorParams(size=vector_dim, distance=qmodels.Distance.COSINE),
            )
        self._initialized = True

    async def upsert_chunks(self, chunks: list[LegalChunk]) -> int:
        """Embed and upsert a batch of `LegalChunk` records into Qdrant."""
        if not chunks or not self.enabled:
            return 0

        texts = [
            f"{c.doc_title} | {c.hierarchical_path}\n{c.text[:2400]}"
            for c in chunks
        ]
        vectors = await self.embedder.embed_texts(texts)
        if not vectors:
            return 0

        self._ensure_collection(len(vectors[0]))
        points = []
        for chunk, vec in zip(chunks, vectors):
            payload = {
                "chunk_id": chunk.chunk_id,
                "doc_id": chunk.doc_id,
                "canonical_id": chunk.canonical_id,
                "language": chunk.language.value,
                "doc_type": chunk.doc_type.value,
                "doc_number": chunk.doc_number or "",
                "status": chunk.status.value,
                "legal_force_rank": chunk.legal_force_rank,
                "branches": [b.value for b in chunk.branches],
                "effective_ord": _date_to_ordinal(chunk.effective_date),
                "expiry_ord": _date_to_ordinal(chunk.expiry_date),
                "article": chunk.article or "",
                "chunk_json": chunk.model_dump_json(),
            }
            points.append(
                qmodels.PointStruct(
                    id=_chunk_id_to_uuid(chunk.chunk_id),
                    vector=vec,
                    payload=payload,
                )
            )

        client = self._get_client()
        client.upsert(collection_name=self.collection_name, points=points, wait=True)
        return len(points)

    async def search(
        self,
        query: str,
        *,
        top_k: int = 12,
        filters: RetrievalFilter | None = None,
    ) -> list[RetrievedChunk]:
        """Execute semantic vector search with Qdrant payload filters and post-verification."""
        if not self.enabled:
            return []
        client = self._get_client()
        if not client.collection_exists(self.collection_name):
            return []

        q_vec = await self.embedder.embed_query(query)
        q_filter = self._build_qdrant_filter(filters)

        try:
            response = client.query_points(
                collection_name=self.collection_name,
                query=q_vec,
                query_filter=q_filter,
                limit=top_k * 2,
                with_payload=True,
            )
            hits = response.points
        except Exception as exc:
            logger.warning("Qdrant search failed: %s", exc)
            return []

        results: list[RetrievedChunk] = []
        for pt in hits:
            payload = pt.payload or {}
            raw_json = payload.get("chunk_json")
            if not raw_json:
                continue
            chunk = LegalChunk.model_validate_json(raw_json)
            if not chunk_matches_filter(chunk, filters):
                continue
            score = float(pt.score or 0.0)
            results.append(
                RetrievedChunk(
                    chunk=chunk,
                    dense_score=score,
                    final_score=score,
                    retrieval_source="dense",
                )
            )
            if len(results) >= top_k:
                break
        return results

    @staticmethod
    def _build_qdrant_filter(flt: RetrievalFilter | None) -> qmodels.Filter | None:
        if flt is None:
            return None
        must: list[qmodels.Condition] = []
        must_not: list[qmodels.Condition] = []

        if flt.languages:
            must.append(
                qmodels.FieldCondition(
                    key="language",
                    match=qmodels.MatchAny(any=[l.value for l in flt.languages]),
                )
            )
        if flt.doc_types:
            must.append(
                qmodels.FieldCondition(
                    key="doc_type",
                    match=qmodels.MatchAny(any=[d.value for d in flt.doc_types]),
                )
            )
        if flt.min_legal_force_rank is not None:
            must.append(
                qmodels.FieldCondition(
                    key="legal_force_rank",
                    range=qmodels.Range(gte=flt.min_legal_force_rank),
                )
            )
        if flt.doc_ids:
            must.append(
                qmodels.FieldCondition(
                    key="doc_id",
                    match=qmodels.MatchAny(any=flt.doc_ids),
                )
            )
        if flt.as_of_date is None and not flt.include_repealed:
            must_not.append(
                qmodels.FieldCondition(
                    key="status",
                    match=qmodels.MatchValue(value=NormStatus.REPEALED.value),
                )
            )

        if not must and not must_not:
            return None
        return qmodels.Filter(must=must or None, must_not=must_not or None)

    def count(self) -> int:
        if not self.enabled and self._client is None:
            return 0
        client = self._get_client()
        if not client.collection_exists(self.collection_name):
            return 0
        return int(client.count(collection_name=self.collection_name).count)

    def close(self) -> None:
        """Close Qdrant client cleanly before Python interpreter shutdown."""
        if self._client is not None:
            try:
                self._client.close()
            except Exception:
                pass
            self._client = None
            self._initialized = False
