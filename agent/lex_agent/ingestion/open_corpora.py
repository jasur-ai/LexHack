"""Bundled open legal corpora: loaders, source registry, and the offline index builder.

The agent ships with an offline knowledge base so that answering never depends on a slow live scrape:

* ``lawcodex_uz.jsonl.gz`` / ``lawcodex_ru.jsonl.gz`` — the Constitution, all 21 codes and every substantive law
  in force (410 acts, including laws restated "in a new edition" such as the law on appeals of individuals and
  legal entities) in Uzbek (Cyrillic, as published) and Russian, consolidated as of 2026-10-12 (LawCodex/uz export
  of lex.uz; built by ``scripts/bundle_lawcodex.py``). ``catalog.json`` lists the acts with their Uzbek/Russian
  lex.uz ids, numbers, dates and branches.
* ``historical_uz.jsonl.gz`` — the 1992 Constitution (valid until 2023-05-01) for questions about past dates.
* ``uz_latn_codes.jsonl.gz`` / ``ru_codes.jsonl.gz`` — optional extra corpora (Latin / Russian article records);
  only acts missing from LawCodex are indexed.
* ``lex_cache/`` — documents captured from lex.uz by the live fetcher (indexed only when not covered above).
* ``practical_facts.json`` — the practical figures pack: BHM / minimum wage / pension base history, the Central
  Bank rate, key statutory rules, deadlines and state-duty rates, each with its source and effective date
  (``curated_facts.json`` from older bundles is still understood).

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
from collections import Counter
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from lex_agent.chunk_text import article_body
from lex_agent.language.textproc import surface_tokens
from lex_agent.language.transliterator import cyrillic_to_latin, normalize_uzbek_apostrophes
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

INDEX_SCHEMA_VERSION = "2026.11-r4"
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

# Sources that ``build_bundled_index`` regenerates from files shipped with the repository.
BUNDLED_SOURCES = frozenset(
    {
        "lawcodex_uz",
        "lawcodex_ru",
        "lex_uz_historical",
        "uzbek_legal_corpus_cc0",
        "uz_rag_eval_aligned",
        "lex_uz_live_cache",
        "curated_facts",
        "practical_facts",
    }
)

_DOC_TYPES_BY_NAME: dict[str, DocumentType] = {
    "constitution": DocumentType.CONSTITUTION,
    "constitutional_law": DocumentType.CONSTITUTIONAL_LAW,
    "code": DocumentType.CODE,
    "law": DocumentType.LAW,
}

# lex.uz documents captured by the live fetcher that are NOT covered by the bundled corpora
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


def _parse_date(value: Any) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _amendment_note(rec: dict[str, Any]) -> str | None:
    """Short provenance line of the latest amendment of an article ("ЎРҚ-1158, 14.07.2026")."""
    notes = rec.get("notes") or []
    if not notes:
        return None
    last = notes[-1]
    act = str(last.get("act") or "").strip()
    published = str(last.get("published") or "").strip()
    if not act and not published:
        return None
    return ", ".join(p for p in (act, published) if p)


def corpus_record_to_chunks(
    rec: dict[str, Any], *, branches: list[LegalBranch] | None = None, catalog_entry: dict[str, Any] | None = None
) -> list[LegalChunk]:
    """Convert one bundled article record into one or more structure-aware chunks."""
    language = Language(rec["lang"])
    doc_key = str(rec["doc_key"])
    # lex.uz serves the Latin-script edition of an act under the negative id ("-6257288"): keep it for links
    lex_doc_id = str(rec.get("lex_doc_id") or doc_key) or doc_key
    title = str(rec["doc_title"]).strip()
    stitle = str(rec.get("short_title") or "").strip() or short_title(title, language)
    doc_type = _DOC_TYPES_BY_NAME.get(str(rec.get("doc_type") or "")) or _doc_type_for(
        str(rec.get("code") or ""), title, doc_key
    )
    article_id = rec.get("article_id")
    art_display = rec.get("article_display")
    is_front = article_id in ("_front", "_end")
    if is_front:
        art_label = None
    else:
        art_label = art_display or (
            (f"Статья {article_id}" if language == Language.RU else f"{article_id}-modda") if article_id else None
        )
    art_title = (rec.get("article_title") or "").strip() or None
    body = _strip_leading_header(str(rec["text"]).strip(), None if is_front else article_id)
    adopted = _parse_date(rec.get("adopted"))
    expiry = _parse_date(rec.get("expiry"))
    status = NormStatus(rec["status"]) if rec.get("status") in {s.value for s in NormStatus} else NormStatus.IN_FORCE
    doc_number = (rec.get("doc_number") or "").strip() or None

    header = stitle
    if art_label:
        header = f"{stitle} · {art_label}" + (f". {art_title}" if art_title else "")
    parts = _split_long_text(body)
    amended = _amendment_note(rec)
    linked: dict[str, str] = {}
    if catalog_entry:
        if catalog_entry.get("uz_id"):
            linked["uz"] = str(catalog_entry["uz_id"])
        if catalog_entry.get("ru_id"):
            linked["ru"] = str(catalog_entry["ru_id"])
    chunks: list[LegalChunk] = []
    for idx, part in enumerate(parts, start=1):
        text = f"{header}\n{part}"
        part_suffix = f"#{idx}" if len(parts) > 1 else ""
        occurrence = f"~{rec['occurrence']}" if rec.get("occurrence") else ""
        chunk_id = f"{rec['source']}:{language.value}:{doc_key}:{article_id or 'body'}{occurrence}{part_suffix}"
        extra: dict[str, Any] = {
            "source": rec["source"],
            "short_title": stitle,
            "snapshot": rec.get("snapshot"),
        }
        if article_id and not is_front:
            extra["article_id"] = str(article_id)
        if amended:
            extra["amended"] = amended
        if linked:
            extra["editions"] = linked
        chunks.append(
            LegalChunk(
                chunk_id=chunk_id,
                doc_id=lex_doc_id,
                canonical_id=doc_key,
                language=language,
                doc_type=doc_type,
                doc_number=doc_number,
                doc_title=title,
                adoption_date=adopted,
                expiry_date=expiry,
                status=status,
                legal_force_rank=LEGAL_FORCE_HIERARCHY.get(doc_type, 20),
                branches=branches or _DOC_BRANCHES.get(doc_key, [LegalBranch.GENERAL]),
                section=rec.get("section") or None,
                chapter=rec.get("chapter") or None,
                article=art_label,
                article_title=art_title,
                clause=f"{idx}/{len(parts)}" if len(parts) > 1 else None,
                text=text,
                url=lex_url(lex_doc_id, language),
                extra=extra,
            )
        )
    return chunks


def load_catalog(corpus_dir: Path) -> dict[str, dict[str, Any]]:
    """The LawCodex act catalog keyed by canonical (Uzbek lex.uz) document id; empty when not bundled."""
    path = corpus_dir / "catalog.json"
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Unreadable act catalog %s: %s", path, exc)
        return {}
    return {str(d["doc_key"]): d for d in data.get("documents", [])}


def _catalog_branches(entry: dict[str, Any] | None, doc_key: str) -> list[LegalBranch]:
    if doc_key in _DOC_BRANCHES:
        return _DOC_BRANCHES[doc_key]
    out: list[LegalBranch] = []
    for b in (entry or {}).get("branches") or []:
        try:
            out.append(LegalBranch(b))
        except ValueError:
            continue
    return out or [LegalBranch.GENERAL]


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


def load_lex_cache_extras(
    cache_dir: Path, parser: Any, *, skip: set[str] | frozenset[str] = frozenset()
) -> tuple[list[DocumentMetadata], list[LegalChunk]]:
    """Parse cached lex.uz documents that complement the bundled corpora (Uzbek Cyrillic editions)."""
    metas: list[DocumentMetadata] = []
    chunks: list[LegalChunk] = []
    for doc_id, info in _LEX_CACHE_EXTRA.items():
        if doc_id in skip:
            continue
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
                url=fact["url"],
                extra={"source": "curated_facts", "short_title": fact["short_title"], "snapshot": data.get("updated")},
            )
        )
    return chunks


_FACT_TITLES: dict[str, tuple[str, str, str]] = {
    "income_tax": ("Jismoniy shaxslar daromad solig'i stavkasi", "Ставка налога на доходы физических лиц", "Personal income tax rate"),
    "alimony": ("Aliment miqdori (ulushlar va eng kam miqdor)", "Размер алиментов (доли и минимум)", "Child support shares and minimum"),
    "severance": ("Ishdan bo'shatish nafaqasi miqdori", "Размер выходного пособия", "Severance pay scale"),
    "wage_delay": ("Ish haqi kechiktirilganda kompensatsiya", "Компенсация за задержку зарплаты", "Compensation for delayed wages"),
    "tax_penalty": ("Soliq penyasi stavkasi", "Ставка налоговой пени", "Tax late-payment interest"),
    "vacation_pay": ("Ta'til pulini hisoblash", "Расчёт отпускных", "How holiday pay is calculated"),
    "consumer_exchange": ("Sifatli tovarni 10 kunda almashtirish", "Обмен качественного товара в течение 10 дней", "10-day exchange of proper-quality goods"),
    "deadlines": ("Asosiy muddatlar", "Основные сроки", "Key deadlines"),
    "state_duty": ("Davlat boji stavkalari (asosiylari)", "Ставки госпошлины (основные)", "State duty rates (main)"),
}
_FACT_HEADER = {"uz_latn": "Amaliy ko'rsatkichlar", "ru": "Практические показатели", "en": "Practical figures"}


def _rule_reference(entry: dict[str, Any], doc: str, article: str, key: str) -> str:
    """' (Mehnat kodeksi, 333-modda)' / ' (Трудовой кодекс, статья 333)' / ' (Labour Code, art. 333)'."""
    if key == "en":
        from lex_agent.assistant.act_names import en_title

        title = en_title(doc)
        return f" ({title}, art. {article})" if title else ""
    if key == "ru":
        title = entry.get("short_ru") or ""
        return f" ({title}, статья {article})" if title else ""
    title = entry.get("short_uz") or ""
    if title and any("\u0400" <= ch <= "\u04ff" for ch in title):
        title = cyrillic_to_latin(title)
    return f" ({title}, {article}-modda)" if title else ""


def load_practical_facts(path: Path, catalog: dict[str, dict[str, Any]] | None = None) -> list[LegalChunk]:
    """Chunks for the practical figures pack (one per series / rule / group, in Uzbek, Russian and English)."""
    from lex_agent.knowledge.facts import FACTS_DOC_ID, FactsPack

    if not path.exists():
        return []
    try:
        pack = FactsPack(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, ValueError) as exc:
        logger.warning("Practical facts pack %s skipped: %s", path, exc)
        return []
    catalog = catalog or {}
    langs = ((Language.UZ_LATN, "uz"), (Language.RU, "ru"), (Language.EN, "en"))
    chunks: list[LegalChunk] = []

    def _add(item_id: str, lang: Language, title: str, text: str, *, doc_type: DocumentType, url: str,
             effective: date | None, number: str | None = None, branches: list[LegalBranch] | None = None) -> None:
        header = _FACT_HEADER[lang.value]
        chunks.append(
            LegalChunk(
                chunk_id=f"facts:{lang.value}:{item_id}",
                doc_id=FACTS_DOC_ID,
                canonical_id=FACTS_DOC_ID,
                language=lang,
                doc_type=doc_type,
                doc_number=number,
                doc_title=header,
                effective_date=effective,
                status=NormStatus.IN_FORCE,
                legal_force_rank=LEGAL_FORCE_HIERARCHY.get(doc_type, 20),
                branches=branches or [LegalBranch.GENERAL],
                article=title,
                article_title=title,
                text=f"{header} · {title}\n{text}",
                url=url,
                extra={"source": "practical_facts", "short_title": header, "snapshot": pack.updated,
                       "article_id": item_id},
            )
        )

    for series in pack.series:
        latest = (pack.history(series) or [None])[0]
        for lang, key in langs:
            _add(series, lang, pack.name(series, key), pack.series_text(series, key),
                 doc_type=DocumentType.DEPARTMENTAL_ACT if series == "cbu_rate" else DocumentType.PRESIDENTIAL_DECREE,
                 url=latest.url if latest else "https://lex.uz", effective=latest.start if latest else None,
                 branches=[LegalBranch.LABOR, LegalBranch.ADMINISTRATIVE, LegalBranch.TAX])
    for rule_id, rule in pack.rules.items():
        entry = catalog.get(str(rule.get("doc"))) or {}
        doc_type = DocumentType.CODE if entry.get("doc_type") == "code" else DocumentType.LAW
        titles = _FACT_TITLES.get(rule_id, (rule_id, rule_id, rule_id))
        for (lang, key), title in zip(langs, titles):
            ref = _rule_reference(entry, str(rule.get("doc")), str(rule.get("article")), key)
            _add(rule_id, lang, title, pack.text(rule, key) + ref, doc_type=doc_type,
                 url=lex_url(str(rule.get("doc")), Language.RU if key == "ru" else Language.UZ_CYRL), effective=None)
    for group, items in (("deadlines", pack.deadlines), ("state_duty", pack.state_duty)):
        if not items:
            continue
        titles = _FACT_TITLES[group]
        for (lang, key), title in zip(langs, titles):
            body = "\n".join(f"- {pack.text(it, key)}" for it in items.values())
            _add(group, lang, title, body, doc_type=DocumentType.LAW,
                 url=lex_url("4680944" if group == "state_duty" else "6257288", Language.UZ_CYRL), effective=None)
    return chunks


def bundle_fingerprint(corpus_dir: Path, cache_dir: Path) -> str:
    from lex_agent.language.textproc import ANALYZER_VERSION

    h = hashlib.sha256(f"{INDEX_SCHEMA_VERSION}+{ANALYZER_VERSION}".encode())
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


def _registry_meta(first: LegalChunk, entry: dict[str, Any] | None) -> DocumentMetadata:
    linked_ids: dict[str, str] = {}
    linked_urls: dict[str, str] = {}
    if entry:
        if entry.get("uz_id"):
            linked_ids["uz_cyrl"] = str(entry["uz_id"])
            linked_urls["uz_cyrl"] = lex_url(str(entry["uz_id"]), Language.UZ_CYRL)
        if entry.get("ru_id"):
            linked_ids["ru"] = str(entry["ru_id"])
            linked_urls["ru"] = lex_url(str(entry["ru_id"]), Language.RU)
    return DocumentMetadata(
        doc_id=first.doc_id,
        canonical_id=first.canonical_id,
        title=first.doc_title,
        doc_type=first.doc_type,
        doc_number=first.doc_number,
        language=first.language,
        adoption_date=first.adoption_date,
        expiry_date=first.expiry_date,
        status=first.status,
        legal_force_rank=first.legal_force_rank,
        branches=first.branches,
        url=first.url,
        linked_doc_ids=linked_ids,
        linked_urls=linked_urls,
        source=str(first.extra.get("source")),
    )


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
    catalog = load_catalog(corpus_dir)

    surface: Counter[str] = Counter()

    def _account(chunks: list[LegalChunk]) -> None:
        for c in chunks:
            entry = per_source.setdefault(str(c.extra.get("source")), {"chunks": 0, "documents": set()})
            entry["chunks"] += 1
            entry["documents"].add(c.canonical_id)
            words = surface_tokens(article_body(c), language=c.language.value)
            surface.update({w for w in words if len(w) >= 4 and w.isalpha()})

    # Acts covered by the consolidated LawCodex export, per language family ("uz" / "ru").
    covered: dict[str, set[str]] = {"uz": set(), "ru": set()}
    registered: set[tuple[str, str]] = set()

    def _index_file(name: str, *, family: str | None = None, skip_family: str | None = None) -> None:
        nonlocal total
        batch: list[LegalChunk] = []
        for rec in iter_corpus_records(corpus_dir / name):
            doc_key = str(rec["doc_key"])
            if skip_family and doc_key in covered[skip_family]:
                continue
            entry = catalog.get(doc_key)
            rec_chunks = corpus_record_to_chunks(
                rec, branches=_catalog_branches(entry, doc_key), catalog_entry=entry
            )
            if not rec_chunks:
                continue
            reg_key = (str(rec["lang"]), rec_chunks[0].doc_id)
            if reg_key not in registered:
                registered.add(reg_key)
                registry.upsert(_registry_meta(rec_chunks[0], entry))
            if family:
                covered[family].add(doc_key)
            batch.extend(rec_chunks)
            if len(batch) >= 1000:
                bm25_store.upsert_chunks(batch)
                _account(batch)
                total += len(batch)
                batch = []
        if batch:
            bm25_store.upsert_chunks(batch)
            _account(batch)
            total += len(batch)

    _index_file("lawcodex_uz.jsonl.gz", family="uz")
    _index_file("lawcodex_ru.jsonl.gz", family="ru")
    _index_file("historical_uz.jsonl.gz")
    _index_file("uz_latn_codes.jsonl.gz", skip_family="uz")
    _index_file("ru_codes.jsonl.gz", skip_family="ru")

    metas, cache_chunks = load_lex_cache_extras(cache_dir, parser, skip=frozenset(covered["uz"]))
    for meta in metas:
        registry.upsert(meta)
    if cache_chunks:
        bm25_store.upsert_chunks(cache_chunks)
        _account(cache_chunks)
        total += len(cache_chunks)

    curated = load_curated_facts(corpus_dir / "curated_facts.json")
    curated += load_practical_facts(corpus_dir / "practical_facts.json", catalog)
    if curated:
        bm25_store.upsert_chunks(curated)
        _account(curated)
        total += len(curated)

    surface_terms = bm25_store.replace_surface_vocabulary(dict(surface)) if hasattr(
        bm25_store, "replace_surface_vocabulary"
    ) else 0
    bundled_max_rid = bm25_store.max_rid()
    if preserved:
        bm25_store.upsert_chunks(preserved)
        total += len(preserved)

    stats = {
        "fingerprint": fingerprint,
        "curated_updated": _curated_updated(corpus_dir / "practical_facts.json")
        if (corpus_dir / "practical_facts.json").exists()
        else _curated_updated(corpus_dir / "curated_facts.json"),
        "bundled_max_rid": bundled_max_rid,
        "schema": INDEX_SCHEMA_VERSION,
        "total_chunks": total,
        "catalog_documents": len(catalog),
        "surface_vocabulary": surface_terms,
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

    def _c(*keys: str) -> tuple[int, int]:
        docs = chunks = 0
        for key in keys:
            entry = counts.get(key) or {}
            docs += int(entry.get("documents", 0))
            chunks += int(entry.get("chunks", 0))
        return docs, chunks

    d_uz, c_uz = _c("lawcodex_uz")
    d_ru, c_ru = _c("lawcodex_ru")
    d_hist, c_hist = _c("lex_uz_historical")
    d_cc0, c_cc0 = _c("uzbek_legal_corpus_cc0")
    d_al, c_al = _c("uz_rag_eval_aligned")
    d_cache, c_cache = _c("lex_uz_live_cache")
    d_facts, c_facts = _c("curated_facts", "practical_facts")
    d_live, c_live = _c("runtime_ingested")
    sources = [
        SourceInfo(
            id="lawcodex_uz",
            name="Lex.uz — amaldagi qonunlar va kodekslar (oʻzbekcha)",
            kind="bundled_corpus",
            languages=["uz_cyrl", "uz_latn"],
            url="https://github.com/LawCodex/uz",
            license="Rasmiy matnlar mualliflik huquqi obyekti emas (OʻRQ-42, 8-modda)",
            snapshot="2026-10-12",
            description="Konstitutsiya, barcha kodekslar va amaldagi qonunlarning joriy tahriri, moddama-modda "
            "(kirill matni; lotin yozuvida ham koʻrsatiladi).",
            documents=d_uz,
            chunks=c_uz,
            available=c_uz > 0,
        ),
        SourceInfo(
            id="lawcodex_ru",
            name="Lex.uz — действующие законы и кодексы (на русском)",
            kind="bundled_corpus",
            languages=["ru"],
            url="https://github.com/LawCodex/uz",
            license="Официальные тексты не являются объектами авторского права",
            snapshot="2026-10-12",
            description="Конституция, все кодексы и действующие законы в актуальной редакции, постатейно.",
            documents=d_ru,
            chunks=c_ru,
            available=c_ru > 0,
        ),
        SourceInfo(
            id="lex_uz_historical",
            name="Tarixiy tahrirlar (1992-yilgi Konstitutsiya)",
            kind="historical",
            languages=["uz_cyrl"],
            url="https://lex.uz/docs/20596",
            license="Rasmiy manba",
            snapshot="2023-04-30",
            description="2023-yil 1-maygacha amal qilgan Konstitutsiya matni — oʻtgan sanalar haqidagi savollar uchun.",
            documents=d_hist,
            chunks=c_hist,
            available=c_hist > 0,
        ),
    ]
    if c_cc0:
        sources.append(
            SourceInfo(
                id="uzbek_legal_corpus_cc0",
                name="Uzbek Legal Corpus (oʻzbek lotin)",
                kind="bundled_corpus",
                languages=["uz_latn"],
                url="https://github.com/javohirmat/uzbek-legal-corpus",
                license="CC0-1.0",
                snapshot="2026-07",
                description="LawCodex toʻplamida boʻlmagan hujjatlar (lotin yozuvida).",
                documents=d_cc0,
                chunks=c_cc0,
                available=True,
            )
        )
    if c_al:
        sources.append(
            SourceInfo(
                id="uz_rag_eval_aligned",
                name="Lex.uz kodekslari — rus tilidagi matnlar (eski toʻplam)",
                kind="bundled_corpus",
                languages=["ru"],
                url="https://github.com/diyorjon-olimjonov/uz-rag-eval",
                license="MIT (matnlar manbasi: lex.uz)",
                snapshot="2025",
                description="Faqat LawCodex toʻplamida yoʻq hujjatlar uchun ishlatiladi.",
                documents=d_al,
                chunks=c_al,
                available=True,
            )
        )
    if c_cache:
        sources.append(
            SourceInfo(
                id="lex_uz_live_cache",
                name="Lex.uz — saqlangan hujjatlar",
                kind="lex_snapshot",
                languages=["uz_cyrl"],
                url="https://lex.uz",
                license="Rasmiy manba",
                snapshot="2026",
                description="Jonli yuklab olingan va bazada boshqacha yoʻq hujjatlar.",
                documents=d_cache,
                chunks=c_cache,
                available=True,
            )
        )
    sources += [
        SourceInfo(
            id="curated_facts",
            name="Amaliy koʻrsatkichlar (BHM, eng kam ish haqi, stavkalar, muddatlar, davlat boji)",
            kind="curated",
            languages=["uz_latn", "uz_cyrl", "ru", "en"],
            url="https://lex.uz",
            license="Rasmiy farmon va qonunlar asosida",
            snapshot=str(index_stats.get("curated_updated") or "2026-09-01"),
            description="Tez-tez soʻraladigan koʻrsatkichlar: BHM, MHTEKM va pensiya bazaviy miqdori tarixi, Markaziy "
            "bank stavkasi, soliq va aliment ulushlari, asosiy muddatlar va davlat boji stavkalari — har biri manba va "
            "kuchga kirish sanasi bilan; kalkulyatorlar shu maʼlumotlardan foydalanadi.",
            documents=d_facts,
            chunks=c_facts,
            available=c_facts > 0,
        ),
        SourceInfo(
            id="lex_uz_live",
            name="Lex.uz jonli qidiruv va yangilanishlar",
            kind="live",
            languages=["uz_latn", "uz_cyrl", "ru", "en"],
            url="https://lex.uz",
            license="Rasmiy manba",
            snapshot="real vaqt",
            description="Bazada topilmagan hujjatlar lex.uz dan jonli olinadi; tez-tez kerak boʻladigan hujjatlar "
            "har kecha yangilanish uchun tekshiriladi.",
            documents=d_live,
            chunks=c_live,
            available=live_enabled,
        ),
    ]
    return sources
