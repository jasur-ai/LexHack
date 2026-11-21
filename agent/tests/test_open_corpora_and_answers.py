"""Tests for the bundled corpora index, query expansion, concise answer format and extractive fallback."""

from __future__ import annotations

import gzip
import json
from pathlib import Path

import pytest

from lex_agent.ingestion.open_corpora import (
    _split_long_text,
    build_bundled_index,
    clean_lex_cache_text,
    corpus_record_to_chunks,
    short_title,
)
from lex_agent.ingestion.parser import LegalDocumentParser
from lex_agent.ingestion.pipeline import DocumentRegistry
from lex_agent.models import Language, LegalBranch, RetrievedChunk
from lex_agent.reasoning.answer_cache import AnswerCache, normalize_question
from lex_agent.reasoning.answer_composer import (
    compose_extractive_answer,
    lead_excerpt,
    parse_answer_sections,
    source_items,
)
from lex_agent.retrieval.bm25_store import BM25Store
from lex_agent.retrieval.query_expansion import expand_query

LABOR_RECORD = {
    "source": "uzbek_legal_corpus_cc0",
    "lang": "uz_latn",
    "doc_key": "6257288",
    "lex_doc_id": "-6257288",
    "code": "mehnat_kodeksi",
    "doc_title": "Oʻzbekiston Respublikasining Mehnat kodeksi",
    "adopted": "2022-10-28",
    "article_id": "217",
    "article_display": "217-modda",
    "article_title": "Har yilgi asosiy eng kam mehnat taʼtilining davomiyligi",
    "section": "II BOʻLIM",
    "chapter": "26-bob",
    "text": "Har yilgi asosiy eng kam mehnat taʼtilining davomiyligi yigirma bir kalendar kunni tashkil etadi.",
    "snapshot": "2026-07",
}

RU_RECORD = {
    "source": "uz_rag_eval_aligned",
    "lang": "ru",
    "doc_key": "6257288",
    "lex_doc_id": "6257288",
    "code": "lex_6257288",
    "doc_title": "Трудовой кодекс Республики Узбекистан",
    "adopted": None,
    "article_id": "161",
    "article_display": "Статья 161",
    "article_title": "Прекращение трудового договора по инициативе работодателя",
    "section": None,
    "chapter": None,
    "text": "Статья 161. Прекращение трудового договора по инициативе работодателя\n\nПрекращение трудового договора по инициативе работодателя должно быть обоснованным.",
    "snapshot": "2025",
}


def _write_corpus(tmp: Path) -> Path:
    corpus = tmp / "corpus"
    corpus.mkdir()
    with gzip.open(corpus / "uz_latn_codes.jsonl.gz", "wt", encoding="utf-8") as fh:
        fh.write(json.dumps(LABOR_RECORD, ensure_ascii=False) + "\n")
        long_rec = dict(LABOR_RECORD, article_id="161", article_display="161-modda",
                        article_title="Mehnat shartnomasini ish beruvchining tashabbusiga koʻra bekor qilish",
                        text="\n".join(f"{i}) asos {'soʻz ' * 60}" for i in range(1, 12)))
        fh.write(json.dumps(long_rec, ensure_ascii=False) + "\n")
    with gzip.open(corpus / "ru_codes.jsonl.gz", "wt", encoding="utf-8") as fh:
        fh.write(json.dumps(RU_RECORD, ensure_ascii=False) + "\n")
    (corpus / "curated_facts.json").write_text(
        json.dumps(
            {
                "updated": "2026-09-01",
                "facts": [
                    {
                        "id": "bhm",
                        "lang": "uz_latn",
                        "doc_id": "pf-115-2026",
                        "doc_number": "PF-115",
                        "title": "Prezident Farmoni PF-115",
                        "short_title": "PF-115",
                        "adopted": "2026-06-23",
                        "effective": "2026-09-01",
                        "branches": ["labor"],
                        "article": "BHM",
                        "url": "https://example.org/pf-115",
                        "text": "2026-yil 1-sentabrdan bazaviy hisoblash miqdori (BHM) — 440 000 soʻm.",
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return corpus


def test_short_title_and_record_to_chunks() -> None:
    assert short_title("Oʻzbekiston Respublikasining Mehnat kodeksi", Language.UZ_LATN) == "Mehnat kodeksi"
    assert short_title("Трудовой кодекс Республики Узбекистан", Language.RU) == "Трудовой кодекс"
    chunks = corpus_record_to_chunks(LABOR_RECORD)
    assert len(chunks) == 1
    c = chunks[0]
    assert c.doc_id == "-6257288" and c.canonical_id == "6257288"
    assert c.url == "https://lex.uz/uz/docs/-6257288"
    assert c.article == "217-modda"
    assert c.text.startswith("Mehnat kodeksi · 217-modda. Har yilgi")
    assert LegalBranch.LABOR in c.branches
    ru = corpus_record_to_chunks(RU_RECORD)[0]
    # the duplicated "Статья 161." header line is stripped from the body
    assert ru.text.count("Статья 161") == 1
    assert ru.url == "https://lex.uz/ru/docs/6257288"


def test_split_long_text_respects_limit() -> None:
    body = "\n".join(f"{i}) " + "soʻz " * 120 for i in range(1, 8))
    parts = _split_long_text(body, limit=900)
    assert len(parts) > 1
    assert all(len(p) <= 900 for p in parts)
    assert "".join(parts).replace("\n", "") .count("soʻz") == body.count("soʻz")


def test_clean_lex_cache_text_strips_toolbar_noise() -> None:
    raw = "Hujjatga taklif yuborish Audioni tinglash Hujjat elementidan havola olish\n1-модда. Мақсад\nМатн"
    assert clean_lex_cache_text(raw) == "1-модда. Мақсад\nМатн"


def test_build_index_is_idempotent_and_searchable(tmp_path: Path) -> None:
    corpus = _write_corpus(tmp_path)
    store = BM25Store(tmp_path / "bm25.sqlite3")
    registry = DocumentRegistry(tmp_path / "registry.sqlite3")
    stats = build_bundled_index(
        bm25_store=store, registry=registry, parser=LegalDocumentParser(), corpus_dir=corpus, cache_dir=tmp_path
    )
    assert stats["skipped"] is False
    assert stats["sources"]["uzbek_legal_corpus_cc0"]["documents"] == 1
    assert stats["sources"]["curated_facts"]["chunks"] == 1
    total = store.count()
    assert total >= 4  # 217 + split 161 parts + ru + curated
    again = build_bundled_index(
        bm25_store=store, registry=registry, parser=LegalDocumentParser(), corpus_dir=corpus, cache_dir=tmp_path
    )
    assert again["skipped"] is True and store.count() == total

    hits = store.search("mehnat ta'tili davomiyligi kalendar kun", top_k=3)
    assert hits and hits[0].chunk.article == "217-modda"
    ru_hits = store.search("прекращение трудового договора", top_k=3)
    assert ru_hits and ru_hits[0].chunk.language == Language.RU
    # upsert of an existing chunk replaces (no duplicates)
    store.upsert_chunks(corpus_record_to_chunks(LABOR_RECORD))
    assert store.count() == total


def test_query_expansion_bridges_colloquial_wording() -> None:
    assert "mehnat shartnomasini ish beruvchining tashabbusiga ko'ra bekor qilish" in expand_query(
        "Ish beruvchi meni ishdan haydadi"
    )
    cyr = expand_query("Алимент миқдори қанча?")
    assert cyr and "aliment" in cyr[0]
    ru = expand_query("Меня уволили без причины")
    assert ru[0].startswith("прекращение трудового договора")
    assert any("bekor qilish" in e for e in ru)  # Russian questions also search the Uzbek corpus
    assert expand_query("") == []


def test_parse_answer_sections_markers_and_fallbacks() -> None:
    text = (
        "### ANSWER\nHa, 21 kalendar kun [1].\n\n### KEY POINTS\n- Mehnat kodeksi, 217-modda: 21 kun [1]\n"
        "- Qo'shimcha ta'tillar qo'shiladi [2]\n### STEPS\n1. Ariza yozing\n2. Imzolating\n"
        "### CAUTION\nJamoa shartnomasini tekshiring.\n### FOLLOW-UPS\n- Ta'til puli qachon to'lanadi\n- Bo'lib olsa bo'ladimi?"
    )
    s = parse_answer_sections(text)
    assert s["structured"] is True
    assert s["answer"] == "Ha, 21 kalendar kun [1]."
    assert len(s["key_points"]) == 2 and s["steps"] == ["Ariza yozing", "Imzolating"]
    assert s["caution"].startswith("Jamoa")
    assert s["follow_ups"] == ["Ta'til puli qachon to'lanadi?", "Bo'lib olsa bo'ladimi?"]

    translated = parse_answer_sections("**Ответ:**\nДа.\n**Основные положения**\n- Пункт [1]")
    assert translated["answer"] == "Да." and translated["key_points"] == ["Пункт [1]"]

    plain = parse_answer_sections("Just a plain answer.")
    assert plain["structured"] is False and plain["answer"] == "Just a plain answer."


def test_extractive_answer_quotes_top_norm_with_citations() -> None:
    chunk = corpus_record_to_chunks(LABOR_RECORD)[0]
    ev = [RetrievedChunk(chunk=chunk, final_score=1.0)]
    text = compose_extractive_answer(query="Ta'til necha kun?", response_lang=Language.UZ_LATN, evidence=ev)
    s = parse_answer_sections(text)
    assert "yigirma bir kalendar kun" in s["answer"] and s["answer"].endswith("[1]")
    assert s["follow_ups"] and s["caution"]
    cyr = compose_extractive_answer(query="Таътил", response_lang=Language.UZ_CYRL, evidence=ev)
    assert "йигирма бир календар кун" in cyr
    none = parse_answer_sections(compose_extractive_answer(query="?", response_lang=Language.RU, evidence=[]))
    assert "не найдена" in none["answer"]
    items = source_items(ev)
    assert items[0]["n"] == 1 and items[0]["title"] == "Mehnat kodeksi" and items[0]["article"] == "217-modda"


def test_lead_excerpt_cuts_on_sentence_boundary() -> None:
    text = "Birinchi gap. " + "Ikkinchi juda uzun gap " * 30
    out = lead_excerpt(text, 80)
    assert out.endswith("…") or out.endswith(".")
    assert len(out) <= 81


def test_answer_cache_ttl_and_lru() -> None:
    cache = AnswerCache(max_items=2, ttl_sec=60)
    cache.put("a", 1)
    cache.put("b", 2)
    assert cache.get("a") == 1
    cache.put("c", 3)  # evicts least recently used ("b")
    assert cache.get("b") is None and cache.get("c") == 3
    assert normalize_question("  BHM  qancha?? ") == "bhm qancha"
    disabled = AnswerCache(max_items=0, ttl_sec=60)
    disabled.put("x", 1)
    assert disabled.get("x") is None


@pytest.mark.parametrize("query", ["", "   "])
def test_expand_query_handles_blank(query: str) -> None:
    assert expand_query(query) == []
