"""Second-stage legal reranker.

Candidates from BM25 (question, statutory re-phrasings, act-scoped search), exact article lookups, situation
lexicon targets and — when enabled — dense search are re-scored with features computed on the same analysed
terms the index uses: IDF-weighted coverage of the question by the article title, chapter heading, body and act
title; title precision; ranks in the individual result lists; whether the situation lexicon or the question
itself points at the article; legal force; plus penalties for repealed norms and generic definition articles.

Scoring order of preference:

1. a LightGBM ranking model trained on question→article pairs (``scripts/train_reranker.py``) and shipped as
   ``lex_agent/data/reranker_model.json`` — evaluated in pure Python, LightGBM is not needed at runtime;
2. an optional neural cross-encoder (``RERANKER_BACKEND=cross_encoder`` + the ``[ml]`` extra; large hosts only);
3. a hand-tuned linear scorer (always available, no dependencies).
"""

from __future__ import annotations

import importlib.util
import json
import logging
import math
import re
import threading
from collections import OrderedDict
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from lex_agent.chunk_text import article_body, chunk_article_id, is_definitions_article, short_act_title
from lex_agent.config import Settings, get_settings
from lex_agent.language.stopwords import stop_terms
from lex_agent.language.textproc import index_terms
from lex_agent.models import DocumentType, NormStatus, RetrievedChunk

logger = logging.getLogger(__name__)

MODEL_PATH = Path(__file__).resolve().parents[1] / "data" / "reranker_model.json"

FEATURE_NAMES: tuple[str, ...] = (
    "bm25_norm",
    "bm25_rank_inv",
    "exp_rank_inv",
    "scoped_rank_inv",
    "syn_rank_inv",
    "rrf",
    "dense",
    "cov_body",
    "cov_art_title",
    "cov_heading",
    "cov_doc_title",
    "art_title_precision",
    "cov_all",
    "matched_ratio",
    "query_terms",
    "exp_cov_title",
    "exp_cov_body",
    "art_mention",
    "act_mention",
    "doc_number_mention",
    "concept_target",
    "concept_doc",
    "first_part",
    "definitions",
    "repealed",
    "doc_type_rank",
    "lang_match",
    "body_len_log",
    "article_num_log",
    "title_terms",
    "title_extra",
)

_DOC_TYPE_RANK = {
    DocumentType.CONSTITUTION: 1.0,
    DocumentType.CODE: 0.85,
    DocumentType.CONSTITUTIONAL_LAW: 0.75,
    DocumentType.LAW: 0.6,
}

_ART_MENTION_RE = re.compile(
    r"\b(\d+(?:[-.]\d+)?)\s*[¹²³⁴⁵⁶⁷⁸⁹]?\s*-?\s*(?:modda|модда|moddasi|моддаси)|"
    r"(?:ст\.|стать\w*|article|art\.)\s*(\d+(?:[-.]\d+)?)\b",
    re.I,
)


@dataclass(slots=True)
class QueryInfo:
    """Analysed question shared by all candidates of one rerank call."""

    text: str
    terms: list[str]
    weights: dict[str, float]
    expansion_terms: set[str] = field(default_factory=set)
    article_mentions: set[str] = field(default_factory=set)
    doc_numbers: set[str] = field(default_factory=set)
    language: str = "uz_latn"
    doc_priors: dict[str, float] = field(default_factory=dict)
    concept_targets: dict[tuple[str, str], float] = field(default_factory=dict)
    concept_docs: set[str] = field(default_factory=set)
    list_ranks: dict[str, dict[str, int]] = field(default_factory=dict)
    idf_lookup: Callable[[Iterable[str]], dict[str, float]] | None = None

    @property
    def total_weight(self) -> float:
        return sum(self.weights.get(t, 1.0) for t in self.terms) or 1.0


@dataclass(slots=True)
class ChunkTerms:
    body: frozenset[str]
    art_title: frozenset[str]
    heading: frozenset[str]
    doc_title: frozenset[str]
    body_len: int


class _LRU:
    def __init__(self, size: int) -> None:
        self.size = size
        self.data: OrderedDict[str, ChunkTerms] = OrderedDict()
        self.lock = threading.Lock()

    def get(self, key: str) -> ChunkTerms | None:
        with self.lock:
            val = self.data.get(key)
            if val is not None:
                self.data.move_to_end(key)
            return val

    def put(self, key: str, val: ChunkTerms) -> None:
        with self.lock:
            self.data[key] = val
            self.data.move_to_end(key)
            while len(self.data) > self.size:
                self.data.popitem(last=False)


_TERM_CACHE = _LRU(20_000)


def chunk_terms(cand: RetrievedChunk) -> ChunkTerms:
    from lex_agent.retrieval.bm25_store import heading_text

    c = cand.chunk
    cached = _TERM_CACHE.get(c.chunk_id)
    if cached is not None:
        return cached
    lang = c.language.value
    body = article_body(c)[:2400]
    terms = ChunkTerms(
        body=frozenset(index_terms(body, language=lang)),
        art_title=frozenset(index_terms(c.article_title or "", language=lang)),
        heading=frozenset(index_terms(heading_text(c), language=lang)),
        doc_title=frozenset(index_terms(f"{short_act_title(c)} {c.doc_title}", language=lang)),
        body_len=len(body),
    )
    _TERM_CACHE.put(c.chunk_id, terms)
    return terms


def article_mentions(text: str) -> set[str]:
    return {(a or b).replace("-", ".") for a, b in _ART_MENTION_RE.findall(text) if (a or b)}


def article_key(cand: RetrievedChunk) -> tuple[str, str]:
    return cand.chunk.canonical_id, chunk_article_id(cand.chunk)


def build_query_info(
    query: str,
    *,
    terms: list[str],
    idf: dict[str, float] | None = None,
    expansion_terms: set[str] | None = None,
    language: str = "uz_latn",
    doc_numbers: set[str] | None = None,
    doc_priors: dict[str, float] | None = None,
    concept_targets: dict[tuple[str, str], float] | None = None,
    concept_docs: set[str] | None = None,
    list_ranks: dict[str, dict[str, int]] | None = None,
    idf_lookup: Callable[[Iterable[str]], dict[str, float]] | None = None,
) -> QueryInfo:
    idf = idf or {}
    weights = {t: max(0.2, idf.get(t, 3.0)) for t in terms}
    return QueryInfo(
        text=query,
        terms=terms,
        weights=weights,
        expansion_terms=set(expansion_terms or set()) - set(terms),
        article_mentions=article_mentions(query),
        doc_numbers=set(doc_numbers or set()),
        language=language,
        doc_priors=dict(doc_priors or {}),
        concept_targets=dict(concept_targets or {}),
        concept_docs=set(concept_docs or set()),
        list_ranks=dict(list_ranks or {}),
        idf_lookup=idf_lookup,
    )


def _rank_inv(ranks: dict[str, int] | None, chunk_id: str) -> float:
    if not ranks:
        return 0.0
    r = ranks.get(chunk_id)
    return 1.0 / (1.0 + r) if r is not None else 0.0


def candidate_features(q: QueryInfo, cand: RetrievedChunk, *, max_bm25: float) -> list[float]:
    """Feature vector (order = ``FEATURE_NAMES``) for one candidate."""
    ct = chunk_terms(cand)
    c = cand.chunk
    tw = q.total_weight

    def cov(bag: frozenset[str]) -> float:
        return sum(q.weights.get(t, 1.0) for t in q.terms if t in bag) / tw

    all_terms = ct.body | ct.art_title | ct.heading | ct.doc_title
    matched = [t for t in q.terms if t in all_terms]
    qset = set(q.terms)
    precision = (len(ct.art_title & qset) / len(ct.art_title)) if ct.art_title else 0.0
    # Share of the article title (by informativeness) the question does not ask about: "Merosning ochilish
    # joyi" for "Meros qachon ochiladi?" carries an extra specific word ("joy") that "Merosning ochilishi" lacks.
    title_extra = 0.0
    if ct.art_title and q.idf_lookup is not None:
        idfs = q.idf_lookup(ct.art_title)
        total = sum(idfs.values()) or 1.0
        title_extra = sum(v for t, v in idfs.items() if t not in qset and t not in q.expansion_terms) / total
    art_id = chunk_article_id(c)
    art_hit = 1.0 if (q.article_mentions and art_id and art_id in q.article_mentions) else 0.0
    num_hit = 0.0
    if q.doc_numbers and c.doc_number:
        from lex_agent.retrieval.bm25_store import number_tokens

        num_hit = 1.0 if number_tokens(c.doc_number) in q.doc_numbers else 0.0
    if q.expansion_terms:
        n_exp = len(q.expansion_terms)
        exp_title = len(q.expansion_terms & (ct.art_title | ct.heading)) / n_exp
        exp_body = len(q.expansion_terms & ct.body) / n_exp
    else:
        exp_title = exp_body = 0.0
    lang = c.language.value
    if q.language == "ru":
        lang_match = 1.0 if lang == "ru" else 0.0
    elif q.language == "en":
        lang_match = 0.5
    else:
        lang_match = 1.0 if lang in ("uz_latn", "uz_cyrl") else 0.0
    try:
        art_num = float(art_id.split(".")[0]) if art_id and art_id[0].isdigit() else 0.0
    except ValueError:
        art_num = 0.0
    cid = c.chunk_id
    concept_w = q.concept_targets.get((c.canonical_id, art_id or ""), 0.0)
    return [
        (cand.bm25_score / max_bm25) if max_bm25 > 0 else 0.0,
        _rank_inv(q.list_ranks.get("main"), cid),
        max(_rank_inv(q.list_ranks.get(k), cid) for k in q.list_ranks if k.startswith("exp")) if any(
            k.startswith("exp") for k in q.list_ranks
        ) else 0.0,
        _rank_inv(q.list_ranks.get("scoped"), cid),
        _rank_inv(q.list_ranks.get("syn"), cid),
        cand.rrf_score,
        cand.dense_score,
        cov(ct.body),
        cov(ct.art_title),
        cov(ct.heading),
        cov(ct.doc_title),
        precision,
        cov(all_terms),
        len(matched) / max(len(q.terms), 1),
        float(len(q.terms)),
        exp_title,
        exp_body,
        art_hit,
        q.doc_priors.get(c.canonical_id, 0.0),
        num_hit,
        concept_w,
        1.0 if c.canonical_id in q.concept_docs else 0.0,
        1.0 if not c.clause or str(c.clause).startswith("1/") else 0.0,
        1.0 if is_definitions_article(c) else 0.0,
        1.0 if c.status == NormStatus.REPEALED else 0.0,
        _DOC_TYPE_RANK.get(c.doc_type, 0.4),
        lang_match,
        math.log1p(ct.body_len),
        math.log1p(art_num),
        float(len(ct.art_title)),
        title_extra,
    ]


def heuristic_score(f: list[float]) -> float:
    """Hand-tuned linear scorer over ``candidate_features`` (used when no trained model is available)."""
    x = dict(zip(FEATURE_NAMES, f))
    return (
        0.30 * x["bm25_norm"]
        + 0.25 * x["bm25_rank_inv"]
        + 0.25 * x["exp_rank_inv"]
        + 0.20 * x["scoped_rank_inv"]
        + 0.10 * x["syn_rank_inv"]
        + 0.32 * x["cov_body"]
        + 0.30 * x["cov_art_title"]
        + 0.12 * x["cov_heading"]
        + 0.10 * x["cov_doc_title"]
        + 0.25 * x["art_title_precision"]
        - 0.25 * x["title_extra"]
        + 0.15 * x["exp_cov_title"]
        + 0.10 * x["exp_cov_body"]
        + 0.80 * x["art_mention"] * max(x["act_mention"], 0.5)
        + 0.25 * x["act_mention"]
        + 0.25 * x["doc_number_mention"]
        + 0.55 * x["concept_target"]
        + 0.08 * x["concept_doc"]
        + 0.02 * x["first_part"]
        - 0.10 * x["definitions"]
        - 0.40 * x["repealed"]
        + 0.12 * x["doc_type_rank"]
        + 0.05 * x["lang_match"]
    )


class TreeEnsemble:
    """Minimal evaluator for a LightGBM model dumped with ``Booster.dump_model()`` (no LightGBM needed)."""

    def __init__(self, dump: dict[str, Any]) -> None:
        self.feature_names: list[str] = list(dump.get("feature_names") or FEATURE_NAMES)
        self.trees = [t["tree_structure"] for t in dump.get("tree_info", [])]
        self.index = [FEATURE_NAMES.index(n) if n in FEATURE_NAMES else -1 for n in self.feature_names]
        self.meta: dict[str, Any] = dict(dump.get("lexhack_meta") or {})

    @classmethod
    def load(cls, path: Path) -> TreeEnsemble | None:
        if not path.exists():
            return None
        try:
            model = cls(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, ValueError, KeyError) as exc:
            logger.warning("Ignoring unreadable reranker model %s: %s", path, exc)
            return None
        if any(i < 0 for i in model.index):
            logger.warning("Reranker model %s was trained on other features; using the heuristic scorer.", path)
            return None
        return model

    def predict(self, features: list[float]) -> float:
        row = [features[i] for i in self.index]
        total = 0.0
        for node in self.trees:
            while "leaf_value" not in node:
                val = row[node["split_feature"]]
                thr = node["threshold"]
                if val != val:  # NaN: follow the default branch
                    go_left = bool(node.get("default_left", True))
                else:
                    go_left = val <= thr if node.get("decision_type", "<=") == "<=" else val < thr
                node = node["left_child"] if go_left else node["right_child"]
            total += float(node["leaf_value"])
        return total


class LegalReranker:
    """Reranks hybrid retrieval candidates so topical relevance dominates over raw legal hierarchy."""

    def __init__(self, settings: Settings | None = None, *, model_path: Path | None = None) -> None:
        self.settings = settings or get_settings()
        self._model: Any = None
        self._cross_encoder_unavailable = (
            not self.settings.reranker_enabled
            or self.settings.reranker_backend != "cross_encoder"
            or importlib.util.find_spec("sentence_transformers") is None
        )
        self.trees: TreeEnsemble | None = None
        if self.settings.reranker_enabled and self.settings.reranker_backend in ("auto", "trained"):
            self.trees = TreeEnsemble.load(model_path or MODEL_PATH)
            if self.trees is not None:
                logger.info("Trained reranker loaded (%d trees).", len(self.trees.trees))
            elif self.settings.reranker_backend == "trained":
                logger.warning("RERANKER_BACKEND=trained but no usable model was found; using the heuristic.")

    @property
    def backend(self) -> str:
        if self._model is not None:
            return "cross_encoder"
        if self.trees is not None:
            return "trained"
        return "heuristic"

    def _ensure_cross_encoder(self) -> Any | None:
        if self._cross_encoder_unavailable:
            return None
        if self._model is None:
            try:
                from sentence_transformers import CrossEncoder

                logger.info("Loading cross-encoder reranker: %s", self.settings.reranker_model)
                self._model = CrossEncoder(self.settings.reranker_model)
            except Exception as exc:  # pragma: no cover - optional heavy dependency
                logger.warning("CrossEncoder unavailable (%s); using the lightweight reranker.", exc)
                self._cross_encoder_unavailable = True
                return None
        return self._model

    def features(self, q: QueryInfo, candidates: list[RetrievedChunk]) -> list[list[float]]:
        max_bm25 = max((c.bm25_score for c in candidates), default=0.0) or 1.0
        return [candidate_features(q, cand, max_bm25=max_bm25) for cand in candidates]

    def score(self, q: QueryInfo, candidates: list[RetrievedChunk]) -> list[tuple[float, list[float]]]:
        out: list[tuple[float, list[float]]] = []
        for f in self.features(q, candidates):
            s = self.trees.predict(f) if self.trees is not None else heuristic_score(f)
            out.append((s, f))
        return out

    def rerank(
        self,
        query: str | QueryInfo,
        candidates: list[RetrievedChunk],
        *,
        top_k: int = 8,
    ) -> list[RetrievedChunk]:
        """Rerank candidates so topical relevance dominates and pure noise is dropped."""
        if not candidates:
            return []
        q = query if isinstance(query, QueryInfo) else self._query_info(query)

        model = self._ensure_cross_encoder()
        if model is not None:  # pragma: no cover - optional heavy dependency
            pairs = [(q.text, f"{c.chunk.doc_title} | {c.chunk.hierarchical_path}\n{c.chunk.text[:1600]}") for c in candidates]
            try:
                scores = model.predict(pairs)
                for cand, s in zip(candidates, scores):
                    penalty = -0.5 if cand.chunk.status == NormStatus.REPEALED else 0.0
                    cand.rerank_score = float(s)
                    cand.final_score = float(s) + (cand.chunk.legal_force_rank / 100.0) * 0.03 + penalty
                candidates.sort(key=lambda c: c.final_score, reverse=True)
                return candidates[:top_k]
            except Exception as exc:
                logger.warning("CrossEncoder inference failed (%s); falling back.", exc)

        kept: list[RetrievedChunk] = []
        idx = {n: i for i, n in enumerate(FEATURE_NAMES)}
        for cand, (s, f) in zip(candidates, self.score(q, candidates)):
            cand.rerank_score = s
            cand.final_score = s
            # Pure noise: nothing of the question appears in the article and nothing else points at it
            if (
                f[idx["cov_all"]] == 0.0
                and cand.bm25_score == 0.0
                and cand.dense_score < 0.55
                and not f[idx["art_mention"]]
                and not f[idx["concept_target"]]
            ):
                continue
            kept.append(cand)
        if not kept:
            kept = list(candidates)
        kept.sort(key=lambda c: c.final_score, reverse=True)
        return kept[:top_k]

    @staticmethod
    def _query_info(query: str) -> QueryInfo:
        from lex_agent.language.textproc import query_terms
        from lex_agent.language.transliterator import detect_language

        lang = detect_language(query).value
        stops = stop_terms(lang)
        terms = [t for t in dict.fromkeys(query_terms(query, language=lang)) if t not in stops]
        return build_query_info(query, terms=terms, language=lang)
