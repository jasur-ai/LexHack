"""Recognition parsers package + backward-compatible exports for existing Haqli test suites."""

from __future__ import annotations

from typing import Any

from app.engines.recognition.classify import classify_document_sync
from app.engines.recognition.parsers.contract import parse_contract
from app.engines.recognition.parsers.fine import parse_fine
from app.engines.recognition.parsers.mrz import mrz_check_digit, parse_mrz, parse_mrz_td1, parse_mrz_td3
from app.engines.recognition.parsers.receipt import parse_receipt_v1

# Legacy mapping from v1.0 canonical DocType -> older Uzbek label used in initial test suite
_LEGACY_TYPE_MAP = {
    "fine_decision": "jarima_qarori",
    "microloan_contract": "mikroqarz_shartnomasi",
    "rental_contract": "ijara_shartnomasi",
    "employment_contract": "mehnat_shartnomasi",
    "demand_letter": "talabnoma",
    "tilxat": "tilxat",
    "receipt": "chek_kvitansiya",
    "passport_data_page": "pasport",
    "unknown": "boshqa_hujjat",
}


def classify_document(text: str) -> dict[str, Any]:
    doc_type, conf, _ = classify_document_sync(text)
    return {"type": _LEGACY_TYPE_MAP.get(doc_type, doc_type), "canonicalType": doc_type, "confidence": conf}


def parse_traffic_fine(text: str) -> dict[str, Any]:
    fields, _route, _warns = parse_fine(text)
    return {
        "fields": {f.key: (str(f.value) if f.value is not None else None) for f in fields},
        "confidences": {f.key: f.confidence for f in fields},
    }


def parse_receipt(text: str) -> dict[str, Any]:
    fields, _route, _warns = parse_receipt_v1(text)
    return {
        "fields": {f.key: (str(f.value) if f.value is not None else None) for f in fields},
        "confidences": {f.key: f.confidence for f in fields},
    }


__all__ = [
    "classify_document",
    "mrz_check_digit",
    "parse_contract",
    "parse_fine",
    "parse_mrz",
    "parse_mrz_td1",
    "parse_mrz_td3",
    "parse_receipt",
    "parse_receipt_v1",
    "parse_traffic_fine",
]
