"""Hybrid legal retriever: query analysis, exact article lookup, BM25 over analysed terms (plus statutory
re-phrasings and typo corrections), optional dense search, RRF fusion, reranking and a guarded live lex.uz
fallback.

Pipeline for one question:

1. *Analyse* — language/script, analysed terms without stop words, spelling corrections for terms the index has
   never seen, formal re-phrasings from the colloquial→legal lexicon, and acts/articles named in the question.
2. *Exact* — "Mehnat kodeksi 217-modda" / "ТК ст. 161" / "O'RQ-547 5-modda" go straight to the article.
3. *Lexical* — BM25 for the question, each re-phrasing, and (when an act is named) inside that act only.
4. *Dense* — only with real neural embeddings configured (hash vectors are noise and stay off).
5. *Fuse + rerank* — reciprocal-rank fusion, then the feature reranker (trained model when bundled).
6. *Present* — prefer the reader's language family and keep one chunk per (act, article) across editions.
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from lex_agent.config import Settings, get_settings
from lex_agent.language.stopwords import stop_terms
from lex_agent.language.textproc import index_terms, query_terms, surface_tokens
from lex_agent.language.transliterator import detect_language
from lex_agent.models import Language, RetrievalFilter, RetrievedChunk
from lex_agent.retrieval.act_resolver import ActRef, ActResolver
from lex_agent.retrieval.bm25_store import BM25Store, chunk_matches_filter, number_tokens
from lex_agent.knowledge.lexicon import ConceptMatch, get_lexicon
from lex_agent.knowledge.synonyms import expansion_text
from lex_agent.retrieval.reranker import LegalReranker, QueryInfo, build_query_info
from lex_agent.retrieval.spelling import SpellingCorrector
from lex_agent.retrieval.vector_store import QdrantVectorStore

if TYPE_CHECKING:
    from lex_agent.ingestion.pipeline import IngestionPipeline

logger = logging.getLogger(__name__)

LIVE_CIRCUIT_COOLDOWN_SEC = 300

# A question names a practical figure (then the figures card may lead the sources)
_FIGURE_WORDS = re.compile(
    r"\bbhm\b|\bbrv\b|\bбрв\b|\bбҳм\b|bazaviy|базов\w* (?:расч|величин)|mhtekm|\bмрот\b|eng kam (?:ish haqi|oylik|maosh)|"
    r"энг кам|минимальн\w* (?:зарплат|размер|заработн)|minimum wage|base calculation|stavka|ставк|\brate\b|penya|пен[яи]|"
    r"davlat boj|давлат бож|пошлин|state duty|court fee|qancha so'?m|сколько сум",
    re.I,
)


@dataclass(slots=True)
class QueryAnalysis:
    """Everything the retriever derives from the raw question (also exposed for routing and answers)."""

    query: str
    language: str
    terms: list[str]
    corrections: dict[str, str] = field(default_factory=dict)
    expansions: list[str] = field(default_factory=list)
    expansion_terms: list[list[str]] = field(default_factory=list)
    acts: list[ActRef] = field(default_factory=list)
    concepts: list[ConceptMatch] = field(default_factory=list)
    synonym_terms: list[str] = field(default_factory=list)

    @property
    def search_terms(self) -> list[str]:
        out = list(self.terms)
        for fixed in self.corrections.values():
            if fixed not in out:
                out.append(fixed)
        return out

    @property
    def all_expansion_terms(self) -> set[str]:
        return {t for terms in self.expansion_terms for t in terms}

    def concept_targets(self) -> dict[tuple[str, str], float]:
        """(act, article) -> prior weight from the matched situations (first situation, first article = 1.0)."""
        out: dict[tuple[str, str], float] = {}
        has_specific = any(not m.concept.generic for m in self.concepts[:3])
        for i, m in enumerate(self.concepts[:3]):
            if m.concept.generic:
                base = 0.25 if has_specific else 0.6
            else:
                base = 1.0 - 0.25 * i
            for j, key in enumerate(m.concept.targets):
                w = max(0.15, base * (1.0 - 0.12 * j))
                if w > out.get(key, 0.0):
                    out[key] = w
        return out

    @property
    def concept_docs(self) -> set[str]:
        return {d for m in self.concepts[:3] for d in m.concept.target_docs}


class HybridLegalRetriever:
    """Fast hybrid search over the offline index with exact article lookup and conditional live lex.uz fallback."""

    def __init__(
        self,
        *,
        bm25_store: BM25Store,
        vector_store: QdrantVectorStore,
        reranker: LegalReranker,
        ingestion_pipeline: IngestionPipeline | None = None,
        settings: Settings | None = None,
        act_resolver: ActResolver | None = None,
        speller: SpellingCorrector | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.bm25_store = bm25_store
        self.vector_store = vector_store
        self.reranker = reranker
        self.ingestion_pipeline = ingestion_pipeline
        self.act_resolver = act_resolver or ActResolver.from_corpus(self.settings.corpus_dir)
        self.speller = speller or SpellingCorrector(bm25_store)
        self._live_circuit_open_until = 0.0

    # ------------------------------------------------------------------ analysis
    def analyze(self, query: str) -> QueryAnalysis:
        lang = detect_language(query).value
        stops = stop_terms(lang)
        terms = [t for t in dict.fromkeys(query_terms(query, language=lang)) if t not in stops][:16]
        if not terms:
            terms = list(dict.fromkeys(query_terms(query, language=lang)))[:8]
        corrections: dict[str, str] = {}
        corrected_words: dict[str, str] = {}
        if lang != "en":  # the corpus has no English text: unknown English words are not typos
            try:
                for typed, fixed, typed_word, fixed_word in self.speller.corrections(
                    query, language=lang, protected=get_lexicon().trigger_words
                ):
                    corrections[typed] = fixed
                    corrected_words[typed_word] = fixed_word
            except Exception as exc:  # pragma: no cover - an empty/locked index must never break answering
                logger.debug("Spelling correction skipped: %s", exc)
        corrected_query = None
        if corrected_words:
            folded = surface_tokens(query, language=lang)
            corrected_query = " ".join(corrected_words.get(w, w) for w in folded)
        try:
            concepts = get_lexicon().match(query, language=lang, corrected_terms=[corrected_query] if corrected_query else None)
        except Exception as exc:  # pragma: no cover - defensive
            logger.debug("Situation lexicon skipped: %s", exc)
            concepts = []
        expansions = get_lexicon().formal_phrases(concepts, language=lang)[:3]
        syn_text = expansion_text(corrected_query or query, language=lang)
        exp_terms: list[list[str]] = []
        for phrase in expansions:
            plang = "ru" if any("\u0400" <= ch <= "\u04ff" for ch in phrase) else "uz_latn"
            pstops = stop_terms(plang)
            exp_terms.append([t for t in dict.fromkeys(index_terms(phrase, language=plang)) if t not in pstops])
        syn_terms: list[str] = []
        if syn_text:
            slang = "ru" if lang in ("ru", "en") else "uz_latn"  # English is bridged to the Russian statute words
            sstops = stop_terms(slang)
            syn_terms = [t for t in dict.fromkeys(index_terms(syn_text, language=slang)) if t not in sstops and t not in terms]
        try:
            acts = self.act_resolver.resolve(query)
        except Exception as exc:  # pragma: no cover - defensive
            logger.debug("Act resolution skipped: %s", exc)
            acts = []
        return QueryAnalysis(
            query=query,
            language=lang,
            terms=terms,
            corrections=corrections,
            expansions=expansions,
            expansion_terms=exp_terms,
            acts=acts,
            concepts=concepts,
            synonym_terms=syn_terms[:12],
        )

    # ------------------------------------------------------------------ main entry
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
        analysis: QueryAnalysis | None = None,
    ) -> tuple[list[RetrievedChunk], list[str]]:
        """Hybrid search; live lex.uz is consulted only when local recall is genuinely weak."""
        top_k = top_k or self.settings.agent_top_k
        rerank_top_k = rerank_top_k or self.settings.agent_rerank_top_k
        # The global switch always wins: a request may opt out of live lookups but never force them on.
        use_live = self.settings.lex_uz_enable_live_fallback and (
            True if enable_live_fallback is None else enable_live_fallback
        )
        # CPU-bound steps run in worker threads so the event loop keeps streaming other answers meanwhile
        # (SQLite connections are per thread; FTS5 queries release the GIL)
        qa = analysis or await asyncio.to_thread(self.analyze, query)
        fused, list_ranks = await self._search_once(qa, top_k=top_k, filters=filters, hop=hop)
        live_fetched_ids: list[str] = []

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
                # Circuit breaker: when lex.uz is slow/unreachable, stop paying the timeout on every question.
                self._live_circuit_open_until = time.monotonic() + LIVE_CIRCUIT_COOLDOWN_SEC
                logger.info(
                    "Live Lex.uz quick-fallback skipped (%s); local corpus only for the next %ss.",
                    exc.__class__.__name__,
                    LIVE_CIRCUIT_COOLDOWN_SEC,
                )
                live_fetched_ids = []
            if live_fetched_ids:
                self.speller.reset()
                fused, list_ranks = await self._search_once(qa, top_k=top_k, filters=filters, hop=hop)

        qinfo = self.query_info(qa, list_ranks)
        reranked = await asyncio.to_thread(
            self.reranker.rerank, qinfo, fused, top_k=max(rerank_top_k * 3, rerank_top_k + 6)
        )
        ranked = self._demote_figures(qa, self._prefer_language_and_dedupe(qa.language, reranked))[:rerank_top_k]
        for item in ranked:
            item.retrieval_hop = hop
        return ranked, live_fetched_ids

    def query_info(self, qa: QueryAnalysis, list_ranks: dict[str, dict[str, int]] | None = None) -> QueryInfo:
        """Reranker view of an analysed question (also used to build training data)."""
        idf = self.bm25_store.idf(qa.search_terms)
        for fixed in qa.corrections.values():
            if fixed in idf and fixed not in qa.terms:
                idf[fixed] *= 0.6  # a guessed correction counts less than what the person actually typed
        return build_query_info(
            qa.query,
            terms=qa.search_terms,
            idf=idf,
            expansion_terms=qa.all_expansion_terms | set(qa.synonym_terms),
            language=qa.language,
            doc_numbers=self._doc_number_tokens(qa.query),
            doc_priors={a.canonical_id: 1.0 for a in qa.acts},
            concept_targets=qa.concept_targets(),
            concept_docs=qa.concept_docs,
            list_ranks=list_ranks or {},
            idf_lookup=self.bm25_store.idf,
        )

    async def candidates(
        self, qa: QueryAnalysis, *, top_k: int = 12, filters: RetrievalFilter | None = None
    ) -> tuple[list[RetrievedChunk], QueryInfo]:
        """First-stage candidates plus the reranker view (training and diagnostics)."""
        fused, list_ranks = await self._search_once(qa, top_k=top_k, filters=filters, hop=1)
        return fused, self.query_info(qa, list_ranks)

    @staticmethod
    def _doc_number_tokens(query: str) -> set[str]:
        from lex_agent.retrieval.act_resolver import _NUMBER_RE

        return {number_tokens(m.group(0)) for m in _NUMBER_RE.finditer(query)} - {""}

    # ------------------------------------------------------------------ one search round
    async def _search_once(
        self, qa: QueryAnalysis, *, top_k: int, filters: RetrievalFilter | None, hop: int
    ) -> tuple[list[RetrievedChunk], dict[str, dict[str, int]]]:
        exact, concept_hits, bm25_hits, list_ranks = await asyncio.to_thread(self._lexical_round, qa, top_k, filters)
        return await self._fuse_round(qa, exact, concept_hits, bm25_hits, list_ranks, top_k=top_k, filters=filters,
                                      hop=hop)

    def _lexical_round(
        self, qa: QueryAnalysis, top_k: int, filters: RetrievalFilter | None
    ) -> tuple[list[RetrievedChunk], list[RetrievedChunk], list[RetrievedChunk], dict[str, dict[str, int]]]:
        """Exact references, situation targets and the BM25 lists of one search round (synchronous, thread-safe)."""
        exact = self._exact_articles(qa, filters)
        concept_hits = self._concept_articles(qa, filters)

        lexical_lists: list[list[RetrievedChunk]] = []
        weights: list[float] = []
        list_ranks: dict[str, dict[str, int]] = {}

        def _add(name: str, hits: list[RetrievedChunk], weight: float) -> None:
            lexical_lists.append(hits)
            weights.append(weight)
            list_ranks[name] = {h.chunk.chunk_id: i for i, h in enumerate(hits)}

        main_terms = qa.search_terms
        if main_terms:
            _add("main", self.bm25_store.search_terms(main_terms, top_k=top_k, filters=filters), 1.0)
        for i, terms in enumerate(qa.expansion_terms):
            if terms:
                _add(f"exp{i}", self.bm25_store.search_terms(terms, top_k=top_k, filters=filters), 1.15)
        if qa.synonym_terms:
            # The question's own words plus the statutory words for its everyday words
            syn_query = list(dict.fromkeys(main_terms + qa.synonym_terms))
            _add("syn", self.bm25_store.search_terms(syn_query, top_k=top_k, filters=filters), 0.8)
        act_ids = [a.canonical_id for a in qa.acts if not a.article]
        if act_ids and main_terms:
            scoped_terms = [t for t in main_terms if t not in self._act_title_terms(act_ids)] or main_terms
            _add(
                "scoped",
                self.bm25_store.search_terms(scoped_terms, top_k=top_k, filters=filters, doc_ids=act_ids[:3]),
                1.3,
            )
        bm25_hits = self._fuse_lexical(lexical_lists, weights) if lexical_lists else []
        return exact, concept_hits, bm25_hits, list_ranks

    async def _fuse_round(
        self,
        qa: QueryAnalysis,
        exact: list[RetrievedChunk],
        concept_hits: list[RetrievedChunk],
        bm25_hits: list[RetrievedChunk],
        list_ranks: dict[str, dict[str, int]],
        *,
        top_k: int,
        filters: RetrievalFilter | None,
        hop: int,
    ) -> tuple[list[RetrievedChunk], dict[str, dict[str, int]]]:
        dense_hits: list[RetrievedChunk] = []
        if self.vector_store.enabled:
            dense_hits = await self.vector_store.search(qa.query, top_k=top_k, filters=filters)

        fused = self._reciprocal_rank_fusion(dense_hits, bm25_hits, k=60, hop=hop, dense_weight=1.0, bm25_weight=1.4)
        seen = {r.chunk.chunk_id for r in fused}
        for extra in (concept_hits, exact):
            for e in extra:
                if e.chunk.chunk_id not in seen:
                    seen.add(e.chunk.chunk_id)
                    fused.append(e)
        if exact:
            exact_ids = {e.chunk.chunk_id for e in exact}
            top_bm25 = max((r.bm25_score for r in fused), default=10.0)
            for r in fused:
                if r.chunk.chunk_id in exact_ids:
                    r.bm25_score = max(r.bm25_score, top_bm25)
                    r.rrf_score = max(r.rrf_score, 1.4 / 61 + 1.0 / 61)
            fused.sort(key=lambda r: (r.chunk.chunk_id not in exact_ids, -r.rrf_score))
        return fused, list_ranks

    def _concept_articles(self, qa: QueryAnalysis, filters: RetrievalFilter | None) -> list[RetrievedChunk]:
        """Target articles of the matched situations, fetched directly (recall for well-known situations)."""
        if not qa.concepts:
            return []
        langs = ("ru",) if qa.language == "ru" else ("uz_cyrl", "uz_latn")
        wanted = [key for key, _w in sorted(qa.concept_targets().items(), key=lambda kv: -kv[1])[:10]]
        found = self.bm25_store.get_articles(wanted, languages=langs, per_article=2)
        out: list[RetrievedChunk] = []
        for key in wanted:
            for c in found.get(key, []):
                if chunk_matches_filter(c, filters):
                    out.append(RetrievedChunk(chunk=c, retrieval_source="situation_lexicon"))
        return out

    def _act_title_terms(self, act_ids: list[str]) -> set[str]:
        out: set[str] = set()
        for cid in act_ids:
            d = self.act_resolver.catalog.get(cid) or {}
            for title, lang in ((d.get("short_uz"), "uz_cyrl"), (d.get("short_ru"), "ru")):
                if title:
                    out.update(index_terms(title, language=lang))
        out.update({"kodeks", "кодекс", "qonun", "закон"})
        return out

    def _exact_articles(self, qa: QueryAnalysis, filters: RetrievalFilter | None) -> list[RetrievedChunk]:
        out: list[RetrievedChunk] = []
        langs = ("ru",) if qa.language == "ru" else ("uz_cyrl", "uz_latn")
        for ref in qa.acts:
            if not ref.article:
                continue
            cid = ref.canonical_id
            if cid in ("111189", "180552"):
                part = self.act_resolver.civil_part_for(ref.article)
                if part and part != cid:
                    continue
            chunks = self.bm25_store.get_article(cid, ref.article, languages=langs, limit=8)
            if not chunks:
                chunks = self.bm25_store.get_article(cid, ref.article, limit=8)
            for c in chunks:
                if not chunk_matches_filter(c, filters):
                    continue
                out.append(
                    RetrievedChunk(
                        chunk=c,
                        bm25_score=10.0,
                        rrf_score=0.05,
                        final_score=1.0,
                        retrieval_source="exact_article",
                    )
                )
        return out

    # ------------------------------------------------------------------ presentation
    @staticmethod
    def _article_key(item: RetrievedChunk) -> tuple[str, str]:
        from lex_agent.chunk_text import chunk_article_id

        art = chunk_article_id(item.chunk)
        return item.chunk.canonical_id, art or item.chunk.chunk_id.split("#")[0]

    @staticmethod
    def _demote_figures(qa: QueryAnalysis, items: list[RetrievedChunk]) -> list[RetrievedChunk]:
        """Practical-figures cards are summaries, not law: they lead only when the question is about a figure
        (BHM, minimum wage, a rate, a duty) — otherwise every statute article ranks above them. Without this an
        English question matched the English figure cards (the only English text in the index) before the law."""
        from lex_agent.knowledge.facts import FACTS_DOC_ID

        if not any(i.chunk.canonical_id == FACTS_DOC_ID for i in items):
            return items
        wants = any(FACTS_DOC_ID in m.concept.target_docs for m in qa.concepts[:3]) or bool(_FIGURE_WORDS.search(qa.query))
        if wants:
            return items
        return [i for i in items if i.chunk.canonical_id != FACTS_DOC_ID] + [
            i for i in items if i.chunk.canonical_id == FACTS_DOC_ID
        ]

    def _prefer_language_and_dedupe(self, q_lang: str | Language, items: list[RetrievedChunk]) -> list[RetrievedChunk]:
        """Prefer norms in the asker's language family and keep one chunk per (act, article) across editions."""
        if not items:
            return items
        lang = q_lang.value if isinstance(q_lang, Language) else str(q_lang)
        for item in items:
            c_lang = item.chunk.language
            if lang == "ru":
                factor = 1.0 if c_lang == Language.RU else 0.82
            elif lang in ("uz_latn", "uz_cyrl"):
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

    # ------------------------------------------------------------------ exact references (multi-hop)
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
            if not chunks and enable_live_fallback and self.ingestion_pipeline and self.settings.lex_uz_enable_live_fallback:
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

        # Fall back to a targeted local search (no live fetch on speculative hops)
        q_parts = [p for p in (doc_number, doc_hint, f"{article}-modda" if article else None) if p]
        if not q_parts:
            return [], live_fetched
        return await self.retrieve(
            " ".join(q_parts),
            top_k=5,
            rerank_top_k=2,
            filters=filters,
            hop=hop,
            enable_live_fallback=False,
        )

    # ------------------------------------------------------------------ fusion helpers
    @staticmethod
    def _fuse_lexical(
        lists: list[list[RetrievedChunk]], weights: list[float] | None = None, k: int = 30
    ) -> list[RetrievedChunk]:
        """Reciprocal-rank fuse several BM25 result lists (question, re-phrasings, act-scoped search)."""
        if len(lists) == 1:
            return lists[0]
        weights = weights or [1.0] + [1.15] * (len(lists) - 1)
        merged: dict[str, tuple[float, RetrievedChunk]] = {}
        for weight, hits in zip(weights, lists):
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
        for weight, hits in ((dense_weight, dense_hits), (bm25_weight, bm25_hits)):
            for rank, item in enumerate(hits, start=1):
                cid = item.chunk.chunk_id
                rrf = weight / (k + rank)
                if cid not in merged:
                    merged[cid] = item.model_copy(
                        update={"rrf_score": rrf, "final_score": rrf, "retrieval_hop": hop, "retrieval_source": "hybrid"}
                    )
                else:
                    merged[cid].dense_score = max(merged[cid].dense_score, item.dense_score)
                    merged[cid].bm25_score = max(merged[cid].bm25_score, item.bm25_score)
                    merged[cid].rrf_score += rrf
                    merged[cid].final_score = merged[cid].rrf_score
        fused = list(merged.values())
        fused.sort(key=lambda r: r.rrf_score, reverse=True)
        return fused

    # ------------------------------------------------------------------ live fallback
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
