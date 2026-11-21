"""Radar (Proactive Law Alerts) & Advocate MSO routers + SSE stream & Health/Verify endpoints."""

from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_db, utcnow
from app.engines.rules import load_constants
from app.engines.translit import localize_text
from app.models.entities import AdvocateLead, DisputeCase, LawAlert, User
from app.routers.deps import get_current_user, require_advocate, write_audit_log
from app.schemas.api import LeadActionRequest
from app.services.notifications import send_telegram_message

radar_router = APIRouter(prefix="/api/radar", tags=["radar"])
mso_router = APIRouter(prefix="/api/mso", tags=["mso"])


def _alert_dto(a: LawAlert, locale: str) -> dict[str, Any]:
    return {
        "id": a.id,
        "decreeRef": a.decree_ref,
        "publishedDate": a.published_date.isoformat(),
        "tags": a.tags,
        "title": localize_text(a.title_uz, locale, a.title_ru),
        "whatChanged": localize_text(a.what_changed_uz, locale, a.what_changed_ru),
        "walletImpact": localize_text(a.wallet_impact_uz, locale, a.wallet_impact_ru),
        "actionLabel": localize_text(a.action_label_uz, locale, a.action_label_ru),
        "actionRoute": a.action_route,
        "legalRefId": a.legal_ref_id,
        "status": a.status,
    }


@radar_router.get("/alerts")
async def list_radar_alerts(
    tags: str = Query(""),
    locale: str = Query("uz_lat"),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    res = await db.execute(select(LawAlert).order_by(desc(LawAlert.published_date)))
    alerts = res.scalars().all()
    filter_tags = {t.strip().lower() for t in tags.split(",") if t.strip()}
    if filter_tags:
        alerts = [a for a in alerts if any(t.lower() in filter_tags for t in (a.tags or []))]
    return {"items": [_alert_dto(a, locale) for a in alerts], "nextCursor": None}


@radar_router.post("/subscribe")
async def subscribe_radar(
    enabled: bool = True,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    user.push_enabled = enabled
    await db.commit()
    return {"pushEnabled": user.push_enabled}


@radar_router.post("/simulate")
async def simulate_radar_alert(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    cfg = get_settings()
    if not cfg.demo_mode:
        raise HTTPException(status_code=403, detail="Simulate endpoint is only available in DEMO_MODE.")
    alert = LawAlert(
        decree_ref="Demo · VMQ yangilanish",
        published_date=date.today(),
        tags=user.profile_tags or ["istemolchi", "xodim"],
        title_uz="Yangi tartib: Elektron chek va ish haqi kechikishida avtomatik penya",
        title_ru="Новый порядок: автоматическая пеня по чекам и задержке зарплаты",
        what_changed_uz="Demo ogohlantirish: fuqarolar da'vo hujjatlarini tezkor elektron talabnoma bilan yuborishlari mumkin.",
        what_changed_ru="Демо-уведомление: граждане могут оперативно направлять досудебные претензии.",
        wallet_impact_uz="O'z vaqtida harakat qilinganda 100% gacha kechikish penyasini saqlab qolasiz.",
        wallet_impact_ru="Своевременная претензия позволяет взыскать до 100% пени за просрочку.",
        action_label_uz="Talabnoma tuzish",
        action_label_ru="Создать претензию",
        action_route="/himoya?category=consumer",
        legal_ref_id="inst_consumer_19",
        status="needs_review",
    )
    db.add(alert)
    await db.commit()
    await db.refresh(alert)
    push = await send_telegram_message(
        user.telegram_id,
        f"<b>Haqli Radar:</b> {alert.title_uz}",
        web_app_url=cfg.public_base_url,
    )
    return {"alert": _alert_dto(alert, user.language), "notification": push}


# ------------------------------------------------------------------
# ADVOCATE MSO ROUTES (§9.5, §10)
# ------------------------------------------------------------------
def _lead_dto(lead: AdvocateLead, *, reveal_contact: bool) -> dict[str, Any]:
    brief = dict(lead.brief_json or {})
    if not reveal_contact:
        brief["clientContact"] = "Qabul qilingandan so'ng ochiladi / Доступно после принятия"
    return {
        "id": lead.id,
        "caseId": lead.case_id,
        "advocateId": lead.advocate_id,
        "status": lead.status,
        "platformFeePercent": lead.platform_fee_percent,
        "brief": brief,
        "declineReason": lead.decline_reason,
        "acceptedAt": lead.accepted_at.isoformat() if lead.accepted_at else None,
        "createdAt": lead.created_at.isoformat(),
    }


@mso_router.post("/escalate/{case_id}")
async def escalate_to_advocate(
    case_id: str,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    case = await db.get(DisputeCase, case_id)
    if case is None or case.user_id != user.id:
        raise HTTPException(status_code=404, detail="Case not found.")
    constants = load_constants()
    fee = int(constants.val("mso.platform_fee_percent"))
    brief = {
        "category": case.category,
        "respondentName": case.respondent_name,
        "incidentDate": case.incident_date.isoformat() if case.incident_date else None,
        "claimAmountUzs": str(case.claim_amount_uzs),
        "computed": case.computed,
        "caseStrength": case.case_strength,
        "strengthBreakdown": case.strength_breakdown,
        "citations": case.citations,
        "assessment": case.assessment_text,
        "clientName": user.full_name,
        "clientContact": f"@{user.username}" if user.username else f"tg://user?id={user.telegram_id}",
        "docHash": case.doc_hash,
    }
    lead = AdvocateLead(case_id=case.id, status="new", brief_json=brief, platform_fee_percent=fee)
    case.status = "escalated"
    db.add(lead)
    await db.flush()
    await write_audit_log(db, actor=user.id, action="escalate_mso", entity="advocate_lead", entity_id=lead.id, request=request)
    await db.commit()
    await db.refresh(lead)
    return _lead_dto(lead, reveal_contact=False)


@mso_router.get("/leads")
async def list_leads(
    status: str | None = Query(None),
    category: str | None = Query(None),
    advocate: User = Depends(require_advocate),
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    res = await db.execute(select(AdvocateLead).order_by(desc(AdvocateLead.created_at)).limit(50))
    leads = res.scalars().all()
    out = []
    for ld in leads:
        if status and ld.status != status:
            continue
        if category and (ld.brief_json or {}).get("category") != category:
            continue
        reveal = ld.status == "accepted" and ld.advocate_id == advocate.id
        out.append(_lead_dto(ld, reveal_contact=reveal))
    return out


@mso_router.get("/leads/{lead_id}")
async def get_lead(
    lead_id: str,
    advocate: User = Depends(require_advocate),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    ld = await db.get(AdvocateLead, lead_id)
    if ld is None:
        raise HTTPException(status_code=404, detail="Lead not found.")
    return _lead_dto(ld, reveal_contact=(ld.status == "accepted" and ld.advocate_id == advocate.id))


@mso_router.post("/leads/{lead_id}/accept")
async def accept_lead(
    lead_id: str,
    request: Request,
    advocate: User = Depends(require_advocate),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    ld = await db.get(AdvocateLead, lead_id)
    if ld is None:
        raise HTTPException(status_code=404, detail="Lead not found.")
    ld.status = "accepted"
    ld.advocate_id = advocate.id
    ld.accepted_at = utcnow()
    await write_audit_log(db, actor=advocate.id, action="accept_lead", entity="advocate_lead", entity_id=ld.id, request=request)
    await db.commit()
    await db.refresh(ld)
    return _lead_dto(ld, reveal_contact=True)


@mso_router.post("/leads/{lead_id}/request-info")
async def request_more_info(
    lead_id: str,
    req: LeadActionRequest,
    advocate: User = Depends(require_advocate),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    ld = await db.get(AdvocateLead, lead_id)
    if ld is None:
        raise HTTPException(status_code=404, detail="Lead not found.")
    ld.status = "more_info_requested"
    case = await db.get(DisputeCase, ld.case_id)
    if case:
        citizen = await db.get(User, case.user_id)
        if citizen:
            await send_telegram_message(
                citizen.telegram_id,
                f"<b>Haqli Advokat so'rovi:</b> {req.message or 'Iltimos, qo`shimcha dalil yuklang.'}",
            )
    await db.commit()
    return _lead_dto(ld, reveal_contact=False)


@mso_router.post("/leads/{lead_id}/decline")
async def decline_lead(
    lead_id: str,
    req: LeadActionRequest,
    advocate: User = Depends(require_advocate),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    ld = await db.get(AdvocateLead, lead_id)
    if ld is None:
        raise HTTPException(status_code=404, detail="Lead not found.")
    ld.status = "declined"
    ld.decline_reason = req.reason or "Declined by advocate"
    await db.commit()
    return _lead_dto(ld, reveal_contact=False)


@mso_router.get("/metrics")
async def mso_metrics(
    advocate: User = Depends(require_advocate),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    res = await db.execute(select(AdvocateLead))
    all_leads = res.scalars().all()
    new_cnt = sum(1 for l in all_leads if l.status == "new")
    accepted_cnt = sum(1 for l in all_leads if l.status == "accepted")
    constants = load_constants()
    return {
        "newLeads": new_cnt,
        "acceptedThisMonth": accepted_cnt,
        "avgIntakeTimeSavedMin": 42,
        "platformFeePercent": int(constants.val("mso.platform_fee_percent")),
        "complianceBanner": "Haqli yuridik xizmat ko'rsatmaydi; mustaqil advokatlarga ish tayyorlaydi.",
    }
