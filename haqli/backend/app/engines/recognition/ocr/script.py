"""Script & language detection plus OCR engine cascade routing (§5.3)."""

from __future__ import annotations

import re
from typing import Any

from app.config import get_settings
from app.engines.recognition.ocr.paddle import PaddleOcrEngine
from app.engines.recognition.ocr.tesseract import TesseractOcrEngine
from app.engines.recognition.ocr.vision_llm import VisionLlmOcrEngine
from app.engines.recognition.types import LangDetected, OcrResult, Script

_paddle_engine = PaddleOcrEngine()
_tesseract_engine = TesseractOcrEngine()
_vision_engine = VisionLlmOcrEngine()

_UZ_SPECIFIC_CYR = set("ўқғҳЎҚҒҲ")
_RU_MARKERS = ("договор", "расписка", "сум", "штраф", "постановление", "итого", "аренды", "работник", "оклад")
_UZ_MARKERS = ("shartnoma", "tilxat", "so'm", "soʻm", "jarima", "qaror", "jami", "xodim", "шартнома", "сўм", "жарима")


def detect_script(text: str) -> Script:
    """Count Latin vs Cyrillic letters; ratio > 0.8 -> latn/cyrl, else mixed (§5.3)."""
    lat = sum(1 for ch in text if ("A" <= ch <= "Z") or ("a" <= ch <= "z"))
    cyr = sum(1 for ch in text if "\u0400" <= ch <= "\u04ff")
    total = lat + cyr
    if total == 0:
        return "unknown"
    if lat / total > 0.8:
        return "latn"
    if cyr / total > 0.8:
        return "cyrl"
    return "mixed"


def detect_language(text: str) -> LangDetected | None:
    if not text.strip():
        return None
    low = text.lower()
    script = detect_script(text)
    has_uz_cyr = any(ch in _UZ_SPECIFIC_CYR for ch in text)
    ru_hits = sum(1 for m in _RU_MARKERS if m in low)
    uz_hits = sum(1 for m in _UZ_MARKERS if m in low) + (2 if has_uz_cyr else 0)

    if script == "latn":
        return "uz"
    if ru_hits > 0 and uz_hits > 0:
        return "mixed"
    if script == "mixed":
        return "mixed"
    if has_uz_cyr or uz_hits > ru_hits:
        return "uz"
    if script == "cyrl":
        return "ru"
    return "uz"


def ocr_engines_status() -> dict[str, Any]:
    cfg = get_settings()
    return {
        "mode": cfg.recognition_ocr,
        "pypdf": True,
        "paddle": _paddle_engine.is_available() if cfg.recognition_ocr in ("auto", "paddle") else False,
        "tesseract": _tesseract_engine.is_available() if cfg.recognition_ocr in ("auto", "tesseract") else False,
        "vision_llm": _vision_engine.is_available() if cfg.recognition_ocr == "vision" else False,
    }


def _candidate_score(res: OcrResult) -> tuple[float, int]:
    return (res.mean_conf, len(res.full_text.strip()))


async def run_ocr_cascade(
    image_variants: list[Any],
    *,
    is_mrz: bool = False,
) -> OcrResult:
    """Run Paddle -> Tesseract -> optional Vision LLM across preprocessed variants; return best candidate (§5.3)."""
    cfg = get_settings()
    if cfg.recognition_ocr == "off" or not image_variants:
        return OcrResult(lines=[], mean_conf=0.0, engine="off")

    best = OcrResult(lines=[], mean_conf=0.0, engine="none")
    hint: Script = "latn" if is_mrz else "unknown"

    order: list[str] = []
    if cfg.recognition_ocr == "paddle":
        order = ["paddle"]
    elif cfg.recognition_ocr == "tesseract":
        order = ["tesseract"]
    elif cfg.recognition_ocr == "vision":
        order = ["vision"]
    else:
        order = ["paddle", "tesseract"]

    for variant in image_variants:
        for eng_name in order:
            if eng_name == "paddle" and _paddle_engine.is_available():
                res = await _paddle_engine.recognize(variant, hint=hint)
                if _candidate_score(res) > _candidate_score(best):
                    best = res
                    if best.full_text:
                        hint = detect_script(best.full_text)
            elif eng_name == "tesseract" and _tesseract_engine.is_available():
                res = await _tesseract_engine.recognize(variant, hint=hint)
                if _candidate_score(res) > _candidate_score(best):
                    best = res
                    if best.full_text:
                        hint = detect_script(best.full_text)
            elif eng_name == "vision" and not is_mrz and _vision_engine.is_available():
                res = await _vision_engine.recognize(variant, hint=hint, allow_external=True)
                if _candidate_score(res) > _candidate_score(best):
                    best = res

    # Vision fallback ONLY if enabled, mean_conf < 0.6, and NEVER for MRZ (§5.3, §11)
    if (
        not is_mrz
        and cfg.recognition_ocr == "vision"
        and best.mean_conf < 0.6
        and _vision_engine.is_available()
        and image_variants
    ):
        res = await _vision_engine.recognize(image_variants[0], hint=hint, allow_external=True)
        if _candidate_score(res) > _candidate_score(best):
            best = res

    return best
