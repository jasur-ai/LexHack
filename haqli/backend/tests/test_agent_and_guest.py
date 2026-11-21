"""Guest sessions, the AI-lawyer proxy (healthy, failing and unreachable agent) and canonical tilxat hashing."""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from typing import Any

import httpx
import pytest

from app.security.canonical import (
    canonical_timestamp,
    tilxat_draft_payload,
    tilxat_hash_candidates,
    tilxat_signed_payload,
)
from app.security.crypto import get_crypto

_REAL_ASYNC_CLIENT = httpx.AsyncClient


@pytest.mark.asyncio
async def test_guest_sessions_are_private_per_device(api_client: httpx.AsyncClient) -> None:
    a = await api_client.post("/api/auth/telegram", json={"initData": "", "deviceId": "device-aaaaaaaaaaaaaaaa"})
    b = await api_client.post("/api/auth/telegram", json={"initData": "", "deviceId": "device-bbbbbbbbbbbbbbbb"})
    again = await api_client.post("/api/auth/telegram", json={"initData": "", "deviceId": "device-aaaaaaaaaaaaaaaa"})
    assert a.status_code == b.status_code == again.status_code == 200
    ua, ub = a.json()["user"], b.json()["user"]
    assert ua["isGuest"] is True and ua["telegramId"] < 0
    assert ua["id"] != ub["id"]
    assert again.json()["user"]["id"] == ua["id"]

    # A tilxat created by device A is not visible to device B
    ha = {"Authorization": f"Bearer {a.json()['accessToken']}"}
    hb = {"Authorization": f"Bearer {b.json()['accessToken']}"}
    created = await api_client.post(
        "/api/tilxat",
        headers=ha,
        json={
            "docType": "loan",
            "partyAName": "Ali Valiyev",
            "partyBName": "Vali Aliyev",
            "amountUzs": "3000000",
            "dueDate": "2027-01-15",
            "dailyPenaltyPercent": "0.1",
            "locale": "uz_lat",
        },
    )
    assert created.status_code == 200, created.text
    mine = (await api_client.get("/api/tilxat", headers=ha)).json()
    theirs = (await api_client.get("/api/tilxat", headers=hb)).json()
    ids_mine = {t["id"] for t in (mine["items"] if isinstance(mine, dict) else mine)}
    ids_theirs = {t["id"] for t in (theirs["items"] if isinstance(theirs, dict) else theirs)}
    assert created.json()["id"] in ids_mine and created.json()["id"] not in ids_theirs

    bad = await api_client.post("/api/auth/telegram", json={"initData": "", "deviceId": "../../etc"})
    assert bad.status_code == 422


@pytest.mark.asyncio
async def test_seeded_demo_tilxat_verifies_as_valid(api_client: httpx.AsyncClient) -> None:
    auth = await api_client.post("/api/auth/telegram", json={"initData": ""})
    headers = {"Authorization": f"Bearer {auth.json()['accessToken']}"}
    listing = (await api_client.get("/api/tilxat", headers=headers)).json()
    items = listing["items"] if isinstance(listing, dict) else listing
    signed = [t for t in items if t["status"] == "signed"]
    assert signed, "demo seed should contain a signed tilxat"
    res = await api_client.get(f"/api/verify/{signed[0]['id']}")
    assert res.status_code == 200
    assert res.json()["status"] == "valid"


class _FakeAgent:
    def __init__(self, mode: str) -> None:
        self.mode = mode
        self.seen: list[dict[str, Any]] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        if self.mode == "down":
            raise httpx.ConnectError("connection refused", request=request)
        if request.url.path == "/api/health":
            return httpx.Response(200, json={"index_ready": True, "answer_mode": "extractive", "bm25_chunks": 17365})
        if request.url.path == "/api/sources":
            return httpx.Response(200, json={"sources": [{"id": "uzbek_legal_corpus_cc0"}], "total_chunks": 17365})
        self.seen.append(json.loads(request.content))
        if self.mode == "http500":
            return httpx.Response(500, text="boom")
        events = [
            {"type": "step", "step": 1, "total": 5, "status": "running"},
            {"type": "sources", "sources": [{"n": 1, "title": "Mehnat kodeksi", "article": "217-modda"}]},
            {"type": "token", "text": "### ANSWER\n21 kun [1]"},
            {
                "type": "done",
                "elapsed_ms": 40,
                "response": {
                    "answer": "21 kun [1]",
                    "mode": "extractive",
                    "sections": {"structured": True, "answer": "21 kun [1]"},
                    "query_plan": {"sub_queries": ["x" * 2000]},
                    "hop_traces": [{"hop": 1}],
                    "verification": {"passed": True, "confidence_score": 0.9, "verified_citations": [{"x": 1}]},
                },
            },
        ]
        if self.mode == "truncated":
            events = events[:3]
        body = "".join(f"data: {json.dumps(e, ensure_ascii=False)}\n\n" for e in events)
        return httpx.Response(200, text=body, headers={"content-type": "text/event-stream"})


def _install_fake_agent(monkeypatch: pytest.MonkeyPatch, fake: _FakeAgent) -> None:
    import app.routers.agent as agent_mod

    def factory(*args: Any, **kwargs: Any) -> httpx.AsyncClient:
        kwargs.pop("transport", None)
        return _REAL_ASYNC_CLIENT(*args, transport=httpx.MockTransport(fake.handler), **kwargs)

    monkeypatch.setattr(agent_mod.httpx, "AsyncClient", factory)
    agent_mod._sources_cache.update(at=0.0, data=None)


async def _stream_events(
    client: httpx.AsyncClient, headers: dict[str, str], query: str, context: str | None = None
) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    body: dict[str, Any] = {"query": query, "locale": "uz_cyr"}
    if context:
        body["context"] = context
    async with client.stream("POST", "/api/agent/ask/stream", headers=headers, json=body) as resp:
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")
        async for line in resp.aiter_lines():
            if line.startswith("data:"):
                events.append(json.loads(line[5:]))
    return events


@pytest.mark.asyncio
async def test_agent_proxy_streams_and_degrades_gracefully(
    api_client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    auth = await api_client.post("/api/auth/telegram", json={"initData": "", "deviceId": "device-cccccccccccccccc"})
    headers = {"Authorization": f"Bearer {auth.json()['accessToken']}"}

    ok = _FakeAgent("ok")
    _install_fake_agent(monkeypatch, ok)
    status = (await api_client.get("/api/agent/status")).json()
    assert status["available"] is True and status["answerMode"] == "extractive"
    sources = (await api_client.get("/api/agent/sources")).json()
    assert sources["totalChunks"] == 17365

    events = await _stream_events(api_client, headers, "Yillik ta'til necha kun?")
    assert [e["type"] for e in events] == ["step", "sources", "token", "done"]
    assert ok.seen[-1]["response_language"] == "uz_cyrl" and ok.seen[-1]["answer_style"] == "concise"
    # the final event keeps what the chat renders and drops the heavy internals
    final = events[-1]["response"]
    assert final["answer"] == "21 kun [1]" and final["sections"]["structured"] is True
    assert final["verification"] == {"passed": True, "confidence_score": 0.9, "warnings": []}
    assert "query_plan" not in final and "hop_traces" not in final

    await _stream_events(api_client, headers, "Muddatlari qanday?", context="Yillik ta'til necha kun?")
    assert ok.seen[-1]["context"] == "Yillik ta'til necha kun?" and ok.seen[-1]["query"] == "Muddatlari qanday?"

    truncated = _FakeAgent("truncated")
    _install_fake_agent(monkeypatch, truncated)
    events = await _stream_events(api_client, headers, "Yillik ta'til necha kun?")
    assert events[-1] == {"type": "error", "code": "agent_incomplete", "detail": "Javob to'liq kelmadi."}

    failing = _FakeAgent("http500")
    _install_fake_agent(monkeypatch, failing)
    events = await _stream_events(api_client, headers, "Yillik ta'til necha kun?")
    assert events[-1]["code"] == "agent_error"

    down = _FakeAgent("down")
    _install_fake_agent(monkeypatch, down)
    assert (await api_client.get("/api/agent/status")).json()["available"] is False
    events = await _stream_events(api_client, headers, "Yillik ta'til necha kun?")
    assert events == [{"type": "error", "code": "agent_unavailable", "detail": "AI yurist hozircha ulanmagan."}]

    too_short = await api_client.post("/api/agent/ask/stream", headers=headers, json={"query": "a"})
    assert too_short.status_code == 422


def test_canonical_tilxat_hash_survives_database_round_trip() -> None:
    crypto = get_crypto()
    signed_at = datetime(2026, 11, 21, 6, 50, 1, 123456, tzinfo=timezone.utc)
    draft = tilxat_draft_payload(
        doc_type="loan", party_a="A", party_b="B", amount_uzs=Decimal("5000000"),
        due_date=date(2027, 1, 1), penalty_percent=Decimal("0.1"), terms="t",
    )
    draft_hash = crypto.chain_hash("0" * 64, draft)
    stored = SimpleNamespace(
        id="t1", status="pending_counterparty", party_b_signed_at=None, chain_prev_hash="0" * 64,
        doc_type="loan", party_a_name="A", party_b_name="B", amount_uzs=Decimal("5000000.00"),
        due_date=date(2027, 1, 1), daily_penalty_percent=Decimal("0.100"), terms_summary="t",
        party_a_tg_id=1, party_b_tg_id=None,
    )
    assert draft_hash in tilxat_hash_candidates(stored)

    signed_hash = crypto.chain_hash(
        draft_hash,
        tilxat_signed_payload(
            tilxat_id="t1", prev_hash=draft_hash, party_a_tg=1, party_b_tg=2,
            signed_at=signed_at, amount_uzs=Decimal("5000000"),
        ),
    )
    # SQLite hands the timestamp back without tzinfo and the amount with two decimals
    stored.status, stored.party_b_signed_at, stored.chain_prev_hash, stored.party_b_tg_id = (
        "signed", signed_at.replace(tzinfo=None), draft_hash, 2,
    )
    assert signed_hash in tilxat_hash_candidates(stored)
    assert canonical_timestamp(signed_at) == canonical_timestamp(signed_at.replace(tzinfo=None))

    # Documents sealed by the previous release (aware isoformat, raw amount) still verify
    legacy = crypto.chain_hash(
        draft_hash,
        {"id": "t1", "prevHash": draft_hash, "partyATg": 1, "partyBTg": 2,
         "signedAt": signed_at.isoformat(), "amountUzs": "5000000.00"},
    )
    assert legacy in tilxat_hash_candidates(stored)
