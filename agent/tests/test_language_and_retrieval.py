"""Unit tests of text processing, the FTS5 store, the trained ranker, act resolution, spelling, lexicon and facts."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from lex_agent.config import Settings
from lex_agent.knowledge.facts import FACTS_DOC_ID, load_facts
from lex_agent.knowledge.lexicon import fold_ru, fold_uz, get_lexicon
from lex_agent.language.stopwords import stop_terms
from lex_agent.language.textproc import index_terms, query_terms, stem_ru, stem_token, surface_tokens
from lex_agent.language.transliterator import detect_language
from lex_agent.models import DocumentType, Language, LegalChunk, NormStatus
from lex_agent.retrieval.act_resolver import ActResolver
from lex_agent.retrieval.bm25_store import (
    BM25Store,
    article_tokens,
    doc_token,
    number_tokens,
    pack_chunk,
    superscript,
    unpack_chunk,
)
from lex_agent.retrieval.reranker import FEATURE_NAMES, MODEL_PATH, LegalReranker, TreeEnsemble
from lex_agent.retrieval.spelling import SpellingCorrector, max_edits

CORPUS = Path(__file__).resolve().parents[1] / "data" / "corpus"


def _chunk(cid: str, text: str, *, art: str = "1", lang: Language = Language.UZ_LATN, doc: str = "100") -> LegalChunk:
    return LegalChunk(
        chunk_id=cid,
        doc_id=doc,
        canonical_id=doc,
        language=lang,
        doc_type=DocumentType.LAW,
        doc_title="Sinov qonuni",
        status=NormStatus.IN_FORCE,
        article=f"{art}-modda",
        text=text,
        url=f"https://lex.uz/docs/{doc}",
        extra={"article_id": art, "short_title": "Sinov qonuni"},
    )


# ------------------------------------------------------------------------------------------------ text processing


@pytest.mark.parametrize("word", ["ishdan", "ishga", "ishimni", "ishlarim", "ishni"])
def test_uzbek_suffixes_are_stripped_to_the_root(word: str) -> None:
    assert stem_token(word) == "ish"


def test_query_terms_fold_apostrophes_scripts_and_stopwords() -> None:
    assert query_terms("Meni ishdan bo'shatishdi, nima qilay?", language="uz_latn")[:3] == ["men", "ish", "boshat"]
    latin = set(query_terms("mehnat taʼtili", language="uz_latn"))
    cyrillic = set(query_terms("меҳнат таътили", language="uz_cyrl"))
    assert latin == cyrillic  # Latin and Cyrillic Uzbek meet in one index
    assert stem_ru("увольнения") == stem_ru("уволили")
    assert "va" in stop_terms("uz_latn") or "va" not in index_terms("ish va oila", language="uz_latn")


def test_number_and_article_tokens() -> None:
    assert article_tokens("217-modda") == "217"
    assert article_tokens("Статья 128³") == "128 128s3"
    assert article_tokens("104.1") == "104 104s1"
    assert number_tokens("ЎРҚ-782") == number_tokens("O'RQ-782") == "orq782"
    assert doc_token("6257288") == "d6257288"
    assert superscript("128.3") == "128³"
    assert "217" in index_terms("Mehnat kodeksining 217-moddasi", language="uz_latn")


def test_surface_tokens_keep_whole_words() -> None:
    words = surface_tokens("Ishdan bo'shatishdi", language="uz_latn")
    assert "ishdan" in words and all(" " not in w for w in words)


def test_language_detection() -> None:
    assert detect_language("Ishdan bo'shatishdi, nima qilay?") == Language.UZ_LATN
    assert detect_language("Ишдан бўшатишди") == Language.UZ_CYRL
    assert detect_language("Пенсия ёши неча ёш?") == Language.UZ_CYRL
    assert detect_language("Как уволиться по собственному желанию?") == Language.RU
    assert detect_language("How long is annual leave?") == Language.EN


# ------------------------------------------------------------------------------------------------ store


def test_pack_unpack_roundtrip() -> None:
    c = _chunk("x:1", "Matn — «qoʻshtirnoq» va ўзбек ёзуви.")
    back = unpack_chunk(pack_chunk(c))
    assert back == c


def test_contentless_fts_upsert_replaces_old_terms(tmp_path: Path) -> None:
    store = BM25Store(tmp_path / "t.sqlite")
    store.upsert_chunks([_chunk("a:1", "aliment toʻlash tartibi"), _chunk("b:1", "mehnat taʼtili", art="2")])
    assert [h.chunk.chunk_id for h in store.search_terms(["aliment"], top_k=5)] == ["a:1"]
    store.upsert_chunks([_chunk("a:1", "meros guvohnomasi")])  # same id, new text
    assert store.search_terms(["aliment"], top_k=5) == []
    hits = store.search_terms(index_terms("meros", language="uz_latn"), top_k=5)
    assert [h.chunk.chunk_id for h in hits] == ["a:1"]
    assert store.count() == 2
    got = store.get_article("100", "2")
    assert got and got[0].chunk_id == "b:1"


# ------------------------------------------------------------------------------------------------ ranker


def test_tree_ensemble_evaluates_dump_and_rejects_foreign_features(tmp_path: Path) -> None:
    dump = {
        "feature_names": list(FEATURE_NAMES),
        "tree_info": [
            {"tree_structure": {"split_feature": 0, "threshold": 0.5, "decision_type": "<=", "default_left": True,
                                "left_child": {"leaf_value": -1.0}, "right_child": {"leaf_value": 2.0}}},
        ],
    }
    path = tmp_path / "m.json"
    path.write_text(json.dumps(dump), encoding="utf-8")
    model = TreeEnsemble.load(path)
    assert model is not None
    row = [0.0] * len(FEATURE_NAMES)
    assert model.predict(row) == -1.0
    row[0] = 1.0
    assert model.predict(row) == 2.0
    row[0] = float("nan")
    assert model.predict(row) == -1.0  # NaN follows the default branch
    dump["feature_names"] = ["no_such_feature", *FEATURE_NAMES[1:]]
    path.write_text(json.dumps(dump), encoding="utf-8")
    assert TreeEnsemble.load(path) is None


def test_bundled_ranker_model_matches_current_features() -> None:
    assert MODEL_PATH.exists(), "lex_agent/data/reranker_model.json must be shipped with the package"
    model = TreeEnsemble.load(MODEL_PATH)
    assert model is not None and len(model.trees) > 10
    rr = LegalReranker(Settings(reranker_backend="auto"))
    assert rr.backend == "trained"
    assert LegalReranker(Settings(reranker_backend="heuristic")).backend == "heuristic"


# ------------------------------------------------------------------------------------------------ acts, spelling


def test_act_resolver_names_abbreviations_and_articles() -> None:
    resolver = ActResolver.from_corpus(CORPUS)
    refs = resolver.resolve("Mehnat kodeksining 217-moddasi")
    assert refs and refs[0].canonical_id == "6257288" and refs[0].article == "217"
    ru = resolver.resolve("статья 99 Семейного кодекса")
    assert any(r.canonical_id == "104720" and r.article == "99" for r in ru)
    assert resolver.civil_part_for("150") == "111189" and resolver.civil_part_for("1146") == "180552"


def test_spelling_corrects_typos_against_corpus_words(tmp_path: Path) -> None:
    store = BM25Store(tmp_path / "s.sqlite")
    store.replace_surface_vocabulary({"bo'shatishdi": 5, "ta'til": 9, "aliment": 12, "kompensatsiya": 4}, min_doc_freq=2)
    sp = SpellingCorrector(store)
    assert max_edits("abc") == 0 and max_edits("aliment") == 2
    assert sp.nearest("aliment") is None  # known words are kept
    assert sp.nearest("alimet") == "aliment"
    assert sp.nearest("kompensasiya") == "kompensatsiya"


# ------------------------------------------------------------------------------------------------ lexicon, facts


@pytest.mark.parametrize(
    ("query", "lang", "concept"),
    [
        ("bolalarimga aliment qancha to'lanadi", "uz_latn", "family.alimony"),
        ("ishdan haydashdi", "uz_latn", "labour.dismissal.employer"),
        ("ishdan chiqmoqchiman", "uz_latn", "labour.dismissal.own_will"),
        ("меня уволили без предупреждения", "ru", "labour.dismissal"),
        ("ijaraga kvartira berdim, soliq to'lashim kerakmi", "uz_latn", "tax.rental_income"),
        ("eri meni uryapti", "uz_latn", "family.domestic_violence"),
        ("militsiya ushlab oldi", "uz_latn", "criminal.arrest_rights"),
    ],
)
def test_lexicon_maps_everyday_words_to_situations(query: str, lang: str, concept: str) -> None:
    ids = [m.id for m in get_lexicon().match(query, language=lang)]
    assert any(i.startswith(concept) for i in ids), ids


def test_lexicon_folding() -> None:
    assert fold_uz("Oʻgʻil bolaga qancha?") == "ogil bolaga kancha?"
    assert fold_ru("ЁЛКА") == "елка"


def test_facts_values_have_sources_and_dates() -> None:
    facts = load_facts(CORPUS)
    for series in ("bhm", "mhtekm", "pension_base", "cbu_rate"):
        values = facts.history(series)
        assert values, series
        for v in values:
            assert v.source and (v.start or v.as_of), (series, v)
    bhm_2025 = facts.value_on("bhm", date(2025, 9, 1))
    assert bhm_2025 is not None and bhm_2025.value == 412000
    assert facts.value_on("bhm", date(2024, 10, 15)).value == 375000
    assert facts.is_holiday(date(2027, 1, 1)) and facts.is_holiday(date(2026, 3, 20))
    assert not facts.is_holiday(date(2026, 11, 23))
    assert FACTS_DOC_ID == "practical-facts"


# ------------------------------------------------------------------------------------------------ English bridge


def test_english_questions_are_bridged_to_russian_statute_words() -> None:
    from lex_agent.knowledge.synonyms import expansion_text

    text = expansion_text("How long does a court take to decide a civil case?", language="en")
    assert "суд" in text and "сроки рассмотрения" in text and "гражданское дело" in text
    assert "декларация" in expansion_text("When is the deadline for the annual income declaration?", language="en")
    assert detect_language("Hello").value == "en" and detect_language("ok rahmat").value == "uz_latn"


def test_figures_cards_never_outrank_the_law_for_non_figure_questions() -> None:
    from lex_agent.models import RetrievedChunk
    from lex_agent.retrieval.hybrid_retriever import HybridLegalRetriever, QueryAnalysis

    def item(doc: str, score: float) -> RetrievedChunk:
        c = LegalChunk(chunk_id=f"{doc}:1", doc_id=doc, canonical_id=doc, doc_title=doc, doc_type=DocumentType.CODE,
                       language=Language.EN if doc == FACTS_DOC_ID else Language.RU, status=NormStatus.IN_FORCE,
                       article="1", text="x", legal_force_rank=3, url="https://lex.uz")
        return RetrievedChunk(chunk=c, final_score=score)

    items = [item(FACTS_DOC_ID, 2.0), item("3517337", 1.0)]
    plain = QueryAnalysis(query="How long does a court take?", language="en", terms=["court"])
    assert [i.chunk.canonical_id for i in HybridLegalRetriever._demote_figures(plain, list(items))] == ["3517337", FACTS_DOC_ID]
    figures = QueryAnalysis(query="What is the minimum wage?", language="en", terms=["minimum", "wage"])
    assert HybridLegalRetriever._demote_figures(figures, list(items))[0].chunk.canonical_id == FACTS_DOC_ID


def _stem_in_threads(words_ru: list[str], words_en: list[str], workers: int = 8, rounds: int = 16):
    import sys
    from concurrent.futures import ThreadPoolExecutor

    from lex_agent.language.textproc import stem_en, stem_ru

    def run(_):  # bypass the lru caches so every call really reaches a stemmer object
        return [stem_ru.__wrapped__(w) for w in words_ru], [stem_en.__wrapped__(w) for w in words_en]

    old = sys.getswitchinterval()
    sys.setswitchinterval(1e-6)  # force frequent thread switches inside stemWord
    try:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            return list(pool.map(run, range(rounds)))
    finally:
        sys.setswitchinterval(old)


def test_stemmers_are_safe_to_use_from_search_worker_threads():
    from lex_agent.language.textproc import stem_en, stem_ru

    ru = ["увольнение", "уволили", "работодатель", "заработной", "отпускные", "алименты", "наследство",
          "превышение", "скорости", "штрафа", "жилищного", "потребителя", "договора", "расторжении"] * 40
    en = ["dismissed", "employer", "wages", "inheritance", "speeding", "consumer", "contracts", "termination"] * 40
    expected = ([stem_ru.__wrapped__(w) for w in ru], [stem_en.__wrapped__(w) for w in en])
    for got in _stem_in_threads(ru, en):
        assert got == expected
