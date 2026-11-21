"""Himoya (Dispute Engine) router: drafts, deterministic analysis + SSE, simulated pay, and sealed PDF generation."""

from __future__ import annotations

import time
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_db, uuid7_str
from app.engines.drafter import draft_dispute_documents
from app.engines.pdf.generator import render_haqli_pdf
from app.engines.retrieval import get_instrument_store
from app.engines.rules import (
    case_strength,
    consumer_penalty,
    labor_delay_compensation,
    limitation_deadline,
    load_constants,
    response_deadline,
    traffic_appeal_window,
)
from app.models.entities import DisputeCase, User
from app.routers.deps import get_current_user, write_audit_log
from app.schemas.api import DisputeAnalyzeRequest, DisputeDraftCreate, DisputeDraftPatch
from app.security.crypto import get_crypto
from app.services.jobs import sse_broker
from app.services.payments import get_payment_provider

router = APIRouter(prefix="/api/disputes", tags=["disputes"])


def _case_dto(c: DisputeCase, locale: str | None = None) -> dict[str, Any]:
    loc = locale or c.locale_used
    store = get_instrument_store()
    resolved_citations = store.resolve_ids(c.citations or [], locale=loc)
    has_unverified = any(ci["status"] != "verified" for ci in resolved_citations)
    return {
        "id": c.id,
        "category": c.category,
        "respondentName": c.respondent_name,
        "incidentDate": c.incident_date.isoformat() if c.incident_date else None,
        "claimAmountUzs": str(c.claim_amount_uzs),
        "delayDays": c.delay_days,
        "computed": c.computed,
        "structuredFacts": c.structured_facts,
        "citations": resolved_citations,
        "hasUnverifiedLegalData": has_unverified,
        "caseStrength": c.case_strength,
        "strengthBreakdown": c.strength_breakdown,
        "assessmentText": c.assessment_text,
        "talabnomaText": c.talabnoma_text,
        "complaintText": c.complaint_text,
        "evidenceIds": c.evidence_ids or [],
        "status": c.status,
        "docHash": c.doc_hash,
        "pdfUrl": f"/api/disputes/{c.id}/pdf?type=talabnoma" if c.pdf_path else None,
        "localeUsed": c.locale_used,
        "engine": c.engine_used,
        "createdAt": c.created_at.isoformat(),
    }


@router.post("/drafts")
async def create_draft(
    req: DisputeDraftCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    case = DisputeCase(
        user_id=user.id,
        category=req.category,
        respondent_name=req.respondent_name,
        incident_date=req.incident_date,
        claim_amount_uzs=req.claim_amount_uzs,
        delay_days=req.delay_days,
        structured_facts=req.structured_facts,
        evidence_ids=req.evidence_ids,
        locale_used=req.locale,
        status="draft",
    )
    db.add(case)
    await db.commit()
    await db.refresh(case)
    return _case_dto(case)


@router.patch("/drafts/{case_id}")
async def patch_draft(
    case_id: str,
    req: DisputeDraftPatch,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    case = await db.get(DisputeCase, case_id)
    if case is None or case.user_id != user.id:
        raise HTTPException(status_code=404, detail="Draft not found.")
    if req.respondent_name is not None:
        case.respondent_name = req.respondent_name
    if req.incident_date is not None:
        case.incident_date = req.incident_date
    if req.claim_amount_uzs is not None:
        case.claim_amount_uzs = req.claim_amount_uzs
    if req.delay_days is not None:
        case.delay_days = req.delay_days
    if req.structured_facts is not None:
        case.structured_facts = req.structured_facts
    if req.evidence_ids is not None:
        case.evidence_ids = req.evidence_ids
    if req.locale is not None:
        case.locale_used = req.locale
    await db.commit()
    await db.refresh(case)
    return _case_dto(case)


@router.post("/analyze")
async def analyze_dispute(
    req: DisputeAnalyzeRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    t0 = time.perf_counter()
    job_id = uuid7_str()
    constants = load_constants()
    store = get_instrument_store()
    crypto = get_crypto()

    async def _emit(stage: str, state: str = "done", done: bool = False) -> None:
        await sse_broker.publish(
            job_id,
            {"stage": stage, "state": state, "elapsedMs": int((time.perf_counter() - t0) * 1000)},
            done=done,
        )

    await _emit("validate_facts")
    lim = limitation_deadline(req.category, req.incident_date, constants)
    resp_dl = response_deadline("consumer" if req.category == "consumer" else "talabnoma", date.today(), constants)

    penalty_uzs = Decimal("0.00")
    total_uzs = req.claim_amount_uzs
    formula = "Asosiy summa"
    legal_refs: list[str] = list(lim["legal_refs"]) + list(resp_dl["legal_refs"])
    extra_calc: dict[str, Any] = {}

    await _emit("compute_rules")
    if req.category == "consumer":
        calc = consumer_penalty(req.claim_amount_uzs, req.delay_days, constants)
        penalty_uzs = calc["penalty_uzs"]
        total_uzs = calc["total_uzs"]
        formula = calc["formula"]
        legal_refs.extend(calc["legal_refs"])
        extra_calc["penaltyDetail"] = {k: str(v) if isinstance(v, Decimal) else v for k, v in calc.items()}
    elif req.category == "labor":
        calc = labor_delay_compensation(req.claim_amount_uzs, req.delay_days, constants)
        penalty_uzs = calc["compensation_uzs"]
        total_uzs = calc["total_uzs"]
        formula = calc["formula"]
        legal_refs.extend(calc["legal_refs"])
        legal_refs.extend(["inst_mk_104", "inst_mk_165"])
        extra_calc["penaltyDetail"] = {k: str(v) if isinstance(v, Decimal) else v for k, v in calc.items()}
    elif req.category == "traffic":
        tw = traffic_appeal_window(req.incident_date, constants)
        legal_refs.extend(tw["legal_refs"])
        extra_calc["trafficWindow"] = tw
    elif req.category == "rental":
        legal_refs.extend(["inst_fk_535", "inst_fk_260"])
    elif req.category == "debt":
        legal_refs.extend(["inst_fk_108", "inst_fk_732", "inst_fk_260"])

    legal_refs = list(dict.fromkeys(legal_refs))
    resolved_citations = store.resolve_ids(legal_refs, locale=req.locale)

    strength = case_strength(
        {
            "has_written_evidence": req.has_written_evidence,
            "evidence_count": len(req.evidence_ids),
            "incident_date": req.incident_date,
            "delay_days": req.delay_days,
            "claim_amount_uzs": req.claim_amount_uzs,
            "limitation_status": lim["status"],
            "legal_refs": legal_refs,
            "respondent_name": req.respondent_name,
        },
        constants,
    )

    await _emit("draft_documents")
    drafts = draft_dispute_documents(
        category=req.category,
        citizen_name=user.full_name,
        respondent_name=req.respondent_name,
        incident_date=req.incident_date,
        claim_amount_uzs=req.claim_amount_uzs,
        penalty_uzs=penalty_uzs,
        total_uzs=total_uzs,
        formula=formula,
        delay_days=req.delay_days,
        response_days=resp_dl["days"],
        response_due=resp_dl["deadline_date"],
        citations=resolved_citations,
        description=req.description,
        locale=req.locale,
    )

    computed_payload = {
        "constantsVersion": constants.version,
        "claimAmountUzs": str(req.claim_amount_uzs),
        "penaltyUzs": str(penalty_uzs),
        "totalUzs": str(total_uzs),
        "formula": formula,
        "limitation": lim,
        "responseDeadline": resp_dl,
        "talabnomaPriceUzs": str(constants.val("pricing.talabnoma_uzs")),
        **extra_calc,
    }

    case: DisputeCase | None = await db.get(DisputeCase, req.case_id) if req.case_id else None
    if case is None or case.user_id != user.id:
        case = DisputeCase(user_id=user.id, category=req.category)
        db.add(case)

    case.category = req.category
    case.respondent_name = req.respondent_name
    case.incident_date = req.incident_date
    case.claim_amount_uzs = req.claim_amount_uzs
    case.delay_days = req.delay_days
    case.computed = computed_payload
    case.structured_facts = {**req.structured_facts, "description": req.description, "hasWrittenEvidence": req.has_written_evidence}
    case.citations = legal_refs
    case.case_strength = strength["score"]
    case.strength_breakdown = strength["breakdown"]
    case.assessment_text = drafts["assessment"]
    case.talabnoma_text = drafts["talabnoma"]
    case.complaint_text = drafts["complaint"]
    case.evidence_ids = req.evidence_ids
    case.locale_used = req.locale
    case.status = "analyzed"
    case.engine_used = "deterministic"

    await db.flush()
    canonical = {
        "id": case.id,
        "category": case.category,
        "respondent": case.respondent_name,
        "totalUzs": str(total_uzs),
        "talabnoma": case.talabnoma_text,
    }
    case.doc_hash = crypto.sha256_canonical(canonical)
    case.seal_signature = crypto.sign_seal(case.doc_hash)

    await write_audit_log(db, actor=user.id, action="analyze_dispute", entity="dispute", entity_id=case.id, request=request)
    await db.commit()
    await db.refresh(case)
    await _emit("result", done=True)

    dto = _case_dto(case, locale=req.locale)
    dto["jobId"] = job_id
    return dto


@router.post("/{case_id}/pay")
async def pay_dispute(
    case_id: str,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    case = await db.get(DisputeCase, case_id)
    if case is None or case.user_id != user.id:
        raise HTTPException(status_code=404, detail="Case not found.")
    constants = load_constants()
    price = constants.val("pricing.talabnoma_uzs")
    provider = get_payment_provider()
    res = await provider.create_payment(order_id=case.id, amount_uzs=price, user_id=user.id)
    case.status = "paid"
    await write_audit_log(db, actor=user.id, action="pay_dispute", entity="dispute", entity_id=case.id, meta={"provider": res.provider}, request=request)
    await db.commit()
    return {
        "paymentId": res.payment_id,
        "provider": res.provider,
        "status": res.status,
        "amountUzs": str(res.amount_uzs),
    }


@router.post("/{case_id}/documents")
async def generate_dispute_document(
    case_id: str,
    doc_type: str = Query("talabnoma", alias="type"),
    locale: str | None = Query(None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    cfg = get_settings()
    case = await db.get(DisputeCase, case_id)
    if case is None or case.user_id != user.id:
        raise HTTPException(status_code=404, detail="Case not found.")
    if doc_type == "talabnoma" and case.status not in ("paid", "escalated", "closed"):
        raise HTTPException(status_code=402, detail="Payment required before generating Talabnoma PDF.")

    loc = locale or case.locale_used
    body_text = case.talabnoma_text if doc_type == "talabnoma" else case.complaint_text
    title = "RASMIY TALABNOMA" if doc_type == "talabnoma" else "DAVLAT ORGANIGA SHIKOYAT"
    subtitle = f"Ish #{case.id[:8]} · Javobgar: {case.respondent_name}"
    comp = case.computed or {}
    table_rows = [
        ["Ko'rsatkich", "Qiymat"],
        ["Asosiy talab summasi", f"{comp.get('claimAmountUzs', '0')} so'm"],
        ["Penya / kompensatsiya", f"{comp.get('penaltyUzs', '0')} so'm ({comp.get('formula', '')})"],
        ["Jami to'lanishi lozim", f"{comp.get('totalUzs', '0')} so'm"],
        ["Javob muddati", str((comp.get("responseDeadline") or {}).get("deadline_date", ""))],
    ]
    out_file = cfg.pdf_dir / f"dispute_{case.id}_{doc_type}_{loc}.pdf"
    render_haqli_pdf(
        doc_id=case.id,
        title=title,
        subtitle=subtitle,
        body_paragraphs=body_text.split("\n\n"),
        table_rows=table_rows,
        doc_hash=case.doc_hash or "0" * 64,
        seal_signature=case.seal_signature or "",
        needs_review=True,
        locale=loc,
        output_path=out_file,
    )
    case.pdf_path = str(out_file)
    await db.commit()
    return {
        "docId": case.id,
        "type": doc_type,
        "pdfUrl": f"/api/disputes/{case.id}/pdf?type={doc_type}&locale={loc}",
        "docHash": case.doc_hash,
    }


@router.get("/{case_id}/pdf")
async def download_dispute_pdf(
    case_id: str,
    doc_type: str = Query("talabnoma", alias="type"),
    locale: str | None = Query(None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FileResponse:
    cfg = get_settings()
    case = await db.get(DisputeCase, case_id)
    if case is None or (case.user_id != user.id and user.role != "advocate"):
        raise HTTPException(status_code=404, detail="Document not found.")
    loc = locale or case.locale_used
    path = cfg.pdf_dir / f"dispute_{case.id}_{doc_type}_{loc}.pdf"
    if not path.exists() and case.pdf_path and Path(case.pdf_path).exists():
        path = Path(case.pdf_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="PDF has not been generated yet.")
    return FileResponse(path, media_type="application/pdf", filename=f"haqli-{doc_type}-{case.id[:8]}.pdf")


@router.get("")
async def list_disputes(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    res = await db.execute(
        select(DisputeCase)
        .where(DisputeCase.user_id == user.id, DisputeCase.deleted_at.is_(None))
        .order_by(desc(DisputeCase.created_at))
        .limit(30)
    )
    return [_case_dto(c) for c in res.scalars().all()]


@router.get("/{case_id}")
async def get_dispute(
    case_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    case = await db.get(DisputeCase, case_id)
    if case is None or (case.user_id != user.id and user.role != "advocate"):
        raise HTTPException(status_code=404, detail="Case not found.")
    return _case_dto(case)
