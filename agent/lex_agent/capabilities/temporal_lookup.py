"""Temporal legal lookup: compare what Uzbekistan legislation provided on a historical date vs. today."""

from __future__ import annotations

from datetime import date

from lex_agent.language.transliterator import detect_language
from lex_agent.llm.client import LLMClient
from lex_agent.models import (
    RetrievalFilter,
    TemporalLookupRequest,
    TemporalLookupResponse,
)
from lex_agent.reasoning.citation_guard import CitationVerificationGuard
from lex_agent.retrieval.hybrid_retriever import HybridLegalRetriever


class TemporalLegalLookup:
    """Retrieves and compares legal regimes across two points in time (historical date vs. current law)."""

    def __init__(self, *, llm: LLMClient, retriever: HybridLegalRetriever) -> None:
        self.llm = llm
        self.retriever = retriever
        self.citation_guard = CitationVerificationGuard()

    async def compare(self, req: TemporalLookupRequest) -> TemporalLookupResponse:
        comp_date = req.comparison_date or date.today()
        lang = req.response_language or detect_language(req.query)

        hist_filter = RetrievalFilter(as_of_date=req.historical_date, include_repealed=True)
        curr_filter = RetrievalFilter(as_of_date=comp_date, include_repealed=False)

        hist_hits, _ = await self.retriever.retrieve(
            req.query,
            top_k=10,
            rerank_top_k=6,
            filters=hist_filter,
            enable_live_fallback=True,
        )
        curr_hits, _ = await self.retriever.retrieve(
            req.query,
            top_k=10,
            rerank_top_k=6,
            filters=curr_filter,
            enable_live_fallback=True,
        )

        hist_verify = self.citation_guard.verify("", hist_hits)
        curr_verify = self.citation_guard.verify("", curr_hits)

        def fmt(hits):
            if not hits:
                return "(No matching norms indexed for this date.)"
            return "\n---\n".join(
                f"{h.chunk.doc_title} ({h.chunk.doc_number or h.chunk.doc_id}) | {h.chunk.article or 'General'} | "
                f"Effective: {h.chunk.effective_date} | Expiry: {h.chunk.expiry_date} | Status: {h.chunk.status.value} | "
                f"URL: {h.chunk.citation_url}\n{h.chunk.text[:1400]}"
                for h in hits
            )

        if self.llm.is_mock:
            combined_verify = self.citation_guard.verify("", hist_hits + curr_hits)
            return TemporalLookupResponse(
                query=req.query,
                historical_date=req.historical_date,
                comparison_date=comp_date,
                historical_regime_summary=f"[Mock Mode] Retrieved {len(hist_hits)} norms effective on {req.historical_date}.",
                current_regime_summary=f"[Mock Mode] Retrieved {len(curr_hits)} norms effective on {comp_date}.",
                key_changes=["Configure LLM_API_KEY for automated legal diff synthesis."],
                historical_citations=hist_verify.verified_citations,
                current_citations=curr_verify.verified_citations,
                verification=combined_verify,
            )

        prompt = (
            f"Compare Uzbekistan legislation regarding: '{req.query}'\n"
            f"1) Historical Regime as of {req.historical_date.isoformat()}\n"
            f"2) Comparison Regime as of {comp_date.isoformat()}\n"
            f"Respond in language: {lang.value}.\n"
            "Use ONLY the retrieved Lex.uz texts below. Never fabricate amendments or dates.\n"
            "Return JSON: {\"historical_regime_summary\": str, \"current_regime_summary\": str, \"key_changes\": [str]}\n\n"
            f"=== NORMS EFFECTIVE ON {req.historical_date.isoformat()} ===\n{fmt(hist_hits)}\n\n"
            f"=== NORMS EFFECTIVE ON {comp_date.isoformat()} ===\n{fmt(curr_hits)}"
        )

        data = await self.llm.complete_json(
            [
                {"role": "system", "content": "You perform exact point-in-time historical legal comparisons for Uzbekistan law."},
                {"role": "user", "content": prompt},
            ],
            fallback={},
        )

        hist_summary = str(data.get("historical_regime_summary", "Insufficient historical texts indexed."))
        curr_summary = str(data.get("current_regime_summary", "Insufficient current texts indexed."))
        key_changes = [str(x) for x in data.get("key_changes", [])]

        combined_text = "\n".join([hist_summary, curr_summary, *key_changes])
        verification = self.citation_guard.verify(combined_text, hist_hits + curr_hits)

        return TemporalLookupResponse(
            query=req.query,
            historical_date=req.historical_date,
            comparison_date=comp_date,
            historical_regime_summary=hist_summary,
            current_regime_summary=curr_summary,
            key_changes=key_changes,
            historical_citations=hist_verify.verified_citations,
            current_citations=curr_verify.verified_citations,
            verification=verification,
        )
