"""Bundled open legal corpora: loaders, source registry, and the offline index builder.

The agent ships with an offline knowledge base so that answering never depends on a slow live scrape:

* ``uz_latn_codes.jsonl.gz`` — Constitution, 21 codes and 4 major laws in Uzbek Latin (CC0 corpus, 2026-07
  snapshot of lex.uz) plus the Housing Code.
* ``ru_codes.jsonl.gz`` — 21 codes and the Constitution in Russian (aligned lex.uz texts).
* ``lex_cache/`` — documents captured from lex.uz by the live fetcher (only the acts missing above are indexed).
* ``curated_facts.json`` — frequently requested legal constants (BHM, minimum wage) with their official source.

``build_bundled_index`` turns all of them into structure-aware ``LegalChunk`` records stored in the SQLite FTS5
index. It is idempotent: a fingerprint of the bundle is stored in the index and the build is skipped when the
fingerprint is unchanged.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import logging
import re
import sqlite3
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from lex_agent.language.transliterator import (
    normalize_uzbek_apostrophes,
    to_searchable_uzbek_latin,
)
from lex_agent.models import (
    LEGAL_FORCE_HIERARCHY,
    DocumentMetadata,
    DocumentType,
    Language,
    LegalBranch,
    LegalChunk,
    NormStatus,
)

logger = logging.getLogger(__name__)

INDEX_SCHEMA_VERSION = "2026.11-r2"
MAX_CHUNK_CHARS = 1800

# Branch tags per code (keyed by the canonical lex.uz document id of the Uzbek edition)
_DOC_BRANCHES: dict[str, list[LegalBranch]] = {
    "6445145": [LegalBranch.CONSTITUTIONAL],
    "111189": [LegalBranch.CIVIL],
    "180552": [LegalBranch.CIVIL],
    "111453": [LegalBranch.CRIMINAL],
    "111460": [LegalBranch.PROCEDURAL_CRIMINAL],
    "163629": [LegalBranch.CRIMINAL],
    "97664": [LegalBranch.ADMINISTRATIVE],
    "6257288": [LegalBranch.LABOR],
    "4674902": [LegalBranch.TAX],
    "3517337": [LegalBranch.PROCEDURAL_CIVIL],
    "3523891": [LegalBranch.PROCEDURAL_ECONOMIC],
    "3527353": [LegalBranch.PROCEDURAL_ADMIN],
    "2876354": [LegalBranch.CUSTOMS],
    "104720": [LegalBranch.FAMILY],
    "106136": [LegalBranch.HOUSING],
    "2304138": [LegalBranch.BANKING_FINANCE],
    "7655343": [LegalBranch.ENVIRONMENTAL_NATURAL],
    "55594": [LegalBranch.GENERAL],
    "4386848": [LegalBranch.CONSTITUTIONAL],
    "152653": [LegalBranch.LAND_REAL_ESTATE],
    "5307951": [LegalBranch.LAND_REAL_ESTATE],
    "4664142": [LegalBranch.INVESTMENT_PPP],
    "72266": [LegalBranch.BANKING_FINANCE],
    "1374865": [LegalBranch.BANKING_FINANCE, LegalBranch.CORPORATE_COMMERCIAL],
    "6518381": [LegalBranch.CORPORATE_COMMERCIAL],
    "2006789": [LegalBranch.CORPORATE_COMMERCIAL],
    "4396419": [LegalBranch.DIGITAL_IT_DATA],
    "5378966": [LegalBranch.CONSTITUTIONAL],
}

# lex.uz documents captured by the live fetcher that are NOT covered by the bundled corpora
# Sources that ``build_bundled_index`` regenerates from files shipped with the repository.
BUNDLED_SOURCES = frozenset({"uzbek_legal_corpus_cc0", "uz_rag_eval_aligned", "lex_uz_live_cache", "curated_facts"})

_LEX_CACHE_EXTRA: dict[str, dict[str, Any]] = {
    "4396419": {
        "title": "Oʻzbekiston Respublikasining “Shaxsga doir maʼlumotlar toʻgʻrisida”gi Qonuni",
        "short_title": "Shaxsga doir maʼlumotlar toʻgʻrisidagi Qonun",
        "doc_number": "O'RQ-547",
        "adopted": date(2019, 7, 2),
        "doc_type": DocumentType.LAW,
    },
    "5378966": {
        "title": "Oʻzbekiston Respublikasining “Normativ-huquqiy hujjatlar toʻgʻrisida”gi Qonuni",
        "short_title": "Normativ-huquqiy hujjatlar toʻgʻrisidagi Qonun",
        "doc_number": "O'RQ-682",
        "adopted": date(2021, 4, 20),
        "doc_type": DocumentType.LAW,
    },
}

# Navigation / toolbar noise that lex.uz renders between paragraphs (UZ / RU / EN interface)
_LEX_NOISE_LINES = (
    "hujjatga taklif yuborish",
    "audioni tinglash",
    "hujjat elementidan havola olish",
    "предложения по документу",
    "прослушать аудио",
    "получить ссылку из элемента документа",
    "suggestion to the document",
    "listen to audio",
    "get a link from a document element",
    "lexuz шарҳи",
    "lexuz sharhi",
)
_LEX_CLASSIFIER_LINE = re.compile(r"^\d+\.\s+(?:\d{2}\.){3}\d{2}\s|^\d+\.\s+[^\n]{3,120}/[^\n]{3,200}\]$")


@dataclass(slots=True)
class SourceInfo:
    """A knowledge source the agent can cite."""

    id: str
    name: str
    kind: str
    languages: list[str]
    url: str
    license: str
    snapshot: str
    description: str
    documents: int = 0
    chunks: int = 0
    available: bool = True
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "kind": self.kind,
            "languages": self.languages,
            "url": self.url,
            "license": self.license,
            "snapshot": self.snapshot,
            "description": self.description,
            "documents": self.documents,
            "chunks": self.chunks,
            "available": self.available,
            "notes": self.notes,
        }


def short_title(title: str, language: Language) -> str:
    """Human-friendly act title without the boilerplate state name."""
    t = re.sub(r"\s+", " ", title).strip()
    if language == Language.RU:
        t = re.sub(r"\s*Республики Узбекистан", "", t)
        return t[:1].upper() + t[1:] if t else title
    t = re.sub(r"^O[ʻ'‘’`]?zbekiston Respublikasining\s+", "", t, flags=re.I)
    t = re.sub(r"^O[ʻ'‘’`]?ZBEKISTON RESPUBLIKASINING\s+", "", t)
    if t.isupper():
        t = t.capitalize()
    return t[:1].upper() + t[1:] if t else title


def lex_url(lex_doc_id: str, language: Language) -> str:
    prefix = "ru" if language == Language.RU else ("en" if language == Language.EN else "uz")
    return f"https://lex.uz/{prefix}/docs/{lex_doc_id}"


def _doc_type_for(code: str, title: str, doc_key: str) -> DocumentType:
    low = normalize_uzbek_apostrophes(f"{code} {title}").lower()
    if doc_key in {"6445145", "6445147", "20596"} or "konstitutsiya" in low or "конституция" in low:
        return DocumentType.CONSTITUTION
    if "qonun" in low or "закон" in low:
        return DocumentType.LAW
    return DocumentType.CODE


def _split_long_text(body: str, limit: int = MAX_CHUNK_CHARS) -> list[str]:
    """Split an article body into paragraph-aligned parts no longer than ``limit`` characters."""
    body = body.strip()
    if len(body) <= limit:
        return [body]
    paragraphs = [p.strip() for p in re.split(r"\n+", body) if p.strip()]
    parts: list[str] = []
    buf = ""
    for para in paragraphs:
        while len(para) > limit:
            cut = para.rfind(". ", 0, limit)
            cut = cut + 1 if cut > limit // 3 else limit
            head, para = para[:cut].strip(), para[cut:].strip()
            if buf:
                parts.append(buf)
                buf = ""
            parts.append(head)
        if not buf:
            buf = para
        elif len(buf) + 1 + len(para) <= limit:
            buf = f"{buf}\n{para}"
        else:
            parts.append(buf)
            buf = para
    if buf:
        parts.append(buf)
    return parts or [body[:limit]]


def _strip_leading_header(text: str, article_id: str | None) -> str:
    """Remove a duplicated 'Статья N. Title' / 'N-modda. Title' first line from aligned-corpus texts."""
    if not article_id:
        return text
    first, _, rest = text.partition("\n")
    head = normalize_uzbek_apostrophes(first).strip().lower()
    num = re.escape(article_id.split(".")[0])
    if re.match(rf"^(?:статья\s+{num}\b|{num}\s*-\s*modda\b|{num}[¹²³⁴⁵⁶⁷⁸⁹⁰]*\s*-\s*modda\b)", head) and rest.strip():
        return rest.strip()
    return text


def iter_corpus_records(path: Path) -> Iterator[dict[str, Any]]:
    if not path.exists():
        return
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                yield json.loads(line)


def corpus_record_to_chunks(rec: dict[str, Any]) -> list[LegalChunk]:
    """Convert one bundled article record into one or more structure-aware chunks."""
    language = Language(rec["lang"])
    doc_key = str(rec["doc_key"])
    lex_doc_id = str(rec.get("lex_doc_id") or doc_key)
    title = str(rec["doc_title"]).strip()
    stitle = short_title(title, language)
    doc_type = _doc_type_for(str(rec.get("code") or ""), title, doc_key)
    article_id = rec.get("article_id")
    art_display = rec.get("article_display")
    if article_id in ("_front", "_end"):
        art_label = None
        art_display = "Muqaddima" if article_id == "_front" and language != Language.RU else art_display
    else:
        art_label = art_display or (
            (f"Статья {article_id}" if language == Language.RU else f"{article_id}-modda") if article_id else None
        )
    art_title = (rec.get("article_title") or "").strip() or None
    body = _strip_leading_header(str(rec["text"]).strip(), article_id if article_id not in ("_front", "_end") else None)
    adopted = None
    if rec.get("adopted"):
        try:
            adopted = date.fromisoformat(str(rec["adopted"]))
        except ValueError:
            adopted = None

    header = stitle
    if art_label:
        header = f"{stitle} · {art_label}" + (f". {art_title}" if art_title else "")
    parts = _split_long_text(body)
    chunks: list[LegalChunk] = []
    for idx, part in enumerate(parts, start=1):
        text = f"{header}\n{part}"
        part_suffix = f"#{idx}" if len(parts) > 1 else ""
        chunk_id = f"{rec['source']}:{language.value}:{doc_key}:{article_id or 'body'}{part_suffix}"
        searchable = to_searchable_uzbek_latin(text, language=language) if language != Language.RU else text
        chunks.append(
            LegalChunk(
                chunk_id=chunk_id,
                doc_id=lex_doc_id,
                canonical_id=doc_key,
                language=language,
                doc_type=doc_type,
                doc_title=title,
                adoption_date=adopted,
                status=NormStatus.IN_FORCE,
                legal_force_rank=LEGAL_FORCE_HIERARCHY.get(doc_type, 20),
                branches=_DOC_BRANCHES.get(doc_key, [LegalBranch.GENERAL]),
                section=rec.get("section") or None,
                chapter=rec.get("chapter") or None,
                article=art_label,
                article_title=art_title,
                clause=f"{idx}/{len(parts)}" if len(parts) > 1 else None,
                text=text,
                normalized_text=searchable,
                url=lex_url(lex_doc_id, language),
                extra={
                    "source": rec["source"],
                    "short_title": stitle,
                    "snapshot": rec.get("snapshot"),
                },
            )
        )
    return chunks


def clean_lex_cache_text(raw: str) -> str:
    """Strip lex.uz toolbar / classifier noise lines from a cached document body."""
    out: list[str] = []
    for line in raw.splitlines():
        s = line.strip()
        if not s:
            continue
        low = s.lower()
        if any(noise in low for noise in _LEX_NOISE_LINES) and len(s) < 160:
            continue
        if _LEX_CLASSIFIER_LINE.match(s):
            continue
        out.append(s)
    return "\n".join(out)


def load_lex_cache_extras(cache_dir: Path, parser: Any) -> tuple[list[DocumentMetadata], list[LegalChunk]]:
    """Parse cached lex.uz documents that complement the bundled corpora (Uzbek Cyrillic editions)."""
    metas: list[DocumentMetadata] = []
    chunks: list[LegalChunk] = []
    for doc_id, info in _LEX_CACHE_EXTRA.items():
        path = cache_dir / f"doc_uz_{doc_id}.json"
        if not path.exists():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Skipping unreadable lex cache file %s: %s", path, exc)
            continue
        text = clean_lex_cache_text(str(data.get("raw_text") or ""))
        if not text:
            continue
        meta = DocumentMetadata(
            doc_id=doc_id,
            canonical_id=doc_id,
            title=info["title"],
            doc_type=info["doc_type"],
            doc_number=info["doc_number"],
            language=Language.UZ_CYRL,
            adoption_date=info["adopted"],
            status=NormStatus.IN_FORCE,
            legal_force_rank=LEGAL_FORCE_HIERARCHY.get(info["doc_type"], 20),
            branches=_DOC_BRANCHES.get(doc_id, [LegalBranch.GENERAL]),
            url=lex_url(doc_id, Language.UZ_CYRL),
            source="lex.uz",
        )
        doc_chunks = parser.parse_to_chunks(meta, text, article_anchors=data.get("article_anchors") or {})
        for c in doc_chunks:
            c.extra = {**c.extra, "source": "lex_uz_live_cache", "short_title": info["short_title"], "snapshot": "2026"}
        metas.append(meta)
        chunks.extend(doc_chunks)
    return metas, chunks


def _curated_updated(path: Path) -> str:
    try:
        return str(json.loads(path.read_text(encoding="utf-8")).get("updated") or "")
    except (OSError, json.JSONDecodeError):
        return ""


def load_curated_facts(path: Path) -> list[LegalChunk]:
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    chunks: list[LegalChunk] = []
    for fact in data.get("facts", []):
        language = Language(fact["lang"])
        doc_type = DocumentType(fact.get("doc_type", "presidential_decree"))
        text = f"{fact['short_title']}\n{fact['text'].strip()}"
        chunks.append(
            LegalChunk(
                chunk_id=f"curated:{fact['id']}:{language.value}",
                doc_id=fact.get("doc_id") or f"curated-{fact['id']}",
                canonical_id=fact.get("doc_id") or f"curated-{fact['id']}",
                language=language,
                doc_type=doc_type,
                doc_number=fact.get("doc_number"),
                doc_title=fact["title"],
                adoption_date=date.fromisoformat(fact["adopted"]) if fact.get("adopted") else None,
                effective_date=date.fromisoformat(fact["effective"]) if fact.get("effective") else None,
                status=NormStatus.IN_FORCE,
                legal_force_rank=LEGAL_FORCE_HIERARCHY.get(doc_type, 20),
                branches=[LegalBranch(b) for b in fact.get("branches", ["general"])],
                article=fact.get("article"),
                article_title=fact.get("article_title"),
                text=text,
                normalized_text=to_searchable_uzbek_latin(text, language=language) if language != Language.RU else text,
                url=fact["url"],
                extra={"source": "curated_facts", "short_title": fact["short_title"], "snapshot": data.get("updated")},
            )
        )
    return chunks


def bundle_fingerprint(corpus_dir: Path, cache_dir: Path) -> str:
    h = hashlib.sha256(INDEX_SCHEMA_VERSION.encode())
    for p in sorted(corpus_dir.glob("*")):
        if p.is_file() and p.suffix in {".gz", ".json"}:
            st = p.stat()
            h.update(f"{p.name}:{st.st_size}".encode())
            h.update(hashlib.sha256(p.read_bytes()).digest())
    for doc_id in sorted(_LEX_CACHE_EXTRA):
        p = cache_dir / f"doc_uz_{doc_id}.json"
        if p.exists():
            h.update(f"{p.name}:{p.stat().st_size}".encode())
    return h.hexdigest()[:24]


def _read_meta(db_path: Path, key: str) -> str | None:
    if not db_path.exists():
        return None
    try:
        with sqlite3.connect(db_path) as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS index_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
            row = conn.execute("SELECT value FROM index_meta WHERE key = ?", (key,)).fetchone()
            return row[0] if row else None
    except sqlite3.Error:
        return None


def _write_meta(db_path: Path, values: dict[str, str]) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS index_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        conn.executemany("INSERT OR REPLACE INTO index_meta(key, value) VALUES (?, ?)", list(values.items()))


def read_index_stats(db_path: Path) -> dict[str, Any]:
    raw = _read_meta(db_path, "bundle_stats")
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


def build_bundled_index(
    *,
    bm25_store: Any,
    registry: Any,
    parser: Any,
    corpus_dir: Path,
    cache_dir: Path,
    force: bool = False,
) -> dict[str, Any]:
    """Index all bundled open corpora into the FTS5 store (skips work when the bundle is unchanged)."""
    fingerprint = bundle_fingerprint(corpus_dir, cache_dir)
    db_path = Path(bm25_store.db_path)
    if not force and _read_meta(db_path, "bundle_fingerprint") == fingerprint and bm25_store.count() > 0:
        stats = read_index_stats(db_path)
        stats["skipped"] = True
        return stats

    # The bundle changed (or a rebuild was forced): start from a clean index so no stale chunks survive,
    # but keep documents that were ingested at runtime (admin ingest / live lex.uz lookups).
    preserved: list[LegalChunk] = []
    if bm25_store.count() > 0:
        preserved = [c for c in bm25_store.iter_chunks() if str((c.extra or {}).get("source")) not in BUNDLED_SOURCES]
    bm25_store.clear()
    per_source: dict[str, dict[str, Any]] = {}
    total = 0

    def _account(source: str, chunks: list[LegalChunk]) -> None:
        entry = per_source.setdefault(source, {"chunks": 0, "documents": set()})
        entry["chunks"] += len(chunks)
        entry["documents"].update(c.canonical_id for c in chunks)

    registered: set[tuple[str, str]] = set()
    for name in ("uz_latn_codes.jsonl.gz", "ru_codes.jsonl.gz"):
        batch: list[LegalChunk] = []
        for rec in iter_corpus_records(corpus_dir / name):
            rec_chunks = corpus_record_to_chunks(rec)
            batch.extend(rec_chunks)
            reg_key = (str(rec["lang"]), str(rec.get("lex_doc_id") or rec["doc_key"]))
            if rec_chunks and reg_key not in registered:
                registered.add(reg_key)
                first = rec_chunks[0]
                registry.upsert(
                    DocumentMetadata(
                        doc_id=first.doc_id,
                        canonical_id=first.canonical_id,
                        title=first.doc_title,
                        doc_type=first.doc_type,
                        language=first.language,
                        adoption_date=first.adoption_date,
                        status=NormStatus.IN_FORCE,
                        legal_force_rank=first.legal_force_rank,
                        branches=first.branches,
                        url=first.url,
                        source=str(first.extra.get("source")),
                    )
                )
            if len(batch) >= 800:
                bm25_store.upsert_chunks(batch)
                for c in batch:
                    _account(str(c.extra.get("source")), [c])
                total += len(batch)
                batch = []
        if batch:
            bm25_store.upsert_chunks(batch)
            for c in batch:
                _account(str(c.extra.get("source")), [c])
            total += len(batch)

    metas, cache_chunks = load_lex_cache_extras(cache_dir, parser)
    for meta in metas:
        registry.upsert(meta)
    if cache_chunks:
        bm25_store.upsert_chunks(cache_chunks)
        _account("lex_uz_live_cache", cache_chunks)
        total += len(cache_chunks)

    curated = load_curated_facts(corpus_dir / "curated_facts.json")
    if curated:
        bm25_store.upsert_chunks(curated)
        _account("curated_facts", curated)
        total += len(curated)

    bundled_max_rid = bm25_store.max_rid()
    if preserved:
        bm25_store.upsert_chunks(preserved)
        total += len(preserved)

    stats = {
        "fingerprint": fingerprint,
        "curated_updated": _curated_updated(corpus_dir / "curated_facts.json"),
        "bundled_max_rid": bundled_max_rid,
        "schema": INDEX_SCHEMA_VERSION,
        "total_chunks": total,
        "sources": {k: {"chunks": v["chunks"], "documents": len(v["documents"])} for k, v in per_source.items()},
        "skipped": False,
    }
    bm25_store.optimize()
    _write_meta(db_path, {"bundle_fingerprint": fingerprint, "bundle_stats": json.dumps(stats, ensure_ascii=False)})
    return stats


def runtime_ingested_counts(bm25_store: Any, index_stats: dict[str, Any]) -> tuple[int, int]:
    """(documents, chunks) added at runtime (admin ingest, live lex.uz lookups) after the bundled build."""
    if not index_stats or "bundled_max_rid" not in index_stats:
        return 0, 0
    chunks, docs = bm25_store.count_after(int(index_stats["bundled_max_rid"]))
    return docs, chunks


def source_registry(
    index_stats: dict[str, Any], *, live_enabled: bool, runtime_counts: tuple[int, int] = (0, 0)
) -> list[SourceInfo]:
    """Describe every knowledge source with live document/chunk counts from the index."""
    counts = dict(index_stats.get("sources", {})) if index_stats else {}
    counts["runtime_ingested"] = {"documents": runtime_counts[0], "chunks": runtime_counts[1]}

    def _c(key: str) -> tuple[int, int]:
        entry = counts.get(key) or {}
        return int(entry.get("documents", 0)), int(entry.get("chunks", 0))

    d1, c1 = _c("uzbek_legal_corpus_cc0")
    d2, c2 = _c("uz_rag_eval_aligned")
    d3, c3 = _c("lex_uz_live_cache")
    d4, c4 = _c("curated_facts")
    d5, c5 = _c("runtime_ingested")
    return [
        SourceInfo(
            id="uzbek_legal_corpus_cc0",
            name="Uzbek Legal Corpus (lex.uz, oʻzbek lotin)",
            kind="bundled_corpus",
            languages=["uz_latn"],
            url="https://github.com/javohirmat/uzbek-legal-corpus",
            license="CC0-1.0 (rasmiy matnlar mualliflik huquqi obyekti emas, OʻRQ-42, 8-modda)",
            snapshot="2026-07",
            description="Konstitutsiya, 20 ta kodeks va 4 ta asosiy qonunning tozalangan, moddama-modda matni.",
            documents=d1,
            chunks=c1,
            available=c1 > 0,
        ),
        SourceInfo(
            id="uz_rag_eval_aligned",
            name="Lex.uz kodekslari — rus tilidagi rasmiy matnlar",
            kind="bundled_corpus",
            languages=["ru", "uz_latn"],
            url="https://github.com/diyorjon-olimjonov/uz-rag-eval",
            license="MIT (matnlar manbasi: lex.uz)",
            snapshot="2025",
            description="21 ta kodeks va Konstitutsiyaning rus tilidagi matni hamda Uy-joy kodeksi (oʻzbekcha).",
            documents=d2,
            chunks=c2,
            available=c2 > 0,
        ),
        SourceInfo(
            id="lex_uz_live_cache",
            name="Lex.uz — saqlangan hujjatlar",
            kind="lex_snapshot",
            languages=["uz_cyrl"],
            url="https://lex.uz",
            license="Rasmiy manba",
            snapshot="2026",
            description="Shaxsga doir maʼlumotlar va normativ-huquqiy hujjatlar toʻgʻrisidagi qonunlar.",
            documents=d3,
            chunks=c3,
            available=c3 > 0,
        ),
        SourceInfo(
            id="curated_facts",
            name="Amaliy koʻrsatkichlar (BHM, eng kam ish haqi)",
            kind="curated",
            languages=["uz_latn", "ru"],
            url="https://www.gazeta.uz/oz/2026/06/23/ish-haqi-nafaqalar/",
            license="Rasmiy farmonlar asosida",
            snapshot=str(index_stats.get("curated_updated") or "2026-09-01"),
            description="Tez-tez soʻraladigan koʻrsatkichlar: BHM, MHTEKM, pensiya bazaviy miqdori.",
            documents=d4,
            chunks=c4,
            available=c4 > 0,
        ),
        SourceInfo(
            id="lex_uz_live",
            name="Lex.uz jonli qidiruv",
            kind="live",
            languages=["uz_latn", "uz_cyrl", "ru", "en"],
            url="https://lex.uz",
            license="Rasmiy manba",
            snapshot="real vaqt",
            description="Mahalliy bazada topilmagan hujjatlar lex.uz dan jonli olinadi va indeksga qoʻshiladi.",
            documents=d5,
            chunks=c5,
            available=live_enabled,
        ),
    ]
