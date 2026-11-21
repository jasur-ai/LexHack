"""End-to-end ingestion pipeline with cross-lingual UZ/RU/EN document registry and hybrid indexing."""

from __future__ import annotations

import json
import logging
import sqlite3
from pathlib import Path
from typing import TYPE_CHECKING, Any

from lex_agent.config import Settings, get_settings
from lex_agent.ingestion.corpora import iter_huggingface_corpus, iter_local_jsonl_or_parquet
from lex_agent.ingestion.lex_fetcher import FetchedDocument, LexUzFetcher
from lex_agent.ingestion.multi_source import (
    ALL_UZBEKISTAN_CODES_LEX_IDS,
    build_foundational_reference_pack,
    build_uploaded_knowledge_document,
    fetch_external_legal_url,
)
from lex_agent.ingestion.parser import LegalDocumentParser
from lex_agent.models import DocumentMetadata, DocumentType, Language, LegalChunk

if TYPE_CHECKING:
    from lex_agent.retrieval.bm25_store import BM25Store
    from lex_agent.retrieval.vector_store import QdrantVectorStore

logger = logging.getLogger(__name__)

# Complete foundational Uzbekistan Constitution, all 18 Codes & organic laws on Lex.uz
CORE_UZBEKISTAN_LEX_IDS: dict[str, str] = ALL_UZBEKISTAN_CODES_LEX_IDS


class DocumentRegistry:
    """SQLite registry linking UZ (Latin/Cyrillic), RU, and EN Lex.uz editions under shared canonical IDs."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS documents (
                    doc_id TEXT NOT NULL,
                    language TEXT NOT NULL,
                    canonical_id TEXT NOT NULL,
                    doc_number TEXT,
                    title TEXT NOT NULL,
                    doc_type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    legal_force_rank INTEGER NOT NULL,
                    adoption_date TEXT,
                    effective_date TEXT,
                    expiry_date TEXT,
                    url TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    PRIMARY KEY (doc_id, language)
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_docs_canonical ON documents(canonical_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_docs_number ON documents(doc_number)")

    def upsert(self, meta: DocumentMetadata) -> DocumentMetadata:
        """Register or update a document and auto-link cross-lingual editions sharing canonical_id or doc_number."""
        with self._connect() as conn:
            # Find existing cross-lingual siblings
            siblings: list[sqlite3.Row] = []
            if meta.doc_number:
                siblings = conn.execute(
                    "SELECT * FROM documents WHERE canonical_id = ? OR doc_number = ?",
                    (meta.canonical_id, meta.doc_number),
                ).fetchall()
            else:
                siblings = conn.execute(
                    "SELECT * FROM documents WHERE canonical_id = ?",
                    (meta.canonical_id,),
                ).fetchall()

            if siblings:
                # Adopt canonical_id from existing group so UZ/RU/EN stay unified
                meta.canonical_id = siblings[0]["canonical_id"]
                for row in siblings:
                    meta.linked_doc_ids.setdefault(row["language"], row["doc_id"])
                    meta.linked_urls.setdefault(row["language"], row["url"])

            meta.linked_doc_ids[meta.language.value] = meta.doc_id
            meta.linked_urls[meta.language.value] = meta.url

            conn.execute(
                """
                INSERT OR REPLACE INTO documents (
                    doc_id, language, canonical_id, doc_number, title, doc_type,
                    status, legal_force_rank, adoption_date, effective_date,
                    expiry_date, url, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    meta.doc_id,
                    meta.language.value,
                    meta.canonical_id,
                    meta.doc_number,
                    meta.title,
                    meta.doc_type.value,
                    meta.status.value,
                    meta.legal_force_rank,
                    meta.adoption_date.isoformat() if meta.adoption_date else None,
                    meta.effective_date.isoformat() if meta.effective_date else None,
                    meta.expiry_date.isoformat() if meta.expiry_date else None,
                    meta.url,
                    meta.model_dump_json(),
                ),
            )
        return meta

    def get_linked_editions(self, doc_id: str) -> list[DocumentMetadata]:
        """Return all indexed language editions (UZ/RU/EN) linked to `doc_id`."""
        with self._connect() as conn:
            row = conn.execute("SELECT canonical_id FROM documents WHERE doc_id = ? LIMIT 1", (doc_id,)).fetchone()
            if not row:
                return []
            rows = conn.execute(
                "SELECT metadata_json FROM documents WHERE canonical_id = ?",
                (row["canonical_id"],),
            ).fetchall()
            return [DocumentMetadata.model_validate_json(r["metadata_json"]) for r in rows]

    def stats(self) -> dict[str, Any]:
        with self._connect() as conn:
            total = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
            by_lang = dict(
                conn.execute("SELECT language, COUNT(*) FROM documents GROUP BY language").fetchall()
            )
            by_type = dict(
                conn.execute("SELECT doc_type, COUNT(*) FROM documents GROUP BY doc_type").fetchall()
            )
            by_status = dict(
                conn.execute("SELECT status, COUNT(*) FROM documents GROUP BY status").fetchall()
            )
        return {
            "total_documents": total,
            "by_language": by_lang,
            "by_type": by_type,
            "by_status": by_status,
        }


class IngestionPipeline:
    """Coordinates live Lex.uz ingestion, offline HF corpora bootstrap, parsing, and dual-index storage."""

    def __init__(
        self,
        *,
        bm25_store: BM25Store,
        vector_store: QdrantVectorStore,
        fetcher: LexUzFetcher | None = None,
        parser: LegalDocumentParser | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.bm25_store = bm25_store
        self.vector_store = vector_store
        self.fetcher = fetcher or LexUzFetcher(self.settings)
        self.parser = parser or LegalDocumentParser()
        self.registry = DocumentRegistry(self.settings.doc_registry_path)

    async def index_fetched_document(self, fetched: FetchedDocument) -> int:
        """Register metadata, parse hierarchical chunks, and index into BM25 + Qdrant."""
        meta = self.registry.upsert(fetched.metadata)
        chunks = self.parser.parse_to_chunks(
            meta,
            fetched.raw_text,
            html_links=fetched.html_links,
            article_anchors=fetched.article_anchors,
        )
        if not chunks:
            return 0
        await self._store_chunks(chunks)
        return len(chunks)

    async def _store_chunks(self, chunks: list[LegalChunk]) -> None:
        self.bm25_store.upsert_chunks(chunks)
        await self.vector_store.upsert_chunks(chunks)

    async def ingest_lex_doc(
        self,
        doc_id: str,
        *,
        fetch_all_languages: bool = True,
        language: Language = Language.UZ_LATN,
    ) -> dict[str, Any]:
        """Fetch a document live from Lex.uz (optionally across UZ/RU/EN) and index it."""
        indexed_docs = 0
        indexed_chunks = 0
        languages_indexed: list[str] = []

        if fetch_all_languages:
            docs_map = await self.fetcher.fetch_all_languages(doc_id)
            for lang, fetched in docs_map.items():
                count = await self.index_fetched_document(fetched)
                if count > 0:
                    indexed_docs += 1
                    indexed_chunks += count
                    languages_indexed.append(lang.value)
        else:
            fetched = await self.fetcher.fetch_document(doc_id, language=language)
            if fetched:
                count = await self.index_fetched_document(fetched)
                if count > 0:
                    indexed_docs = 1
                    indexed_chunks = count
                    languages_indexed.append(fetched.metadata.language.value)

        return {
            "doc_id": doc_id,
            "documents_indexed": indexed_docs,
            "chunks_indexed": indexed_chunks,
            "languages": languages_indexed,
        }

    async def ingest_lex_search(
        self,
        query: str,
        *,
        language: Language = Language.UZ_LATN,
        limit: int = 5,
        fetch_all_languages: bool = False,
    ) -> dict[str, Any]:
        """Search Lex.uz live and ingest the top matching normative-legal acts."""
        hits = await self.fetcher.search(query, language=language, limit=limit)
        total_chunks = 0
        ingested_ids: list[str] = []
        for hit in hits:
            res = await self.ingest_lex_doc(
                hit.doc_id,
                fetch_all_languages=fetch_all_languages,
                language=hit.language,
            )
            if res["chunks_indexed"] > 0:
                total_chunks += res["chunks_indexed"]
                ingested_ids.append(hit.doc_id)
        return {
            "query": query,
            "hits_found": len(hits),
            "ingested_doc_ids": ingested_ids,
            "chunks_indexed": total_chunks,
        }

    async def ingest_huggingface_corpus(
        self,
        dataset_name: str = "Alii2004/lexuz-legislation",
        *,
        split: str = "train",
        max_docs: int | None = 1000,
        batch_chunks: int = 128,
    ) -> dict[str, Any]:
        """Bootstrap the local hybrid index from HuggingFace Lex.uz datasets."""
        docs_count = 0
        chunks_count = 0
        chunk_buffer: list[LegalChunk] = []

        try:
            for fetched in iter_huggingface_corpus(dataset_name, split=split, max_docs=max_docs):
                meta = self.registry.upsert(fetched.metadata)
                chunks = self.parser.parse_to_chunks(meta, fetched.raw_text)
                if not chunks:
                    continue
                docs_count += 1
                chunk_buffer.extend(chunks)
                if len(chunk_buffer) >= batch_chunks:
                    await self._store_chunks(chunk_buffer)
                    chunks_count += len(chunk_buffer)
                    chunk_buffer.clear()
                    if docs_count % 100 == 0:
                        logger.info("Ingested %d documents (%d chunks) from %s...", docs_count, chunks_count, dataset_name)
        finally:
            if chunk_buffer:
                await self._store_chunks(chunk_buffer)
                chunks_count += len(chunk_buffer)
                chunk_buffer.clear()
            self.bm25_store.rebuild_index()

        return {
            "dataset": dataset_name,
            "documents_indexed": docs_count,
            "chunks_indexed": chunks_count,
        }

    async def ingest_local_path(
        self,
        path: Path,
        *,
        max_docs: int | None = None,
        batch_chunks: int = 128,
    ) -> dict[str, Any]:
        """Ingest local `.jsonl`, `.json`, or `.parquet` Lex.uz files."""
        docs_count = 0
        chunks_count = 0
        chunk_buffer: list[LegalChunk] = []

        for fetched in iter_local_jsonl_or_parquet(path, max_docs=max_docs):
            meta = self.registry.upsert(fetched.metadata)
            chunks = self.parser.parse_to_chunks(meta, fetched.raw_text)
            if not chunks:
                continue
            docs_count += 1
            chunk_buffer.extend(chunks)
            if len(chunk_buffer) >= batch_chunks:
                await self._store_chunks(chunk_buffer)
                chunks_count += len(chunk_buffer)
                chunk_buffer.clear()

        if chunk_buffer:
            await self._store_chunks(chunk_buffer)
            chunks_count += len(chunk_buffer)

        self.bm25_store.rebuild_index()
        return {
            "path": str(path),
            "documents_indexed": docs_count,
            "chunks_indexed": chunks_count,
        }

    async def bootstrap_core_codes(self, *, fetch_all_languages: bool = True) -> dict[str, Any]:
        """Fetch and index Uzbekistan's Constitution and all 18 foundational Codes live from Lex.uz."""
        summary: dict[str, Any] = {}
        for label, doc_id in CORE_UZBEKISTAN_LEX_IDS.items():
            try:
                res = await self.ingest_lex_doc(doc_id, fetch_all_languages=fetch_all_languages)
                summary[label] = res
            except Exception as exc:
                logger.warning("Failed bootstrapping %s (%s): %s", label, doc_id, exc)
                summary[label] = {"doc_id": doc_id, "error": str(exc)}
        self.bm25_store.rebuild_index()
        return summary

    def seed_foundational_codes_fast(self) -> int:
        """Index the built-in verified Uzbekistan Codes reference pack directly into SQLite FTS5 (<50ms)."""
        added = 0
        for fetched in build_foundational_reference_pack():
            meta = self.registry.upsert(fetched.metadata)
            chunks = self.parser.parse_to_chunks(meta, fetched.raw_text)
            if chunks:
                self.bm25_store.upsert_chunks(chunks)
                added += len(chunks)
        return added

    async def ingest_external_url(self, url: str) -> dict[str, Any]:
        """Fetch and index a legal article, commentary, or Supreme Court resolution from any Uzbekistan portal."""
        fetched = await fetch_external_legal_url(url)
        if not fetched:
            return {"url": url, "chunks_indexed": 0, "error": "Sahifadan yetarli huquqiy matn topilmadi."}
        count = await self.index_fetched_document(fetched)
        return {
            "url": url,
            "doc_id": fetched.metadata.doc_id,
            "title": fetched.metadata.title,
            "language": fetched.metadata.language.value,
            "chunks_indexed": count,
        }

    async def ingest_uploaded_file(
        self,
        filename: str,
        content: bytes,
        *,
        title: str | None = None,
        doc_type: DocumentType | None = None,
        source_url: str | None = None,
    ) -> dict[str, Any]:
        """Parse and index an uploaded Code PDF, Supreme Court Plenum DOCX, or legal commentary TXT."""
        fetched = build_uploaded_knowledge_document(
            filename,
            content,
            title=title,
            doc_type=doc_type,
            source_url=source_url,
        )
        count = await self.index_fetched_document(fetched)
        return {
            "filename": filename,
            "doc_id": fetched.metadata.doc_id,
            "title": fetched.metadata.title,
            "doc_type": fetched.metadata.doc_type.value,
            "language": fetched.metadata.language.value,
            "chunks_indexed": count,
        }
