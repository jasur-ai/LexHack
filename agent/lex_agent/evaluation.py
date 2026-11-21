"""Retrieval quality evaluation against a hand-labelled gold set (``eval/retrieval_gold.jsonl``).

Each gold line: ``{"q": question, "lang": "uz_latn|uz_cyrl|ru", "expect": [[canonical_doc_id, [article ids | "*"]], ...]}``.
A hit means one of the top-k retrieved chunks belongs to an expected document and article.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from lex_agent.chunk_text import chunk_article_id
from lex_agent.models import RetrievedChunk

DEFAULT_GOLD = Path(__file__).resolve().parents[1] / "eval" / "retrieval_gold.jsonl"


def _article_id(item: RetrievedChunk) -> str:
    return chunk_article_id(item.chunk)


def _matches(item: RetrievedChunk, expect: list[list[Any]]) -> bool:
    for doc, arts in expect:
        if item.chunk.canonical_id != doc and item.chunk.doc_id.lstrip("-") != doc:
            continue
        if "*" in arts or _article_id(item) in {str(a) for a in arts}:
            return True
    return False


def load_gold(gold_path: Path = DEFAULT_GOLD, *, split: str | None = None) -> list[dict[str, Any]]:
    rows = [json.loads(line) for line in gold_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if split and split != "all":
        rows = [r for r in rows if r.get("split", "dev") == split]
    return rows


def _rate(group: list[dict[str, Any]], k: int) -> dict[str, float]:
    n = max(len(group), 1)
    return {
        "n": len(group),
        "hit@1": round(sum(1 for g in group if g["rank"] == 1) / n, 3),
        f"hit@{k}": round(sum(1 for g in group if g["rank"]) / n, 3),
    }


async def evaluate_retrieval(
    retriever: Any, gold_path: Path = DEFAULT_GOLD, *, k: int = 5, split: str | None = None
) -> dict[str, Any]:
    rows = load_gold(gold_path, split=split)
    per_query: list[dict[str, Any]] = []
    hits_at_1 = hits_at_k = 0
    rr_sum = 0.0
    latencies: list[float] = []
    for row in rows:
        t0 = time.perf_counter()
        results, _ = await retriever.retrieve(
            row["q"], top_k=retriever.settings.agent_top_k, rerank_top_k=max(k, 8), enable_live_fallback=False
        )
        latencies.append((time.perf_counter() - t0) * 1000)
        rank = next((i for i, r in enumerate(results[:k], start=1) if _matches(r, row["expect"])), None)
        if rank == 1:
            hits_at_1 += 1
        if rank:
            hits_at_k += 1
            rr_sum += 1.0 / rank
        per_query.append(
            {
                "q": row["q"],
                "lang": row.get("lang"),
                "domain": row.get("domain", ""),
                "split": row.get("split", "dev"),
                "typo": bool(row.get("typo")),
                "rank": rank,
                "top": [f"{(r.chunk.extra or {}).get('short_title', r.chunk.doc_title)} {r.chunk.article}" for r in results[:3]],
            }
        )
    n = max(len(rows), 1)
    latencies.sort()
    breakdown: dict[str, dict[str, dict[str, float]]] = {"lang": {}, "domain": {}, "split": {}, "typo": {}}
    for key in ("lang", "domain", "split"):
        for value in sorted({str(q[key]) for q in per_query}):
            breakdown[key][value] = _rate([q for q in per_query if str(q[key]) == value], k)
    for value in (True, False):
        group = [q for q in per_query if q["typo"] is value]
        if group:
            breakdown["typo"]["with_typos" if value else "clean"] = _rate(group, k)
    return {
        "queries": len(rows),
        "hit@1": round(hits_at_1 / n, 3),
        f"hit@{k}": round(hits_at_k / n, 3),
        f"mrr@{k}": round(rr_sum / n, 3),
        "p50_ms": round(latencies[len(latencies) // 2], 1) if latencies else 0.0,
        "p95_ms": round(latencies[max(int(len(latencies) * 0.95) - 1, 0)], 1) if latencies else 0.0,
        "breakdown": breakdown,
        "misses": [q for q in per_query if not q["rank"]],
        "per_query": per_query,
    }
