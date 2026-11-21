"""faster-whisper local CPU STT engine with lazy load, VAD filter, and low-confidence language re-run (§7)."""

from __future__ import annotations

import importlib.util
import math
from pathlib import Path
from typing import Any

import anyio

from app.config import get_settings
from app.engines.recognition.types import Transcript, TranscriptSegment


class FasterWhisperSttEngine:
    name = "faster_whisper"

    def __init__(self) -> None:
        self._model: Any = None

    def is_available(self) -> bool:
        return importlib.util.find_spec("faster_whisper") is not None

    def _load_model(self) -> Any:
        if self._model is None:
            cfg = get_settings()
            from faster_whisper import WhisperModel  # type: ignore

            self._model = WhisperModel(cfg.whisper_model, device="cpu", compute_type=cfg.whisper_compute_type)
        return self._model

    def _run_sync(self, audio_path: Path, lang_hint: str | None) -> Transcript:
        model = self._load_model()
        lang_arg = lang_hint if lang_hint in ("uz", "ru") else None
        segs_iter, info = model.transcribe(str(audio_path), language=lang_arg, vad_filter=True)
        segs = list(segs_iter)

        detected_lang = getattr(info, "language", None)
        lang_prob = float(getattr(info, "language_probability", 1.0))

        # Re-run with dominant language if auto-detection probability < 0.6 (§7)
        if lang_arg is None and lang_prob < 0.6 and detected_lang in ("uz", "ru"):
            segs_iter2, info2 = model.transcribe(str(audio_path), language=detected_lang, vad_filter=True)
            segs = list(segs_iter2)
            lang_prob = float(getattr(info2, "language_probability", lang_prob))

        out_segs: list[TranscriptSegment] = []
        texts: list[str] = []
        logprobs: list[float] = []
        for s in segs:
            txt = str(getattr(s, "text", "")).strip()
            if not txt:
                continue
            lp = float(getattr(s, "avg_logprob", -0.35))
            out_segs.append(
                TranscriptSegment(
                    start=round(float(getattr(s, "start", 0.0)), 2),
                    end=round(float(getattr(s, "end", 0.0)), 2),
                    text=txt,
                    avg_logprob=round(lp, 3),
                )
            )
            texts.append(txt)
            logprobs.append(lp)

        mean_lp = sum(logprobs) / len(logprobs) if logprobs else -2.0
        conf = round(max(0.0, min(0.99, math.exp(mean_lp))), 2)
        return Transcript(
            text=" ".join(texts),
            language=detected_lang if detected_lang in ("uz", "ru") else None,
            segments=out_segs,
            confidence=conf,
            engine=self.name,
        )

    async def transcribe(self, audio_path: Path, lang_hint: str | None = None) -> Transcript:
        if not self.is_available() or not audio_path.exists():
            return Transcript(engine=self.name)
        try:
            return await anyio.to_thread.run_sync(self._run_sync, audio_path, lang_hint)
        except Exception:
            return Transcript(engine=self.name)
