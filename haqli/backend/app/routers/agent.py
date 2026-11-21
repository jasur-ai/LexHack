"""AI-lawyer chat: authenticated, rate-limited streaming proxy to the Lex.uz legal agent (`agent/`).

The browser never talks to the agent directly. The agent can therefore run as a private service, and haqli stays
the single public origin, which keeps auth, rate limits and CORS in one place. When the agent is down, the stream
ends with a friendly ``error`` event (code ``agent_unavailable``) instead of a hanging request.
"""

from __future__ import annotations

import json
import time
from collections.abc import AsyncIterator
from typing import Any

import httpx
import structlog
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from app.config import get_settings
from app.models.entities import User
from app.routers.deps import get_current_user
from app.schemas.api import AgentAskRequest
from app.security.ratelimit import SlidingWindowRateLimiter

router = APIRouter(prefix="/api/agent", tags=["agent"])
logger = structlog.get_logger()

_LOCALE_TO_AGENT = {"uz_lat": "uz_latn", "uz_cyr": "uz_cyrl", "ru": "ru"}
_per_user_limiter: SlidingWindowRateLimiter | None = None
_sources_cache: dict[str, Any] = {"at": 0.0, "data": None}


def _limiter() -> SlidingWindowRateLimiter:
    global _per_user_limiter
    if _per_user_limiter is None:
        _per_user_limiter = SlidingWindowRateLimiter(
            max_requests=max(1, get_settings().agent_user_questions_per_hour), window_seconds=3600
        )
    return _per_user_limiter


def _agent_url(path: str) -> str:
    return f"{get_settings().agent_base_url.rstrip('/')}{path}"


def _sse(payload: dict[str, Any]) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


# Fields of the agent's final response that the chat screen renders. Everything else (query plan, hop traces,
# raw citations) stays server-side, which keeps the last event small on mobile connections.
_DONE_FIELDS = ("answer", "sections", "sources", "mode", "elapsed_ms", "response_language", "answer_style", "as_of_date")


def _slim_done(line: str) -> str | None:
    """Return a compact ``done`` event for an agent ``done`` line, or None when the line is something else."""
    raw = line[5:].strip()
    if '"done"' not in raw:
        return None
    try:
        event = json.loads(raw)
    except ValueError:
        return None
    if not isinstance(event, dict) or event.get("type") != "done":
        return None
    response = event.get("response") if isinstance(event.get("response"), dict) else {}
    verification = response.get("verification") if isinstance(response.get("verification"), dict) else {}
    slim: dict[str, Any] = {key: response[key] for key in _DONE_FIELDS if key in response}
    slim["verification"] = {
        "passed": bool(verification.get("passed", False)),
        "confidence_score": verification.get("confidence_score", 0.0),
        "warnings": list(verification.get("repealed_or_amended_warnings") or [])[:3],
    }
    return _sse({"type": "done", "elapsed_ms": event.get("elapsed_ms"), "response": slim})


@router.get("/status")
async def agent_status() -> dict[str, Any]:
    """Cheap availability probe used by the chat screen (never raises)."""
    t0 = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(3.0, connect=2.0)) as client:
            resp = await client.get(_agent_url("/api/health"))
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:  # noqa: BLE001 - any failure means "unavailable"
        return {"available": False, "reason": type(exc).__name__, "latencyMs": int((time.perf_counter() - t0) * 1000)}
    return {
        "available": bool(data.get("index_ready", True)),
        "answerMode": data.get("answer_mode", "llm"),
        "indexedChunks": data.get("bm25_chunks", 0),
        "version": data.get("version"),
        "latencyMs": int((time.perf_counter() - t0) * 1000),
    }


@router.get("/sources")
async def agent_sources() -> dict[str, Any]:
    """Knowledge sources behind the answers (cached for 10 minutes)."""
    now = time.monotonic()
    if _sources_cache["data"] is not None and now - _sources_cache["at"] < 600:
        return _sources_cache["data"]
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(5.0, connect=2.0)) as client:
            resp = await client.get(_agent_url("/api/sources"))
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail="AI yurist hozircha mavjud emas.") from exc
    payload = {"sources": data.get("sources", []), "totalChunks": data.get("total_chunks", 0)}
    _sources_cache.update(at=now, data=payload)
    return payload


async def _relay(req: AgentAskRequest, user_id: str) -> AsyncIterator[str]:
    cfg = get_settings()
    body: dict[str, Any] = {"query": req.query.strip(), "answer_style": req.answer_style}
    if req.locale:
        body["response_language"] = _LOCALE_TO_AGENT[req.locale]
    if req.context and req.context.strip():
        body["context"] = req.context.strip()
    t0 = time.perf_counter()
    got_done = False
    try:
        timeout = httpx.Timeout(cfg.agent_timeout_sec, connect=4.0, read=cfg.agent_timeout_sec)
        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream("POST", _agent_url("/api/ask/stream"), json=body) as resp:
                if resp.status_code >= 400:
                    detail = (await resp.aread()).decode("utf-8", "replace")[:300]
                    logger.warning("agent_http_error", status=resp.status_code, detail=detail)
                    yield _sse({"type": "error", "code": "agent_error", "detail": f"HTTP {resp.status_code}"})
                    return
                async for line in resp.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    done_event = _slim_done(line)
                    if done_event is not None:
                        got_done = True
                        yield done_event
                        continue
                    yield line + "\n\n"
    except (httpx.ConnectError, httpx.ConnectTimeout):
        yield _sse({"type": "error", "code": "agent_unavailable", "detail": "AI yurist hozircha ulanmagan."})
        return
    except httpx.TimeoutException:
        yield _sse({"type": "error", "code": "agent_timeout", "detail": "Javob juda uzoq kechikdi."})
        return
    except Exception as exc:  # noqa: BLE001
        logger.warning("agent_stream_failed", error=str(exc))
        yield _sse({"type": "error", "code": "agent_error", "detail": "AI yurist bilan aloqa uzildi."})
        return
    finally:
        logger.info(
            "agent_question",
            user=user_id,
            ms=int((time.perf_counter() - t0) * 1000),
            completed=got_done,
            chars=len(req.query),
        )
    if not got_done:
        yield _sse({"type": "error", "code": "agent_incomplete", "detail": "Javob to'liq kelmadi."})


@router.post("/ask/stream")
async def ask_agent_stream(req: AgentAskRequest, user: User = Depends(get_current_user)) -> StreamingResponse:
    if not _limiter().allow(user.id):
        raise HTTPException(status_code=429, detail="Savollar limiti tugadi. Birozdan keyin qayta urinib ko'ring.")
    return StreamingResponse(
        _relay(req, user.id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
