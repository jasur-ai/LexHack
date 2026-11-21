"""Idempotent first-start demo seeder (§12): 6 law alerts, 3 escalated advocate leads, 1 signed Tilxat with sealed PDF."""

from __future__ import annotations

import json
import secrets
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import utcnow
from app.engines.drafter import draft_tilxat_summary
from app.engines.rules import check_written_form, load_constants
from app.models.entities import AdvocateLead, DisputeCase, LawAlert, TilxatAgreement, User
from app.routers.tilxat import _render_tilxat_pdf
from app.security.canonical import tilxat_draft_payload, tilxat_signed_payload
from app.security.crypto import get_crypto


async def seed_demo_data(db: AsyncSession) -> None:
    cfg = get_settings()
    constants = load_constants()
    crypto = get_crypto()

    # 1. Seed Demo Citizen & Demo Advocate
    res_cit = await db.execute(select(User).where(User.telegram_id == 999000111))
    citizen = res_cit.scalar_one_or_none()
    if citizen is None:
        citizen = User(
            telegram_id=999000111,
            full_name="Azizbek Karimov",
            username="azizbek_demo",
            role="citizen",
            language="uz_lat",
            profile_tags=["xodim", "ijarachi", "istemolchi"],
            consent_version="2026-v1",
            consent_at=utcnow(),
        )
        db.add(citizen)
        await db.flush()

    res_adv = await db.execute(select(User).where(User.telegram_id == 999000222))
    if res_adv.scalar_one_or_none() is None:
        db.add(
            User(
                telegram_id=999000222,
                full_name="Dilnoza Rustamova (Advokat)",
                username="advokat_demo",
                role="advocate",
                license_number="TN-004812",
                language="uz_lat",
                consent_version="2026-v1",
                consent_at=utcnow(),
            )
        )

    # 2. Seed 6 Law Alerts from legal_data/law_alerts.json
    alert_cnt = (await db.execute(select(func.count(LawAlert.id)))).scalar_one()
    if alert_cnt == 0:
        alerts_raw = json.loads((cfg.legal_data_dir / "law_alerts.json").read_text(encoding="utf-8"))
        for item in alerts_raw:
            db.add(
                LawAlert(
                    decree_ref=item["decree_ref"],
                    published_date=date.fromisoformat(item["published_date"]),
                    tags=item["tags"],
                    title_uz=item["title_uz"],
                    title_ru=item["title_ru"],
                    what_changed_uz=item["what_changed_uz"],
                    what_changed_ru=item["what_changed_ru"],
                    wallet_impact_uz=item["wallet_impact_uz"],
                    wallet_impact_ru=item["wallet_impact_ru"],
                    action_label_uz=item["action_label_uz"],
                    action_label_ru=item["action_label_ru"],
                    action_route=item["action_route"],
                    legal_ref_id=item["legal_ref_id"],
                    status=item["status"],
                )
            )

    # 3. Seed 3 escalated cases in Advokat MSO queue
    lead_cnt = (await db.execute(select(func.count(AdvocateLead.id)))).scalar_one()
    if lead_cnt == 0:
        sample_cases = [
            ("labor", "Toshkent Build Tech MCHJ", Decimal("12500000"), 45, 86, ["inst_mk_333", "inst_mk_560"]),
            ("consumer", "MegaElektronika Savdo MCHJ", Decimal("7800000"), 18, 91, ["inst_consumer_19", "inst_consumer_14"]),
            ("rental", "Xudoyberdiyev Sardor (Uy egasi)", Decimal("5500000"), 14, 78, ["inst_fk_535", "inst_fk_260"]),
        ]
        for cat, resp_name, amt, days, strength, cites in sample_cases:
            c = DisputeCase(
                user_id=citizen.id,
                category=cat,
                respondent_name=resp_name,
                incident_date=date.today() - timedelta(days=days),
                claim_amount_uzs=amt,
                delay_days=days,
                computed={"claimAmountUzs": str(amt), "totalUzs": str(amt), "constantsVersion": constants.version},
                citations=cites,
                case_strength=strength,
                strength_breakdown={"written_evidence": 25, "dates_consistent": 15, "amount_documented": 15, "within_limitation": 15, "clear_statutory_basis": 16},
                assessment_text=f"{resp_name} bo'yicha {amt} so'm undirish ishi advokatga uzatildi.",
                status="escalated",
            )
            db.add(c)
            await db.flush()
            # Same canonical payload the dispute analyzer seals, so the demo case verifies as "valid".
            c.doc_hash = crypto.sha256_canonical(
                {"id": c.id, "category": cat, "respondent": resp_name, "totalUzs": str(amt), "talabnoma": c.talabnoma_text}
            )
            c.seal_signature = crypto.sign_seal(c.doc_hash)
            db.add(
                AdvocateLead(
                    case_id=c.id,
                    status="new",
                    platform_fee_percent=int(constants.val("mso.platform_fee_percent")),
                    brief_json={
                        "category": cat,
                        "respondentName": resp_name,
                        "claimAmountUzs": str(amt),
                        "caseStrength": strength,
                        "citations": cites,
                        "assessment": c.assessment_text,
                        "clientName": citizen.full_name,
                        "clientContact": "@azizbek_demo",
                        "docHash": c.doc_hash,
                    },
                )
            )

    # 4. Seed 1 fully signed sample Tilxat with sealed PDF
    tilxat_cnt = (await db.execute(select(func.count(TilxatAgreement.id)))).scalar_one()
    if tilxat_cnt == 0:
        amt = Decimal("5000000.00")
        wf = check_written_form(amt, constants)
        due = date.today() + timedelta(days=45)
        summary = draft_tilxat_summary(
            doc_type="loan",
            party_a_name="Azizbek Karimov",
            party_b_name="Bobur Tursunov",
            amount_uzs=amt,
            due_date=due,
            daily_penalty_percent=Decimal("0.1"),
            locale="uz_lat",
        )
        draft_hash = crypto.chain_hash(
            "0" * 64,
            tilxat_draft_payload(
                doc_type="loan",
                party_a="Azizbek Karimov",
                party_b="Bobur Tursunov",
                amount_uzs=amt,
                due_date=due,
                penalty_percent=Decimal("0.1"),
                terms=summary,
            ),
        )
        t = TilxatAgreement(
            user_id=citizen.id,
            doc_type="loan",
            party_a_name="Azizbek Karimov",
            party_a_passport_enc=crypto.encrypt_field("AD1234567"),
            party_a_tg_id=999000111,
            party_a_signed_at=utcnow() - timedelta(hours=4),
            party_b_name="Bobur Tursunov",
            party_b_passport_enc=crypto.encrypt_field("AB7654321"),
            party_b_tg_id=888000222,
            party_b_signed_at=utcnow() - timedelta(hours=2),
            amount_uzs=amt,
            bhm_ratio=wf["ratio"],
            requires_written=wf["mandatory_written"],
            threshold_snapshot={"thresholdBhm": str(wf["threshold_bhm"]), "constantsVersion": constants.version},
            due_date=due,
            daily_penalty_percent=Decimal("0.1"),
            terms_summary=summary,
            sign_token=secrets.token_urlsafe(24),
            sign_token_expires_at=utcnow() + timedelta(days=7),
            chain_prev_hash="0" * 64,
            doc_hash=draft_hash,
            seal_signature=crypto.sign_seal(draft_hash),
            status="signed",
            locale_used="uz_lat",
        )
        db.add(t)
        await db.flush()
        # Counter-signature re-seal, exactly like POST /api/tilxat/public/{token}/sign does.
        t.chain_prev_hash = draft_hash
        t.doc_hash = crypto.chain_hash(
            draft_hash,
            tilxat_signed_payload(
                tilxat_id=t.id,
                prev_hash=draft_hash,
                party_a_tg=t.party_a_tg_id,
                party_b_tg=t.party_b_tg_id,
                signed_at=t.party_b_signed_at,
                amount_uzs=amt,
            ),
        )
        t.seal_signature = crypto.sign_seal(t.doc_hash)
        pdf_path: Path = _render_tilxat_pdf(t)
        t.pdf_path = str(pdf_path)

    await db.commit()
