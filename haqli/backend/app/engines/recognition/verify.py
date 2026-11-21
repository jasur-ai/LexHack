"""Haqli PDF authenticity verification (§8): metadata -> QR -> footer -> canonical SHA-256 + Ed25519 + Tilxat hash chain + field diff."""

from __future__ import annotations

import io
import re
import time
from decimal import Decimal
from typing import Any

from pypdf import PdfReader
from sqlalchemy.ext.asyncio import AsyncSession

from app.engines.recognition.entities.money import extract_money
from app.engines.recognition.types import VerifyDocumentResult
from app.models.entities import ContractAudit, DisputeCase, TilxatAgreement
from app.security.crypto import get_crypto

_META_DOC_ID_RE = re.compile(r"HaqliDocId[=:]\s*([0-9a-fA-F\-]{8,36})")
_META_SEAL_RE = re.compile(r"HaqliSeal[=:]\s*([A-Za-z0-9+/=]{32,128})")
_QR_URL_ID_RE = re.compile(r"/v/([0-9a-fA-F\-]{8,36})")
_FOOTER_ID_RE = re.compile(r"ID:\s*([0-9a-fA-F\-]{8,36})")


def _decode_qr_from_pdf_page1(pdf_bytes: bytes) -> str | None:
    """Attempt QR decoding from rendered page 1 via pypdfium2 + OpenCV QRCodeDetector if available."""
    try:
        import cv2  # type: ignore
        import numpy as np  # type: ignore
        import pypdfium2 as pdfium  # type: ignore

        pdf = pdfium.PdfDocument(pdf_bytes)
        if len(pdf) == 0:
            return None
        pil_img = pdf[0].render(scale=2.0).to_pil().convert("RGB")
        arr = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
        detector = cv2.QRCodeDetector()
        val, _, _ = detector.detectAndDecode(arr)
        return val.strip() if val else None
    except Exception:
        return None


def extract_pdf_doc_info(pdf_bytes: bytes) -> dict[str, Any]:
    """Extract doc_id, seal metadata, and full text from an uploaded PDF (§8: metadata -> QR -> footer)."""
    doc_id: str | None = None
    embedded_seal: str | None = None
    full_text = ""

    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
        meta = reader.metadata or {}
        for field_key in ("/Subject", "/Keywords"):
            val = str(meta.get(field_key, "") or "")
            if not doc_id and (m := _META_DOC_ID_RE.search(val)):
                doc_id = m.group(1)
            if not embedded_seal and (m := _META_SEAL_RE.search(val)):
                embedded_seal = m.group(1)
        full_text = "\n".join(p.extract_text() or "" for p in reader.pages)
    except Exception:
        return {"doc_id": None, "embedded_seal": None, "text": ""}

    # Priority 2: QR decode on page 1
    if not doc_id:
        qr_val = _decode_qr_from_pdf_page1(pdf_bytes)
        if qr_val and (m := _QR_URL_ID_RE.search(qr_val)):
            doc_id = m.group(1)

    # Priority 3: Footer URL or ID regex
    if not doc_id:
        if m := _QR_URL_ID_RE.search(full_text):
            doc_id = m.group(1)
        elif m := _FOOTER_ID_RE.search(full_text):
            doc_id = m.group(1)

    return {"doc_id": doc_id, "embedded_seal": embedded_seal, "text": full_text}


def _mask_name(name: str) -> str:
    parts = [p for p in name.strip().split() if p]
    return " ".join(f"{p[0]}***" if len(p) > 2 else p for p in parts)


def _compare_pdf_key_fields(
    *,
    pdf_text: str,
    expected_amount: Decimal | None,
    expected_parties: list[str],
    expected_dates: list[str],
) -> list[str]:
    """Verify key extracted fields in an uploaded PDF match the canonical database record (§8)."""
    if not pdf_text.strip():
        return []
    mismatches: list[str] = []
    compact_text = re.sub(r"[\s\u00a0\u202f]+", "", pdf_text)

    if expected_amount is not None and expected_amount > 0:
        amt_int = str(int(expected_amount))
        amt_2dp = str(expected_amount.quantize(Decimal("0.01")))
        moneys = extract_money(pdf_text)
        money_vals = {m.amount.quantize(Decimal("0.01")) for m in moneys}
        if (
            amt_int not in compact_text
            and amt_2dp not in compact_text
            and expected_amount.quantize(Decimal("0.01")) not in money_vals
        ):
            mismatches.append("amount")

    low_text = pdf_text.lower()
    for idx, party in enumerate(expected_parties):
        clean_p = party.strip()
        if len(clean_p) >= 3 and clean_p.lower() not in low_text:
            # Also check first token (surname/company word) to allow layout wrapping
            first_tok = clean_p.split()[0].lower()
            if first_tok not in low_text:
                mismatches.append(f"party_{idx + 1}")

    for dt_iso in expected_dates:
        if dt_iso and dt_iso not in pdf_text:
            # Also accept DD.MM.YYYY representation
            parts = dt_iso.split("-")
            dmy = f"{parts[2]}.{parts[1]}.{parts[0]}" if len(parts) == 3 else dt_iso
            if dmy not in pdf_text:
                mismatches.append("date")

    return list(dict.fromkeys(mismatches))


async def verify_document_authenticity(
    db: AsyncSession,
    *,
    doc_id: str | None = None,
    qr_payload: str | None = None,
    uploaded_pdf_bytes: bytes | None = None,
    public_viewer: bool = True,
) -> VerifyDocumentResult:
    """Verify a Haqli document via canonical SHA-256, Ed25519 seal, Tilxat chain, and uploaded PDF field check (§8)."""
    t0 = time.perf_counter()
    crypto = get_crypto()

    pdf_info: dict[str, Any] = {"doc_id": None, "embedded_seal": None, "text": ""}
    if uploaded_pdf_bytes:
        pdf_info = extract_pdf_doc_info(uploaded_pdf_bytes)

    resolved_id = doc_id
    if not resolved_id and qr_payload and (m := _QR_URL_ID_RE.search(qr_payload)):
        resolved_id = m.group(1)
    if not resolved_id:
        resolved_id = pdf_info.get("doc_id")

    if not resolved_id:
        return VerifyDocumentResult(
            status="unknown",
            doc_id=None,
            detail="Hujjat identifikatori (ID/QR) topilmadi.",
            processing_time_ms=int((time.perf_counter() - t0) * 1000),
        )

    target: TilxatAgreement | DisputeCase | ContractAudit | None = None
    doc_kind = "unknown"
    for model, kind_name in ((TilxatAgreement, "tilxat"), (DisputeCase, "dispute"), (ContractAudit, "contract_audit")):
        found = await db.get(model, resolved_id)
        if found is not None:
            target = found
            doc_kind = kind_name
            break

    if target is None:
        return VerifyDocumentResult(
            status="unknown",
            doc_id=resolved_id,
            detail="Hujjat Haqli reyestrida topilmadi.",
            processing_time_ms=int((time.perf_counter() - t0) * 1000),
        )

    stored_hash = target.doc_hash or ""
    stored_seal = target.seal_signature or ""
    seal_ok = bool(stored_hash and stored_seal and crypto.verify_seal(stored_hash, stored_seal))

    # If the PDF embedded a seal in metadata, it must match the stored seal in constant time
    embedded_seal = pdf_info.get("embedded_seal")
    if embedded_seal and stored_seal and not crypto.constant_time_eq(embedded_seal, stored_seal):
        seal_ok = False

    chain_ok: bool | None = None
    expected_amount: Decimal | None = None
    expected_parties: list[str] = []
    expected_dates: list[str] = []
    checked_fields: dict[str, str] = {}

    if isinstance(target, TilxatAgreement):
        # Verify hash chain H_n = SHA256(H_{n-1} || canonical_json) for signed or pending Tilxat
        if target.status == "signed" and target.party_b_signed_at:
            signed_payload = {
                "id": target.id,
                "prevHash": target.chain_prev_hash,
                "partyATg": target.party_a_tg_id,
                "partyBTg": target.party_b_tg_id,
                "signedAt": target.party_b_signed_at.isoformat(),
                "amountUzs": str(target.amount_uzs),
            }
            recomputed = crypto.chain_hash(target.chain_prev_hash, signed_payload)
            chain_ok = crypto.constant_time_eq(recomputed, stored_hash)
        else:
            canonical = {
                "docType": target.doc_type,
                "partyA": target.party_a_name,
                "partyB": target.party_b_name,
                "amountUzs": str(target.amount_uzs),
                "dueDate": target.due_date.isoformat(),
                "penalty": str(target.daily_penalty_percent),
                "terms": target.terms_summary,
            }
            recomputed = crypto.chain_hash(target.chain_prev_hash, canonical)
            chain_ok = crypto.constant_time_eq(recomputed, stored_hash)

        expected_amount = Decimal(str(target.amount_uzs))
        expected_parties = [target.party_a_name, target.party_b_name]
        expected_dates = [target.due_date.isoformat()]
        checked_fields = {
            "amountUzs": str(target.amount_uzs),
            "partyA": _mask_name(target.party_a_name) if public_viewer else target.party_a_name,
            "partyB": _mask_name(target.party_b_name) if public_viewer else target.party_b_name,
            "dueDate": target.due_date.isoformat(),
            "status": target.status,
        }

    elif isinstance(target, DisputeCase):
        total_uzs = str((target.computed or {}).get("totalUzs", target.claim_amount_uzs))
        canonical = {
            "id": target.id,
            "category": target.category,
            "respondent": target.respondent_name,
            "totalUzs": total_uzs,
            "talabnoma": target.talabnoma_text,
        }
        recomputed = crypto.sha256_canonical(canonical)
        chain_ok = crypto.constant_time_eq(recomputed, stored_hash)
        expected_amount = Decimal(str(target.claim_amount_uzs))
        expected_parties = [target.respondent_name]
        checked_fields = {
            "category": target.category,
            "respondent": _mask_name(target.respondent_name) if public_viewer else target.respondent_name,
            "claimAmountUzs": str(target.claim_amount_uzs),
        }

    elif isinstance(target, ContractAudit):
        canonical = {
            "title": target.title,
            "score": target.safety_score,
            "flags": len(target.red_flags or []),
        }
        recomputed = crypto.sha256_canonical(canonical)
        chain_ok = crypto.constant_time_eq(recomputed, stored_hash)
        checked_fields = {"title": target.title, "safetyScore": str(target.safety_score)}

    # Key field diff + PDF EOF integrity check (regenerated clean layout stays valid; appended garbage/edited fields -> tampered)
    mismatched_fields: list[str] = []
    if uploaded_pdf_bytes:
        eof_pos = uploaded_pdf_bytes.rfind(b"%%EOF")
        if eof_pos == -1 or len(uploaded_pdf_bytes[eof_pos + 5 :].strip()) > 0:
            mismatched_fields.append("pdf_structure")
        mismatched_fields.extend(
            _compare_pdf_key_fields(
                pdf_text=pdf_info.get("text", ""),
                expected_amount=expected_amount,
                expected_parties=expected_parties,
                expected_dates=expected_dates,
            )
        )
        mismatched_fields = list(dict.fromkeys(mismatched_fields))

    tampered = (not seal_ok) or (chain_ok is False) or bool(mismatched_fields)
    return VerifyDocumentResult(
        status="tampered" if tampered else "valid",
        doc_id=target.id,
        doc_kind=doc_kind,
        doc_hash_short=stored_hash[:16],
        seal_verified=seal_ok,
        chain_verified=chain_ok,
        mismatched_fields=mismatched_fields,
        checked_fields=checked_fields,
        issued_at=target.created_at.isoformat(),
        processing_time_ms=int((time.perf_counter() - t0) * 1000),
    )
