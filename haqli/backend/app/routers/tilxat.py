"""Tilxat (P2P Receipt) router: parse, create with Art. 108 check, public counterparty sign, revoke, PDF, WebSocket."""

from __future__ import annotations

import secrets
from datetime import timedelta
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_db, utcnow
from app.engines.drafter import draft_tilxat_summary
from app.engines.intake import parse_intake_text
from app.engines.pdf.generator import render_haqli_pdf
from app.engines.rules import amount_in_words, check_written_form, load_constants
from app.models.entities import TilxatAgreement, User
from app.routers.deps import get_current_user, write_audit_log
from app.schemas.api import TilxatCreateRequest, TilxatParseRequest, TilxatPublicSignRequest
from app.security.crypto import get_crypto
from app.security.telegram_auth import TelegramAuthError, validate_init_data
from app.services.jobs import tilxat_ws_hub

router = APIRouter(tags=["tilxat"])


def _tilxat_dto(t: TilxatAgreement, *, public_view: bool = False) -> dict[str, Any]:
    cfg = get_settings()
    crypto = get_crypto()
    pa_pass = crypto.mask_passport(crypto.decrypt_field(t.party_a_passport_enc)) if t.party_a_passport_enc else None
    pb_pass = crypto.mask_passport(crypto.decrypt_field(t.party_b_passport_enc)) if t.party_b_passport_enc else None
    base = {
        "id": t.id,
        "docType": t.doc_type,
        "partyAName": t.party_a_name,
        "partyAPassportMasked": pa_pass,
        "partyASignedAt": t.party_a_signed_at.isoformat() if t.party_a_signed_at else None,
        "partyBName": t.party_b_name,
        "partyBPassportMasked": pb_pass,
        "partyBSignedAt": t.party_b_signed_at.isoformat() if t.party_b_signed_at else None,
        "amountUzs": str(t.amount_uzs),
        "amountInWords": amount_in_words(t.amount_uzs, t.locale_used),
        "bhmRatio": str(t.bhm_ratio),
        "requiresWritten": t.requires_written,
        "thresholdSnapshot": t.threshold_snapshot,
        "dueDate": t.due_date.isoformat(),
        "dailyPenaltyPercent": str(t.daily_penalty_percent),
        "termsSummary": t.terms_summary,
        "docHash": t.doc_hash,
        "status": t.status,
        "expiresAt": t.sign_token_expires_at.isoformat(),
        "pdfUrl": f"/api/tilxat/{t.id}/pdf" if t.pdf_path else None,
        "verifyUrl": f"{cfg.public_base_url.rstrip('/')}/v/{t.id}",
        "eConfirmNotice": (
            "Telegram tasdig'i va kriptografik muhr oddiy elektron tasdiq bo'lib, malakali ERI (ETsP) yoki notarial tasdiq o'rnini bosmaydi."
        ),
        "createdAt": t.created_at.isoformat(),
    }
    if not public_view:
        base["signToken"] = t.sign_token
        base["signDeepLink"] = f"https://t.me/{cfg.telegram_bot_username}/app?startapp=sign_{t.sign_token}"
        base["signWebUrl"] = f"{cfg.public_base_url.rstrip('/')}/sign/{t.sign_token}"
    return base


def _render_tilxat_pdf(t: TilxatAgreement, locale: str | None = None) -> Path:
    cfg = get_settings()
    crypto = get_crypto()
    loc = locale or t.locale_used
    pa_pass = crypto.decrypt_field(t.party_a_passport_enc) or "—"
    pb_pass = crypto.decrypt_field(t.party_b_passport_enc) or "—"
    words = amount_in_words(t.amount_uzs, loc)
    out = cfg.pdf_dir / f"tilxat_{t.id}_{loc}.pdf"
    rows = [
        ["Maydon", "Ma'lumot"],
        ["1-tomon (Beruvchi)", f"{t.party_a_name} | Pasport: {pa_pass} | TG: {t.party_a_tg_id or '—'}"],
        ["2-tomon (Oluvchi)", f"{t.party_b_name} | Pasport: {pb_pass} | TG: {t.party_b_tg_id or '—'}"],
        ["Summa", f"{t.amount_uzs} so'm ({words})"],
        ["BHM nisbati", f"{t.bhm_ratio} BHM (Yozma shakl majburiymi: {'Ha' if t.requires_written else 'Yo`q'})"],
        ["Qaytarish muddati", t.due_date.isoformat()],
        ["Kunlik penya", f"{t.daily_penalty_percent}%"],
        ["1-tomon tasdig'i", t.party_a_signed_at.isoformat() if t.party_a_signed_at else "Kutilmoqda"],
        ["2-tomon tasdig'i", t.party_b_signed_at.isoformat() if t.party_b_signed_at else "Kutilmoqda"],
    ]
    render_haqli_pdf(
        doc_id=t.id,
        title="QARZ / MAJBURIIYAT TILXATI" if loc != "ru" else "ДОЛГОВАЯ РАСПИСКА (ТИЛЬХАТ)",
        subtitle=f"Fuqarolik kodeksi 108, 732-733-moddalari asosida · Holat: {t.status.upper()}",
        body_paragraphs=[t.terms_summary],
        table_rows=rows,
        doc_hash=t.doc_hash,
        seal_signature=t.seal_signature,
        needs_review=True,
        locale=loc,
        output_path=out,
    )
    return out


@router.post("/api/tilxat/parse")
async def parse_tilxat(
    req: TilxatParseRequest,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    return await parse_intake_text(req.text)


@router.post("/api/tilxat")
async def create_tilxat(
    req: TilxatCreateRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    constants = load_constants()
    crypto = get_crypto()
    wf = check_written_form(req.amount_uzs, constants)

    summary = req.terms_summary.strip() or draft_tilxat_summary(
        doc_type=req.doc_type,
        party_a_name=req.party_a_name,
        party_b_name=req.party_b_name,
        amount_uzs=req.amount_uzs,
        due_date=req.due_date,
        daily_penalty_percent=req.daily_penalty_percent,
        locale=req.locale,
    )

    prev_res = await db.execute(select(TilxatAgreement.doc_hash).order_by(desc(TilxatAgreement.created_at)).limit(1))
    prev_hash = prev_res.scalar_one_or_none() or ("0" * 64)

    canonical = {
        "docType": req.doc_type,
        "partyA": req.party_a_name,
        "partyB": req.party_b_name,
        "amountUzs": str(req.amount_uzs),
        "dueDate": req.due_date.isoformat(),
        "penalty": str(req.daily_penalty_percent),
        "terms": summary,
    }
    doc_hash = crypto.chain_hash(prev_hash, canonical)
    seal = crypto.sign_seal(doc_hash)

    agreement = TilxatAgreement(
        user_id=user.id,
        doc_type=req.doc_type,
        party_a_name=req.party_a_name,
        party_a_passport_enc=crypto.encrypt_field(req.party_a_passport),
        party_a_tg_id=user.telegram_id,
        party_a_signed_at=utcnow(),
        party_b_name=req.party_b_name,
        party_b_passport_enc=crypto.encrypt_field(req.party_b_passport),
        amount_uzs=req.amount_uzs,
        bhm_ratio=wf["ratio"],
        requires_written=wf["mandatory_written"],
        threshold_snapshot={
            "thresholdBhm": str(wf["threshold_bhm"]),
            "thresholdUzs": str(wf["threshold_uzs"]),
            "constantsVersion": wf["constants_version"],
            "needsReview": wf["needs_review"],
            "legalRefs": wf["legal_refs"],
        },
        due_date=req.due_date,
        daily_penalty_percent=req.daily_penalty_percent,
        terms_summary=summary,
        sign_token=secrets.token_urlsafe(24),
        sign_token_expires_at=utcnow() + timedelta(days=7),
        chain_prev_hash=prev_hash,
        doc_hash=doc_hash,
        seal_signature=seal,
        status="pending_counterparty",
        locale_used=req.locale,
    )
    db.add(agreement)
    await db.flush()
    await write_audit_log(db, actor=user.id, action="create_tilxat", entity="tilxat", entity_id=agreement.id, request=request)
    await db.commit()
    await db.refresh(agreement)
    return _tilxat_dto(agreement)


@router.get("/api/tilxat")
async def list_tilxats(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    res = await db.execute(
        select(TilxatAgreement)
        .where(TilxatAgreement.user_id == user.id, TilxatAgreement.deleted_at.is_(None))
        .order_by(desc(TilxatAgreement.created_at))
        .limit(30)
    )
    return [_tilxat_dto(t) for t in res.scalars().all()]


@router.get("/api/tilxat/public/{token}")
async def get_public_tilxat(token: str, db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    res = await db.execute(select(TilxatAgreement).where(TilxatAgreement.sign_token == token))
    t = res.scalar_one_or_none()
    if t is None:
        raise HTTPException(status_code=404, detail="Signing link not found.")
    if t.status == "revoked":
        raise HTTPException(status_code=410, detail="Agreement was revoked by creator.")
    return _tilxat_dto(t, public_view=True)


@router.post("/api/tilxat/public/{token}/sign")
async def sign_public_tilxat(
    token: str,
    req: TilxatPublicSignRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    cfg = get_settings()
    crypto = get_crypto()
    res = await db.execute(select(TilxatAgreement).where(TilxatAgreement.sign_token == token))
    t = res.scalar_one_or_none()
    if t is None:
        raise HTTPException(status_code=404, detail="Signing link not found.")
    if t.status == "revoked":
        raise HTTPException(status_code=410, detail="Agreement has been revoked.")
    if not req.agreed:
        raise HTTPException(status_code=400, detail="Explicit confirmation checkbox (agreed=true) is required.")

    signer_tg_id: int | None = None
    if req.init_data.strip():
        try:
            validated = validate_init_data(req.init_data, cfg.telegram_bot_token)
            signer_tg_id = int((validated.get("user") or {}).get("id", 0)) or None
        except TelegramAuthError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
    elif cfg.demo_mode:
        signer_tg_id = 888000222
    else:
        raise HTTPException(status_code=401, detail="Telegram initData confirmation required.")

    if req.signer_name:
        t.party_b_name = req.signer_name.strip()[:180]
    if req.signer_passport:
        t.party_b_passport_enc = crypto.encrypt_field(req.signer_passport)

    t.party_b_tg_id = signer_tg_id
    t.party_b_signed_at = utcnow()
    t.status = "signed"

    # Re-seal canonical hash including both signatures
    signed_payload = {
        "id": t.id,
        "prevHash": t.doc_hash,
        "partyATg": t.party_a_tg_id,
        "partyBTg": t.party_b_tg_id,
        "signedAt": t.party_b_signed_at.isoformat(),
        "amountUzs": str(t.amount_uzs),
    }
    t.chain_prev_hash = t.doc_hash
    t.doc_hash = crypto.chain_hash(t.chain_prev_hash, signed_payload)
    t.seal_signature = crypto.sign_seal(t.doc_hash)

    pdf_file = _render_tilxat_pdf(t)
    t.pdf_path = str(pdf_file)

    await write_audit_log(db, actor=str(signer_tg_id or "counterparty"), action="sign_tilxat", entity="tilxat", entity_id=t.id, request=request)
    await db.commit()
    await db.refresh(t)

    dto = _tilxat_dto(t, public_view=False)
    await tilxat_ws_hub.broadcast(t.id, {"event": "signed", "tilxat": dto})
    return dto


@router.post("/api/tilxat/{tilxat_id}/revoke")
async def revoke_tilxat(
    tilxat_id: str,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    t = await db.get(TilxatAgreement, tilxat_id)
    if t is None or t.user_id != user.id:
        raise HTTPException(status_code=404, detail="Tilxat not found.")
    if t.status == "signed":
        raise HTTPException(status_code=409, detail="Already signed agreement cannot be revoked.")
    t.status = "revoked"
    await write_audit_log(db, actor=user.id, action="revoke_tilxat", entity="tilxat", entity_id=t.id, request=request)
    await db.commit()
    await tilxat_ws_hub.broadcast(t.id, {"event": "revoked", "status": "revoked"})
    return _tilxat_dto(t)


@router.get("/api/tilxat/{tilxat_id}/pdf")
async def download_tilxat_pdf(
    tilxat_id: str,
    locale: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
) -> FileResponse:
    t = await db.get(TilxatAgreement, tilxat_id)
    if t is None:
        raise HTTPException(status_code=404, detail="Tilxat not found.")
    path = _render_tilxat_pdf(t, locale=locale) if locale else (Path(t.pdf_path) if t.pdf_path and Path(t.pdf_path).exists() else _render_tilxat_pdf(t))
    return FileResponse(path, media_type="application/pdf", filename=f"haqli-tilxat-{t.id[:8]}.pdf")


@router.websocket("/ws/tilxat/{tilxat_id}")
async def tilxat_ws(ws: WebSocket, tilxat_id: str) -> None:
    await tilxat_ws_hub.connect(tilxat_id, ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        tilxat_ws_hub.disconnect(tilxat_id, ws)
