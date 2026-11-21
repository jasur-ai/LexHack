"""Cross-encoder legal reranker (BAAI/bge-reranker-v2-m3) with precision lexical + tie-break authority fallback."""

from __future__ import annotations

import importlib.util
import logging
import re
from typing import Any

from lex_agent.config import Settings, get_settings
from lex_agent.models import NormStatus, RetrievedChunk
from lex_agent.retrieval.bm25_store import legal_tokenize

logger = logging.getLogger(__name__)


class LegalReranker:
    """Reranks hybrid retrieval candidates ensuring relevance always dominates over raw legal hierarchy."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._model: Any = None
        self._model_unavailable = (
            not self.settings.reranker_enabled
            or importlib.util.find_spec("sentence_transformers") is None
        )

    def _ensure_cross_encoder(self) -> Any | None:
        if self._model_unavailable:
            return None
        if self._model is None:
            try:
                from sentence_transformers import CrossEncoder

                logger.info("Loading cross-encoder reranker: %s", self.settings.reranker_model)
                self._model = CrossEncoder(self.settings.reranker_model)
            except Exception as exc:
                logger.warning("CrossEncoder unavailable (%s); using fast lexical reranker.", exc)
                self._model_unavailable = True
                return None
        return self._model

    def rerank(
        self,
        query: str,
        candidates: list[RetrievedChunk],
        *,
        top_k: int = 8,
    ) -> list[RetrievedChunk]:
        """Rerank candidates so topical relevance dominates and irrelevant codes are filtered out."""
        if not candidates:
            return []

        model = self._ensure_cross_encoder()
        if model is not None:
            pairs = [(query, f"{c.chunk.doc_title} | {c.chunk.hierarchical_path}\n{c.chunk.text[:1600]}") for c in candidates]
            try:
                scores = model.predict(pairs)
                for cand, score in zip(candidates, scores):
                    authority_tiebreak = (cand.chunk.legal_force_rank / 100.0) * 0.03
                    status_penalty = -0.50 if cand.chunk.status == NormStatus.REPEALED else 0.0
                    cand.rerank_score = float(score)
                    cand.final_score = float(score) + authority_tiebreak + status_penalty
                candidates.sort(key=lambda c: c.final_score, reverse=True)
                return candidates[:top_k]
            except Exception as exc:
                logger.warning("CrossEncoder inference failed (%s); falling back.", exc)

        # Precision lexical reranker: drop stopwords so common words don't inflate irrelevant laws
        q_tokens = set(legal_tokenize(query, drop_stopwords=True))
        if not q_tokens:
            q_tokens = set(legal_tokenize(query, drop_stopwords=False))

        art_mentions = {
            a or b
            for a, b in re.findall(
                r"\b(\d+(?:[-.]\d+)?)\s*-?\s*(?:modda|модда)|(?:ст\.|стать\w+|article)\s*(\d+(?:[-.]\d+)?)\b",
                query,
                re.I,
            )
            if (a or b)
        }

        max_bm25 = max((c.bm25_score for c in candidates), default=0.0) or 1.0
        scored: list[RetrievedChunk] = []

        for cand in candidates:
            title_tokens = set(legal_tokenize(f"{cand.chunk.doc_title} {cand.chunk.article or ''} {cand.chunk.article_title or ''}", drop_stopwords=True))
            body_tokens = set(legal_tokenize(cand.chunk.text[:1800], drop_stopwords=True))
            all_tokens = title_tokens | body_tokens

            body_overlap = len(q_tokens & all_tokens) / max(len(q_tokens), 1)
            title_overlap = len(q_tokens & title_tokens) / max(len(q_tokens), 1)
            # Title precision: an article whose title is fully explained by the question is the most specific match
            art_title_tokens = set(legal_tokenize(cand.chunk.article_title or "", drop_stopwords=True))
            title_precision = (
                len(q_tokens & art_title_tokens) / len(art_title_tokens) if art_title_tokens else 0.0
            )
            first_part_bonus = 0.02 if not cand.chunk.clause or str(cand.chunk.clause).startswith("1/") else 0.0
            norm_bm25 = cand.bm25_score / max_bm25 if cand.bm25_score > 0 else 0.0

            art_bonus = 0.0
            if art_mentions and cand.chunk.article:
                m = re.search(r"(\d+(?:[-.]\d+)?)", cand.chunk.article)
                if m and m.group(1) in art_mentions:
                    art_bonus = 0.45

            # Small tie-breaker only (max 0.015) — NEVER lets irrelevant Codes outrank relevant laws!
            authority_tiebreak = (cand.chunk.legal_force_rank / 100.0) * 0.015
            status_penalty = -0.35 if cand.chunk.status == NormStatus.REPEALED else 0.0

            relevance = (
                (0.45 * norm_bm25)
                + (0.35 * body_overlap)
                + (0.20 * title_overlap)
                + (0.18 * title_precision)
                + first_part_bonus
                + art_bonus
            )
            cand.rerank_score = relevance
            cand.final_score = relevance + (cand.rrf_score * 2.0) + authority_tiebreak + status_penalty

            # Drop pure noise chunks with zero keyword overlap and no BM25 match
            if body_overlap == 0.0 and cand.bm25_score == 0.0 and cand.dense_score < 0.55:
                continue
            scored.append(cand)

        if not scored:
            scored = list(candidates)

        scored.sort(key=lambda c: c.final_score, reverse=True)
        return scored[:top_k]
