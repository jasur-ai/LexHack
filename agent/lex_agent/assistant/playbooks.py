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


def playbook_for(concept_ids: list[str]) -> Playbook | None:
    """Most specific playbook for the matched situations (exact id, then id prefixes)."""
    for cid in concept_ids:
        parts = cid.split(".")
        for n in range(len(parts), 0, -1):
            key = ".".join(parts[:n])
            if key in PLAYBOOKS:
                return PLAYBOOKS[key]
    return None


# One-sentence direct answers for "what do I do / how does it work" questions, each tied to the articles that
# state it (doc:article;...). Every figure here was checked against the article text in the index.
LEADS: dict[str, tuple[str, str, str, str]] = {
    "labour.dismissal.employer": (
        "Ish beruvchi tashabbusi bilan boʻshatish asosli boʻlishi shart; noqonuniy boʻlsa, buyruq nusxasini olgan "
        "kundan 3 oy ichida sudga ishga tiklash haqida murojaat qilishingiz mumkin.",
        "Увольнение по инициативе работодателя должно быть обоснованным; при незаконном увольнении можно обратиться в "
        "суд о восстановлении в течение 3 месяцев со дня вручения копии приказа.",
        "A dismissal by the employer must be justified; if it is unlawful you can sue for reinstatement within 3 months "
        "of receiving the dismissal order.",
        "6257288:161;6257288:560"),
    "labour.reinstatement": (
        "Ishga tiklash haqida sudga buyruq nusxasi topshirilgan kundan 3 oy ichida murojaat qilinadi; xodim sud "
        "xarajatlarini toʻlamaydi.",
        "Иск о восстановлении на работе подаётся в течение 3 месяцев со дня вручения копии приказа; работник "
        "освобождён от судебных расходов.",
        "A reinstatement claim is filed within 3 months of receiving the order; employees pay no court costs.",
        "6257288:560;6257288:562"),
    "labour.wage.delay": (
        "Ish haqi kechiktirilsa, ish beruvchi qarzdan tashqari har bir kechiktirilgan kun uchun Markaziy bank "
        "stavkasining 10 foizi miqdorida kompensatsiya toʻlashi shart.",
        "При задержке зарплаты работодатель помимо долга обязан выплатить компенсацию — 10% ставки Центрального банка "
        "за каждый день задержки.",
        "If wages are late, the employer must pay the arrears plus 10% of the Central Bank rate for each day of delay.",
        "6257288:333"),
    "labour.dismissal.own_will": (
        "Oʻz xohishingiz bilan ishdan ketish uchun ish beruvchini 14 kalendar kun oldin yozma ogohlantirasiz; "
        "hisob-kitob oxirgi ish kuni toʻlanadi.",
        "Чтобы уволиться по собственному желанию, предупредите работодателя письменно за 14 календарных дней; расчёт "
        "выплачивается в день увольнения.",
        "To resign, give your employer 14 calendar days' written notice; final pay is due on your last day.",
        "6257288:160;6257288:254"),
    "labour.leave": (
        "Har yilgi asosiy mehnat taʼtili kamida 21 kalendar kun; taʼtil vaqtida oʻrtacha ish haqi saqlanadi.",
        "Ежегодный основной трудовой отпуск — не менее 21 календарного дня; за время отпуска сохраняется средняя "
        "зарплата.",
        "Annual leave is at least 21 calendar days, paid at your average salary.",
        "6257288:217;6257288:233"),
    "family.divorce": (
        "Nikoh odatda sud orqali bekor qilinadi; ikkalangiz rozi boʻlsangiz va umumiy voyaga yetmagan farzandingiz "
        "boʻlmasa — FHDYO organida.",
        "Брак расторгается, как правило, в суде; при взаимном согласии супругов без общих несовершеннолетних детей — "
        "в органах ЗАГС.",
        "Divorce normally goes through a court; spouses who both agree and have no minor children can divorce at the "
        "civil registry office.",
        "104720:38;104720:42"),
    "family.alimony": (
        "Kelishuv boʻlmasa, sud aliment undiradi: 1 bolaga daromadning 1/4, 2 bolaga 1/3, 3 va undan ortiq bolaga 1/2 "
        "qismi.",
        "Без соглашения суд взыскивает алименты: на 1 ребёнка — 1/4 дохода, на 2 детей — 1/3, на 3 и более — 1/2.",
        "Without an agreement the court orders child support: 1/4 of income for one child, 1/3 for two, 1/2 for three "
        "or more.",
        "104720:99"),
    "family.child_residence": (
        "Bola bilan alohida yashovchi ota-ona u bilan koʻrishish va tarbiyasida qatnashish huquqiga ega; nizolarni "
        "vasiylik organi ishtirokida sud hal qiladi.",
        "Родитель, проживающий отдельно, вправе общаться с ребёнком и участвовать в его воспитании; споры решает суд "
        "с участием органа опеки.",
        "A parent living apart keeps the right to see the child and take part in upbringing; disputes go to court with "
        "the guardianship authority involved.",
        "104720:76;104720:88"),
    "family.domestic_violence": (
        "Tazyiq va zoʻravonlik qurboniga ichki ishlar organi himoya orderi beradi — u tajovuzkorga cheklovlar qoʻyadi.",
        "Жертве притеснения и насилия орган внутренних дел выдаёт охранный ордер, который ограничивает действия "
        "обидчика.",
        "The police issue a protection order to a victim of harassment or violence, placing restrictions on the "
        "abuser.",
        "4494709:23;4494709:26"),
    "inheritance": (
        "Meros vafot etgan kuni ochiladi; meros huquqi haqidagi guvohnomani notarius meros ochilgan kundan 6 oy "
        "oʻtgach beradi.",
        "Наследство открывается со дня смерти; свидетельство о праве на наследство нотариус выдаёт по истечении 6 "
        "месяцев.",
        "An estate opens on the day of death; the notary issues the certificate of inheritance after 6 months.",
        "180552:1116;180552:1146"),
    "civil.loan": (
        "Qarz qaytarilmasa, yozma talabdan keyin sudga daʼvo berasiz; umumiy daʼvo muddati — 3 yil.",
        "Если долг не возвращают, после письменного требования подаётся иск; общий срок исковой давности — 3 года.",
        "If a loan is not repaid, send a written demand and then sue; the general limitation period is 3 years.",
        "111189:150"),
    "civil.lease": (
        "Turar joyni ijaraga berish shartnomasi yozma tuziladi va soliq organida hisobga qoʻyiladi.",
        "Договор найма жилого помещения заключается в письменной форме и ставится на учёт в налоговых органах.",
        "A residential lease must be in writing and registered with the tax authorities.",
        "180552:603"),
    "consumer": (
        "Sifatsiz tovar uchun almashtirish, narxni kamaytirish, nuqsonni bepul tuzatish yoki pulni qaytarishni talab "
        "qilishingiz mumkin.",
        "За товар с недостатками вы вправе потребовать замены, уменьшения цены, бесплатного устранения недостатков "
        "или возврата денег.",
        "For faulty goods you can demand a replacement, a price cut, a free repair or a refund.",
        "4704:13"),
    "traffic.accident": (
        "YTH joyini tark etmang — buning uchun 15 BHM jarima bor; zarar OSAGO sugʻurtasi boʻyicha qoplanadi.",
        "Не покидайте место ДТП — за это штраф 15 БРВ; ущерб возмещается по ОСАГО.",
        "Do not leave the scene of an accident (a 15 BHM fine); damage is covered by compulsory motor insurance.",
        "97664:137;1342474:19"),
    "admin.appeal": (
        "Maʼmuriy jarima haqidagi qaror ustidan yuqori organga yoki sudga qaror nusxasi olingan kundan 10 kun ichida "
        "shikoyat qilinadi.",
        "Постановление об административном штрафе обжалуется в вышестоящий орган или суд в течение 10 дней со дня "
        "получения копии.",
        "An administrative fine can be appealed to a higher body or a court within 10 days of receiving the decision.",
        "97664:315;97664:316"),
    "criminal.arrest_rights": (
        "Ushlangan shaxs nima uchun gumon qilinayotganini bilish, advokat yoki yaqiniga qoʻngʻiroq qilish va ushlangan "
        "paytdan himoyachiga ega boʻlish huquqiga ega.",
        "Задержанный вправе знать, в чём его подозревают, позвонить адвокату или родственнику и иметь защитника с "
        "момента задержания.",
        "A detained person has the right to know the suspicion, to call a lawyer or relative and to have a defender "
        "from the moment of detention.",
        "111460:48"),
    "rights.appeals": (
        "Davlat organi murojaatni 15 kun ichida, qoʻshimcha oʻrganish kerak boʻlsa 1 oygacha koʻrib chiqishi shart.",
        "Госорган обязан рассмотреть обращение в течение 15 дней, а при необходимости дополнительного изучения — до 1 "
        "месяца.",
        "A state body must answer an appeal within 15 days, or up to 1 month if extra study is needed.",
        "3336169:28"),
    "tax.rental_income": (
        "Ha — ijaraga berishdan olingan daromad mulkiy daromad hisoblanadi va 12 foiz stavkada soliqqa tortiladi; "
        "uy-joy ijarasi shartnomasi soliq organida hisobga qoʻyiladi.",
        "Да — доход от сдачи имущества в аренду относится к имущественным доходам и облагается по ставке 12%; договор "
        "найма жилья ставится на учёт в налоговом органе.",
        "Yes — rental income is property income taxed at 12%, and a residential lease must be registered with the tax "
        "authority.",
        "4674902:375;4674902:381;180552:603"),
    "social.pension": (
        "Yoshga doir pensiya: erkaklar 60 yoshda (kamida 25 yil staj), ayollar 55 yoshda (kamida 20 yil staj).",
        "Пенсия по возрасту: мужчины — с 60 лет при стаже не менее 25 лет, женщины — с 55 лет при стаже не менее 20 "
        "лет.",
        "Old-age pension: men at 60 with at least 25 years of service, women at 55 with at least 20 years.",
        "112314:7"),
}


def lead_for(concept_ids: list[str]) -> tuple[dict[str, str], list[tuple[str, str]]] | None:
    """(text by language, basis articles) for the most specific matched situation that has a lead."""
    for cid in concept_ids:
        parts = cid.split(".")
        for n in range(len(parts), 0, -1):
            key = ".".join(parts[:n])
            if key in LEADS:
                uz, ru, en, basis = LEADS[key]
                pairs = [tuple(x.split(":", 1)) for x in basis.split(";") if x]
                return {"uz": uz, "ru": ru, "en": en}, pairs  # type: ignore[return-value]
    return None
