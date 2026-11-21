"""Tests for image quality metrics, normalize offset-map round-trip, parsers, eval gates, and graceful fallback (§5-§12)."""

from __future__ import annotations

import io
from datetime import date
from decimal import Decimal

import pytest
from PIL import Image, ImageDraw

from app.engines.recognition.eval.runner import run_evaluation
from app.engines.recognition.normalize import normalize_ocr_text
from app.engines.recognition.parsers.contract import parse_contract
from app.engines.recognition.parsers.fine import parse_fine
from app.engines.recognition.parsers.receipt import parse_receipt_v1
from app.engines.recognition.pipeline import run_recognition_pipeline
from app.engines.recognition.quality import assess_image_quality
from app.engines.recognition.types import OcrLine


def _make_png(width: int, height: int, fill: int, *, draw_edges: bool = False) -> bytes:
    img = Image.new("RGB", (width, height), (fill, fill, fill))
    if draw_edges:
        draw = ImageDraw.Draw(img)
        for y in range(40, height - 40, 32):
            draw.rectangle([40, y, width - 40, y + 10], fill=(15, 15, 15))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_image_quality_metrics_synthetic_images() -> None:
    dark_small = _make_png(400, 300, 15)
    q_bad = assess_image_quality(dark_small)
    assert q_bad.ok is False
    assert "rec.warn.dark" in q_bad.warnings
    assert "rec.warn.small" in q_bad.warnings
    assert "rec.warn.blurry" in q_bad.warnings

    sharp_hi = _make_png(1200, 1000, 180, draw_edges=True)
    q_good = assess_image_quality(sharp_hi)
    assert q_good.resolution_min == 1000
    assert q_good.blur > 80.0
    assert "rec.warn.small" not in q_good.warnings


def test_normalize_offset_map_round_trip_and_repairs() -> None:
    lines = [
        OcrLine(text="O‘zbekiston shart-\nnoma 4 5OO 000 so'm", confidence=0.92, bbox=(10.0, 20.0, 300.0, 60.0)),
        OcrLine(text="Узбекистон конуни буйича", confidence=0.90, bbox=(10.0, 70.0, 300.0, 110.0)),
    ]
    raw = "\n".join(ln.text for ln in lines)
    norm = normalize_ocr_text(raw, lines=lines)
    assert "shartnoma" in norm.text
    assert "4 500 000" in norm.text
    assert "Ўзбекистон" in norm.text
    assert len(norm.offset_map) == len(norm.text)
    idx = norm.text.index("4 500 000")
    bbox = norm.span_to_bbox(idx, idx + 9)
    assert bbox == (10.0, 20.0, 300.0, 60.0)


def test_parsers_fine_receipt_mismatch_and_contract_clauses() -> None:
    # 1. Fine parser
    f_fields, f_route, _ = parse_fine(
        "Toshkent shahar IIBB YHXB\nJarima qarori № YHX-9910\nSana: 12.04.2026\n128-3-modda 01 А 555 АА\nJarima: 1 500 000 so'm\n50% chegirma 15 kun ichida",
        today=date(2026, 4, 15),
    )
    fmap = {f.key: f.value for f in f_fields}
    assert fmap["vehiclePlate"] == "01 A 555 AA"
    assert fmap["fineAmountUzs"] == Decimal("1500000.00")
    assert f_route.target == "himoya" and f_route.category == "traffic"

    # 2. Receipt parser with total mismatch (>1%)
    r_fields, r_route, r_warns = parse_receipt_v1(
        "Alpha Savdo MChJ\nSTIR: 301234567\nSana: 10.04.2026\nNon 10 000\nChoy 20 000\nJami: 500 000 so'm",
        today=date(2026, 4, 15),
    )
    assert "rec.warn.total_mismatch" in r_warns
    tot_f = next(f for f in r_fields if f.key == "totalUzs")
    assert tot_f.needs_confirm is True
    assert r_route.target == "himoya" and r_route.category == "consumer"

    # 3. Contract segmenter
    c_raw = "Ijara shartnomasi\nKarimov Azizbek va Alimov Javohir\n1. Kvartira muddati 12 oy.\n2. Depozit 300 USD.\n3. Kechikish penya 2% kuniga."
    norm = normalize_ocr_text(c_raw)
    c_fields, clauses, c_route, c_warns = parse_contract(norm, job_id="job-1")
    assert len(clauses) == 3
    assert c_route.target == "skaner"
    assert "rec.warn.foreign_currency" in c_warns


@pytest.mark.asyncio
async def test_pipeline_graceful_fallback_when_engines_off(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.config import get_settings

    monkeypatch.setenv("RECOGNITION_OCR", "off")
    monkeypatch.setenv("RECOGNITION_STT", "off")
    get_settings.cache_clear()
    try:
        res_img, stages_img, _ = await run_recognition_pipeline(
            job_id="fallback-img",
            kind="document",
            file_bytes=_make_png(1000, 1000, 200, draw_edges=True),
            mime="image/png",
        )
        assert res_img.route_hint is not None
        assert "rec.warn.no_text_found" in res_img.warnings
        assert any(s.stage == "done" for s in stages_img)

        res_voice, _, _ = await run_recognition_pipeline(
            job_id="fallback-voice",
            kind="voice",
            file_bytes=b"RIFF\x24\x00\x00\x00WAVEfmt ",
            mime="audio/wav",
        )
        assert "rec.warn.stt_unavailable" in res_voice.warnings
    finally:
        get_settings.cache_clear()


@pytest.mark.asyncio
async def test_eval_harness_passes_all_ci_gates() -> None:
    summary = await run_evaluation()
    assert summary.gates_passed is True, f"CI gates failed: {summary.gate_failures}"
