"""BM25 + exact-ID legal retrieval over `backend/app/legal_data/instruments.json` (no vector DB needed)."""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from rank_bm25 import BM25Okapi

from app.engines.translit import latin_to_cyrillic


class LegalInstrumentStore:
    """In-memory BM25 + ID lookup over versioned Uzbekistan statutory instruments."""

    def __init__(self, path: Path | None = None) -> None:
        target = path or (Path(__file__).resolve().parent.parent / "legal_data" / "instruments.json")
        self.items: list[dict[str, Any]] = json.loads(target.read_text(encoding="utf-8"))
        self.by_id: dict[str, dict[str, Any]] = {it["id"]: it for it in self.items}
        tokenized = [self._tokenize(self._doc_text(it)) for it in self.items]
        self._bm25 = BM25Okapi(tokenized) if tokenized else None

    @staticmethod
    def _doc_text(it: dict[str, Any]) -> str:
        return " ".join(
            [
                it.get("id", ""),
                it.get("instrument", ""),
                it.get("article", ""),
                it.get("title_uz", ""),
                it.get("summary_uz", ""),
                it.get("summary_ru", ""),
                it.get("source_ref", ""),
            ]
        )

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        return re.findall(r"[a-zA-Z0-9\u0400-\u04ff'-]+", text.lower())

    def resolve_ids(self, ids: list[str], locale: str = "uz_lat") -> list[dict[str, Any]]:
        """Resolve legal_ref IDs into localized citation cards; never returns unknown IDs."""
        out: list[dict[str, Any]] = []
        seen: set[str] = set()
        for rid in ids:
            if rid in seen or rid not in self.by_id:
                continue
            seen.add(rid)
            it = self.by_id[rid]
            title = it["title_uz"] if locale != "uz_cyr" else latin_to_cyrillic(it["title_uz"])
            if locale == "ru":
                summary = it["summary_ru"]
            elif locale == "uz_cyr":
                summary = latin_to_cyrillic(it["summary_uz"])
            else:
                summary = it["summary_uz"]
            out.append(
                {
                    "id": it["id"],
                    "instrument": latin_to_cyrillic(it["instrument"]) if locale == "uz_cyr" else it["instrument"],
                    "article": latin_to_cyrillic(it["article"]) if locale == "uz_cyr" else it["article"],
                    "title": title,
                    "summary": summary,
                    "effectiveFrom": it["effective_from"],
                    "sourceRef": it["source_ref"],
                    "sourceUrl": it.get("source_url"),
                    "status": it["status"],
                }
            )
        return out

    def search(self, query: str, *, top_k: int = 4, locale: str = "uz_lat") -> list[dict[str, Any]]:
        if not self._bm25:
            return []
        q_toks = self._tokenize(query)
        if not q_toks:
            return []
        scores = self._bm25.get_scores(q_toks)
        ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)
        top_ids = [self.items[idx]["id"] for idx, sc in ranked[:top_k] if sc > 0]
        return self.resolve_ids(top_ids, locale=locale)


@lru_cache(maxsize=1)
def get_instrument_store() -> LegalInstrumentStore:
    return LegalInstrumentStore()
