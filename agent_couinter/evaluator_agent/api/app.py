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
from pydantic import BaseModel, Field

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

    @app.get("/sams", response_class=HTMLResponse, include_in_schema=False)
    async def serve_sams() -> HTMLResponse:
        index_file = _STATIC_DIR / "index.html"
        if index_file.exists():
            return HTMLResponse(index_file.read_text(encoding="utf-8"))
        return HTMLResponse("<h1>SAMS Studio</h1>")

    @app.get("/api/sams/crew")
    async def sams_crew_status() -> dict[str, Any]:
        import httpx

        eng = get_engine()
        agent_health = await eng.target.check_health()
        haqli_online = False
        haqli_info: dict[str, Any] = {}
        try:
            async with httpx.AsyncClient(timeout=1.8) as client:
                r = await client.get("http://localhost:8002/healthz")
                if r.status_code == 200:
                    haqli_online = True
                    haqli_info = r.json() if r.headers.get("content-type", "").startswith("application/json") else {"status": "ok"}
        except Exception:
            haqli_online = False

        kstats = eng.verifier.knowledge.stats()
        return {
            "studio": "LEXHACK SAMS // Huquqiy Agentlar Boshqaruv Tizimi",
            "crew": [
                {
                    "id": "haqli",
                    "name": "HAQLI (Asosiy Platforma)",
                    "role": "1-Bosqich · Tilxat, OCR & Shartnoma Skaneri",
                    "port": 8002,
                    "url": "http://localhost:8002",
                    "online": haqli_online,
                    "status_label": "Faol (:8002)" if haqli_online else "Avtonom Rejim",
                    "capabilities": ["Qarz Tilxati (FK 733-m)", "Pasport MRZ & OCR v1.0", "Shartnoma Xavf Skaneri", "Fuqaro Huquqiy Radari"],
                    "info": haqli_info,
                },
                {
                    "id": "agent",
                    "name": "LEGAL AGENT (Lex.uz RAG)",
                    "role": "2-Bosqich · Qonuniy Sintez & Kodekslar",
                    "port": 8000,
                    "url": eng.target.base_url,
                    "online": bool(agent_health.get("reachable")),
                    "status_label": "Faol (:8000)" if agent_health.get("reachable") else "Oltin Baza Sintez",
                    "capabilities": ["Lex.uz Hybrid BM25+Vector", "O'RQ-682 Kolliziya Yechimi", "Citation Guard", "Shartnoma & Da'vo Auditi"],
                    "info": agent_health,
                },
                {
                    "id": "counter",
                    "name": "COUNTER AGENT (Fakt-Auditor)",
                    "role": "3-Bosqich · 4-Tier Tekshiruv & Red-Team",
                    "port": 8001,
                    "url": "http://localhost:8001",
                    "online": True,
                    "status_label": "Faol (:8001)",
                    "capabilities": ["24 Huquqiy Tuzoq Banki", "4-Bosqichli Modda Tekshiruvi", "0-100 Ishonchlilik Bali", "Root-Cause Fix Plan"],
                    "total_audits": len(eng.store.list_audits(limit=2000)),
                },
                {
                    "id": "vault",
                    "name": "LEX.UZ KODEKSLAR SEYFI",
                    "role": "Oltin Baza · 26+ Kodeks & Konstitutsiya",
                    "port": 8001,
                    "url": "http://localhost:8001",
                    "online": True,
                    "status_label": f"{kstats.get('registered_statutes', 26)} Qonun · {kstats.get('total_verified_articles', 36)} Modda",
                    "capabilities": ["2023 Yangi Konstitutsiya", "26+ O'zbekiston Kodekslari", "Lex.uz Jonli O'qitish", "Oliy Sud Plenum Bazasi"],
                    "stats": kstats,
                },
            ],
        }

    @app.get("/api/health")
    async def health() -> dict[str, Any]:
        eng = get_engine()
        target_status = await eng.target.check_health()
        return {
            "status": "ok",
            "version": __version__,
            "auditor_llm_active": eng.llm.is_available,
            "auditor_llm_model": eng.settings.auditor_llm_model,
            "target_agent_url": eng.target.base_url,
            "target_agent_timeout": eng.target.timeout,
            "target_health": target_status,
            "golden_failures_count": len(eng.store.list_golden_failures()),
            "total_audits": len(eng.store.list_audits(limit=2000)),
            "knowledge_stats": eng.verifier.knowledge.stats(),
        }

    class TrainArticlePayload(BaseModel):
        code_name: str = Field(..., min_length=2)
        doc_id: str = Field(..., min_length=1)
        doc_number: str = ""
        article: str = "1"
        status: str = "in_force"
        branch: str = "general"
        summary_uz: str = Field(..., min_length=10)
        summary_ru: str = ""
        bulk_mode: bool = False

    class TrainLexDocPayload(BaseModel):
        doc_id: str = Field(..., min_length=2)
        code_name: str = ""
        branch: str = "general"

    @app.get("/api/corpus/stats")
    async def corpus_stats() -> dict[str, Any]:
        eng = get_engine()
        return eng.verifier.knowledge.stats()

    @app.post("/api/corpus/train-auto")
    async def train_auto_from_local_corpus() -> dict[str, Any]:
        eng = get_engine()
        eng.verifier.knowledge._seed_builtin_knowledge()
        synced = eng.verifier.knowledge.sync_from_local_bm25_corpus(
            eng.settings.resolved_corpus_db_path, limit=20000
        )
        return {
            "synced_from_local_bm25": synced,
            "stats": eng.verifier.knowledge.stats(),
        }

    @app.get("/api/traps/random10")
    async def generate_random10_and_master_prompt() -> dict[str, Any]:
        import random
        from evaluator_agent.knowledge_base import UZBEKISTAN_STATUTE_REGISTRY

        eng = get_engine()
        all_traps = eng.traps.list_curated_traps()
        picked = random.sample(all_traps, min(10, len(all_traps)))

        statutes_sample = random.sample(
            [v for v in UZBEKISTAN_STATUTE_REGISTRY.values() if v.get("status") == "in_force"],
            min(10, len(UZBEKISTAN_STATUTE_REGISTRY)),
        )
        statutes_lines = "\n".join(
            f"  {i+1}. {s['title_uz']} (Lex.uz doc_id={s['doc_id']}, {s['doc_number']}, max modda={s['max_article']})"
            for i, s in enumerate(statutes_sample)
        )

        master_prompt = (
            "SEN O'ZBEKISTON RESPUBLIKASI QONUNCHILIGI (LEX.UZ) BO'YICHA SENIOR RED-TEAM HUQUQIY AUDITORISAN.\n"
            "Vazifang: Huquqiy AI Agentni (Legal Agent) eng qiyin, chalg'ituvchi va ko'p qatlamli huquqiy tuzoqlarda sinash uchun "
            "10 TA MURAKKAB TEST SAVOLI tuzib ber.\n\n"
            "QAT'IY TALABLAR:\n"
            "1. Savollar quyidagi O'zbekiston kodeks va qonunlarining aniq moddalari, qismlari (qism), bandlari (band) va darajali moddalarini (masalan: 47⁷-modda, 332¹-modda, 27¹-modda) qamrab olsin:\n"
            f"{statutes_lines}\n\n"
            "2. 10 ta savol quyidagi 7 ta Red-Team tuzoq toifasini o'z ichiga olsin:\n"
            "   - [1-2 savol] DIRECT_NORM_PRECISION: Aniq foizlar, muddatlar, MHTEKM vs BHM farqi (masalan: Oila kodeksi 99-modda 26.5% MHTEKM, MK 173-modda 50%..200% staj shkalasi, Soliq kodeksi QQS 12%, Advokatura 7-modda 15 kun).\n"
            "   - [3-4 savol] TEMPORAL_REPEAL_TRAP: Kuchini yo'qotgan 1995-yilgi Mehnat kodeksi modda raqamlari (100-modda vs yangi 161-modda, 134-modda 15 ish kuni vs yangi 217-modda 21 kalendar kun) yoki 1992 vs 2023 Konstitutsiya modda siljishi (25-modda vs 27-modda Habeas corpus 48 soat).\n"
            "   - [5-6 savol] FABRICATED_CITATION_TRAP (Gallyutsinatsiya tuzog'i): Kodeksning maksimal moddasidan katta bo'lgan soxta modda (masalan: JK 615-modda, Yer kodeksi 145-modda, Oila kodeksi 412-modda) yoki soxta PF-9999 / VMQ-8888 haqida savol.\n"
            "   - [7 savol] NORM_CONFLICT_HIERARCHY: O'RQ-682 18 va 41-moddalari bo'yicha Vazirlar Mahkamasi yangi qarori va Kodeks o'rtasidagi kolliziya (lex superior / lex specialis) hamda qonunning orqaga qaytish kuchi.\n"
            "   - [8 savol] CROSS_LINGUAL_DRIFT_TRAP: O'zbek lotin, o'zbek kirill va rus tili aralash yozilgan (code-switching / transliteratsiya xatoli) murakkab savol.\n"
            "   - [9-10 savol] COMPLEX_PRACTICAL_CASE: Bir nechta kodeks moddalari (FK 733/326 tilxat va penya, MK 129/130/165/405, MJtK 332-1 va 131-modda mast holda chegirma yo'qligi, O'RQ-931 manfaatlar to'qnashuvi 1 ish kuni) kesishgan amaliy kazus.\n\n"
            "3. Javobni FAQAT quyidagi JSON massiv formatida qaytar (boshqa izoh yozma):\n"
            "[\n"
            "  {\n"
            '    "question": "Savol matni (uz_latn / uz_cyrl / ru / en)",\n'
            '    "category": "DIRECT_NORM_PRECISION | TEMPORAL_REPEAL_TRAP | FABRICATED_CITATION_TRAP | NORM_CONFLICT_HIERARCHY | CROSS_LINGUAL_DRIFT_TRAP | MULTI_HOP_CHAIN | COMPLEX_PRACTICAL_CASE",\n'
            '    "language": "uz_latn",\n'
            '    "legal_branch": "labor | civil | family | tax | criminal | administrative | constitutional | land | procedural",\n'
            '    "is_false_premise": false,\n'
            '    "expected_articles": ["129", "130"],\n'
            '    "expected_key_facts": ["3 oy", "3 kun", "yozma"],\n'
            '    "forbidden_claims": ["oddiy xodimga 6 oy", "ogohlantirmasdan bo\'shatish"],\n'
            '    "gold_reference_summary": "To\'g\'ri qonuniy javob va aniq modda havolasi"\n'
            "  }\n"
            "]"
        )

        return {
            "master_prompt": master_prompt,
            "questions": [t.model_dump(mode="json") for t in picked],
        }

    @app.get("/api/corpus/search")
    async def search_corpus(
        q: str = Query(""),
        branch: str = Query(""),
        limit: int = Query(100, ge=1, le=300),
    ) -> list[dict[str, Any]]:
        eng = get_engine()
        return eng.verifier.knowledge.search_knowledge(query=q, branch=branch, limit=limit)

    @app.post("/api/corpus/train")
    async def train_corpus_article(payload: TrainArticlePayload) -> dict[str, Any]:
        eng = get_engine()
        if payload.bulk_mode:
            count = eng.verifier.knowledge.train_bulk_document_text(
                code_name=payload.code_name,
                doc_id=payload.doc_id,
                raw_text=payload.summary_uz,
                doc_number=payload.doc_number,
                status=payload.status,
                branch=payload.branch,
            )
            return {"trained_count": count, "stats": eng.verifier.knowledge.stats()}
        rec = eng.verifier.knowledge.train_article(
            code_name=payload.code_name,
            doc_id=payload.doc_id,
            article=payload.article,
            summary_uz=payload.summary_uz,
            summary_ru=payload.summary_ru,
            doc_number=payload.doc_number,
            status=payload.status,
            branch=payload.branch,
        )
        return {"trained_count": 1, "article": rec, "stats": eng.verifier.knowledge.stats()}

    @app.post("/api/corpus/train-lex")
    async def train_from_live_lex(payload: TrainLexDocPayload) -> dict[str, Any]:
        eng = get_engine()
        doc = await eng.verifier._fetch_live_lex_doc(payload.doc_id)
        if not doc or not doc.get("exists"):
            raise HTTPException(status_code=404, detail=f"Lex.uz hujjati ({payload.doc_id}) topilmadi.")
        title = payload.code_name.strip() or str(doc.get("doc_title") or f"Lex-{payload.doc_id}")
        count = eng.verifier.knowledge.train_bulk_document_text(
            code_name=title[:140],
            doc_id=str(doc.get("doc_id") or payload.doc_id),
            raw_text=str(doc.get("text") or ""),
            status=str(doc.get("status") or "in_force"),
            branch=payload.branch,
            url=str(doc.get("url") or f"https://lex.uz/uz/docs/{payload.doc_id}"),
            source="lex_uz_live_trained",
        )
        return {
            "trained_count": count,
            "doc_title": title,
            "status": doc.get("status"),
            "stats": eng.verifier.knowledge.stats(),
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
