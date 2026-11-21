"""24-hour auto-purge task and immediate hard-delete helper for RecognitionJob & UploadedFile (§4.2, §11)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import utcnow
from app.models.entities import RecognitionJob, UploadedFile


def _unlink_safe(path_str: str | None) -> bool:
    if not path_str:
        return False
    try:
        p = Path(path_str)
        if p.exists() and p.is_file():
            p.unlink()
            return True
    except Exception:
        pass
    return False


async def purge_job_immediately(db: AsyncSession, job: RecognitionJob) -> dict[str, Any]:
    """Hard-delete a recognition job's uploaded file, encrypted raw text, and DB row (§4.2, §9)."""
    removed_file = False
    if job.file_id:
        uf = await db.get(UploadedFile, job.file_id)
        if uf is not None and uf.attached_case_id is None:
            removed_file = _unlink_safe(uf.path)
            await db.delete(uf)
    job.raw_text_enc = None
    job.result_enc = None
    await db.delete(job)
    await db.commit()
    return {"purged": True, "jobId": job.id, "fileRemoved": removed_file}


async def purge_expired_recognition_data(db: AsyncSession) -> dict[str, int]:
    """Delete expired RecognitionJob rows and unattached UploadedFile rows/files where expires_at/purge_at < now."""
    now = utcnow()
    jobs_res = await db.execute(select(RecognitionJob).where(RecognitionJob.expires_at < now))
    expired_jobs = list(jobs_res.scalars().all())

    files_res = await db.execute(
        select(UploadedFile).where(UploadedFile.purge_at < now, UploadedFile.attached_case_id.is_(None))
    )
    expired_files = list(files_res.scalars().all())

    files_removed = 0
    for uf in expired_files:
        if _unlink_safe(uf.path):
            files_removed += 1
        await db.delete(uf)

    for job in expired_jobs:
        await db.delete(job)

    await db.commit()
    return {
        "purgedJobs": len(expired_jobs),
        "purgedFiles": len(expired_files),
        "diskFilesUnlinked": files_removed,
    }
