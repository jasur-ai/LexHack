"""High-speed SQLite FTS5 BM25 exact keyword & article-number store (<10ms queries across 100k+ chunks)."""

from __future__ import annotations

import logging
import re
import sqlite3
from pathlib import Path

from lex_agent.language.transliterator import normalize_uzbek_apostrophes, to_searchable_uzbek_latin
from lex_agent.models import LegalChunk, NormStatus, RetrievalFilter, RetrievedChunk

logger = logging.getLogger(__name__)

_TOKEN_RE = re.compile(r"[a-zA-Z0-9\u0400-\u04ff'-]+", re.UNICODE)

# High-frequency legal & conversational stopwords across UZ / RU / EN that pollute OR queries
_STOPWORDS = {
    # UZ Latin
    "va", "ham", "hamda", "yoki", "uchun", "bilan", "bo'yicha", "haqida", "to'g'risida",
    "qanday", "nima", "qancha", "qaysi", "kerak", "mumkin", "bo'lsa", "bo'lgan", "ushbu",
    "bu", "shu", "u", "ular", "uning", "boshqa", "asosida", "muvofiq", "tartibda", "holatda",
    "qilish", "berish", "olish", "etish", "bo'lish", "o'zbekiston", "respublikasi", "respublikasining",
    # RU
    "и", "в", "во", "на", "по", "с", "со", "к", "о", "об", "от", "до", "за", "из", "для", "при",
    "или", "как", "что", "какой", "какие", "сколько", "нужно", "можно", "если", "при", "это",
    "республики", "узбекистан", "узбекистана", "согласно", "порядке", "случае", "настоящего",
    # EN
    "the", "and", "for", "with", "that", "this", "from", "are", "was", "were", "what", "how",
    "does", "under", "about", "into", "uzbekistan", "republic", "law", "code", "article",
}


def legal_tokenize(text: str, *, drop_stopwords: bool = False) -> list[str]:
    """Tokenize legal text while preserving article numbers, act codes (O'RQ-682), and UZ Latin mirrors."""
    norm = normalize_uzbek_apostrophes(text).lower()
    latin_mirror = to_searchable_uzbek_latin(norm).lower()
    combined = norm if latin_mirror == norm else f"{norm} {latin_mirror}"
    raw_tokens = _TOKEN_RE.findall(combined)

    tokens: list[str] = []
    seen: set[str] = set()

    def _emit(t: str) -> None:
        if not t or (drop_stopwords and t in _STOPWORDS):
            return
        if not drop_stopwords or t not in seen:
            seen.add(t)
            tokens.append(t)

    for tok in raw_tokens:
        tok = tok.strip("'-")
        if not tok:
            continue
        _emit(tok)
        m = re.match(r"^(\d+(?:[-.]\d+)?)-(?:modda|модда|band|банд)$", tok)
        if m:
            _emit(m.group(1))
        if tok.startswith(("ўрқ-", "зру-")):
            _emit("o'rq-" + tok.split("-", 1)[1])
        elif tok.startswith(("пф-", "уп-")):
            _emit("pf-" + tok.split("-", 1)[1])
        elif tok.startswith(("пқ-", "пп-")):
            _emit("pq-" + tok.split("-", 1)[1])
        elif tok.startswith(("вмқ-", "пкм-")):
            _emit("vmq-" + tok.split("-", 1)[1])
    return tokens


def chunk_matches_filter(chunk: LegalChunk, flt: RetrievalFilter | None) -> bool:
    """Apply language, hierarchy, status, branch, article, and temporal validity filters."""
    if flt is None:
        return True

    if flt.languages and chunk.language not in flt.languages:
        return False
    if flt.doc_types and chunk.doc_type not in flt.doc_types:
        return False
    if flt.doc_ids and chunk.doc_id not in flt.doc_ids and chunk.canonical_id not in flt.doc_ids:
        return False
    if flt.min_legal_force_rank is not None and chunk.legal_force_rank < flt.min_legal_force_rank:
        return False
    if flt.branches and not any(b in flt.branches for b in chunk.branches):
        return False
    if flt.statuses and chunk.status not in flt.statuses:
        return False
    if flt.article_number:
        target = re.sub(r"[^\d.-]", "", flt.article_number)
        if not chunk.article or target not in chunk.article:
            return False

    if flt.as_of_date is not None:
        if chunk.effective_date and chunk.effective_date > flt.as_of_date:
            return False
        if chunk.expiry_date and chunk.expiry_date <= flt.as_of_date:
            return False
    elif not flt.include_repealed and chunk.status == NormStatus.REPEALED:
        return False

    return True


def _sanitize_fts_term(term: str, *, prefix_stem: bool = False) -> str:
    cleaned = re.sub(r'["*():^]', "", term).strip()
    if not cleaned:
        return ""
    # Uzbek & Russian are richly inflected (aliment -> alimentni/alimentlar, бо'shatish -> bo'shatishda).
    # Prefix matching on stems >= 6 chars dramatically boosts recall without hurting precision.
    if prefix_stem and len(cleaned) >= 6 and cleaned.isalpha():
        stem = cleaned[: max(5, len(cleaned) - 2)]
        return f'"{stem}"*'
    return f'"{cleaned}"'


def _build_fts_queries(query: str) -> list[str]:
    """Build precision-first (exact AND) -> morphological stem AND -> broad OR FTS5 MATCH queries."""
    tokens = legal_tokenize(query, drop_stopwords=True)
    if not tokens:
        tokens = legal_tokenize(query, drop_stopwords=False)
    clean_terms = [t for t in tokens if len(t) >= 2 or t.isdigit()][:10]
    if not clean_terms:
        return []

    exact_quoted = [q for q in (_sanitize_fts_term(t, prefix_stem=False) for t in clean_terms) if q]
    stem_quoted = [q for q in (_sanitize_fts_term(t, prefix_stem=True) for t in clean_terms) if q]
    if not exact_quoted:
        return []

    queries: list[str] = []
    if len(exact_quoted) >= 2:
        queries.append(" AND ".join(exact_quoted[:4]))
        if stem_quoted != exact_quoted:
            queries.append(" AND ".join(stem_quoted[:4]))
    queries.append(" OR ".join(stem_quoted))
    return list(dict.fromkeys(queries))


class BM25Store:
    """SQLite-persisted chunk store with C-speed FTS5 BM25 full-text search and exact doc/article SQL lookup."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._fts_ready = False
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS chunks (
                    chunk_id TEXT PRIMARY KEY,
                    doc_id TEXT NOT NULL,
                    canonical_id TEXT NOT NULL,
                    language TEXT NOT NULL,
                    doc_type TEXT NOT NULL,
                    doc_number TEXT,
                    article TEXT,
                    status TEXT NOT NULL,
                    legal_force_rank INTEGER NOT NULL,
                    effective_date TEXT,
                    expiry_date TEXT,
                    chunk_json TEXT NOT NULL
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_chunks_doc_id ON chunks(doc_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_chunks_canonical ON chunks(canonical_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_chunks_doc_number ON chunks(doc_number)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_chunks_article ON chunks(article)")

            # Native C-speed SQLite FTS5 index with BM25 ranking
            conn.execute(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
                    chunk_id UNINDEXED,
                    doc_title,
                    doc_number,
                    article,
                    body,
                    tokenize='unicode61 remove_diacritics 2'
                )
                """
            )

    def _ensure_fts_synced(self) -> None:
        """One-time fast backfill of FTS5 table if existing chunks predate FTS5 creation."""
        if self._fts_ready:
            return
        with self._connect() as conn:
            total_chunks = int(conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0])
            total_fts = int(conn.execute("SELECT COUNT(*) FROM chunks_fts").fetchone()[0])
            if total_chunks > 0 and total_fts < total_chunks:
                logger.info("Building fast SQLite FTS5 BM25 index for %d existing chunks (one-time)...", total_chunks)
                conn.execute("DELETE FROM chunks_fts")
                cursor = conn.execute("SELECT chunk_id, chunk_json FROM chunks")
                batch: list[tuple[str, str, str, str, str]] = []
                for row in cursor:
                    c = LegalChunk.model_validate_json(row["chunk_json"])
                    body = c.text if not c.normalized_text or c.normalized_text == c.text else f"{c.text}\n{c.normalized_text}"
                    batch.append((c.chunk_id, c.doc_title, c.doc_number or "", c.article or "", body))
                    if len(batch) >= 1000:
                        conn.executemany(
                            "INSERT INTO chunks_fts(chunk_id, doc_title, doc_number, article, body) VALUES (?, ?, ?, ?, ?)",
                            batch,
                        )
                        batch.clear()
                if batch:
                    conn.executemany(
                        "INSERT INTO chunks_fts(chunk_id, doc_title, doc_number, article, body) VALUES (?, ?, ?, ?, ?)",
                        batch,
                    )
                logger.info("SQLite FTS5 BM25 index ready (%d chunks).", total_chunks)
        self._fts_ready = True

    def upsert_chunks(self, chunks: list[LegalChunk]) -> None:
        if not chunks:
            return
        rows = [
            (
                c.chunk_id,
                c.doc_id,
                c.canonical_id,
                c.language.value,
                c.doc_type.value,
                c.doc_number,
                c.article,
                c.status.value,
                c.legal_force_rank,
                c.effective_date.isoformat() if c.effective_date else None,
                c.expiry_date.isoformat() if c.expiry_date else None,
                c.model_dump_json(),
            )
            for c in chunks
        ]
        fts_rows = [
            (
                c.chunk_id,
                c.doc_title,
                c.doc_number or "",
                c.article or "",
                c.text if not c.normalized_text or c.normalized_text == c.text else f"{c.text}\n{c.normalized_text}",
            )
            for c in chunks
        ]
        chunk_ids = [(c.chunk_id,) for c in chunks]
        with self._connect() as conn:
            conn.executemany(
                """
                INSERT OR REPLACE INTO chunks (
                    chunk_id, doc_id, canonical_id, language, doc_type, doc_number,
                    article, status, legal_force_rank, effective_date, expiry_date, chunk_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
            conn.executemany("DELETE FROM chunks_fts WHERE chunk_id = ?", chunk_ids)
            conn.executemany(
                "INSERT INTO chunks_fts(chunk_id, doc_title, doc_number, article, body) VALUES (?, ?, ?, ?, ?)",
                fts_rows,
            )
        self._fts_ready = True

    def count(self) -> int:
        with self._connect() as conn:
            return int(conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0])

    def rebuild_index(self) -> int:
        """Ensure FTS5 index is synced and optimized."""
        self._fts_ready = False
        self._ensure_fts_synced()
        return self.count()

    def search(
        self,
        query: str,
        *,
        top_k: int = 12,
        filters: RetrievalFilter | None = None,
    ) -> list[RetrievedChunk]:
        """Execute C-speed SQLite FTS5 BM25 search with exact article & act-number precision boosting."""
        self._ensure_fts_synced()
        fts_queries = _build_fts_queries(query)
        if not fts_queries:
            return []

        art_nums = set(
            re.findall(
                r"\b(\d+(?:[-.]\d+)?)\s*-?\s*(?:modda|модда)|(?:ст\.|стать\w+|article)\s*(\d+(?:[-.]\d+)?)\b",
                query,
                re.I,
            )
        )
        flat_art_nums = {a or b for a, b in art_nums if (a or b)}
        doc_nums = {
            m.upper()
            for m in re.findall(
                r"\b(?:O'RQ|ЎРҚ|ЗРУ|PF|ПФ|УП|PQ|ПҚ|ПП|VMQ|ВМҚ|ПКМ)-?\d+\b",
                normalize_uzbek_apostrophes(query),
                re.I,
            )
        }

        collected: dict[str, tuple[float, LegalChunk]] = {}
        fetch_limit = max(top_k * 5, 40)

        with self._connect() as conn:
            for q_idx, fts_q in enumerate(fts_queries):
                # Precision bonus for AND query matches (q_idx == 0 when len(fts_queries) == 2)
                and_bonus = 1.6 if (q_idx == 0 and len(fts_queries) > 1) else 1.0
                try:
                    rows = conn.execute(
                        """
                        SELECT c.chunk_json, bm25(chunks_fts, 0.0, 4.0, 5.0, 4.5, 1.0) AS rank_score
                        FROM chunks_fts
                        JOIN chunks c ON c.chunk_id = chunks_fts.chunk_id
                        WHERE chunks_fts MATCH ?
                        ORDER BY rank_score
                        LIMIT ?
                        """,
                        (fts_q, fetch_limit),
                    ).fetchall()
                except sqlite3.OperationalError as exc:
                    logger.debug("FTS5 query '%s' skipped: %s", fts_q, exc)
                    continue

                for row in rows:
                    chunk = LegalChunk.model_validate_json(row["chunk_json"])
                    if not chunk_matches_filter(chunk, filters):
                        continue
                    # SQLite bm25() returns negative numbers where MORE NEGATIVE = BETTER MATCH
                    raw_bm25 = max(0.01, -float(row["rank_score"])) * and_bonus

                    if flat_art_nums and chunk.article:
                        m = re.search(r"(\d+(?:[-.]\d+)?)", chunk.article)
                        if m and m.group(1) in flat_art_nums:
                            raw_bm25 *= 2.2
                    if doc_nums and chunk.doc_number and chunk.doc_number.upper() in doc_nums:
                        raw_bm25 *= 2.5

                    prev = collected.get(chunk.chunk_id)
                    if prev is None or raw_bm25 > prev[0]:
                        collected[chunk.chunk_id] = (raw_bm25, chunk)

                # If strict AND query already found plenty of exact hits, no need to scan broad OR!
                if q_idx == 0 and len(collected) >= top_k:
                    break

        scored_items = sorted(collected.values(), key=lambda x: x[0], reverse=True)
        return [
            RetrievedChunk(
                chunk=chunk,
                bm25_score=score,
                final_score=score,
                retrieval_source="bm25_fts5",
            )
            for score, chunk in scored_items[:top_k]
        ]

    def get_chunks_by_doc(
        self,
        doc_id: str,
        *,
        article: str | None = None,
        limit: int = 30,
    ) -> list[LegalChunk]:
        """Exact SQL lookup for all chunks (across UZ/RU/EN) belonging to a `doc_id` or `canonical_id`."""
        with self._connect() as conn:
            if article:
                art_num = re.sub(r"[^\d.-]", "", article)
                rows = conn.execute(
                    """
                    SELECT chunk_json FROM chunks
                    WHERE (doc_id = ? OR canonical_id = ?) AND article LIKE ?
                    LIMIT ?
                    """,
                    (doc_id, doc_id, f"%{art_num}%", limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT chunk_json FROM chunks WHERE doc_id = ? OR canonical_id = ? LIMIT ?",
                    (doc_id, doc_id, limit),
                ).fetchall()
        return [LegalChunk.model_validate_json(r["chunk_json"]) for r in rows]

    def find_by_doc_number(self, doc_number: str, *, article: str | None = None, limit: int = 10) -> list[LegalChunk]:
        """Exact lookup by normative act number (e.g. O'RQ-682, PF-158, VMQ-123)."""
        clean_num = normalize_uzbek_apostrophes(doc_number).upper().strip()
        with self._connect() as conn:
            if article:
                art_num = re.sub(r"[^\d.-]", "", article)
                rows = conn.execute(
                    """
                    SELECT chunk_json FROM chunks
                    WHERE UPPER(doc_number) LIKE ? AND article LIKE ?
                    LIMIT ?
                    """,
                    (f"%{clean_num}%", f"%{art_num}%", limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT chunk_json FROM chunks WHERE UPPER(doc_number) LIKE ? LIMIT ?",
                    (f"%{clean_num}%", limit),
                ).fetchall()
        return [LegalChunk.model_validate_json(r["chunk_json"]) for r in rows]
