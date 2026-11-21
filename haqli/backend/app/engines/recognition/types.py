"""Pydantic v2 data contracts for the Haqli Recognition Engine ("Tanib olish") v1.0 (§4.1)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field as PydField, model_validator

Kind = Literal["document", "receipt", "id_mrz", "voice", "qr"]
Script = Literal["latn", "cyrl", "mixed", "unknown"]
Source = Literal["rule", "ocr", "llm", "user"]
Stage = Literal["received", "quality", "preprocess", "recognize", "classify", "parse", "validate", "done"]
StageState = Literal["pending", "running", "ok", "warn", "failed", "skipped"]
DocType = Literal[
    "rental_contract",
    "employment_contract",
    "microloan_contract",
    "receipt",
    "fine_decision",
    "demand_letter",
    "tilxat",
    "passport_data_page",
    "unknown",
]
RouteTarget = Literal["himoya", "tilxat", "skaner", "none"]
LangDetected = Literal["uz", "ru", "mixed"]


def _to_camel(s: str) -> str:
    parts = s.split("_")
    return parts[0] + "".join(p.capitalize() for p in parts[1:])


class RecognitionBaseModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=_to_camel,
        populate_by_name=True,
        ser_json_timedelta="iso8601",
    )


class Field(RecognitionBaseModel):
    """Single extracted structured field carrying provenance, span/bbox, and confirmation flag."""

    key: str
    value: str | Decimal | date | None = None
    display: str = ""
    confidence: float = PydField(default=0.0, ge=0.0, le=1.0)
    source: Source = "rule"
    span: tuple[int, int] | None = None
    bbox: tuple[float, float, float, float] | None = None
    needs_confirm: bool = False

    @model_validator(mode="after")
    def _enforce_confirm_threshold(self) -> "Field":
        if self.confidence < 0.75:
            self.needs_confirm = True
        if not self.display and self.value is not None:
            self.display = str(self.value)
        return self


class StageEvent(RecognitionBaseModel):
    """SSE pipeline progress event persisted per job (§4.1, §5)."""

    job_id: str
    stage: Stage
    state: StageState
    elapsed_ms: int = 0
    message_key: str | None = None


class RouteHint(RecognitionBaseModel):
    """Downstream navigation target and prefill map produced by the pipeline."""

    target: RouteTarget = "none"
    category: str | None = None
    prefill: dict[str, Any] = PydField(default_factory=dict)


class RecognitionResult(RecognitionBaseModel):
    """Final structured recognition response (§4.1)."""

    job_id: str
    kind: Kind
    doc_type: DocType | None = None
    doc_type_confidence: float | None = None
    script: Script = "unknown"
    language: LangDetected | None = None
    engine: str = "deterministic"
    fields: list[Field] = PydField(default_factory=list)
    raw_text_preview: str = ""
    warnings: list[str] = PydField(default_factory=list)
    route_hint: RouteHint | None = None
    processing_time_ms: int = 0
    clauses: list[dict[str, Any]] = PydField(default_factory=list)
    transcript: str | None = None


class QualityMetrics(RecognitionBaseModel):
    """Image quality measurements produced by server `quality.py` (§5.1)."""

    blur: float = 0.0
    brightness: float = 0.0
    contrast: float = 0.0
    skew_deg: float = 0.0
    resolution_min: int = 0
    glare_ratio: float = 0.0
    ok: bool = True
    rejected: bool = False
    warnings: list[str] = PydField(default_factory=list)


class OcrLine(RecognitionBaseModel):
    text: str
    confidence: float = PydField(default=0.0, ge=0.0, le=1.0)
    bbox: tuple[float, float, float, float] | None = None


class OcrResult(RecognitionBaseModel):
    lines: list[OcrLine] = PydField(default_factory=list)
    mean_conf: float = 0.0
    engine: str = "none"

    @property
    def full_text(self) -> str:
        return "\n".join(ln.text for ln in self.lines if ln.text)


class TranscriptSegment(RecognitionBaseModel):
    start: float = 0.0
    end: float = 0.0
    text: str = ""
    avg_logprob: float = 0.0


class Transcript(RecognitionBaseModel):
    text: str = ""
    language: str | None = None
    segments: list[TranscriptSegment] = PydField(default_factory=list)
    confidence: float = 0.0
    engine: str = "none"


class ConfirmFieldInput(RecognitionBaseModel):
    key: str
    value: Any = None


class ConfirmJobRequest(RecognitionBaseModel):
    fields: list[ConfirmFieldInput] = PydField(default_factory=list)
    doc_type: DocType | None = None


class VerifyDocumentResult(RecognitionBaseModel):
    status: Literal["valid", "tampered", "unknown"]
    doc_id: str | None = None
    doc_kind: str | None = None
    doc_hash_short: str | None = None
    seal_verified: bool = False
    chain_verified: bool | None = None
    mismatched_fields: list[str] = PydField(default_factory=list)
    checked_fields: dict[str, str] = PydField(default_factory=dict)
    issued_at: str | None = None
    e_confirm_notice: str = (
        "Haqli kriptografik muhri hujjat o'zgartirilmaganini tasdiqlaydi; malakali ERI (ETsP) o'rnini bosmaydi."
    )
    detail: str | None = None
    processing_time_ms: int = 0
