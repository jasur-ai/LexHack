"""Agentic legal reasoning pipeline exports (lazy-loaded to avoid circular imports)."""

from __future__ import annotations

from typing import Any

__all__ = [
    "extract_cross_references",
    "LegalQueryDecomposer",
    "NormConflictResolver",
    "CitationVerificationGuard",
    "LegalAgentOrchestrator",
]


def __getattr__(name: str) -> Any:
    if name == "extract_cross_references":
        from lex_agent.reasoning.cross_ref import extract_cross_references

        return extract_cross_references
    if name == "LegalQueryDecomposer":
        from lex_agent.reasoning.decomposer import LegalQueryDecomposer

        return LegalQueryDecomposer
    if name == "NormConflictResolver":
        from lex_agent.reasoning.norm_resolver import NormConflictResolver

        return NormConflictResolver
    if name == "CitationVerificationGuard":
        from lex_agent.reasoning.citation_guard import CitationVerificationGuard

        return CitationVerificationGuard
    if name == "LegalAgentOrchestrator":
        from lex_agent.reasoning.orchestrator import LegalAgentOrchestrator

        return LegalAgentOrchestrator
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
