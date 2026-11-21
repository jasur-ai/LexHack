"""Re-create the bundled open legal corpora shipped in ``agent/data/corpus``.

Sources (all texts originate from the National Database of Legislation, lex.uz; official legal texts are
not objects of copyright under Article 8 of the Law of the Republic of Uzbekistan "On Copyright and
Related Rights", OʻRQ-42):

1. ``javohirmat/uzbek-legal-corpus`` (GitHub, data CC0-1.0) — 25 audited codes/laws in Uzbek Latin,
   article-level JSONL, snapshot 2026-07.
2. ``diyorjon-olimjonov/uz-rag-eval`` (GitHub, MIT) — 6,827 aligned Russian articles of 21 codes (derived from
   ``sukhrobnurali/uzbek-legal-corpus-v1``) plus the Uzbek Latin Housing Code that source #1 lacks.

Usage (needs outbound access to codeload.github.com)::

    python scripts/bundle_open_corpora.py --out data/corpus
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import json
import tarfile
import urllib.request
from pathlib import Path

TOMARIS_TARBALL = "https://codeload.github.com/javohirmat/uzbek-legal-corpus/tar.gz/refs/heads/main"
UZ_RAG_EVAL_TARBALL = "https://codeload.github.com/diyorjon-olimjonov/uz-rag-eval/tar.gz/refs/heads/main"

# Official Russian titles for the aligned Russian corpus (keyed by the Uzbek lex.uz document id).
RU_TITLES: dict[str, str] = {
    "6445145": "Конституция Республики Узбекистан",
    "111189": "Гражданский кодекс Республики Узбекистан (часть первая)",
    "180552": "Гражданский кодекс Республики Узбекистан (часть вторая)",
    "111453": "Уголовный кодекс Республики Узбекистан",
    "111460": "Уголовно-процессуальный кодекс Республики Узбекистан",
    "163629": "Уголовно-исполнительный кодекс Республики Узбекистан",
    "97664": "Кодекс Республики Узбекистан об административной ответственности",
    "6257288": "Трудовой кодекс Республики Узбекистан",
    "4674902": "Налоговый кодекс Республики Узбекистан",
    "3517337": "Гражданский процессуальный кодекс Республики Узбекистан",
    "3523891": "Экономический процессуальный кодекс Республики Узбекистан",
    "3527353": "Кодекс Республики Узбекистан об административном судопроизводстве",
    "2876354": "Таможенный кодекс Республики Узбекистан",
    "104720": "Семейный кодекс Республики Узбекистан",
    "106136": "Жилищный кодекс Республики Узбекистан",
    "2304138": "Бюджетный кодекс Республики Узбекистан",
    "7655343": "Водный кодекс Республики Узбекистан",
    "55594": "Воздушный кодекс Республики Узбекистан",
    "4386848": "Избирательный кодекс Республики Узбекистан",
    "152653": "Земельный кодекс Республики Узбекистан",
    "5307951": "Градостроительный кодекс Республики Узбекистан",
}


def _download_tar(url: str) -> tarfile.TarFile:
    with urllib.request.urlopen(url, timeout=180) as resp:  # noqa: S310 - fixed https URL
        payload = resp.read()
    return tarfile.open(fileobj=io.BytesIO(payload), mode="r:gz")


def _members(tar: tarfile.TarFile, suffix: str) -> list[tarfile.TarInfo]:
    return sorted((m for m in tar.getmembers() if m.isfile() and m.name.endswith(suffix)), key=lambda m: m.name)


def _write_gz_jsonl(path: Path, records: list[dict]) -> str:
    raw = "\n".join(json.dumps(r, ensure_ascii=False, separators=(",", ":")) for r in records).encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.GzipFile(filename=path.name, mode="wb", fileobj=path.open("wb"), mtime=0) as fh:
        fh.write(raw)
    return hashlib.sha256(raw).hexdigest()


def bundle(out_dir: Path) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1) Uzbek Latin audited corpus (CC0)
    tar = _download_tar(TOMARIS_TARBALL)
    manifest_member = next(m for m in tar.getmembers() if m.name.endswith("/manifest.csv"))
    manifest_rows = list(csv.DictReader(io.StringIO(tar.extractfile(manifest_member).read().decode("utf-8-sig"))))
    adopted_by_code = {row["filename"].removesuffix(".txt"): row.get("adopted") or None for row in manifest_rows}

    uz_records: list[dict] = []
    for member in _members(tar, ".jsonl"):
        if "/data/articles/" not in member.name:
            continue
        for line in tar.extractfile(member).read().decode("utf-8").splitlines():
            if not line.strip():
                continue
            rec = json.loads(line)
            if not str(rec.get("text") or "").strip():
                continue
            lex_doc = str(rec.get("lex_uz_doc") or "").strip()
            uz_records.append(
                {
                    "source": "uzbek_legal_corpus_cc0",
                    "lang": "uz_latn",
                    "doc_key": lex_doc.lstrip("-") or rec["code"],
                    "lex_doc_id": lex_doc or None,
                    "code": rec["code"],
                    "doc_title": rec["code_title"],
                    "adopted": adopted_by_code.get(rec["code"]),
                    "article_id": rec.get("article_id"),
                    "article_display": rec.get("article_display"),
                    "article_title": rec.get("title") or None,
                    "section": rec.get("section") or None,
                    "chapter": rec.get("chapter") or None,
                    "text": rec["text"],
                    "snapshot": rec.get("snapshot_date") or "2026-07",
                }
            )

    # 2) Aligned Russian corpus + Uzbek Latin Housing Code (MIT repo; texts from lex.uz)
    tar2 = _download_tar(UZ_RAG_EVAL_TARBALL)
    ru_member = next(m for m in tar2.getmembers() if m.name.endswith("corpus/ru_articles.jsonl"))
    uz_member = next(m for m in tar2.getmembers() if m.name.endswith("corpus/uz_articles.jsonl"))

    def _aligned(member: tarfile.TarInfo, lang: str, only_doc: str | None = None) -> list[dict]:
        out: list[dict] = []
        for line in tar2.extractfile(member).read().decode("utf-8").splitlines():
            if not line.strip():
                continue
            rec = json.loads(line)
            if only_doc and rec["doc_key"] != only_doc:
                continue
            doc_key = str(rec["doc_key"])
            art = str(rec.get("article_number") or "").strip() or None
            title = RU_TITLES.get(doc_key, rec["doc_title"]) if lang == "ru" else (
                "Oʻzbekiston Respublikasining Uy-joy kodeksi" if doc_key == "106136" else rec["doc_title"]
            )
            out.append(
                {
                    "source": "uz_rag_eval_aligned",
                    "lang": lang,
                    "doc_key": doc_key,
                    "lex_doc_id": doc_key if lang == "ru" else f"-{doc_key}",
                    "code": f"lex_{doc_key}",
                    "doc_title": title,
                    "adopted": None,
                    "article_id": art,
                    "article_display": (f"Статья {art}" if lang == "ru" else f"{art}-modda") if art else None,
                    "article_title": rec.get("article_title") or None,
                    "section": rec.get("part") or None,
                    "chapter": rec.get("chapter") or None,
                    "text": rec["text"],
                    "snapshot": "2025",
                }
            )
        return out

    ru_records = _aligned(ru_member, "ru")
    housing_records = _aligned(uz_member, "uz_latn", only_doc="106136")

    files = {
        "uz_latn_codes.jsonl.gz": uz_records + housing_records,
        "ru_codes.jsonl.gz": ru_records,
    }
    summary: dict = {"files": {}}
    for name, recs in files.items():
        digest = _write_gz_jsonl(out_dir / name, recs)
        summary["files"][name] = {
            "records": len(recs),
            "documents": len({r["doc_key"] for r in recs}),
            "sha256_uncompressed": digest,
        }
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path(__file__).resolve().parents[1] / "data" / "corpus")
    args = parser.parse_args()
    print(json.dumps(bundle(args.out), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
