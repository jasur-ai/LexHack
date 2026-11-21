"""Tests for Zero-Trust Atomic Claim & Citation Parser."""

from evaluator_agent.claim_parser import parse_claims_and_citations


def test_parse_multilingual_claims_and_urls() -> None:
    answer = (
        "Oila kodeksining 99-moddasiga (https://lex.uz/uz/docs/104720) ko'ra 1 bola uchun 1/4 qismi undiriladi. "
        "Также действует ст. 258 Налогового кодекса и Закон O'RQ-682."
    )
    claims = parse_claims_and_citations(answer)
    assert any(c.cited_doc_id == "104720" and c.cited_article == "99" for c in claims)
    assert any(c.cited_article == "258" for c in claims)
    assert any(c.cited_doc_number == "O'RQ-682" for c in claims)
