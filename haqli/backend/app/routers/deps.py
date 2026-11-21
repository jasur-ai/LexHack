"""Shared FastAPI dependencies: JWT authentication, user resolution, and audit logging."""

from __future__ import annotations

from typing import Any

from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_db, utcnow
from app.models.entities import AuditLog, User
from app.security.crypto import CryptoService
from app.security.jwt import JWTError, decode_access_token


async def get_current_user(
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> User:
    cfg = get_settings()
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
        try:
            payload = decode_access_token(token, cfg.jwt_secret)
        except JWTError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        user = await db.get(User, payload["sub"])
        if user is None or user.deleted_at is not None:
            raise HTTPException(status_code=401, detail="User not found or deleted.")
        user.last_seen_at = utcnow()
        return user

    # In DEMO_MODE allow transparent fallback to seeded demo citizen if no Bearer token sent
    if cfg.demo_mode:
        res = await db.execute(select(User).where(User.telegram_id == 999000111, User.deleted_at.is_(None)))
        demo = res.scalar_one_or_none()
        if demo is not None:
            return demo

    raise HTTPException(status_code=401, detail="Authentication required.")


async def require_advocate(user: User = Depends(get_current_user)) -> User:
    if user.role != "advocate":
        raise HTTPException(status_code=403, detail="Advocate role required.")
    return user


async def write_audit_log(
    db: AsyncSession,
    *,
    actor: str,
    action: str,
    entity: str,
    entity_id: str,
    meta: dict[str, Any] | None = None,
    request: Request | None = None,
) -> None:
    ip = request.client.host if (request and request.client) else "local"
    db.add(
        AuditLog(
            actor=actor,
            action=action,
            entity=entity,
            entity_id=entity_id,
            meta=meta or {},
            ip_hash=CryptoService.hash_ip(ip),
        )
    )
