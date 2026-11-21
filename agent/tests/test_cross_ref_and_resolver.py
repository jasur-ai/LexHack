"""Tests for cross-reference extraction, norm conflict resolution, and end-to-end offline multi-hop retrieval."""

from datetime import date
from pathlib import Path

import pytest

from lex_agent.config import Settings
from lex_agent.ingestion.lex_fetcher import FetchedDocument
from lex_agent.models import (
    AgentQueryRequest,
    DocumentMetadata,
    DocumentType,
    LEGAL_FORCE_HIERARCHY,
    Language,
    LegalBranch,
    LegalChunk,
    NormStatus,
    RetrievedChunk,
)
from lex_agent.reasoning.cross_ref import extract_cross_references
from lex_agent.reasoning.norm_resolver import NormConflictResolver
from lex_agent.runtime import AgentRuntime


def test_cross_reference_extraction_multilingual() -> None:
    text = (
        "Javobgarlik Jinoyat kodeksining 168-moddasiga hamda O'RQ-682-son Qonunga muvofiq belgilanadi. "
        "Также применяется статья 155 Трудового кодекса и https://lex.uz/ru/docs/6257288."
    )
    refs = extract_cross_references(text, current_doc_id="111")
    assert any(r.target_doc_hint == "Jinoyat kodeksi" and r.target_article == "168" for r in refs)
    assert any(r.target_doc_number == "O'RQ-682" for r in refs)
    assert any(r.target_doc_id == "6257288" for r in refs)


def test_norm_conflict_resolver_lex_superior_and_repealed() -> None:
    code_chunk = RetrievedChunk(
        chunk=LegalChunk(
            chunk_id="c1",
            doc_id="6257288",
            canonical_id="6257288",
            language=Language.UZ_LATN,
            doc_type=DocumentType.CODE,
            doc_title="O'zbekiston Respublikasining Mehnat kodeksi",
            status=NormStatus.IN_FORCE,
            legal_force_rank=LEGAL_FORCE_HIERARCHY[DocumentType.CODE],
            branches=[LegalBranch.LABOR],
            effective_date=date(2023, 4, 30),
            text="Mehnat shartnomasi asosiy qoidalari.",
            url="https://lex.uz/uz/docs/6257288",
        ),
        final_score=0.9,
    )
    cabinet_chunk = RetrievedChunk(
        chunk=LegalChunk(
            chunk_id="c2",
            doc_id="999999",
            canonical_id="999999",
            language=Language.UZ_LATN,
            doc_type=DocumentType.CABINET_RESOLUTION,
            doc_title="Vazirlar Mahkamasining Qarori VMQ-50",
            status=NormStatus.IN_FORCE,
            legal_force_rank=LEGAL_FORCE_HIERARCHY[DocumentType.CABINET_RESOLUTION],
            branches=[LegalBranch.LABOR],
            effective_date=date(2024, 1, 1),
            text="Mehnat shartnomasi bo'yicha qo'shimcha tartib.",
            url="https://lex.uz/uz/docs/999999",
        ),
        final_score=0.85,
    )
    repealed_chunk = RetrievedChunk(
        chunk=LegalChunk(
            chunk_id="c3",
            doc_id="142859",
            canonical_id="142859",
            language=Language.UZ_LATN,
            doc_type=DocumentType.CODE,
            doc_title="Eski Mehnat kodeksi (1995)",
            status=NormStatus.REPEALED,
            legal_force_rank=LEGAL_FORCE_HIERARCHY[DocumentType.CODE],
            branches=[LegalBranch.LABOR],
            effective_date=date(1996, 4, 1),
            expiry_date=date(2023, 4, 30),
            text="Eski qoidalar.",
            url="https://lex.uz/uz/docs/142859",
        ),
        final_score=0.95,
    )

    resolver = NormConflictResolver()
    ordered, resolutions, warnings = resolver.resolve([repealed_chunk, cabinet_chunk, code_chunk])

    # Repealed norm must be demoted below in-force norms and explicitly warned
    assert ordered[0].chunk.doc_id == "6257288"
    assert ordered[-1].chunk.status == NormStatus.REPEALED
    assert any(r.principle_applied == "lex_superior" and r.higher_norm_doc_id == "6257288" for r in resolutions)
    assert any("REPEALED NORM" in w for w in warnings)


@pytest.mark.asyncio
async def test_offline_multihop_end_to_end(tmp_path: Path) -> None:
    cfg = Settings(
        llm_provider="mock",
        llm_api_key="",
        embedding_provider="hash",
        embedding_dim=256,
        qdrant_mode="memory",
        reranker_enabled=False,
        lex_uz_enable_live_fallback=False,
        data_dir=tmp_path / "data",
    )
    rt = AgentRuntime.build(cfg)
    try:
        doc1 = FetchedDocument(
            metadata=DocumentMetadata(
                doc_id="6257288",
                canonical_id="6257288",
                title="O'zbekiston Respublikasining Mehnat kodeksi",
                doc_type=DocumentType.CODE,
                doc_number="O'RQ-798",
                language=Language.UZ_LATN,
                adoption_date=date(2022, 10, 28),
                effective_date=date(2023, 4, 30),
                status=NormStatus.IN_FORCE,
                legal_force_rank=LEGAL_FORCE_HIERARCHY[DocumentType.CODE],
                branches=[LegalBranch.LABOR],
                url="https://lex.uz/uz/docs/6257288",
            ),
            raw_text=(
                "161-modda. Mehnat shartnomasini ish beruvchining tashabbusi bilan bekor qilish\n"
                "Ish beruvchi xodimni ogohlantirish muddatlariga rioya etishi shart. "
                "Nizolar Fuqarolik kodeksining 354-moddasi hamda O'RQ-682 talablariga muvofiq ko'rib chiqiladi."
            ),
        )
        doc2 = FetchedDocument(
            metadata=DocumentMetadata(
                doc_id="5378966",
                canonical_id="5378966",
                title="Normativ-huquqiy hujjatlar to'g'risida",
                doc_type=DocumentType.LAW,
                doc_number="O'RQ-682",
                language=Language.UZ_LATN,
                adoption_date=date(2021, 4, 20),
                effective_date=date(2021, 4, 21),
                status=NormStatus.IN_FORCE,
                legal_force_rank=LEGAL_FORCE_HIERARCHY[DocumentType.LAW],
                branches=[LegalBranch.GENERAL],
                url="https://lex.uz/uz/docs/5378966",
            ),
            raw_text="18-modda. Normativ-huquqiy hujjatlarning yuridik kuchi iyerarxiyasi.",
        )

        await rt.ingestion.index_fetched_document(doc1)
        await rt.ingestion.index_fetched_document(doc2)

        resp = await rt.orchestrator.answer(
            AgentQueryRequest(
                query="Меҳнат кодексининг 161-моддаси бўйича ишдан бўшатиш тартиби",
                enable_live_lex=False,
            )
        )
        assert resp.response_language == Language.UZ_CYRL
        assert resp.evidence_count >= 1
        assert any(c.doc_id == "6257288" for c in resp.citations)
        # Multi-hop should follow cross-reference to O'RQ-682
        assert any(c.doc_id == "5378966" for c in resp.citations)
    finally:
        await rt.close()
