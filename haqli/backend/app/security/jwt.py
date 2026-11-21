"""Short-lived HS256 JWT access tokens bound to user_id and telegram_id."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from typing import Any


class JWTError(ValueError):
    """Raised when access token is malformed, invalid, or expired."""


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64url_decode(encoded: str) -> bytes:
    pad = "=" * ((4 - len(encoded) % 4) % 4)
    return base64.urlsafe_b64decode((encoded + pad).encode("ascii"))


def create_access_token(
    *,
    user_id: str,
    telegram_id: int,
    role: str,
    secret: str,
    ttl_minutes: int = 15,
) -> str:
    now = int(time.time())
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "sub": user_id,
        "tg": telegram_id,
        "role": role,
        "iat": now,
        "exp": now + ttl_minutes * 60,
    }
    h_b64 = _b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    p_b64 = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{h_b64}.{p_b64}".encode("ascii")
    sig = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
    return f"{h_b64}.{p_b64}.{_b64url_encode(sig)}"


def decode_access_token(token: str, secret: str) -> dict[str, Any]:
    parts = token.split(".")
    if len(parts) != 3:
        raise JWTError("Malformed token.")
    h_b64, p_b64, s_b64 = parts
    signing_input = f"{h_b64}.{p_b64}".encode("ascii")
    expected = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
    try:
        actual = _b64url_decode(s_b64)
        payload = json.loads(_b64url_decode(p_b64).decode("utf-8"))
    except Exception as exc:
        raise JWTError("Corrupted token payload.") from exc

    if not hmac.compare_digest(expected, actual):
        raise JWTError("Invalid token signature.")
    if int(payload.get("exp", 0)) < int(time.time()):
        raise JWTError("Access token expired.")
    return payload
