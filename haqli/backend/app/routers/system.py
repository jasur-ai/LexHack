"""SSE Pipeline Stream (with 15s heartbeat & replay), Health/Readiness/Metrics, and Public Document Verify router."""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import PlainTextResponse, StreamingResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.engines.llm.provider import get_llm_gateway
from app.engines.pdf.generator import check_font_glyph_coverage
from app.engines.recognition.pipeline import ocr_backends_status
from app.engines.rules import load_constants
from app.routers.recognition import verify_document_record
from app.security.ratelimit import SlidingWindowRateLimiter
from app.services.jobs import sse_broker

router = APIRouter(tags=["system"])
_public_get_verify_limiter = SlidingWindowRateLimiter(max_requests=60, window_seconds=60)


@router.get("/api/stream/{job_id}")
async def stream_job_stages(job_id: str) -> StreamingResponse:
    async def gen():
        async for ev in sse_broker.subscribe(job_id, heartbeat_sec=15.0):
            if ev.get("_heartbeat"):
                yield ": heartbeat\n\n"
            else:
                yield f"data: {json.dumps(ev, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/api/verify/{doc_id}")
async def api_verify_document(
    doc_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    ip = request.client.host if request.client else "local"
    if not _public_get_verify_limiter.allow(ip):
        raise HTTPException(status_code=429, detail="Rate limit exceeded.")
    return await verify_document_record(db, doc_id=doc_id, public_viewer=True)


@router.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/readyz")
async def readyz(db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    db_ok = True
    try:
        await db.execute(text("SELECT 1"))
    except Exception:
        db_ok = False
    fonts = check_font_glyph_coverage()
    gw = get_llm_gateway()
    constants = load_constants()
    rec_engines = ocr_backends_status()
    return {
        "ready": db_ok,
        "database": "ok" if db_ok else "error",
        "fonts": fonts,
        "ocrBackends": rec_engines["ocr"],
        "sttBackends": rec_engines["stt"],
        "llmProvider": gw.name,
        "llmCircuit": gw.circuit_state,
        "constantsVersion": constants.version,
    }


@router.get("/metrics", response_class=PlainTextResponse)
async def prometheus_metrics() -> str:
    gw = get_llm_gateway()
    circuit_val = 1 if gw.circuit_state == "open" else 0
    return (
        "# HELP haqli_up Service liveness\n"
        "# TYPE haqli_up gauge\n"
        "haqli_up 1\n"
        "# HELP haqli_llm_circuit_open 1 if LLM circuit breaker is open\n"
        "# TYPE haqli_llm_circuit_open gauge\n"
        f"haqli_llm_circuit_open {circuit_val}\n"
    )
