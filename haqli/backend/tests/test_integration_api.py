"""End-to-end integration tests for Haqli FastAPI backend (§10, §14)."""

from __future__ import annotations

import httpx
import pytest

from tests.conftest import build_signed_init_data


@pytest.mark.asyncio
async def test_telegram_hmac_auth_valid_and_tampered(api_client: httpx.AsyncClient) -> None:
    valid_init = build_signed_init_data(bot_token="123456:TEST_BOT_SECRET_TOKEN", user_id=777111)
    r_ok = await api_client.post("/api/auth/telegram", json={"initData": valid_init})
    assert r_ok.status_code == 200
    body = r_ok.json()
    assert body["accessToken"]
    assert body["user"]["telegramId"] == 777111
    assert "processingTimeMs" in body
    assert "X-Request-Id" in r_ok.headers
    assert "Server-Timing" in r_ok.headers

    # Tampered initData MUST be rejected with 401
    tampered = valid_init.replace("Sardor", "Hacker")
    r_bad = await api_client.post("/api/auth/telegram", json={"initData": tampered})
    assert r_bad.status_code == 401


@pytest.mark.asyncio
async def test_dispute_full_lifecycle_pay_and_pdf(api_client: httpx.AsyncClient) -> None:
    auth = await api_client.post("/api/auth/telegram", json={"initData": "", "demoName": "Azizbek Test"})
    assert auth.status_code == 200
    headers = {"Authorization": f"Bearer {auth.json()['accessToken']}"}

    # 1. Create draft & patch
    draft = await api_client.post(
        "/api/disputes/drafts",
        headers=headers,
        json={"category": "consumer", "respondentName": "TechShop MCHJ", "claimAmountUzs": "3500000", "delayDays": 12},
    )
    assert draft.status_code == 200
    case_id = draft.json()["id"]

    # 2. Analyze
    analyzed = await api_client.post(
        "/api/disputes/analyze",
        headers=headers,
        json={
            "caseId": case_id,
            "category": "consumer",
            "respondentName": "TechShop MCHJ",
            "incidentDate": "2026-04-01",
            "claimAmountUzs": "3500000",
            "delayDays": 12,
            "description": "Telefon nosoz chiqdi, 12 kundan beri qaytarilmadi.",
            "hasWrittenEvidence": True,
            "locale": "uz_lat",
        },
    )
    assert analyzed.status_code == 200
    a_data = analyzed.json()
    assert a_data["caseStrength"] >= 85
    assert a_data["computed"]["penaltyUzs"] == "420000.00"
    assert a_data["hasUnverifiedLegalData"] is True

    # 3. Attempting Talabnoma PDF before payment returns 402
    pre_pay = await api_client.post(f"/api/disputes/{case_id}/documents?type=talabnoma", headers=headers)
    assert pre_pay.status_code == 402

    # 4. Simulated payment
    pay = await api_client.post(f"/api/disputes/{case_id}/pay", headers=headers)
    assert pay.status_code == 200
    assert pay.json()["provider"] == "simulated"

    # 5. Generate & download PDF + verify seal
    gen = await api_client.post(f"/api/disputes/{case_id}/documents?type=talabnoma", headers=headers)
    assert gen.status_code == 200
    pdf_resp = await api_client.get(f"/api/disputes/{case_id}/pdf?type=talabnoma", headers=headers)
    assert pdf_resp.status_code == 200
    assert pdf_resp.headers["content-type"].startswith("application/pdf")
    assert pdf_resp.content[:4] == b"%PDF"

    # 6. Verify authenticity endpoint (valid vs tampered bytes)
    ver_ok = await api_client.post(
        "/api/recognition/verify-document",
        data={"doc_id": case_id},
        files={"file": ("talabnoma.pdf", pdf_resp.content, "application/pdf")},
    )
    assert ver_ok.status_code == 200
    assert ver_ok.json()["status"] == "valid"

    ver_tampered = await api_client.post(
        "/api/recognition/verify-document",
        data={"doc_id": case_id},
        files={"file": ("tampered.pdf", pdf_resp.content + b"TAMPER", "application/pdf")},
    )
    assert ver_tampered.status_code == 200
    assert ver_tampered.json()["status"] == "tampered"


@pytest.mark.asyncio
async def test_tilxat_create_public_sign_and_verify(api_client: httpx.AsyncClient) -> None:
    auth = await api_client.post("/api/auth/telegram", json={"initData": ""})
    headers = {"Authorization": f"Bearer {auth.json()['accessToken']}"}

    created = await api_client.post(
        "/api/tilxat",
        headers=headers,
        json={
            "docType": "loan",
            "partyAName": "Azizbek Karimov",
            "partyAPassport": "AD1234567",
            "partyBName": "Javohir Alimov",
            "amountUzs": "8000000",
            "dueDate": "2026-09-01",
            "dailyPenaltyPercent": "0.1",
            "locale": "uz_lat",
        },
    )
    assert created.status_code == 200
    t = created.json()
    assert t["requiresWritten"] is True
    assert t["partyAPassportMasked"] == "AD***4567"
    token = t["signToken"]

    # Counterparty opens public view
    pub = await api_client.get(f"/api/tilxat/public/{token}")
    assert pub.status_code == 200
    assert pub.json()["status"] == "pending_counterparty"

    # Counterparty confirms
    signed = await api_client.post(
        f"/api/tilxat/public/{token}/sign",
        json={"agreed": True, "signerName": "Javohir Alimov", "signerPassport": "AA9876543", "demoConfirm": True},
    )
    assert signed.status_code == 200
    assert signed.json()["status"] == "signed"
    assert signed.json()["partyBPassportMasked"] == "AA***6543"

    # Public verify URL works
    ver = await api_client.get(f"/api/verify/{t['id']}")
    assert ver.status_code == 200
    assert ver.json()["status"] == "valid"


@pytest.mark.asyncio
async def test_scanner_radar_and_mso_advocate_gate(api_client: httpx.AsyncClient) -> None:
    auth = await api_client.post("/api/auth/telegram", json={"initData": ""})
    headers = {"Authorization": f"Bearer {auth.json()['accessToken']}"}

    # Scanner audit on risky microloan sample
    audit = await api_client.post("/api/scanner/audit", headers=headers, json={"sampleId": "microloan", "locale": "uz_lat"})
    assert audit.status_code == 200
    a = audit.json()
    assert a["safetyScore"] < 75
    assert len(a["redFlags"]) >= 2

    # Contextual clause Q&A grounded in instruments.json
    qa = await api_client.post(
        "/api/scanner/ask-clause",
        headers=headers,
        json={"clauseText": a["redFlags"][0]["quotedClause"], "question": "Bu band qonuniymi?", "legalRefs": ["inst_fk_260"]},
    )
    assert qa.status_code == 200
    assert len(qa.json()["citations"]) >= 1

    # Radar alerts
    alerts = await api_client.get("/api/radar/alerts?tags=xodim,haydovchi")
    assert alerts.status_code == 200
    assert len(alerts.json()["items"]) >= 2

    # MSO gate: citizen cannot access advocate leads
    denied = await api_client.get("/api/mso/leads", headers=headers)
    assert denied.status_code == 403

    # Wrong invite code fails
    bad_code = await api_client.patch("/api/auth/preferences", headers=headers, json={"role": "advocate", "inviteCode": "WRONG"})
    assert bad_code.status_code == 403

    # Valid invite code unlocks advocate workspace & contact reveal only after accept
    ok_adv = await api_client.patch(
        "/api/auth/preferences",
        headers=headers,
        json={"role": "advocate", "inviteCode": "HAQLI-ADV-2026", "licenseNumber": "UZ-ADV-0042"},
    )
    assert ok_adv.status_code == 200
    adv_headers = {"Authorization": f"Bearer {ok_adv.json()['accessToken']}"}

    leads = await api_client.get("/api/mso/leads", headers=adv_headers)
    assert leads.status_code == 200
    assert len(leads.json()) >= 1
    first = leads.json()[0]
    assert "ochiladi" in first["brief"]["clientContact"] or "принятия" in first["brief"]["clientContact"]

    accepted = await api_client.post(f"/api/mso/leads/{first['id']}/accept", headers=adv_headers)
    assert accepted.status_code == 200
    assert accepted.json()["status"] == "accepted"
    assert "ochiladi" not in accepted.json()["brief"]["clientContact"]

    # Health & readiness
    ready = await api_client.get("/readyz")
    assert ready.status_code == 200
    assert ready.json()["ready"] is True
