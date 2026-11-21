"""SttEngine protocol and safe subprocess ffmpeg transcoder (no shell, 15s timeout) (§7, §11)."""

from __future__ import annotations

import asyncio
import importlib.util
import shutil
from pathlib import Path
from typing import Any, Protocol

from app.config import get_settings
from app.engines.recognition.types import Transcript


class SttEngine(Protocol):
    name: str

    def is_available(self) -> bool: ...

    async def transcribe(self, audio_path: Path, lang_hint: str | None = None) -> Transcript: ...


async def transcode_to_wav_16k(src_path: Path, dst_path: Path, timeout_sec: float = 15.0) -> bool:
    """Transcode any uploaded audio to 16 kHz mono WAV via ffmpeg subprocess with NO shell interpolation (§7, §11)."""
    ffmpeg_bin = shutil.which("ffmpeg")
    if not ffmpeg_bin:
        return False
    try:
        proc = await asyncio.create_subprocess_exec(
            ffmpeg_bin,
            "-y",
            "-i",
            str(src_path),
            "-ac",
            "1",
            "-ar",
            "16000",
            "-f",
            "wav",
            str(dst_path),
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await asyncio.wait_for(proc.wait(), timeout=timeout_sec)
        return proc.returncode == 0 and dst_path.exists()
    except Exception:
        return False


def stt_engines_status() -> dict[str, Any]:
    cfg = get_settings()
    return {
        "mode": cfg.recognition_stt,
        "ffmpeg": shutil.which("ffmpeg") is not None,
        "faster_whisper": importlib.util.find_spec("faster_whisper") is not None if cfg.recognition_stt in ("auto", "local") else False,
        "cloud_stt": bool(cfg.cloud_stt_url) if cfg.recognition_stt in ("auto", "cloud") else False,
    }
