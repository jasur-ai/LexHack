"""API & security integration tests: 202/200 MRZ memory-only, confirm gate, purge, SSE replay, verify regenerated layout (§8-§12)."""

from __future__ import annotations

import asyncio
from datetime import timedelta
from pathlib import Path

import httpx
import pytest

from app.db import get_session_factory, utcnow
from app.engines.pdf.generator import render_haqli_pdf
from app.engines.recognition.eval.fixtures import make_td3
from app.engines.recognition.purge import purge_expired_recognition_data
from app.models.entities import RecognitionJob, TilxatAgreement, UploadedFile
from tests.conftest import build_signed_init_data


async def _auth_headers(client: httpx.AsyncClient, user_id: int, name: str) -> dict[str, str]:
    init_data = build_signed_init_data(bot_token="123456:TEST_BOT_SECRET_TOKEN", user_id=user_id, first_name=name)
    r = await client.post("/api/auth/telegram", json={"initData": init_data})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['accessToken']}"}


@pytest.mark.asyncio
async def test_mrz_inline_200_never_writes_file_to_disk(api_client: httpx.AsyncClient) -> None:
    headers = await _auth_headers(api_client, 100001, "MrzUser")
    mrz = make_td3("KARIMOV", "AZIZBEK", "AD7654321", "950412", "320412")

    resp = await api_client.post(
        "/api/recognition/jobs",
        headers=headers,
        data={"kind": "id_mrz", "text_input": mrz},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["result"]["docType"] == "passport_data_page"
    assert "<DOC_NUM_REDACTED>" in body["result"]["rawTextPreview"]
    assert "AD7654321" not in body["result"]["rawTextPreview"]

    # Confirm zero UploadedFile rows created for id_mrz
    async with get_session_factory()() as db:
        files = (await db.execute(UploadedFile.__table__.select())).fetchall()
        assert len(files) == 0


@pytest.mark.asyncio
async def test_async_job_202_sse_replay_confirm_ownership_and_purge(api_client: httpx.AsyncClient) -> None:
    h_owner = await _auth_headers(api_client, 100002, "Owner")
    h_other = await _auth_headers(api_client, 100003, "Intruder")

    # Reject bad magic bytes disguised as .jpg
    bad_magic = await api_client.post(
        "/api/recognition/jobs",
        headers=h_owner,
        data={"kind": "document"},
        files={"file": ("fake.jpg", b"NOT_A_REAL_JPEG_EXECUTABLE", "image/jpeg")},
    )
    assert bad_magic.status_code == 400

    # Valid text receipt job -> 202
    create = await api_client.post(
        "/api/recognition/jobs",
        headers=h_owner,
        data={
            "kind": "receipt",
            "text_input": "Texnomart MCHJ\nSTIR: 304567891\nSana: 18.03.2026\nJami: 4 200 000 so'm",
        },
    )
    assert create.status_code == 202
    job_id = create.json()["jobId"]

    # Wait briefly for background task completion
    detail_body = None
    for _ in range(25):
        g = await api_client.get(f"/api/recognition/jobs/{job_id}", headers=h_owner)
        assert g.status_code == 200
        if g.json()["status"] in ("done", "failed"):
            detail_body = g.json()
            break
        await asyncio.sleep(0.08)

    assert detail_body is not None
    assert detail_body["status"] == "done"
    assert len(detail_body["stages"]) >= 6

    # Ownership check: another user MUST get 404
    intruder_get = await api_client.get(f"/api/recognition/jobs/{job_id}", headers=h_other)
    assert intruder_get.status_code == 404

    # SSE replay returns persisted stages cleanly
    sse = await api_client.get(f"/api/stream/{job_id}")
    assert sse.status_code == 200
    assert '"stage": "done"' in sse.text or '"stage":"done"' in sse.text

    # Confirm edits -> source="user", confidence=1.0, confirmed=True
    conf = await api_client.post(
        f"/api/recognition/jobs/{job_id}/confirm",
        headers=h_owner,
        json={"fields": [{"key": "totalUzs", "value": "4200000.00"}], "docType": "receipt"},
    )
    assert conf.status_code == 200
    assert conf.json()["confirmed"] is True
    assert conf.json()["routeHint"]["target"] == "himoya"

    # Immediate purge via DELETE
    deleted = await api_client.delete(f"/api/recognition/jobs/{job_id}", headers=h_owner)
    assert deleted.status_code == 200
    assert deleted.json()["purged"] is True
    assert (await api_client.get(f"/api/recognition/jobs/{job_id}", headers=h_owner)).status_code == 404


@pytest.mark.asyncio
async def test_verify_valid_regenerated_layout_tampered_and_unknown(api_client: httpx.AsyncClient) -> None:
    headers = await _auth_headers(api_client, 100004, "VerifyUser")

    # Create & sign a Tilxat
    created = await api_client.post(
        "/api/tilxat",
        headers=headers,
        json={
            "docType": "loan",
            "partyAName": "Azizbek Karimov",
            "partyBName": "Javohir Alimov",
            "amountUzs": "8000000",
            "dueDate": "2026-09-01",
            "dailyPenaltyPercent": "0.1",
            "locale": "uz_lat",
        },
    )
    t = created.json()
    signed = await api_client.post(
        f"/api/tilxat/public/{t['signToken']}/sign",
        json={"agreed": True, "signerName": "Javohir Alimov", "demoConfirm": True},
    )
    assert signed.status_code == 200

    # 1. Original PDF -> valid
    pdf_orig = (await api_client.get(f"/api/tilxat/{t['id']}/pdf")).content
    r_valid = await api_client.post(
        "/api/recognition/verify-document",
        files={"file": ("tilxat.pdf", pdf_orig, "application/pdf")},
    )
    assert r_valid.json()["status"] == "valid"
    assert r_valid.json()["chainVerified"] is True

    # 2. Regenerated PDF layout (different subtitle/layout, same canonical fields & seal) -> MUST STAY VALID (§8, §12)
    async with get_session_factory()() as db:
        rec = await db.get(TilxatAgreement, t["id"])
        assert rec is not None
        regen_pdf = render_haqli_pdf(
            doc_id=rec.id,
            title="RE-RENDERED LAYOUT TILXAT",
            subtitle="Alternative layout check",
            body_paragraphs=["Azizbek Karimov va Javohir Alimov. Summa: 8000000 so'm. Muddat: 2026-09-01."],
            doc_hash=rec.doc_hash,
            seal_signature=rec.seal_signature,
        )
        tampered_amount_pdf = render_haqli_pdf(
            doc_id=rec.id,
            title="TAMPERED AMOUNT TILXAT",
            subtitle="Edited amount",
            body_paragraphs=["Azizbek Karimov va Javohir Alimov. Summa: 99000000 so'm. Muddat: 2026-09-01."],
            doc_hash=rec.doc_hash,
            seal_signature=rec.seal_signature,
        )

    r_regen = await api_client.post(
        "/api/recognition/verify-document",
        files={"file": ("regen.pdf", regen_pdf, "application/pdf")},
    )
    assert r_regen.json()["status"] == "valid"

    # 3. Tampered amount PDF -> tampered with "amount" in mismatchedFields
    r_tamp = await api_client.post(
        "/api/recognition/verify-document",
        files={"file": ("tampered.pdf", tampered_amount_pdf, "application/pdf")},
    )
    assert r_tamp.json()["status"] == "tampered"
    assert "amount" in r_tamp.json()["mismatchedFields"]

    # 4. Unknown ID -> unknown
    r_unk = await api_client.get("/api/verify/00000000-0000-0000-0000-000000000000")
    assert r_unk.json()["status"] == "unknown"


@pytest.mark.asyncio
async def test_purge_expired_job_and_file(api_client: httpx.AsyncClient, tmp_path: Path) -> None:
    await _auth_headers(api_client, 100005, "PurgeUser")  # creates the user row
    # Insert an already-expired job & unattached disk file
    dummy_file = tmp_path / "expired.txt"
    dummy_file.write_text("secret", encoding="utf-8")

    async with get_session_factory()() as db:
        from app.models.entities import User
        from sqlalchemy import select

        u = (await db.execute(select(User).where(User.telegram_id == 100005))).scalar_one()
        uf = UploadedFile(
            owner_id=u.id,
            sha256="a" * 64,
            mime="text/plain",
            size=6,
            path=str(dummy_file),
            purge_at=utcnow() - timedelta(hours=1),
        )
        db.add(uf)
        await db.flush()
        db.add(
            RecognitionJob(
                user_id=u.id,
                kind="document",
                status="done",
                file_id=uf.id,
                expires_at=utcnow() - timedelta(hours=1),
            )
        )
        await db.commit()

        stats = await purge_expired_recognition_data(db)
        assert stats["purgedJobs"] >= 1
        assert stats["purgedFiles"] >= 1
        assert not dummy_file.exists()
