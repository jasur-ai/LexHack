"""Localized fixed replies: greetings, capabilities, off-topic redirects, emergency help, refusals, honest
"not found" answers and clarifying questions. Every reply is a ready ``sections`` dict (answer, key points,
steps, caution, follow-ups) so the API shape never changes."""

from __future__ import annotations

from typing import Any

from lex_agent.models import Language


def lang_key(lang: Language | str) -> str:
    v = lang.value if isinstance(lang, Language) else str(lang)
    if v == "ru":
        return "ru"
    if v == "en":
        return "en"
    if v == "uz_cyrl":
        return "uz_cyrl"
    return "uz"


EXAMPLES = {
    "uz": ["Ishdan boʻshatishdi, nima qilishim kerak?", "Bitta bola uchun aliment qancha?", "Ajrashish uchun davlat boji qancha?"],
    "uz_cyrl": ["Ишдан бўшатишди, нима қилишим керак?", "Битта бола учун алимент қанча?", "Ажрашиш учун давлат божи қанча?"],
    "ru": ["Меня уволили, что делать?", "Какой размер алиментов на одного ребёнка?", "Сколько стоит госпошлина за развод?"],
    "en": ["I was fired — what can I do?", "How much is child support for one child?", "What is the court fee for a divorce?"],
}

_TEXT: dict[str, dict[str, Any]] = {
    "greeting": {
        "uz": "Assalomu alaykum! Men Haqli — Oʻzbekiston qonunchiligi boʻyicha AI yordamchiman. Vaziyatingizni oddiy "
              "soʻzlar bilan yozing: qonundagi tegishli moddani topib, qisqa va aniq tushuntiraman.",
        "uz_cyrl": "Ассалому алайкум! Мен Ҳақли — Ўзбекистон қонунчилиги бўйича AI ёрдамчиман. Вазиятингизни оддий "
                   "сўзлар билан ёзинг: қонундаги тегишли моддани топиб, қисқа ва аниқ тушунтираман.",
        "ru": "Здравствуйте! Я Haqli — AI-помощник по законодательству Узбекистана. Опишите ситуацию своими словами: "
              "я найду нужную статью закона и коротко объясню.",
        "en": "Hello! I'm Haqli, an AI assistant for the laws of Uzbekistan. Describe your situation in plain words and "
              "I'll find the relevant article and explain it briefly.",
    },
    "thanks": {
        "uz": "Arzimaydi! Yana savolingiz boʻlsa, yozing.",
        "uz_cyrl": "Арзимайди! Яна саволингиз бўлса, ёзинг.",
        "ru": "Пожалуйста! Если появятся вопросы — пишите.",
        "en": "You're welcome! Ask any time.",
    },
    "farewell": {
        "uz": "Xayr! Huquqlaringizni himoya qilishda omad tilayman.",
        "uz_cyrl": "Хайр! Ҳуқуқларингизни ҳимоя қилишда омад тилайман.",
        "ru": "До свидания! Удачи в защите ваших прав.",
        "en": "Goodbye, and good luck protecting your rights.",
    },
    "about": {
        "uz": "Men Haqli — AI yordamchiman, advokat emasman. Javoblarim lex.uz dagi amaldagi kodeks va qonunlar matniga "
              "tayanadi va har birida manba (modda) koʻrsatiladi. Ichki koʻrsatmalarimni oshkor qilmayman.",
        "uz_cyrl": "Мен Ҳақли — AI ёрдамчиман, адвокат эмасман. Жавобларим lex.uz даги амалдаги кодекс ва қонунлар "
                   "матнига таянади ва ҳар бирида манба (модда) кўрсатилади. Ички кўрсатмаларимни ошкор қилмайман.",
        "ru": "Я Haqli — AI-помощник, а не адвокат. Ответы основаны на текстах действующих кодексов и законов с lex.uz, "
              "у каждого указан источник (статья). Свои внутренние инструкции я не раскрываю.",
        "en": "I'm Haqli, an AI assistant — not a lawyer. Answers are based on the in-force codes and laws published on "
              "lex.uz, each with its source article. I don't disclose my internal instructions.",
    },
    "about_points": {
        "uz": ["Huquqiy savollarga qisqa javob va aniq modda", "Aliment, jarima, davlat boji, kompensatsiya, muddatlarni hisoblash",
               "Ariza va daʼvo arizasi namunalari", "Oʻzbek (lotin/kirill), rus va ingliz tillarida"],
        "uz_cyrl": ["Ҳуқуқий саволларга қисқа жавоб ва аниқ модда", "Алимент, жарима, давлат божи, компенсация, муддатларни ҳисоблаш",
                    "Ариза ва даъво аризаси намуналари", "Ўзбек (лотин/кирилл), рус ва инглиз тилларида"],
        "ru": ["Короткие ответы со ссылкой на статью", "Расчёт алиментов, штрафов, госпошлины, компенсаций, сроков",
               "Образцы заявлений и исков", "На узбекском (латиница/кириллица), русском и английском"],
        "en": ["Short answers citing the exact article", "Calculators: child support, fines, state duty, compensation, deadlines",
               "Sample applications and claims", "Uzbek (Latin/Cyrillic), Russian and English"],
    },
    "off_topic": {
        "uz": "Men faqat Oʻzbekiston qonunchiligi boʻyicha savollarga javob beraman. Huquqiy vaziyatingizni yozing — "
              "masalan, ish, oila, uy-joy, jarima yoki soliq haqida.",
        "uz_cyrl": "Мен фақат Ўзбекистон қонунчилиги бўйича саволларга жавоб бераман. Ҳуқуқий вазиятингизни ёзинг — "
                   "масалан, иш, оила, уй-жой, жарима ёки солиқ ҳақида.",
        "ru": "Я отвечаю только на вопросы о законодательстве Узбекистана. Опишите правовую ситуацию — например, о "
              "работе, семье, жилье, штрафах или налогах.",
        "en": "I only answer questions about the laws of Uzbekistan. Describe your legal situation — for example about "
              "work, family, housing, fines or taxes.",
    },
    "emergency": {
        "uz": "Agar hozir xavf ostida boʻlsangiz, darhol qoʻngʻiroq qiling: 112 (yagona favqulodda xizmat), 102 "
              "(militsiya), 103 (tez yordam). Zoʻravonlik yoki tazyiq boʻyicha bepul ishonch telefoni — 1146.",
        "uz_cyrl": "Агар ҳозир хавф остида бўлсангиз, дарҳол қўнғироқ қилинг: 112 (ягона фавқулодда хизмат), 102 "
                   "(милиция), 103 (тез ёрдам). Зўравонлик ёки тазйиқ бўйича бепул ишонч телефони — 1146.",
        "ru": "Если вы сейчас в опасности, звоните немедленно: 112 (единая экстренная служба), 102 (полиция), 103 "
              "(скорая). Бесплатный телефон доверия по насилию и давлению — 1146.",
        "en": "If you are in danger right now, call 112 (single emergency number), 102 (police) or 103 (ambulance). "
              "Free helpline for violence and abuse: 1146.",
    },
    "illegal": {
        "uz": "Qonunni chetlab oʻtish yoki javobgarlikdan qochishga yordam bera olmayman. Quyida qonun bu haqda nima "
              "deyishi va qanday qonuniy yoʻllar borligi:",
        "uz_cyrl": "Қонунни четлаб ўтиш ёки жавобгарликдан қочишга ёрдам бера олмайман. Қуйида қонун бу ҳақда нима "
                   "дейиши ва қандай қонуний йўллар борлиги:",
        "ru": "Помочь обойти закон или уйти от ответственности я не могу. Ниже — что говорит закон и какие есть "
              "законные варианты:",
        "en": "I can't help with breaking the law or evading liability. Here is what the law says and what lawful "
              "options exist:",
    },
    "not_found": {
        "uz": "Bazadagi qonunlardan bu savolga aniq javob beradigan modda topilmadi.",
        "uz_cyrl": "Базадаги қонунлардан бу саволга аниқ жавоб берадиган модда топилмади.",
        "ru": "В базе законов не нашлось статьи, которая точно отвечает на этот вопрос.",
        "en": "I couldn't find an article in the law database that answers this precisely.",
    },
    "not_found_steps": {
        "uz": ["Vaziyatni batafsilroq yozing: kim, qachon, qanday hujjat yoki summa", "lex.uz saytida qidirib koʻring",
               "Bepul yuridik yordam: davlat hisobidan yuridik yordam olish huquqingiz boʻlishi mumkin"],
        "uz_cyrl": ["Вазиятни батафсилроқ ёзинг: ким, қачон, қандай ҳужжат ёки сумма", "lex.uz сайтида қидириб кўринг",
                    "Бепул юридик ёрдам: давлат ҳисобидан юридик ёрдам олиш ҳуқуқингиз бўлиши мумкин"],
        "ru": ["Опишите подробнее: кто, когда, какой документ или сумма", "Попробуйте поиск на lex.uz",
               "Бесплатная юрпомощь: возможно, вы вправе получить её за счёт государства"],
        "en": ["Describe it in more detail: who, when, which document or amount", "Try the search on lex.uz",
               "Free legal aid: you may qualify for state-funded legal assistance"],
    },
    "clarify": {
        "uz": "Aniq javob berishim uchun biroz batafsilroq yozing:",
        "uz_cyrl": "Аниқ жавоб беришим учун бироз батафсилроқ ёзинг:",
        "ru": "Чтобы ответить точно, уточните, пожалуйста:",
        "en": "To answer precisely, please tell me:",
    },
    "calc_ask": {
        "uz": "Aniq hisoblash uchun quyidagilarni yozing: {fields}.",
        "uz_cyrl": "Аниқ ҳисоблаш учун қуйидагиларни ёзинг: {fields}.",
        "ru": "Для точного расчёта напишите: {fields}.",
        "en": "For an exact calculation, please give: {fields}.",
    },
    "ai_caution": {
        "uz": "Bu AI tomonidan qonun matnidan tayyorlangan maʼlumot, yuridik maslahat emas. Muhim qarordan oldin moddani "
              "toʻliq oʻqing yoki advokat bilan maslahatlashing.",
        "uz_cyrl": "Бу AI томонидан қонун матнидан тайёрланган маълумот, юридик маслаҳат эмас. Муҳим қарордан олдин "
                   "моддани тўлиқ ўқинг ёки адвокат билан маслаҳатлашинг.",
        "ru": "Это справка, подготовленная AI по тексту закона, а не юридическая консультация. Перед важным решением "
              "прочитайте статью полностью или посоветуйтесь с юристом.",
        "en": "This is AI-prepared information from the legal text, not legal advice. Read the full article or consult "
              "a lawyer before an important decision.",
    },
}


def text(key: str, lang: Language | str) -> Any:
    entry = _TEXT[key]
    return entry.get(lang_key(lang)) or entry["uz"]


def simple_reply(kind: str, lang: Language | str) -> dict[str, Any]:
    """Sections for greeting / thanks / farewell / about / off-topic turns."""
    lk = lang_key(lang)
    sections: dict[str, Any] = {"answer": text(kind, lang), "key_points": [], "steps": [], "caution": "", "follow_ups": []}
    if kind == "about":
        sections["key_points"] = list(text("about_points", lang))
    if kind in ("greeting", "about", "off_topic", "thanks"):
        sections["follow_ups"] = list(EXAMPLES.get(lk, EXAMPLES["uz"]))
    return sections
