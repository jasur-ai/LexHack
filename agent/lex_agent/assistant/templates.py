"""Document templates people ask for most, each tied to the articles that define its required contents.

Templates are short skeletons with placeholders in square brackets; the answer lists what must be filled in and
cites the legal basis, so the person can complete the document and check it against the law.
"""

from __future__ import annotations

from dataclasses import dataclass

from lex_agent.language.transliterator import latin_to_cyrillic


@dataclass(frozen=True, slots=True)
class Template:
    kind: str
    basis: tuple[tuple[str, str], ...]
    title: dict[str, str]
    body: dict[str, str]
    notes: dict[str, list[str]]


TEMPLATES: dict[str, Template] = {
    "lawsuit": Template(
        "lawsuit",
        (("3517337", "189"), ("3517337", "191"), ("4680944", "annex")),
        {"uz": "Daʼvo arizasi (fuqarolik ishi)", "ru": "Исковое заявление (гражданское дело)", "en": "Statement of claim (civil case)"},
        {
            "uz": "[Sud nomi]ga\nDaʼvogar: [F.I.Sh., manzil, telefon]\nJavobgar: [F.I.Sh. yoki tashkilot nomi, manzil]\n"
                  "Daʼvo bahosi: [summa] soʻm\n\nDAʼVO ARIZASI\n[Nizo mazmuni: nima boʻldi, qachon, qanday huquqingiz buzildi]\n"
                  "[Holatlarni tasdiqlovchi dalillar: hujjatlar, guvohlar]\n\nShularga asosan SOʻRAYMAN:\n1. [Talab: masalan, "
                  "qarz summasini undirish]\n\nIlova: daʼvo arizasi nusxasi, davlat boji toʻlangani haqida hujjat, dalillar nusxalari.\n"
                  "[Sana]                [Imzo]",
            "ru": "В [наименование суда]\nИстец: [ФИО, адрес, телефон]\nОтветчик: [ФИО или наименование организации, адрес]\n"
                  "Цена иска: [сумма] сум\n\nИСКОВОЕ ЗАЯВЛЕНИЕ\n[Суть спора: что произошло, когда, какое право нарушено]\n"
                  "[Доказательства: документы, свидетели]\n\nНа основании изложенного ПРОШУ:\n1. [Требование: например, взыскать "
                  "сумму долга]\n\nПриложения: копия иска, документ об уплате госпошлины, копии доказательств.\n[Дата]                [Подпись]",
        },
        {
            "uz": ["Arizada sud nomi, taraflar, daʼvo mazmuni, dalillar, daʼvo bahosi va ilovalar boʻlishi shart",
                   "Davlat boji: mulkiy daʼvo — daʼvo bahosining 4%, kamida 1 BHM"],
            "ru": ["В иске обязательны: суд, стороны, суть требований, доказательства, цена иска и приложения",
                   "Госпошлина: имущественный иск — 4% цены иска, не менее 1 БРВ"],
            "en": ["The claim must name the court and parties and state the demand, evidence, claim value and annexes",
                   "Court fee: property claims — 4% of the claim value, at least 1 × BHM"],
        },
    ),
    "alimony_claim": Template(
        "alimony_claim",
        (("104720", "99"), ("104720", "136"), ("3517337", "186"), ("3517337", "170")),
        {"uz": "Aliment undirish haqida daʼvo arizasi", "ru": "Иск о взыскании алиментов", "en": "Claim for child support"},
        {
            "uz": "[Tuman (shahar) sudi]ga\nDaʼvogar: [F.I.Sh., manzil]\nJavobgar: [F.I.Sh., manzil, ish joyi]\n\n"
                  "ALIMENT UNDIRISH HAQIDA DAʼVO ARIZASI\nJavobgar bilan [nikohda boʻlganmiz / nikohdan ajrashganmiz]. "
                  "Bizning [soni] nafar voyaga yetmagan farzandimiz bor: [ismi, tugʻilgan sanasi]. Javobgar bolalar "
                  "taʼminotiga ixtiyoriy yordam bermayapti.\n\nOila kodeksining 99-moddasiga asosan SOʻRAYMAN:\n"
                  "Javobgardan bolalar taʼminoti uchun har oylik ish haqi va boshqa daromadining [1/4, 1/3 yoki 1/2] qismi "
                  "miqdorida aliment undirilsin.\n\nIlova: bolalarning tugʻilganlik guvohnomalari nusxasi, nikoh "
                  "(ajrashish) guvohnomasi nusxasi, javobgarning daromadi haqida maʼlumot (boʻlsa).\n[Sana]   [Imzo]",
            "ru": "В [районный (городской) суд]\nИстец: [ФИО, адрес]\nОтветчик: [ФИО, адрес, место работы]\n\n"
                  "ИСКОВОЕ ЗАЯВЛЕНИЕ О ВЗЫСКАНИИ АЛИМЕНТОВ\nС ответчиком [состоим в браке / брак расторгнут]. У нас [число] "
                  "несовершеннолетних детей: [имя, дата рождения]. Добровольно ответчик на содержание детей не помогает.\n\n"
                  "На основании ст. 99 Семейного кодекса ПРОШУ:\nвзыскать с ответчика алименты на содержание детей в размере "
                  "[1/4, 1/3 или 1/2] заработка и иного дохода ежемесячно.\n\nПриложения: копии свидетельств о рождении детей, "
                  "свидетельства о браке (разводе), сведения о доходе ответчика (при наличии).\n[Дата]   [Подпись]",
        },
        {
            "uz": ["Aliment arizani bolaning yashash joyidagi sudga ham berish mumkin",
                   "Tez yoʻl: aliment uchun sud buyrugʻi soʻrab ariza berish mumkin (nizo boʻlmasa)",
                   "Har bir bola uchun aliment MHTEKMning 26,5%idan kam boʻlmaydi"],
            "ru": ["Иск об алиментах можно подать и по месту жительства истца",
                   "Быстрый путь: заявление о выдаче судебного приказа (если нет спора)",
                   "На каждого ребёнка — не менее 26,5% МРОТ"],
            "en": ["You may also file where the child lives", "Faster route: apply for a court order if there is no dispute",
                   "At least 26.5% of the minimum wage per child"],
        },
    ),
    "reinstatement_claim": Template(
        "reinstatement_claim",
        (("6257288", "174"), ("6257288", "560"), ("6257288", "562"), ("6257288", "564")),
        {"uz": "Ishga tiklash haqida daʼvo arizasi", "ru": "Иск о восстановлении на работе", "en": "Claim for reinstatement"},
        {
            "uz": "[Fuqarolik ishlari boʻyicha tuman (shahar) sudi]ga\nDaʼvogar: [F.I.Sh., manzil]\nJavobgar: [ish beruvchi "
                  "nomi, manzil]\n\nISHGA TIKLASH HAQIDA DAʼVO ARIZASI\nMen [sana]dan [lavozim] boʻlib ishlaganman. [Sana]dagi "
                  "[raqam]-sonli buyruq bilan [asos] boʻyicha ishdan boʻshatildim. Boʻshatish qonunga xilof, chunki [sabablar: "
                  "asos yoʻq, ogohlantirilmaganman, kasaba uyushmasi bilan kelishilmagan va h.k.].\n\nSOʻRAYMAN:\n1. Meni "
                  "avvalgi ishimga tiklash.\n2. Majburiy progul vaqti uchun oʻrtacha ish haqini undirish.\n3. Maʼnaviy "
                  "ziyonni qoplash ([summa] soʻm).\n\nIlova: buyruq nusxasi, mehnat shartnomasi nusxasi, boshqa dalillar.\n[Sana]   [Imzo]",
            "ru": "В [районный (городской) суд по гражданским делам]\nИстец: [ФИО, адрес]\nОтветчик: [работодатель, адрес]\n\n"
                  "ИСКОВОЕ ЗАЯВЛЕНИЕ О ВОССТАНОВЛЕНИИ НА РАБОТЕ\nС [дата] я работал(а) [должность]. Приказом № [номер] от [дата] "
                  "уволен(а) по [основание]. Увольнение незаконно, потому что [причины: нет основания, не предупредили, не "
                  "согласовано с профкомом и т. п.].\n\nПРОШУ:\n1. Восстановить меня на прежней работе.\n2. Взыскать средний "
                  "заработок за время вынужденного прогула.\n3. Взыскать компенсацию морального вреда ([сумма] сум).\n\n"
                  "Приложения: копия приказа, копия трудового договора, иные доказательства.\n[Дата]   [Подпись]",
        },
        {
            "uz": ["Muddat: boʻshatish buyrugʻi nusxasi berilgan kundan 3 oy", "Xodimlar mehnat nizolari boʻyicha sud xarajatlaridan ozod"],
            "ru": ["Срок: 3 месяца со дня вручения копии приказа", "Работники освобождены от судебных расходов по трудовым спорам"],
            "en": ["Deadline: 3 months from receiving the dismissal order", "Employees are exempt from court costs in labour disputes"],
        },
    ),
    "resignation": Template(
        "resignation",
        (("6257288", "160"), ("6257288", "254")),
        {"uz": "Oʻz xohishiga koʻra ishdan boʻshash haqida ariza", "ru": "Заявление об увольнении по собственному желанию",
         "en": "Resignation letter"},
        {
            "uz": "[Tashkilot nomi] rahbari [F.I.Sh.]ga\n[Lavozim] [F.I.Sh.]dan\n\nARIZA\nMehnat kodeksining 160-moddasiga "
                  "asosan meni [sana]dan oʻz xohishimga koʻra ishdan boʻshatishingizni soʻrayman.\n[Sana]   [Imzo]",
            "ru": "Руководителю [наименование организации] [ФИО]\nот [должность] [ФИО]\n\nЗАЯВЛЕНИЕ\nНа основании статьи 160 "
                  "Трудового кодекса прошу уволить меня по собственному желанию с [дата].\n[Дата]   [Подпись]",
        },
        {
            "uz": ["Ish beruvchini kamida 14 kalendar kun oldin yozma ogohlantiring",
                   "Arizani ikki nusxada yozing va qabul qilingani haqida belgi qoʻydiring",
                   "Hisob-kitob oxirgi ish kunida toʻlanadi"],
            "ru": ["Предупредите работодателя письменно не менее чем за 14 календарных дней",
                   "Сделайте два экземпляра и получите отметку о приёме", "Расчёт выплачивается в последний рабочий день"],
            "en": ["Give at least 14 calendar days' written notice", "Keep a copy stamped as received",
                   "Final pay is due on the last working day"],
        },
    ),
    "consumer_claim": Template(
        "consumer_claim",
        (("4704", "13"), ("4704", "14"), ("4704", "17"), ("4704", "18")),
        {"uz": "Sotuvchiga talabnoma (pretenziya)", "ru": "Претензия продавцу", "en": "Complaint letter to a seller"},
        {
            "uz": "[Sotuvchi nomi, manzil]ga\nIsteʼmolchi: [F.I.Sh., manzil, telefon]\n\nTALABNOMA\n[Sana]da [tovar nomi]ni "
                  "[narx] soʻmga sotib oldim (chek №[raqam]). Tovarda [kamchilik] aniqlandi.\n\"Isteʼmolchilarning "
                  "huquqlarini himoya qilish toʻgʻrisida\"gi Qonunning 13-moddasiga asosan [tovarni almashtirishni / "
                  "pulni qaytarishni / kamchilikni bepul tuzatishni] talab qilaman.\nJavobni [muddat] ichida yozma berishingizni soʻrayman.\n"
                  "Ilova: chek nusxasi, kafolat taloni nusxasi.\n[Sana]   [Imzo]",
            "ru": "[Наименование продавца, адрес]\nПотребитель: [ФИО, адрес, телефон]\n\nПРЕТЕНЗИЯ\n[Дата] я купил(а) [товар] за "
                  "[цена] сум (чек № [номер]). В товаре обнаружен недостаток: [описание].\nНа основании статьи 13 Закона «О "
                  "защите прав потребителей» требую [заменить товар / вернуть деньги / безвозмездно устранить недостаток].\n"
                  "Прошу дать письменный ответ в течение [срок].\nПриложения: копия чека, копия гарантийного талона.\n[Дата]   [Подпись]",
        },
        {
            "uz": ["Talabnomani ikki nusxada topshiring yoki buyurtma xat bilan yuboring",
                   "Sifatli tovarni ham 10 kun ichida almashtirish mumkin (foydalanilmagan boʻlsa)"],
            "ru": ["Вручите претензию в двух экземплярах или отправьте заказным письмом",
                   "Даже качественный товар можно обменять в течение 10 дней (если не использовался)"],
            "en": ["Hand it over in two copies or send it by registered mail",
                   "Even proper-quality goods can be exchanged within 10 days if unused"],
        },
    ),
    "appeal_state_body": Template(
        "appeal_state_body",
        (("3336169", "6"), ("3336169", "21"), ("3336169", "28")),
        {"uz": "Davlat organiga ariza (shikoyat)", "ru": "Обращение (жалоба) в государственный орган",
         "en": "Application / complaint to a state body"},
        {
            "uz": "[Davlat organi nomi]ga\n[F.I.Sh.], [manzil], [telefon, e-pochta]dan\n\nARIZA (SHIKOYAT)\n[Masalaning mazmuni: "
                  "nima boʻldi, kim, qachon]. [Qanday huquqim buzildi].\nIltimos, [aniq talab: masalan, qarorni qayta koʻrib "
                  "chiqish, maʼlumot berish].\nIlova: [hujjatlar nusxalari].\n[Sana]   [Imzo]",
            "ru": "В [наименование госоргана]\nот [ФИО], [адрес], [телефон, e-mail]\n\nОБРАЩЕНИЕ (ЖАЛОБА)\n[Суть вопроса: что "
                  "произошло, кто, когда]. [Какое право нарушено].\nПрошу [конкретное требование: например, пересмотреть "
                  "решение, предоставить информацию].\nПриложения: [копии документов].\n[Дата]   [Подпись]",
        },
        {
            "uz": ["Arizada F.I.Sh., yashash joyi va masalaning mazmuni boʻlishi shart",
                   "Koʻrib chiqish muddati — 15 kun, qoʻshimcha oʻrganish kerak boʻlsa 1 oygacha",
                   "Onlayn: Prezidentning Virtual qabulxonasi yoki my.gov.uz orqali ham yuborish mumkin"],
            "ru": ["В обращении обязательны ФИО, адрес и суть вопроса", "Срок рассмотрения — 15 дней, при дополнительном изучении до 1 месяца",
                   "Онлайн: через Виртуальную приёмную Президента или my.gov.uz"],
            "en": ["Include your full name, address and the substance of the issue",
                   "It must be considered within 15 days (up to 1 month if extra checks are needed)",
                   "Online: via the President's Virtual Reception or my.gov.uz"],
        },
    ),
}


def render(kind: str, lang: str) -> tuple[str, str, list[str]]:
    """(title, template body, notes) in the reader's language and script."""
    tpl = TEMPLATES.get(kind) or TEMPLATES["appeal_state_body"]
    key = "ru" if lang == "ru" else "en" if lang == "en" else "uz"
    body_key = "ru" if lang == "ru" else "uz"
    title, body, notes = tpl.title[key], tpl.body[body_key], list(tpl.notes[key])
    if lang == "uz_cyrl":
        title, body, notes = latin_to_cyrillic(title), latin_to_cyrillic(body), [latin_to_cyrillic(n) for n in notes]
    return title, body, notes
