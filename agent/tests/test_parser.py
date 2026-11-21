"""Tests for structure-aware hierarchical legal parsing and Uzbekistan norm hierarchy classification."""

from datetime import date

from lex_agent.ingestion.parser import LegalDocumentParser, classify_document_type
from lex_agent.models import DocumentMetadata, DocumentType, LEGAL_FORCE_HIERARCHY, Language, NormStatus


def test_document_type_classification_and_hierarchy() -> None:
    assert classify_document_type("O'zbekiston Respublikasining Konstitutsiyasi") == DocumentType.CONSTITUTION
    assert classify_document_type("O'zbekiston Respublikasining Mehnat kodeksi") == DocumentType.CODE
    assert classify_document_type("O'zbekiston Respublikasining Qonuni O'RQ-682") == DocumentType.LAW
    assert classify_document_type("O'zbekiston Respublikasi Prezidentining Farmoni PF-158") == DocumentType.PRESIDENTIAL_DECREE
    assert classify_document_type("Vazirlar Mahkamasining Qarori VMQ-123") == DocumentType.CABINET_RESOLUTION
    assert classify_document_type("Oliy sud Plenumi qarori") == DocumentType.SUPREME_COURT_PLENUM

    assert LEGAL_FORCE_HIERARCHY[DocumentType.CONSTITUTION] > LEGAL_FORCE_HIERARCHY[DocumentType.CODE]
    assert LEGAL_FORCE_HIERARCHY[DocumentType.CODE] > LEGAL_FORCE_HIERARCHY[DocumentType.LAW]
    assert LEGAL_FORCE_HIERARCHY[DocumentType.LAW] > LEGAL_FORCE_HIERARCHY[DocumentType.PRESIDENTIAL_DECREE]
    assert LEGAL_FORCE_HIERARCHY[DocumentType.PRESIDENTIAL_DECREE] > LEGAL_FORCE_HIERARCHY[DocumentType.CABINET_RESOLUTION]


def test_hierarchical_section_chapter_article_chunking() -> None:
    sample_law = """
    I BO'LIM. UMUMIY QOIDALAR
    1-bob. Asosiy prinsiplar
    1-modda. Qonunning maqsadi
    Ushbu Qonun normativ-huquqiy hujjatlarni qabul qilish tartibini belgilaydi va O'RQ-682 talablariga muvofiq amal qiladi.

    2-modda. Fuqarolik kodeksi bilan o'zaro bog'liqlik
    Ushbu moddada nazarda tutilgan munosabatlar Fuqarolik kodeksining 354-moddasi asosida tartibga solinadi.
    """
    meta = DocumentMetadata(
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
        url="https://lex.uz/uz/docs/5378966",
    )
    parser = LegalDocumentParser()
    chunks = parser.parse_to_chunks(meta, sample_law)

    assert len(chunks) == 2
    assert chunks[0].section == "I BO'LIM. UMUMIY QOIDALAR"
    assert chunks[0].chapter == "1-bob. Asosiy prinsiplar"
    assert chunks[0].article == "1-modda"
    assert chunks[1].article == "2-modda"
    assert any(r.target_doc_hint == "Fuqarolik kodeksi" and r.target_article == "354" for r in chunks[1].cross_references)
