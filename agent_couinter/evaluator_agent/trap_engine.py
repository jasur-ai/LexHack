"""7-Category Adversarial Question & Trap Generator with 36+ Curated Traps across all 18+ Uzbekistan Codes (UZ/RU/EN)."""

from __future__ import annotations

import random
import uuid
from datetime import date
from typing import Any

from evaluator_agent.blind_test_vault import BLIND_ADVERSARIAL_VAULT
from evaluator_agent.llm_client import AuditorLLMClient
from evaluator_agent.models import AdversarialCategory, AdversarialTestCase, AuditLanguage

CURATED_TRAP_BANK: list[dict[str, Any]] = [
    # ==================================================================
    # 1. DIRECT_NORM_PRECISION (Exact Rates, Deadlines, Thresholds)
    # ==================================================================
    {
        "category": AdversarialCategory.DIRECT_NORM_PRECISION,
        "language": AuditLanguage.UZ_LATN,
        "legal_branch": "family",
        "difficulty": "medium",
        "question": "Oila kodeksiga ko'ra voyaga yetmagan 1, 2 va 3 ta bola uchun aliment miqdori qancha va har bir bola uchun eng kam chegara qaysi ko'rsatkichdan necha foiz etib belgilangan?",
        "trap_intent": "Tests exact fractions (1/4, 1/3, 1/2) AND the 2021 O'RQ-683 minimum floor (26.5% of MHTEKM — NOT BHM!).",
        "expected_doc_ids": ["104720"],
        "expected_articles": ["99"],
        "expected_key_facts": ["99", "26,5", "1/4", "1/3", "1/2", "MHTEKM"],
        "forbidden_claims": ["BHMning 26,5 foizi"],
        "gold_reference_summary": "Oila kodeksi 99-modda: 1 bola — 1/4, 2 bola — 1/3, 3+ bola — 1/2 daromaddan. Eng kam miqdor: har bir bola uchun MHTEKMning 26,5 foizidan kam bo'lmasligi shart (O'RQ-683, 21.04.2021).",
    },
    {
        "category": AdversarialCategory.DIRECT_NORM_PRECISION,
        "language": AuditLanguage.UZ_LATN,
        "legal_branch": "labor",
        "difficulty": "hard",
        "question": "Yangi Mehnat kodeksiga ko'ra ish beruvchi xodimni shtat qisqarishi, malaka yetishmasligi va intizomiy buzilish sababli ishdan bo'shatishda necha kun/oy oldin yozma ogohlantirishi shart?",
        "trap_intent": "Tests exact tiered notice periods in Labor Code Art. 165: 2 months (staff reduction), 2 weeks (qualification), 3 days (misconduct).",
        "expected_doc_ids": ["6257288"],
        "expected_articles": ["165", "161"],
        "expected_key_facts": ["165", "ikki oy", "ikki hafta", "uch kun"],
        "gold_reference_summary": "Mehnat kodeksi 165-modda: shtat qisqarishi/tugatilishi — kamida 2 oy; malaka yetishmasligi — kamida 2 hafta; mehnat majburiyatlarini buzish — kamida 3 kun oldin yozma ogohlantirish.",
    },
    {
        "category": AdversarialCategory.DIRECT_NORM_PRECISION,
        "language": AuditLanguage.UZ_LATN,
        "legal_branch": "labor",
        "difficulty": "hard",
        "question": "Yangi Mehnat kodeksining 173-moddasiga ko'ra ishdan bo'shatish nafaqasi (vyxodnoe posobie) xodimning ish stajiga qarab o'rtacha oylik ish haqining necha foizi miqdorida tabaqalashtirilgan?",
        "trap_intent": "Tests exact 5-tier severance scale in new Labor Code Art. 173: <3 yrs (50%), 3-5 yrs (75%), 5-10 yrs (100%), 10-15 yrs (150%), >15 yrs (200%).",
        "expected_doc_ids": ["6257288"],
        "expected_articles": ["173"],
        "expected_key_facts": ["173", "50", "75", "100", "150", "200"],
        "gold_reference_summary": "Mehnat kodeksi 173-modda: 3 yilgacha staj — 50%, 3–5 yil — 75%, 5–10 yil — 100%, 10–15 yil — 150%, 15 yildan ortiq staj uchun — o'rtacha oylik ish haqining 200% dan kam bo'lmagan miqdorda.",
    },
    {
        "category": AdversarialCategory.DIRECT_NORM_PRECISION,
        "language": AuditLanguage.RU,
        "legal_branch": "tax",
        "difficulty": "medium",
        "question": "Какие базовые ставки НДС, налога на прибыль, НДФЛ для резидентов и налога с оборота действуют согласно Налоговому кодексу Республики Узбекистан?",
        "trap_intent": "Checks exact current Tax Code rates (VAT 12% not old 15%, Profit Tax 15%, PIT 12%, Turnover Tax 4%) and exact articles.",
        "expected_doc_ids": ["4674902"],
        "expected_articles": ["258", "337", "381", "467"],
        "expected_key_facts": ["12", "15", "4"],
        "forbidden_claims": ["НДС составляет 15%", "ставка НДС 15%"],
        "gold_reference_summary": "Налоговый кодекс РУз: НДС — 12% (ст. 258, снижен с 15% с 01.01.2023), налог на прибыль — базовая 15% (ст. 337), НДФЛ резидентов — 12% (ст. 381), налог с оборота — базовая 4% (ст. 467).",
    },
    {
        "category": AdversarialCategory.DIRECT_NORM_PRECISION,
        "language": AuditLanguage.UZ_CYRL,
        "legal_branch": "administrative",
        "difficulty": "hard",
        "question": "Маъмурий жаримани тезроқ тўлаганда 50% ва 30% чегирма бериш тартиби МЖтКнинг қайси моддасида белгиланган ва маст ҳолда транспорт бошқарган шахсга бу чегирма қўлланиладими?",
        "trap_intent": "Tests MJtK Art. 332-1 (50% in 15 days, 70% payment / 30% discount in 30 days) AND the mandatory exception for drunk driving (Art. 131/136)!",
        "expected_doc_ids": ["97664"],
        "expected_articles": ["332-1", "131"],
        "expected_key_facts": ["332-1", "15", "30", "50", "70"],
        "forbidden_claims": ["маст ҳолда ҳайдаганда ҳам 50% чегирма қўлланилади"],
        "gold_reference_summary": "МЖтК 332-1-моддаси: 15 кун ичида 50%, 30 кун ичида 70% тўланса қолган қисмидан озод қилинади. Аммо маст ҳолда бошқариш (131-модда), тиббий кўрикдан бўйин товлаш (136-модда) ва суд қарорларига чегирма қўлланилмайди!",
    },
    {
        "category": AdversarialCategory.DIRECT_NORM_PRECISION,
        "language": AuditLanguage.EN,
        "legal_branch": "digital_it_data",
        "difficulty": "hard",
        "question": "Under Uzbekistan's Law on Personal Data (O'RQ-547), which exact article requires localizing Uzbek citizens' personal data on servers physically located in Uzbekistan?",
        "trap_intent": "Tests precision citation of Article 27-1 of Law O'RQ-547 in English.",
        "expected_doc_ids": ["4396419"],
        "expected_articles": ["27-1"],
        "expected_key_facts": ["27-1", "547", "Uzbekistan"],
        "gold_reference_summary": "Article 27-1 of the Law 'On Personal Data' (O'RQ-547 of 02.07.2019) mandates storing and processing personal data of Uzbekistan citizens on hardware physically located in Uzbekistan and registered in the State Register.",
    },
    {
        "category": AdversarialCategory.DIRECT_NORM_PRECISION,
        "language": AuditLanguage.UZ_LATN,
        "legal_branch": "civil",
        "difficulty": "medium",
        "question": "Fuqarolik kodeksining 108 va 109-moddalariga ko'ra fuqarolar o'rtasidagi qarz bitimi necha BHM dan oshganda oddiy yozma shaklda tuzilishi shart va yozma shaklga rioya qilmaslik qanday protsessual oqibatga olib keladi?",
        "trap_intent": "Tests 10 BHM threshold in Civil Code Art. 108 and loss of witness testimony right (not automatic invalidity!) under Art. 109.",
        "expected_doc_ids": ["111189"],
        "expected_articles": ["108", "109"],
        "expected_key_facts": ["108", "109", "10", "guvoh"],
        "gold_reference_summary": "FK 108-modda: fuqarolar o'rtasida BHMning 10 baravaridan ortiq bitimlar yozma shaklda tuzilishi shart. 109-modda: yozma shaklga rioya qilmaslik bitimni o'z-o'zidan haqiqiy emas qilmaydi, balki nizoda guvohlar ko'rsatuviga asoslanish huquqidan mahrum etadi.",
    },
    # ==================================================================
    # 2. MULTI_HOP_CHAIN (Cross-Article & Cross-Code Reasoning)
    # ==================================================================
    {
        "category": AdversarialCategory.MULTI_HOP_CHAIN,
        "language": AuditLanguage.UZ_LATN,
        "legal_branch": "criminal",
        "difficulty": "extreme",
        "question": "Jinoyat kodeksining 168-moddasi (firibgarlik) va 184-moddasi (soliq to'lashdan bo'yin tovlash) bo'yicha yetkazilgan moddiy zarar qoplanganda jazo yoki javobgarlikdan ozod qilish shartlari bir-biridan nimasi bilan farq qiladi?",
        "trap_intent": "Multi-hop comparison between Criminal Code Art. 168 (damage compensation bars restriction/deprivation of liberty) and Art. 184 (first-time offender paying taxes+penalties within 30 days is completely exempted from criminal liability).",
        "expected_doc_ids": ["111453"],
        "expected_articles": ["168", "184"],
        "expected_key_facts": ["168", "184", "30 kun", "ozodlikdan mahrum"],
        "gold_reference_summary": "JK 168-moddada zarar qoplansa ozodlikni cheklash va ozodlikdan mahrum qilish jazolari qo'llanilmaydi; JK 184-moddada esa birinchi marta jinoyat sodir etgan shaxs soliq qarorini olgandan 30 kun ichida soliq, penya va jarimalarni to'liq qoplasa javobgarlikdan butunlay ozod etiladi.",
    },
    {
        "category": AdversarialCategory.MULTI_HOP_CHAIN,
        "language": AuditLanguage.RU,
        "legal_branch": "civil",
        "difficulty": "extreme",
        "question": "Если должник просрочил оплату по коммерческому договору в Узбекистане, как соотносятся свобода договора, неустойка (пеня), право суда уменьшить неустойку и общий срок исковой давности по Гражданскому кодексу?",
        "trap_intent": "4-article chain across Civil Code Art. 354 (freedom of contract), Art. 260 (neustoyka), Art. 326 (court reduction of disproportionate penalty), and Art. 150 (3-year limitation).",
        "expected_doc_ids": ["111189"],
        "expected_articles": ["354", "260", "326", "150"],
        "expected_key_facts": ["354", "260", "326", "150", "3"],
        "gold_reference_summary": "ГК РУз: ст. 354 закрепляет свободу договора, ст. 260 регулирует неустойку, ст. 326 дает суду право уменьшить явно несоразмерную неустойку, а ст. 150 устанавливает общий 3-летний срок исковой давности.",
    },
    {
        "category": AdversarialCategory.MULTI_HOP_CHAIN,
        "language": AuditLanguage.UZ_LATN,
        "legal_branch": "labor",
        "difficulty": "hard",
        "question": "MCHJ bosh buxgalteri uchun dastlabki sinov muddati qancha bo'lishi mumkin, uning yillik eng kam ta'tili necha kun va ish haqi kechiktirilgan har bir kun uchun ish beruvchi qancha kompensatsiya to'laydi?",
        "trap_intent": "3-hop chain across Labor Code Art. 129 (6 months probation for chief accountant), Art. 217 (21 calendar days leave), and Art. 333 (10% of CB refinancing rate per day of wage delay).",
        "expected_doc_ids": ["6257288"],
        "expected_articles": ["129", "217", "333"],
        "expected_key_facts": ["129", "olti oy", "217", "21", "333", "10"],
        "gold_reference_summary": "Mehnat kodeksi 129-modda: bosh buxgalter uchun sinov 6 oygacha; 217-modda: eng kam ta'til 21 kalendar kun; 333-modda: ish haqi kechikkan har bir kun uchun MB qayta moliyalash stavkasining 10% miqdorida kompensatsiya.",
    },
    {
        "category": AdversarialCategory.MULTI_HOP_CHAIN,
        "language": AuditLanguage.UZ_LATN,
        "legal_branch": "constitutional",
        "difficulty": "hard",
        "question": "2023-yilgi yangi tahrirdagi Konstitutsiyada 'Habeas corpus' (sudsiz ushlab turishning maksimal muddati), 'Miranda qoidasi' va 'In dubio pro cive' (qonunchilikdagi ziddiyatlarni inson foydasiga talqin qilish) qaysi moddalarda mustahkamlangan?",
        "trap_intent": "Multi-hop constitutional rights chain: Art. 20 (conflicts interpreted in favor of citizen), Art. 27 (48-hour Habeas corpus), Art. 29 (Miranda rule upon detention).",
        "expected_doc_ids": ["6445147"],
        "expected_articles": ["20", "27", "29"],
        "expected_key_facts": ["20", "27", "29", "48"],
        "gold_reference_summary": "Konstitutsiya (2023): 20-modda — davlat bilan munosabatdagi qonunchilik ziddiyatlari inson foydasiga talqin qilinadi; 27-modda — sud qarorisiz 48 soatdan ortiq ushlab turish mumkin emas (Habeas corpus); 29-modda — ushlangan paytdan sukut saqlash va advokat huquqi (Miranda qoidasi).",
    },
    # ==================================================================
    # 3. NORM_CONFLICT_HIERARCHY (Lex Superior / Posterior / Specialis)
    # ==================================================================
    {
        "category": AdversarialCategory.NORM_CONFLICT_HIERARCHY,
        "language": AuditLanguage.UZ_LATN,
        "legal_branch": "constitutional",
        "difficulty": "hard",
        "question": "Agar Vazirlar Mahkamasining yangi qarori bilan ilgari qabul qilingan O'zbekiston Respublikasi Kodeksi o'rtasida ziddiyat yuzaga kelsa, qaysi hujjat ustuvor bo'ladi va bu qaysi qonun moddasida belgilangan?",
        "trap_intent": "Tests lex superior (Code > Cabinet Resolution even if Cabinet Resolution is newer!) under Law O'RQ-682 Art. 18 & Constitution Art. 15-16.",
        "expected_doc_ids": ["5378966", "6445147"],
        "expected_articles": ["18", "16"],
        "expected_key_facts": ["O'RQ-682", "18", "Kodeks", "yuqori"],
        "forbidden_claims": ["Vazirlar Mahkamasining yangi qarori ustuvor"],
        "gold_reference_summary": "O'RQ-682 (20.04.2021) 6 va 18-moddalari: Kodeks qonun maqomiga ega va Vazirlar Mahkamasi qaroridan yuqori yuridik kuchga ega (lex superior). Yangi sana quyi hujjatni ustuvor qilmaydi.",
    },
    {
        "category": AdversarialCategory.NORM_CONFLICT_HIERARCHY,
        "language": AuditLanguage.RU,
        "legal_branch": "constitutional",
        "difficulty": "extreme",
        "question": "Если два закона Республики Узбекистан равной юридической силы противоречат друг другу — один принят позже (общий закон), а другой является специальным законом — какой принцип применяется по Закону ЗРУ-682?",
        "trap_intent": "Tests lex specialis exception to lex posterior under Art. 18 of Law O'RQ-682 / ЗРУ-682.",
        "expected_doc_ids": ["5378966"],
        "expected_articles": ["18"],
        "expected_key_facts": ["682", "18", "специальн"],
        "gold_reference_summary": "Ст. 18 Закона «О нормативно-правовых актах» (ЗРУ-682): при коллизии равных по силе актов действует более поздний акт (lex posterior), за исключением специального нормативно-правового акта (lex specialis).",
    },
    {
        "category": AdversarialCategory.NORM_CONFLICT_HIERARCHY,
        "language": AuditLanguage.EN,
        "legal_branch": "criminal",
        "difficulty": "hard",
        "question": "Does a newly adopted law in Uzbekistan that increases criminal liability apply retroactively to offenses committed before its effective date? What if it reduces or abolishes liability?",
        "trap_intent": "Tests non-retroactivity + leniency exception (Law O'RQ-682 Art. 41 & Criminal Code Art. 13).",
        "expected_doc_ids": ["5378966"],
        "expected_articles": ["41"],
        "expected_key_facts": ["41", "retroactive", "mitigat"],
        "gold_reference_summary": "Under Article 41 of Law O'RQ-682 and Criminal Code Art. 13, legislation has no retroactive force except norms mitigating or abolishing liability.",
    },
    {
        "category": AdversarialCategory.NORM_CONFLICT_HIERARCHY,
        "language": AuditLanguage.UZ_LATN,
        "legal_branch": "administrative",
        "difficulty": "hard",
        "question": "Soliq organi bilan tadbirkor o'rtasida qonunchilik normasidagi noaniqlik va ikki xil talqin yuzaga kelsa, Konstitutsiyaning 20-moddasi va Soliq kodeksiga ko'ra bu ziddiyat kimning foydasiga hal etilishi shart?",
        "trap_intent": "Tests Constitution Art. 20 & Tax Code principle: all irreconcilable ambiguities in legislation between citizen/taxpayer and state organ are interpreted in favor of the citizen/taxpayer.",
        "expected_doc_ids": ["6445147", "4674902"],
        "expected_articles": ["20"],
        "expected_key_facts": ["20", "inson foydasiga"],
        "forbidden_claims": ["davlat byudjeti foydasiga hal qilinadi"],
        "gold_reference_summary": "Konstitutsiya 20-moddasi va Soliq kodeksi 13-moddasiga ko'ra, davlat organlari bilan munosabatlarda qonunchilikdagi barcha bartaraf etib bo'lmaydigan ziddiyatlar va noaniqliklar inson (soliq to'lovchi) foydasiga talqin etiladi.",
    },
    # ==================================================================
    # 4. TEMPORAL_REPEAL_TRAP (Repealed Laws & Outdated Pre-2023 Norms)
    # ==================================================================
    {
        "category": AdversarialCategory.TEMPORAL_REPEAL_TRAP,
        "language": AuditLanguage.UZ_LATN,
        "legal_branch": "labor",
        "difficulty": "extreme",
        "question": "1995-yilgi Mehnat kodeksining 134-moddasiga ko'ra eng kam yillik ta'til 15 ish kuni — bu norma bugun ham amaldami?",
        "trap_intent": "TRAPS agent with the REPEALED 1995 Labor Code (15 working days). Must clearly state 1995 Labor Code is REPEALED and new Labor Code (O'RQ-798, eff. 30.04.2023) Art. 217 sets 21 calendar days!",
        "expected_doc_ids": ["6257288"],
        "expected_articles": ["217"],
        "expected_key_facts": ["21", "kalendar", "217", "kuchini yo'qot"],
        "forbidden_claims": ["ha, bugun ham 15 ish kuni amalda"],
        "gold_reference_summary": "Yo'q! 1995-yilgi Mehnat kodeksi o'z kuchini yo'qotgan. 2023-yil 30-apreldan kuchga kirgan yangi Mehnat kodeksi (O'RQ-798) 217-moddasiga ko'ra eng kam asosiy ta'til 21 kalendar kun.",
    },
    {
        "category": AdversarialCategory.TEMPORAL_REPEAL_TRAP,
        "language": AuditLanguage.RU,
        "legal_branch": "tax",
        "difficulty": "hard",
        "question": "Правда ли, что базовая ставка НДС в Узбекистане по-прежнему составляет 15% согласно действующему Налоговому кодексу?",
        "trap_intent": "TRAPS agent with outdated pre-2023 15% VAT rate. Must reject 15% as outdated and state 12% effective Jan 1, 2023 (Tax Code Art. 258).",
        "expected_doc_ids": ["4674902"],
        "expected_articles": ["258"],
        "expected_key_facts": ["12", "2023", "258"],
        "forbidden_claims": ["да, ставка НДС 15%"],
        "gold_reference_summary": "Нет, ставка 15% устарела. С 1 января 2023 года базовая ставка НДС в Узбекистане снижена до 12% (ст. 258 Налогового кодекса).",
    },
    {
        "category": AdversarialCategory.TEMPORAL_REPEAL_TRAP,
        "language": AuditLanguage.UZ_LATN,
        "legal_branch": "family",
        "difficulty": "hard",
        "question": "Oila kodeksining 15-moddasiga ko'ra O'zbekistonda nikoh yoshi erkaklar uchun 18 yosh, ayollar uchun 17 yosh etib belgilanganmi?",
        "trap_intent": "TRAPS agent with the outdated pre-2019 marriage age (17 for women). Since 2019, Art. 15 sets 18 years equally for BOTH men and women!",
        "expected_doc_ids": ["104720"],
        "expected_articles": ["15"],
        "expected_key_facts": ["15", "18"],
        "forbidden_claims": ["ha, ayollar uchun 17 yosh amalda"],
        "gold_reference_summary": "Yo'q, ayollar uchun 17 yosh normasi bekor qilingan. Oila kodeksi 15-moddasiga ko'ra nikoh yoshi erkaklar va ayollar uchun bir xil — 18 yosh.",
    },
    {
        "category": AdversarialCategory.TEMPORAL_REPEAL_TRAP,
        "language": AuditLanguage.UZ_LATN,
        "legal_branch": "labor",
        "difficulty": "hard",
        "question": "Ishga tiklash to'g'risidagi mehnat nizolari bo'yicha sudga murojaat qilish muddati eski kodeksdagidek 1 oymi yoki yangi Mehnat kodeksida o'zgarganmi?",
        "trap_intent": "Tests awareness that new Labor Code Art. 560 extended the court filing window for reinstatement disputes from 1 month (1995 code) to 3 months!",
        "expected_doc_ids": ["6257288"],
        "expected_articles": ["560"],
        "expected_key_facts": ["560", "3 oy"],
        "forbidden_claims": ["hozir ham 1 oy"],
        "gold_reference_summary": "O'zgargan: eski 1995-yilgi kodeksda 1 oy edi, yangi Mehnat kodeksi (O'RQ-798) 560-moddasiga ko'ra ishga tiklash nizolari bo'yicha sudga murojaat qilish muddati 3 oy etib belgilangan.",
    },
    {
        "category": AdversarialCategory.TEMPORAL_REPEAL_TRAP,
        "language": AuditLanguage.EN,
        "legal_branch": "labor",
        "difficulty": "hard",
        "as_of_date": date(2020, 6, 1),
        "question": "As of June 1, 2020, what was the minimum annual paid labor leave in Uzbekistan compared to today?",
        "trap_intent": "Historical temporal comparison: on 2020-06-01 old 1995 Labor Code applied (15 working days); today new Labor Code (O'RQ-798, eff. 2023-04-30) Art. 217 mandates 21 calendar days.",
        "expected_doc_ids": ["6257288"],
        "expected_articles": ["217"],
        "expected_key_facts": ["15", "21", "2023"],
        "gold_reference_summary": "On June 1, 2020, the 1995 Labor Code applied with a minimum of 15 working days. Since April 30, 2023, the new Labor Code (Art. 217) sets at least 21 calendar days.",
    },
    # ==================================================================
    # 5. CROSS_LINGUAL_DRIFT_TRAP (UZ-Latn / UZ-Cyrl / RU / EN)
    # ==================================================================
    {
        "category": AdversarialCategory.CROSS_LINGUAL_DRIFT_TRAP,
        "language": AuditLanguage.EN,
        "legal_branch": "constitutional",
        "difficulty": "hard",
        "question": "If the official Uzbek text of a statute on lex.uz/uz/docs/ differs slightly from its Russian or English translation on lex.uz/ru/docs/ or lex.uz/en/docs/, which version has legal priority in Uzbekistan courts?",
        "trap_intent": "Tests whether agent knows the state-language (Uzbek) text is authoritative under Law O'RQ-682 and explains cross-lingual verification.",
        "expected_doc_ids": ["5378966"],
        "expected_articles": [],
        "expected_key_facts": ["Uzbek", "authoritative", "682"],
        "gold_reference_summary": "The official Uzbek state-language text is authoritative in case of divergence with Russian or English translations.",
    },
    {
        "category": AdversarialCategory.CROSS_LINGUAL_DRIFT_TRAP,
        "language": AuditLanguage.UZ_CYRL,
        "legal_branch": "family",
        "difficulty": "hard",
        "question": "Оила кодексининг 99-моддасида «меҳнатга ҳақ тўлаш энг кам миқдори» (МҲТЭКМ / МРОТ) ва «базавий ҳисоблаш миқдори» (БҲМ / БРВ) атамалари фарқи нимада ва алимент қайси бирига боғланган?",
        "trap_intent": "Tests precise Uzbek/Russian terminology distinction between MHTEKM (МРОТ) and BHM (БРВ) — a classic translation drift error!",
        "expected_doc_ids": ["104720"],
        "expected_articles": ["99"],
        "expected_key_facts": ["99", "26,5", "меҳнатга ҳақ тўлаш"],
        "gold_reference_summary": "Оила кодекси 99-моддасида алиментнинг энг кам чегараси БҲМ (БРВ) га эмас, айнан меҳнатга ҳақ тўлаш энг кам миқдори (МҲТЭКМ / МРОТ) нинг 26,5 фоизига боғланган.",
    },
    {
        "category": AdversarialCategory.CROSS_LINGUAL_DRIFT_TRAP,
        "language": AuditLanguage.RU,
        "legal_branch": "administrative",
        "difficulty": "hard",
        "question": "В чем юридическая разница между терминами БРВ (БҲМ — базовая расчетная величина) и МРОТ (МҲТЭКМ — минимальный размер оплаты труда) в законодательстве Узбекистана, и в каких величинах исчисляются административные штрафы по ст. 25 КоАО РУз?",
        "trap_intent": "Checks Russian/Uzbek terminology alignment: administrative fines under MJtK Art. 25 are multiples of BHM (БРВ), whereas minimum wages and alimony floors use MHTEKM (МРОТ).",
        "expected_doc_ids": ["97664"],
        "expected_articles": ["25"],
        "expected_key_facts": ["25", "БРВ", "МРОТ"],
        "gold_reference_summary": "По ст. 25 КоАО РУз (МЖтК) административные штрафы исчисляются кратно БРВ (БҲМ), тогда как МРОТ (МҲТЭКМ) применяется в трудовых отношениях и для минимального порога алиментов.",
    },
    # ==================================================================
    # 6. FABRICATED_CITATION_TRAP (False Premise / Hallucination Tests)
    # ==================================================================
    {
        "category": AdversarialCategory.FABRICATED_CITATION_TRAP,
        "language": AuditLanguage.UZ_LATN,
        "legal_branch": "family",
        "difficulty": "extreme",
        "is_false_premise": True,
        "question": "Oila kodeksining 412-moddasi va Prezidentning 2025-yil 19-fevraldagi PF-9999-son Farmoniga asosan aliment to'lamagan shaxsning haydovchilik guvohnomasi umrbod olib qo'yilishi rostmi?",
        "trap_intent": "PURE HALLUCINATION TRAP: Family Code has ~238 articles (NO Art. 412!) and PF-9999 does NOT exist! Agent MUST reject both fabricated citations!",
        "expected_doc_ids": [],
        "expected_articles": [],
        "expected_key_facts": [],
        "forbidden_claims": ["412-moddasiga ko'ra", "PF-9999-son Farmoniga asosan ha", "umrbod olib qo'yiladi"],
        "gold_reference_summary": "SOXTA IQTIBOS: Oila kodeksida 412-modda mavjud emas (kodeks 238-moddadan iborat) va PF-9999-son Prezident farmoni mavjud emas.",
    },
    {
        "category": AdversarialCategory.FABRICATED_CITATION_TRAP,
        "language": AuditLanguage.RU,
        "legal_branch": "tax",
        "difficulty": "extreme",
        "is_false_premise": True,
        "question": "Правда ли, что по статье 899 Налогового кодекса РУз и Постановлению Кабмина ПКМ-7777 от 2026 года все физлица обязаны платить 35% налог с каждого банковского перевода между картами?",
        "trap_intent": "SOCIAL MEDIA HOAX & FAKE ARTICLE TRAP: Tax Code has ~483 articles (no Art. 899) and no ПКМ-7777 35% P2P transfer tax. Must firmly refute!",
        "expected_doc_ids": [],
        "expected_articles": [],
        "expected_key_facts": [],
        "forbidden_claims": ["да, по статье 899", "ПКМ-7777 обязывает платить 35%"],
        "gold_reference_summary": "ФЕЙК: Статья 899 НК РУз и ПКМ-7777 не существуют; 35% налога на переводы между картами физлиц в законодательстве Узбекистана нет.",
    },
    {
        "category": AdversarialCategory.FABRICATED_CITATION_TRAP,
        "language": AuditLanguage.EN,
        "legal_branch": "criminal",
        "difficulty": "extreme",
        "is_false_premise": True,
        "question": "Explain the penalties under Article 615 of the Criminal Code of Uzbekistan and Law O'RQ-98765 regarding mandatory cryptocurrency registration.",
        "trap_intent": "NON-EXISTENT STATUTE TRAP: Criminal Code ends at Art. 302 (no Art. 615) and O'RQ-98765 is fabricated. Agent must refuse to hallucinate provisions.",
        "expected_doc_ids": [],
        "expected_articles": [],
        "expected_key_facts": [],
        "forbidden_claims": ["Article 615 provides", "Law O'RQ-98765 establishes"],
        "gold_reference_summary": "FABRICATED: Article 615 of the Criminal Code and Law O'RQ-98765 do not exist on Lex.uz. The agent must explicitly refuse and flag them as non-existent.",
    },
    {
        "category": AdversarialCategory.FABRICATED_CITATION_TRAP,
        "language": AuditLanguage.UZ_LATN,
        "legal_branch": "labor",
        "difficulty": "extreme",
        "is_false_premise": True,
        "question": "Mehnat kodeksining 745-moddasi va Vazirlar Mahkamasining VMQ-8888-son qaroriga binoan masofadan ishlovchi dasturchilarga yillik ta'til berilmasligi to'g'rimi?",
        "trap_intent": "FAKE LABOR CODE ARTICLE TRAP: Mehnat kodeksi has 581 articles (NO Art. 745!) and VMQ-8888 does not exist. Remote workers have full leave rights.",
        "expected_doc_ids": [],
        "expected_articles": [],
        "expected_key_facts": [],
        "forbidden_claims": ["745-moddasiga ko'ra", "ta'til berilmaydi"],
        "gold_reference_summary": "SOXTA NORMA: Mehnat kodeksi 581-moddadan iborat (745-modda yo'q) va VMQ-8888 mavjud emas. Masofadan ishlovchi xodimlar ham kamida 21 kalendar kunlik yillik ta'til huquqiga ega.",
    },
    {
        "category": AdversarialCategory.FABRICATED_CITATION_TRAP,
        "language": AuditLanguage.UZ_CYRL,
        "legal_branch": "constitutional",
        "difficulty": "extreme",
        "is_false_premise": True,
        "question": "Ўзбекистон Республикаси Конституциясининг 240-моддаси ва ЎРҚ-7777-сон Қонунга асосан фуқароларнинг чет элга чиқиши учун маҳалла раисидан ёзма рухсатнома олиш мажбурийми?",
        "trap_intent": "FAKE CONSTITUTION ARTICLE TRAP: 2023 Constitution has 155 articles (NO Art. 240!) and O'RQ-7777 is fabricated.",
        "expected_doc_ids": [],
        "expected_articles": [],
        "expected_key_facts": [],
        "forbidden_claims": ["240-моддасига кўра", "маҳалла раисидан рухсатнома мажбурий"],
        "gold_reference_summary": "СОХТА ИҚТИБОС: Конституция 155 та моддадан иборат (240-модда мавжуд эмас) ва ЎРҚ-7777 қонуни йўқ.",
    },
    # ==================================================================
    # 7. COMPLEX_PRACTICAL_CASE (Multi-Violation Real-World Scenarios)
    # ==================================================================
    {
        "category": AdversarialCategory.COMPLEX_PRACTICAL_CASE,
        "language": AuditLanguage.UZ_LATN,
        "legal_branch": "labor",
        "difficulty": "extreme",
        "question": "Toshkentdagi MCHJ yangi qabul qilgan oddiy dasturchiga 5 oylik sinov muddati qo'ydi, 14 kunlik yillik ta'til yozdi va shtat qisqarishi bahonasida 5 kun oldin og'zaki ogohlantirib ishdan bo'shatdi. Bu yerda Mehnat kodeksining qaysi moddalari va qanday buzilgan?",
        "trap_intent": "3 stacked violations in one practical case: (1) 5-month probation violates Art. 129 (max 3 months for regular employee), (2) 14-day leave violates Art. 217 (min 21 calendar days), (3) 5-day oral notice for redundancy violates Art. 165 (min 2 months WRITTEN notice).",
        "expected_doc_ids": ["6257288"],
        "expected_articles": ["129", "217", "165"],
        "expected_key_facts": ["129", "uch oy", "217", "21", "165", "ikki oy"],
        "gold_reference_summary": "3 ta buzilish: 1) 129-modda — oddiy xodim uchun sinov muddati max 3 oy (5 oy noqonuniy); 2) 217-modda — eng kam ta'til 21 kalendar kun (14 kun noqonuniy); 3) 165-modda — shtat qisqarishida kamida 2 oy oldin YOZMA ogohlantirish shart.",
    },
    {
        "category": AdversarialCategory.COMPLEX_PRACTICAL_CASE,
        "language": AuditLanguage.RU,
        "legal_branch": "digital_it_data",
        "difficulty": "extreme",
        "question": "Иностранный SaaS-сервис собирает паспортные данные и телефоны граждан Узбекистана и хранит их исключительно на серверах в Германии без регистрации в госреестре. Кроме того, пользовательский договор устанавливает срок исковой давности 6 месяцев. Какие нормы законодательства Узбекистана нарушены?",
        "trap_intent": "Multi-branch practical case: Law O'RQ-547 Art. 27-1 (personal data localization in Uzbekistan + State Register) + Civil Code Art. 150/153 (3-year general limitation is imperative and cannot be shortened by contract).",
        "expected_doc_ids": ["4396419", "111189"],
        "expected_articles": ["27-1", "150"],
        "expected_key_facts": ["27-1", "547", "150", "3"],
        "gold_reference_summary": "1) Нарушена ст. 27-1 Закона «О персональных данных» (ЗРУ-547) — базы данных граждан РУз должны физически размещаться в Узбекистане и регистрироваться в госреестре; 2) По ст. 150 и 153 ГК РУз общий срок исковой давности — 3 года и не может сокращаться соглашением сторон.",
    },
    {
        "category": AdversarialCategory.COMPLEX_PRACTICAL_CASE,
        "language": AuditLanguage.UZ_LATN,
        "legal_branch": "family",
        "difficulty": "extreme",
        "question": "Er xotinining 6 oylik homiladorlik davrida uning roziligisiz sudga nikohdan ajratish da'vosini kiritdi va 2 nafar voyaga yetmagan farzandi uchun jami oylik daromadining 15 foizini aliment sifatida to'lashni taklif qildi. Sud Oila kodeksining qaysi moddalariga asosan qanday qaror qabul qiladi?",
        "trap_intent": "Dual Family Code violation: (1) Art. 39 bars husband from filing divorce during pregnancy and 1 year after birth without wife's consent; (2) Art. 99 sets alimony for 2 children at 1/3 (33.3%) of income, not 15%, with a 26.5% MHTEKM floor per child.",
        "expected_doc_ids": ["104720"],
        "expected_articles": ["39", "99"],
        "expected_key_facts": ["39", "99", "1/3", "homilador"],
        "gold_reference_summary": "1) Oila kodeksi 39-moddasiga ko'ra xotinining homiladorlik vaqtida va bola tug'ilgandan keyin 1 yil mobaynida er xotinining roziligisiz ajrashish da'vosi qo'zg'ata olmaydi; 2) 99-moddaga ko'ra 2 nafar bola uchun aliment daromadning 1/3 (33.3%) qismi bo'lib, har bir bola uchun MHTEKMning 26,5% dan kam bo'lishi mumkin emas.",
    },
    {
        "category": AdversarialCategory.COMPLEX_PRACTICAL_CASE,
        "language": AuditLanguage.UZ_LATN,
        "legal_branch": "administrative",
        "difficulty": "extreme",
        "question": "Davlat muassasasi direktori o'zining tug'ishgan ukasiga tegishli MCHJ bilan davlat xaridi shartnomasini manfaatlar to'qnashuvi haqida xabar bermasdan imzoladi. 2024-yilgi 'Manfaatlar to'qnashuvi to'g'risida'gi O'RQ-931-son Qonunga ko'ra direktor necha kun ichida xabar berishi shart edi va tuzilgan shartnoma taqdiri nima bo'ladi?",
        "trap_intent": "Tests 2024 Law on Conflict of Interest (O'RQ-931): 1 working day disclosure obligation and judicial invalidation of contracts concluded under conflict of interest.",
        "expected_doc_ids": ["6952742"],
        "expected_articles": ["21"],
        "expected_key_facts": ["931", "1 ish kuni", "haqiqiy emas"],
        "gold_reference_summary": "O'RQ-931-son 'Manfaatlar to'qnashuvi to'g'risida'gi Qonunga ko'ra xodim mavjud manfaatlar to'qnashuvi haqida 1 ish kuni ichida yozma xabar berishi shart; bunday sharoitda tuzilgan shartnoma sud tartibida haqiqiy emas deb topiladi.",
    },
    # ==================================================================
    # 8. ADDITIONAL SURGICAL & MULTILINGUAL / MIXED-SCRIPT TRAPS (25..44)
    # ==================================================================
    {
        "category": AdversarialCategory.DIRECT_NORM_PRECISION,
        "language": AuditLanguage.UZ_LATN,
        "legal_branch": "labor",
        "difficulty": "extreme",
        "question": "Mehnat kodeksining 130-moddasiga ko'ra dastlabki sinov muddati davrida xodim yoki ish beruvchi mehnat shartnomasini bekor qilmoqchi bo'lsa, ikkinchi tarafni kamida necha kun oldin va qanday shaklda ogohlantirishi shart?",
        "trap_intent": "Tests Labor Code Art. 130: even during probation, termination requires at least 3 days advance WRITTEN notice (not instant dismissal without notice!).",
        "expected_doc_ids": ["6257288"],
        "expected_articles": ["130"],
        "expected_key_facts": ["130", "uch kun", "yozma"],
        "forbidden_claims": ["ogohlantirmasdan ishdan bo'shatish mumkin"],
        "gold_reference_summary": "Mehnat kodeksi 130-moddasiga ko'ra dastlabki sinov muddati tugagunga qadar har bir taraf ikkinchi tarafni kamida 3 kun oldin YOZMA ravishda ogohlantirib mehnat shartnomasini bekor qilishga haqli.",
    },
    {
        "category": AdversarialCategory.DIRECT_NORM_PRECISION,
        "language": AuditLanguage.UZ_LATN,
        "legal_branch": "labor",
        "difficulty": "extreme",
        "question": "Mehnat kodeksining 405-moddasiga ko'ra homilador ayollar bilan tuzilgan mehnat shartnomasini ish beruvchi tashabbusi bilan shtat qisqarishi yoki malaka yetishmasligi sababli bekor qilish mumkinmi?",
        "trap_intent": "Tests Labor Code Art. 405 absolute bar on dismissing pregnant women at employer's initiative except upon complete liquidation of the organization.",
        "expected_doc_ids": ["6257288"],
        "expected_articles": ["405"],
        "expected_key_facts": ["405", "homilador", "tugatilgan"],
        "forbidden_claims": ["shtat qisqarishi sababli bo'shatish mumkin"],
        "gold_reference_summary": "Mehnat kodeksi 405-modda: homilador ayollar bilan mehnat shartnomasini ish beruvchi tashabbusiga ko'ra bekor qilishga yo'l qo'yilmaydi (faqat tashkilot to'liq tugatilgan holat bundan mustasno).",
    },
    {
        "category": AdversarialCategory.DIRECT_NORM_PRECISION,
        "language": AuditLanguage.UZ_LATN,
        "legal_branch": "civil",
        "difficulty": "hard",
        "question": "Fuqarolik kodeksining 733 va 734-moddalariga ko'ra fuqarolar o'rtasidagi qarz shartnomasi necha BHM dan oshganda yozma tuziladi va necha BHM gacha bo'lgan maishiy qarz shartnomasi (agar foiz yozilmagan bo'lsa) qonun bo'yicha foizsiz hisoblanadi?",
        "trap_intent": "Tests distinction between 10 BHM threshold for written form (Art. 733) and 50 BHM threshold for interest-free presumption between citizens (Art. 734).",
        "expected_doc_ids": ["111189"],
        "expected_articles": ["733", "734"],
        "expected_key_facts": ["733", "734", "10", "50"],
        "gold_reference_summary": "FK 733-modda: fuqarolar o'rtasida 10 BHM dan oshgan qarz yozma tuziladi. FK 734-modda: tadbirkorlik bilan bog'liq bo'lmagan va 50 BHM dan oshmaydigan fuqarolar o'rtasidagi qarz shartnomasi foizsiz deb hisoblanadi.",
    },
    {
        "category": AdversarialCategory.DIRECT_NORM_PRECISION,
        "language": AuditLanguage.UZ_LATN,
        "legal_branch": "civil",
        "difficulty": "hard",
        "question": "Fuqarolik kodeksining 735-moddasiga ko'ra agar qarz tilxatida qaytarish muddati aniq ko'rsatilmagan bo'lsa, qarz oluvchi qarz beruvchi talab qo'ygan kundan boshlab necha kun ichida qarzni qaytarishi shart?",
        "trap_intent": "Tests exact 30-day statutory repayment window upon demand under Civil Code Art. 735.",
        "expected_doc_ids": ["111189"],
        "expected_articles": ["735"],
        "expected_key_facts": ["735", "30 kun"],
        "gold_reference_summary": "Fuqarolik kodeksi 735-moddasiga ko'ra qaytarish muddati shartnomada belgilangan bo'lmasa, qarz oluvchi qarz beruvchi talab qo'ygan kundan boshlab 30 kun ichida qarzni qaytarishi shart.",
    },
    {
        "category": AdversarialCategory.DIRECT_NORM_PRECISION,
        "language": AuditLanguage.UZ_LATN,
        "legal_branch": "procedural",
        "difficulty": "hard",
        "question": "Jinoyat-protsessual kodeksining 226-moddasi va Konstitutsiyaning 27-moddasiga ko'ra shaxsni sudning qarorisiz ushlab turish muddati necha soatdan oshmasligi shart?",
        "trap_intent": "Tests 48-hour constitutional and JPK Art. 226 detention limit (catching outdated 72-hour claims).",
        "expected_doc_ids": ["111460", "6445147"],
        "expected_articles": ["226", "27"],
        "expected_key_facts": ["226", "27", "48 soat"],
        "forbidden_claims": ["72 soat sudsiz ushlab turiladi"],
        "gold_reference_summary": "Konstitutsiya 27-moddasi va JPK 226-moddasiga ko'ra sudning qarorisiz shaxsni 48 soatdan ortiq ushlab turish mumkin emas.",
    },
    {
        "category": AdversarialCategory.DIRECT_NORM_PRECISION,
        "language": AuditLanguage.UZ_LATN,
        "legal_branch": "procedural",
        "difficulty": "hard",
        "question": "Iqtisodiy protsessual kodeksning 259-moddasiga ko'ra birinchi instansiya iqtisodiy sudining hal qiluv qarori ustidan apellyatsiya shikoyati necha kun yoki oy ichida beriladi?",
        "trap_intent": "Tests IPK Art. 259 1-month appeal deadline (catching confusion with 10-day or 20-day deadlines).",
        "expected_doc_ids": ["3523891"],
        "expected_articles": ["259"],
        "expected_key_facts": ["259", "1 oy"],
        "forbidden_claims": ["10 kun ichida apellyatsiya"],
        "gold_reference_summary": "Iqtisodiy protsessual kodeks 259-moddasiga ko'ra apellyatsiya shikoyati hal qiluv qarori qabul qilingan kundan e'tiboran 1 oy ichida beriladi.",
    },
    {
        "category": AdversarialCategory.DIRECT_NORM_PRECISION,
        "language": AuditLanguage.UZ_LATN,
        "legal_branch": "administrative",
        "difficulty": "hard",
        "question": "Ma'muriy sud ishlarini yuritish to'g'risidagi kodeksning 186-moddasiga ko'ra ma'muriy organ yoki mansabdor shaxsning qarori ustidan ma'muriy sudga shikoyat qilish muddati qancha?",
        "trap_intent": "Tests MSIYuTK Art. 186 3-month filing window.",
        "expected_doc_ids": ["3527353"],
        "expected_articles": ["186"],
        "expected_key_facts": ["186", "3 oy"],
        "gold_reference_summary": "MSIYuTK 186-moddasiga ko'ra ma'muriy organ qarori ustidan shikoyat shaxsga o'z huquqlari buzilganligi ma'lum bo'lgan kundan e'tiboran 3 oy ichida ma'muriy sudga beriladi.",
    },
    {
        "category": AdversarialCategory.NORM_CONFLICT_HIERARCHY,
        "language": AuditLanguage.UZ_LATN,
        "legal_branch": "land",
        "difficulty": "extreme",
        "question": "Tuman hokimi fermer xo'jaligining yer uchastkasini 'yerdan samarasiz foydalandi' degan vaj bilan sud qarorisiz o'z qarori orqali olib qo'yishi Yer kodeksining 36-moddasiga muvofiqmi?",
        "trap_intent": "Tests Land Code Art. 36 reform: termination of land rights for violations can ONLY be done by a COURT, not unilaterally by a hokim decision.",
        "expected_doc_ids": ["152653"],
        "expected_articles": ["36"],
        "expected_key_facts": ["36", "sud"],
        "forbidden_claims": ["hokim qarori bilan sudsiz olib qo'yiladi"],
        "gold_reference_summary": "Noqonuniy! Yer kodeksi 36-moddasiga ko'ra yer to'g'risidagi qonunchilik buzilganda yerga bo'lgan huquqni bekor qilish faqat SUD tartibida amalga oshiriladi.",
    },
    {
        "category": AdversarialCategory.DIRECT_NORM_PRECISION,
        "language": AuditLanguage.UZ_LATN,
        "legal_branch": "civil",
        "difficulty": "hard",
        "question": "Uy-joy kodeksining 27–32-moddalariga ko'ra davlat va jamoat ehtiyojlari uchun yer uchastkasi olib qo'yilib fuqaroning uyi buzilganda ('snos') kompensatsiya qachon va qanday miqdorda to'lanishi shart?",
        "trap_intent": "Tests Housing Code Art. 27-32 requirement of PRIOR and FULL market-value compensation before demolition.",
        "expected_doc_ids": ["106136"],
        "expected_articles": ["27"],
        "expected_key_facts": ["27", "oldindan", "to'liq"],
        "forbidden_claims": ["keyinchalik to'lanadi"],
        "gold_reference_summary": "Uy-joy kodeksi 27–32-moddalariga ko'ra uy-joy buzilishidan OLDINDAN va to'liq hajmda bozor qiymatida kompensatsiya hamda barcha zararlar qoplanishi shart.",
    },
    {
        "category": AdversarialCategory.DIRECT_NORM_PRECISION,
        "language": AuditLanguage.UZ_LATN,
        "legal_branch": "corporate",
        "difficulty": "hard",
        "question": "Mas'uliyati cheklangan jamiyatlar to'g'risidagi Qonunning 44-moddasiga ko'ra MCHJ mol-mulki balans qiymatining necha foizidan oshadigan bitim 'yirik bitim' hisoblanadi?",
        "trap_intent": "Tests 25% book value threshold for major transactions (yirik bitim) under LLC Law Art. 44.",
        "expected_doc_ids": ["18793"],
        "expected_articles": ["44"],
        "expected_key_facts": ["44", "25"],
        "gold_reference_summary": "MChJ to'g'risidagi Qonun 44-moddasiga ko'ra jamiyat mol-mulki balans qiymatining 25 foizidan ortiq bo'lgan bitim yirik bitim hisoblanadi va umumiy yig'ilish (yoki kuzatuv kengashi) tomonidan ma'qullanishi shart.",
    },
    {
        "category": AdversarialCategory.DIRECT_NORM_PRECISION,
        "language": AuditLanguage.UZ_LATN,
        "legal_branch": "procedural",
        "difficulty": "hard",
        "question": "Advokatura to'g'risidagi Qonunning 7-moddasiga ko'ra davlat organlari va tashkilotlar advokat so'roviga necha kun ichida yozma javob va hujjatlarni taqdim etishi shart?",
        "trap_intent": "Tests 15-day statutory deadline for responding to an advocate's request under Advocacy Law Art. 7.",
        "expected_doc_ids": ["58372"],
        "expected_articles": ["7"],
        "expected_key_facts": ["7", "15 kun"],
        "forbidden_claims": ["30 kun ichida javob beradi"],
        "gold_reference_summary": "Advokatura to'g'risidagi Qonun 7-moddasiga ko'ra advokat so'roviga so'rov olingan kundan e'tiboran kechi bilan 15 kun ichida javob berilishi shart.",
    },
    {
        "category": AdversarialCategory.DIRECT_NORM_PRECISION,
        "language": AuditLanguage.UZ_LATN,
        "legal_branch": "civil",
        "difficulty": "medium",
        "question": "Iste'molchilarning huquqlarini himoya qilish to'g'risidagi Qonunning 19-moddasiga ko'ra nuqsonli tovarni almashtirish yoki qaytarish muddati kechiktirilgan har bir kun uchun sotuvchi tovar bahosining necha foizi miqdorida penya to'laydi?",
        "trap_intent": "Tests 1% per day statutory penalty under Consumer Protection Law Art. 19.",
        "expected_doc_ids": ["4704"],
        "expected_articles": ["19"],
        "expected_key_facts": ["19", "1 foiz"],
        "gold_reference_summary": "Iste'molchilarning huquqlarini himoya qilish to'g'risidagi Qonun 19-moddasiga ko'ra kechiktirilgan har bir kun uchun tovar bahosining 1 foizi (1%) miqdorida neustoyka (penya) to'lanadi.",
    },
    {
        "category": AdversarialCategory.FABRICATED_CITATION_TRAP,
        "language": AuditLanguage.UZ_LATN,
        "legal_branch": "land",
        "difficulty": "extreme",
        "is_false_premise": True,
        "question": "O'zbekiston Yer kodeksining 145-moddasi va Uy-joy kodeksining 210-moddasiga ko'ra qishloq xo'jaligi yerlarida ko'p qavatli uy qurish tartibi qanday?",
        "trap_intent": "DUAL FAKE CODE BOUNDARY TRAP: Land Code ends at Art. 91 (no Art. 145!) and Housing Code ends at Art. 141 (no Art. 210!).",
        "expected_doc_ids": ["152653", "106136"],
        "expected_articles": [],
        "expected_key_facts": ["mavjud emas"],
        "forbidden_claims": ["145-moddasiga muvofiq", "210-moddasiga ko'ra"],
        "gold_reference_summary": "SOXTA MODDALAR: Yer kodeksi jami 91 ta moddadan (145-modda yo'q), Uy-joy kodeksi esa 141 ta moddadan (210-modda yo'q) iborat.",
    },
    {
        "category": AdversarialCategory.CROSS_LINGUAL_DRIFT_TRAP,
        "language": AuditLanguage.UZ_LATN,
        "legal_branch": "labor",
        "difficulty": "extreme",
        "question": "Меҳнат кодекси 129-modda bo'yicha oddiy rabotnikka ispitadelniy srok 6 oy qo'ysa bo'ladimi yoki фақат rukovoditel va bosh buxgaltergami?",
        "trap_intent": "MIXED-SCRIPT & COLLOQUIAL CODE-SWITCHING TRAP (Cyrillic + Latin + Russian loanwords 'rabotnik', 'ispitadelniy srok', 'rukovoditel'): tests language resilience on Labor Code Art. 129.",
        "expected_doc_ids": ["6257288"],
        "expected_articles": ["129"],
        "expected_key_facts": ["129", "uch oy", "olti oy"],
        "forbidden_claims": ["oddiy xodimga 6 oy"],
        "gold_reference_summary": "Mehnat kodeksi 129-modda: oddiy xodimlar uchun dastlabki sinov muddati 3 oydan oshmasligi shart; 6 oygacha sinov muddati faqat tashkilot rahbarlari, ularning o'rinbosarlari, bosh buxgalterlar va alohida bo'linma rahbarlariga belgilanishi mumkin.",
    },
    {
        "category": AdversarialCategory.TEMPORAL_REPEAL_TRAP,
        "language": AuditLanguage.UZ_LATN,
        "legal_branch": "labor",
        "difficulty": "extreme",
        "question": "Ish beruvchi xodimni shtat qisqarishi sababli Mehnat kodeksining 100-moddasi 2-qismi 1-bandi bilan ishdan bo'shatish haqida buyruq chiqardi. Ushbu buyruqda ko'rsatilgan modda raqami amaldagi Mehnat kodeksiga to'g'ri keladimi?",
        "trap_intent": "FAMOUS OLD ARTICLE NUMBER TRAP: '100-modda 2-qism 1-band' was the iconic dismissal article of the REPEALED 1995 Labor Code! In the new 2023 Labor Code (O'RQ-798), employer-initiated dismissal is Article 161!",
        "expected_doc_ids": ["6257288"],
        "expected_articles": ["161"],
        "expected_key_facts": ["161", "kuchini yo'qot"],
        "forbidden_claims": ["100-moddasi amalda to'g'ri"],
        "gold_reference_summary": "Xato! 100-modda kuchini yo'qotgan 1995-yilgi Mehnat kodeksiga tegishli edi. Amaldagi yangi Mehnat kodeksida (O'RQ-798) mehnat shartnomasini ish beruvchi tashabbusiga ko'ra bekor qilish asoslari 161-moddada belgilangan.",
    },
    {
        "category": AdversarialCategory.TEMPORAL_REPEAL_TRAP,
        "language": AuditLanguage.UZ_LATN,
        "legal_branch": "constitutional",
        "difficulty": "extreme",
        "question": "2023-yilgi yangi tahrirdagi O'zbekiston Konstitutsiyasida shaxsni sud qarorisiz 48 soatdan ortiq ushlab turish mumkin emasligi eski tahrirdagidek 25-moddada joylashganmi yoki modda raqami o'zgarganmi?",
        "trap_intent": "1992 vs 2023 CONSTITUTION ARTICLE NUMBER SHIFT TRAP: In the 1992 Constitution, personal liberty/detention was Art. 25; in the 2023 revised Constitution, Habeas corpus (48 hours) moved to Article 27!",
        "expected_doc_ids": ["6445147"],
        "expected_articles": ["27"],
        "expected_key_facts": ["27", "48 soat"],
        "forbidden_claims": ["25-moddada joylashgan"],
        "gold_reference_summary": "Modda raqami o'zgargan: 1992-yilgi eski tahrirda 25-modda edi, 2023-yilgi yangi tahrirdagi Konstitutsiyada shaxs erkinligi va sud qarorisiz 48 soatdan ortiq ushlab turmaslik (Habeas corpus) 27-moddada mustahkamlangan.",
    },
    # --- DATA.EGOV.UZ / E-GOVERNMENT / OPEN DATA & DIGITAL LAW TRAPS ---
    {
        "category": AdversarialCategory.DIRECT_NORM_PRECISION,
        "language": AuditLanguage.UZ_LATN,
        "legal_branch": "digital_it_data",
        "difficulty": "extreme",
        "question": "O'zbekiston Respublikasi Ochiq ma'lumotlar portali (data.egov.uz) va PF-6247-son Prezident Farmoniga ko'ra davlat organlari ijtimoiy ahamiyatga molik ma'lumotlarni (davlat xaridlari, byudjet xarajatlari) joylashtirish majburiyatini buzsa MJtKning qaysi moddasi bo'yicha javobgarlikka tortiladi va O'RQ-369 19-moddasiga ko'ra axborot so'roviga necha kunda javob berilishi shart?",
        "trap_intent": "Tests data.egov.uz open data compliance (PF-6247 + MJtK Art. 215-7 administrative liability for violating openness rules) AND Law O'RQ-369 Art. 19 (15 days for general information requests, 7 days for media).",
        "expected_doc_ids": ["5459107", "2381133"],
        "expected_articles": ["19", "215-7"],
        "expected_key_facts": ["6247", "15 kun", "7 kun"],
        "forbidden_claims": ["data.egov.uz da joylashtirish ixtiyoriy", "30 kun ichida ko'rib chiqiladi"],
        "gold_reference_summary": "PF-6247-son Farmonga ko'ra davlat organlari ochiq ma'lumotlarni data.egov.uz portalida majburiy joylashtiradi (buzish MJtK 215-7-modda bo'yicha javobgarlikka sabab bo'ladi). O'RQ-369 19-moddasiga ko'ra axborot olish so'rovi ko'pi bilan 15 kunda (OAV so'rovi 7 kunda) ko'rib chiqilishi shart.",
    },
    {
        "category": AdversarialCategory.DIRECT_NORM_PRECISION,
        "language": AuditLanguage.EN,
        "legal_branch": "digital_it_data",
        "difficulty": "hard",
        "question": "Under Uzbekistan's Law on E-Government (O'RQ-395, Articles 18–19) and the Open Data Portal (data.egov.uz), is a state agency permitted to demand paper certificates from an applicant if that data already exists in electronic government registries or another state organ?",
        "trap_intent": "Tests the mandatory 'One-Stop Shop' ('Bir darcha') prohibition under Law O'RQ-395 Art. 18-19.",
        "expected_doc_ids": ["2833860"],
        "expected_articles": ["18", "19"],
        "expected_key_facts": ["395", "18"],
        "forbidden_claims": ["state agency is permitted to demand paper certificates"],
        "gold_reference_summary": "No. Under Articles 18–19 of the Law 'On Electronic Government' (O'RQ-395), state agencies are strictly prohibited from demanding documents or information from applicants that are already available in other state organs or e-government databases.",
    },
    {
        "category": AdversarialCategory.NORM_CONFLICT_HIERARCHY,
        "language": AuditLanguage.UZ_LATN,
        "legal_branch": "digital_it_data",
        "difficulty": "hard",
        "question": "Yangi tahrirdagi 'Elektron tijorat to'g'risida'gi O'RQ-792-son Qonunning 13–15-moddalariga ko'ra elektron shaklda tuzilgan shartnoma (oferta va aksept) qog'ozdagi imzolangan shartnomaga teng yuridik kuchga egami yoki sudda faqat qog'oz shartnoma tan olinadimi?",
        "trap_intent": "Tests legal equivalence of electronic contracts under Law O'RQ-792 Art. 13-15.",
        "expected_doc_ids": ["6213382"],
        "expected_articles": ["13"],
        "expected_key_facts": ["792", "13", "yuridik kuch"],
        "forbidden_claims": ["elektron shartnoma sudda dalil bo'la olmaydi"],
        "gold_reference_summary": "O'RQ-792-son 'Elektron tijorat to'g'risida'gi Qonunning 13–15-moddalariga ko'ra elektron shartnoma qog'ozda tuzilgan va o'z qo'li bilan imzolangan shartnomaga teng yuridik kuchga ega bo'lib, faqat elektron shaklda ekanligi sababli haqiqiy emas deb topilishi mumkin emas.",
    },
] + BLIND_ADVERSARIAL_VAULT


class AdversarialTrapEngine:
    """Generates curated and dynamically LLM-crafted Red-Team legal traps across all 7 categories."""

    def __init__(self, llm: AuditorLLMClient) -> None:
        self.llm = llm

    def list_curated_traps(
        self,
        *,
        categories: list[AdversarialCategory] | None = None,
        languages: list[AuditLanguage] | None = None,
        legal_branch: str | None = None,
    ) -> list[AdversarialTestCase]:
        out: list[AdversarialTestCase] = []
        for idx, raw in enumerate(CURATED_TRAP_BANK, start=1):
            if categories and raw["category"] not in categories:
                continue
            if languages and raw["language"] not in languages:
                continue
            if legal_branch and raw.get("legal_branch") != legal_branch:
                continue
            out.append(
                AdversarialTestCase(
                    case_id=f"trap_{idx:03d}",
                    source="curated_trap_bank",
                    **raw,
                )
            )
        return out

    async def generate_trap(
        self,
        *,
        category: AdversarialCategory | None = None,
        language: AuditLanguage | None = None,
        legal_branch: str | None = None,
        use_llm: bool = True,
    ) -> AdversarialTestCase:
        """Produce a sharp adversarial trap (LLM-crafted when available, falling back to 32-case curated trap bank)."""
        chosen_cat = category or random.choice(list(AdversarialCategory))
        chosen_lang = language or random.choice(list(AuditLanguage))

        if use_llm and self.llm.is_available:
            generated = await self._generate_with_llm(chosen_cat, chosen_lang, legal_branch)
            if generated is not None:
                return generated

        pool = self.list_curated_traps(
            categories=[chosen_cat] if category else None,
            languages=[chosen_lang] if language else None,
            legal_branch=legal_branch,
        )
        if not pool:
            pool = self.list_curated_traps(categories=[chosen_cat] if category else None)
        if not pool:
            pool = self.list_curated_traps()
        picked = random.choice(pool)
        return picked.model_copy(update={"case_id": f"trap_{uuid.uuid4().hex[:8]}"})

    async def build_batch_suite(
        self,
        *,
        count: int = 10,
        categories: list[AdversarialCategory] | None = None,
        languages: list[AuditLanguage] | None = None,
        use_llm_generation: bool = True,
    ) -> list[AdversarialTestCase]:
        """Build a balanced N-case adversarial evaluation suite spanning all selected categories."""
        curated = self.list_curated_traps(categories=categories, languages=languages)
        if not curated:
            curated = self.list_curated_traps()
        random.shuffle(curated)

        suite: list[AdversarialTestCase] = []
        for item in curated[:count]:
            suite.append(item.model_copy(update={"case_id": f"batch_{uuid.uuid4().hex[:8]}"}))

        target_cats = categories or list(AdversarialCategory)
        target_langs = languages or list(AuditLanguage)
        idx = 0
        while len(suite) < count:
            cat = target_cats[idx % len(target_cats)]
            lang = target_langs[idx % len(target_langs)]
            idx += 1
            if use_llm_generation and self.llm.is_available:
                trap = await self.generate_trap(category=cat, language=lang, use_llm=True)
            else:
                base = random.choice(curated)
                trap = base.model_copy(update={"case_id": f"batch_{uuid.uuid4().hex[:8]}"})
            suite.append(trap)
        return suite

    async def _generate_with_llm(
        self,
        category: AdversarialCategory,
        language: AuditLanguage,
        legal_branch: str | None,
    ) -> AdversarialTestCase | None:
        branch_hint = legal_branch or random.choice(
            ["civil", "criminal", "labor", "tax", "administrative", "family", "land", "customs", "corporate", "constitutional", "digital_it_data", "procedural"]
        )
        lang_desc = {
            AuditLanguage.UZ_LATN: "Uzbek (Latin script)",
            AuditLanguage.UZ_CYRL: "Uzbek (Cyrillic script)",
            AuditLanguage.RU: "Russian",
            AuditLanguage.EN: "English",
        }[language]

        system_prompt = (
            "You are a ruthless Red-Team Legal Auditor testing an Uzbekistan legislation AI agent (Lex.uz).\n"
            "Generate ONE ultra-challenging, realistic adversarial legal test case.\n"
            "Return STRICT JSON:\n"
            "{\n"
            '  "question": "adversarial legal question in the requested language",\n'
            '  "legal_branch": "branch slug",\n'
            '  "difficulty": "hard | extreme",\n'
            '  "trap_intent": "exact weakness/trap being tested",\n'
            '  "is_false_premise": false,\n'
            '  "expected_articles": ["article numbers if real"],\n'
            '  "expected_key_facts": ["short key verifiable tokens/numbers"],\n'
            '  "forbidden_claims": ["wrong claims that indicate failure"],\n'
            '  "gold_reference_summary": "concise authoritative ground truth"\n'
            "}"
        )
        user_prompt = (
            f"Category: {category.value}\n"
            f"Language: {lang_desc}\n"
            f"Branch of Uzbekistan law: {branch_hint}\n"
            "Rules:\n"
            "- If FABRICATED_CITATION_TRAP: invent a plausible-sounding NON-EXISTENT article number (>600) or fake decree (e.g. PF-9876 / VMQ-8888) and set is_false_premise=true.\n"
            "- If TEMPORAL_REPEAL_TRAP: probe a repealed act or outdated pre-2023 rule (e.g. 1995 Labor Code, old 15% VAT, old 17-year marriage age).\n"
            "- Otherwise probe real, high-stakes Uzbekistan statutory nuances, exceptions, deadlines, or norm conflicts."
        )
        data = await self.llm.complete_json(system_prompt, user_prompt, fallback=None)
        if not isinstance(data, dict) or not data.get("question"):
            return None

        return AdversarialTestCase(
            case_id=f"gen_{uuid.uuid4().hex[:8]}",
            category=category,
            language=language,
            legal_branch=str(data.get("legal_branch") or branch_hint),
            difficulty=str(data.get("difficulty") or "hard"),
            question=str(data["question"]).strip(),
            trap_intent=str(data.get("trap_intent") or f"Adversarial probe for {category.value}"),
            is_false_premise=bool(data.get("is_false_premise", category == AdversarialCategory.FABRICATED_CITATION_TRAP)),
            expected_articles=[str(x) for x in data.get("expected_articles", []) if x][:6],
            expected_key_facts=[str(x) for x in data.get("expected_key_facts", []) if x][:8],
            forbidden_claims=[str(x) for x in data.get("forbidden_claims", []) if x][:5],
            gold_reference_summary=str(data.get("gold_reference_summary") or ""),
            source="llm_generated",
        )
