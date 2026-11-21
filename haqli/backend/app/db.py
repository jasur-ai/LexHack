"""Async SQLAlchemy 2.0 database engine, session factory, and UUIDv7 primary key generator."""

from __future__ import annotations

import os
import time
import uuid
from collections.abc import AsyncIterator
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def uuid7_str() -> str:
    """Generate an RFC 9562 time-ordered UUIDv7 string."""
    ts_ms = int(time.time() * 1000) & ((1 << 48) - 1)
    rand_bytes = os.urandom(10)
    rand_a = int.from_bytes(rand_bytes[:2], "big") & 0x0FFF
    rand_b = int.from_bytes(rand_bytes[2:], "big") & ((1 << 62) - 1)
    value = (ts_ms << 80) | (0x7 << 76) | (rand_a << 64) | (0x2 << 62) | rand_b
    return str(uuid.UUID(int=value))


class Base(DeclarativeBase):
    pass


_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        cfg = get_settings()
        cfg.ensure_dirs()
        _engine = create_async_engine(cfg.database_url, future=True, echo=False)
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            bind=get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _session_factory


def reset_engine_for_tests(database_url: str) -> None:
    """Rebind async engine to a fresh test database URL."""
    global _engine, _session_factory
    _engine = create_async_engine(database_url, future=True, echo=False)
    _session_factory = async_sessionmaker(bind=_engine, class_=AsyncSession, expire_on_commit=False)


async def init_db() -> None:
    import app.models.entities  # noqa: F401

    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db() -> AsyncIterator[AsyncSession]:
    factory = get_session_factory()
    async with factory() as session:
        yield session
