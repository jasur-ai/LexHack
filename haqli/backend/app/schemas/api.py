"""Pydantic v2 request/response schemas with camelCase serialization."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


def _to_camel(s: str) -> str:
    parts = s.split("_")
    return parts[0] + "".join(p.capitalize() for p in parts[1:])


class CamelModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=_to_camel,
        populate_by_name=True,
        from_attributes=True,
    )


class TelegramAuthRequest(CamelModel):
    init_data: str = ""
    demo_name: str | None = None
    # Random per-browser id (UUID v4) used for guest sessions outside Telegram.
    device_id: str | None = Field(default=None, min_length=16, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")


class AgentAskRequest(CamelModel):
    query: str = Field(min_length=3, max_length=2000)
    locale: Literal["uz_lat", "uz_cyr", "ru"] | None = None
    answer_style: Literal["concise", "detailed"] = "concise"
    # Previous question, sent when the user taps a suggested follow-up, so the agent keeps the topic.
    context: str | None = Field(default=None, max_length=600)


class PreferencesPatch(CamelModel):
    language: Literal["uz_lat", "uz_cyr", "ru"] | None = None
    role: Literal["citizen", "advocate"] | None = None
    invite_code: str | None = None
    license_number: str | None = None
    profile_tags: list[str] | None = None
    theme_pref: Literal["auto", "light", "dark"] | None = None
    push_enabled: bool | None = None


class ConsentRequest(CamelModel):
    version: str = "2026-v1"
    scope: str = "core_document_processing"


class DisputeDraftCreate(CamelModel):
    category: Literal["labor", "consumer", "rental", "traffic", "debt"]
    respondent_name: str = ""
    incident_date: date | None = None
    claim_amount_uzs: Decimal = Field(default=Decimal("0"), ge=0)
    delay_days: int = Field(default=0, ge=0, le=3650)
    structured_facts: dict[str, Any] = Field(default_factory=dict)
    evidence_ids: list[str] = Field(default_factory=list)
    locale: Literal["uz_lat", "uz_cyr", "ru"] = "uz_lat"


class DisputeDraftPatch(CamelModel):
    respondent_name: str | None = None
    incident_date: date | None = None
    claim_amount_uzs: Decimal | None = Field(default=None, ge=0)
    delay_days: int | None = Field(default=None, ge=0, le=3650)
    structured_facts: dict[str, Any] | None = None
    evidence_ids: list[str] | None = None
    locale: Literal["uz_lat", "uz_cyr", "ru"] | None = None


class DisputeAnalyzeRequest(CamelModel):
    case_id: str | None = None
    category: Literal["labor", "consumer", "rental", "traffic", "debt"]
    respondent_name: str = Field(..., min_length=2)
    incident_date: date
    claim_amount_uzs: Decimal = Field(default=Decimal("0"), ge=0)
    delay_days: int = Field(default=0, ge=0, le=3650)
    description: str = ""
    has_written_evidence: bool = True
    structured_facts: dict[str, Any] = Field(default_factory=dict)
    evidence_ids: list[str] = Field(default_factory=list)
    locale: Literal["uz_lat", "uz_cyr", "ru"] = "uz_lat"


class TilxatParseRequest(CamelModel):
    text: str = Field(..., min_length=3)
    locale: Literal["uz_lat", "uz_cyr", "ru"] = "uz_lat"


class TilxatCreateRequest(CamelModel):
    doc_type: Literal["loan", "deposit", "service"] = "loan"
    party_a_name: str = Field(..., min_length=2)
    party_a_passport: str | None = None
    party_b_name: str = Field(..., min_length=2)
    party_b_passport: str | None = None
    amount_uzs: Decimal = Field(..., gt=0)
    due_date: date
    daily_penalty_percent: Decimal = Field(default=Decimal("0.0"), ge=0, le=5)
    terms_summary: str = ""
    locale: Literal["uz_lat", "uz_cyr", "ru"] = "uz_lat"


class TilxatPublicSignRequest(CamelModel):
    init_data: str = ""
    signer_name: str | None = None
    signer_passport: str | None = None
    agreed: bool = False
    demo_confirm: bool = False


class ScannerAuditRequest(CamelModel):
    recognition_job_id: str | None = None
    text: str | None = None
    sample_id: Literal["rental", "microloan", "employment"] | None = None
    title: str | None = None
    locale: Literal["uz_lat", "uz_cyr", "ru"] = "uz_lat"


class ClauseQuestionRequest(CamelModel):
    clause_text: str
    question: str
    legal_refs: list[str] = Field(default_factory=list)
    locale: Literal["uz_lat", "uz_cyr", "ru"] = "uz_lat"


class LeadActionRequest(CamelModel):
    reason: str = ""
    message: str = ""
