"""Constant-time Telegram WebApp initData HMAC-SHA256 validation with auth_date freshness (<= 1h)."""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from typing import Any
from urllib.parse import parse_qsl


class TelegramAuthError(ValueError):
    """Raised when Telegram initData signature or freshness validation fails."""


def validate_init_data(
    init_data: str,
    bot_token: str,
    *,
    max_age_seconds: int = 3600,
    now_ts: int | None = None,
) -> dict[str, Any]:
    """Validate Telegram Mini App `initData` query string per official Telegram WebApp spec."""
    if not init_data or not init_data.strip():
        raise TelegramAuthError("Missing Telegram initData.")
    if not bot_token:
        raise TelegramAuthError("TELEGRAM_BOT_TOKEN is not configured.")

    pairs = parse_qsl(init_data, keep_blank_values=True)
    data = dict(pairs)
    received_hash = data.pop("hash", None)
    if not received_hash:
        raise TelegramAuthError("Missing hash in initData.")

    auth_date_raw = data.get("auth_date")
    if not auth_date_raw or not auth_date_raw.isdigit():
        raise TelegramAuthError("Missing or invalid auth_date.")

    current = int(time.time()) if now_ts is None else now_ts
    auth_date = int(auth_date_raw)
    if current - auth_date > max_age_seconds or auth_date - current > 120:
        raise TelegramAuthError("Stale or invalid auth_date (> 1h).")

    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(data.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256).digest()
    expected_hash = hmac.new(secret_key, data_check_string.encode("utf-8"), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected_hash, received_hash):
        raise TelegramAuthError("Invalid Telegram initData HMAC signature.")

    user_raw = data.get("user")
    user_obj = json.loads(user_raw) if user_raw else {}
    return {
        "auth_date": auth_date,
        "query_id": data.get("query_id"),
        "start_param": data.get("start_param"),
        "user": user_obj,
    }


def build_signed_init_data(user: dict[str, Any], bot_token: str, *, auth_date: int | None = None) -> str:
    """Helper for tests to generate a validly signed Telegram initData payload."""
    from urllib.parse import urlencode

    ts = int(time.time()) if auth_date is None else auth_date
    payload = {"auth_date": str(ts), "user": json.dumps(user, separators=(",", ":"))}
    data_check = "\n".join(f"{k}={v}" for k, v in sorted(payload.items()))
    secret = hmac.new(b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256).digest()
    sig = hmac.new(secret, data_check.encode("utf-8"), hashlib.sha256).hexdigest()
    payload["hash"] = sig
    return urlencode(payload)
