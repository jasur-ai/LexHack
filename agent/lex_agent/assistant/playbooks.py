"""Practical next steps for the most common situations (keyed by situation-lexicon id prefix).

Each step is a plain action in the reader's language; the articles in ``basis`` are added to the answer's
sources so every step stays checkable. Steps only describe procedures the cited norms provide for.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Playbook:
    basis: tuple[tuple[str, str], ...]
    steps: dict[str, tuple[str, ...]]
    caution: dict[str, str]


def _p(basis: str, uz: tuple[str, ...], ru: tuple[str, ...], en: tuple[str, ...], cuz: str = "", cru: str = "", cen: str = "") -> Playbook:
    pairs = tuple(tuple(x.split(":", 1)) for x in basis.split(";") if x)  # type: ignore[misc]
    return Playbook(pairs, {"uz": uz, "ru": ru, "en": en}, {"uz": cuz, "ru": cru, "en": cen})  # type: ignore[arg-type]


PLAYBOOKS: dict[str, Playbook] = {
    "labour.dismissal.employer": _p(
        "6257288:170;6257288:560;6257288:562",
        ("Boʻshatish buyrugʻi nusxasini va hisob-kitobni yozma talab qiling",
         "Mehnat nizolari komissiyasiga yoki toʻgʻridan-toʻgʻri sudga ishga tiklash haqida ariza bering",
         "Sudga sud xarajatlarisiz murojaat qilasiz; vaqtni boy bermang"),
        ("Потребуйте копию приказа об увольнении и расчёт в письменной форме",
         "Подайте заявление в комиссию по трудовым спорам или сразу иск в суд о восстановлении",
         "Работник освобождён от судебных расходов — не теряйте время"),
        ("Ask in writing for a copy of the dismissal order and your final pay",
         "Apply to the labour disputes commission or file a reinstatement claim in court",
         "Employees pay no court costs — act quickly"),
        "Ishga tiklash haqida sudga murojaat muddati — buyruq nusxasi berilgan kundan 3 oy.",
        "Срок обращения в суд о восстановлении — 3 месяца со дня вручения копии приказа.",
        "The deadline for a reinstatement claim is 3 months from receiving the order."),
    "labour.reinstatement": _p(
        "6257288:560;6257288:564;6257288:562",
        ("Boʻshatish buyrugʻi nusxasini oling", "Sudga ishga tiklash va majburiy progul haqini undirish haqida daʼvo bering",
         "Maʼnaviy ziyonni ham talab qilish mumkin"),
        ("Получите копию приказа", "Подайте иск о восстановлении и оплате вынужденного прогула",
         "Можно также требовать компенсацию морального вреда"),
        ("Get a copy of the dismissal order", "Sue for reinstatement and pay for the forced absence",
         "You can also claim moral damages"),
        "Muddat — 3 oy; uni oʻtkazib yuborsangiz, uzrli sabab bilan tiklashni soʻrash kerak boʻladi.",
        "Срок — 3 месяца; при пропуске придётся просить восстановить его по уважительной причине.",
        "The deadline is 3 months; missing it requires asking the court to restore it for a valid reason."),
    "labour.wage.delay": _p(
        "6257288:333;6257288:545;6257288:535",
        ("Ish beruvchiga qarz va kechiktirilgan kunlar uchun kompensatsiyani yozma talab qiling",
         "Javob boʻlmasa — Davlat mehnat inspeksiyasiga yoki mehnat nizolari komissiyasiga murojaat qiling",
         "Keyin sudga: ish haqi va kompensatsiyani undirish haqida daʼvo"),
        ("Письменно потребуйте долг и компенсацию за каждый день задержки",
         "Без ответа — в Государственную инспекцию труда или комиссию по трудовым спорам",
         "Далее — иск в суд о взыскании зарплаты и компенсации"),
        ("Demand the arrears and the per-day compensation in writing",
         "No answer — complain to the State Labour Inspectorate or the labour disputes commission",
         "Then sue for the wages and compensation"),
        "Kompensatsiya ish beruvchining aybidan qatʼi nazar toʻlanadi.",
        "Компенсация положена независимо от вины работодателя.",
        "Compensation is owed regardless of the employer's fault."),
    "labour.dismissal.own_will": _p(
        "6257288:160;6257288:254",
        ("Ish beruvchiga ishdan boʻshash haqida yozma ariza bering (nusxasida qabul belgisi boʻlsin)",
         "14 kalendar kun ishlab bering yoki ish beruvchi bilan erta boʻshashni kelishing",
         "Oxirgi kuni hisob-kitob va mehnat daftarchasini oling"),
        ("Подайте письменное заявление (на копии — отметка о приёме)",
         "Отработайте 14 календарных дней или договоритесь об увольнении раньше",
         "В последний день получите расчёт и трудовую книжку"),
        ("Hand in a written resignation (keep a copy stamped as received)",
         "Work the 14 calendar days or agree on an earlier date", "Collect your final pay and records on the last day"),
        "", "", ""),
    "labour.leave": _p(
        "6257288:217;6257288:233",
        ("Taʼtil jadvali va ish yilingizni aniqlang", "Taʼtil puli taʼtil boshlanishidan oldingi oxirgi ish kunida toʻlanishi kerak"),
        ("Уточните график отпусков и рабочий год", "Отпускные должны выплатить не позднее последнего рабочего дня перед отпуском"),
        ("Check the leave schedule and your working year", "Holiday pay is due before the last working day ahead of the leave"),
        "", "", ""),
    "family.divorce": _p(
        "104720:42;104720:40;4680944:annex",
        ("Ikkalangiz rozi boʻlsangiz va voyaga yetmagan farzand boʻlmasa — FHDYOga birgalikda ariza bering",
         "Aks holda — sudga nikohdan ajratish haqida daʼvo bering (davlat boji — 2 BHM)",
         "Bolalar, aliment va mol-mulk masalasini shu bilan birga hal qilishni soʻrang"),
        ("Если оба согласны и нет несовершеннолетних детей — совместное заявление в ЗАГС",
         "Иначе — иск о расторжении брака в суд (госпошлина — 2 БРВ)",
         "Попросите одновременно решить вопросы детей, алиментов и имущества"),
        ("If both agree and there are no minor children — a joint application at the registry office",
         "Otherwise — a divorce claim in court (state duty: 2 × BHM)",
         "Ask the court to settle children, support and property at the same time"),
        "", "", ""),
    "family.alimony": _p(
        "104720:130;104720:136;3517337:170",
        ("Avval aliment toʻlash haqida notarial kelishuv tuzishga harakat qiling",
         "Kelishilmasa — sudga aliment undirish haqida daʼvo yoki sud buyrugʻi soʻrab ariza bering",
         "Qaror chiqqach, ijro varaqasini Majburiy ijro byurosiga topshiring"),
        ("Сначала попробуйте заключить нотариальное соглашение об уплате алиментов",
         "Не договорились — иск о взыскании алиментов или заявление о выдаче судебного приказа",
         "После решения передайте исполнительный лист в Бюро принудительного исполнения"),
        ("First try a notarised child-support agreement", "Otherwise sue for support or apply for a court order",
         "Then hand the enforcement document to the Compulsory Enforcement Bureau"),
        "", "", ""),
    "family.child_residence": _p(
        "104720:76;104720:88",
        ("Bola bilan koʻrishish tartibini ikkinchi ota-ona bilan yozma kelishib oling",
         "Kelishilmasa — vasiylik va homiylik organi ishtirokida sud hal qiladi"),
        ("Договоритесь письменно о порядке общения с ребёнком", "Если не договорились — спор решит суд с участием органа опеки"),
        ("Agree the contact arrangements in writing", "If you can't agree, the court decides with the guardianship authority"),
        "", "", ""),
    "family.domestic_violence": _p(
        "4494709:23;4494709:26;97664:59.2",
        ("Xavf boʻlsa darhol 102 yoki 112 ga qoʻngʻiroq qiling", "Ichki ishlar organidan himoya orderi berilishini soʻrang",
         "1146 ishonch telefoni orqali psixologik va huquqiy yordam oling"),
        ("При опасности сразу звоните 102 или 112", "Попросите полицию выдать защитный ордер",
         "Психологическая и юридическая помощь — телефон доверия 1146"),
        ("If in danger, call 102 or 112 now", "Ask the police for a protection order", "Get psychological and legal help on 1146"),
        "", "", ""),
    "inheritance": _p(
        "180552:1116;180552:1146;54458:49",
        ("Meros ochilgan joydagi notariusga murojaat qiling (vafot haqida guvohnoma, qarindoshlikni tasdiqlovchi hujjatlar bilan)",
         "Merosni qabul qilish haqida ariza bering",
         "Merosga boʻlgan huquq toʻgʻrisidagi guvohnoma odatda 6 oy oʻtgach beriladi"),
        ("Обратитесь к нотариусу по месту открытия наследства (свидетельство о смерти, документы о родстве)",
         "Подайте заявление о принятии наследства", "Свидетельство о праве на наследство обычно выдают через 6 месяцев"),
        ("Go to a notary where the inheritance opened (death certificate, proof of kinship)",
         "File an application to accept the inheritance", "The inheritance certificate is normally issued after 6 months"),
        "", "", ""),
    "civil.loan": _p(
        "180552:733;180552:737;3517337:170",
        ("Qarzdorga qaytarish talabini yozma yuboring (tilxat yoki oʻtkazma dalillarini saqlang)",
         "Qaytarmasa — sud buyrugʻi soʻrab yoki daʼvo bilan sudga murojaat qiling",
         "Umumiy daʼvo muddati — 3 yil"),
        ("Направьте должнику письменное требование (сохраните расписку или подтверждение перевода)",
         "Не возвращает — заявление о судебном приказе или иск", "Общий срок исковой давности — 3 года"),
        ("Send the borrower a written demand (keep the receipt or transfer proof)",
         "If unpaid — apply for a court order or sue", "The general limitation period is 3 years"),
        "", "", ""),
    "civil.lease": _p(
        "180552:603;180552:615",
        ("Ijara shartnomasini yozma tuzing va shartlarini (haq, muddat, taʼmir) kelishing",
         "Nizo boʻlsa — avval yozma talab, keyin sud"),
        ("Заключите письменный договор и согласуйте условия (плата, срок, ремонт)", "При споре — письменное требование, затем суд"),
        ("Sign a written lease covering rent, term and repairs", "In a dispute — written demand first, then court"),
        "", "", ""),
    "consumer": _p(
        "4704:13;4704:17;4704:23",
        ("Chek va kafolat talonini saqlang", "Sotuvchiga yozma talabnoma (pretenziya) bering",
         "Rad etilsa — isteʼmolchilar huquqlarini himoya qilish organiga yoki sudga murojaat qiling"),
        ("Сохраните чек и гарантийный талон", "Вручите продавцу письменную претензию",
         "При отказе — в орган по защите прав потребителей или в суд"),
        ("Keep the receipt and warranty card", "Give the seller a written complaint",
         "If refused — go to the consumer protection authority or court"),
        "", "", ""),
    "traffic.accident": _p(
        "97664:137;1342474:19",
        ("Voqea joyini tark etmang, jabrlanganlar boʻlsa 103 va 102 ga qoʻngʻiroq qiling",
         "Sugʻurta kompaniyangizni darhol xabardor qiling", "Zarar sugʻurta yoki sud orqali undiriladi"),
        ("Не покидайте место ДТП; при пострадавших звоните 103 и 102", "Сразу сообщите страховщику",
         "Ущерб возмещается через страховку или суд"),
        ("Don't leave the scene; call 103 and 102 if anyone is hurt", "Notify your insurer straight away",
         "Damage is recovered through insurance or court"),
        "", "", ""),
    "admin.appeal": _p(
        "97664:315;97664:316",
        ("Qaror nusxasini oling", "Yuqori turuvchi organga yoki sudga 10 kun ichida shikoyat bering"),
        ("Получите копию постановления", "Подайте жалобу в вышестоящий орган или суд в течение 10 дней"),
        ("Get a copy of the decision", "Appeal to the higher authority or court within 10 days"),
        "Muddat qaror nusxasi olingan kundan 10 kun.", "Срок — 10 дней со дня получения копии.",
        "The deadline is 10 days from receiving the copy."),
    "criminal": _p(
        "111460:55;111460:27",
        ("Ichki ishlar organiga (102) yoki prokuraturaga ariza bering", "Dalillarni saqlang: yozishmalar, chek, guvohlar",
         "Jabrlanuvchi sifatida huquqlaringizdan foydalaning, advokat jalb qiling"),
        ("Подайте заявление в полицию (102) или прокуратуру", "Сохраните доказательства: переписку, чеки, свидетелей",
         "Пользуйтесь правами потерпевшего, привлеките адвоката"),
        ("Report it to the police (102) or prosecutor", "Keep evidence: messages, receipts, witnesses",
         "Use your rights as a victim; get a lawyer"),
        "", "", ""),
    "criminal.arrest_rights": _p(
        "111460:48;111460:51;6445145:29",
        ("Ushlash sababini va huquqlaringizni soʻrang", "Himoyachi (advokat) talab qiling — u ishtirok etishi shart boʻlgan hollar bor",
         "Bayonnomani oʻqimasdan imzolamang"),
        ("Спросите основание задержания и ваши права", "Требуйте защитника — в ряде случаев его участие обязательно",
         "Не подписывайте протокол, не прочитав"),
        ("Ask for the reason and your rights", "Demand a defence lawyer", "Don't sign the record without reading it"),
        "", "", ""),
    "procedure.claim": _p(
        "3517337:189;3517337:191;4680944:annex",
        ("Daʼvo arizasini yozing (sud, taraflar, talab, dalillar, daʼvo bahosi)", "Davlat bojini toʻlang",
         "Arizani javobgar yashaydigan joydagi sudga yoki E-SUD orqali topshiring"),
        ("Составьте иск (суд, стороны, требование, доказательства, цена иска)", "Оплатите госпошлину",
         "Подайте иск в суд по месту жительства ответчика или через E-SUD"),
        ("Draft the claim (court, parties, demand, evidence, value)", "Pay the state duty",
         "File it with the court where the defendant lives or online via E-SUD"),
        "", "", ""),
    "procedure.enforcement": _p(
        "26477:7;26477:23;26477:27",
        ("Sud qarori kuchga kirgach, ijro hujjatini oling", "Uni Majburiy ijro byurosiga topshiring",
         "Ijroga topshirish muddatini oʻtkazib yubormang"),
        ("После вступления решения в силу получите исполнительный документ", "Передайте его в Бюро принудительного исполнения",
         "Не пропустите срок предъявления к исполнению"),
        ("Get the enforcement document once the judgment is final", "Hand it to the Compulsory Enforcement Bureau",
         "Watch the deadline for submitting it"),
        "", "", ""),
    "rights.appeals": _p(
        "3336169:6;3336169:28;3336169:38",
        ("Arizani yozma yoki elektron shaklda bering (F.I.Sh., manzil, masala mazmuni)",
         "Javob 15 kunda (qoʻshimcha oʻrganish kerak boʻlsa 1 oygacha) berilishi kerak",
         "Javob boʻlmasa — yuqori turuvchi organga yoki sudga shikoyat qiling"),
        ("Подайте обращение письменно или электронно (ФИО, адрес, суть вопроса)",
         "Ответ — в течение 15 дней (до 1 месяца при дополнительном изучении)",
         "Нет ответа — жалоба в вышестоящий орган или суд"),
        ("Submit it in writing or online (name, address, the issue)", "An answer is due in 15 days (up to 1 month)",
         "No answer — complain to the higher body or court"),
        "", "", ""),
    "social.pension": _p(
        "112314:43;112314:47",
        ("Pensiya tayinlash uchun ariza bering (ish staji hujjatlari bilan)", "Rad etilsa — qaror ustidan shikoyat qiling"),
        ("Подайте заявление о назначении пенсии (с документами о стаже)", "При отказе — обжалуйте решение"),
        ("Apply for the pension with your service records", "If refused — appeal the decision"),
        "", "", ""),
}


PLAYBOOKS["consumer.food_safety"] = _p(
    "4704:12;4704:20;4704:22",
    ("Shifokorga murojaat qiling va zaharlanish haqida tibbiy xulosa oling",
     "Chek, buyurtma yoki toʻlov dalilini va qolgan mahsulotni saqlang",
     "Sotuvchiga (restoranga) yozma daʼvo bering; javob boʻlmasa — sanitariya-epidemiologiya xizmatiga va sudga"),
    ("Обратитесь к врачу и получите медицинское заключение об отравлении",
     "Сохраните чек, заказ или подтверждение оплаты и остатки продукта",
     "Направьте продавцу (ресторану) письменную претензию; без ответа — в санэпидслужбу и суд"),
    ("See a doctor and get a medical report on the poisoning",
     "Keep the receipt, order or payment proof and any leftover food",
     "Send a written claim to the seller (restaurant); if ignored, complain to the sanitary service and sue"),
    "Zarar (davolanish xarajatlari, ish haqi yoʻqotilishi) va maʼnaviy zarar qoplanishini talab qilish mumkin.",
    "Можно требовать возмещения вреда (лечение, утраченный заработок) и компенсации морального вреда.",
    "You can claim damages (treatment, lost earnings) and compensation for moral harm.")

# Situations whose ids do not share the playbook key as a prefix
_PLAYBOOK_ALIASES: dict[str, str] = {
    "labour.leave.annual": "labour.leave", "labour.leave.duration": "labour.leave", "labour.leave.pay": "labour.leave",
    "labour.leave.first_year": "labour.leave", "labour.leave.unused": "labour.leave",
    "labour.leave.transfer_split": "labour.leave",
    "social.pension_age": "social.pension", "social.pension_amount": "social.pension",
    "social.pension_service": "social.pension", "social.pension_apply": "social.pension",
    "social.pension_appeal": "social.pension", "social.pension_general": "social.pension",
    "social.disability_pension": "social.pension", "social.survivor_pension": "social.pension",
}
_LEAVE_PLAYBOOK = PLAYBOOKS.pop("labour.leave")


def playbook_for(concept_ids: list[str]) -> Playbook | None:
    """Most specific playbook for the matched situations (exact id, alias, then id prefixes)."""
    for cid in concept_ids:
        alias = _PLAYBOOK_ALIASES.get(cid)
        if alias:
            return _LEAVE_PLAYBOOK if alias == "labour.leave" else PLAYBOOKS[alias]
        parts = cid.split(".")
        for n in range(len(parts), 0, -1):
            key = ".".join(parts[:n])
            if key in PLAYBOOKS:
                return PLAYBOOKS[key]
    return None


# One-sentence direct answers for the most common situations. Every figure and condition was checked against the
# article text in the index; ``basis`` lists the articles that state it (doc:article;...). ``polarity`` marks leads
# that answer a yes/no question ("Can a pregnant woman be dismissed?" -> "No — ...").


@dataclass(frozen=True, slots=True)
class Lead:
    uz: str
    ru: str
    en: str
    basis: str
    polarity: str | None = None  # "yes" | "no"


def _l(uz: str, ru: str, en: str, basis: str, polarity: str | None = None) -> Lead:
    return Lead(uz, ru, en, basis, polarity)


LEADS: dict[str, Lead] = {
    # ---------------------------------------------------------------- labour
    "labour.dismissal.employer": _l(
        "Ish beruvchi tashabbusi bilan boʻshatish asosli boʻlishi shart; noqonuniy boʻlsa, buyruq nusxasini olgan "
        "kundan 3 oy ichida sudga ishga tiklash haqida murojaat qilishingiz mumkin.",
        "Увольнение по инициативе работодателя должно быть обоснованным; при незаконном увольнении можно обратиться в "
        "суд о восстановлении в течение 3 месяцев со дня вручения копии приказа.",
        "A dismissal by the employer must be justified; if it is unlawful you can sue for reinstatement within 3 months "
        "of receiving the dismissal order.",
        "6257288:161;6257288:560"),
    "labour.reinstatement": _l(
        "Ishga tiklash haqida sudga buyruq nusxasi topshirilgan kundan 3 oy ichida murojaat qilinadi; xodim sud "
        "xarajatlarini toʻlamaydi.",
        "Иск о восстановлении на работе подаётся в течение 3 месяцев со дня вручения копии приказа; работник "
        "освобождён от судебных расходов.",
        "A reinstatement claim is filed within 3 months of receiving the order; employees pay no court costs.",
        "6257288:560;6257288:562"),
    "labour.wage.delay": _l(
        "Ish haqi kechiktirilsa, ish beruvchi qarzdan tashqari har bir kechiktirilgan kun uchun Markaziy bank "
        "stavkasining 10 foizi miqdorida kompensatsiya toʻlashi shart.",
        "При задержке зарплаты работодатель помимо долга обязан выплатить компенсацию — 10% ставки Центрального банка "
        "за каждый день задержки.",
        "If wages are late, the employer must pay the arrears plus 10% of the Central Bank rate for each day of delay.",
        "6257288:333", "yes"),
    "labour.wage.payment": _l(
        "Ish haqi kamida har yarim oyda bir marta toʻlanishi shart.",
        "Заработная плата выплачивается не реже одного раза в каждые полмесяца.",
        "Wages must be paid at least every half month.",
        "6257288:253"),
    "labour.dismissal.notice": _l(
        "Ish beruvchi boʻshatish haqida yozma ogohlantirishi shart: tashkilot tugatilsa yoki shtat qisqarsa — kamida "
        "2 oy, malaka yetarli boʻlmasa — kamida 2 hafta, xodimning aybli harakati uchun — kamida 3 kun oldin; "
        "ogohlantirish oʻrniga shu muddatga teng pul kompensatsiyasi toʻlanishi mumkin.",
        "Работодатель обязан письменно предупредить об увольнении: при ликвидации организации или сокращении штата — "
        "не менее чем за 2 месяца, при недостаточной квалификации — за 2 недели, за виновные действия — за 3 дня; "
        "предупреждение можно заменить денежной компенсацией за этот срок.",
        "Your employer must warn you in writing: at least 2 months before a dismissal for liquidation or staff cuts, "
        "2 weeks for insufficient qualification and 3 days for misconduct; the notice can be replaced by pay for that period.",
        "6257288:165;6257288:560"),
    "labour.dismissal.own_will": _l(
        "Oʻz xohishingiz bilan ishdan ketish uchun ish beruvchini 14 kalendar kun oldin yozma ogohlantirasiz; "
        "hisob-kitob oxirgi ish kuni toʻlanadi.",
        "Чтобы уволиться по собственному желанию, предупредите работодателя письменно за 14 календарных дней; расчёт "
        "выплачивается в день увольнения.",
        "To resign, give your employer 14 calendar days' written notice; final pay is due on your last day.",
        "6257288:160;6257288:254", "yes"),
    "labour.dismissal.pregnant": _l(
        "Homilador ayolni ish beruvchi tashabbusi bilan ishdan boʻshatish mumkin emas (faqat tashkilot tugatilgan hol "
        "bundan mustasno); homiladorlik sababli ishga olmaslik yoki boʻshatish taqiqlanadi.",
        "Увольнять беременную женщину по инициативе работодателя нельзя (кроме ликвидации организации); отказ в приёме "
        "или увольнение из-за беременности запрещены.",
        "A pregnant woman cannot be dismissed at the employer's initiative except when the organisation is liquidated; "
        "refusing to hire or dismissing because of pregnancy is prohibited.",
        "6257288:408;6257288:392", "no"),
    "labour.final_settlement": _l(
        "Ishdan ketganda barcha toʻlovlar (ish haqi, foydalanilmagan taʼtillar uchun kompensatsiya) oxirgi ish kuni "
        "toʻlanadi; oʻsha kuni ishlamagan boʻlsangiz — talab qilganingizdan keyin 3 kun ichida.",
        "При увольнении все выплаты (зарплата, компенсация за неиспользованные отпуска) производятся в последний день "
        "работы, а если вы в этот день не работали — не позднее 3 дней после требования о расчёте.",
        "On leaving, all payments (wages, compensation for unused leave) are due on your last day, or within 3 days of "
        "your request if you did not work that day.",
        "6257288:172;6257288:254"),
    "labour.severance": _l(
        "Ishdan boʻshatish nafaqasi shartnoma ayrim asoslarda bekor qilinganda toʻlanadi va stajga qarab oʻrtacha "
        "oylikning kamida 50 foizidan (3 yilgacha) 200 foizigacha (15 yildan ortiq) boʻladi.",
        "Выходное пособие выплачивается при прекращении договора по отдельным основаниям и в зависимости от стажа "
        "составляет не менее 50% (до 3 лет) — 200% (свыше 15 лет) среднемесячной зарплаты.",
        "Severance pay is due when the contract ends on certain grounds and ranges from at least 50% (under 3 years of "
        "service) to 200% (over 15 years) of average monthly pay.",
        "6257288:173"),
    "labour.probation": _l(
        "Dastlabki sinov muddati 3 oydan (rahbarlar, ularning oʻrinbosarlari va bosh buxgalterlar uchun 6 oydan) "
        "oshmasligi kerak; kasallik davri sinov muddatiga qoʻshilmaydi.",
        "Испытательный срок — не более 3 месяцев (для руководителей, их заместителей и главных бухгалтеров — до 6 "
        "месяцев); период болезни в него не засчитывается.",
        "Probation may not exceed 3 months (6 months for managers, their deputies and chief accountants); sick leave "
        "does not count towards it.",
        "6257288:130"),
    "labour.contract.form": _l(
        "Mehnat shartnomasi yozma (qogʻoz yoki elektron) shaklda kamida 2 nusxada tuziladi va har birini ikkala tomon "
        "imzolaydi.",
        "Трудовой договор заключается в письменной (бумажной или электронной) форме не менее чем в двух экземплярах, "
        "каждый из которых подписывают стороны.",
        "An employment contract must be in writing (paper or electronic), in at least two copies signed by both sides.",
        "6257288:106", "yes"),
    "labour.working_hours": _l(
        "Normal ish vaqti haftasiga 40 soatdan oshmasligi kerak (5 yoki 6 kunlik ish haftasida).",
        "Нормальная продолжительность рабочего времени — не более 40 часов в неделю (при пяти- или шестидневке).",
        "Normal working time may not exceed 40 hours a week (five- or six-day week).",
        "6257288:182"),
    "labour.overtime": _l(
        "Ish vaqtidan tashqari ish ketma-ket 2 kunda 4 soatdan oshmasligi kerak; dastlabki 2 soat kamida 1,5 baravar, "
        "keyingi soatlar kamida 2 baravar haq bilan toʻlanadi.",
        "Сверхурочная работа — не более 4 часов в течение двух дней подряд; первые 2 часа оплачиваются не менее чем в "
        "полуторном размере, последующие — не менее чем в двойном.",
        "Overtime is capped at 4 hours over two consecutive days; the first 2 hours are paid at least 1.5x, further "
        "hours at least 2x.",
        "6257288:190;6257288:262"),
    "labour.night_work": _l(
        "Tungi vaqt — 22:00 dan 6:00 gacha; tunda ishlangan har bir soat kamida 1,5 baravar haq bilan toʻlanadi.",
        "Ночное время — с 22:00 до 6:00; каждый час работы ночью оплачивается не менее чем в полуторном размере.",
        "Night time is 22:00–6:00; each night hour is paid at least 1.5x.",
        "6257288:188;6257288:264"),
    "labour.leave.annual": _l(
        "Har yilgi asosiy mehnat taʼtili kamida 21 kalendar kun; taʼtil vaqtida oʻrtacha ish haqi saqlanadi.",
        "Ежегодный основной трудовой отпуск — не менее 21 календарного дня; за время отпуска сохраняется средняя "
        "зарплата.",
        "Annual leave is at least 21 calendar days, paid at your average salary.",
        "6257288:217;6257288:233"),
    "labour.leave.maternity": _l(
        "Homiladorlik va tugʻish taʼtili tugʻishdan oldin 70 kalendar kun va keyin 56 kun (asoratli tugʻishda yoki "
        "egizaklarda — 70 kun) nafaqa bilan beriladi.",
        "Отпуск по беременности и родам — 70 календарных дней до родов и 56 после (при осложнённых родах или двойне — "
        "70) с выплатой пособия.",
        "Maternity leave is 70 calendar days before birth and 56 after (70 after complicated or multiple births), "
        "with a benefit.",
        "6257288:404"),
    "labour.leave.childcare": _l(
        "Homiladorlik va tugʻish taʼtilidan keyin ayolga bola 2 yoshga toʻlguncha nafaqa bilan taʼtil, xohishiga koʻra "
        "3 yoshga toʻlguncha haq toʻlanmaydigan qoʻshimcha taʼtil beriladi.",
        "После отпуска по беременности и родам женщине предоставляется отпуск по уходу за ребёнком до 2 лет с пособием "
        "и по желанию — дополнительный отпуск без сохранения зарплаты до 3 лет.",
        "After maternity leave a mother gets childcare leave with a benefit until the child is 2 and, if she wishes, "
        "unpaid leave until the child is 3.",
        "6257288:405"),
    "labour.leave.unpaid": _l(
        "Haq saqlanmaydigan taʼtil yozma arizangiz boʻyicha ish beruvchi bilan kelishib beriladi; ayrim toifalarga "
        "(masalan, I va II guruh nogironligi boʻlganlarga yiliga 14 kungacha) majburiy beriladi.",
        "Отпуск без сохранения зарплаты предоставляется по письменному заявлению по соглашению с работодателем; "
        "некоторым категориям (например, лицам с инвалидностью I и II групп — до 14 дней в году) — обязательно.",
        "Unpaid leave is granted on written request by agreement with the employer; some groups (e.g. people with "
        "group I or II disability, up to 14 days a year) are entitled to it.",
        "6257288:241;6257288:242", "yes"),
    "labour.wage.cut": _l(
        "Ish beruvchi ish haqi shartlarini xodim uchun yomon tomonga faqat uning roziligi bilan oʻzgartirishi mumkin; "
        "istisno holatlarda (ishlab chiqarish va mehnatni tashkil etishdagi oʻzgarishlar) kamida 2 oy oldin imzo "
        "qoʻydirib ogohlantirishi shart.",
        "Ухудшать условия оплаты труда без согласия работника нельзя; в исключительных случаях (изменения в производстве "
        "и организации труда) работодатель обязан предупредить под роспись не позднее чем за 2 месяца.",
        "Your employer cannot worsen your pay terms without your consent; in exceptional cases (changes in production "
        "or work organisation) it must warn you in writing at least 2 months in advance.",
        "6257288:247", "no"),
    "labour.transfer": _l(
        "Boshqa ishga doimiy oʻtkazish faqat roziligingiz bilan mumkin; vaqtincha oʻtkazish ham roziligingiz bilan "
        "amalga oshiriladi — ishlab chiqarish zarurati yoki bekor turib qolish holatlari bundan mustasno.",
        "Постоянный перевод на другую работу допускается только с вашего согласия; временный — тоже, кроме случаев "
        "производственной необходимости или простоя.",
        "A permanent transfer to another job requires your consent; a temporary one does too, except in cases of "
        "production necessity or downtime.",
        "6257288:140"),
    "labour.safety": _l(
        "Ishda olingan jarohat yoki kasb kasalligi tufayli sogʻliqqa yetkazilgan zararni ish beruvchi qoplaydi: bir "
        "martalik nafaqa, yoʻqotilgan ish haqi uchun har oylik toʻlovlar va qoʻshimcha xarajatlar kompensatsiyasi.",
        "Вред здоровью от трудового увечья или профзаболевания возмещает работодатель: единовременное пособие, "
        "ежемесячные выплаты в возмещение утраченного заработка и компенсация дополнительных расходов.",
        "The employer compensates harm from a workplace injury or occupational disease: a lump-sum benefit, monthly "
        "payments for lost earnings and compensation of extra expenses.",
        "6257288:321;6257288:322"),
    "labour.minors": _l(
        "Ishga qabul qilish 16 yoshdan ruxsat etiladi; oʻquvchilarni yengil ishlarga qabul qilishga qonundagi shartlar "
        "bilan yoʻl qoʻyiladi.",
        "Приём на работу допускается с 16 лет; учащихся можно принимать на лёгкий труд на условиях, установленных "
        "законом.",
        "Employment is allowed from age 16; students may do light work under the conditions set by law.",
        "6257288:118"),
    # ---------------------------------------------------------------- family
    "family.divorce": _l(
        "Nikoh odatda sud orqali bekor qilinadi; ikkalangiz rozi boʻlsangiz va umumiy voyaga yetmagan farzandingiz "
        "boʻlmasa — FHDYO organida.",
        "Брак расторгается, как правило, в суде; при взаимном согласии супругов без общих несовершеннолетних детей — "
        "в органах ЗАГС.",
        "Divorce normally goes through a court; spouses who both agree and have no minor children can divorce at the "
        "civil registry office.",
        "104720:38;104720:42"),
    "family.alimony": _l(
        "Kelishuv boʻlmasa, sud aliment undiradi: 1 bolaga daromadning 1/4, 2 bolaga 1/3, 3 va undan ortiq bolaga 1/2 "
        "qismi.",
        "Без соглашения суд взыскивает алименты: на 1 ребёнка — 1/4 дохода, на 2 детей — 1/3, на 3 и более — 1/2.",
        "Without an agreement the court orders child support: 1/4 of income for one child, 1/3 for two, 1/2 for three "
        "or more.",
        "104720:99"),
    "family.alimony.debt": _l(
        "Sud qarori boʻyicha alimentni oʻz aybi bilan toʻlamagan shaxs qarzdan tashqari neustoyka toʻlaydi; qarz uning "
        "ish haqi va boshqa daromadidan undiriladi.",
        "Лицо, по своей вине не плативщее алименты по решению суда, помимо долга уплачивает неустойку; задолженность "
        "взыскивается из его заработка и иного дохода.",
        "A parent who culpably fails to pay court-ordered support owes a penalty on top of the arrears, which are "
        "recovered from wages and other income.",
        "104720:142;104720:139"),
    "family.marriage_age": _l(
        "Nikoh yoshi erkaklar va ayollar uchun 18 yosh; uzrli sabablar boʻlsa, istisno tariqasida hokim uni "
        "kamaytirishi mumkin.",
        "Брачный возраст для мужчин и женщин — 18 лет; при уважительных причинах в исключительных случаях хоким может "
        "его снизить.",
        "The marriage age is 18 for men and women; in exceptional cases with good reason the hokim may lower it.",
        "104720:15"),
    "family.paternity": _l(
        "Nikohda boʻlmagan ota-onaning birgalikdagi arizasi boʻlmasa, otalik sud tartibida belgilanadi.",
        "Если родители не состоят в браке и нет их совместного заявления, отцовство устанавливается в судебном "
        "порядке.",
        "If the parents are not married and there is no joint application, paternity is established by a court.",
        "104720:62;104720:61", "yes"),
    "family.common_property": _l(
        "Nikoh davomida orttirilgan mol-mulk, nikoh shartnomasida boshqacha belgilanmagan boʻlsa, er-xotinning umumiy "
        "mulki hisoblanadi; uni nikoh davomida ham, ajrashgandan keyin ham boʻlish mumkin.",
        "Имущество, нажитое в браке, является общей совместной собственностью супругов, если брачный договор не "
        "предусматривает иное; разделить его можно как в браке, так и после развода.",
        "Property acquired during marriage is joint property unless a marriage contract says otherwise; it can be "
        "divided during the marriage or after divorce.",
        "104720:23;104720:27", "yes"),
    "family.parental_rights": _l(
        "Ota-ona majburiyatlarini bajarishdan, jumladan aliment toʻlashdan boʻyin tovlasa, sud uni ota-onalik "
        "huquqidan mahrum qilishi mumkin.",
        "Родителя, уклоняющегося от своих обязанностей, в том числе от уплаты алиментов, суд может лишить "
        "родительских прав.",
        "A parent who evades parental duties, including child support, can be deprived of parental rights by a court.",
        "104720:79", "yes"),
    "family.child_residence": _l(
        "Bola bilan alohida yashovchi ota-ona u bilan koʻrishish va tarbiyasida qatnashish huquqiga ega; nizolarni "
        "vasiylik organi ishtirokida sud hal qiladi.",
        "Родитель, проживающий отдельно, вправе общаться с ребёнком и участвовать в его воспитании; споры решает суд "
        "с участием органа опеки.",
        "A parent living apart keeps the right to see the child and take part in upbringing; disputes go to court with "
        "the guardianship authority involved.",
        "104720:76;104720:88"),
    "family.domestic_violence": _l(
        "Tazyiq va zoʻravonlik qurboniga ichki ishlar organi himoya orderi beradi — u tajovuzkorga cheklovlar qoʻyadi.",
        "Жертве притеснения и насилия орган внутренних дел выдаёт охранный ордер, который ограничивает действия "
        "обидчика.",
        "The police issue a protection order to a victim of harassment or violence, placing restrictions on the "
        "abuser.",
        "4494709:23;4494709:26"),
    "family.grandparents": _l(
        "Bobo, buvi, aka-uka, opa-singillar va boshqa yaqin qarindoshlar bola bilan koʻrishish huquqiga ega; ota-ona "
        "toʻsqinlik qilsa, vasiylik va homiylik organi ularni bunga majbur qilishi, keyin esa nizoni sud hal qilishi "
        "mumkin.",
        "Дедушка, бабушка, братья, сёстры и другие близкие родственники имеют право на общение с ребёнком; если "
        "родители препятствуют, орган опеки может обязать их не мешать, а затем спор решает суд.",
        "Grandparents, siblings and other close relatives have a right to contact with the child; if the parents "
        "refuse, the guardianship authority can order them not to obstruct it, and then a court can decide.",
        "104720:77", "yes"),
    # ---------------------------------------------------------------- inheritance
    "inheritance": _l(
        "Meros vafot etgan kuni ochiladi; meros huquqi haqidagi guvohnomani notarius meros ochilgan kundan 6 oy "
        "oʻtgach beradi.",
        "Наследство открывается со дня смерти; свидетельство о праве на наследство нотариус выдаёт по истечении 6 "
        "месяцев.",
        "An estate opens on the day of death; the notary issues the certificate of inheritance after 6 months.",
        "180552:1116;180552:1146"),
    "inheritance.by_law": _l(
        "Qonun boʻyicha birinchi navbatda vafot etganning bolalari, eri yoki xotini va ota-onasi teng ulushda meros "
        "oladi.",
        "Наследники первой очереди по закону — дети, супруг и родители наследодателя; они наследуют в равных долях.",
        "First-order heirs by law are the deceased's children, spouse and parents, in equal shares.",
        "180552:1135"),
    "inheritance.spouse": _l(
        "Er yoki xotin birinchi navbat merosxoʻri: bolalar va ota-ona bilan teng ulushda meros oladi.",
        "Супруг — наследник первой очереди и наследует наравне с детьми и родителями.",
        "A spouse is a first-order heir, inheriting equally with the children and parents.",
        "180552:1135", "yes"),
    "inheritance.mandatory_share": _l(
        "Voyaga yetmagan yoki mehnatga layoqatsiz bolalar, mehnatga layoqatsiz er (xotin) va ota-ona vasiyatnomadan "
        "qatʼi nazar qonun boʻyicha tegadigan ulushning kamida yarmini oladi.",
        "Несовершеннолетние или нетрудоспособные дети, нетрудоспособные супруг и родители независимо от завещания "
        "получают не менее половины доли, причитающейся им по закону.",
        "Minor or disabled children and a disabled spouse or parents receive, regardless of the will, at least half of "
        "their share by law.",
        "180552:1142"),
    # ---------------------------------------------------------------- civil
    "civil.loan": _l(
        "Qarz qaytarilmasa, yozma talabdan keyin sudga daʼvo berasiz; umumiy daʼvo muddati — 3 yil.",
        "Если долг не возвращают, после письменного требования подаётся иск; общий срок исковой давности — 3 года.",
        "If a loan is not repaid, send a written demand and then sue; the general limitation period is 3 years.",
        "111189:150"),
    "civil.limitation": _l(
        "Umumiy daʼvo muddati — 3 yil; u huquqingiz buzilganini bilgan yoki bilishingiz lozim boʻlgan kundan "
        "boshlanadi.",
        "Общий срок исковой давности — 3 года; он начинается со дня, когда вы узнали или должны были узнать о "
        "нарушении права.",
        "The general limitation period is 3 years from the day you learned, or should have learned, of the violation.",
        "111189:150;111189:154"),
    "civil.unjust_enrichment": _l(
        "Asossiz olingan mol-mulk (masalan, xato oʻtkazilgan pul) egasiga qaytarilishi shart; ixtiyoriy qaytarmasa — "
        "sud orqali undiriladi.",
        "Неосновательно полученное имущество (например, ошибочно переведённые деньги) подлежит возврату; если не "
        "возвращают добровольно — через суд.",
        "Property received without legal grounds (such as money sent by mistake) must be returned; if not, it can be "
        "recovered in court.",
        "180552:1023", "yes"),
    "civil.moral_damage": _l(
        "Maʼnaviy zarar pul bilan qoplanadi; miqdorini sud azob-uqubatlar xususiyati va aybdorlik darajasiga qarab "
        "belgilaydi.",
        "Моральный вред компенсируется деньгами; размер определяет суд с учётом характера страданий и степени вины.",
        "Moral harm is compensated in money; the court sets the amount based on the suffering and the degree of fault.",
        "180552:1022;180552:1021", "yes"),
    "civil.lease": _l(
        "Turar joyni ijaraga berish shartnomasi yozma tuziladi va soliq organida hisobga qoʻyiladi.",
        "Договор найма жилого помещения заключается в письменной форме и ставится на учёт в налоговых органах.",
        "A residential lease must be in writing and registered with the tax authorities.",
        "180552:603"),
    "civil.lease.sublease": _l(
        "Ijaraga olingan uyni qoʻshimcha ijaraga berish faqat uy egasining (ijaraga beruvchining) roziligi bilan "
        "mumkin; qoʻshimcha ijarachi uyga mustaqil huquq olmaydi.",
        "Сдать нанятое жильё в поднаём можно только с согласия наймодателя; поднаниматель не получает "
        "самостоятельного права на жильё.",
        "You may sublet a rented home only with the landlord's consent; the subtenant gets no independent right to the "
        "home.",
        "180552:613", "yes"),
    "civil.lease.rent_increase": _l(
        "Ijara haqi miqdori shartnomada tomonlarning kelishuvi bilan belgilanadi; uni bir tomonlama oʻzgartirishga, "
        "qonun yoki shartnomada nazarda tutilgan hollardan tashqari, yoʻl qoʻyilmaydi.",
        "Размер платы за жильё устанавливается соглашением сторон в договоре; одностороннее изменение не допускается, "
        "кроме случаев, предусмотренных законом или договором.",
        "Rent is set by agreement in the lease; it cannot be changed unilaterally unless the law or the contract "
        "allows it.",
        "180552:611", "no"),
    "housing.eviction": _l(
        "Hech kim oʻz uy-joyidan sud qarorisiz va qonunga zid ravishda mahrum qilinishi mumkin emas; ijaraga "
        "beruvchi ham ijara shartnomasini faqat qonunda koʻrsatilgan hollarda (masalan, 6 oy haq toʻlanmasa) sud "
        "orqali bekor qildira oladi.",
        "Никто не может быть лишён жилища иначе как по решению суда и в соответствии с законом; наймодатель может "
        "расторгнуть договор найма только в суде и по основаниям закона (например, неуплата за 6 месяцев).",
        "No one may be deprived of their home except by a court decision under the law; a landlord can end a "
        "residential lease only through a court and on statutory grounds (e.g. 6 months of unpaid rent).",
        "6445145:47;180552:615", "no"),
    "finance.insurance_refusal": _l(
        "Sugʻurtalovchi tovon toʻlashni faqat qonunda koʻrsatilgan hollarda rad etishi mumkin — masalan, shartnoma "
        "sugʻurta hodisasidan oldin tugagan yoki u haqiqiy boʻlmasa.",
        "Страховщик вправе отказать в выплате только в случаях, указанных в законе, — например, если договор "
        "прекратился до страхового случая или является ничтожным.",
        "An insurer may refuse to pay only on the grounds set by law — for example, if the policy ended before the "
        "insured event or is void.",
        "180552:955"),
    "finance.credit_change": _l(
        "Isteʼmol krediti shartnomasi shartlari tomonlarning kelishuvi bilan oʻzgartiriladi, agar qonunchilikda "
        "boshqacha nazarda tutilmagan boʻlsa.",
        "Условия договора потребительского кредита изменяются по соглашению сторон, если иное не предусмотрено "
        "законодательством.",
        "The terms of a consumer credit agreement are changed by agreement of the parties, unless legislation provides "
        "otherwise.",
        "1004687:12", "no"),
    # ---------------------------------------------------------------- consumer
    "consumer": _l(
        "Sifatsiz tovar uchun almashtirish, narxni kamaytirish, nuqsonni bepul tuzatish yoki pulni qaytarishni talab "
        "qilishingiz mumkin.",
        "За товар с недостатками вы вправе потребовать замены, уменьшения цены, бесплатного устранения недостатков "
        "или возврата денег.",
        "For faulty goods you can demand a replacement, a price cut, a free repair or a refund.",
        "4704:13"),
    "consumer.return": _l(
        "Sifatli nooziq-ovqat tovarini xarid kunidan 10 kun ichida sotib olingan joyda oʻxshashiga almashtirish "
        "mumkin (tovar ishlatilmagan boʻlsa); oʻxshashi boʻlmasa — pul qaytariladi.",
        "Непродовольственный товар надлежащего качества можно обменять у продавца в течение 10 дней со дня покупки "
        "(если он не был в употреблении); при отсутствии аналогичного — вернуть деньги.",
        "Non-food goods of proper quality can be exchanged at the seller within 10 days of purchase (if unused); if "
        "no equivalent is available, you get your money back.",
        "4704:18", "yes"),
    "consumer.warranty": _l(
        "Uzoq muddat foydalaniladigan barcha tovarlar va xizmatlarga kafolat muddati belgilanishi shart; u sotilgan "
        "kundan hisoblanadi.",
        "На все товары длительного пользования и услуги устанавливается гарантийный срок; он исчисляется со дня "
        "продажи.",
        "All durable goods and services must carry a warranty period, counted from the day of sale.",
        "4704:11"),
    "consumer.food_safety": _l(
        "Xavfsiz boʻlmagan tovar yoki xizmat (jumladan, ovqat) sogʻligʻingizga zarar yetkazgan boʻlsa, sotuvchi yoki "
        "ijrochi zararni qoplashi shart — shartnoma bor-yoʻqligidan qatʼi nazar; maʼnaviy zarar ham qoplanadi.",
        "Если небезопасный товар или услуга (в том числе еда) причинили вред здоровью, продавец или исполнитель обязан "
        "его возместить — независимо от наличия договора; компенсируется и моральный вред.",
        "If unsafe goods or services (including food) harmed your health, the seller or provider must compensate it — "
        "with or without a contract — and moral harm is compensated too.",
        "4704:12;4704:20;4704:22", "yes"),
    # ---------------------------------------------------------------- traffic and admin
    "traffic.accident": _l(
        "YTH joyini tark etmang — buning uchun 15 BHM jarima bor; zarar OSAGO sugʻurtasi boʻyicha qoplanadi.",
        "Не покидайте место ДТП — за это штраф 15 БРВ; ущерб возмещается по ОСАГО.",
        "Do not leave the scene of an accident (a 15 BHM fine); damage is covered by compulsory motor insurance.",
        "97664:137;1342474:19"),
    "traffic.drunk": _l(
        "Mast holda transport boshqarish — 40 BHM jarima va 3 yilga haydovchilik huquqidan mahrum qilish.",
        "Управление транспортом в состоянии опьянения — штраф 40 БРВ и лишение права управления на 3 года.",
        "Drink-driving: a 40 BHM fine and a 3-year driving ban.",
        "97664:131"),
    "traffic.speeding": _l(
        "Tezlikni 20 km/soatgacha oshirish — 1 BHM jarima; koʻproq oshirilsa jarima 5, 9 va 15 BHMgacha ortadi.",
        "Превышение скорости до 20 км/ч — штраф 1 БРВ; при большем превышении — 5, 9 и до 15 БРВ.",
        "Speeding by up to 20 km/h costs 1 BHM; larger excesses cost 5, 9 and up to 15 BHM.",
        "97664:128.3"),
    "admin.appeal": _l(
        "Maʼmuriy jarima haqidagi qaror ustidan yuqori organga yoki sudga qaror nusxasi olingan kundan 10 kun ichida "
        "shikoyat qilinadi.",
        "Постановление об административном штрафе обжалуется в вышестоящий орган или суд в течение 10 дней со дня "
        "получения копии.",
        "An administrative fine can be appealed to a higher body or a court within 10 days of receiving the decision.",
        "97664:315;97664:316", "yes"),
    # ---------------------------------------------------------------- criminal, procedure, rights
    "criminal.arrest_rights": _l(
        "Ushlangan shaxs nima uchun gumon qilinayotganini bilish, advokat yoki yaqiniga qoʻngʻiroq qilish va ushlangan "
        "paytdan himoyachiga ega boʻlish huquqiga ega.",
        "Задержанный вправе знать, в чём его подозревают, позвонить адвокату или родственнику и иметь защитника с "
        "момента задержания.",
        "A detained person has the right to know the suspicion, to call a lawyer or relative and to have a defender "
        "from the moment of detention.",
        "111460:48"),
    "criminal.kidnapping": _l(
        "Odam oʻgʻirlash jinoyat boʻlib, 3 yildan 5 yilgacha ozodlikni cheklash yoki ozodlikdan mahrum qilish bilan "
        "jazolanadi; voyaga yetmaganga nisbatan sodir etilsa — 5 yildan 10 yilgacha ozodlikdan mahrum qilish.",
        "Похищение человека наказывается ограничением или лишением свободы от 3 до 5 лет; в отношении "
        "несовершеннолетнего — лишением свободы от 5 до 10 лет.",
        "Kidnapping is punished by 3 to 5 years of restricted liberty or imprisonment; kidnapping a minor carries 5 to "
        "10 years in prison.",
        "111453:137"),
    "procedure.court_cost_deferral": _l(
        "Sud mulkiy ahvolingizni hisobga olib, davlat daromadiga undiriladigan sud xarajatlarini toʻlashni "
        "kechiktirishi, boʻlib-boʻlib toʻlashga ruxsat berishi yoki ularning miqdorini kamaytirishi mumkin.",
        "С учётом имущественного положения суд может отсрочить или рассрочить уплату судебных расходов, взыскиваемых "
        "в доход государства, а также уменьшить их размер.",
        "Depending on your financial situation, the court can defer the court costs payable to the state, allow "
        "payment in instalments or reduce them.",
        "3517337:133", "yes"),
    "procedure.appeal": _l(
        "Fuqarolik ishi boʻyicha apellyatsiya shikoyati sud qarori qabul qilingan kundan 1 oy ichida beriladi.",
        "Апелляционная жалоба по гражданскому делу подаётся в течение 1 месяца со дня принятия решения.",
        "A civil appeal is filed within 1 month of the judgment.",
        "3517337:385.1", "yes"),
    "procedure.cassation": _l(
        "Kassatsiya shikoyati birinchi instansiya qarori qonuniy kuchga kirgan kundan 6 oy ichida beriladi.",
        "Кассационная жалоба подаётся в течение 6 месяцев со дня вступления решения первой инстанции в силу.",
        "A cassation appeal is filed within 6 months of the first-instance judgment taking effect.",
        "3517337:405.1", "yes"),
    "rights.appeals": _l(
        "Davlat organi murojaatni 15 kun ichida, qoʻshimcha oʻrganish kerak boʻlsa 1 oygacha koʻrib chiqishi shart.",
        "Госорган обязан рассмотреть обращение в течение 15 дней, а при необходимости дополнительного изучения — до 1 "
        "месяца.",
        "A state body must answer an appeal within 15 days, or up to 1 month if extra study is needed.",
        "3336169:28"),
    "rights.information_access": _l(
        "Har kim har qanday axborotni izlash, olish va tarqatish huquqiga ega; bu huquq faqat qonunga muvofiq va zarur "
        "darajada cheklanishi mumkin.",
        "Каждый имеет право искать, получать и распространять любую информацию; ограничение допускается только по "
        "закону и лишь в необходимой мере.",
        "Everyone has the right to seek, receive and impart any information; it may be restricted only by law and only "
        "as far as necessary.",
        "6445145:33"),
    "migration.dual_citizenship": _l(
        "Oʻzbekiston Respublikasi fuqarosining boshqa davlat fuqaroligiga mansubligi tan olinmaydi.",
        "Принадлежность гражданина Республики Узбекистан к гражданству иностранного государства не признаётся.",
        "Uzbekistan does not recognise a citizen's foreign citizenship.",
        "4761984:12", "no"),
    "migration.foreigner_property": _l(
        "Chet el fuqarolari va fuqaroligi boʻlmagan shaxslar Oʻzbekistonda mulk huquqidan Oʻzbekiston fuqarolari bilan "
        "teng foydalanadi, agar qonun yoki xalqaro shartnomada boshqacha belgilanmagan boʻlsa.",
        "Иностранные граждане и лица без гражданства пользуются в Узбекистане правом собственности наравне с "
        "гражданами, если иное не предусмотрено законами или международными договорами.",
        "Foreign nationals and stateless persons enjoy property rights in Uzbekistan on an equal footing with citizens, "
        "unless laws or international treaties provide otherwise.",
        "5443899:14", "yes"),
    "tax.audit": _l(
        "Soliq auditi 30 kundan oshmasligi kerak; u 2 oygacha, istisno hollarda 3 oygacha uzaytirilishi mumkin.",
        "Налоговый аудит не может длиться более 30 дней; его можно продлить до 2 месяцев, в исключительных случаях — "
        "до 3 месяцев.",
        "A tax audit may not last more than 30 days; it can be extended to 2 months, or 3 months in exceptional cases.",
        "4674902:141;4674902:142"),
    # ---------------------------------------------------------------- tax and social
    "tax.income": _l(
        "Rezident jismoniy shaxslar daromadiga 12 foiz stavkada soliq solinadi (dividend va foizlarga — 5 foiz).",
        "Доходы физических лиц — резидентов облагаются по ставке 12% (дивиденды и проценты — 5%).",
        "Residents' income is taxed at 12% (dividends and interest at 5%).",
        "4674902:381"),
    "tax.declaration": _l(
        "Jami yillik daromad deklaratsiyasi keyingi yilning 1-aprelidan kechiktirmay yashash joyidagi soliq organiga "
        "topshiriladi.",
        "Декларация о совокупном годовом доходе подаётся в налоговый орган по месту жительства не позднее 1 апреля "
        "следующего года.",
        "The annual income declaration is filed with the local tax office by 1 April of the following year.",
        "4674902:397"),
    "tax.rental_income": _l(
        "Ijaraga berishdan olingan daromad mulkiy daromad hisoblanadi va 12 foiz stavkada soliqqa tortiladi; uy-joy "
        "ijarasi shartnomasi soliq organida hisobga qoʻyiladi.",
        "Доход от сдачи имущества в аренду относится к имущественным доходам и облагается по ставке 12%; договор "
        "найма жилья ставится на учёт в налоговом органе.",
        "Rental income is property income taxed at 12%, and a residential lease must be registered with the tax "
        "authority.",
        "4674902:375;4674902:381;180552:603", "yes"),
    "social.pension_age": _l(
        "Yoshga doir pensiya: erkaklar 60 yoshda (kamida 25 yil staj), ayollar 55 yoshda (kamida 20 yil staj).",
        "Пенсия по возрасту: мужчины — с 60 лет при стаже не менее 25 лет, женщины — с 55 лет при стаже не менее 20 "
        "лет.",
        "Old-age pension: men at 60 with at least 25 years of service, women at 55 with at least 20 years.",
        "112314:7"),
    # ---------------------------------------------------------------- liability (answers to requests for wrongdoing)
    "tax.evasion": _l(
        "Daromadni yashirish yoki soliq toʻlashdan qasddan boʻyin tovlash uchun fuqaroga 15–25 BHM jarima solinadi; "
        "maʼmuriy jazodan keyin yana sodir etilsa yoki koʻp miqdorda boʻlsa — jinoiy javobgarlik, eng ogʻir holda 7 "
        "yilgacha ozodlikdan mahrum qilish. Yashirilgan daromad boʻyicha soliq toʻliq toʻlansa, ozodlikni cheklash va "
        "ozodlikdan mahrum qilish qoʻllanilmaydi.",
        "За умышленное сокрытие дохода или уклонение от уплаты налогов гражданину грозит штраф 15–25 БРВ; если это "
        "повторилось после административного взыскания или совершено в крупном размере — уголовная ответственность, в "
        "самых тяжёлых случаях до 7 лет лишения свободы. При полной уплате налогов на сокрытый доход ограничение и "
        "лишение свободы не применяются.",
        "Deliberately hiding income or evading tax costs an individual a fine of 15–25 BHM; if repeated after an "
        "administrative penalty or done on a large scale it is a crime punishable, in the gravest cases, by up to 7 "
        "years in prison. If the tax on the hidden income is paid in full, restriction or deprivation of liberty is not "
        "applied.",
        "97664:174;111453:184"),
    "criminal.forgery": _l(
        "Huquq beradigan yoki majburiyatdan ozod qiladigan rasmiy hujjatni (diplom, maʼlumotnoma, guvohnoma) "
        "soxtalashtirish yoki sotish — jinoyat: 50–100 BHM jarima yoki axloq tuzatish ishlari, takroran yoki guruh "
        "boʻlib — 5 yilgacha ozodlikdan mahrum qilish. Soxta hujjatdan bila turib foydalanish ham jazolanadi: 25–50 BHM "
        "jarimadan 2 yilgacha ozodlikdan mahrum qilishgacha.",
        "Изготовление, подделка или сбыт официального документа, дающего право или освобождающего от обязанности "
        "(диплом, справка, удостоверение), — преступление: штраф 50–100 БРВ или исправительные работы, повторно или "
        "группой — до 5 лет лишения свободы. Использование заведомо подложного документа тоже наказуемо: от штрафа "
        "25–50 БРВ до 2 лет лишения свободы.",
        "Making, forging or selling an official document that grants a right or releases from a duty (a diploma, "
        "certificate or licence) is a crime: a fine of 50–100 BHM or correctional labour, and up to 5 years in prison "
        "if repeated or done by a group. Knowingly using a forged document is punished too: from a fine of 25–50 BHM "
        "up to 2 years in prison.",
        "111453:228", "no"),
    "public.military_evasion": _l(
        "Muddatli harbiy yoki muqobil xizmatga chaqiruvdan uzrli sababsiz boʻyin tovlash maʼmuriy jazodan keyin "
        "takrorlansa — jinoyat: 50 BHMgacha jarima, majburiy jamoat ishlari yoki axloq tuzatish ishlari; oʻzini "
        "jarohatlash yoki hujjatni soxtalashtirish yoʻli bilan — 3 yilgacha ozodlikdan mahrum qilish. Qonuniy yoʻl — "
        "oilaviy sharoit, salomatlik yoki oʻqish sababli chaqiruvni kechiktirish yoki salomatligi boʻyicha ozod etish.",
        "Уклонение без уважительной причины от призыва на срочную военную или альтернативную службу после "
        "административного взыскания — преступление: штраф до 50 БРВ, обязательные общественные или исправительные "
        "работы; путём членовредительства или подлога документов — до 3 лет лишения свободы. Законный путь — отсрочка "
        "по семейным обстоятельствам, здоровью или для учёбы либо освобождение по состоянию здоровья.",
        "Evading conscription to compulsory military or alternative service without a valid reason, after an "
        "administrative penalty, is a crime: a fine of up to 50 BHM or community or correctional work; by self-injury "
        "or forged documents, up to 3 years in prison. The lawful route is a deferral for family circumstances, health "
        "or studies, or an exemption on health grounds.",
        "111453:225;78717:21;78717:22"),
    "procedure.enforcement_evasion": _l(
        "Sud hujjati yuklagan majburiyatni bajarishdan maʼmuriy jazodan keyin ham boʻyin tovlash — jinoyat: 100 "
        "BHMgacha jarima, majburiy jamoat ishlari, axloq tuzatish ishlari yoki 1 yilgacha ozodlikdan mahrum qilish. "
        "Davlat ijrochisi qarzdorni va uning mol-mulkini qidirishni eʼlon qilishi mumkin.",
        "Уклонение от исполнения судебного акта, продолжаемое после административного взыскания, — преступление: "
        "штраф до 100 БРВ, обязательные или исправительные работы либо до 1 года лишения свободы. Государственный "
        "исполнитель может объявить розыск должника и его имущества.",
        "Evading what a court decision requires, after an administrative penalty, is a crime: a fine of up to 100 BHM, "
        "community or correctional work, or up to 1 year in prison. The state enforcement officer can order a search "
        "for the debtor and the debtor's property.",
        "111453:232;26477:42", "no"),
}

_LEAD_ALIASES: dict[str, str] = {
    "labour.leave.duration": "labour.leave.annual",
    "labour.leave.pay": "labour.leave.annual",
    "family.divorce.registry": "family.divorce",
    "family.divorce.court": "family.divorce",
    "family.alimony.court": "family.alimony",
    "inheritance.general": "inheritance",
    "inheritance.opening": "inheritance",
    "inheritance.certificate": "inheritance",
    "civil.loan.unpaid": "civil.loan",
    "civil.lease.dwelling": "civil.lease",
    "civil.lease.form": "civil.lease",
    "consumer.defective": "consumer",
    "consumer.rights": "consumer",
    "social.pension_general": "social.pension_age",
}


def lead_for(concept_ids: list[str]) -> tuple[dict[str, str], list[tuple[str, str]]] | None:
    """(texts by language + optional "polarity", basis articles) for the best-matched situation.

    Only the first (most specific) situation is used, and only an exact id or an explicit alias counts: a parent
    situation's answer is often wrong for a sub-situation (child support shares do not apply to spousal support)."""
    if not concept_ids:
        return None
    cid = concept_ids[0]
    lead = LEADS.get(cid) or LEADS.get(_LEAD_ALIASES.get(cid, ""))
    if lead is None:
        return None
    pairs = [tuple(x.split(":", 1)) for x in lead.basis.split(";") if x]
    texts = {"uz": lead.uz, "ru": lead.ru, "en": lead.en}
    if lead.polarity:
        texts["polarity"] = lead.polarity
    return texts, pairs  # type: ignore[return-value]
