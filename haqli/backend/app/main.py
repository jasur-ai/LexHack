"""Haqli v2.1 FastAPI Application Factory — lifespan migrate+seed+prewarm, Server-Timing, security headers, static SPA."""

from __future__ import annotations

import asyncio
import json
import time
from contextlib import asynccontextmanager
from pathlib import Path

import structlog
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app import __version__
from app.config import get_settings
from app.db import get_session_factory, init_db, uuid7_str
from app.engines.pdf.generator import check_font_glyph_coverage
from app.engines.recognition.pipeline import prewarm_recognition_engines
from app.engines.recognition.purge import purge_expired_recognition_data
from app.engines.retrieval import get_instrument_store
from app.engines.rules import load_constants
from app.routers import auth, disputes, recognition, scanner, system, tilxat
from app.routers.radar_mso import mso_router, radar_router
from app.security.ratelimit import SlidingWindowRateLimiter, problem_response
from app.seed import seed_demo_data

logger = structlog.get_logger()


def create_app() -> FastAPI:
    cfg = get_settings()
    rate_limiter = SlidingWindowRateLimiter(max_requests=200, window_seconds=60)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        cfg.ensure_dirs()
        await init_db()
        # Pre-warm legal constants, BM25 instruments, PDF Cyrillic fonts & recognition engines (§3, §12)
        load_constants()
        get_instrument_store()
        check_font_glyph_coverage()
        prewarm_recognition_engines()
        async with get_session_factory()() as db:
            await seed_demo_data(db)
            await purge_expired_recognition_data(db)

        async def _purge_loop() -> None:
            while True:
                await asyncio.sleep(3600)
                try:
                    async with get_session_factory()() as db:
                        await purge_expired_recognition_data(db)
                except Exception:
                    pass

        purge_task = asyncio.create_task(_purge_loop())
        logger.info("haqli_started", version=__version__, demo_mode=cfg.demo_mode)
        try:
            yield
        finally:
            purge_task.cancel()

    app = FastAPI(
        title="Haqli LegalTech API",
        version=__version__,
        description="Citizen-first Uzbekistan legal document & recognition platform (Telegram Mini App + FastAPI).",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cfg.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def observability_and_security_middleware(request: Request, call_next):
        req_id = request.headers.get("X-Request-Id") or uuid7_str()[:12]
        request.state.request_id = req_id
        ip = request.client.host if request.client else "local"

        if request.url.path.startswith("/api/") and not rate_limiter.allow(ip):
            return problem_response(
                status=429,
                title="Too Many Requests",
                detail="Rate limit exceeded. Please retry shortly.",
                code="RATE_LIMITED",
                request_id=req_id,
            )

        t0 = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = int((time.perf_counter() - t0) * 1000)

        # Inject processingTimeMs into JSON responses from /api/ (§2, §10)
        if (
            request.url.path.startswith("/api/")
            and response.headers.get("content-type", "").startswith("application/json")
            and hasattr(response, "body_iterator")
        ):
            body_chunks = [chunk async for chunk in response.body_iterator]
            raw_body = b"".join(body_chunks)
            try:
                parsed = json.loads(raw_body.decode("utf-8"))
                if isinstance(parsed, dict):
                    if "processingTimeMs" not in parsed:
                        parsed["processingTimeMs"] = elapsed_ms
                    if "processing_time_ms" not in parsed:
                        parsed["processing_time_ms"] = elapsed_ms
                    response = JSONResponse(content=parsed, status_code=response.status_code)
                else:
                    response = JSONResponse(content=parsed, status_code=response.status_code)
            except Exception:
                pass

        response.headers["X-Request-Id"] = req_id
        response.headers["Server-Timing"] = f"app;dur={elapsed_ms}"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response

    @app.exception_handler(HTTPException)
    async def http_exc_handler(request: Request, exc: HTTPException):
        return problem_response(
            status=exc.status_code,
            title="Request Error",
            detail=str(exc.detail),
            code=f"HTTP_{exc.status_code}",
            request_id=getattr(request.state, "request_id", ""),
        )

    app.include_router(auth.router)
    app.include_router(disputes.router)
    app.include_router(tilxat.router)
    app.include_router(scanner.router)
    app.include_router(recognition.router)
    app.include_router(radar_router)
    app.include_router(mso_router)
    app.include_router(system.router)

    # Serve built React SPA (`web/dist`) if present
    web_dist = Path(__file__).resolve().parent.parent.parent / "web" / "dist"
    if web_dist.exists():
        assets_dir = web_dist / "assets"
        if assets_dir.exists():
            app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

        @app.get("/{full_path:path}", include_in_schema=False)
        async def spa_fallback(full_path: str):
            candidate = web_dist / full_path
            if full_path and candidate.exists() and candidate.is_file():
                return FileResponse(candidate)
            return FileResponse(web_dist / "index.html")
    else:
        @app.get("/", response_class=HTMLResponse, include_in_schema=False)
        async def api_index() -> HTMLResponse:
            return HTMLResponse(
                "<h1>Haqli v2.1 API</h1>"
                "<p>OpenAPI docs: <a href='/docs'>/docs</a> · Readiness: <a href='/readyz'>/readyz</a></p>"
                "<p>Run frontend with <code>cd haqli/web && pnpm dev</code> (or build into <code>web/dist</code>).</p>"
            )

    return app


app = create_app()
