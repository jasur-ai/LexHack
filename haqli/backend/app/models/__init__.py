"""SQLAlchemy 2.0 ORM entities exports."""

from app.models.entities import (
    AdvocateLead,
    AuditLog,
    ConsentRecord,
    ContractAudit,
    DisputeCase,
    LawAlert,
    RecognitionJob,
    TilxatAgreement,
    UploadedFile,
    User,
)

__all__ = [
    "User",
    "DisputeCase",
    "TilxatAgreement",
    "ContractAudit",
    "RecognitionJob",
    "UploadedFile",
    "LawAlert",
    "AdvocateLead",
    "AuditLog",
    "ConsentRecord",
]
