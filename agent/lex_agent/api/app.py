"""Production FastAPI server exposing all Lex.uz Legal AI Agent capabilities and Web UI."""

from __future__ import annotations

import json
import logging
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, Response, StreamingResponse
from openai import AuthenticationError
from pydantic import BaseModel, Field

from lex_agent import __version__
from lex_agent.capabilities.document_analyzer import extract_text_from_uploaded_bytes
from lex_agent.models import (
    AgentQueryRequest,
    AgentResponse,
    DocumentAuditRequest,
    DocumentAuditResponse,
    Language,
    RetrievalFilter,
    TemporalLookupRequest,
    TemporalLookupResponse,
    TranslationCompareRequest,
    TranslationCompareResponse,
)
from lex_agent.runtime import AgentRuntime

logger = logging.getLogger(__name__)
_STATIC_DIR = Path(__file__).resolve().parent / "static"


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1)
    top_k: int = Field(default=10, ge=1, le=50)
    filters: RetrievalFilter | None = None
    enable_live_lex: bool = True


class IngestLexDocRequest(BaseModel):
    doc_id: str
    fetch_all_languages: bool = True
    language: Language = Language.UZ_LATN


class IngestLexSearchRequest(BaseModel):
    query: str
    language: Language = Language.UZ_LATN
    limit: int = Field(default=5, ge=1, le=25)
    fetch_all_languages: bool = False


class IngestHFRequest(BaseModel):
    dataset_name: str = "Alii2004/lexuz-legislation"
    split: str = "train"
    max_docs: int | None = Field(default=500, ge=1)


class IngestUrlRequest(BaseModel):
    url: str = Field(..., min_length=8)


def create_app() -> FastAPI:
    runtime_holder: dict[str, AgentRuntime] = {}

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        rt = AgentRuntime.build()
        runtime_holder["rt"] = rt
        logging.basicConfig(level=getattr(logging, rt.settings.log_level.upper(), logging.INFO))
        # Pre-warm fast SQLite FTS5 BM25 index, seed foundational Uzbekistan Codes pack, and warm HTTP pool
        rt.bm25_store._ensure_fts_synced()
        rt.ingestion.seed_foundational_codes_fast()
        await rt.llm.warmup()
        logger.info(
            "Lex.uz Legal AI Agent v%s initialized (chunks=%d, qdrant_mode=%s, llm=%s)",
            __version__,
            rt.bm25_store.count(),
            rt.settings.qdrant_mode,
            rt.llm.active_mode_label,
        )
        try:
            yield
        finally:
            await rt.close()

    app = FastAPI(
        title="Lex.uz Legal AI Agent",
        version=__version__,
        description=(
            "Unrestricted, zero-hallucination Legal Knowledge & Reasoning Agent covering all legislation "
            "of the Republic of Uzbekistan across Uzbek (Latin & Cyrillic), Russian, and English."
        ),
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(AuthenticationError)
    async def handle_llm_auth_error(_request: Request, exc: AuthenticationError) -> JSONResponse:
        return JSONResponse(
            status_code=401,
            content={
                "detail": (
                    "LLM authentication failed (401 Unauthorized). "
                    "Set a valid `LLM_API_KEY` and `LLM_BASE_URL` in `agent/.env` "
                    "(OpenAI, Google Gemini OpenAI-compat, OpenRouter, or local Ollama), then restart the server."
                ),
                "provider_error": str(exc),
            },
        )

    @app.get("/favicon.ico", include_in_schema=False)
    async def favicon() -> Response:
        return Response(status_code=204)

    def get_rt() -> AgentRuntime:
        rt = runtime_holder.get("rt")
        if rt is None:
            rt = AgentRuntime.build()
            runtime_holder["rt"] = rt
        return rt

    def _fast_health_payload(rt: AgentRuntime) -> dict[str, Any]:
        """Instant (<2ms) health payload without forcing a slow local Qdrant disk scan."""
        bm25_count = rt.bm25_store.count()
        vec_count = (
            bm25_count
            if rt.settings.qdrant_mode == "local" and rt.vector_store._client is None
            else rt.vector_store.count()
        )
        return {
            "status": "ok",
            "version": __version__,
            "llm_mode": rt.llm.active_mode_label,
            "embedding_provider": rt.settings.embedding_provider,
            "qdrant_mode": rt.settings.qdrant_mode,
            "bm25_chunks": bm25_count,
            "vector_chunks": vec_count,
        }

    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    async def serve_ui() -> HTMLResponse:
        index_file = _STATIC_DIR / "index.html"
        if not index_file.exists():
            return HTMLResponse("<h1>Lex.uz Legal AI Agent API</h1><p>Open <a href='/docs'>/docs</a>.</p>")
        rt = get_rt()
        html = index_file.read_text(encoding="utf-8")
        initial_json = json.dumps(_fast_health_payload(rt), ensure_ascii=False)
        html = html.replace("__INITIAL_HEALTH_JSON__", initial_json)
        return HTMLResponse(html)

    @app.exception_handler(PermissionError)
    async def handle_vertex_auth_error(_request: Request, exc: PermissionError) -> JSONResponse:
        return JSONResponse(
            status_code=401,
            content={"detail": str(exc)},
        )

    @app.get("/api/health")
    async def health() -> dict[str, Any]:
        rt = get_rt()
        return _fast_health_payload(rt)

    @app.get("/api/stats")
    async def stats() -> dict[str, Any]:
        rt = get_rt()
        reg_stats = rt.ingestion.registry.stats()
        payload = _fast_health_payload(rt)
        reg_stats["bm25_chunks"] = payload["bm25_chunks"]
        reg_stats["vector_chunks"] = payload["vector_chunks"]
        return reg_stats

    @app.post("/api/ask", response_model=AgentResponse)
    async def ask_legal_question(req: AgentQueryRequest) -> AgentResponse:
        rt = get_rt()
        return await rt.orchestrator.answer(req)

    @app.post("/api/ask/stream")
    async def ask_legal_question_stream(req: AgentQueryRequest) -> StreamingResponse:
        """Server-Sent Events endpoint streaming live thinking steps, answer tokens, and verified citations."""
        rt = get_rt()

        async def event_gen():
            try:
                async for ev in rt.orchestrator.answer_stream(req):
                    if ev.get("type") == "done":
                        payload = {
                            "type": "done",
                            "elapsed_ms": ev.get("elapsed_ms", 0),
                            "response": ev["response"].model_dump(mode="json"),
                        }
                    else:
                        payload = ev
                    yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
            except (AuthenticationError, PermissionError) as exc:
                yield f"data: {json.dumps({'type': 'error', 'detail': str(exc)}, ensure_ascii=False)}\n\n"
            except Exception as exc:
                logger.exception("Error during streaming legal Q&A")
                msg = str(exc).strip() or f"{type(exc).__name__}: AI xizmati bilan ulanishda kechikish yuz berdi, iltimos qayta urinib ko'ring."
                yield f"data: {json.dumps({'type': 'error', 'detail': msg}, ensure_ascii=False)}\n\n"

        return StreamingResponse(
            event_gen(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    @app.post("/api/search")
    async def hybrid_search(req: SearchRequest) -> dict[str, Any]:
        rt = get_rt()
        hits, live_ids = await rt.retriever.retrieve(
            req.query,
            top_k=req.top_k,
            rerank_top_k=req.top_k,
            filters=req.filters,
            enable_live_fallback=req.enable_live_lex,
        )
        return {
            "query": req.query,
            "live_lex_fetched": live_ids,
            "count": len(hits),
            "results": [h.model_dump(mode="json") for h in hits],
        }

    @app.post("/api/audit", response_model=DocumentAuditResponse)
    async def audit_document(req: DocumentAuditRequest) -> DocumentAuditResponse:
        rt = get_rt()
        return await rt.document_analyzer.audit(req)

    @app.post("/api/audit/upload", response_model=DocumentAuditResponse)
    async def audit_uploaded_document(
        file: UploadFile = File(...),
        document_kind: str = Form("contract"),
        response_language: Language | None = Form(None),
        as_of_date: date | None = Form(None),
    ) -> DocumentAuditResponse:
        rt = get_rt()
        content = await file.read()
        try:
            text = extract_text_from_uploaded_bytes(file.filename or "upload.txt", content)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if len(text.strip()) < 20:
            raise HTTPException(status_code=400, detail="Extracted document text is too short to audit.")
        req = DocumentAuditRequest(
            document_text=text,
            document_kind=document_kind,
            response_language=response_language,
            as_of_date=as_of_date,
        )
        return await rt.document_analyzer.audit(req)

    @app.post("/api/translate", response_model=TranslationCompareResponse)
    async def translate_and_compare(req: TranslationCompareRequest) -> TranslationCompareResponse:
        rt = get_rt()
        try:
            return await rt.comparator.translate_and_compare(req)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/temporal", response_model=TemporalLookupResponse)
    async def temporal_lookup(req: TemporalLookupRequest) -> TemporalLookupResponse:
        rt = get_rt()
        return await rt.temporal_lookup.compare(req)

    @app.post("/api/ingest/lex-doc")
    async def ingest_lex_doc(req: IngestLexDocRequest) -> dict[str, Any]:
        rt = get_rt()
        return await rt.ingestion.ingest_lex_doc(
            req.doc_id,
            fetch_all_languages=req.fetch_all_languages,
            language=req.language,
        )

    @app.post("/api/ingest/lex-search")
    async def ingest_lex_search(req: IngestLexSearchRequest) -> dict[str, Any]:
        rt = get_rt()
        return await rt.ingestion.ingest_lex_search(
            req.query,
            language=req.language,
            limit=req.limit,
            fetch_all_languages=req.fetch_all_languages,
        )

    @app.post("/api/ingest/bootstrap-core")
    async def ingest_bootstrap_core(fetch_all_languages: bool = True) -> dict[str, Any]:
        rt = get_rt()
        return await rt.ingestion.bootstrap_core_codes(fetch_all_languages=fetch_all_languages)

    @app.post("/api/ingest/huggingface")
    async def ingest_huggingface(req: IngestHFRequest) -> dict[str, Any]:
        rt = get_rt()
        try:
            return await rt.ingestion.ingest_huggingface_corpus(
                dataset_name=req.dataset_name,
                split=req.split,
                max_docs=req.max_docs,
            )
        except RuntimeError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/ingest/url")
    async def ingest_external_url(req: IngestUrlRequest) -> dict[str, Any]:
        """Ingest legal documents or commentaries from sud.uz, ksu.uz, adliya.uz, soliq.uz, norma.uz, etc."""
        rt = get_rt()
        try:
            return await rt.ingestion.ingest_external_url(req.url)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/ingest/upload")
    async def ingest_uploaded_knowledge(
        file: UploadFile = File(...),
        title: str | None = Form(None),
    ) -> dict[str, Any]:
        """Upload a Code PDF, Supreme Court Plenum DOCX, or legal textbook TXT directly into the knowledge base."""
        rt = get_rt()
        content = await file.read()
        try:
            return await rt.ingestion.ingest_uploaded_file(file.filename or "legal_doc.txt", content, title=title)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    return app


app = create_app()
