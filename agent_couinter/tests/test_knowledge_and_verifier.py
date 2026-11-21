"""Tests for the 26+ Uzbekistan Statute Registry, Trainable Knowledge Base, and 4-Tier Independent Verifier."""

from pathlib import Path

import pytest

from evaluator_agent.config import AuditorSettings
from evaluator_agent.independent_verifier import IndependentLexVerifier
from evaluator_agent.knowledge_base import UZBEKISTAN_STATUTE_REGISTRY, AuditorKnowledgeStore
from evaluator_agent.models import ClaimVerificationStatus, ExtractedClaim


def test_knowledge_store_seeds_all_codes_and_supports_training(tmp_path: Path) -> None:
    store = AuditorKnowledgeStore(tmp_path / "auditor_kb.sqlite3")
    stats = store.stats()
    assert stats["registered_statutes_count"] >= 26
    assert stats["total_verified_articles"] >= 25
    assert "Mehnat kodeksi" in UZBEKISTAN_STATUTE_REGISTRY
    assert "Manfaatlar to'qnashuvi to'g'risida" in UZBEKISTAN_STATUTE_REGISTRY

    # Train a new multi-article chapter and verify retrieval
    trained = store.train_bulk_document_text(
        code_name="Test Kodeksi",
        doc_id="999111",
        raw_text="10-modda. Birinchi qoida matni bu yerda.\n11-modda. Ikkinchi qoida matni ham shu yerda.",
        branch="civil",
    )
    assert trained == 2
    hit = store.lookup_article(doc_id="999111", article="11")
    assert hit is not None
    assert "Ikkinchi qoida" in hit["summary_uz"]


@pytest.mark.asyncio
async def test_four_tier_verifier_catches_contradictions_repeals_and_verifies_golden(tmp_path: Path) -> None:
    cfg = AuditorSettings(
        auditor_llm_provider="mock",
        enable_live_lex_verify=False,
        local_corpus_db_path=tmp_path / "missing.sqlite3",
        data_dir=tmp_path / "data",
    )
    verifier = IndependentLexVerifier(cfg)

    # 1. Verified golden article from Tier 2 Knowledge Base (Mehnat kodeksi Art. 217 -> 21 kalendar kun)
    c_ok = ExtractedClaim(
        claim_id="CLM-1",
        claim_text="Mehnat kodeksining 217-moddasiga ko'ra eng kam mehnat ta'tili 21 kalendar kun.",
        cited_doc_title="Mehnat kodeksi",
        cited_article="217",
    )
    res_ok = await verifier.verify_claim(c_ok)
    assert res_ok.status == ClaimVerificationStatus.VERIFIED
    assert "21 kalendar" in res_ok.independent_excerpt

    # 2. Statutory contradiction caught by Tier 2 (claiming BHM instead of MHTEKM on Oila kodeksi Art. 99)
    c_contradict = ExtractedClaim(
        claim_id="CLM-2",
        claim_text="Oila kodeksining 99-moddasiga ko'ra aliment BHMning 26,5 foizi miqdorida undiriladi.",
        cited_doc_title="Oila kodeksi",
        cited_article="99",
    )
    res_contra = await verifier.verify_claim(c_contradict)
    assert res_contra.status == ClaimVerificationStatus.MISQUOTED_OR_DRIFT

    # 3. Repealed 1995 Labor Code caught by Tier 1/2
    c_repealed = ExtractedClaim(
        claim_id="CLM-3",
        claim_text="1995-yilgi Mehnat kodeksining 134-moddasiga ko'ra ta'til 15 ish kuni.",
        cited_doc_title="Eski Mehnat kodeksi (1995)",
        cited_article="134",
    )
    res_rep = await verifier.verify_claim(c_repealed)
    assert res_rep.status == ClaimVerificationStatus.REPEALED_OR_OUTDATED
