"""Pydantic v2 camelCase API schemas for Haqli v2.1."""

from app.schemas.api import (
    CamelModel,
    ConsentRequest,
    DisputeAnalyzeRequest,
    DisputeDraftCreate,
    DisputeDraftPatch,
    PreferencesPatch,
    ScannerAuditRequest,
    TelegramAuthRequest,
    TilxatCreateRequest,
    TilxatParseRequest,
    TilxatPublicSignRequest,
)

__all__ = [
    "CamelModel",
    "TelegramAuthRequest",
    "PreferencesPatch",
    "ConsentRequest",
    "DisputeDraftCreate",
    "DisputeDraftPatch",
    "DisputeAnalyzeRequest",
    "TilxatParseRequest",
    "TilxatCreateRequest",
    "TilxatPublicSignRequest",
    "ScannerAuditRequest",
]
