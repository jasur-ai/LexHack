"""High-speed SQLite FTS5 BM25 exact keyword & article-number store (<10ms queries across 100k+ chunks)."""

from __future__ import annotations

import logging
import re
import sqlite3
from pathlib import Path

from lex_agent.language.transliterator import (
    normalize_uzbek_apostrophes,
    to_searchable_uzbek_latin,
)
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
    """SQLite-persisted chunk store with C-speed FTS5 BM25 full-text search and exact doc/article SQL lookup.

    Schema: ``chunks`` (one row per chunk, integer ``rid`` primary key) and the ``chunks_fts`` FTS5 table whose
    ``rowid`` equals ``chunks.rid``. Article titles live in their own heavily weighted FTS column because they are
    the most precise summary of what a norm regulates.
    """

    _FTS_COLUMNS = ("doc_title", "doc_number", "article", "article_title", "body")

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._fts_ready = False
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            cols = [r["name"] for r in conn.execute("PRAGMA table_info(chunks)").fetchall()]
            fts_cols = [r["name"] for r in conn.execute("PRAGMA table_info(chunks_fts)").fetchall()]
            if (cols and "rid" not in cols) or (fts_cols and "article_title" not in fts_cols):
                # Legacy cache layout (pre-2026.11): it only ever held re-fetchable data, so rebuild it.
                logger.warning("Upgrading legacy BM25 index layout at %s (cached chunks will be rebuilt).", self.db_path)
                conn.execute("DROP TABLE IF EXISTS chunks_fts")
                conn.execute("DROP TABLE IF EXISTS chunks")
                conn.execute("DROP TABLE IF EXISTS index_meta")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS chunks (
                    rid INTEGER PRIMARY KEY AUTOINCREMENT,
                    chunk_id TEXT NOT NULL UNIQUE,
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
            conn.execute(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
                    doc_title,
                    doc_number,
                    article,
                    article_title,
                    body,
                    tokenize='unicode61 remove_diacritics 2'
                )
                """
            )
            conn.execute("CREATE TABLE IF NOT EXISTS index_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")

    @staticmethod
    def _fts_body(c: LegalChunk) -> str:
        """Searchable body: apostrophe-normalized text plus a Latin mirror for Uzbek Cyrillic."""
        base = normalize_uzbek_apostrophes(c.text)
        mirror = c.normalized_text or ""
        if mirror and mirror != base and mirror != c.text:
            return f"{base}\n{mirror}"
        return base

    @classmethod
    def _fts_row(cls, rid: int, c: LegalChunk) -> tuple[int, str, str, str, str, str]:
        return (
            rid,
            normalize_uzbek_apostrophes(c.doc_title),
            normalize_uzbek_apostrophes(c.doc_number or ""),
            c.article or "",
            normalize_uzbek_apostrophes(c.article_title or ""),
            cls._fts_body(c),
        )

    @staticmethod
    def _stored_json(c: LegalChunk) -> str:
        # The searchable mirror lives in FTS only; keeping it out of chunk_json halves the database size.
        return c.model_dump_json(exclude={"normalized_text"})

    def _ensure_fts_synced(self) -> None:
        """Backfill the FTS5 table if it is out of sync with ``chunks`` (e.g. after an interrupted build)."""
        if self._fts_ready:
            return
        with self._connect() as conn:
            total_chunks = int(conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0])
            total_fts = int(conn.execute("SELECT COUNT(*) FROM chunks_fts").fetchone()[0])
            if total_chunks != total_fts:
                logger.info("Re-syncing SQLite FTS5 index for %d chunks...", total_chunks)
                conn.execute("DELETE FROM chunks_fts")
                batch: list[tuple[int, str, str, str, str, str]] = []
                for row in conn.execute("SELECT rid, chunk_json FROM chunks"):
                    c = LegalChunk.model_validate_json(row["chunk_json"])
                    batch.append(self._fts_row(int(row["rid"]), c))
                    if len(batch) >= 1000:
                        conn.executemany(
                            "INSERT INTO chunks_fts(rowid, doc_title, doc_number, article, article_title, body) "
                            "VALUES (?, ?, ?, ?, ?, ?)",
                            batch,
                        )
                        batch.clear()
                if batch:
                    conn.executemany(
                        "INSERT INTO chunks_fts(rowid, doc_title, doc_number, article, article_title, body) "
                        "VALUES (?, ?, ?, ?, ?, ?)",
                        batch,
                    )
        self._fts_ready = True

    def upsert_chunks(self, chunks: list[LegalChunk]) -> None:
        if not chunks:
            return
        # De-duplicate within the batch (last one wins)
        unique: dict[str, LegalChunk] = {c.chunk_id: c for c in chunks}
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
                self._stored_json(c),
            )
            for c in unique.values()
        ]
        with self._connect() as conn:
            ids = list(unique)
            existing: dict[str, int] = {}
            for i in range(0, len(ids), 500):
                part = ids[i : i + 500]
                q = f"SELECT rid, chunk_id FROM chunks WHERE chunk_id IN ({','.join('?' * len(part))})"
                existing.update({r["chunk_id"]: int(r["rid"]) for r in conn.execute(q, part)})
            if existing:
                conn.executemany("DELETE FROM chunks_fts WHERE rowid = ?", [(rid,) for rid in existing.values()])
            conn.executemany(
                """
                INSERT INTO chunks (
                    chunk_id, doc_id, canonical_id, language, doc_type, doc_number,
                    article, status, legal_force_rank, effective_date, expiry_date, chunk_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(chunk_id) DO UPDATE SET
                    doc_id=excluded.doc_id, canonical_id=excluded.canonical_id, language=excluded.language,
                    doc_type=excluded.doc_type, doc_number=excluded.doc_number, article=excluded.article,
                    status=excluded.status, legal_force_rank=excluded.legal_force_rank,
                    effective_date=excluded.effective_date, expiry_date=excluded.expiry_date,
                    chunk_json=excluded.chunk_json
                """,
                rows,
            )
            rid_map: dict[str, int] = {}
            for i in range(0, len(ids), 500):
                part = ids[i : i + 500]
                q = f"SELECT rid, chunk_id FROM chunks WHERE chunk_id IN ({','.join('?' * len(part))})"
                rid_map.update({r["chunk_id"]: int(r["rid"]) for r in conn.execute(q, part)})
            conn.executemany(
                "INSERT INTO chunks_fts(rowid, doc_title, doc_number, article, article_title, body) VALUES (?, ?, ?, ?, ?, ?)",
                [self._fts_row(rid_map[c.chunk_id], c) for c in unique.values()],
            )
        self._fts_ready = True

    def clear(self) -> None:
        """Remove every chunk (used before a forced full rebuild)."""
        with self._connect() as conn:
            conn.execute("DELETE FROM chunks_fts")
            conn.execute("DELETE FROM chunks")
            conn.execute("DELETE FROM index_meta")
        self._fts_ready = True

    def iter_chunks(self, batch_size: int = 1000):
        """Yield every stored chunk (used to carry runtime-ingested documents across full rebuilds)."""
        last = 0
        while True:
            with self._connect() as conn:
                rows = conn.execute(
                    "SELECT rid, chunk_json FROM chunks WHERE rid > ? ORDER BY rid LIMIT ?", (last, batch_size)
                ).fetchall()
            if not rows:
                return
            for r in rows:
                yield LegalChunk.model_validate_json(r["chunk_json"])
            last = int(rows[-1]["rid"])

    def max_rid(self) -> int:
        with self._connect() as conn:
            return int(conn.execute("SELECT COALESCE(MAX(rid), 0) FROM chunks").fetchone()[0])

    def count_after(self, rid: int) -> tuple[int, int]:
        """(chunks, distinct documents) stored after row id ``rid`` — i.e. added after the bundled build."""
        with self._connect() as conn:
            row = conn.execute("SELECT COUNT(*), COUNT(DISTINCT doc_id) FROM chunks WHERE rid > ?", (rid,)).fetchone()
            return int(row[0]), int(row[1])

    def optimize(self) -> None:
        with self._connect() as conn:
            conn.execute("INSERT INTO chunks_fts(chunks_fts) VALUES('optimize')")

    def count(self) -> int:
        with self._connect() as conn:
            return int(conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0])

    def language_counts(self) -> dict[str, int]:
        with self._connect() as conn:
            return {r["language"]: int(r["n"]) for r in conn.execute("SELECT language, COUNT(*) AS n FROM chunks GROUP BY language")}

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
                        SELECT c.chunk_json, bm25(chunks_fts, 3.0, 5.0, 4.5, 6.0, 1.0) AS rank_score
                        FROM chunks_fts
                        JOIN chunks c ON c.rid = chunks_fts.rowid
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

    def get_chunks_by_ids(self, chunk_ids: list[str]) -> dict[str, LegalChunk]:
        if not chunk_ids:
            return {}
        with self._connect() as conn:
            q = f"SELECT chunk_id, chunk_json FROM chunks WHERE chunk_id IN ({','.join('?' * len(chunk_ids))})"
            return {r["chunk_id"]: LegalChunk.model_validate_json(r["chunk_json"]) for r in conn.execute(q, chunk_ids)}

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
