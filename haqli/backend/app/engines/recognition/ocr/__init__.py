"""OCR engines and script routing package (§5.3)."""

from app.engines.recognition.ocr.base import OcrEngine
from app.engines.recognition.ocr.script import detect_language, detect_script, ocr_engines_status, run_ocr_cascade

__all__ = ["OcrEngine", "detect_language", "detect_script", "ocr_engines_status", "run_ocr_cascade"]
