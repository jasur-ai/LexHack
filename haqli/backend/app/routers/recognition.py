"""Recognition Engine v1.0 Router (§9): 202 async jobs, 200 inline memory-only MRZ, confirm gate, purge & verify."""

from __future__ import annotations

import asyncio
import hashlib
import io
import json
from collections import defaultdict
from datetime import timedelta
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse
from pypdf import PdfReader
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_db, get_session_factory, utcnow, uuid7_str
from app.engines.recognition.pipeline import run_recognition_pipeline
from app.engines.recognition.purge import purge_job_immediately
from app.engines.recognition.types import (
    ConfirmJobRequest,
    Field,
    Kind,
    RecognitionResult,
    RouteHint,
    StageEvent,
)
from app.engines.recognition.verify import verify_document_authenticity
from app.models.entities import RecognitionJob, UploadedFile, User
from app.routers.deps import get_current_user, write_audit_log
from app.security.crypto import get_crypto
from app.security.ratelimit import (
    ALLOWED_UPLOAD_MIMES,
    AUDIO_MIMES,
    IMAGE_MIMES,
    SlidingWindowRateLimiter,
    sniff_magic_mime,
    strip_image_exif,
    validate_image_dimensions,
)
from app.services.jobs import sse_broker

router = APIRouter(prefix="/api/recognition", tags=["recognition"])

_user_hourly_limiter = SlidingWindowRateLimiter(max_requests=20, window_seconds=3600)
_public_verify_limiter = SlidingWindowRateLimiter(max_requests=60, window_seconds=60)
_user_active_jobs: dict[str, int] = defaultdict(int)
_background_tasks: set[asyncio.Task[Any]] = set()


def _serialize_job_for_client(job: RecognitionJob) -> dict[str, Any]:
    crypto = get_crypto()
    result_dict: dict[str, Any] = {}
    if job.result_enc:
        try:
            result_dict = json.loads(crypto.decrypt_field(job.result_enc) or "{}")
        except Exception:
            result_dict = {}
    elif job.parsed:
        result_dict = job.parsed

    return {
        "jobId": job.id,
        "kind": job.kind,
        "status": job.status,
        "confirmed": job.confirmed,
        "confidence": job.confidence,
        "stages": job.stages or [],
        "result": result_dict,
        "expiresAt": job.expires_at.isoformat(),
    }


async def _execute_async_job(
    *,
    job_id: str,
    user_id: str,
    kind: Kind,
    file_bytes: bytes,
    mime: str,
    text_input: str,
    lang_hint: str | None,
    timezone_name: str,
    file_id: str | None,
) -> None:
    crypto = get_crypto()
    try:
        async def _emit(ev: StageEvent) -> None:
            await sse_broker.publish(
                job_id,
                ev.model_dump(by_alias=True, mode="json"),
                done=(ev.stage == "done"),
            )

        result, stages, raw_text = await run_recognition_pipeline(
            job_id=job_id,
            kind=kind,
            file_bytes=file_bytes,
            mime=mime,
            text_input=text_input,
            lang_hint=lang_hint,
            timezone_name=timezone_name,
            file_id=file_id,
            emit_stage=_emit,
        )

        confs = [f.confidence for f in result.fields]
        overall_conf = round(sum(confs) / len(confs), 2) if confs else (result.doc_type_confidence or 0.0)
        res_json = result.model_dump(by_alias=True, mode="json")

        async with get_session_factory()() as db:
            job = await db.get(RecognitionJob, job_id)
            if job is not None:
                job.status = "done" if (result.fields or result.clauses or result.raw_text_preview) else "failed"
                job.stages = [s.model_dump(by_alias=True, mode="json") for s in stages]
                job.confidence = overall_conf
                job.raw_text_enc = crypto.encrypt_field(raw_text) if raw_text else None
                job.result_enc = crypto.encrypt_field(json.dumps(res_json, ensure_ascii=False))
                job.parsed = {
                    "docType": result.doc_type,
                    "docTypeConfidence": result.doc_type_confidence,
                    "warnings": result.warnings,
                    "engine": result.engine,
                }
                await db.commit()
    finally:
        _user_active_jobs[user_id] = max(0, _user_active_jobs[user_id] - 1)


@router.post("/jobs")
async def create_recognition_job(
    request: Request,
    kind: Kind = Form("document"),
    text_input: str = Form(""),
    text: str = Form(""),
    lang_hint: str | None = Form(default=None),
    timezone: str = Form("Asia/Tashkent"),
    file: UploadFile | None = File(default=None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    cfg = get_settings()

    # Rate limits (§9): 20 jobs/hour/user, 5 concurrent per user
    if not _user_hourly_limiter.allow(user.id):
        raise HTTPException(status_code=429, detail="Recognition hourly quota (20 jobs/hour) exceeded.")
    if _user_active_jobs[user.id] >= cfg.recognition_user_max_concurrent:
        raise HTTPException(status_code=429, detail="Maximum 5 concurrent recognition jobs exceeded.")

    combined_text = (text_input or text or "").strip()
    raw_bytes = b""
    mime = "text/plain"
    file_id: str | None = None

    if file is not None:
        raw_bytes = await file.read()
        mime = sniff_magic_mime(raw_bytes, file.filename or "")
        if mime not in ALLOWED_UPLOAD_MIMES:
            raise HTTPException(status_code=400, detail=f"Unsupported file type detected by magic bytes: {mime}")

        max_mb = cfg.max_audio_mb if mime in AUDIO_MIMES else cfg.max_upload_mb
        if len(raw_bytes) > max_mb * 1024 * 1024:
            raise HTTPException(status_code=413, detail=f"File exceeds {max_mb} MB limit.")

        if mime in IMAGE_MIMES:
            ok_dim, err_dim = validate_image_dimensions(raw_bytes, max_megapixels=cfg.max_image_megapixels)
            if not ok_dim:
                raise HTTPException(status_code=400, detail=err_dim or "Image dimensions exceed limit.")
            raw_bytes = strip_image_exif(raw_bytes, mime)

        if mime == "application/pdf":
            try:
                page_count = len(PdfReader(io.BytesIO(raw_bytes)).pages)
                if page_count > cfg.max_pdf_pages:
                    raise HTTPException(status_code=400, detail=f"PDF exceeds {cfg.max_pdf_pages} page limit.")
            except HTTPException:
                raise
            except Exception as exc:
                raise HTTPException(status_code=400, detail=f"Invalid PDF file: {exc}") from exc

        # §6.4 / §9 HARD RULE: NEVER write `id_mrz` image bytes to disk or create UploadedFile!
        if kind != "id_mrz":
            file_id = uuid7_str()
            dest = cfg.upload_dir / file_id
            dest.write_bytes(raw_bytes)
            db.add(
                UploadedFile(
                    id=file_id,
                    owner_id=user.id,
                    sha256=hashlib.sha256(raw_bytes).hexdigest(),
                    mime=mime,
                    size=len(raw_bytes),
                    path=str(dest),
                    purge_at=utcnow() + timedelta(hours=cfg.recognition_retention_hours),
                )
            )

    job_id = uuid7_str()

    # §9: `id_mrz` is processed inline in memory and returns HTTP 200 with final result (never stored on disk)
    if kind == "id_mrz":
        result, stages, _raw = await run_recognition_pipeline(
            job_id=job_id,
            kind="id_mrz",
            file_bytes=raw_bytes,
            mime=mime,
            text_input=combined_text,
            lang_hint=lang_hint,
            timezone_name=timezone,
        )
        await write_audit_log(
            db,
            actor=user.id,
            action="recognition_mrz_inline",
            entity="recognition_job",
            entity_id=job_id,
            meta={"fieldKeys": [f.key for f in result.fields], "warnings": result.warnings},
            request=request,
        )
        await db.commit()
        return JSONResponse(
            status_code=200,
            content={
                "jobId": job_id,
                "status": "done" if result.fields else "failed",
                "stages": [s.model_dump(by_alias=True, mode="json") for s in stages],
                "result": result.model_dump(by_alias=True, mode="json"),
            },
        )

    # Non-MRZ jobs: persist queued record, spawn async pipeline emitting SSE events, return HTTP 202 (§9)
    job = RecognitionJob(
        id=job_id,
        user_id=user.id,
        kind=kind,
        status="queued",
        stages=[],
        confidence=0.0,
        file_id=file_id,
        pii_redacted=True,
        expires_at=utcnow() + timedelta(hours=cfg.recognition_retention_hours),
    )
    db.add(job)
    await write_audit_log(
        db,
        actor=user.id,
        action="recognition_job_created",
        entity="recognition_job",
        entity_id=job_id,
        meta={"kind": kind, "mime": mime},
        request=request,
    )
    await db.commit()

    _user_active_jobs[user.id] += 1
    task = asyncio.create_task(
        _execute_async_job(
            job_id=job_id,
            user_id=user.id,
            kind=kind,
            file_bytes=raw_bytes,
            mime=mime,
            text_input=combined_text,
            lang_hint=lang_hint,
            timezone_name=timezone,
            file_id=file_id,
        )
    )
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)

    return JSONResponse(
        status_code=202,
        content={
            "jobId": job_id,
            "status": "queued",
            "streamUrl": f"/api/stream/{job_id}",
        },
    )


@router.get("/jobs/{job_id}")
async def get_recognition_job(
    job_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    job = await db.get(RecognitionJob, job_id)
    if job is None or job.user_id != user.id:
        raise HTTPException(status_code=404, detail="Recognition job not found.")
    return _serialize_job_for_client(job)


@router.post("/jobs/{job_id}/confirm")
async def confirm_recognition_job(
    job_id: str,
    req: ConfirmJobRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Validate user edits (`source="user"`, `confidence=1.0`), mark confirmed, and return final RouteHint (§9)."""
    crypto = get_crypto()
    job = await db.get(RecognitionJob, job_id)
    if job is None or job.user_id != user.id:
        raise HTTPException(status_code=404, detail="Recognition job not found.")

    raw_res = json.loads(crypto.decrypt_field(job.result_enc) or "{}") if job.result_enc else {}
    rec_res = RecognitionResult.model_validate(raw_res) if raw_res else RecognitionResult(job_id=job.id, kind=job.kind)  # type: ignore[arg-type]

    edits = {item.key: item.value for item in req.fields}
    updated_fields: list[Field] = []
    seen: set[str] = set()
    for f in rec_res.fields:
        seen.add(f.key)
        if f.key in edits:
            val = edits[f.key]
            updated_fields.append(
                Field(
                    key=f.key,
                    value=val,
                    display=str(val) if val is not None else "",
                    confidence=1.0,
                    source="user",
                    span=f.span,
                    bbox=f.bbox,
                    needs_confirm=False,
                )
            )
        else:
            updated_fields.append(f.model_copy(update={"needs_confirm": False}))

    for k, v in edits.items():
        if k not in seen:
            updated_fields.append(Field(key=k, value=v, display=str(v or ""), confidence=1.0, source="user", needs_confirm=False))

    rec_res.fields = updated_fields
    if req.doc_type is not None:
        rec_res.doc_type = req.doc_type

    route = rec_res.route_hint or RouteHint(target="himoya")
    for f in updated_fields:
        if f.value is not None:
            route.prefill[f.key] = str(f.value)
    rec_res.route_hint = route

    job.confirmed = True
    job.confidence = 1.0
    job.result_enc = crypto.encrypt_field(json.dumps(rec_res.model_dump(by_alias=True, mode="json"), ensure_ascii=False))
    await write_audit_log(
        db,
        actor=user.id,
        action="recognition_job_confirmed",
        entity="recognition_job",
        entity_id=job.id,
        meta={"confirmedKeys": [f.key for f in updated_fields]},
        request=request,
    )
    await db.commit()

    return {
        "jobId": job.id,
        "confirmed": True,
        "routeHint": route.model_dump(by_alias=True, mode="json"),
        "fields": [f.model_dump(by_alias=True, mode="json") for f in updated_fields],
    }


@router.delete("/jobs/{job_id}")
async def purge_recognition_job(
    job_id: str,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    job = await db.get(RecognitionJob, job_id)
    if job is None or job.user_id != user.id:
        raise HTTPException(status_code=404, detail="Recognition job not found.")
    await write_audit_log(db, actor=user.id, action="recognition_job_purged", entity="recognition_job", entity_id=job.id, request=request)
    return await purge_job_immediately(db, job)


async def verify_document_record(
    db: AsyncSession,
    *,
    doc_id: str | None = None,
    qr_payload: str | None = None,
    uploaded_pdf_bytes: bytes | None = None,
    public_viewer: bool = True,
) -> dict[str, Any]:
    res = await verify_document_authenticity(
        db,
        doc_id=doc_id,
        qr_payload=qr_payload,
        uploaded_pdf_bytes=uploaded_pdf_bytes,
        public_viewer=public_viewer,
    )
    return res.model_dump(by_alias=True, mode="json")


@router.post("/verify-document")
async def verify_document_endpoint(
    request: Request,
    doc_id: str | None = Form(default=None),
    qr_payload: str | None = Form(default=None),
    file: UploadFile | None = File(default=None),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    ip = request.client.host if request.client else "local"
    if not _public_verify_limiter.allow(ip):
        raise HTTPException(status_code=429, detail="Too many verification requests. Please retry shortly.")
    pdf_bytes = await file.read() if file is not None else None
    return await verify_document_record(
        db,
        doc_id=doc_id,
        qr_payload=qr_payload,
        uploaded_pdf_bytes=pdf_bytes,
        public_viewer=True,
    )
