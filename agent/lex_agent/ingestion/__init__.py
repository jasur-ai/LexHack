"""Ingestion subsystem exports (lazy-loaded to keep leaf module imports fast and cycle-free)."""

from __future__ import annotations

from typing import Any

__all__ = [
    "LexUzFetcher",
    "FetchedDocument",
    "LexSearchResult",
    "LegalDocumentParser",
    "classify_document_type",
    "classify_branches",
    "IngestionPipeline",
]


def __getattr__(name: str) -> Any:
    if name in ("LexUzFetcher", "FetchedDocument", "LexSearchResult"):
        from lex_agent.ingestion import lex_fetcher

        return getattr(lex_fetcher, name)
    if name in ("LegalDocumentParser", "classify_document_type", "classify_branches"):
        from lex_agent.ingestion import parser

        return getattr(parser, name)
    if name == "IngestionPipeline":
        from lex_agent.ingestion.pipeline import IngestionPipeline

        return IngestionPipeline
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
