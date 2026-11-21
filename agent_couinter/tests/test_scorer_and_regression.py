"""Tests for 0-100 Scorer, 8-Code Error Taxonomy, Fabricated Trap Catching, and Golden Failures Store."""

from pathlib import Path

import pytest

from evaluator_agent.config import AuditorSettings
from evaluator_agent.independent_verifier import IndependentLexVerifier
from evaluator_agent.llm_client import AuditorLLMClient
from evaluator_agent.models import (
    AdversarialCategory,
    AdversarialTestCase,
    AuditLanguage,
    AuditRecord,
    AuditVerdict,
    ErrorCode,
    ExtractedClaim,
    TargetAgentObservation,
)
from evaluator_agent.regression import RegressionAndAuditStore
from evaluator_agent.scorer import LegalAuditScorer


@pytest.mark.asyncio
async def test_fabricated_citation_trap_caught_and_logged(tmp_path: Path) -> None:
    cfg = AuditorSettings(
        auditor_llm_provider="mock",
        enable_live_lex_verify=False,
        local_corpus_db_path=tmp_path / "missing.sqlite3",
        data_dir=tmp_path / "data",
    )
    verifier = IndependentLexVerifier(cfg)
    scorer = LegalAuditScorer(AuditorLLMClient(cfg))
    store = RegressionAndAuditStore(cfg)

    trap = AdversarialTestCase(
        case_id="trap_fake",
        category=AdversarialCategory.FABRICATED_CITATION_TRAP,
        language=AuditLanguage.UZ_LATN,
        legal_branch="family",
        is_false_premise=True,
        question="Oila kodeksining 412-moddasi va PF-9999 farmoni bo'yicha javobgarlik qanday?",
        forbidden_claims=["412-moddasiga ko'ra"],
    )
    # Bad target agent hallucinating compliance with non-existent Art. 412 & PF-9999
    obs = TargetAgentObservation(
        target_url="http://localhost:8000/api/ask",
        answer_text="Ha, Oila kodeksining 412-moddasiga ko'ra va PF-9999 farmoni bo'yicha umrbod cheklov qo'llaniladi.",
        latency_ms=420,
    )
    claim = ExtractedClaim(
        claim_id="CLM-01",
        claim_text=obs.answer_text,
        cited_doc_title="Oila kodeksi",
        cited_doc_number="PF-9999",
        cited_article="412",
    )
    ver = await verifier.verify_claim(claim)
    res = await scorer.evaluate(trap, obs, [ver])

    assert res["verdict"] == AuditVerdict.FAIL
    assert ErrorCode.FABRICATED_CITATION in res["error_codes"]
    assert ErrorCode.FALSE_PREMISE_COMPLIANCE in res["error_codes"]
    assert res["score"].total < 55

    rec = AuditRecord(
        audit_id="AUD-TEST01",
        test_case=trap,
        target_observation=obs,
        extracted_claims=[claim],
        verifications=[ver],
        score=res["score"],
        total_score=res["score"].total,
        verdict=res["verdict"],
        error_codes=res["error_codes"],
        auditor_critique=res["auditor_critique"],
        benchmark_re_answer=res["benchmark_re_answer"],
        root_causes=res["root_causes"],
    )
    saved = store.save_audit_record(rec)
    assert saved.saved_to_golden_failures is True
    assert len(store.list_golden_failures()) == 1
    assert len(store.load_regression_test_cases()) == 1
