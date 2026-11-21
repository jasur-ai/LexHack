"""Exact legal calculators, each grounded in the article that sets the rule and in the dated figures pack.

* ``fine``          — fines set in BHM multiples (from the article text or "10 BHM") -> so'm on a date
* ``state_duty``    — court and notary state duty (State Duty Law annex)
* ``alimony``       — child support shares and the per-child minimum (Family Code art. 99)
* ``wage_delay``    — compensation for late wages: 10% of the CB rate per day (Labour Code art. 333)
* ``tax_penalty``   — tax late-payment interest: 1/300 of the CB rate per day (Tax Code art. 110)
* ``severance``     — severance pay scale by length of service (Labour Code art. 173)
* ``vacation_pay``  — holiday pay: average monthly pay / 25.3 x paid days (Labour Code arts. 233, 257)
* ``income_tax``    — 12% personal income tax (Tax Code art. 381)
* ``deadline``      — end date of a statutory period (calendar rules of the codes; weekend/holiday shift)

Every result lists the inputs it used, the formula, the legal basis and — when inputs are missing — exactly what
to ask the person.
"""

from __future__ import annotations

import calendar
import math
import re
from dataclasses import dataclass, field
from datetime import date, timedelta

from lex_agent.assistant.entities import Entities
from lex_agent.knowledge.facts import FactsPack
from lex_agent.knowledge.lexicon import fold_uz

# ------------------------------------------------------------------------------------------------ number words

_UZ_UNITS = {"bir": 1, "ikki": 2, "uch": 3, "tort": 4, "besh": 5, "olti": 6, "yetti": 7, "sakkiz": 8, "tokkiz": 9}
_UZ_TENS = {"on": 10, "yigirma": 20, "ottiz": 30, "kirk": 40, "ellik": 50, "oltmish": 60, "yetmish": 70,
            "sakson": 80, "tokson": 90}


def uz_number(words: str) -> float | None:
    """'o'n besh' -> 15, 'yuz' -> 100, 'uch yuz' -> 300, 'bir yarim' -> 1.5 (folded or plain Uzbek Latin)."""
    toks = fold_uz(words).split()
    total = 0.0
    current = 0.0
    seen = False
    for t in toks:
        t = t.rstrip(",.;")
        base = t[:-1] if t.endswith(("i",)) and t[:-1] in {**_UZ_UNITS, **_UZ_TENS} else t
        if base in _UZ_UNITS:
            current += _UZ_UNITS[base]
            seen = True
        elif base in _UZ_TENS:
            current += _UZ_TENS[base]
            seen = True
        elif base in ("yuz", "юз"):
            current = (current or 1) * 100
            seen = True
        elif base == "ming":
            total += (current or 1) * 1000
            current = 0
            seen = True
        elif base == "yarim":
            current += 0.5
            seen = True
        elif t.isdigit():
            current += float(t)
            seen = True
        else:
            break
    return total + current if seen else None


_FINE_RE = re.compile(
    r"bazaviy hisoblash mikdorining\s+((?:[a-z]+\s+){0,3}?[a-z]+)\s+baravar(?:i|idan)(?:\s+(?:dan|gacha))?"
    r"(?:\s+((?:[a-z]+\s+){0,3}?[a-z]+)\s+baravarigacha)?",
)
_RU_FINE_RE = re.compile(r"(?:от\s+)?(\w+)(?:\s+до\s+(\w+))?\s+базов\w+\s+расч[её]тн\w+\s+величин", re.I)
_RU_NUMBERS = {
    "одной": 1, "одна": 1, "двух": 2, "трех": 3, "трёх": 3, "четырех": 4, "четырёх": 4, "пяти": 5, "шести": 6,
    "семи": 7, "восьми": 8, "девяти": 9, "десяти": 10, "пятнадцати": 15, "двадцати": 20, "тридцати": 30,
    "сорока": 40, "пятидесяти": 50, "семидесяти": 70, "ста": 100, "двухсот": 200, "трехсот": 300, "трёхсот": 300,
}


def fines_in_text(text: str) -> list[tuple[float, float | None]]:
    """BHM multiples stated in an article: [(from, to|None), ...] ('besh baravari' -> (5, None))."""
    out: list[tuple[float, float | None]] = []
    folded = fold_uz(text)
    for m in _FINE_RE.finditer(folded):
        low = uz_number(m.group(1))
        high = uz_number(m.group(2)) if m.group(2) else None
        if low:
            out.append((low, high))
    if not out:
        for m in _RU_FINE_RE.finditer(text.lower()):
            low = _RU_NUMBERS.get(m.group(1))
            high = _RU_NUMBERS.get(m.group(2)) if m.group(2) else None
            if low:
                out.append((float(low), float(high) if high else None))
    seen: set[tuple[float, float | None]] = set()
    return [f for f in out if not (f in seen or seen.add(f))]


# ------------------------------------------------------------------------------------------------ results


@dataclass(slots=True)
class CalcResult:
    kind: str
    ok: bool
    headline: dict[str, str] = field(default_factory=dict)  # lang -> direct answer sentence
    lines: dict[str, list[str]] = field(default_factory=dict)  # lang -> breakdown bullets
    missing: list[str] = field(default_factory=list)  # input names to ask for
    basis: list[tuple[str, str]] = field(default_factory=list)  # (doc, article) that set the rule
    facts: list[str] = field(default_factory=list)  # practical-facts ids used
    values: dict[str, float] = field(default_factory=dict)


def som(value: float) -> str:
    return f"{int(round(value)):,}".replace(",", "\u00a0") + "\u00a0soʻm"


def _rub(value: float) -> str:  # Russian formatting
    return f"{int(round(value)):,}".replace(",", "\u00a0") + "\u00a0сум"


def _L(uz: str, ru: str, en: str) -> dict[str, str]:
    return {"uz": uz, "ru": ru, "en": en}


ASK_TEXT: dict[str, dict[str, str]] = {
    "income": _L("oylik daromad (soʻmda)", "ежемесячный доход (в сумах)", "monthly income (UZS)"),
    "children": _L("bolalar soni", "количество детей", "number of children"),
    "amount": _L("summa (soʻmda)", "сумма (в сумах)", "amount (UZS)"),
    "days": _L("necha kun kechiktirilgani", "количество дней просрочки", "days of delay"),
    "monthly_wage": _L("oʻrtacha oylik ish haqi (soʻmda)", "среднемесячная зарплата (в сумах)", "average monthly pay (UZS)"),
    "years": _L("shu ish beruvchidagi ish staji (yil)", "стаж у этого работодателя (лет)", "years with this employer"),
    "claim_value": _L("daʼvo bahosi (soʻmda)", "цена иска (в сумах)", "claim value (UZS)"),
    "bhm_multiple": _L("jarima necha BHM ekani yoki huquqbuzarlik turi", "размер штрафа в БРВ или вид нарушения",
                       "the fine in BHM or the type of offence"),
    "start_date": _L("hisob boshlanadigan sana (kun.oy.yil)", "дата начала отсчёта (дд.мм.гггг)", "start date (dd.mm.yyyy)"),
    "deadline_kind": _L("qaysi muddat (masalan, apellyatsiya, maʼmuriy shikoyat)", "какой срок (например, апелляция)",
                        "which deadline (e.g. appeal)"),
    "duty_kind": _L("qaysi sud yoki notarial harakat (masalan, ajrashish, mulkiy daʼvo)",
                    "какой суд или нотариальное действие (например, развод, имущественный иск)",
                    "which court case or notarial act (e.g. divorce, property claim)"),
}


def _bhm(facts: FactsPack, on: date | None) -> tuple[float | None, str]:
    sv = facts.value_on("bhm", on)
    if not sv:
        return None, ""
    period = f"{sv.start:%d.%m.%Y}" if sv.start else ""
    return sv.value, period


# ------------------------------------------------------------------------------------------------ calculators


def calc_fine(facts: FactsPack, ent: Entities, *, article_text: str = "", on: date | None = None,
              basis: tuple[str, str] | None = None) -> CalcResult:
    on = on or (ent.dates[0] if ent.dates else date.today())
    bhm, since = _bhm(facts, on)
    res = CalcResult(kind="fine", ok=False, facts=["bhm"], basis=[basis] if basis else [])
    multiples: list[tuple[float, float | None]] = []
    if ent.bhm_multiple:
        multiples = [(ent.bhm_multiple, None)]
    elif article_text:
        multiples = fines_in_text(article_text)
    if not bhm:
        res.missing = ["start_date"]
        return res
    if not multiples:
        res.missing = ["bhm_multiple"]
        res.headline = _L(f"1 BHM = {som(bhm)} ({since} dan).", f"1 БРВ = {_rub(bhm)} (с {since}).",
                          f"1 BHM = UZS {int(bhm):,} (since {since}).")
        return res
    res.ok = True
    uz, ru, en = [], [], []
    for low, high in multiples[:6]:
        if high:
            uz.append(f"BHMning {low:g}–{high:g} baravari = {som(low * bhm)} – {som(high * bhm)}")
            ru.append(f"от {low:g} до {high:g} БРВ = {_rub(low * bhm)} – {_rub(high * bhm)}")
            en.append(f"{low:g}–{high:g} × BHM = UZS {int(low * bhm):,} – {int(high * bhm):,}")
        else:
            uz.append(f"BHMning {low:g} baravari = {som(low * bhm)}")
            ru.append(f"{low:g} БРВ = {_rub(low * bhm)}")
            en.append(f"{low:g} × BHM = UZS {int(low * bhm):,}")
    first_low, first_high = multiples[0]
    amount = som(first_low * bhm) + (f" – {som(first_high * bhm)}" if first_high else "")
    amount_ru = _rub(first_low * bhm) + (f" – {_rub(first_high * bhm)}" if first_high else "")
    amount_en = f"UZS {int(first_low * bhm):,}" + (f" – {int(first_high * bhm):,}" if first_high else "")
    note = len(multiples) > 1
    res.headline = _L(
        f"Jarima {amount}" + (" (birinchi holat; boshqa holatlar quyida)" if note else "")
        + f" — 1 BHM {som(bhm)} ({since} dan) boʻyicha.",
        f"Штраф {amount_ru}" + (" (первый случай; остальные ниже)" if note else "")
        + f" — исходя из БРВ {_rub(bhm)} (с {since}).",
        f"The fine is {amount_en}" + (" (first case; others below)" if note else "")
        + f", using BHM = UZS {int(bhm):,} (since {since}).",
    )
    res.lines = {"uz": uz, "ru": ru, "en": en}
    res.values = {"bhm": bhm, "first_low": first_low * bhm}
    return res


_DUTY_KEYS = [
    ("appeal_fee", r"apell?yats|apelyats|kassats|апелляц|кассац|\bappeal"),
    ("divorce_repeat", r"takroriy~ajra|ikkinchi (?:marta )?ajra|povtorn|повторн\w*~(?:развод|брак)"),
    ("divorce", r"ajra|talok|nikoh\w*~bekor|razvod|развод|расторжени\w* брак|divorce"),
    ("economic_property_claim", r"iktisodiy sud|хозяйствен|экономическ\w* суд|economic court"),
    ("notary_will", r"vasiyat|завещан|\bwill\b"),
    ("inheritance_certificate_fee", r"meros\w*~guvohnoma|свидетельств\w* о праве на наслед|inheritance certificate"),
    ("notary_real_estate_city", r"notarius\w*~(?:uy|kvartira|kochmas)|(?:uy|kvartira|kochmas)\w*~notarius|"
                                r"нотариус\w*~(?:квартир|недвиж|дом)|(?:квартир|недвиж)\w*~нотариус|notar\w*~(?:house|flat|property)"),
    ("notary_loan", r"kar[zs] shartnoma\w*~notarius|notarius\w*~kar[zs]|нотариус\w*~займ"),
    ("admin_court_citizen", r"mamuriy sud|административн\w* суд|administrative court"),
    ("special_proceedings", r"alohida tartib|особ\w* производств|fakt(?:ni)? aniklash"),
    ("civil_property_claim", r"davo|sudga|иск|суд|lawsuit|claim|court"),
]


def duty_kind(question: str) -> str | None:
    from lex_agent.knowledge.lexicon import _GAP

    folded = fold_uz(question) + " " + (question or "").lower()
    for kind, pattern in _DUTY_KEYS:
        if re.search(pattern.replace("~", _GAP), folded, re.I):
            return kind
    return None


def calc_state_duty(facts: FactsPack, ent: Entities, question: str, *, on: date | None = None) -> CalcResult:
    on = on or date.today()
    bhm, since = _bhm(facts, on)
    kind = duty_kind(question)
    res = CalcResult(kind="state_duty", ok=False, facts=["bhm", "state_duty"], basis=[("4680944", "annex")])
    if not kind or kind not in facts.state_duty:
        res.missing = ["duty_kind"]
        return res
    item = facts.state_duty[kind]
    if not bhm:
        res.missing = ["start_date"]
        return res
    texts = {k: facts.text(item, k) for k in ("uz", "ru", "en")}
    if "percent" in item:
        claim = max(ent.amounts) if ent.amounts else None
        if claim is None:
            res.missing = ["claim_value"]
            res.headline = {k: v for k, v in texts.items()}
            return res
        duty = max(claim * float(item["percent"]) / 100, float(item.get("min_bhm", 0)) * bhm)
        res.ok = True
        res.values = {"claim": claim, "duty": duty}
        res.headline = _L(
            f"Davlat boji: {som(duty)} (daʼvo bahosi {som(claim)} × {item['percent']}%, lekin kamida "
            f"{item.get('min_bhm', 0)} BHM).",
            f"Госпошлина: {_rub(duty)} ({item['percent']}% от цены иска {_rub(claim)}, но не менее "
            f"{item.get('min_bhm', 0)} БРВ).",
            f"State duty: UZS {int(duty):,} ({item['percent']}% of the UZS {int(claim):,} claim, at least "
            f"{item.get('min_bhm', 0)} × BHM).",
        )
    elif "share" in item:
        # Appeals pay half of the first-instance rate of the same kind of case
        base_kind = duty_kind(re.sub(r"(?i)apell?yats\w*|apelyats\w*|kassats\w*|апелляц\w*|кассац\w*|appeal\w*", " ", question))
        base_item = facts.state_duty.get(base_kind or "") if base_kind != "appeal_fee" else None
        if base_item is None or "percent" in base_item:
            claim = max(ent.amounts) if ent.amounts else None
            if claim is None:
                res.missing = ["claim_value"]
                res.headline = {k: v for k, v in texts.items()}
                return res
            pct = float((base_item or facts.state_duty["civil_property_claim"])["percent"])
            first = max(claim * pct / 100, bhm)
        else:
            first = float(base_item["bhm"]) * bhm
        duty = first * float(item["share"])
        res.ok = True
        res.values = {"duty": duty}
        res.headline = _L(
            f"Shikoyat uchun davlat boji: {som(duty)} (birinchi instansiya stavkasining 50%i: {som(first)}).",
            f"Госпошлина за жалобу: {_rub(duty)} (50% от ставки первой инстанции {_rub(first)}).",
            f"Duty for the appeal: UZS {int(duty):,} (50% of the first-instance UZS {int(first):,}).",
        )
    else:
        duty = float(item["bhm"]) * bhm
        res.ok = True
        res.values = {"duty": duty}
        res.headline = _L(
            f"Davlat boji: {som(duty)} (BHMning {item['bhm']:g} {'baravari' if item['bhm'] >= 1 else 'qismi'}; "
            f"1 BHM = {som(bhm)}, {since} dan).",
            f"Госпошлина: {_rub(duty)} ({item['bhm']:g} БРВ; 1 БРВ = {_rub(bhm)} с {since}).",
            f"State duty: UZS {int(duty):,} ({item['bhm']:g} × BHM; BHM = UZS {int(bhm):,} since {since}).",
        )
    res.lines = {k: [v] for k, v in texts.items()}
    return res


def calc_alimony(facts: FactsPack, ent: Entities) -> CalcResult:
    res = CalcResult(kind="alimony", ok=False, facts=["mhtekm", "alimony"], basis=[("104720", "99")])
    children = ent.children or 1
    share = {1: 0.25, 2: 1 / 3}.get(children, 0.5)
    share_txt = {1: ("toʻrtdan bir (25%)", "1/4 (25%)", "1/4 (25%)"), 2: ("uchdan bir (33,3%)", "1/3 (33,3%)", "1/3 (33.3%)")}.get(
        children, ("yarmi (50%)", "1/2 (50%)", "1/2 (50%)"))
    mh = facts.current("mhtekm")
    minimum = 0.265 * mh.value * children if mh else None
    income = max(ent.amounts) if ent.amounts else None
    lines_uz = [f"{children} bola uchun ulush: daromadning {share_txt[0]}"]
    lines_ru = [f"Доля на {children} детей: {share_txt[1]} дохода"]
    lines_en = [f"Share for {children} child(ren): {share_txt[2]} of income"]
    if minimum:
        lines_uz.append(f"Eng kam miqdor: har bir bola uchun MHTEKMning 26,5% = {som(0.265 * mh.value)} (jami {som(minimum)})")
        lines_ru.append(f"Минимум: 26,5% МРОТ на каждого ребёнка = {_rub(0.265 * mh.value)} (всего {_rub(minimum)})")
        lines_en.append(f"Minimum: 26.5% of the minimum wage per child = UZS {int(0.265 * mh.value):,} (total UZS {int(minimum):,})")
    res.lines = {"uz": lines_uz, "ru": lines_ru, "en": lines_en}
    if not ent.children:
        res.missing.append("children")
    if income is None:
        res.missing.append("income")
        res.headline = _L(
            f"Aliment: {children} bola uchun daromadning {share_txt[0]}, lekin har bir bolaga kamida "
            f"{som(0.265 * mh.value) if mh else 'MHTEKMning 26,5%'}.",
            f"Алименты: на {children} детей — {share_txt[1]} дохода, но не менее "
            f"{_rub(0.265 * mh.value) if mh else '26,5% МРОТ'} на каждого ребёнка.",
            f"Child support: {share_txt[2]} of income for {children} child(ren), at least "
            f"UZS {int(0.265 * mh.value):,} per child." if mh else "Child support shares apply.",
        )
        return res
    amount = income * share
    if minimum and amount < minimum:
        amount = minimum
    res.ok = True
    res.values = {"income": income, "amount": amount}
    res.headline = _L(
        f"Oyiga taxminan {som(amount)} ({som(income)} daromadning {share_txt[0]}); sud miqdorni ahvolga qarab "
        f"oʻzgartirishi mumkin.",
        f"Около {_rub(amount)} в месяц ({share_txt[1]} от дохода {_rub(income)}); суд может изменить размер.",
        f"About UZS {int(amount):,} a month ({share_txt[2]} of UZS {int(income):,}); the court may adjust it.",
    )
    return res


def calc_wage_delay(facts: FactsPack, ent: Entities) -> CalcResult:
    res = CalcResult(kind="wage_delay", ok=False, facts=["cbu_rate", "wage_delay"], basis=[("6257288", "333")])
    rate = facts.current("cbu_rate")
    days = ent.duration_days()
    amount = max(ent.amounts) if ent.amounts else None
    if amount is None:
        res.missing.append("amount")
    if days is None:
        res.missing.append("days")
    if not rate:
        return res
    daily = rate.value * 0.10  # percent per day
    res.lines = {
        "uz": [f"Kunlik kompensatsiya: Markaziy bank stavkasi {rate.value:g}% × 10% = kuniga {daily:g}%"],
        "ru": [f"Компенсация в день: ставка ЦБ {rate.value:g}% × 10% = {daily:g}% в день"],
        "en": [f"Daily compensation: CB rate {rate.value:g}% × 10% = {daily:g}% per day"],
    }
    if res.missing:
        res.headline = _L(
            f"Har bir kechiktirilgan kun uchun qarz summasining {daily:g}% miqdorida kompensatsiya toʻlanadi.",
            f"За каждый день задержки — компенсация {daily:g}% от суммы долга.",
            f"Compensation is {daily:g}% of the unpaid amount per day of delay.",
        )
        return res
    assert amount is not None and days is not None
    comp = amount * daily / 100 * days
    res.ok = True
    res.values = {"amount": amount, "days": days, "compensation": comp}
    res.headline = _L(
        f"Kompensatsiya: {som(comp)} ({som(amount)} × {daily:g}% × {days:g} kun), qarzning oʻzidan tashqari.",
        f"Компенсация: {_rub(comp)} ({_rub(amount)} × {daily:g}% × {days:g} дн.) сверх самой задолженности.",
        f"Compensation: UZS {int(comp):,} (UZS {int(amount):,} × {daily:g}% × {days:g} days) on top of the debt.",
    )
    return res


def calc_tax_penalty(facts: FactsPack, ent: Entities) -> CalcResult:
    res = CalcResult(kind="tax_penalty", ok=False, facts=["cbu_rate", "tax_penalty"], basis=[("4674902", "110")])
    rate = facts.current("cbu_rate")
    days = ent.duration_days()
    amount = max(ent.amounts) if ent.amounts else None
    if amount is None:
        res.missing.append("amount")
    if days is None:
        res.missing.append("days")
    if not rate:
        return res
    daily = rate.value / 300
    res.lines = {
        "uz": [f"Kunlik penya: Markaziy bank stavkasi {rate.value:g}% ÷ 300 = kuniga {daily:.4f}%"],
        "ru": [f"Пеня в день: ставка ЦБ {rate.value:g}% ÷ 300 = {daily:.4f}% в день"],
        "en": [f"Daily penalty: CB rate {rate.value:g}% ÷ 300 = {daily:.4f}% per day"],
    }
    if res.missing:
        res.headline = _L(
            f"Kechiktirilgan har bir kun uchun toʻlanmagan soliqning {daily:.4f}% miqdorida penya hisoblanadi.",
            f"За каждый день просрочки начисляется пеня {daily:.4f}% от неуплаченного налога.",
            f"Penalty interest is {daily:.4f}% of the unpaid tax per day.",
        )
        return res
    assert amount is not None and days is not None
    pen = amount * daily / 100 * days
    res.ok = True
    res.values = {"amount": amount, "days": days, "penalty": pen}
    res.headline = _L(
        f"Penya: {som(pen)} ({som(amount)} × {daily:.4f}% × {days:g} kun).",
        f"Пеня: {_rub(pen)} ({_rub(amount)} × {daily:.4f}% × {days:g} дн.).",
        f"Penalty: UZS {int(pen):,} (UZS {int(amount):,} × {daily:.4f}% × {days:g} days).",
    )
    return res


_SEVERANCE = [(3, 0.5), (5, 0.75), (10, 1.0), (15, 1.5), (math.inf, 2.0)]


def calc_severance(facts: FactsPack, ent: Entities) -> CalcResult:
    res = CalcResult(kind="severance", ok=False, facts=["severance"], basis=[("6257288", "173")])
    years = ent.duration_years()
    wage = max(ent.amounts) if ent.amounts else None
    scale_uz = "3 yilgacha 50%, 3–5 yil 75%, 5–10 yil 100%, 10–15 yil 150%, 15 yildan ortiq 200%"
    scale_ru = "до 3 лет — 50%, 3–5 лет — 75%, 5–10 лет — 100%, 10–15 лет — 150%, свыше 15 лет — 200%"
    scale_en = "under 3 years 50%, 3–5 years 75%, 5–10 years 100%, 10–15 years 150%, over 15 years 200%"
    res.lines = {"uz": [f"Oʻrtacha oylik ish haqiga nisbatan: {scale_uz}"], "ru": [f"От среднемесячной зарплаты: {scale_ru}"],
                 "en": [f"Of average monthly pay: {scale_en}"]}
    if years is None:
        res.missing.append("years")
    if wage is None:
        res.missing.append("monthly_wage")
    if res.missing:
        res.headline = _L(f"Ishdan boʻshatish nafaqasi stajga bogʻliq: {scale_uz} (kamida).",
                          f"Выходное пособие зависит от стажа: {scale_ru} (не менее).",
                          f"Severance depends on service: {scale_en} (minimum).")
        return res
    assert years is not None and wage is not None
    pct = next(p for limit, p in _SEVERANCE if years < limit)
    amount = wage * pct
    res.ok = True
    res.values = {"years": years, "wage": wage, "amount": amount}
    res.headline = _L(
        f"Kamida {som(amount)} ({years:g} yillik staj uchun oʻrtacha oylikning {int(pct * 100)}%i).",
        f"Не менее {_rub(amount)} ({int(pct * 100)}% среднемесячной зарплаты при стаже {years:g} лет).",
        f"At least UZS {int(amount):,} ({int(pct * 100)}% of average monthly pay for {years:g} years).",
    )
    return res


def calc_vacation_pay(facts: FactsPack, ent: Entities) -> CalcResult:
    res = CalcResult(kind="vacation_pay", ok=False, facts=["vacation_pay"], basis=[("6257288", "233"), ("6257288", "257")])
    wage = max(ent.amounts) if ent.amounts else None
    days = ent.duration_days() or 21
    paid_days = round(days * 6 / 7) if not ent.dates else days
    if wage is None:
        res.missing.append("monthly_wage")
        res.headline = _L("Taʼtil puli = oʻrtacha oylik ish haqi ÷ 25,3 × haq toʻlanadigan kunlar (yakshanbalar hisobga olinmaydi).",
                          "Отпускные = среднемесячная зарплата ÷ 25,3 × оплачиваемые дни (воскресенья не оплачиваются).",
                          "Holiday pay = average monthly pay ÷ 25.3 × paid days (Sundays are not paid).")
        return res
    daily = wage / 25.3
    pay = daily * paid_days
    res.ok = True
    res.values = {"wage": wage, "days": days, "paid_days": paid_days, "pay": pay}
    res.headline = _L(
        f"Taxminan {som(pay)}: {som(wage)} ÷ 25,3 = kuniga {som(daily)} × {paid_days:g} kun "
        f"({days:g} kalendar kundan yakshanbalarsiz).",
        f"Около {_rub(pay)}: {_rub(wage)} ÷ 25,3 = {_rub(daily)} в день × {paid_days:g} дн. "
        f"(из {days:g} календарных дней без воскресений).",
        f"About UZS {int(pay):,}: UZS {int(wage):,} ÷ 25.3 = UZS {int(daily):,} a day × {paid_days:g} days "
        f"({days:g} calendar days without Sundays).",
    )
    return res


def calc_income_tax(facts: FactsPack, ent: Entities) -> CalcResult:
    res = CalcResult(kind="income_tax", ok=False, facts=["income_tax"], basis=[("4674902", "381")])
    amount = max(ent.amounts) if ent.amounts else None
    if amount is None:
        res.missing.append("amount")
        res.headline = _L("Rezident jismoniy shaxslar daromadiga 12% soliq solinadi (dividend va foizlarga 5%).",
                          "Доходы резидентов облагаются по ставке 12% (дивиденды и проценты — 5%).",
                          "Residents' income is taxed at 12% (dividends and interest at 5%).")
        return res
    tax = amount * 0.12
    res.ok = True
    res.values = {"amount": amount, "tax": tax, "net": amount - tax}
    res.headline = _L(f"Soliq {som(tax)} (12%), qoʻlga {som(amount - tax)}.",
                      f"Налог {_rub(tax)} (12%), на руки {_rub(amount - tax)}.",
                      f"Tax UZS {int(tax):,} (12%), net UZS {int(amount - tax):,}.")
    return res


# ------------------------------------------------------------------------------------------------ deadlines

_FIXED_HOLIDAYS = {(1, 1), (3, 8), (3, 21), (5, 9), (9, 1), (10, 1), (12, 8)}  # Labour Code art. 208

_DEADLINE_KEYS = [
    ("admin_complaint", r"mamuriy~(?:shikoyat|jarima|karor)|jarima\w*~shikoyat|административн\w*~(?:жалоб|обжал)|штраф\w*~обжал"),
    ("cassation_civil", r"kassats|кассац|cassation"),
    ("appeal_civil", r"apell?yats|apelyats|sud karor\w*~shikoyat|апелляц|appeal"),
    ("labour_reinstatement", r"ishga tiklan|kayta tiklan|восстановлен\w* на работ|reinstat"),
    ("labour_dispute", r"mehnat nizo|трудов\w* спор|labou?r dispute"),
    ("inheritance_certificate", r"meros|наслед|inherit"),
    ("state_body_reply", r"muroja+t|ariza\w*~javob|обращени|жалоб\w*~госорган|petition"),
    ("resignation_notice", r"oz hohish|ishdan ket|по собственному|уволит|resign"),
    ("limitation_general", r"davo muddat|исков\w* давност|limitation"),
]


def deadline_kind(question: str) -> str | None:
    from lex_agent.knowledge.lexicon import _GAP

    folded = fold_uz(question) + " " + (question or "").lower()
    for kind, pattern in _DEADLINE_KEYS:
        if re.search(pattern.replace("~", _GAP), folded, re.I):
            return kind
    return None


def _add_months(d: date, months: int) -> date:
    m = d.month - 1 + months
    y = d.year + m // 12
    m = m % 12 + 1
    day = min(d.day, calendar.monthrange(y, m)[1])
    return date(y, m, day)


def _is_day_off(d: date, facts: FactsPack | None) -> bool:
    if d.weekday() >= 5:
        return True
    if facts is not None and (facts.fixed_holidays or facts.movable_holidays):
        return facts.is_holiday(d)
    return (d.month, d.day) in _FIXED_HOLIDAYS


def next_working_day(d: date, facts: FactsPack | None = None) -> date:
    while _is_day_off(d, facts):
        d += timedelta(days=1)
    return d


def deadline_end(start: date, *, days: int = 0, months: int = 0, years: int = 0,
                 facts: FactsPack | None = None) -> tuple[date, date]:
    """(raw end, end shifted to the next working day) for a period counted from ``start``.

    A period in days ends on the last day counted from the day after ``start``; a period in months or years ends
    on the same date of the last month; a period ending on a day off moves to the next working day."""
    if years:
        raw = _add_months(start, 12 * years)
    elif months:
        raw = _add_months(start, months)
    else:
        raw = start + timedelta(days=days)
    return raw, next_working_day(raw, facts)


def calc_deadline(facts: FactsPack, ent: Entities, question: str) -> CalcResult:
    kind = deadline_kind(question)
    res = CalcResult(kind="deadline", ok=False, facts=["deadlines"])
    period: dict[str, int] = {}
    if kind and kind in facts.deadlines:
        item = facts.deadlines[kind]
        res.basis = [(str(item["doc"]), str(item["article"]))]
        res.lines = {k: [facts.text(item, k)] for k in ("uz", "ru", "en")}
        period = {"days": int(item.get("days", 0)), "months": int(item.get("months", 0)), "years": int(item.get("years", 0))}
    elif ent.durations:
        # The question states the period itself ("10 kun ichida", "в течение 1 месяца")
        value, unit = ent.durations[0]
        n = int(value)
        period = {"day": {"days": n}, "week": {"days": 7 * n}, "month": {"months": n}, "year": {"years": n}}[unit]
        res.facts = []
    else:
        res.missing.append("deadline_kind")
        if not ent.dates:
            res.missing.append("start_date")
        return res
    if not ent.dates:
        res.missing.append("start_date")
        if res.lines:
            res.headline = {k: res.lines[k][0] for k in ("uz", "ru", "en")}
        return res
    start = ent.dates[0]
    raw, end = deadline_end(start, days=period.get("days", 0), months=period.get("months", 0),
                            years=period.get("years", 0), facts=facts)
    res.ok = True
    shifted = end != raw
    res.values = {"days_left": float((end - date.today()).days)}
    tentative = [facts.tentative_holiday(raw + timedelta(days=i)) for i in range((end - raw).days + 1)]
    tentative = [t for t in tentative if t]
    if tentative:
        t = tentative[0]
        for k, tail in (("uz", "sanasi hali rasman eʼlon qilinmagan, muddatni qayta tekshiring"),
                        ("ru", "дата ещё официально не объявлена, перепроверьте срок"),
                        ("en", "its date is not yet official; re-check the deadline")):
            res.lines.setdefault(k, []).append(f"{t.get(k, t.get('uz'))}: {tail}.")
    res.headline = _L(
        f"Muddat {end:%d.%m.%Y} kuni tugaydi" + (f" ({raw:%d.%m.%Y} dam olish yoki bayram kuni boʻlgani uchun keyingi ish kuniga koʻchadi)" if shifted else "")
        + f"; hisob {start:%d.%m.%Y} dan keyingi kundan boshlanadi.",
        f"Срок истекает {end:%d.%m.%Y}" + (f" ({raw:%d.%m.%Y} — нерабочий день, срок переносится)" if shifted else "")
        + f"; отсчёт со дня, следующего за {start:%d.%m.%Y}.",
        f"The deadline ends on {end:%d.%m.%Y}" + (f" ({raw:%d.%m.%Y} is a non-working day)" if shifted else "")
        + f"; counting starts the day after {start:%d.%m.%Y}.",
    )
    return res


CALCULATORS = ("fine", "state_duty", "alimony", "wage_delay", "tax_penalty", "severance", "vacation_pay",
               "income_tax", "deadline")


def run(kind: str, facts: FactsPack, ent: Entities, question: str, *, article_text: str = "",
        basis: tuple[str, str] | None = None) -> CalcResult:
    if kind == "fine":
        return calc_fine(facts, ent, article_text=article_text, basis=basis)
    if kind == "state_duty":
        return calc_state_duty(facts, ent, question)
    if kind == "alimony":
        return calc_alimony(facts, ent)
    if kind == "wage_delay":
        return calc_wage_delay(facts, ent)
    if kind == "tax_penalty":
        return calc_tax_penalty(facts, ent)
    if kind == "severance":
        return calc_severance(facts, ent)
    if kind == "vacation_pay":
        return calc_vacation_pay(facts, ent)
    if kind == "income_tax":
        return calc_income_tax(facts, ent)
    if kind == "deadline":
        return calc_deadline(facts, ent, question)
    raise ValueError(f"Unknown calculator: {kind}")
