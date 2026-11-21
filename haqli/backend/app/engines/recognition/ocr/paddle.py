"""PaddleOCR CPU adapter with lazy initialization and graceful degradation (§3, §5.3)."""

from __future__ import annotations

import importlib.util
from typing import Any

import anyio

from app.engines.recognition.types import OcrLine, OcrResult, Script


class PaddleOcrEngine:
    name = "paddle"

    def __init__(self) -> None:
        self._instances: dict[str, Any] = {}

    def is_available(self) -> bool:
        return importlib.util.find_spec("paddleocr") is not None

    def _get_reader(self, lang: str) -> Any:
        if lang not in self._instances:
            from paddleocr import PaddleOCR  # type: ignore

            self._instances[lang] = PaddleOCR(use_angle_cls=True, lang=lang, use_gpu=False, show_log=False)
        return self._instances[lang]

    def _run_sync(self, image: Any, hint: Script) -> OcrResult:
        import numpy as np  # type: ignore

        lang = "cyrillic" if hint == "cyrl" else "latin"
        reader = self._get_reader(lang)
        arr = image if isinstance(image, np.ndarray) else np.array(image)
        raw = reader.ocr(arr, cls=True) or []
        lines: list[OcrLine] = []
        confs: list[float] = []
        for page in raw:
            if not page:
                continue
            for item in page:
                if not item or len(item) < 2:
                    continue
                pts, (txt, conf) = item[0], item[1]
                xs = [float(p[0]) for p in pts]
                ys = [float(p[1]) for p in pts]
                bbox = (min(xs), min(ys), max(xs), max(ys))
                c = max(0.0, min(1.0, float(conf)))
                lines.append(OcrLine(text=str(txt).strip(), confidence=round(c, 3), bbox=bbox))
                confs.append(c)
        mean_c = round(sum(confs) / len(confs), 3) if confs else 0.0
        return OcrResult(lines=lines, mean_conf=mean_c, engine=self.name)

    async def recognize(self, image: Any, hint: Script = "unknown") -> OcrResult:
        if not self.is_available():
            return OcrResult(lines=[], mean_conf=0.0, engine=self.name)
        try:
            return await anyio.to_thread.run_sync(self._run_sync, image, hint)
        except Exception:
            return OcrResult(lines=[], mean_conf=0.0, engine=self.name)
