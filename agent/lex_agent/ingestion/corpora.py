"""Offline bootstrap corpora loaders for HuggingFace Lex.uz datasets and local JSONL/Parquet dumps."""

from __future__ import annotations

import json
import logging
import os
import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any

# Silence noisy Windows symlink cache warnings from huggingface_hub
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

from lex_agent.ingestion.lex_fetcher import FetchedDocument
from lex_agent.ingestion.parser import classify_branches, classify_document_type, parse_date_string
from lex_agent.language.transliterator import detect_language, normalize_uzbek_apostrophes
from lex_agent.models import DocumentMetadata, LEGAL_FORCE_HIERARCHY, Language, NormStatus

logger = logging.getLogger(__name__)

# Curated HuggingFace datasets sourced from Lex.uz
SUPPORTED_HF_DATASETS: dict[str, dict[str, str]] = {
    "Alii2004/lexuz-legislation": {
        "description": "77,000+ Lex.uz normative-legal acts in Uzbek (Latin/Cyrillic) and Russian",
        "split": "train",
    },
    "sukhrobnurali/uzbek-legal-corpus": {
        "description": "Article-structured Uzbek Latin national legislation corpus (1991-2026)",
        "split": "train",
    },
    "Mehriddin1997/lex-uzbek-laws": {
        "description": "Structured Uzbek laws subset in JSONL format",
        "split": "train",
    },
}


def _row_to_fetched_document(row: dict[str, Any], source_name: str, fallback_idx: int) -> FetchedDocument | None:
    """Normalize heterogeneous HuggingFace / JSONL Lex.uz schemas into a canonical `FetchedDocument`."""
    text = (
        row.get("text")
        or row.get("content")
        or row.get("body")
        or row.get("article_text")
        or row.get("full_text")
        or ""
    )
    if not isinstance(text, str) or len(text.strip()) < 30:
        return None

    raw_id = (
        row.get("doc_id")
        or row.get("lex_id")
        or row.get("id")
        or row.get("document_id")
        or f"corpus_{fallback_idx}"
    )
    doc_id = str(raw_id).strip()

    # Extract numeric Lex.uz ID from URL if present
    url = str(row.get("url") or row.get("link") or "").strip()
    if url:
        m = re.search(r"/docs/(-?\d+)", url)
        if m:
            doc_id = m.group(1)

    title = str(
        row.get("title")
        or row.get("doc_title")
        or row.get("law_name")
        or row.get("name")
        or f"Lex.uz Document {doc_id}"
    ).strip()
    title = normalize_uzbek_apostrophes(title)

    # Prepend article header if dataset is article-row structured (like sukhrobnurali/uzbek-legal-corpus)
    article_col = row.get("article") or row.get("article_number") or row.get("modda")
    if article_col and str(article_col).strip() and str(article_col) not in text[:100]:
        art_str = str(article_col).strip()
        if re.fullmatch(r"\d+(?:[-.]\d+)?", art_str):
            text = f"{art_str}-modda.\n{text}"
        else:
            text = f"{art_str}\n{text}"

    raw_lang = str(row.get("language") or row.get("lang") or "").lower().strip()
    if raw_lang in ("uz_latn", "uz-latn", "oz", "uzb_latn"):
        lang = Language.UZ_LATN
    elif raw_lang in ("uz_cyrl", "uz-cyrl", "uzb_cyrl"):
        lang = Language.UZ_CYRL
    elif raw_lang in ("ru", "rus", "russian"):
        lang = Language.RU
    elif raw_lang in ("en", "eng", "english"):
        lang = Language.EN
    else:
        lang = detect_language(f"{title}\n{text[:1500]}")

    if not url:
        url = f"https://lex.uz/{lang.lex_path_prefix}/docs/{doc_id}"

    doc_type = classify_document_type(title, text[:1200])
    branches = classify_branches(title, text[:2500])
    doc_number = row.get("doc_number") or row.get("number") or row.get("act_number")
    adoption_date = parse_date_string(row.get("adoption_date") or row.get("date") or row.get("adopted_at"))
    effective_date = parse_date_string(row.get("effective_date") or row.get("in_force_date")) or adoption_date
    expiry_date = parse_date_string(row.get("expiry_date") or row.get("repealed_date"))

    raw_status = str(row.get("status") or "").lower()
    if any(k in raw_status for k in ("repeal", "утрат", "yo'qot", "йўқот", "inactive")):
        status = NormStatus.REPEALED
    elif any(k in raw_status for k in ("amend", "редакц", "o'zgart")):
        status = NormStatus.AMENDED
    elif any(k in raw_status for k in ("force", "действ", "amalda", "active")):
        status = NormStatus.IN_FORCE
    else:
        status = NormStatus.IN_FORCE if expiry_date is None else NormStatus.REPEALED

    canonical_id = str(abs(int(doc_id))) if re.fullmatch(r"-?\d+", doc_id) else doc_id

    metadata = DocumentMetadata(
        doc_id=doc_id,
        canonical_id=canonical_id,
        title=title,
        doc_type=doc_type,
        doc_number=str(doc_number).strip() if doc_number else None,
        language=lang,
        issuing_body=str(row.get("issuing_body") or row.get("authority") or "") or None,
        adoption_date=adoption_date,
        effective_date=effective_date,
        expiry_date=expiry_date,
        status=status,
        legal_force_rank=LEGAL_FORCE_HIERARCHY.get(doc_type, 20),
        branches=branches,
        url=url,
        linked_doc_ids={lang.value: doc_id},
        linked_urls={lang.value: url},
        source=source_name,
    )
    return FetchedDocument(metadata=metadata, raw_text=text)


def _iter_hf_parquet_shards_schema_safe(
    dataset_name: str,
    *,
    max_docs: int | None = None,
) -> Iterator[FetchedDocument]:
    """Read Parquet shards directly via pyarrow so heterogeneous null/string columns never crash Arrow casting."""
    from huggingface_hub import HfApi, hf_hub_download
    import pyarrow.parquet as pq

    api = HfApi()
    repo_files = api.list_repo_files(repo_id=dataset_name, repo_type="dataset")
    parquet_files = sorted(f for f in repo_files if f.lower().endswith(".parquet"))
    if not parquet_files:
        return

    logger.info(
        "Streaming %d Parquet shard(s) directly from %s (schema-safe mode)",
        len(parquet_files),
        dataset_name,
    )
    count = 0
    idx = 0
    for shard_rel_path in parquet_files:
        try:
            local_file = hf_hub_download(
                repo_id=dataset_name,
                filename=shard_rel_path,
                repo_type="dataset",
            )
            pf = pq.ParquetFile(local_file)
            for batch in pf.iter_batches(batch_size=256):
                for row in batch.to_pylist():
                    idx += 1
                    doc = _row_to_fetched_document(row, source_name=dataset_name, fallback_idx=idx)
                    if doc is None:
                        continue
                    yield doc
                    count += 1
                    if max_docs is not None and count >= max_docs:
                        return
        except Exception as exc:
            logger.warning("Skipping shard '%s' due to read error: %s", shard_rel_path, exc)
            continue


def iter_huggingface_corpus(
    dataset_name: str,
    *,
    split: str = "train",
    max_docs: int | None = None,
    streaming: bool = True,
) -> Iterator[FetchedDocument]:
    """Stream normative-legal acts from HuggingFace Lex.uz datasets safely across heterogeneous Parquet shards."""
    # Prefer schema-safe shard-by-shard Parquet reader (avoids HuggingFace Arrow `string -> null` cast crashes
    # on multi-shard datasets like Alii2004/lexuz-legislation).
    yielded_any = False
    try:
        for doc in _iter_hf_parquet_shards_schema_safe(dataset_name, max_docs=max_docs):
            yielded_any = True
            yield doc
        if yielded_any:
            return
    except Exception as exc:
        logger.info("Direct Parquet shard reader fell back to `datasets.load_dataset` (%s)", exc)

    try:
        from datasets import load_dataset
    except ImportError as exc:
        raise RuntimeError(
            "Install HuggingFace datasets (`pip install datasets huggingface-hub pyarrow`) to ingest offline corpora."
        ) from exc

    logger.info("Loading HuggingFace dataset %s (split=%s, streaming=%s)", dataset_name, split, streaming)
    ds = load_dataset(dataset_name, split=split, streaming=streaming)
    count = 0
    for idx, row in enumerate(ds):
        doc = _row_to_fetched_document(dict(row), source_name=dataset_name, fallback_idx=idx)
        if doc is None:
            continue
        yield doc
        count += 1
        if max_docs is not None and count >= max_docs:
            break


def iter_local_jsonl_or_parquet(
    path: Path,
    *,
    max_docs: int | None = None,
) -> Iterator[FetchedDocument]:
    """Load Lex.uz documents from a local `.jsonl`, `.json`, or `.parquet` file or directory."""
    files: list[Path] = [path] if path.is_file() else sorted(path.rglob("*"))
    count = 0
    for file_path in files:
        if not file_path.is_file():
            continue
        suffix = file_path.suffix.lower()
        rows: list[dict[str, Any]] = []

        if suffix == ".jsonl":
            with file_path.open("r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if line:
                        rows.append(json.loads(line))
        elif suffix == ".json":
            payload = json.loads(file_path.read_text(encoding="utf-8"))
            rows = payload if isinstance(payload, list) else [payload]
        elif suffix == ".parquet":
            try:
                import pyarrow.parquet as pq

                pf = pq.ParquetFile(file_path)
                for batch in pf.iter_batches(batch_size=256):
                    for row in batch.to_pylist():
                        doc = _row_to_fetched_document(row, source_name=str(file_path.name), fallback_idx=count)
                        if doc is None:
                            continue
                        yield doc
                        count += 1
                        if max_docs is not None and count >= max_docs:
                            return
                continue
            except ImportError as exc:
                raise RuntimeError("Install `pyarrow` to read `.parquet` datasets.") from exc
        else:
            continue

        for idx, row in enumerate(rows):
            doc = _row_to_fetched_document(row, source_name=str(file_path.name), fallback_idx=count + idx)
            if doc is None:
                continue
            yield doc
            count += 1
            if max_docs is not None and count >= max_docs:
                return
