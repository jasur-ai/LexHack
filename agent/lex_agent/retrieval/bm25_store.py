"""SQLite FTS5 BM25 store over morphology-normalised terms (fast exact keyword and article lookup).

Every chunk is indexed as *search terms* rather than raw words: Uzbek text (either script) is folded to
apostrophe-free Latin and lightly stemmed, Russian is Snowball-stemmed (see ``language.textproc``). Queries go
through the same analysis, so "ishdan boʻshatishdi", "ishdan bo'shatish" and "Ишдан бўшатиш" all hit the same
postings. Original texts stay in ``chunk_json`` for display.

Schema: ``chunks`` (one row per chunk, integer ``rid``, zlib-compressed chunk JSON) and the contentless
``chunks_fts`` FTS5 table whose ``rowid`` equals ``chunks.rid``. Columns: act titles, act number, article number
tokens, article title, chapter/section headings, body terms and a ``doc`` token (``d<canonical id>``, weight 0) used
to search inside one act.
"""

from __future__ import annotations

import logging
import math
import re
import sqlite3
import threading
import zlib
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from lex_agent.chunk_text import article_body, article_number, chunk_article_id, short_act_title
from lex_agent.language.stopwords import stop_terms
from lex_agent.language.textproc import ANALYZER_VERSION, index_terms, query_terms
from lex_agent.language.transliterator import detect_language, normalize_uzbek_apostrophes
from lex_agent.models import LegalChunk, NormStatus, RetrievalFilter, RetrievedChunk

logger = logging.getLogger(__name__)

BM25_SCHEMA = "terms-v4-z"
# What an existing index must match to be reused: storage layout + text analyzer (stemming changes the terms).
_LAYOUT_TAG = f"{BM25_SCHEMA}+{ANALYZER_VERSION}"

_SUP = str.maketrans("0123456789", "⁰¹²³⁴⁵⁶⁷⁸⁹")


def legal_tokenize(text: str, *, drop_stopwords: bool = False) -> list[str]:
    """Search terms of a free text (language auto-detected); kept for callers outside the retriever."""
    lang = detect_language(text).value if text else "uz_latn"
    terms = query_terms(text, language=lang)
    stops = stop_terms(lang) if drop_stopwords else frozenset()
    out: list[str] = []
    seen: set[str] = set()
    for t in terms:
        if t in stops:
            continue
        if t not in seen:
            seen.add(t)
            out.append(t)
    return out


def article_tokens(article: str | None) -> str:
    """'217-modda' -> '217', '104¹-modda' -> '104 104s1' (base number plus an exact token)."""
    num = article_number(article)
    if not num:
        return ""
    if "." in num:
        base, sup = num.split(".", 1)
        return f"{base} {base}s{sup}"
    return num


def number_tokens(doc_number: str | None) -> str:
    """Act numbers in a script-neutral form: 'ЎРҚ-547' / "O'RQ-547" / 'ЗРУ-547' -> 'orq547'."""
    if not doc_number:
        return ""
    n = normalize_uzbek_apostrophes(doc_number).upper().replace("'", "").replace(" ", "")
    n = n.replace("ЎРҚ", "ORQ").replace("ЗРУ", "ORQ").replace("ЎРК", "ORQ")
    n = n.replace("ПФ", "PF").replace("УП", "PF").replace("ПҚ", "PQ").replace("ПП", "PQ")
    n = n.replace("ВМҚ", "VMQ").replace("ПКМ", "VMQ")
    m = re.match(r"^([A-Z]+)-?(\d+)", n)
    if m:
        return f"{m.group(1).lower()}{m.group(2)}"
    m = re.match(r"^(\d+)-([IVXLCХ]+)$", n)
    if m:
        return f"n{m.group(1)}{m.group(2).replace('Х', 'X').lower()}"
    return re.sub(r"[^0-9a-z]+", "", n.lower())


_HEADING_NUM_RE = re.compile(
    r"^\s*(?:(?:[IVXLC]+|\d+(?:[.-]\d+)?)\s*[-.]?\s*(?:боб|бўлим|қисм|bob|bo[ʻ'’`]?lim|qism)\b|"
    r"(?:глава|раздел|подраздел|часть)\s+[IVXLC\d]+(?:[.-]\d+)?)\s*[.:]?\s*",
    re.I,
)


def heading_text(c: LegalChunk) -> str:
    """Chapter and section headings without their numbering ("35-bob. Soliq stavkalari" -> "Soliq stavkalari")."""
    parts = []
    for h in (c.chapter, c.section):
        if h:
            parts.append(_HEADING_NUM_RE.sub("", str(h)))
    return " ".join(parts)


def doc_token(canonical_id: str) -> str:
    """FTS token that identifies one act ("d6257288")."""
    return "d" + re.sub(r"[^0-9a-z]+", "", str(canonical_id).lower())


def chunk_matches_filter(chunk: LegalChunk, flt: RetrievalFilter | None) -> bool:
    """Apply language, hierarchy, status, branch, article, and temporal validity filters."""
    if flt is None:
        return chunk.status != NormStatus.REPEALED
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
        target = article_number(flt.article_number) or re.sub(r"[^\d.]", "", flt.article_number)
        if not chunk.article or article_number(chunk.article) != target:
            return False
    if flt.as_of_date is not None:
        if chunk.effective_date and chunk.effective_date > flt.as_of_date:
            return False
        if chunk.expiry_date and chunk.expiry_date <= flt.as_of_date:
            return False
        if chunk.status == NormStatus.REPEALED and not chunk.expiry_date and not flt.include_repealed:
            return False
    elif not flt.include_repealed and chunk.status == NormStatus.REPEALED:
        return False
    return True


def pack_chunk(c: LegalChunk) -> bytes:
    """Compressed stored form of a chunk (Cyrillic legal text shrinks ~4x)."""
    raw = c.model_dump_json(exclude={"normalized_text"}, exclude_defaults=True)
    return zlib.compress(raw.encode("utf-8"), 6)


def unpack_chunk(blob: bytes | str) -> LegalChunk:
    if isinstance(blob, (bytes, bytearray, memoryview)):
        return LegalChunk.model_validate_json(zlib.decompress(bytes(blob)))
    return LegalChunk.model_validate_json(blob)


@dataclass(slots=True)
class LexicalHit:
    """Light FTS hit (the stored chunk is decoded lazily, only for candidates that survive scoring)."""

    rid: int
    score: float
    chunk_json: bytes

    def load(self) -> LegalChunk:
        return unpack_chunk(self.chunk_json)


def _quote(term: str) -> str:
    return '"' + term.replace('"', "") + '"'


class BM25Store:
    """SQLite-persisted chunk store with FTS5 BM25 search over normalised terms and exact SQL lookups."""

    _FTS_COLUMNS = ("title", "doc_number", "article", "article_title", "heading", "body", "doc")
    # bm25() column weights: act title, act number, article number, article title, chapter/section heading, body,
    # doc filter token
    _WEIGHTS = (1.2, 4.0, 2.0, 4.0, 1.5, 1.0, 0.0)

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._fts_ready = False
        self._df_cache: dict[str, int] = {}
        self._df_lock = threading.Lock()
        self._n_docs: int | None = None
        self._local = threading.local()
        self._init_schema()

    # ------------------------------------------------------------------ schema & connections
    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30.0, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA cache_size=-32000")
        conn.execute("PRAGMA mmap_size=268435456")
        return conn

    def _reader(self) -> sqlite3.Connection:
        """Per-thread connection for read-only queries (avoids reconnecting on every lookup)."""
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = self._connect()
            self._local.conn = conn
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS index_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
            row = conn.execute("SELECT value FROM index_meta WHERE key = 'bm25_schema'").fetchone()
            has_chunks = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='chunks'"
            ).fetchone()
            if has_chunks and (row is None or row[0] != _LAYOUT_TAG):
                # Older index layout: it only ever held re-buildable data, so rebuild from scratch.
                logger.warning("Upgrading BM25 index layout at %s (it will be rebuilt).", self.db_path)
                conn.execute("DROP TABLE IF EXISTS chunks_fts")
                conn.execute("DROP TABLE IF EXISTS chunks_vocab")
                conn.execute("DROP TABLE IF EXISTS surface_vocab")
                conn.execute("DROP TABLE IF EXISTS chunks")
                conn.execute("DELETE FROM index_meta")
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
                    doc_number_key TEXT,
                    article TEXT,
                    article_id TEXT,
                    status TEXT NOT NULL,
                    legal_force_rank INTEGER NOT NULL,
                    effective_date TEXT,
                    expiry_date TEXT,
                    chunk_json BLOB NOT NULL
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_chunks_doc_id ON chunks(doc_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_chunks_canonical ON chunks(canonical_id, article_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_chunks_doc_number ON chunks(doc_number_key)")
            # Contentless FTS: the term strings are derived from chunk_json, so storing them twice is pure waste.
            conn.execute(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
                    title, doc_number, article, article_title, heading, body, doc,
                    content='', tokenize='unicode61 remove_diacritics 0'
                )
                """
            )
            conn.execute("CREATE VIRTUAL TABLE IF NOT EXISTS chunks_vocab USING fts5vocab(chunks_fts, 'row')")
            # Unstemmed words of the corpus with their document frequency (typo correction works on real words)
            conn.execute("CREATE TABLE IF NOT EXISTS surface_vocab (term TEXT PRIMARY KEY, df INTEGER NOT NULL)")
            conn.execute("INSERT OR REPLACE INTO index_meta(key, value) VALUES ('bm25_schema', ?)", (_LAYOUT_TAG,))

    # ------------------------------------------------------------------ indexing
    @staticmethod
    def fts_values(c: LegalChunk) -> tuple[str, str, str, str, str, str, str]:
        lang = c.language.value
        stitle = short_act_title(c)
        title_src = stitle if stitle and stitle in c.doc_title else f"{stitle} {c.doc_title}"
        title = " ".join(index_terms(title_src, language=lang))
        art_title = " ".join(index_terms(c.article_title or "", language=lang))
        heading = " ".join(index_terms(heading_text(c), language=lang))
        body = " ".join(index_terms(article_body(c), language=lang))
        return (
            title,
            number_tokens(c.doc_number),
            article_tokens(c.article),
            art_title,
            heading,
            body,
            doc_token(c.canonical_id),
        )


    def upsert_chunks(self, chunks: list[LegalChunk]) -> None:
        if not chunks:
            return
        unique: dict[str, LegalChunk] = {c.chunk_id: c for c in chunks}
        rows = [
            (
                c.chunk_id,
                c.doc_id,
                c.canonical_id,
                c.language.value,
                c.doc_type.value,
                c.doc_number,
                number_tokens(c.doc_number) or None,
                c.article,
                chunk_article_id(c) or None,
                c.status.value,
                c.legal_force_rank,
                c.effective_date.isoformat() if c.effective_date else None,
                c.expiry_date.isoformat() if c.expiry_date else None,
                pack_chunk(c),
            )
            for c in unique.values()
        ]
        fts_payload = {cid: self.fts_values(c) for cid, c in unique.items()}
        with self._connect() as conn:
            ids = list(unique)
            existing: list[tuple] = []
            for i in range(0, len(ids), 500):
                part = ids[i : i + 500]
                q = f"SELECT rid, chunk_json FROM chunks WHERE chunk_id IN ({','.join('?' * len(part))})"
                for r in conn.execute(q, part):
                    # Contentless FTS5 deletes need the exact indexed values: recompute them from the old chunk.
                    existing.append(("delete", int(r["rid"]), *self.fts_values(unpack_chunk(r["chunk_json"]))))
            if existing:
                conn.executemany(
                    "INSERT INTO chunks_fts(chunks_fts, rowid, title, doc_number, article, article_title, heading, body, doc) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    existing,
                )
            conn.executemany(
                """
                INSERT INTO chunks (
                    chunk_id, doc_id, canonical_id, language, doc_type, doc_number, doc_number_key,
                    article, article_id, status, legal_force_rank, effective_date, expiry_date, chunk_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(chunk_id) DO UPDATE SET
                    doc_id=excluded.doc_id, canonical_id=excluded.canonical_id, language=excluded.language,
                    doc_type=excluded.doc_type, doc_number=excluded.doc_number,
                    doc_number_key=excluded.doc_number_key, article=excluded.article,
                    article_id=excluded.article_id, status=excluded.status,
                    legal_force_rank=excluded.legal_force_rank, effective_date=excluded.effective_date,
                    expiry_date=excluded.expiry_date, chunk_json=excluded.chunk_json
                """,
                rows,
            )
            rid_map: dict[str, int] = {}
            for i in range(0, len(ids), 500):
                part = ids[i : i + 500]
                q = f"SELECT rid, chunk_id FROM chunks WHERE chunk_id IN ({','.join('?' * len(part))})"
                rid_map.update({r["chunk_id"]: int(r["rid"]) for r in conn.execute(q, part)})
            conn.executemany(
                "INSERT INTO chunks_fts(rowid, title, doc_number, article, article_title, heading, body, doc) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                [(rid_map[cid], *fts_payload[cid]) for cid in unique],
            )
        self._fts_ready = True
        self._invalidate_stats()

    def _invalidate_stats(self) -> None:
        with self._df_lock:
            self._df_cache.clear()
            self._n_docs = None

    def clear(self) -> None:
        """Remove every chunk (used before a forced full rebuild)."""
        with self._connect() as conn:
            conn.execute("INSERT INTO chunks_fts(chunks_fts) VALUES('delete-all')")
            conn.execute("DELETE FROM chunks")
            conn.execute("DELETE FROM sqlite_sequence WHERE name = 'chunks'")
            conn.execute("DELETE FROM surface_vocab")
            conn.execute("DELETE FROM index_meta WHERE key != 'bm25_schema'")
        with self._connect() as conn:
            conn.execute("VACUUM")
        self._fts_ready = True
        self._invalidate_stats()

    def iter_chunks(self, batch_size: int = 1000):
        """Yield every stored chunk (used to carry runtime-ingested documents across full rebuilds)."""
        last = 0
        while True:
            with _nullctx(self._reader()) as conn:
                rows = conn.execute(
                    "SELECT rid, chunk_json FROM chunks WHERE rid > ? ORDER BY rid LIMIT ?", (last, batch_size)
                ).fetchall()
            if not rows:
                return
            for r in rows:
                yield unpack_chunk(r["chunk_json"])
            last = int(rows[-1]["rid"])

    def max_rid(self) -> int:
        with _nullctx(self._reader()) as conn:
            return int(conn.execute("SELECT COALESCE(MAX(rid), 0) FROM chunks").fetchone()[0])

    def count_after(self, rid: int) -> tuple[int, int]:
        """(chunks, distinct documents) stored after row id ``rid`` — i.e. added after the bundled build."""
        with _nullctx(self._reader()) as conn:
            row = conn.execute("SELECT COUNT(*), COUNT(DISTINCT doc_id) FROM chunks WHERE rid > ?", (rid,)).fetchone()
            return int(row[0]), int(row[1])

    def optimize(self) -> None:
        with self._connect() as conn:
            conn.execute("INSERT INTO chunks_fts(chunks_fts) VALUES('optimize')")
            conn.execute("ANALYZE")

    def count(self) -> int:
        with _nullctx(self._reader()) as conn:
            return int(conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0])

    def language_counts(self) -> dict[str, int]:
        with _nullctx(self._reader()) as conn:
            return {
                r["language"]: int(r["n"])
                for r in conn.execute("SELECT language, COUNT(*) AS n FROM chunks GROUP BY language")
            }

    def rebuild_index(self) -> int:
        """Make sure the FTS table is in sync with ``chunks`` and return the chunk count."""
        self._fts_ready = False
        self._ensure_fts_synced()
        return self.count()

    def _ensure_fts_synced(self) -> None:
        if self._fts_ready:
            return
        with self._connect() as conn:
            total_chunks = int(conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0])
            total_fts = int(conn.execute("SELECT COUNT(*) FROM chunks_fts").fetchone()[0])
            if total_chunks != total_fts:
                logger.info("Re-syncing FTS5 index for %d chunks...", total_chunks)
                conn.execute("INSERT INTO chunks_fts(chunks_fts) VALUES('delete-all')")
                batch: list[tuple] = []
                for row in conn.execute("SELECT rid, chunk_json FROM chunks"):
                    c = unpack_chunk(row["chunk_json"])
                    batch.append((int(row["rid"]), *self.fts_values(c)))
                    if len(batch) >= 1000:
                        conn.executemany(
                            "INSERT INTO chunks_fts(rowid, title, doc_number, article, article_title, heading, body, doc) "
                            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                            batch,
                        )
                        batch.clear()
                if batch:
                    conn.executemany(
                        "INSERT INTO chunks_fts(rowid, title, doc_number, article, article_title, heading, body, doc) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                        batch,
                    )
        self._fts_ready = True

    # ------------------------------------------------------------------ term statistics
    def total_docs(self) -> int:
        if self._n_docs is None:
            with _nullctx(self._reader()) as conn:
                self._n_docs = int(conn.execute("SELECT COUNT(*) FROM chunks_fts").fetchone()[0]) or 1
        return self._n_docs

    def doc_freqs(self, terms: Iterable[str]) -> dict[str, int]:
        """Number of chunks containing each term (cached)."""
        wanted = [t for t in dict.fromkeys(terms) if t]
        missing = [t for t in wanted if t not in self._df_cache]
        if missing:
            with _nullctx(self._reader()) as conn:
                found: dict[str, int] = {}
                for i in range(0, len(missing), 400):
                    part = missing[i : i + 400]
                    q = f"SELECT term, doc FROM chunks_vocab WHERE term IN ({','.join('?' * len(part))})"
                    found.update({r["term"]: int(r["doc"]) for r in conn.execute(q, part)})
            with self._df_lock:
                for t in missing:
                    self._df_cache[t] = found.get(t, 0)
                if len(self._df_cache) > 200_000:
                    self._df_cache.clear()
        return {t: self._df_cache.get(t, 0) for t in wanted}

    def idf(self, terms: Iterable[str]) -> dict[str, float]:
        n = self.total_docs()
        return {t: math.log(1 + (n - df + 0.5) / (df + 0.5)) for t, df in self.doc_freqs(terms).items()}

    def replace_surface_vocabulary(self, counts: dict[str, int], *, min_doc_freq: int = 2) -> int:
        """Store the corpus word list used for typo correction (replaces the previous one)."""
        rows = [(t, int(n)) for t, n in counts.items() if n >= min_doc_freq]
        with self._connect() as conn:
            conn.execute("DELETE FROM surface_vocab")
            conn.executemany("INSERT INTO surface_vocab(term, df) VALUES (?, ?)", rows)
        return len(rows)

    def surface_vocabulary(self) -> list[tuple[str, int]]:
        with _nullctx(self._reader()) as conn:
            try:
                return [(r["term"], int(r["df"])) for r in conn.execute("SELECT term, df FROM surface_vocab")]
            except sqlite3.OperationalError:
                return []

    def vocabulary(self, *, min_doc_freq: int = 2) -> list[tuple[str, int]]:
        """(term, document frequency) for every indexed term seen in at least ``min_doc_freq`` chunks."""
        with _nullctx(self._reader()) as conn:
            return [
                (r["term"], int(r["doc"]))
                for r in conn.execute("SELECT term, doc FROM chunks_vocab WHERE doc >= ?", (min_doc_freq,))
            ]

    # ------------------------------------------------------------------ search
    def match_terms(
        self,
        terms: list[str],
        *,
        mode: str = "or",
        limit: int = 60,
        prefix_terms: Iterable[str] = (),
        columns: tuple[str, ...] | None = None,
        doc_ids: Iterable[str] | None = None,
    ) -> list[LexicalHit]:
        """Run one FTS5 MATCH over pre-analysed terms; returns hits best-first with positive BM25 scores."""
        self._ensure_fts_synced()
        prefix = set(prefix_terms)
        parts = [f"{_quote(t)}*" if t in prefix else _quote(t) for t in dict.fromkeys(terms) if t]
        if not parts:
            return []
        expr = (" AND " if mode == "and" else " OR ").join(parts)
        if columns:
            expr = "{" + " ".join(columns) + "} : (" + expr + ")"
        docs = [doc_token(d) for d in (doc_ids or []) if d]
        if docs:
            expr = "(" + expr + ") AND {doc} : (" + " OR ".join(_quote(d) for d in docs) + ")"
        weights = ", ".join(str(w) for w in self._WEIGHTS)
        sql = (
            f"SELECT c.rid, c.chunk_json, bm25(chunks_fts, {weights}) AS s FROM chunks_fts "
            "JOIN chunks c ON c.rid = chunks_fts.rowid WHERE chunks_fts MATCH ? ORDER BY s LIMIT ?"
        )
        try:
            with _nullctx(self._reader()) as conn:
                rows = conn.execute(sql, (expr, limit)).fetchall()
        except sqlite3.OperationalError as exc:
            logger.debug("FTS5 query skipped (%s): %s", expr, exc)
            return []
        return [LexicalHit(rid=int(r["rid"]), score=max(0.01, -float(r["s"])), chunk_json=r["chunk_json"]) for r in rows]

    def search(
        self,
        query: str,
        *,
        top_k: int = 12,
        filters: RetrievalFilter | None = None,
        extra_terms: Iterable[str] = (),
        doc_ids: Iterable[str] | None = None,
    ) -> list[RetrievedChunk]:
        """Keyword search for a free-text query (precision AND pass, then a broad OR pass)."""
        terms = legal_tokenize(query, drop_stopwords=True)[:14]
        if not terms:
            terms = legal_tokenize(query)[:10]
        for t in extra_terms:
            if t and t not in terms:
                terms.append(t)
        return self.search_terms(terms, top_k=top_k, filters=filters, doc_ids=doc_ids)

    def search_terms(
        self,
        terms: list[str],
        *,
        top_k: int = 12,
        filters: RetrievalFilter | None = None,
        doc_ids: Iterable[str] | None = None,
        and_bonus: float = 1.4,
    ) -> list[RetrievedChunk]:
        """BM25 over pre-analysed terms: an AND pass over the most informative terms, then a broad OR pass."""
        terms = [t for t in dict.fromkeys(terms) if t]
        if not terms:
            return []
        docs = list(doc_ids or [])
        idf = self.idf(terms)
        informative = [t for t in sorted(terms, key=lambda t: -idf.get(t, 0.0)) if idf.get(t, 0.0) > 0.3]
        collected: dict[int, tuple[float, bytes]] = {}
        if len(informative) >= 2:
            for hit in self.match_terms(informative[:4], mode="and", limit=max(top_k * 4, 40), doc_ids=docs):
                collected[hit.rid] = (hit.score * and_bonus, hit.chunk_json)
        if len(collected) < top_k:
            prefix = [t for t in terms if len(t) >= 6 and t.isalpha()]
            for hit in self.match_terms(terms, mode="or", limit=max(top_k * 5, 60), prefix_terms=prefix, doc_ids=docs):
                prev = collected.get(hit.rid)
                if prev is None or hit.score > prev[0]:
                    collected[hit.rid] = (hit.score, hit.chunk_json)
        ranked = sorted(collected.values(), key=lambda x: x[0], reverse=True)
        out: list[RetrievedChunk] = []
        for score, raw in ranked:
            chunk = unpack_chunk(raw)
            if not chunk_matches_filter(chunk, filters):
                continue
            out.append(RetrievedChunk(chunk=chunk, bm25_score=score, final_score=score, retrieval_source="bm25_fts5"))
            if len(out) >= top_k:
                break
        return out

    # ------------------------------------------------------------------ exact lookups
    def get_chunks_by_ids(self, chunk_ids: list[str]) -> dict[str, LegalChunk]:
        if not chunk_ids:
            return {}
        out: dict[str, LegalChunk] = {}
        with _nullctx(self._reader()) as conn:
            for i in range(0, len(chunk_ids), 500):
                part = chunk_ids[i : i + 500]
                q = f"SELECT chunk_id, chunk_json FROM chunks WHERE chunk_id IN ({','.join('?' * len(part))})"
                out.update({r["chunk_id"]: unpack_chunk(r["chunk_json"]) for r in conn.execute(q, part)})
        return out

    def get_article(
        self, canonical_id: str, article_id: str, *, languages: Iterable[str] | None = None, limit: int = 12
    ) -> list[LegalChunk]:
        """All chunks of one article (every edition/part), e.g. ('6257288', '217')."""
        sql = "SELECT chunk_json FROM chunks WHERE (canonical_id = ? OR doc_id = ?) AND article_id = ?"
        params: list = [canonical_id, canonical_id, article_id]
        langs = list(languages or [])
        if langs:
            sql += f" AND language IN ({','.join('?' * len(langs))})"
            params += langs
        sql += " ORDER BY rid LIMIT ?"
        params.append(limit)
        with _nullctx(self._reader()) as conn:
            return [unpack_chunk(r["chunk_json"]) for r in conn.execute(sql, params)]

    def get_articles(
        self, keys: Iterable[tuple[str, str]], *, languages: Iterable[str] | None = None, per_article: int = 2
    ) -> dict[tuple[str, str], list[LegalChunk]]:
        """Chunks of several (act, article) pairs in one query, at most ``per_article`` chunks each."""
        wanted = list(dict.fromkeys(keys))
        if not wanted:
            return {}
        docs = sorted({d for d, _ in wanted})
        arts = sorted({a for _, a in wanted})
        sql = (
            f"SELECT canonical_id, article_id, chunk_json FROM chunks WHERE canonical_id IN ({','.join('?' * len(docs))}) "
            f"AND article_id IN ({','.join('?' * len(arts))})"
        )
        params: list = [*docs, *arts]
        langs = list(languages or [])
        if langs:
            sql += f" AND language IN ({','.join('?' * len(langs))})"
            params += langs
        sql += " ORDER BY rid"
        want = set(wanted)
        out: dict[tuple[str, str], list[LegalChunk]] = {}
        with _nullctx(self._reader()) as conn:
            for r in conn.execute(sql, params):
                key = (r["canonical_id"], r["article_id"])
                if key not in want:
                    continue
                bucket = out.setdefault(key, [])
                if len(bucket) < per_article:
                    bucket.append(unpack_chunk(r["chunk_json"]))
        return out

    def get_chunks_by_doc(
        self,
        doc_id: str,
        *,
        article: str | None = None,
        limit: int = 30,
    ) -> list[LegalChunk]:
        """Exact lookup for chunks (across UZ/RU/EN) of a `doc_id` or `canonical_id`, optionally one article."""
        if article:
            art_id = article_number(article) or re.sub(r"[^\d.]", "", article)
            return self.get_article(doc_id, art_id, limit=limit)
        with _nullctx(self._reader()) as conn:
            rows = conn.execute(
                "SELECT chunk_json FROM chunks WHERE doc_id = ? OR canonical_id = ? ORDER BY rid LIMIT ?",
                (doc_id, doc_id, limit),
            ).fetchall()
        return [unpack_chunk(r["chunk_json"]) for r in rows]

    def find_by_doc_number(self, doc_number: str, *, article: str | None = None, limit: int = 10) -> list[LegalChunk]:
        """Exact lookup by normative act number (e.g. O'RQ-682, ЗРУ-547, PF-158, 221-I)."""
        key = number_tokens(doc_number)
        if not key:
            return []
        with _nullctx(self._reader()) as conn:
            if article:
                art_id = article_number(article) or re.sub(r"[^\d.]", "", article)
                rows = conn.execute(
                    "SELECT chunk_json FROM chunks WHERE doc_number_key = ? AND article_id = ? ORDER BY rid LIMIT ?",
                    (key, art_id, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT chunk_json FROM chunks WHERE doc_number_key = ? ORDER BY rid LIMIT ?", (key, limit)
                ).fetchall()
        return [unpack_chunk(r["chunk_json"]) for r in rows]

    def doc_articles(self, canonical_id: str, *, language_family: str = "uz") -> list[tuple[str, str]]:
        """(article_id, article label) pairs of one act, in order — used for article-range answers."""
        langs = ("uz_latn", "uz_cyrl") if language_family == "uz" else (language_family,)
        with _nullctx(self._reader()) as conn:
            rows = conn.execute(
                f"SELECT DISTINCT article_id, article FROM chunks WHERE canonical_id = ? AND article_id IS NOT NULL "
                f"AND language IN ({','.join('?' * len(langs))}) ORDER BY rid",
                (canonical_id, *langs),
            ).fetchall()
        return [(r["article_id"], r["article"]) for r in rows]


class _nullctx:
    """``with`` wrapper for a shared read connection (no commit/close on exit)."""

    __slots__ = ("conn",)

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def __enter__(self) -> sqlite3.Connection:
        return self.conn

    def __exit__(self, *exc: object) -> None:
        return None


def superscript(article_id: str) -> str:
    """'104.1' -> '104¹' (display form of an article id)."""
    if "." in article_id:
        base, sup = article_id.split(".", 1)
        return f"{base}{sup.translate(_SUP)}"
    return article_id
