"""Shared dependency container wiring all Lex.uz Legal AI Agent subsystems."""

from __future__ import annotations

from dataclasses import dataclass

from lex_agent.capabilities.document_analyzer import LegalDocumentAnalyzer
from lex_agent.capabilities.temporal_lookup import TemporalLegalLookup
from lex_agent.config import Settings, get_settings
from lex_agent.ingestion.lex_fetcher import LexUzFetcher
from lex_agent.ingestion.parser import LegalDocumentParser
from lex_agent.ingestion.pipeline import IngestionPipeline
from lex_agent.language.comparator import LegalLanguageComparator
from lex_agent.llm.client import EmbeddingClient, LLMClient
from lex_agent.reasoning.orchestrator import LegalAgentOrchestrator
from lex_agent.retrieval.bm25_store import BM25Store
from lex_agent.retrieval.hybrid_retriever import HybridLegalRetriever
from lex_agent.retrieval.reranker import LegalReranker
from lex_agent.retrieval.vector_store import QdrantVectorStore


@dataclass
class AgentRuntime:
    """Singleton-friendly runtime container for FastAPI and CLI entrypoints."""

    settings: Settings
    llm: LLMClient
    embedder: EmbeddingClient
    bm25_store: BM25Store
    vector_store: QdrantVectorStore
    reranker: LegalReranker
    fetcher: LexUzFetcher
    parser: LegalDocumentParser
    ingestion: IngestionPipeline
    retriever: HybridLegalRetriever
    comparator: LegalLanguageComparator
    orchestrator: LegalAgentOrchestrator
    document_analyzer: LegalDocumentAnalyzer
    temporal_lookup: TemporalLegalLookup

    @classmethod
    def build(cls, settings: Settings | None = None) -> AgentRuntime:
        cfg = settings or get_settings()
        cfg.ensure_directories()

        llm = LLMClient(cfg)
        embedder = EmbeddingClient(cfg)
        bm25_store = BM25Store(cfg.bm25_db_path)
        vector_store = QdrantVectorStore(embedder=embedder, settings=cfg)
        reranker = LegalReranker(cfg)
        fetcher = LexUzFetcher(cfg)
        parser = LegalDocumentParser()

        ingestion = IngestionPipeline(
            bm25_store=bm25_store,
            vector_store=vector_store,
            fetcher=fetcher,
            parser=parser,
            settings=cfg,
        )
        retriever = HybridLegalRetriever(
            bm25_store=bm25_store,
            vector_store=vector_store,
            reranker=reranker,
            ingestion_pipeline=ingestion,
            settings=cfg,
        )
        comparator = LegalLanguageComparator(llm=llm, fetcher=fetcher, bm25_store=bm25_store)
        orchestrator = LegalAgentOrchestrator(
            llm=llm,
            retriever=retriever,
            comparator=comparator,
            settings=cfg,
        )
        document_analyzer = LegalDocumentAnalyzer(llm=llm, retriever=retriever)
        temporal_lookup = TemporalLegalLookup(llm=llm, retriever=retriever)

        return cls(
            settings=cfg,
            llm=llm,
            embedder=embedder,
            bm25_store=bm25_store,
            vector_store=vector_store,
            reranker=reranker,
            fetcher=fetcher,
            parser=parser,
            ingestion=ingestion,
            retriever=retriever,
            comparator=comparator,
            orchestrator=orchestrator,
            document_analyzer=document_analyzer,
            temporal_lookup=temporal_lookup,
        )

    def build_index(self, *, force: bool = False) -> dict:
        """Index the bundled open corpora (no-op when the bundle fingerprint is unchanged)."""
        from lex_agent.ingestion.open_corpora import build_bundled_index

        return build_bundled_index(
            bm25_store=self.bm25_store,
            registry=self.ingestion.registry,
            parser=self.parser,
            corpus_dir=self.settings.corpus_dir,
            cache_dir=self.settings.cache_dir,
            force=force,
        )

    async def close(self) -> None:
        await self.fetcher.close()
        await self.llm.close()
        self.vector_store.close()
