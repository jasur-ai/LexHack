"""SQLAlchemy 2.0 async data model matching Haqli v2.1 §5 specification."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, utcnow, uuid7_str


class TimestampMixin:
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid7_str)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)


class User(TimestampMixin, Base):
    __tablename__ = "users"

    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(160), nullable=False)
    username: Mapped[str | None] = mapped_column(String(80), nullable=True)
    role: Mapped[str] = mapped_column(String(20), default="citizen", nullable=False)
    license_number: Mapped[str | None] = mapped_column(String(80), nullable=True)
    language: Mapped[str] = mapped_column(String(10), default="uz_lat", nullable=False)
    theme_pref: Mapped[str] = mapped_column(String(10), default="auto", nullable=False)
    profile_tags: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    push_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    consent_version: Mapped[str | None] = mapped_column(String(24), nullable=True)
    consent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class DisputeCase(TimestampMixin, Base):
    __tablename__ = "dispute_cases"
    __table_args__ = (Index("ix_disputes_user_created", "user_id", "created_at"),)

    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    category: Mapped[str] = mapped_column(String(24), nullable=False)
    respondent_name: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    incident_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    claim_amount_uzs: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0.00"), nullable=False)
    delay_days: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    computed: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    structured_facts: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    citations: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    case_strength: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    strength_breakdown: Mapped[dict[str, int]] = mapped_column(JSON, default=dict, nullable=False)
    assessment_text: Mapped[str] = mapped_column(Text, default="", nullable=False)
    talabnoma_text: Mapped[str] = mapped_column(Text, default="", nullable=False)
    complaint_text: Mapped[str] = mapped_column(Text, default="", nullable=False)
    evidence_ids: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="draft", nullable=False)
    doc_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    seal_signature: Mapped[str | None] = mapped_column(Text, nullable=True)
    pdf_path: Mapped[str | None] = mapped_column(String(300), nullable=True)
    locale_used: Mapped[str] = mapped_column(String(10), default="uz_lat", nullable=False)
    engine_used: Mapped[str] = mapped_column(String(24), default="deterministic", nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class TilxatAgreement(TimestampMixin, Base):
    __tablename__ = "tilxat_agreements"
    __table_args__ = (Index("ix_tilxat_user_created", "user_id", "created_at"),)

    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    doc_type: Mapped[str] = mapped_column(String(24), default="loan", nullable=False)
    party_a_name: Mapped[str] = mapped_column(String(180), nullable=False)
    party_a_passport_enc: Mapped[str | None] = mapped_column(Text, nullable=True)
    party_a_tg_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    party_a_signed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    party_b_name: Mapped[str] = mapped_column(String(180), nullable=False)
    party_b_passport_enc: Mapped[str | None] = mapped_column(Text, nullable=True)
    party_b_tg_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    party_b_signed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    amount_uzs: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    bhm_ratio: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    requires_written: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    threshold_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    daily_penalty_percent: Mapped[Decimal] = mapped_column(Numeric(6, 3), default=Decimal("0.000"), nullable=False)
    terms_summary: Mapped[str] = mapped_column(Text, default="", nullable=False)
    sign_token: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    sign_token_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    chain_prev_hash: Mapped[str] = mapped_column(String(64), default="0" * 64, nullable=False)
    doc_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    seal_signature: Mapped[str] = mapped_column(Text, nullable=False)
    pdf_path: Mapped[str | None] = mapped_column(String(300), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="pending_counterparty", nullable=False)
    locale_used: Mapped[str] = mapped_column(String(10), default="uz_lat", nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ContractAudit(TimestampMixin, Base):
    __tablename__ = "contract_audits"
    __table_args__ = (Index("ix_audits_user_created", "user_id", "created_at"),)

    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(220), nullable=False)
    source: Mapped[str] = mapped_column(String(24), default="text", nullable=False)
    extracted_text_enc: Mapped[str] = mapped_column(Text, nullable=False)
    language_detected: Mapped[str] = mapped_column(String(10), default="uz_lat", nullable=False)
    safety_score: Mapped[int] = mapped_column(Integer, default=50, nullable=False)
    red_flags: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    warnings: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    safe_clauses: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    doc_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    seal_signature: Mapped[str | None] = mapped_column(Text, nullable=True)
    pdf_path: Mapped[str | None] = mapped_column(String(300), nullable=True)
    recognition_job_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    engine_used: Mapped[str] = mapped_column(String(24), default="deterministic", nullable=False)


class RecognitionJob(TimestampMixin, Base):
    __tablename__ = "recognition_jobs"
    __table_args__ = (
        Index("ix_recog_user_created", "user_id", "created_at"),
        Index("ix_recog_expires_at", "expires_at"),
    )

    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    kind: Mapped[str] = mapped_column(String(24), nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="queued", nullable=False)
    stages: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    raw_text_enc: Mapped[str | None] = mapped_column(Text, nullable=True)
    parsed: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    result_enc: Mapped[str | None] = mapped_column(Text, nullable=True)
    file_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("uploaded_files.id", ondelete="SET NULL"), nullable=True)
    confirmed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    pii_redacted: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class UploadedFile(TimestampMixin, Base):
    __tablename__ = "uploaded_files"
    __table_args__ = (Index("ix_uploaded_purge_at", "purge_at"),)

    owner_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    mime: Mapped[str] = mapped_column(String(120), nullable=False)
    size: Mapped[int] = mapped_column(Integer, nullable=False)
    path: Mapped[str] = mapped_column(String(320), nullable=False)
    purge_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    attached_case_id: Mapped[str | None] = mapped_column(String(36), nullable=True)


class LawAlert(TimestampMixin, Base):
    __tablename__ = "law_alerts"

    decree_ref: Mapped[str] = mapped_column(String(140), nullable=False)
    published_date: Mapped[date] = mapped_column(Date, nullable=False)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    title_uz: Mapped[str] = mapped_column(String(240), nullable=False)
    title_ru: Mapped[str] = mapped_column(String(240), nullable=False)
    what_changed_uz: Mapped[str] = mapped_column(Text, nullable=False)
    what_changed_ru: Mapped[str] = mapped_column(Text, nullable=False)
    wallet_impact_uz: Mapped[str] = mapped_column(Text, nullable=False)
    wallet_impact_ru: Mapped[str] = mapped_column(Text, nullable=False)
    action_label_uz: Mapped[str] = mapped_column(String(140), nullable=False)
    action_label_ru: Mapped[str] = mapped_column(String(140), nullable=False)
    action_route: Mapped[str] = mapped_column(String(140), nullable=False)
    legal_ref_id: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="needs_review", nullable=False)


class AdvocateLead(TimestampMixin, Base):
    __tablename__ = "advocate_leads"

    case_id: Mapped[str] = mapped_column(String(36), ForeignKey("dispute_cases.id", ondelete="CASCADE"), index=True, nullable=False)
    advocate_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="new", nullable=False)
    brief_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    platform_fee_percent: Mapped[int] = mapped_column(Integer, default=15, nullable=False)
    decline_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid7_str)
    actor: Mapped[str] = mapped_column(String(80), nullable=False)
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    entity: Mapped[str] = mapped_column(String(60), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(64), nullable=False)
    meta: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    ip_hash: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class ConsentRecord(Base):
    __tablename__ = "consent_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid7_str)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    version: Mapped[str] = mapped_column(String(24), nullable=False)
    scope: Mapped[str] = mapped_column(String(120), nullable=False)
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
