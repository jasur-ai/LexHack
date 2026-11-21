"""Tesseract OCR adapter supporting uzb, uzb_cyrl, and rus with line-level bboxes & confidences (§5.3)."""

from __future__ import annotations

import importlib.util
import shutil
from collections import defaultdict
from typing import Any

import anyio
from PIL import Image

from app.engines.recognition.types import OcrLine, OcrResult, Script


class TesseractOcrEngine:
    name = "tesseract"

    def is_available(self) -> bool:
        return importlib.util.find_spec("pytesseract") is not None and shutil.which("tesseract") is not None

    def _select_lang(self, hint: Script) -> str:
        if hint == "cyrl":
            return "uzb_cyrl+rus"
        if hint == "latn":
            return "uzb+eng"
        return "uzb+rus+eng"

    def _run_sync(self, image: Any, hint: Script) -> OcrResult:
        import pytesseract  # type: ignore

        pil_img = image if isinstance(image, Image.Image) else Image.fromarray(image[:, :, ::-1])
        lang = self._select_lang(hint)
        try:
            data = pytesseract.image_to_data(pil_img, lang=lang, output_type=pytesseract.Output.DICT)
        except Exception:
            # Fallback to default eng/rus if uzb traineddata is missing on host
            data = pytesseract.image_to_data(pil_img, lang="rus+eng", output_type=pytesseract.Output.DICT)

        grouped: dict[tuple[int, int, int], list[tuple[str, float, tuple[float, float, float, float]]]] = defaultdict(list)
        n = len(data.get("text", []))
        for i in range(n):
            txt = str(data["text"][i] or "").strip()
            if not txt:
                continue
            raw_conf = float(data["conf"][i])
            if raw_conf < 0:
                continue
            key = (int(data["block_num"][i]), int(data["par_num"][i]), int(data["line_num"][i]))
            x, y, w, h = float(data["left"][i]), float(data["top"][i]), float(data["width"][i]), float(data["height"][i])
            grouped[key].append((txt, raw_conf / 100.0, (x, y, x + w, y + h)))

        lines: list[OcrLine] = []
        confs: list[float] = []
        for words in grouped.values():
            line_txt = " ".join(w[0] for w in words)
            avg_c = sum(w[1] for w in words) / len(words)
            bbox = (
                min(w[2][0] for w in words),
                min(w[2][1] for w in words),
                max(w[2][2] for w in words),
                max(w[2][3] for w in words),
            )
            lines.append(OcrLine(text=line_txt, confidence=round(avg_c, 3), bbox=bbox))
            confs.append(avg_c)

        mean_c = round(sum(confs) / len(confs), 3) if confs else 0.0
        return OcrResult(lines=lines, mean_conf=mean_c, engine=self.name)

    async def recognize(self, image: Any, hint: Script = "unknown") -> OcrResult:
        if not self.is_available():
            return OcrResult(lines=[], mean_conf=0.0, engine=self.name)
        try:
            return await anyio.to_thread.run_sync(self._run_sync, image, hint)
        except Exception:
            return OcrResult(lines=[], mean_conf=0.0, engine=self.name)
