"""Colloquial → statutory query expansion for Uzbek (Latin/Cyrillic) and Russian legal questions.

People ask "ishdan haydashdi" ("they kicked me out of work"); the Labour Code says "mehnat shartnomasini ish
beruvchining tashabbusiga koʻra bekor qilish". Lexical retrieval cannot bridge that gap on its own, so every
question is additionally searched with the formal wording of the norms it most likely refers to. The table is
hand-curated from the article titles of the bundled codes and evaluated with ``eval/retrieval_gold.jsonl``.
"""

from __future__ import annotations

import re

from lex_agent.language.transliterator import (
    cyrillic_to_latin,
    detect_language,
    normalize_uzbek_apostrophes,
)
from lex_agent.models import Language

# Concept table: Uzbek-Latin trigger, Russian trigger, formal Uzbek wording, formal Russian wording.
# Russian questions are expanded in BOTH languages because the Uzbek corpus is the complete, authoritative one.
_CONCEPTS: list[tuple[str | None, str | None, str, str]] = [
    (r"ishdan (?:hayda|bo'shat|chiqar|olib tashla|ketkaz)|haydab yubor|haydash|ishdan bo'shatdi|sokrashen",
     r"увол(?:ьн|ил|ят|ен|ня)|сокращени",
     "mehnat shartnomasini ish beruvchining tashabbusiga ko'ra bekor qilish",
     "прекращение трудового договора по инициативе работодателя"),
    (r"o'z xohish|ariza yozib ket|ishdan ket(?!kaz)|bo'shamoqchi|bo'shab ket",
     r"по собственному желани|сам(?:а)? уйти|уволиться",
     "mehnat shartnomasini xodimning tashabbusiga ko'ra bekor qilish ogohlantirish",
     "прекращение трудового договора по инициативе работника предупреждение"),
    (r"ta'til|tatil|otpusk|dam olish kun",
     r"отпуск",
     "har yilgi asosiy eng kam mehnat ta'tilining davomiyligi kalendar kun",
     "понятие и виды ежегодного трудового отпуска"),
    (r"oylik|maosh|zarplata|ish haqi(?!.*eng kam)|ish haqini",
     r"зарплат|заработн",
     "ish haqini to'lash muddatlari",
     "сроки выплаты заработной платы"),
    (r"sinov muddat|sinov davri|ispitatel",
     r"испытательн",
     "ishga qabul qilish chog'idagi dastlabki sinov muddati",
     "срок предварительного испытания при приеме на работу"),
    (r"ish vaqti|necha soat ishla|soat ishlash|smena",
     r"рабоч(?:ее|его) врем|сколько часов",
     "ish vaqtining normal davomiyligi haftasiga soat",
     "нормальная продолжительность рабочего времени"),
    (r"mehnat shartnoma|trudovoy dogovor",
     r"трудов\w* договор\w* (?:форм|письмен)|форм\w* трудов",
     "mehnat shartnomasining shakli yozma",
     "форма трудового договора"),
    (r"ajrash|taloq|razvod|ajralish|ajralmoqchi|nikohdan chiq",
     r"развод|расторжени\w* брак",
     "nikohdan ajratish tartibi fuqarolik holati dalolatnomalarini qayd etish organlarida",
     "расторжение брака в органах записи актов гражданского состояния"),
    (r"aliment",
     r"алимент",
     "ota-onaning voyaga yetmagan bolalariga to'laydigan aliment miqdori",
     "размер алиментов взыскиваемых на несовершеннолетних детей"),
    (r"nikoh yosh|turmushga chiq|uylanish yosh|necha yoshda uylan",
     r"брачн\w* возраст|во сколько лет\w* (?:жениться|выйти замуж)",
     "nikoh yoshi",
     "брачный возраст"),
    (r"qarz|tilxat|raspiska|dolg|qarzdor",
     r"займ|заём|долг|расписк",
     "qarz shartnomasining shakli oddiy yozma shakl bazaviy hisoblash miqdorining o'n baravari",
     "форма договора займа простая письменная форма"),
    (r"(?:qaytarma|to'lama|bermay).*(?:sud|necha yil|muddat)|(?:sud|da'vo).*(?:necha yil|muddati)|da'vo muddat",
     r"исков\w* давност|срок\w* (?:для|подачи) (?:суд|иск)",
     "umumiy da'vo muddati uch yil da'vo muddatining o'ta boshlashi",
     "общий срок исковой давности"),
    (r"buzuq|sifatsiz|nosoz|brak|ishlamay(?:di|apti)|qaytarib ol|almashtir|do'konga qaytar",
     r"некачественн|бракован|вернуть товар|обмен\w* товар",
     "sotib oluvchiga sifati tegishli darajada bo'lmagan tovar sotilganida uning huquqlari tovarni almashtirish",
     "права покупателя в случае продажи товара ненадлежащего качества"),
    (r"meros|merosxo'r",
     r"наследств|наследник",
     "merosning ochilishi meros tarkibi",
     "открытие наследства состав наследства"),
    (r"vasiyat",
     r"завещани",
     "vasiyatnomaning shakliga doir umumiy qoidalar notarial tasdiqlangan vasiyatnoma",
     "форма завещания нотариально удостоверенное завещание"),
    (r"firib|aldab|aldash|aldov|moshennik",
     r"мошенн",
     "firibgarlik",
     "мошенничество"),
    (r"o'g'ri|o'g'irla|krazha|o'g'irlik",
     r"краж|украл|воровств",
     "o'g'rilik",
     "кража"),
    (r"mast|ichib|alkogol|spirtli|pyaniy",
     r"пьян|нетрезв|алкогол|опьянени",
     "transport vositalarini mastlik holatida boshqarish",
     "управление транспортными средствами в состоянии опьянения"),
    (r"bezori|so'kin|haqorat|janjal",
     r"хулиган",
     "mayda bezorilik",
     "мелкое хулиганство"),
    (r"neustoyka|penya|kechiktir|kechikkan",
     r"неустойк|пен[яию]",
     "neustoyka tushunchasi qonuniy neustoyka",
     "понятие неустойки законная неустойка"),
    (r"davlat boji|poshlina|bojini",
     r"госпошлин|государственн\w* пошлин",
     "davlat boji to'lash asoslari va tartibi",
     "государственная пошлина основания и порядок уплаты"),
    (r"\bbhm\b|bazaviy hisoblash|\bbrv\b",
     r"\bбрв\b|базов\w* расч[её]тн",
     "bazaviy hisoblash miqdori BHM so'm",
     "базовая расчётная величина БРВ сумов"),
    (r"eng kam ish haqi|minimal(?:naya)? (?:zarplata|ish haqi)|\bmhtekm\b|\bmrot\b|eng kam oylik",
     r"\bмрот\b|минимальн\w* (?:зарплат|оплат|размер)",
     "mehnatga haq to'lashning eng kam miqdori MHTEKM",
     "минимальный размер оплаты труда МРОТ"),
    (r"shaxsiy hayot|daxlsiz|yozishmalar siri|telefon sir",
     r"неприкосновенност\w* частн|тайн\w* переписк",
     "shaxsiy hayotining daxlsizligi shaxsiy va oilaviy sir",
     "неприкосновенность частной жизни личная и семейная тайна"),
    (r"shaxsga doir|shaxsiy ma'lumot|ma'lumotlarim|personal",
     r"персональн\w* данн",
     "shaxsga doir ma'lumotlarga ishlov berishga rozilik berish",
     "согласие на обработку персональных данных"),
    (r"soliq.*(?:to'lama|qoch|yashir)|soliqdan qoch",
     r"налог\w* (?:не плат|уклон)|уклонени\w* от уплат",
     "soliqlar yoki yig'imlarni to'lashdan bo'yin tovlash",
     "уклонение от уплаты налогов или сборов"),
    (r"ko'chir|uydan chiqar|kvartiradan chiqar|vyselen|uyidan haydab",
     r"выселени|выселить",
     "turar joydan ko'chirish",
     "выселение из жилого помещения"),
    (r"ijara|arenda|kvartirant|ijarachi",
     r"аренд|на[её]м жил|съ[её]мн",
     "mulk ijarasi shartnomasi ijaraga beruvchi ijaraga oluvchi",
     "договор аренды имущества"),
    (r"guvohnomasiz|haydovchilik guvohnoma|pravasiz|prava",
     r"без (?:водительск|прав)",
     "transport vositasini boshqarish huquqiga ega bo'lmagan shaxs",
     "лицо, не имеющее права управления транспортным средством"),
]

_COMPILED: list[tuple[re.Pattern[str] | None, re.Pattern[str] | None, str, str]] = [
    (re.compile(uz, re.I) if uz else None, re.compile(ru, re.I) if ru else None, uz_exp, ru_exp)
    for uz, ru, uz_exp, ru_exp in _CONCEPTS
]


def _uz_latin_view(query: str) -> str:
    text = normalize_uzbek_apostrophes(query)
    if re.search(r"[\u0400-\u04ff]", text):
        text = cyrillic_to_latin(text)
    return normalize_uzbek_apostrophes(text).lower()


def expand_query(query: str, *, max_expansions: int = 2) -> list[str]:
    """Return up to ``max_expansions`` formal statutory phrasings for a colloquial legal question."""
    if not query or not query.strip():
        return []
    lang = detect_language(query)
    out: list[str] = []
    if lang == Language.RU:
        low = query.lower()
        for _uz_rx, ru_rx, uz_exp, ru_exp in _COMPILED:
            if ru_rx is not None and ru_rx.search(low):
                for exp in (ru_exp, uz_exp):
                    if exp not in out:
                        out.append(exp)
    else:
        view = _uz_latin_view(query)
        for uz_rx, _ru_rx, uz_exp, _ru_exp in _COMPILED:
            if uz_rx is not None and uz_rx.search(view) and uz_exp not in out:
                out.append(uz_exp)
        if lang == Language.EN:
            out = out[:1]
    return out[:max_expansions]
