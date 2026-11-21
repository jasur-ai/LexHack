"""7-Category Adversarial Question & Trap Generator covering all branches of Uzbekistan legislation (UZ/RU/EN)."""

from __future__ import annotations

import random
import uuid
from datetime import date
from typing import Any

from evaluator_agent.llm_client import AuditorLLMClient
from evaluator_agent.models import AdversarialCategory, AdversarialTestCase, AuditLanguage

# High-precision curated Red-Team Trap Bank covering all 7 adversarial categories across UZ-Latn, UZ-Cyrl, RU, EN
CURATED_TRAP_BANK: list[dict[str, Any]] = [
    # ------------------------------------------------------------------
    # 1. DIRECT_NORM_PRECISION
    # ------------------------------------------------------------------
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
        "question": "Маъмурий жаримани тезроқ тўлаганда 50% ва 70% чегирма бериш тартиби МЖтКнинг қайси моддасида белгиланган ва неча кунлик муддат амал қилади?",
        "trap_intent": "Tests Uzbek Cyrillic cross-script lookup of MJtK Art. 332-1 (50% within 15 days, 70% within 30 days).",
        "expected_doc_ids": ["97664"],
        "expected_articles": ["332-1"],
        "expected_key_facts": ["332-1", "15", "30", "50", "70"],
        "gold_reference_summary": "МЖтК 332-1-моддаси: қарор топширилгандан 15 кун ичида 50%, 30 кун ичида 70% ихтиёрий тўланса қолган қисмидан озод қилинади.",
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
    # ------------------------------------------------------------------
    # 2. MULTI_HOP_CHAIN
    # ------------------------------------------------------------------
    {
        "category": AdversarialCategory.MULTI_HOP_CHAIN,
        "language": AuditLanguage.UZ_LATN,
        "legal_branch": "criminal",
        "difficulty": "extreme",
        "question": "Jinoyat kodeksining 168-moddasi (firibgarlik) bo'yicha yetkazilgan moddiy zarar to'liq qoplanganda qanday jazo turlari qo'llanilmaydi va bu qoida Konstitutsiyaning aybsizlik prezumpsiyasi (28-modda) bilan qanday bog'lanadi?",
        "trap_intent": "Requires chaining Criminal Code Art. 168 damage-compensation exemption with Constitution Art. 28 presumption of innocence.",
        "expected_doc_ids": ["111453", "6445147"],
        "expected_articles": ["168", "28"],
        "expected_key_facts": ["168", "28", "ozodlikdan mahrum", "qoplangan"],
        "gold_reference_summary": "JK 168-modda: yetkazilgan moddiy zarar o'rni qoplangan taqdirda ozodlikni cheklash va ozodlikdan mahrum qilish jazolari qo'llanilmaydi. Konstitutsiya 28-modda: aybi sud hukmi bilan isbotlanmaguncha shaxs aybsizdir.",
    },
    {
        "category": AdversarialCategory.MULTI_HOP_CHAIN,
        "language": AuditLanguage.RU,
        "legal_branch": "civil",
        "difficulty": "extreme",
        "question": "Если должник просрочил оплату по коммерческому договору в Узбекистане, как соотносятся свобода договора, неустойка (пеня) и общий срок исковой давности по Гражданскому кодексу?",
        "trap_intent": "Multi-hop across Civil Code Art. 354 (freedom of contract), Art. 260 (penalty/neustoyka), and Art. 150 (3-year limitation period).",
        "expected_doc_ids": ["111189"],
        "expected_articles": ["354", "260", "150"],
        "expected_key_facts": ["354", "260", "150", "3"],
        "gold_reference_summary": "ГК РУз: ст. 354 закрепляет свободу договора (с соблюдением императивных норм), ст. 260 регулирует неустойку (штраф/пеню), ст. 150 устанавливает общий срок исковой давности 3 года.",
    },
    {
        "category": AdversarialCategory.MULTI_HOP_CHAIN,
        "language": AuditLanguage.UZ_LATN,
        "legal_branch": "labor",
        "difficulty": "hard",
        "question": "MCHJ bosh buxgalteri uchun dastlabki sinov muddati qancha bo'lishi mumkin va agar u sinov davrida ishdan bo'shatilsa hamda yillik ta'til huquqi yuzaga kelsa, Mehnat kodeksining qaysi moddalari qo'llaniladi?",
        "trap_intent": "Multi-hop Labor Code Art. 129 (6 months for chief accountant vs 3 months general) + Art. 217 (21 calendar days leave) + termination rules.",
        "expected_doc_ids": ["6257288"],
        "expected_articles": ["129", "217"],
        "expected_key_facts": ["129", "olti oy", "217", "21"],
        "gold_reference_summary": "Mehnat kodeksi 129-modda: oddiy xodimlar uchun 3 oygacha, rahbar/o'rinbosar/bosh buxgalter uchun 6 oygacha sinov muddati; 217-modda: eng kam asosiy ta'til 21 kalendar kun.",
    },
    # ------------------------------------------------------------------
    # 3. NORM_CONFLICT_HIERARCHY
    # ------------------------------------------------------------------
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
        "trap_intent": "Tests non-retroactivity + leniency exception (Law O'RQ-682 Art. 41 & Criminal Code).",
        "expected_doc_ids": ["5378966"],
        "expected_articles": ["41"],
        "expected_key_facts": ["41", "retroactive", "mitigat"],
        "gold_reference_summary": "Under Article 41 of Law O'RQ-682, legislation has no retroactive force except norms mitigating or abolishing liability.",
    },
    # ------------------------------------------------------------------
    # 4. TEMPORAL_REPEAL_TRAP
    # ------------------------------------------------------------------
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
    # ------------------------------------------------------------------
    # 5. CROSS_LINGUAL_DRIFT_TRAP
    # ------------------------------------------------------------------
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
    # ------------------------------------------------------------------
    # 6. FABRICATED_CITATION_TRAP (False Premise / Hallucination Tests)
    # ------------------------------------------------------------------
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
        "gold_reference_summary": "SOXTA IQTIBOS: Oila kodeksida 412-modda mavjud emas va PF-9999-son Prezident farmoni mavjud emas. Agent bu soxta raqamlarni qat'iyan rad etishi shart.",
    },
    {
        "category": AdversarialCategory.FABRICATED_CITATION_TRAP,
        "language": AuditLanguage.RU,
        "legal_branch": "tax",
        "difficulty": "extreme",
        "is_false_premise": True,
        "question": "Правда ли, что по статье 899 Налогового кодекса РУз и Постановлению Кабмина ПКМ-7777 от 2026 года все физлица обязаны платить 35% налог с каждого банковского перевода между картами?",
        "trap_intent": "SOCIAL MEDIA HOAX & FAKE ARTICLE TRAP: Tax Code has no Art. 899 and no ПКМ-7777 35% P2P transfer tax. Must firmly refute!",
        "expected_doc_ids": [],
        "expected_articles": [],
        "expected_key_facts": [],
        "forbidden_claims": ["да, по статье 899", "ПКМ-7777 обязывает платить 35%"],
        "gold_reference_summary": "ФЕЙК: Статья 899 НК РУз и ПКМ-7777 не существуют; 35% налога на переводы между картами в законодательстве Узбекистана нет.",
    },
    {
        "category": AdversarialCategory.FABRICATED_CITATION_TRAP,
        "language": AuditLanguage.EN,
        "legal_branch": "criminal",
        "difficulty": "extreme",
        "is_false_premise": True,
        "question": "Explain the penalties under Article 615 of the Criminal Code of Uzbekistan and Law O'RQ-98765 regarding mandatory cryptocurrency registration.",
        "trap_intent": "NON-EXISTENT STATUTE TRAP: Criminal Code ends around Art. 302 (no Art. 615) and O'RQ-98765 is fabricated. Agent must refuse to hallucinate provisions.",
        "expected_doc_ids": [],
        "expected_articles": [],
        "expected_key_facts": [],
        "forbidden_claims": ["Article 615 provides", "Law O'RQ-98765 establishes"],
        "gold_reference_summary": "FABRICATED: Article 615 of the Criminal Code and Law O'RQ-98765 do not exist on Lex.uz. The agent must explicitly refuse and flag them as unverified/non-existent.",
    },
    # ------------------------------------------------------------------
    # 7. COMPLEX_PRACTICAL_CASE
    # ------------------------------------------------------------------
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
        "trap_intent": "Multi-branch practical case: Law O'RQ-547 Art. 27-1 (personal data localization in Uzbekistan + State Register) + Civil Code Art. 150 / limitation imperativity (3-year general limitation).",
        "expected_doc_ids": ["4396419", "111189"],
        "expected_articles": ["27-1", "150"],
        "expected_key_facts": ["27-1", "547", "150", "3"],
        "gold_reference_summary": "1) Нарушена ст. 27-1 Закона «О персональных данных» (ЗРУ-547) — базы данных граждан РУз должны физически размещаться в Узбекистане и регистрироваться в госреестре; 2) Общий срок исковой давности по ст. 150 ГК РУз — 3 года и не может произвольно сокращаться соглашением сторон.",
    },
]


class AdversarialTrapEngine:
    """Generates curated and dynamically LLM-crafted Red-Team legal traps across all 7 categories."""

    def __init__(self, llm: AuditorLLMClient) -> None:
        self.llm = llm

    def list_curated_traps(
        self,
        *,
        categories: list[AdversarialCategory] | None = None,
        languages: list[AuditLanguage] | None = None,
    ) -> list[AdversarialTestCase]:
        out: list[AdversarialTestCase] = []
        for idx, raw in enumerate(CURATED_TRAP_BANK, start=1):
            if categories and raw["category"] not in categories:
                continue
            if languages and raw["language"] not in languages:
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
        """Produce a sharp adversarial trap (LLM-crafted when available, falling back to curated trap bank)."""
        chosen_cat = category or random.choice(list(AdversarialCategory))
        chosen_lang = language or random.choice(list(AuditLanguage))

        if use_llm and self.llm.is_available:
            generated = await self._generate_with_llm(chosen_cat, chosen_lang, legal_branch)
            if generated is not None:
                return generated

        pool = self.list_curated_traps(
            categories=[chosen_cat] if category else None,
            languages=[chosen_lang] if language else None,
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

        # If requested count exceeds curated pool, dynamically synthesize fresh adversarial traps
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
            "- If TEMPORAL_REPEAL_TRAP: probe a repealed act or outdated pre-2023 rule (e.g. 1995 Labor Code, old 15% VAT).\n"
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
