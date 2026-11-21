"""Optional Cloud STT adapter (explicitly opt-in via env CLOUD_STT_URL & RECOGNITION_STT=cloud|auto) (§7, §11)."""

from __future__ import annotations

from pathlib import Path

import httpx

from app.config import get_settings
from app.engines.recognition.types import Transcript


class CloudSttEngine:
    name = "cloud_stt"

    def is_available(self) -> bool:
        cfg = get_settings()
        return bool(cfg.cloud_stt_url.strip()) and cfg.recognition_stt in ("cloud", "auto")

    async def transcribe(self, audio_path: Path, lang_hint: str | None = None) -> Transcript:
        if not self.is_available() or not audio_path.exists():
            return Transcript(engine=self.name)
        cfg = get_settings()
        headers: dict[str, str] = {}
        if cfg.cloud_stt_api_key:
            headers["Authorization"] = f"Bearer {cfg.cloud_stt_api_key}"
        try:
            async with httpx.AsyncClient(timeout=12.0) as client:
                with audio_path.open("rb") as fh:
                    files = {"file": (audio_path.name, fh, "audio/wav")}
                    data = {"language": lang_hint} if lang_hint else {}
                    resp = await client.post(cfg.cloud_stt_url, headers=headers, files=files, data=data)
                if resp.status_code != 200:
                    return Transcript(engine=self.name)
                payload = resp.json()
                txt = str(payload.get("text", "")).strip()
                return Transcript(
                    text=txt,
                    language=payload.get("language") or lang_hint,
                    confidence=float(payload.get("confidence", 0.85 if txt else 0.0)),
                    engine=self.name,
                )
        except Exception:
            return Transcript(engine=self.name)
