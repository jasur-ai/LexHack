"""Telegram Bot API notification sender (graceful no-op when TELEGRAM_BOT_TOKEN is unset)."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)


async def send_telegram_message(
    telegram_id: int,
    text: str,
    *,
    web_app_url: str | None = None,
    button_text: str = "Haqli ochish",
) -> dict[str, Any]:
    cfg = get_settings()
    if not cfg.telegram_bot_token:
        logger.info("Simulated Telegram notification to %s: %s", telegram_id, text[:120])
        return {"sent": False, "simulated": True}

    payload: dict[str, Any] = {
        "chat_id": telegram_id,
        "text": text,
        "parse_mode": "HTML",
    }
    if web_app_url:
        payload["reply_markup"] = {
            "inline_keyboard": [[{"text": button_text, "web_app": {"url": web_app_url}}]]
        }

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.post(
                f"https://api.telegram.org/bot{cfg.telegram_bot_token}/sendMessage",
                json=payload,
            )
            return {"sent": resp.status_code == 200, "status": resp.status_code}
    except Exception as exc:
        logger.warning("Telegram sendMessage failed: %s", exc)
        return {"sent": False, "error": str(exc)}
