"""Tests for the zero-hallucination Citation Verification Guard."""

from lex_agent.models import DocumentType, Language, LegalChunk, NormStatus, RetrievedChunk
from lex_agent.reasoning.citation_guard import CitationVerificationGuard


def _sample_evidence() -> list[RetrievedChunk]:
    return [
        RetrievedChunk(
            chunk=LegalChunk(
                chunk_id="ev1",
                doc_id="6257288",
                canonical_id="6257288",
                language=Language.UZ_LATN,
                doc_type=DocumentType.CODE,
                doc_number="O'RQ-798",
                doc_title="O'zbekiston Respublikasining Mehnat kodeksi",
                status=NormStatus.IN_FORCE,
                legal_force_rank=90,
                article="161-modda",
                text="161-modda. Mehnat shartnomasini ish beruvchining tashabbusi bilan bekor qilish.",
                url="https://lex.uz/uz/docs/6257288",
            ),
            final_score=0.95,
        )
    ]


def test_citation_guard_passes_grounded_answer() -> None:
    guard = CitationVerificationGuard()
    answer = (
        "Mehnat kodeksining (O'RQ-798) 161-moddasiga muvofiq "
        "(https://lex.uz/uz/docs/6257288), ish beruvchi qonuniy asoslarga rioya qilishi shart."
    )
    report = guard.verify(answer, _sample_evidence())
    assert report.passed is True
    assert report.unverified_references == []
    assert report.confidence_score >= 0.9


def test_citation_guard_catches_fabricated_article_and_url() -> None:
    guard = CitationVerificationGuard()
    hallucinated = (
        "Mehnat kodeksining 999-moddasi va PF-9999 farmoni (https://lex.uz/uz/docs/1234567) bo'yicha "
        "xodimga 10 baravar kompensatsiya to'lanadi."
    )
    report = guard.verify(hallucinated, _sample_evidence())
    assert report.passed is False
    assert len(report.unverified_references) >= 3
    assert any("999" in u for u in report.unverified_references)
    assert any("1234567" in u for u in report.unverified_references)
    assert any("PF-9999" in u for u in report.unverified_references)
