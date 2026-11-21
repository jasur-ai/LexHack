"""FastAPI Control Center Backend for LEX AUDITOR // RED-TEAM & FACT-VERIFICATION ENGINE."""

from __future__ import annotations

import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, Response, StreamingResponse

from evaluator_agent import __version__
from evaluator_agent.audit_engine import RedTeamAuditEngine
from evaluator_agent.models import (
    AdversarialCategory,
    AuditLanguage,
    BatchAuditRequest,
    GenerateTrapRequest,
    SingleAuditRequest,
    TargetConfigUpdate,
)

logger = logging.getLogger(__name__)
_STATIC_DIR = Path(__file__).resolve().parent / "static"


def create_app() -> FastAPI:
    holder: dict[str, RedTeamAuditEngine] = {}

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        engine = RedTeamAuditEngine()
        holder["engine"] = engine
        logging.basicConfig(level=getattr(logging, engine.settings.log_level.upper(), logging.INFO))
        logger.info(
            "LEX AUDITOR v%s ready on :%d (Target=%s, AuditorLLM=%s)",
            __version__,
            engine.settings.api_port,
            engine.target.base_url,
            "active" if engine.llm.is_available else "deterministic-only",
        )
        try:
            yield
        finally:
            await engine.close()

    app = FastAPI(
        title="LEX AUDITOR // Red-Team & Fact-Verification Engine",
        version=__version__,
        description="Zero-Trust Adversarial Auditor for Uzbekistan Legislation AI Agents (Lex.uz UZ/RU/EN).",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    def get_engine() -> RedTeamAuditEngine:
        eng = holder.get("engine")
        if eng is None:
            eng = RedTeamAuditEngine()
            holder["engine"] = eng
        return eng

    @app.get("/favicon.ico", include_in_schema=False)
    async def favicon() -> Response:
        return Response(status_code=204)

    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    async def serve_dashboard() -> HTMLResponse:
        index_file = _STATIC_DIR / "index.html"
        if not index_file.exists():
            return HTMLResponse("<h1>LEX AUDITOR API</h1><p>Open <a href='/docs'>/docs</a>.</p>")
        return HTMLResponse(index_file.read_text(encoding="utf-8"))

    @app.get("/api/health")
    async def health() -> dict[str, Any]:
        eng = get_engine()
        target_status = await eng.target.check_health()
        return {
            "status": "ok",
            "version": __version__,
            "auditor_llm_active": eng.llm.is_available,
            "target_agent_url": eng.target.base_url,
            "target_agent_timeout": eng.target.timeout,
            "target_health": target_status,
            "golden_failures_count": len(eng.store.list_golden_failures()),
            "total_audits": len(eng.store.list_audits(limit=2000)),
        }

    @app.post("/api/config/target")
    async def update_target_config(cfg: TargetConfigUpdate) -> dict[str, Any]:
        eng = get_engine()
        eng.target.update_config(cfg.target_agent_url, cfg.target_agent_timeout)
        target_status = await eng.target.check_health()
        return {
            "target_agent_url": eng.target.base_url,
            "target_agent_timeout": eng.target.timeout,
            "target_health": target_status,
        }

    @app.get("/api/traps/bank")
    async def list_trap_bank(
        category: AdversarialCategory | None = None,
        language: AuditLanguage | None = None,
    ) -> list[dict[str, Any]]:
        eng = get_engine()
        traps = eng.traps.list_curated_traps(
            categories=[category] if category else None,
            languages=[language] if language else None,
        )
        return [t.model_dump(mode="json") for t in traps]

    @app.post("/api/traps/generate")
    async def generate_trap(req: GenerateTrapRequest) -> dict[str, Any]:
        eng = get_engine()
        trap = await eng.traps.generate_trap(
            category=req.category,
            language=req.language,
            legal_branch=req.legal_branch,
            use_llm=req.use_llm,
        )
        return trap.model_dump(mode="json")

    @app.post("/api/audit/single")
    async def run_single_audit(req: SingleAuditRequest) -> dict[str, Any]:
        eng = get_engine()
        record = await eng.audit_single(req)
        return record.model_dump(mode="json")

    @app.post("/api/audit/single/stream")
    async def run_single_audit_stream(req: SingleAuditRequest) -> StreamingResponse:
        eng = get_engine()

        async def gen():
            try:
                async for ev in eng.audit_single_stream(req):
                    yield f"data: {json.dumps(ev, ensure_ascii=False)}\n\n"
            except Exception as exc:
                logger.exception("Single audit stream error")
                yield f"data: {json.dumps({'type': 'error', 'detail': str(exc)}, ensure_ascii=False)}\n\n"

        return StreamingResponse(gen(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})

    @app.post("/api/audit/batch/stream")
    async def run_batch_audit_stream(req: BatchAuditRequest) -> StreamingResponse:
        eng = get_engine()

        async def gen():
            try:
                async for ev in eng.run_batch_stream(req):
                    yield f"data: {json.dumps(ev, ensure_ascii=False)}\n\n"
            except Exception as exc:
                logger.exception("Batch audit stream error")
                yield f"data: {json.dumps({'type': 'error', 'detail': str(exc)}, ensure_ascii=False)}\n\n"

        return StreamingResponse(gen(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})

    @app.post("/api/regression/run/stream")
    async def run_regression_stream() -> StreamingResponse:
        eng = get_engine()

        async def gen():
            try:
                async for ev in eng.run_regression_stream():
                    yield f"data: {json.dumps(ev, ensure_ascii=False)}\n\n"
            except Exception as exc:
                logger.exception("Regression stream error")
                yield f"data: {json.dumps({'type': 'error', 'detail': str(exc)}, ensure_ascii=False)}\n\n"

        return StreamingResponse(gen(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})

    @app.post("/api/audit/stop")
    async def stop_active_audit() -> dict[str, Any]:
        eng = get_engine()
        eng.request_stop()
        return {"status": "stop_requested"}

    @app.post("/api/audit/pause")
    async def pause_active_audit(paused: bool = True) -> dict[str, Any]:
        eng = get_engine()
        eng.request_pause(paused)
        return {"paused": paused}

    @app.get("/api/audits")
    async def list_audits(
        category: str | None = Query(None),
        error_code: str | None = Query(None),
        verdict: str | None = Query(None),
        language: str | None = Query(None),
        min_score: int | None = Query(None, ge=0, le=100),
        max_score: int | None = Query(None, ge=0, le=100),
        search: str | None = Query(None),
        limit: int = Query(150, ge=1, le=500),
    ) -> list[dict[str, Any]]:
        eng = get_engine()
        items = eng.store.list_audits(
            category=category,
            error_code=error_code,
            verdict=verdict,
            language=language,
            min_score=min_score,
            max_score=max_score,
            search=search,
            limit=limit,
        )
        return [r.model_dump(mode="json") for r in items]

    @app.get("/api/golden-failures")
    async def get_golden_failures() -> list[dict[str, Any]]:
        eng = get_engine()
        return eng.store.list_golden_failures()

    @app.get("/api/analytics")
    async def get_analytics() -> dict[str, Any]:
        eng = get_engine()
        return eng.store.compute_analytics().model_dump(mode="json")

    @app.get("/api/export/{fmt}")
    async def export_report(fmt: str) -> Response:
        if fmt.lower() not in ("json", "markdown", "md", "csv"):
            raise HTTPException(status_code=400, detail="Supported formats: json, markdown, csv")
        eng = get_engine()
        content, media_type, filename = eng.store.export_report("markdown" if fmt == "md" else fmt)
        return Response(
            content=content,
            media_type=media_type,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    return app


app = create_app()
