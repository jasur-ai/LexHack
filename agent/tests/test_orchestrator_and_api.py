"""End-to-end tests of the streaming pipeline (extractive, LLM, LLM failure/timeout, cache) and the HTTP API."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from lex_agent.config import Settings, get_settings
from lex_agent.models import AgentQueryRequest
from lex_agent.runtime import AgentRuntime

from .test_open_corpora_and_answers import _write_corpus


def _settings(tmp_path: Path, **overrides: Any) -> Settings:
    corpus = tmp_path / "corpus"
    if not corpus.exists():
        _write_corpus(tmp_path)
    base: dict[str, Any] = {
        "data_dir": tmp_path / "data",
        "corpus_dir": corpus,
        "llm_provider": "mock",
        "llm_api_key": "",
        "lex_uz_enable_live_fallback": False,
        "llm_first_token_timeout": 0.5,
        "llm_request_timeout": 2.0,
    }
    base.update(overrides)
    cfg = Settings(**base)
    cfg.ensure_directories()
    return cfg


async def _collect(rt: AgentRuntime, query: str, **kw: Any) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    async for ev in rt.orchestrator.answer_stream(AgentQueryRequest(query=query, **kw)):
        events.append(ev)
    return events


def _runtime(tmp_path: Path, **overrides: Any) -> AgentRuntime:
    rt = AgentRuntime.build(_settings(tmp_path, **overrides))
    rt.build_index()
    return rt


@pytest.mark.asyncio
async def test_extractive_stream_has_steps_sources_and_sections(tmp_path: Path) -> None:
    rt = _runtime(tmp_path)
    events = await _collect(rt, "Yillik mehnat ta'tili necha kun?")
    types = [e["type"] for e in events]
    assert types[0] == "step" and types[-1] == "done"
    assert "sources" in types and types.index("sources") < types.index("token")
    resp = events[-1]["response"]
    assert resp.mode == "extractive"
    assert resp.sections and resp.sections.structured
    assert "yigirma bir" in resp.sections.answer
    assert resp.sources[0].article == "217-modda"
    # identical question is served from cache
    again = await _collect(rt, "yillik mehnat ta'tili necha kun")
    assert again[-1]["response"].mode == "cache"
    await rt.close()


@pytest.mark.asyncio
async def test_llm_stream_success_and_failure_fallback(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    rt = _runtime(tmp_path, answer_cache_size=0)
    monkeypatch.setattr(type(rt.llm), "is_mock", property(lambda self: False))

    async def good_stream(self: Any, messages: list[dict[str, Any]], **_: Any) -> AsyncIterator[str]:
        assert "EVIDENCE" in messages[-1]["content"]
        for part in ["### ANSWER\nHa, 21 kalendar kun [1].\n", "### KEY POINTS\n- Mehnat kodeksi, 217-modda [1]\n",
                     "### FOLLOW-UPS\n- Ta'til puli qachon beriladi"]:
            yield part

    monkeypatch.setattr(type(rt.llm), "stream_complete", good_stream)
    events = await _collect(rt, "Yillik mehnat ta'tili necha kun?")
    resp = events[-1]["response"]
    assert resp.mode == "llm"
    assert resp.sections.answer == "Ha, 21 kalendar kun [1]."
    assert resp.sections.follow_ups == ["Ta'til puli qachon beriladi?"]
    assert resp.verification.passed

    async def broken_stream(self: Any, messages: list[dict[str, Any]], **_: Any) -> AsyncIterator[str]:
        raise RuntimeError("AI service error (503)")
        yield ""  # pragma: no cover

    monkeypatch.setattr(type(rt.llm), "stream_complete", broken_stream)
    events = await _collect(rt, "Yillik mehnat ta'tili necha kun?")
    assert any(e["type"] == "replace_answer" and e.get("mode") == "extractive" for e in events)
    assert events[-1]["response"].mode == "extractive"

    async def slow_stream(self: Any, messages: list[dict[str, Any]], **_: Any) -> AsyncIterator[str]:
        await asyncio.sleep(5)
        yield "late"

    monkeypatch.setattr(type(rt.llm), "stream_complete", slow_stream)
    events = await _collect(rt, "Yillik mehnat ta'tili necha kun?")
    assert events[-1]["response"].mode == "extractive"  # first-token deadline (0.5s) triggered the fallback
    await rt.close()


def test_http_api_health_sources_stream_and_admin_guard(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write_corpus(tmp_path)
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("CORPUS_DIR", str(tmp_path / "corpus"))
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    monkeypatch.setenv("LLM_API_KEY", "")
    monkeypatch.setenv("LEX_UZ_ENABLE_LIVE_FALLBACK", "false")
    monkeypatch.setenv("ADMIN_TOKEN", "secret-token")
    get_settings.cache_clear()
    from lex_agent.api.app import create_app

    try:
        with TestClient(create_app()) as client:
            health = client.get("/api/health").json()
            assert health["index_ready"] is True and health["answer_mode"] == "extractive"

            sources = client.get("/api/sources").json()
            ids = {s["id"] for s in sources["sources"]}
            assert {"uzbek_legal_corpus_cc0", "uz_rag_eval_aligned", "curated_facts", "lex_uz_live"} <= ids

            with client.stream("POST", "/api/ask/stream", json={"query": "BHM qancha?"}) as resp:
                assert resp.status_code == 200
                events = [json.loads(line[5:]) for line in resp.iter_lines() if line.startswith("data:")]
            assert events[-1]["type"] == "done"
            final = events[-1]["response"]
            assert "440 000" in final["sections"]["answer"]
            assert final["sources"][0]["url"] == "https://example.org/pf-115"

            sync = client.post("/api/ask", json={"query": "Прекращение трудового договора по инициативе работодателя"})
            assert sync.status_code == 200 and sync.json()["sources"][0]["language"] == "ru"

            denied = client.post("/api/ingest/url", json={"url": "https://example.org/x"})
            assert denied.status_code == 403
    finally:
        get_settings.cache_clear()


@pytest.mark.asyncio
async def test_live_lex_circuit_breaker_skips_after_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    rt = _runtime(tmp_path, lex_uz_enable_live_fallback=True, lex_uz_live_fallback_timeout=0.2)
    retriever = rt.orchestrator.retriever
    calls: list[str] = []

    async def failing_live(self: Any, query: str, **_: Any) -> list[str]:
        calls.append(query)
        raise ConnectionError("lex.uz unreachable")

    monkeypatch.setattr(type(retriever), "_augment_from_live_lex", failing_live)
    # A question with no local match triggers the live lookup once ...
    hits, live_ids = await retriever.retrieve("kosmik kemalar ruxsatnomasi tartibi")
    assert live_ids == [] and len(calls) == 1
    # ... then the breaker is open and the next weak question answers locally without waiting.
    await retriever.retrieve("suv osti kemalari reestri")
    assert len(calls) == 1
    # Once the cooldown passes, live lookups are attempted again.
    retriever._live_circuit_open_until = 0.0
    await retriever.retrieve("suv osti kemalari reestri")
    assert len(calls) == 2
    await rt.close()


def test_runtime_ingested_documents_survive_bundle_rebuild(tmp_path: Path) -> None:
    from lex_agent.ingestion.open_corpora import (
        read_index_stats,
        runtime_ingested_counts,
    )
    from lex_agent.models import LegalChunk

    rt = _runtime(tmp_path)
    base = rt.bm25_store.count()
    sample = next(iter(rt.bm25_store.iter_chunks()))
    ingested = LegalChunk(
        **{
            **sample.model_dump(),
            "chunk_id": "live-doc-1#1",
            "doc_id": "live-doc-1",
            "canonical_id": "live-doc-1",
            "extra": {"source": "lex_uz_live"},
        }
    )
    rt.bm25_store.upsert_chunks([ingested])
    stats = read_index_stats(rt.settings.bm25_db_path)
    assert runtime_ingested_counts(rt.bm25_store, stats) == (1, 1)

    rt.build_index(force=True)
    assert rt.bm25_store.count() == base + 1
    assert "live-doc-1#1" in rt.bm25_store.get_chunks_by_ids(["live-doc-1#1"])
    stats = read_index_stats(rt.settings.bm25_db_path)
    assert runtime_ingested_counts(rt.bm25_store, stats) == (1, 1)


def test_language_detection_handles_everyday_uzbek_latin() -> None:
    from lex_agent.language.transliterator import detect_language
    from lex_agent.models import Language

    for question in ["Yillik ta'til necha kun?", "Yillik tatil necha kun", "Aliment miqdori qancha?",
                     "Ishdan bo'shatishdi, nima qilishim kerak?", "BHM qancha?", "Ijara depozitini qaytarmayapti"]:
        assert detect_language(question) == Language.UZ_LATN, question
    for question in ["How many days of annual leave do I get?", "My employer didn't pay my salary"]:
        assert detect_language(question) == Language.EN, question
    assert detect_language("Сколько дней ежегодный отпуск?") == Language.RU
    assert detect_language("Алимент миқдори") == Language.UZ_CYRL


@pytest.mark.asyncio
async def test_follow_up_question_uses_previous_question_as_context(tmp_path: Path) -> None:
    rt = _runtime(tmp_path)
    retriever = rt.orchestrator.retriever
    searched: list[str] = []
    original = retriever.retrieve

    async def spy(query: str, **kw: Any) -> Any:
        searched.append(query)
        return await original(query, **kw)

    retriever.retrieve = spy  # type: ignore[method-assign]
    follow_up = "Bu qancha davom etadi?"
    await _collect(rt, follow_up)
    assert searched[0] == follow_up
    searched.clear()
    with_context = await _collect(rt, follow_up, context="Yillik mehnat ta'tili necha kun?")
    resp = with_context[-1]["response"]
    assert searched[0] == "Yillik mehnat ta'tili necha kun? Bu qancha davom etadi?"
    assert resp.sources and resp.sources[0].article == "217-modda"
    # the context is part of the cache key, so the follow-up is not served the context-free cached answer
    assert resp.mode != "cache"
    # a long, self-contained question ignores the context
    orch = rt.orchestrator
    long_q = AgentQueryRequest(query="Mehnat shartnomasini bekor qilishda ish beruvchi qancha oldin ogohlantirishi kerak",
                               context="Yillik ta'til necha kun?")
    assert orch._follow_up_context(long_q) is None
    await rt.close()
