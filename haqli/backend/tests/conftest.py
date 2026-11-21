"""Shared pytest fixtures for isolated async FastAPI & SQLite integration testing."""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from pathlib import Path
from urllib.parse import urlencode

import httpx
import pytest
import pytest_asyncio

from app.config import get_settings


def build_signed_init_data(
    *,
    bot_token: str,
    user_id: int = 555123456,
    first_name: str = "Sardor",
    last_name: str = "Alimov",
    username: str = "sardor_test",
    language_code: str = "uz",
    auth_date: int | None = None,
) -> str:
    """Create a cryptographically valid Telegram WebApp initData query string."""
    user_json = json.dumps(
        {
            "id": user_id,
            "first_name": first_name,
            "last_name": last_name,
            "username": username,
            "language_code": language_code,
        },
        separators=(",", ":"),
        ensure_ascii=False,
    )
    fields = {
        "auth_date": str(auth_date if auth_date is not None else int(time.time())),
        "query_id": "AAHdF6IQAAAAAN0XohDhrOrc",
        "user": user_json,
    }
    data_check_string = "\n".join(f"{k}={fields[k]}" for k in sorted(fields.keys()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256).digest()
    sig = hmac.new(secret_key, data_check_string.encode("utf-8"), hashlib.sha256).hexdigest()
    fields["hash"] = sig
    return urlencode(fields)


@pytest_asyncio.fixture
async def api_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Spin up an isolated Haqli FastAPI app backed by a fresh temporary SQLite database."""
    db_file = tmp_path / "test_haqli.db"
    storage_dir = tmp_path / "storage"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{db_file.as_posix()}")
    monkeypatch.setenv("STORAGE_DIR", str(storage_dir))
    monkeypatch.setenv("DEMO_MODE", "true")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123456:TEST_BOT_SECRET_TOKEN")
    monkeypatch.setenv("ADVOCATE_INVITE_CODES", "HAQLI-ADV-2026")
    monkeypatch.setenv("JWT_SECRET", "test-jwt-secret-key-for-haqli-2026-suite")

    get_settings.cache_clear()

    # Reset engine globals so tests bind to the temp SQLite file
    import app.db as db_mod
    import app.security.crypto as crypto_mod

    db_mod._engine = None
    db_mod._session_factory = None
    crypto_mod._crypto_instance = None

    from app.main import create_app

    app = create_app()
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            yield client

    if db_mod._engine is not None:
        await db_mod._engine.dispose()
    db_mod._engine = None
    db_mod._session_factory = None
    get_settings.cache_clear()
