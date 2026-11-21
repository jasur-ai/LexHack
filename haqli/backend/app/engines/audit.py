"""Deterministic contract & microloan red-flag auditor (§9.3) with span offsets, legal refs, and 3 sample contracts."""

from __future__ import annotations

import re
from decimal import Decimal
from typing import Any

from app.engines.retrieval import get_instrument_store
from app.engines.rules import ConstantsSnapshot
from app.engines.translit import localize_text, normalize_uz_text

SAMPLE_CONTRACTS: dict[str, dict[str, str]] = {
    "rental": {
        "title_uz": "Namuna: Kvartira ijara shartnomasi (xatarli shartlar)",
        "title_ru": "Образец: Договор аренды квартиры (рискованные условия)",
        "text_uz": (
            "KVARTIRA IJARA SHARTNOMASI\n"
            "1. Ijara haqi oyiga 4 500 000 so'm. Oldindan 4 500 000 so'm depozit olinadi.\n"
            "2. Ijarachi shartnomani muddatidan oldin bekor qilsa, depozit hech qanday shartda qaytarilmaydi.\n"
            "3. Uy egasi istalgan vaqtda bir tomonlama tartibda ogohlantirmasdan shartnomani bekor qilib, ijarachini 24 soat ichida chiqarib yuborish huquqiga ega.\n"
            "4. To'lov 1 kun kechiksa har bir kun uchun 3% penya hisoblanadi."
        ),
        "text_ru": (
            "ДОГОВОР АРЕНДЫ КВАРТИРЫ\n"
            "1. Арендная плата 4 500 000 сум в месяц. Депозит 4 500 000 сум.\n"
            "2. При досрочном расторжении депозит ни при каких обстоятельствах не возвращается.\n"
            "3. Арендодатель вправе в одностороннем порядке без предупреждения расторгнуть договор и выселить арендатора за 24 часа.\n"
            "4. За каждый день просрочки начисляется пеня 3% в день."
        ),
    },
    "microloan": {
        "title_uz": "Namuna: Mikroqarz shartnomasi (yashirin foiz va penya)",
        "title_ru": "Образец: Договор микрозайма (скрытые проценты и пеня)",
        "text_uz": (
            "MIKROQARZ SHARTNOMASI\n"
            "1. Qarz summasi: 8 000 000 so'm, muddati 12 oy.\n"
            "2. Foiz stavkasi oyiga 6% (yillik 72%) hamda xizmat ko'rsatish komissiyasi 10% oldindan ushlab qolinadi.\n"
            "3. To'lov kechiktirilgan har bir kun uchun 2% penya undiriladi.\n"
            "4. Kreditor bir tomonlama tartibda foiz stavkasini istalgan paytda oshirishi mumkin."
        ),
        "text_ru": (
            "ДОГОВОР МИКРОЗАЙМА\n"
            "1. Сумма займа: 8 000 000 сум, срок 12 месяцев.\n"
            "2. Процентная ставка 6% в месяц (72% годовых) и комиссия 10% удерживается заранее.\n"
            "3. За каждый день просрочки начисляется пеня 2% в день.\n"
            "4. Кредитор вправе в одностороннем порядке повысить ставку в любой момент."
        ),
    },
    "employment": {
        "title_uz": "Namuna: Adolatsiz mehnat shartnomasi",
        "title_ru": "Образец: Несправедливый трудовой договор",
        "text_uz": (
            "MEHNAT SHARTNOMASI\n"
            "1. Xodim dastlabki 6 oy sinov muddati bilan oddiy menejer lavozimiga qabul qilinadi.\n"
            "2. Ish haqi rahbarning ixtiyoriga ko'ra belgilanadi va shartnomada aniq summa ko'rsatilmaydi.\n"
            "3. Ish beruvchi xodimni istalgan paytda bir tomonlama ogohlantirmasdan ishdan bo'shatish huquqiga ega.\n"
            "4. Yillik ta'til berilmaydi."
        ),
        "text_ru": (
            "ТРУДОВОЙ ДОГОВОР\n"
            "1. Работник принимается рядовым менеджером с испытательным сроком 6 месяцев.\n"
            "2. Зарплата определяется по усмотрению руководителя без указания точной суммы в договоре.\n"
            "3. Работодатель вправе уволить работника в одностороннем порядке без предупреждения.\n"
            "4. Ежегодный отпуск не предоставляется."
        ),
    },
}


def _find_span(text: str, pattern: str) -> tuple[int, int, str]:
    m = re.search(pattern, text, re.I)
    if not m:
        return 0, min(len(text), 120), text[:120].strip()
    start = max(0, text.rfind("\n", 0, m.start()) + 1)
    end = text.find("\n", m.end())
    if end == -1:
        end = len(text)
    return start, end, text[start:end].strip()


def audit_contract_deterministic(
    text: str,
    constants: ConstantsSnapshot,
    *,
    locale: str = "uz_lat",
) -> dict[str, Any]:
    """Run named deterministic red-flag rules with legal_refs, character spans, and safe alternatives."""
    norm = normalize_uz_text(text)
    low = norm.lower()
    store = get_instrument_store()
    high_apr_thresh = constants.val("scanner.microloan_high_apr_threshold_percent")

    red_flags: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    safe_clauses: list[dict[str, Any]] = []
    score = 100

    # Rule 1: High effective annual interest rate (APR) on microloans
    m_monthly = re.search(r"(?:oyiga|в месяц|per month)\s*(\d+(?:[.,]\d+)?)\s*%|(\d+(?:[.,]\d+)?)\s*%\s*(?:oyiga|в месяц)", low)
    m_annual = re.search(r"(?:yillik|годовых)\s*(\d+(?:[.,]\d+)?)\s*%|(\d+(?:[.,]\d+)?)\s*%\s*(?:yillik|годовых)", low)
    est_apr = Decimal("0")
    if m_monthly:
        raw_m = (m_monthly.group(1) or m_monthly.group(2)).replace(",", ".")
        est_apr = Decimal(raw_m) * Decimal("12")
    elif m_annual:
        raw_a = (m_annual.group(1) or m_annual.group(2)).replace(",", ".")
        est_apr = Decimal(raw_a)
    if est_apr >= high_apr_thresh:
        s, e, quote = _find_span(norm, r"\d+\s*%")
        score -= 28
        red_flags.append(
            {
                "ruleId": "high_effective_apr",
                "severity": "critical",
                "spanStart": s,
                "spanEnd": e,
                "quotedClause": quote,
                "whyRisky": localize_text(
                    f"Samarali yillik foiz stavkasi taxminan {est_apr}% ni tashkil etadi — bu juda og'ir moliyaviy yuk.",
                    locale,
                    f"Эффективная годовая ставка около {est_apr}% — чрезмерная долговая нагрузка.",
                ),
                "safeAlternative": localize_text(
                    "Yillik foiz stavkasi va to'liq kredit qiymati (PSV) barcha komissiyalar bilan aniq cheklanib ko'rsatilishi kerak.",
                    locale,
                    "Укажите прозрачную полную стоимость займа (ПСК) без скрытых удержаний и в пределах допустимых ставок.",
                ),
                "citations": store.resolve_ids(["inst_fk_734"], locale=locale),
            }
        )

    # Rule 2: Excessive daily penalty annualized (> 0.5%/day -> > 182.5%/year)
    m_pen = re.search(r"(?:penya|пеня|неустойк\w*|jarima)[^\n]{0,35}?(\d+(?:[.,]\d+)?)\s*%|(\d+(?:[.,]\d+)?)\s*%[^\n]{0,25}?(?:penya|пеня)", low)
    if m_pen:
        rate = Decimal((m_pen.group(1) or m_pen.group(2)).replace(",", "."))
        ann_pen = rate * Decimal("365")
        if rate >= Decimal("0.5"):
            s, e, quote = _find_span(norm, r"penya|пеня|неустойк")
            score -= 22
            red_flags.append(
                {
                    "ruleId": "excessive_daily_penalty",
                    "severity": "high",
                    "spanStart": s,
                    "spanEnd": e,
                    "quotedClause": quote,
                    "whyRisky": localize_text(
                        f"Kunlik {rate}% penya yiliga {ann_pen}% ga teng bo'lib, qarz summasidan oshib ketish xavfini yaratadi.",
                        locale,
                        f"Пеня {rate}% в день равна {ann_pen}% годовых и несоразмерна нарушению.",
                    ),
                    "safeAlternative": localize_text(
                        "Kechiktirilgan har bir kun uchun 0,1% penya, ammo asosiy qarz summasining 20% dan oshmagan miqdorda.",
                        locale,
                        "Пеня 0,1% за каждый день просрочки, но не более 20% от просроченной суммы (ст. 260, 326 ГК).",
                    ),
                    "citations": store.resolve_ids(["inst_fk_260"], locale=locale),
                }
            )

    # Rule 3: Unilateral termination / rate change without notice
    if re.search(r"bir tomonlama|одностороннем порядке|ogohlantirmasdan|без предупреждения", low):
        s, e, quote = _find_span(norm, r"bir tomonlama|одностороннем порядке|ogohlantirmasdan|без предупреждения")
        score -= 22
        red_flags.append(
            {
                "ruleId": "unilateral_termination",
                "severity": "critical",
                "spanStart": s,
                "spanEnd": e,
                "quotedClause": quote,
                "whyRisky": localize_text(
                    "Ikkinchi tarafni ogohlantirmasdan bir tomonlama bekor qilish yoki shartni o'zgartirish huquqlaringizni qo'pol cheklaydi.",
                    locale,
                    "Одностороннее расторжение или изменение условий без уведомления нарушает баланс прав сторон.",
                ),
                "safeAlternative": localize_text(
                    "Shartnomani muddatidan oldin bekor qilish faqat 30 kun oldin yozma ogohlantirish va o'zaro hisob-kitob asosida amalga oshiriladi.",
                    locale,
                    "Досрочное расторжение допускается только при письменном уведомлении за 30 дней и полном взаиморасчете.",
                ),
                "citations": store.resolve_ids(["inst_fk_535", "inst_mk_165"], locale=locale),
            }
        )

    # Rule 4: Non-refundable deposit
    if re.search(r"depozit[^\n]{0,50}qaytarilmaydi|депозит[^\n]{0,50}не возвращается", low):
        s, e, quote = _find_span(norm, r"depozit|депозит")
        score -= 18
        red_flags.append(
            {
                "ruleId": "non_refundable_deposit",
                "severity": "high",
                "spanStart": s,
                "spanEnd": e,
                "quotedClause": quote,
                "whyRisky": localize_text(
                    "Depozitni hech qanday shartda qaytarmaslik sharti ijara tugaganda pulingizni asossiz ushlab qolishga olib keladi.",
                    locale,
                    "Условие о невозврате депозита позволяет арендодателю безосновательно удерживать ваши средства.",
                ),
                "safeAlternative": localize_text(
                    "Depozit ijara tugaganda mulk shikastlanmagan va kommunal qarzlar yo'qligi topshirish akti bilan tasdiqlangach 3 ish kunida to'liq qaytariladi.",
                    locale,
                    "Депозит возвращается в полном объеме в течение 3 рабочих дней после подписания акта возврата имущества.",
                ),
                "citations": store.resolve_ids(["inst_fk_535"], locale=locale),
            }
        )

    # Rule 5: Missing mandatory employment elements
    if any(k in low for k in ("mehnat shartnomasi", "трудовой договор", "xodim", "работник")):
        if re.search(r"aniq summa ko'rsatilmaydi|без указания точной суммы|ta'til berilmaydi|отпуск не предоставляется", low):
            s, e, quote = _find_span(norm, r"ish haqi|зарплат|ta'til|отпуск")
            score -= 22
            red_flags.append(
                {
                    "ruleId": "missing_mandatory_employment_terms",
                    "severity": "critical",
                    "spanStart": s,
                    "spanEnd": e,
                    "quotedClause": quote,
                    "whyRisky": localize_text(
                        "Mehnat shartnomasida aniq ish haqi va yillik haq to'lanadigan ta'til majburiy; ularni cheklash Mehnat kodeksiga zid.",
                        locale,
                        "Отсутствие точного оклада или отказ в отпуске прямо противоречат Трудовому кодексу РУз.",
                    ),
                    "safeAlternative": localize_text(
                        "Xodimning oylik ish haqi aniq raqamda belgilanadi va kamida 21 kalendar kunlik haq to'lanadigan yillik ta'til kafolatlanadi.",
                        locale,
                        "Укажите точный размер оклада и гарантируйте ежегодный оплачиваемый отпуск не менее 21 календарного дня.",
                    ),
                    "citations": store.resolve_ids(["inst_mk_104"], locale=locale),
                }
            )

    # Rule 6: Missing handover act for rentals
    if any(k in low for k in ("ijara", "kvartira", "аренд", "квартир")) and not re.search(r"dalolatnoma|akt|акт приема", low):
        score -= 8
        warnings.append(
            {
                "ruleId": "missing_handover_act",
                "severity": "medium",
                "spanStart": 0,
                "spanEnd": min(len(norm), 80),
                "quotedClause": norm[:80].strip(),
                "whyRisky": localize_text(
                    "Shartnomada kvartira va jihozlar holatini qayd etuvchi topshirish-qabul qilish dalolatnomasi (akt) ko'rsatilmagan.",
                    locale,
                    "В договоре отсутствует упоминание акта приема-передачи квартиры и мебели.",
                ),
                "safeAlternative": localize_text(
                    "Shartnomaga ilova sifatida hisoblagich ko'rsatkichlari va jihozlar ro'yxati kiritilgan Topshirish-qabul qilish akti imzolanadi.",
                    locale,
                    "Приложите к договору Акт приема-передачи с показаниями счетчиков и описью имущества.",
                ),
                "citations": store.resolve_ids(["inst_fk_535"], locale=locale),
            }
        )

    # Rule 7: Missing force majeure clause
    if not re.search(r"fors-major|форс-мажор|yengib bo'lmas kuch|непреодолим", low):
        score -= 5
        warnings.append(
            {
                "ruleId": "missing_force_majeure",
                "severity": "low",
                "spanStart": 0,
                "spanEnd": min(len(norm), 80),
                "quotedClause": norm[:80].strip(),
                "whyRisky": localize_text(
                    "Shartnomada fors-major (yengib bo'lmas kuch) holatlari bo'yicha javobgarlikdan ozod qilish bandi mavjud emas.",
                    locale,
                    "В договоре не прописана оговорка о форс-мажоре (обстоятельствах непреодолимой силы).",
                ),
                "safeAlternative": localize_text(
                    "Taraflar yengib bo'lmas kuch (fors-major) holatlari yuzaga kelganda majburiyatni kechiktirganlik uchun javobgarlikdan ozod etiladi.",
                    locale,
                    "Стороны освобождаются от ответственности за просрочку при наступлении обстоятельств непреодолимой силы.",
                ),
                "citations": store.resolve_ids(["inst_fk_242"], locale=locale),
            }
        )

    if not red_flags:
        safe_clauses.append(
            {
                "ruleId": "no_critical_traps",
                "severity": "safe",
                "quotedClause": norm[:140].strip(),
                "whyRisky": localize_text(
                    "Tanqidiy darajadagi yashirin jarima yoki bir tomonlama bekor qilish tuzoqlari topilmadi.",
                    locale,
                    "Критических ловушек одностороннего расторжения или скрытых штрафов не выявлено.",
                ),
                "safeAlternative": "",
                "citations": [],
            }
        )

    final_score = max(5, min(100, score))
    verdict = "safe" if final_score >= 75 else ("caution" if final_score >= 45 else "high_risk")
    lang_detected = "ru" if sum(1 for c in norm if "\u0400" <= c <= "\u04ff") > len(norm) * 0.25 else "uz_lat"

    return {
        "safetyScore": final_score,
        "verdict": verdict,
        "languageDetected": lang_detected,
        "redFlags": red_flags,
        "warnings": warnings,
        "safeClauses": safe_clauses,
        "engine": "deterministic",
    }
