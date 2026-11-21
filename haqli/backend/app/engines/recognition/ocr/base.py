"""OcrEngine protocol definition (§5.3)."""

from __future__ import annotations

from typing import Any, Protocol

from app.engines.recognition.types import OcrResult, Script


class OcrEngine(Protocol):
    name: str

    def is_available(self) -> bool: ...

    async def recognize(self, image: Any, hint: Script = "unknown") -> OcrResult: ...
