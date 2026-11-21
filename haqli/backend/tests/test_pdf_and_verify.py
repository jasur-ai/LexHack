"""PDF Cyrillic glyph coverage, pypdf text extraction, and tamper-detection seal tests (§13, §14)."""

from __future__ import annotations

import io
from pathlib import Path

from pypdf import PdfReader

from app.engines.pdf.generator import check_font_glyph_coverage, render_haqli_pdf
from app.security.crypto import get_crypto


def test_pdf_font_covers_uzbek_cyrillic_and_latin() -> None:
    cov = check_font_glyph_coverage()
    assert cov["ok"] is True, f"Font missing required glyphs: {cov}"
    assert cov["missing_glyphs"] == []


def test_pdf_renders_cyrillic_and_latin_text_cleanly(tmp_path: Path) -> None:
    crypto = get_crypto()
    doc_hash = crypto.sha256_canonical({"title": "test", "amount": "5000000"})
    seal = crypto.sign_seal(doc_hash)
    out = tmp_path / "sample_cyrillic.pdf"

    pdf_bytes = render_haqli_pdf(
        doc_id="01950000-0000-7000-8000-000000000001",
        title="ҚАРЗ ТИЛХАТИ / ТАЛАБНОМА",
        subtitle="Ўзбекистон Республикаси Фуқаролик кодекси 108-модда · Ғоя ва Ҳуқуқ",
        body_paragraphs=[
            "Мазкур ҳужжат Ўзбекистон қонунчилигига мувофиқ расмийлаштирилди.",
            "Настоящий документ подтверждает обязательство в размере 5 000 000 сум.",
        ],
        table_rows=[
            ["Кўрсаткич", "Қиймат"],
            ["Сумма", "5 000 000 сўм"],
        ],
        doc_hash=doc_hash,
        seal_signature=seal,
        needs_review=True,
        locale="uz_cyr",
        output_path=out,
    )

    assert len(pdf_bytes) > 1500
    assert out.exists()

    reader = PdfReader(io.BytesIO(pdf_bytes))
    extracted = "\n".join(page.extract_text() or "" for page in reader.pages)
    assert "Ўзбекистон" in extracted
    assert "5 000 000" in extracted
    assert doc_hash[:16] in extracted


def test_ed25519_seal_detects_tampering() -> None:
    crypto = get_crypto()
    doc_hash = crypto.sha256_canonical({"doc": "tilxat-1", "amount": "10000000"})
    seal = crypto.sign_seal(doc_hash)
    assert crypto.verify_seal(doc_hash, seal) is True

    tampered_hash = crypto.sha256_canonical({"doc": "tilxat-1", "amount": "90000000"})
    assert crypto.verify_seal(tampered_hash, seal) is False
