"""Auth, preferences, consent, and GDPR/Personal Data erasure router (§10)."""

from __future__ import annotations

import hashlib
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_db, utcnow
from app.engines.rules import load_constants
from app.models.entities import (
    ConsentRecord,
    ContractAudit,
    DisputeCase,
    RecognitionJob,
    TilxatAgreement,
    UploadedFile,
    User,
)
from app.routers.deps import get_current_user, write_audit_log
from app.schemas.api import ConsentRequest, PreferencesPatch, TelegramAuthRequest
from app.security.jwt import create_access_token
from app.security.telegram_auth import TelegramAuthError, validate_init_data

router = APIRouter(prefix="/api/auth", tags=["auth"])


def guest_telegram_id(device_id: str) -> int:
    digest = hashlib.sha256(f"haqli-guest:{device_id}".encode()).hexdigest()
    return -(int(digest[:15], 16) + 1)


def _user_dto(u: User) -> dict[str, Any]:
    return {
        "id": u.id,
        "telegramId": u.telegram_id,
        "fullName": u.full_name,
        "username": u.username,
        "role": u.role,
        "licenseNumber": u.license_number,
        "language": u.language,
        "themePref": u.theme_pref,
        "profileTags": u.profile_tags or [],
        "pushEnabled": u.push_enabled,
        "consentVersion": u.consent_version,
        "isGuest": u.telegram_id < 0,
    }


@router.post("/telegram")
async def auth_telegram(
    req: TelegramAuthRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    cfg = get_settings()
    constants = load_constants()

    if req.init_data.strip():
        try:
            validated = validate_init_data(req.init_data, cfg.telegram_bot_token)
        except TelegramAuthError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        tg_user = validated.get("user") or {}
        tg_id = int(tg_user.get("id", 0))
        if tg_id <= 0:
            raise HTTPException(status_code=401, detail="Invalid Telegram user in initData.")
        full_name = " ".join(p for p in (tg_user.get("first_name"), tg_user.get("last_name")) if p) or "Fuqaro"
        username = tg_user.get("username")
        raw_lang = str(tg_user.get("language_code") or "uz").lower()
        lang = "ru" if raw_lang.startswith("ru") else "uz_lat"
    elif req.device_id and (cfg.allow_web_guests or cfg.demo_mode):
        # Private guest account per browser; negative ids never collide with real Telegram users.
        tg_id = guest_telegram_id(req.device_id)
        full_name = (req.demo_name or "").strip()[:120] or "Azizbek Karimov"
        username = "demo_fuqaro"
        lang = "uz_lat"
    elif cfg.demo_mode:
        tg_id = 999000111
        full_name = req.demo_name or "Azizbek Karimov"
        username = "demo_citizen"
        lang = "uz_lat"
    else:
        raise HTTPException(status_code=401, detail="Telegram initData or a device id is required.")

    res = await db.execute(select(User).where(User.telegram_id == tg_id))
    user = res.scalar_one_or_none()
    if user is None:
        user = User(
            telegram_id=tg_id,
            full_name=full_name,
            username=username,
            language=lang,
            profile_tags=["xodim", "istemolchi"],
        )
        db.add(user)
    else:
        user.deleted_at = None
        user.last_seen_at = utcnow()
        if full_name and not user.full_name:
            user.full_name = full_name

    await db.flush()
    await write_audit_log(db, actor=user.id, action="auth_telegram", entity="user", entity_id=user.id, request=request)
    await db.commit()

    token = create_access_token(
        user_id=user.id,
        telegram_id=user.telegram_id,
        role=user.role,
        secret=cfg.jwt_secret,
        ttl_minutes=cfg.jwt_ttl_minutes,
    )
    bhm = constants.get("bhm_uzs")
    return {
        "accessToken": token,
        "user": _user_dto(user),
        "demoMode": cfg.demo_mode,
        "constants": {
            "bhm": str(bhm.value),
            "bhmStatus": bhm.status,
            "version": constants.version,
            "talabnomaPriceUzs": str(constants.val("pricing.talabnoma_uzs")),
        },
    }


@router.patch("/preferences")
async def update_preferences(
    req: PreferencesPatch,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    cfg = get_settings()
    if req.full_name is not None and req.full_name.strip():
        user.full_name = req.full_name.strip()[:120]
    if req.language is not None:
        user.language = req.language
    if req.theme_pref is not None:
        user.theme_pref = req.theme_pref
    if req.profile_tags is not None:
        user.profile_tags = req.profile_tags
    if req.push_enabled is not None:
        user.push_enabled = req.push_enabled
    if req.license_number is not None:
        user.license_number = req.license_number.strip()[:80]
    if req.role is not None:
        if req.role == "advocate" and user.role != "advocate":
            code = (req.invite_code or "").strip().upper()
            if code not in cfg.advocate_codes_set:
                raise HTTPException(
                    status_code=403,
                    detail="Advokat rejimiga o'tish uchun yaroqli taklif kodi (invite code) talab qilinadi.",
                )
        user.role = req.role

    await write_audit_log(db, actor=user.id, action="update_preferences", entity="user", entity_id=user.id, request=request)
    await db.commit()

    new_token = create_access_token(
        user_id=user.id,
        telegram_id=user.telegram_id,
        role=user.role,
        secret=cfg.jwt_secret,
        ttl_minutes=cfg.jwt_ttl_minutes,
    )
    return {"user": _user_dto(user), "accessToken": new_token}


@router.post("/consent")
async def grant_consent(
    req: ConsentRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    user.consent_version = req.version
    user.consent_at = utcnow()
    db.add(ConsentRecord(user_id=user.id, version=req.version, scope=req.scope))
    await write_audit_log(db, actor=user.id, action="grant_consent", entity="user", entity_id=user.id, request=request)
    await db.commit()
    return {"ok": True, "consentVersion": req.version}


@router.delete("/me")
async def delete_my_data(
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Erase all user personal records and queue stored files for immediate removal (§11)."""
    uid = user.id
    await db.execute(delete(RecognitionJob).where(RecognitionJob.user_id == uid))
    await db.execute(delete(ContractAudit).where(ContractAudit.user_id == uid))
    await db.execute(delete(TilxatAgreement).where(TilxatAgreement.user_id == uid))
    await db.execute(delete(DisputeCase).where(DisputeCase.user_id == uid))
    await db.execute(delete(UploadedFile).where(UploadedFile.owner_id == uid))
    user.deleted_at = utcnow()
    await write_audit_log(db, actor=uid, action="erase_user_data", entity="user", entity_id=uid, request=request)
    await db.commit()
    return {"deleted": True}
