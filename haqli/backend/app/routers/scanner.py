"""Contract & Microloan Scanner router + contextual 'Ask about this clause' endpoint (Rule 5)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_db
from app.engines.audit import SAMPLE_CONTRACTS, audit_contract_deterministic
from app.engines.pdf.generator import render_haqli_pdf
from app.engines.retrieval import get_instrument_store
from app.engines.rules import load_constants
from app.engines.translit import localize_text
from app.models.entities import ContractAudit, RecognitionJob, User
from app.routers.deps import get_current_user, write_audit_log
from app.schemas.api import ClauseQuestionRequest, ScannerAuditRequest
from app.security.crypto import get_crypto

router = APIRouter(prefix="/api/scanner", tags=["scanner"])


def _audit_dto(a: ContractAudit) -> dict[str, Any]:
    return {
        "id": a.id,
        "title": a.title,
        "source": a.source,
        "languageDetected": a.language_detected,
        "safetyScore": a.safety_score,
        "verdict": "safe" if a.safety_score >= 75 else ("caution" if a.safety_score >= 45 else "high_risk"),
        "redFlags": a.red_flags,
        "warnings": a.warnings,
        "safeClauses": a.safe_clauses,
        "docHash": a.doc_hash,
        "pdfUrl": f"/api/scanner/{a.id}/pdf",
        "engine": a.engine_used,
        "createdAt": a.created_at.isoformat(),
    }


@router.get("/samples")
async def list_samples(locale: str = "uz_lat") -> list[dict[str, Any]]:
    out = []
    for sid, data in SAMPLE_CONTRACTS.items():
        title = localize_text(data["title_uz"], locale, data["title_ru"])
        text = localize_text(data["text_uz"], locale, data["text_ru"])
        out.append({"id": sid, "title": title, "preview": text[:140]})
    return out


@router.post("/audit")
async def run_contract_audit(
    req: ScannerAuditRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    crypto = get_crypto()
    constants = load_constants()
    source = "text"
    title = req.title or "Shartnoma auditi"
    text = (req.text or "").strip()

    if req.sample_id:
        sample = SAMPLE_CONTRACTS[req.sample_id]
        source = "sample"
        title = localize_text(sample["title_uz"], req.locale, sample["title_ru"])
        text = localize_text(sample["text_uz"], req.locale, sample["text_ru"])
    elif req.recognition_job_id:
        job = await db.get(RecognitionJob, req.recognition_job_id)
        if job is None or job.user_id != user.id:
            raise HTTPException(status_code=404, detail="Recognition job not found.")
        source = "camera"
        text = crypto.decrypt_field(job.raw_text_enc) or ""

    if len(text) < 20:
        raise HTTPException(status_code=400, detail="Contract text must be at least 20 characters.")

    result = audit_contract_deterministic(text, constants, locale=req.locale)
    doc_hash = crypto.sha256_canonical({"title": title, "score": result["safetyScore"], "flags": len(result["redFlags"])})
    seal = crypto.sign_seal(doc_hash)

    rec = ContractAudit(
        user_id=user.id,
        title=title,
        source=source,
        extracted_text_enc=crypto.encrypt_field(text) or "",
        language_detected=result["languageDetected"],
        safety_score=result["safetyScore"],
        red_flags=result["redFlags"],
        warnings=result["warnings"],
        safe_clauses=result["safeClauses"],
        doc_hash=doc_hash,
        seal_signature=seal,
        recognition_job_id=req.recognition_job_id,
        engine_used=result["engine"],
    )
    db.add(rec)
    await db.flush()
    await write_audit_log(db, actor=user.id, action="contract_audit", entity="contract_audit", entity_id=rec.id, request=request)
    await db.commit()
    await db.refresh(rec)
    return _audit_dto(rec)


@router.post("/ask-clause")
async def ask_about_clause(
    req: ClauseQuestionRequest,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Contextual clause Q&A allowed ONLY inside a result screen, strictly grounded in instruments.json (Rule 5)."""
    store = get_instrument_store()
    citations = store.resolve_ids(req.legal_refs, locale=req.locale) if req.legal_refs else store.search(
        f"{req.clause_text} {req.question}", top_k=2, locale=req.locale
    )
    if not citations:
        citations = store.search(req.clause_text, top_k=2, locale=req.locale)

    explanation_parts = [f"{c['instrument']} ({c['article']}): {c['summary']}" for c in citations]
    answer = "\n\n".join(explanation_parts) or localize_text(
        "Ushbu band bo'yicha aniq modda topilmadi; xavfsiz muqobil matndan foydalanish tavsiya etiladi.",
        req.locale,
        "Точная статья по этому пункту не найдена; рекомендуется использовать безопасную альтернативу.",
    )
    return {"answer": answer, "citations": citations, "engine": "deterministic"}


@router.get("/{audit_id}/pdf")
async def download_audit_pdf(
    audit_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FileResponse:
    cfg = get_settings()
    rec = await db.get(ContractAudit, audit_id)
    if rec is None or rec.user_id != user.id:
        raise HTTPException(status_code=404, detail="Audit not found.")
    out = cfg.pdf_dir / f"audit_{rec.id}.pdf"
    if not out.exists():
        paras = [f"Xavfsizlik darajasi: {rec.safety_score}/100"]
        for fl in rec.red_flags + rec.warnings:
            paras.append(
                f"[{fl['severity'].upper()}] {fl['quotedClause']}\n"
                f"Sabab: {fl['whyRisky']}\nXavfsiz muqobil: {fl['safeAlternative']}"
            )
        render_haqli_pdf(
            doc_id=rec.id,
            title="SHARTNOMA XAVFSIZLIK AUDITI",
            subtitle=rec.title,
            body_paragraphs=paras,
            doc_hash=rec.doc_hash or "0" * 64,
            seal_signature=rec.seal_signature or "",
            needs_review=True,
            output_path=out,
        )
        rec.pdf_path = str(out)
        await db.commit()
    return FileResponse(out, media_type="application/pdf", filename=f"haqli-audit-{rec.id[:8]}.pdf")


@router.get("")
async def list_audits(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    res = await db.execute(
        select(ContractAudit).where(ContractAudit.user_id == user.id).order_by(desc(ContractAudit.created_at)).limit(20)
    )
    return [_audit_dto(a) for a in res.scalars().all()]
