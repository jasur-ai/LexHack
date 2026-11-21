"""Deterministic legal document drafter (Talabnoma, State Organ Complaint, Tilxat text, Advocate Brief)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from app.engines.rules import amount_in_words
from app.engines.translit import localize_text


def _fmt_money(amount: Decimal | str | int) -> str:
    d = Decimal(str(amount)).quantize(Decimal("0.01"))
    whole = int(d)
    frac = int((d - whole) * 100)
    grouped = f"{whole:,}".replace(",", " ")
    return f"{grouped}.{frac:02d}" if frac else grouped


def draft_dispute_documents(
    *,
    category: str,
    citizen_name: str,
    respondent_name: str,
    incident_date: date,
    claim_amount_uzs: Decimal,
    penalty_uzs: Decimal,
    total_uzs: Decimal,
    formula: str,
    delay_days: int,
    response_days: int,
    response_due: str,
    citations: list[dict[str, Any]],
    description: str,
    locale: str = "uz_lat",
) -> dict[str, str]:
    """Generate deterministic assessment, formal Talabnoma, and paste-ready state-organ complaint."""
    cite_str = "; ".join(f"{c['instrument']} ({c['article']})" for c in citations) or "O'zbekiston Respublikasi qonunchiligi"
    today_str = date.today().isoformat()

    assessment_uz = (
        f"Holat bo'yicha dastlabki huquqiy baholash: '{respondent_name}' ga nisbatan {_fmt_money(claim_amount_uzs)} so'm "
        f"asosiy talab va {_fmt_money(penalty_uzs)} so'm penya/kompensatsiya (jami: {_fmt_money(total_uzs)} so'm) hisoblandi. "
        f"Huquqiy asos: {cite_str}. Javobgar tarafga {response_days} kun ({response_due} gacha) ixtiyoriy bajarish muddati beriladi."
    )
    assessment_ru = (
        f"Правовая оценка: к '{respondent_name}' рассчитано основное требование {_fmt_money(claim_amount_uzs)} сум "
        f"и неустойка/компенсация {_fmt_money(penalty_uzs)} сум (итого: {_fmt_money(total_uzs)} сум). "
        f"Правовая база: {cite_str}. Срок добровольного исполнения: {response_days} дн. (до {response_due})."
    )

    talabnoma_uz = (
        f"Kimga: {respondent_name}\n"
        f"Kimdan: {citizen_name}\n"
        f"Sana: {today_str}\n\n"
        f"RASMIY TALABNOMA (SUDGACHA HAL ETISH TARTIBIDA)\n\n"
        f"1. Holat bayoni:\n"
        f"{incident_date.isoformat()} sanasida yuz bergan holat bo'yicha siz tomondan majburiyatlar bajarilmagan "
        f"(kechikish: {delay_days} kun). Tafsilotlar: {description or 'Asosiy summa o‘z vaqtida to‘lanmagan/qaytarilmagan.'}\n\n"
        f"2. Huquqiy asos:\n{cite_str}.\n\n"
        f"3. Hisob-kitob:\n"
        f"- Asosiy talab summasi: {_fmt_money(claim_amount_uzs)} so'm\n"
        f"- Penya / kompensatsiya ({formula}): {_fmt_money(penalty_uzs)} so'm\n"
        f"- Jami to'lanishi lozim: {_fmt_money(total_uzs)} so'm ({amount_in_words(total_uzs, 'uz_lat')})\n\n"
        f"4. Talab:\n"
        f"Ushbu Talabnoma olingan kundan boshlab {response_days} kalendar kun ichida ({response_due} ga qadar) "
        f"jami {_fmt_money(total_uzs)} so'mni to'liq qoplashingizni talab qilaman. Aks holda vakolatli davlat organiga "
        f"shikoyat hamda sudga da'vo arizasi kiritilishi va barcha sud xarajatlari sizning hisobingizdan undirilishini ma'lum qilaman."
    )
    talabnoma_ru = (
        f"Кому: {respondent_name}\n"
        f"От кого: {citizen_name}\n"
        f"Дата: {today_str}\n\n"
        f"ОФИЦИАЛЬНАЯ ДОСУДЕБНАЯ ПРЕТЕНЗИЯ (ТАЛАБНОМА)\n\n"
        f"1. Обстоятельства:\n"
        f"По инциденту от {incident_date.isoformat()} обязательства не исполнены (просрочка: {delay_days} дн.). "
        f"Детали: {description or 'Сумма не возвращена / обязательство не выполнено в срок.'}\n\n"
        f"2. Правовое основание:\n{cite_str}.\n\n"
        f"3. Расчет суммы:\n"
        f"- Основная сумма: {_fmt_money(claim_amount_uzs)} сум\n"
        f"- Пеня / компенсация ({formula}): {_fmt_money(penalty_uzs)} сум\n"
        f"- Итого к выплате: {_fmt_money(total_uzs)} сум ({amount_in_words(total_uzs, 'ru')})\n\n"
        f"4. Требование:\n"
        f"В течение {response_days} календарных дней (до {response_due}) прошу выплатить {_fmt_money(total_uzs)} сум. "
        f"В противном случае последует жалоба в уполномоченный орган и иск в суд с отнесением судебных расходов на вас."
    )

    organ_map_uz = {
        "labor": "Davlat mehnat inspeksiyasiga (my.gov.uz orqali)",
        "consumer": "Raqobatni rivojlantirish va iste'molchilar huquqlarini himoya qilish qo'mitasiga (my.gov.uz orqali)",
        "rental": "Tuman fuqarolik ishlari bo'yicha sudiga / Soliq organiga",
        "traffic": "YHXX yuqori turuvchi organiga yoki Ma'muriy sudga",
        "debt": "Fuqarolik ishlari bo'yicha sudga",
    }

    if category == "traffic":
        limitation_text_uz = ""
        limitation_text_ru = ""
        if delay_days > 10:
            limitation_text_uz = (
                "\n\nMUDDATNI TIKLASH TO'G'RISIDA ILTIMOSNOMA (MJtK 316-modda):\n"
                "Qaror qabul qilinganligi to'g'risidagi xabarnoma o'z vaqtida yetkazilmaganligi sababli, "
                "10 kunlik shikoyat berish muddatini uzrli deb topib, qayta tiklashingizni so'rayman.\n"
            )
            limitation_text_ru = (
                "\n\nХОДАТАЙСТВО О ВОССТАНОВЛЕНИИ СРОКА (ст. 316 КоАО):\n"
                "В связи с несвоевременным вручением постановления, прошу признать причину пропуска 10-дневного срока уважительной и восстановить срок обжалования.\n"
            )

        organ_uz = organ_map_uz.get(category, "YHXX yuqori turuvchi organiga / Ma'muriy sudga")
        complaint_uz = (
            f"Kimga: {organ_uz}\n"
            f"Arizachi: {citizen_name}\n"
            f"Javobgar / Qaror chiqargan organ: {respondent_name}\n"
            f"Sana: {today_str}\n\n"
            f"YHXX MA'MURIY QARORI USTIDAN SHIKOYAT ARIZASI\n"
            f"(O'zR MJtK 315-moddasiga muvofiq, shikoyat bo'yicha davlat boji to'lanmaydi — 0 so'm)\n\n"
            f"1. Holat bayoni:\n"
            f"{respondent_name} tomonidan {incident_date.isoformat()} sanasida chiqarilgan qarorga asosan "
            f"{_fmt_money(claim_amount_uzs)} so'm miqdorida ma'muriy jarima qo'llanilgan. "
            f"Tafsilotlar: {description or 'Qaror asossiz yoki xabarnoma kechikkan'}.\n"
            f"{limitation_text_uz}\n"
            f"2. Qonuniy asoslar:\n"
            f"- {cite_str}\n"
            f"- MJtK 315-moddasi (Davlat boji to'lanmasligi: 0 so'm)\n"
            f"- MJtK 271-moddasi (Ma'muriy ish yuritishni istisno etuvchi holatlar)\n\n"
            f"3. Talab:\n"
            f"Mazkur ma'muriy jarima qarorini bekor qilishingizni va ish yuritishni tugatishingizni so'rayman.\n\n"
            f"Yo'riqnoma: Ushbu matnni nusxalab my.gov.uz yoki e-sud.uz portaliga joylashtiring."
        )
        complaint_ru = (
            f"Кому: В вышестоящий орган СБДД / Административный суд\n"
            f"Заявитель: {citizen_name}\n"
            f"Орган, вынесший постановление: {respondent_name}\n"
            f"Дата: {today_str}\n\n"
            f"ЖАЛОБА НА ПОСТАНОВЛЕНИЕ ПО ДЕЛУ ОБ АДМИНИСТРАТИВНОМ ПРАВОНАРУШЕНИИ\n"
            f"(Согласно ст. 315 КоАО РУз, государственная пошлина по жалобе не взимается — 0 сум)\n\n"
            f"1. Обстоятельства:\n"
            f"Постановлением от {incident_date.isoformat()} наложен штраф в размере {_fmt_money(claim_amount_uzs)} сум. "
            f"Основания несогласия: {description or 'Постановление вынесено необоснованно'}.\n"
            f"{limitation_text_ru}\n"
            f"2. Правовые основания:\n"
            f"- {cite_str}\n"
            f"- ст. 315 КоАО (Освобождение от уплаты пошлины: 0 сум)\n"
            f"- ст. 271 КоАО (Обстоятельства, исключающие производство по делу)\n\n"
            f"3. Требование:\n"
            f"Прошу отменить указанное постановление и прекратить производство по делу.\n\n"
            f"Инструкция: скопируйте текст и подайте через my.gov.uz или e-sud.uz."
        )
    else:
        complaint_uz = (
            f"Kimga: {organ_map_uz.get(category, 'Vakolatli davlat organiga')}\n"
            f"Arizachi: {citizen_name}\n\n"
            f"SHIKOYAT ARIZASI\n"
            f"'{respondent_name}' tomonidan {incident_date.isoformat()} sanasidan buyon huquqlarim buzilib, "
            f"{_fmt_money(claim_amount_uzs)} so'm to'lanmasdan kelinmoqda ({delay_days} kun kechikish). "
            f"Qonuniy asos ({cite_str}) bo'yicha chora ko'rishingizni va jami {_fmt_money(total_uzs)} so'mni undirishda "
            f"yordam berishingizni so'rayman.\n\n"
            f"Yo'riqnoma: Ushbu matnni nusxalab my.gov.uz portalidagi murojaatlar bo'limiga joylashtiring."
        )
        complaint_ru = (
            f"Кому: В уполномоченный государственный орган (через портал my.gov.uz)\n"
            f"Заявитель: {citizen_name}\n\n"
            f"ЖАЛОБА\n"
            f"Со стороны '{respondent_name}' с {incident_date.isoformat()} нарушаются мои права: не выплачена сумма "
            f"{_fmt_money(claim_amount_uzs)} сум (просрочка {delay_days} дн.). На основании ({cite_str}) прошу принять меры "
            f"и содействовать взысканию итоговой суммы {_fmt_money(total_uzs)} сум.\n\n"
            f"Инструкция: скопируйте текст и подайте через раздел обращений на my.gov.uz."
        )

    return {
        "assessment": localize_text(assessment_uz, locale, assessment_ru),
        "talabnoma": localize_text(talabnoma_uz, locale, talabnoma_ru),
        "complaint": localize_text(complaint_uz, locale, complaint_ru),
    }


def draft_tilxat_summary(
    *,
    doc_type: str,
    party_a_name: str,
    party_b_name: str,
    amount_uzs: Decimal,
    due_date: date,
    daily_penalty_percent: Decimal,
    locale: str = "uz_lat",
) -> str:
    words = amount_in_words(amount_uzs, locale)
    type_uz = {"loan": "QARZ TILXATI", "deposit": "ZAKLAD / AVANS TILXATI", "service": "XIZMAT / IJARA TILXATI"}.get(doc_type, "TILXAT")
    type_ru = {"loan": "ДОЛГОВАЯ РАСПИСКА", "deposit": "РАСПИСКА О ЗАДАТКЕ / АВАНСЕ", "service": "РАСПИСКА ПО УСЛУГЕ / АРЕНДЕ"}.get(doc_type, "РАСПИСКА")

    uz = (
        f"{type_uz}: Men, {party_b_name}, {party_a_name} dan {_fmt_money(amount_uzs)} so'm ({words}) oldim "
        f"va ushbu summani {due_date.isoformat()} sanasigacha to'liq qaytarish/bajarish majburiyatini olaman. "
        f"Kechiktirilgan har bir kun uchun penya: {daily_penalty_percent}%."
    )
    ru = (
        f"{type_ru}: Я, {party_b_name}, получил(а) от {party_a_name} {_fmt_money(amount_uzs)} сум ({words}) "
        f"и обязуюсь вернуть/исполнить обязательство до {due_date.isoformat()}. "
        f"Пеня за каждый день просрочки: {daily_penalty_percent}%."
    )
    return localize_text(uz, locale, ru)
