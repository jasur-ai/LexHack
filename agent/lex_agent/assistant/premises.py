"""Check what a question takes for granted before answering it.

People, and adversarial testers, cite articles that do not exist ("Oila kodeksining 412-moddasi"), codes that were
never adopted ("Kriptovalyuta kodeksi"), invented act numbers ("PF-9999") and rules that changed long ago
("1995-yilgi Mehnat kodeksining 134-moddasi", "QQS hali ham 15%mi?"). Answering such a question as asked would
confirm the false premise, so the answer has to correct it first. This module finds those premises:

* missing articles: the cited article is not in the current text of the named act. Past the act's last article
  this is certain; inside the range the article was most likely repealed;
* unknown codes: a "… kodeksi / кодекс / Code" that is not one of the codes in force;
* unknown act numbers: law numbers missing from the catalog, and decree, resolution or law numbers outside any
  range ever used (certain);
* repealed editions and outdated rules: the 1995 Labour Code, the 1992 Constitution, the 2007 Tax Code, old article
  numbers people still quote, and figures that changed. Each rule names the current article it is checked against,
  and those articles are verified against the index by ``tests/test_premises.py``.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

from lex_agent.language.textproc import fold_for_match
from lex_agent.retrieval.act_resolver import _ARTICLE_RE, _SUP, ActResolver, range_articles

CIVIL_PARTS = ("111189", "180552")

# --------------------------------------------------------------------------------------------- data classes


@dataclass(frozen=True, slots=True)
class PremiseIssue:
    kind: str  # missing_article | unknown_code | unknown_number
    certain: bool
    act_id: str | None = None
    article: str | None = None
    name: str | None = None  # the code name or act number as written
    max_article: int | None = None
    series: str | None = None  # law | decree | resolution | cabinet (act numbers)


@dataclass(frozen=True, slots=True)
class TemporalRule:
    """A rule that changed: how people still quote it, and where the current rule is."""

    id: str
    triggers: tuple[str, ...]  # regexes on the folded question; all groups in one tuple entry must match (" && ")
    text: Mapping[str, str]  # uz_latn / uz_cyrl / ru / en
    refs: tuple[tuple[str, str], ...] = ()  # current (act, article) to cite


@dataclass(slots=True)
class PremiseReport:
    issues: list[PremiseIssue] = field(default_factory=list)
    temporal: list[TemporalRule] = field(default_factory=list)
    yes_no: bool = False

    @property
    def certain_false(self) -> bool:
        return any(i.certain for i in self.issues)

    def __bool__(self) -> bool:
        return bool(self.issues or self.temporal)

    @property
    def refs(self) -> list[tuple[str, str]]:
        out: list[tuple[str, str]] = []
        for rule in self.temporal:
            for ref in rule.refs:
                if ref not in out:
                    out.append(ref)
        return out


# --------------------------------------------------------------------------------------------- vocabularies

# Words that may stand before "kodeks" without naming a code
_GENERIC_UZ = {
    "yangi", "amaldagi", "ushbu", "mazkur", "tegishli", "respublikasining", "respublikasi", "ozbekiston", "uzbekiston",
    "bu", "shu", "qaysi", "eski", "togrisidagi", "haqidagi", "yilgi", "tahrirdagi", "va", "yoki", "hamda", "ham",
    "boyicha", "asosan", "kora", "binoan", "muvofiq", "barcha", "boshqa", "har", "bir", "qanday", "hozirgi",
}
_KNOWN_UZ = (
    "mehnat", "oila", "fuqarolik", "jinoyat", "soliq", "uy-joy", "uyjoy", "joy", "yer", "bojxona", "budjet", "byudjet",
    "saylov", "shaharsozlik", "havo", "suv", "protsessual", "ijroiya", "javobgarlik", "yuritish", "mamuriy",
)
_GENERIC_RU = {"новый", "нового", "новом", "новым", "действующий", "действующего", "действующем", "этот", "этого", "данный",
               "данного", "настоящий", "настоящего", "республики", "узбекистан", "узбекистана", "и", "или", "по", "ст", "статье",
               "статьи", "статья", "статьей", "согласно", "старый", "старого", "старом", "какой", "какого"}
_KNOWN_RU = ("трудов", "семейн", "гражданск", "уголовн", "налогов", "жилищн", "земельн", "таможенн", "бюджетн", "избирательн",
             "градостроительн", "воздушн", "водн", "процессуальн", "исполнительн")
_GENERIC_EN = {"the", "uzbekistan's", "uzbekistans", "uzbek", "new", "current", "this", "of", "and", "or", "under", "old",
               "s", "republic", "national", "what", "is", "a", "an", "which", "by", "to", "in", "per", "according"}
# "zip code", "promo code"… are not legal codes
_NON_LEGAL_EN = {"zip", "postal", "post", "promo", "promotional", "discount", "qr", "bar", "source", "error", "dress",
                 "country", "area", "phone", "dialling", "dialing", "access", "verification", "activation", "morse", "sms",
                 "pin", "security", "tax-free", "colour", "color", "machine", "program", "programming", "python"}
_KNOWN_EN = ("labour", "labor", "family", "civil", "criminal", "tax", "housing", "land", "customs", "budget", "election",
             "electoral", "planning", "urban", "air", "water", "procedure", "procedural", "enforcement", "administrative",
             "liability", "responsibility", "offences", "offenses", "executive", "penal")

_CODE_UZ_RE = re.compile(r"((?:[a-z][a-z-]*\s+){1,3})kodeks(?:i|ining|iga|ida|idan|ini|ni|lari|larida)?\b")
_CODE_RU_RE = re.compile(r"((?:[а-яё-]+\s+){1,2})кодекс(?:а|е|у|ом|ы|ов)?\b|кодекс(?:а|е|у|ом)?\s+(об?\s+[а-яё]+)")
_CODE_EN_RE = re.compile(r"((?:[a-z']+\s+){1,3})code\b")

# Act numbers: (series, regex). Laws use one running number; decrees and resolutions restarted in 2022.
_NUMBER_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("law", re.compile(r"(?:\bo['ʻʼ‘’`]?rq|\bорқ|ўрқ|\bзру|\bzru)\s*[-–№]?\s*(\d{1,6})\b", re.I)),
    ("decree", re.compile(r"(?:\bpf|\bпф|\bup|\bуп)\s*[-–№]\s*(\d{1,6})\b", re.I)),
    ("resolution", re.compile(r"(?:\bpq|\bпқ|\bпп|\bpp)\s*[-–№]\s*(\d{1,6})\b", re.I)),
    ("cabinet", re.compile(r"(?:\bvmq|\bвмқ|\bпкм|\bvm|\bвм)\s*[-–№]\s*(\d{1,6})\b", re.I)),
)
# Highest numbers ever used (old numbering for decrees and resolutions ended in 2021)
_MAX_EVER = {"decree": 6500, "resolution": 5500, "cabinet": 1500}
_MAX_NEW_NUMBERING = {"decree": 600, "resolution": 700, "cabinet": 1500}
_YEAR_RE = re.compile(r"\b(20[2-3]\d)\s*[-–]?\s*(?:yil|йил|год|г\b)")

_YES_NO_RE = re.compile(
    r"(?:\bmi\s*\?|\bmi\b\s*$|-?\bmi\b[,.]|\bmikan\b|правда ли|верно ли|по-прежнему|до сих пор|is it true|\bstill\b|"
    r"hali ham|hamon|hozir ham|bugun ham|ли\s*\?|\b(?:is|are|does|do|can)\b[^?]*\?\s*$)",
    re.I,
)

# --------------------------------------------------------------------------------------------- temporal rules


def _rule(id: str, triggers: tuple[str, ...], refs: tuple[tuple[str, str], ...], **text: str) -> TemporalRule:
    return TemporalRule(id=id, triggers=triggers, text=text, refs=refs)


TEMPORAL_RULES: tuple[TemporalRule, ...] = (
    _rule(
        "labour_code_1995",
        (r"\b1995\b[^.?!]{0,25}(?:mehnat kodeks|трудов\w* кодекс|labou?r code)",
         r"\beski mehnat kodeks|\bavvalgi mehnat kodeks|старо\w* трудов\w* кодекс|прежн\w* трудов\w* кодекс|\bold labou?r code"),
        (),
        uz_latn="1995-yilgi Mehnat kodeksi 2023-yil 30-aprelda kuchini yoʻqotgan: oʻrniga 2022-yil 28-oktyabrdagi yangi "
                "Mehnat kodeksi amalda.",
        uz_cyrl="1995 йилги Меҳнат кодекси 2023 йил 30 апрелда кучини йўқотган: ўрнига 2022 йил 28 октябрдаги янги "
                "Меҳнат кодекси амалда.",
        ru="Трудовой кодекс 1995 года утратил силу 30 апреля 2023 года: действует новый Трудовой кодекс от 28 октября "
           "2022 года.",
        en="The 1995 Labour Code was repealed on 30 April 2023 and replaced by the new Labour Code of 28 October 2022.",
    ),
    _rule(
        "constitution_1992",
        (r"\b1992\b[^.?!]{0,25}(?:konstitutsiya|конституци|constitution)",
         r"\beski tahrirdagi konstitutsiya|\beski konstitutsiya|старо\w* конституци|прежн\w* редакци\w* конституци|"
         r"\bold constitution"),
        (),
        uz_latn="Konstitutsiyaning 1992-yilgi tahriri 2023-yil 1-maydan kuchini yoʻqotgan: 2023-yil 30-apreldagi "
                "referendumda qabul qilingan yangi tahrir amalda, moddalar raqamlari ham oʻzgargan.",
        uz_cyrl="Конституциянинг 1992 йилги таҳрири 2023 йил 1 майдан кучини йўқотган: 2023 йил 30 апрелдаги "
                "референдумда қабул қилинган янги таҳрир амалда, моддалар рақамлари ҳам ўзгарган.",
        ru="Конституция в редакции 1992 года утратила силу с 1 мая 2023 года: действует новая редакция, принятая на "
           "референдуме 30 апреля 2023 года, и номера статей изменились.",
        en="The 1992 text of the Constitution has been repealed since 1 May 2023: the new text adopted by the referendum "
           "of 30 April 2023 applies, and the article numbers changed.",
    ),
    _rule(
        "tax_code_2007",
        (r"\b2007\b[^.?!]{0,25}(?:soliq kodeks|налогов\w* кодекс|tax code)",
         r"\beski soliq kodeks|старо\w* налогов\w* кодекс|\bold tax code"),
        (),
        uz_latn="2007-yilgi Soliq kodeksi 2020-yil 1-yanvardan kuchini yoʻqotgan: hozir 2019-yil 30-dekabrdagi Soliq "
                "kodeksi amalda.",
        uz_cyrl="2007 йилги Солиқ кодекси 2020 йил 1 январдан кучини йўқотган: ҳозир 2019 йил 30 декабрдаги Солиқ "
                "кодекси амалда.",
        ru="Налоговый кодекс 2007 года утратил силу с 1 января 2020 года: действует Налоговый кодекс от 30 декабря 2019 года.",
        en="The 2007 Tax Code was repealed on 1 January 2020; the Tax Code of 30 December 2019 applies.",
    ),
    # Old Labour Code article numbers that are still quoted (the same numbers cover other topics in the new code)
    _rule(
        "lc_old_100",
        (r"(?:mehnat kodeks\w*|\bmk\b|трудов\w* кодекс\w*|\bтк\b|labou?r code)[^.?!]{0,40}\b100\b && "
         r"(?:boshat|tashabbus|shtat|qisqar|bekor qil|уволь|увольн|инициатив|сокращ|прекращ|dismiss|terminat|redundan)",
         r"\b100\b[^.?!]{0,30}(?:modda|стать|article)[^.?!]{0,40}(?:mehnat kodeks|трудов\w* кодекс|labou?r code) && "
         r"(?:boshat|tashabbus|shtat|qisqar|уволь|увольн|инициатив|сокращ|dismiss|terminat|redundan)"),
        (("6257288", "161"),),
        uz_latn="100-modda — 1995-yilgi (kuchini yoʻqotgan) Mehnat kodeksining raqami: amaldagi Mehnat kodeksida mehnat "
                "shartnomasini ish beruvchining tashabbusi bilan bekor qilish 161-moddada.",
        uz_cyrl="100-модда — 1995 йилги (кучини йўқотган) Меҳнат кодексининг рақами: амалдаги Меҳнат кодексида меҳнат "
                "шартномасини иш берувчининг ташаббуси билан бекор қилиш 161-моддада.",
        ru="Статья 100 — номер из Трудового кодекса 1995 года, который утратил силу: в действующем Трудовом кодексе "
           "прекращение трудового договора по инициативе работодателя — статья 161.",
        en="Article 100 is the number from the repealed 1995 Labour Code: in the Labour Code in force, termination at the "
           "employer's initiative is article 161.",
    ),
    _rule(
        "lc_old_134",
        (r"(?:mehnat kodeks\w*|\bmk\b|трудов\w* кодекс\w*|\bтк\b|labou?r code)[^.?!]{0,40}\b134\b && (?:tatil|отпуск|leave|vacation)",),
        (("6257288", "217"),),
        uz_latn="134-modda va 15 ish kunlik taʼtil — 1995-yilgi (kuchini yoʻqotgan) Mehnat kodeksining normasi: amaldagi "
                "Mehnat kodeksining 217-moddasiga koʻra eng kam yillik taʼtil 21 kalendar kun.",
        uz_cyrl="134-модда ва 15 иш кунлик таътил — 1995 йилги (кучини йўқотган) Меҳнат кодексининг нормаси: амалдаги "
                "Меҳнат кодексининг 217-моддасига кўра энг кам йиллик таътил 21 календарь кун.",
        ru="Статья 134 и отпуск 15 рабочих дней — норма Трудового кодекса 1995 года, который утратил силу: по статье 217 "
           "действующего Трудового кодекса минимальный ежегодный отпуск — 21 календарный день.",
        en="Article 134 and 15 working days of leave come from the repealed 1995 Labour Code: under article 217 of the "
           "Labour Code in force, the minimum annual leave is 21 calendar days.",
    ),
    _rule(
        "lc_old_84",
        (r"(?:mehnat kodeks\w*|\bmk\b|трудов\w* кодекс\w*|\bтк\b|labou?r code)[^.?!]{0,40}\b84\b && (?:sinov|испыт|probation)",),
        (("6257288", "129"),),
        uz_latn="84-modda — 1995-yilgi (kuchini yoʻqotgan) Mehnat kodeksining raqami: amaldagi kodeksda dastlabki sinov "
                "129-moddada.",
        uz_cyrl="84-модда — 1995 йилги (кучини йўқотган) Меҳнат кодексининг рақами: амалдаги кодексда дастлабки синов "
                "129-моддада.",
        ru="Статья 84 — номер из утратившего силу Трудового кодекса 1995 года: в действующем кодексе предварительное "
           "испытание — статья 129.",
        en="Article 84 is from the repealed 1995 Labour Code: probation is article 129 of the Labour Code in force.",
    ),
    _rule(
        "lc_old_109",
        (r"(?:mehnat kodeks\w*|\bmk\b|трудов\w* кодекс\w*|\bтк\b|labou?r code)[^.?!]{0,40}\b109\b && (?:nafaqa|пособи|severance)",),
        (("6257288", "173"),),
        uz_latn="109-modda — 1995-yilgi (kuchini yoʻqotgan) Mehnat kodeksining raqami: amaldagi kodeksda ishdan "
                "boʻshatish nafaqasi 173-moddada.",
        uz_cyrl="109-модда — 1995 йилги (кучини йўқотган) Меҳнат кодексининг рақами: амалдаги кодексда ишдан бўшатиш "
                "нафақаси 173-моддада.",
        ru="Статья 109 — номер из утратившего силу Трудового кодекса 1995 года: выходное пособие в действующем кодексе — "
           "статья 173.",
        en="Article 109 is from the repealed 1995 Labour Code: severance pay is article 173 of the Labour Code in force.",
    ),
    _rule(
        "lc_old_270",
        (r"(?:mehnat kodeks\w*|\bmk\b|трудов\w* кодекс\w*|\bтк\b|labou?r code)[^.?!]{0,40}\b270\b && (?:sud|muddat|суд|срок|court|deadline)",),
        (("6257288", "560"),),
        uz_latn="270-modda — 1995-yilgi (kuchini yoʻqotgan) Mehnat kodeksining raqami: amaldagi kodeksda sudga murojaat "
                "muddatlari 560-moddada (ishga tiklash nizolari — 3 oy).",
        uz_cyrl="270-модда — 1995 йилги (кучини йўқотган) Меҳнат кодексининг рақами: амалдаги кодексда судга мурожаат "
                "муддатлари 560-моддада (ишга тиклаш низолари — 3 ой).",
        ru="Статья 270 — номер из утратившего силу Трудового кодекса 1995 года: сроки обращения в суд — статья 560 "
           "действующего кодекса (по спорам о восстановлении на работе — три месяца).",
        en="Article 270 is from the repealed 1995 Labour Code: court deadlines are article 560 of the Labour Code in force "
           "(three months for reinstatement claims).",
    ),
    # Old Constitution article numbers (1992 -> 2023)
    _rule(
        "const_old_25",
        (r"(?:konstitutsiya\w*|конституци\w*|constitution)[^.?!]{0,40}\b25\b && (?:ushlab|hibs|qamoq|ozodlik|задерж|арест|страж|detain|detention|arrest|48)",),
        (("6445145", "27"),),
        uz_latn="25-modda — Konstitutsiyaning 1992-yilgi tahriridagi raqam: amaldagi tahrirda shaxs erkinligi va sud "
                "qarorisiz 48 soatdan ortiq ushlab turish taqiqi 27-moddada.",
        uz_cyrl="25-модда — Конституциянинг 1992 йилги таҳриридаги рақам: амалдаги таҳрирда шахс эркинлиги ва суд "
                "қарорисиз 48 соатдан ортиқ ушлаб туриш тақиқи 27-моддада.",
        ru="Статья 25 — номер из редакции Конституции 1992 года: в действующей редакции свобода личности и запрет "
           "задержания без решения суда дольше 48 часов — статья 27.",
        en="Article 25 is the 1992 numbering: in the Constitution in force, liberty and the 48-hour limit on detention "
           "without a court decision are in article 27.",
    ),
    _rule(
        "const_old_26",
        (r"(?:konstitutsiya\w*|конституци\w*|constitution)[^.?!]{0,40}\b26\b && (?:aybsiz|prezump|невиновн|презумпц|innocen)",),
        (("6445145", "28"),),
        uz_latn="26-modda — Konstitutsiyaning 1992-yilgi tahriridagi raqam: amaldagi tahrirda aybsizlik prezumpsiyasi "
                "28-moddada.",
        uz_cyrl="26-модда — Конституциянинг 1992 йилги таҳриридаги рақам: амалдаги таҳрирда айбсизлик презумпцияси "
                "28-моддада.",
        ru="Статья 26 — номер из редакции Конституции 1992 года: презумпция невиновности в действующей редакции — статья 28.",
        en="Article 26 is the 1992 numbering: the presumption of innocence is article 28 of the Constitution in force.",
    ),
    _rule(
        "const_old_44",
        (r"(?:konstitutsiya\w*|конституци\w*|constitution)[^.?!]{0,40}\b44\b && (?:sud orqali himoya|sudga shikoyat|судебн\w* защит|judicial protection|court protection)",),
        (("6445145", "55"),),
        uz_latn="44-modda — Konstitutsiyaning 1992-yilgi tahriridagi raqam: amaldagi tahrirda huquqlarni sud orqali "
                "himoya qilish 55-moddada.",
        uz_cyrl="44-модда — Конституциянинг 1992 йилги таҳриридаги рақам: амалдаги таҳрирда ҳуқуқларни суд орқали ҳимоя "
                "қилиш 55-моддада.",
        ru="Статья 44 — номер из редакции Конституции 1992 года: судебная защита прав в действующей редакции — статья 55.",
        en="Article 44 is the 1992 numbering: judicial protection of rights is article 55 of the Constitution in force.",
    ),
    _rule(
        "const_48h_old_edition",
        (r"(?:konstitutsiya\w*|конституци\w*|constitution) && \b48\s*(?:soat|соат|час|hour) && "
         r"(?:eski tahrir|1992|avvalgi tahrir|qaysi moddada edi|старой редакци|прежней редакци|редакции 1992|old (?:text|version|edition)|1992 text)",),
        (("6445145", "27"),),
        uz_latn="Konstitutsiyaning yangi tahririda (2023) sud qarorisiz 48 soatdan ortiq ushlab turish taqiqi 27-moddada; "
                "kuchini yoʻqotgan eski tahririda (1992) shaxs erkinligi va daxlsizligi 25-moddada edi (48 soatlik muddat u "
                "yerda yozilmagan).",
        uz_cyrl="Конституциянинг янги таҳририда (2023) суд қарорисиз 48 соатдан ортиқ ушлаб туриш тақиқи 27-моддада; "
                "кучини йўқотган эски таҳририда (1992) шахс эркинлиги ва дахлсизлиги 25-моддада эди (48 соатлик муддат у "
                "ерда ёзилмаган).",
        ru="В новой редакции Конституции (2023) запрет задержания без решения суда дольше 48 часов — статья 27; в "
           "утратившей силу редакции 1992 года свобода и личная неприкосновенность были в статье 25 (без срока 48 часов).",
        en="In the new text of the Constitution (2023) the ban on detention without a court decision for over 48 hours is "
           "article 27; in the repealed 1992 text liberty and personal inviolability were article 25 (without the 48-hour limit).",
    ),
    _rule(
        "annual_leave_history",
        (r"(?:tatil|отпуск|annual (?:paid )?(?:labou?r )?leave|paid leave|vacation) && "
         r"(?:\b(?:199\d|200\d|201\d|202[0-2])\b)",),
        (("6257288", "217"),),
        uz_latn="2023-yil 30-aprelgacha 1995-yilgi Mehnat kodeksi amalda boʻlgan: eng kam yillik taʼtil 15 ish kuni edi; "
                "2023-yil 30-apreldan amaldagi Mehnat kodeksining 217-moddasiga koʻra — 21 kalendar kun.",
        uz_cyrl="2023 йил 30 апрелгача 1995 йилги Меҳнат кодекси амалда бўлган: энг кам йиллик таътил 15 иш куни эди; "
                "2023 йил 30 апрелдан амалдаги Меҳнат кодексининг 217-моддасига кўра — 21 календарь кун.",
        ru="До 30 апреля 2023 года действовал Трудовой кодекс 1995 года: минимальный ежегодный отпуск составлял 15 рабочих "
           "дней; с 30 апреля 2023 года по статье 217 действующего Трудового кодекса — 21 календарный день.",
        en="Until 30 April 2023 the 1995 Labour Code applied: the minimum annual leave was 15 working days; since 30 April "
           "2023 article 217 of the Labour Code in force sets 21 calendar days.",
    ),
    # Figures that changed
    _rule(
        "vat_rate",
        (r"(?:\bqqs\b|qoshilgan qiymat solig|\bндс\b|добавленн\w* стоимост|\bvat\b|value[- ]added tax) && "
         r"\b(?:15|20)\s*(?:%|foiz|фоиз|процент|percent)",),
        (("4674902", "258"),),
        uz_latn="QQS stavkasi 2023-yil 1-yanvardan 12 foiz (Soliq kodeksi 258-modda); 15 foizlik stavka eskirgan "
                "(2019-yil oktyabrdan 2022-yil oxirigacha amalda boʻlgan).",
        uz_cyrl="ҚҚС ставкаси 2023 йил 1 январдан 12 фоиз (Солиқ кодекси 258-модда); 15 фоизлик ставка эскирган "
                "(2019 йил октябрдан 2022 йил охиригача амалда бўлган).",
        ru="Ставка НДС с 1 января 2023 года снижена до 12 процентов (ст. 258 Налогового кодекса); ставка 15% устарела "
           "(действовала с октября 2019 года до конца 2022 года).",
        en="The VAT rate has been 12% since 1 January 2023 (Tax Code art. 258); the 15% rate is outdated (it applied "
           "from October 2019 to the end of 2022).",
    ),
    _rule(
        "marriage_age_17",
        (r"(?:nikoh yosh|nikohlanish yosh|брачн\w* возраст|marriage age|marriageable age|age (?:of|for) marriage) && \b17\b",),
        (("104720", "15"),),
        uz_latn="Nikoh yoshi erkaklar va ayollar uchun bir xil — 18 yosh (Oila kodeksi 15-modda); ayollar uchun 17 yosh "
                "normasi bekor qilingan (2019-yil).",
        uz_cyrl="Никоҳ ёши эркаклар ва аёллар учун бир хил — 18 ёш (Оила кодекси 15-модда); аёллар учун 17 ёш нормаси "
                "бекор қилинган (2019 йил).",
        ru="Брачный возраст для мужчин и женщин одинаковый — 18 лет (ст. 15 Семейного кодекса); норма о 17 годах для "
           "женщин отменена (2019 год).",
        en="The marriage age is the same for men and women — 18 (Family Code art. 15); the old age of 17 for women was "
           "repealed in 2019.",
    ),
    _rule(
        "annual_leave_15",
        (r"(?:tatil|отпуск|annual leave|paid leave|vacation) && \b15\s*(?:ish kun|рабоч|working day)",),
        (("6257288", "217"),),
        uz_latn="Eng kam yillik taʼtil — 21 kalendar kun (Mehnat kodeksi 217-modda); 15 ish kuni — kuchini yoʻqotgan "
                "1995-yilgi kodeksning normasi.",
        uz_cyrl="Энг кам йиллик таътил — 21 календарь кун (Меҳнат кодекси 217-модда); 15 иш куни — кучини йўқотган "
                "1995 йилги кодекснинг нормаси.",
        ru="Минимальный ежегодный отпуск — 21 календарный день (ст. 217 Трудового кодекса); 15 рабочих дней — норма "
           "утратившего силу кодекса 1995 года.",
        en="The minimum annual leave is 21 calendar days (Labour Code art. 217); 15 working days was the rule of the "
           "repealed 1995 code.",
    ),
    _rule(
        "detention_72h",
        (r"(?:ushlab tur|ushlan|hibsga|задерж|detain|detention) && \b72\s*(?:soat|соат|час|hour)",),
        (("6445145", "27"),),
        uz_latn="Sud qarorisiz ushlab turish koʻpi bilan 48 soat (Konstitutsiya 27-modda); 72 soat — eskirgan muddat.",
        uz_cyrl="Суд қарорисиз ушлаб туриш кўпи билан 48 соат (Конституция 27-модда); 72 соат — эскирган муддат.",
        ru="Без решения суда задержание допускается не более чем на 48 часов (ст. 27 Конституции); 72 часа — устаревший "
           "срок.",
        en="Detention without a court decision is limited to 48 hours (Constitution art. 27); 72 hours is outdated.",
    ),
    _rule(
        "reinstatement_1_month",
        (r"(?:ishga tiklash|ishga qayta tiklash|восстановлен\w* на работ|reinstat) && "
         r"\b(?:1|bir|один|одного|one)\s*(?:oy|ой|месяц|month)",),
        (("6257288", "560"),),
        uz_latn="Ishga tiklash toʻgʻrisidagi nizo boʻyicha sudga murojaat muddati — 3 oy (Mehnat kodeksi 560-modda); "
                "1 oylik muddat kuchini yoʻqotgan eski kodeksda edi.",
        uz_cyrl="Ишга тиклаш тўғрисидаги низо бўйича судга мурожаат муддати — 3 ой (Меҳнат кодекси 560-модда); "
                "1 ойлик муддат кучини йўқотган эски кодексда эди.",
        ru="Срок обращения в суд по спору о восстановлении на работе — три месяца (ст. 560 Трудового кодекса); "
           "месячный срок был в утратившем силу кодексе.",
        en="The deadline to go to court for reinstatement is three months (Labour Code art. 560); one month was the rule "
           "of the repealed code.",
    ),
)

# --------------------------------------------------------------------------------------------- notices

# A non-existent act number is not repeated in the answer (it would read like a citation); its kind is named instead
_KIND = {
    "law": {"uz_latn": "qonun", "uz_cyrl": "қонун", "ru": "закон", "en": "law"},
    "decree": {"uz_latn": "Prezident farmoni", "uz_cyrl": "Президент фармони", "ru": "указ Президента", "en": "presidential decree"},
    "resolution": {"uz_latn": "Prezident qarori", "uz_cyrl": "Президент қарори", "ru": "постановление Президента", "en": "presidential resolution"},
    "cabinet": {"uz_latn": "Vazirlar Mahkamasi qarori", "uz_cyrl": "Вазирлар Маҳкамаси қарори", "ru": "постановление Кабинета Министров", "en": "Cabinet of Ministers resolution"},
}

_NOTICE = {
    "missing_certain": {
        "uz_latn": "{act}da {art} raqamli modda mavjud emas: unda jami {max} ta modda bor.",
        "uz_cyrl": "{act}да {art} рақамли модда мавжуд эмас: унда жами {max} та модда бор.",
        "ru": "Статьи под номером {art} в документе «{act}» не существует: в нём всего {max} {articles}.",
        "en": "There is no article number {art} in the {act}: it has {max} articles in total.",
    },
    "missing_range": {
        "uz_latn": "{act}ning amaldagi matnida {art} raqamli modda topilmadi (kuchini yoʻqotgan boʻlishi mumkin).",
        "uz_cyrl": "{act}нинг амалдаги матнида {art} рақамли модда топилмади (кучини йўқотган бўлиши мумкин).",
        "ru": "Статья под номером {art} в действующей редакции документа «{act}» не найдена (возможно, утратила силу).",
        "en": "Article number {art} was not found in the current text of the {act} (it may have been repealed).",
    },
    "unknown_code": {
        "uz_latn": "Oʻzbekistonda «{name} kodeksi» mavjud emas: amaldagi kodekslar orasida bunday hujjat yoʻq.",
        "uz_cyrl": "Ўзбекистонда «{name} кодекси» мавжуд эмас: амалдаги кодекслар орасида бундай ҳужжат йўқ.",
        "ru": "Такого кодекса («{name}») в Узбекистане не существует: среди действующих кодексов его нет.",
        "en": "There is no “{name} Code” in Uzbekistan: it does not exist among the codes in force.",
    },
    "number_certain": {
        "uz_latn": "Savolda koʻrsatilgan {kind} raqami mavjud emas: bunday raqam berilmagan.",
        "uz_cyrl": "Саволда кўрсатилган {kind} рақами мавжуд эмас: бундай рақам берилмаган.",
        "ru": "Указанного в вопросе номера ({kind}) не существует: такой номер не присваивался.",
        "en": "The {kind} number given in the question does not exist: no act has that number.",
    },
    "number_unknown": {
        "uz_latn": "{name} raqamli qonun bazamizda topilmadi — raqamni lex.uz saytida tekshiring.",
        "uz_cyrl": "{name} рақамли қонун базамизда топилмади — рақамни lex.uz сайтида текширинг.",
        "ru": "Закон {name} в нашей базе не найден — проверьте номер на lex.uz.",
        "en": "Law {name} was not found in our database — please check the number on lex.uz.",
    },
}
_LEAD = {
    "no": {"uz_latn": "Yoʻq.", "uz_cyrl": "Йўқ.", "ru": "Нет.", "en": "No."},
    "attention": {"uz_latn": "Diqqat:", "uz_cyrl": "Диққат:", "ru": "Обратите внимание:", "en": "Please note:"},
    "false_tail": {
        "uz_latn": "Shuning uchun savoldagi havolaga tayanib boʻlmaydi.",
        "uz_cyrl": "Шунинг учун саволдаги ҳаволага таяниб бўлмайди.",
        "ru": "Поэтому на ссылку из вопроса опираться нельзя.",
        "en": "So the reference in the question cannot be relied on.",
    },
    "current": {
        "uz_latn": "Amaldagi qonunchilik boʻyicha:",
        "uz_cyrl": "Амалдаги қонунчилик бўйича:",
        "ru": "По действующему законодательству:",
        "en": "Under the law in force:",
    },
}
PREMISE_STEPS = {
    "uz_latn": [
        "Hujjat nomi va modda raqamini rasmiy matndan tekshiring (lex.uz)",
        "Vaziyatni oddiy soʻzlar bilan yozing — tegishli amaldagi normani topib beraman",
    ],
    "uz_cyrl": [
        "Ҳужжат номи ва модда рақамини расмий матндан текширинг (lex.uz)",
        "Вазиятни оддий сўзлар билан ёзинг — тегишли амалдаги нормани топиб бераман",
    ],
    "ru": [
        "Проверьте название документа и номер статьи по официальному тексту (lex.uz)",
        "Опишите ситуацию своими словами — я найду действующую норму",
    ],
    "en": [
        "Check the act's name and the article number against the official text (lex.uz)",
        "Describe your situation in plain words and I will find the provision in force",
    ],
}


def _ru_articles(n: int | None) -> str:
    """Russian plural: 1 статья, 2 статьи, 5 статей (11-14 статей)."""
    if n is None:
        return "статей"
    if n % 10 == 1 and n % 100 != 11:
        return "статья"
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return "статьи"
    return "статей"


def _lang_key(lang: Any) -> str:
    value = getattr(lang, "value", lang)
    return value if value in ("uz_latn", "uz_cyrl", "ru", "en") else "uz_latn"


# --------------------------------------------------------------------------------------------- checker


def _article_mentions(folded: str) -> list[tuple[str, int, int]]:
    out: list[tuple[str, int, int]] = []
    for m in _ARTICLE_RE.finditer(folded):
        base = m.group(1) or m.group(4) or m.group(7)
        sub = m.group(2) or m.group(5) or (m.group(3) or m.group(6) or "").translate(_SUP)
        out.append((f"{base}.{sub}" if sub else base, m.start(), m.end()))
    seen = {a for a, _, _ in out}
    out.extend(r for r in range_articles(folded) if r[0] not in seen)
    return out


def _base_number(article: str) -> int | None:
    m = re.match(r"\d+", article or "")
    return int(m.group()) if m else None


class PremiseChecker:
    """Finds false or outdated premises in a question (see the module docstring)."""

    def __init__(self, resolver: ActResolver, inventory: Callable[[], Mapping[str, frozenset[str]]]) -> None:
        self.resolver = resolver
        self._inventory_fn = inventory
        self._inventory: Mapping[str, frozenset[str]] | None = None
        self._max_law = 0
        self._law_numbers: set[int] = set()
        for d in resolver.catalog.values():
            for key in ("number_uz", "number_ru"):
                m = re.search(r"(?:ЎРҚ|ЗРУ|O.?RQ|ZRU)\s*[-–]?\s*(\d+)", str(d.get(key) or ""), re.I)
                if m:
                    n = int(m.group(1))
                    self._law_numbers.add(n)
                    self._max_law = max(self._max_law, n)
        self._compiled = [
            (rule, [[re.compile(part.strip(), re.I) for part in trig.split(" && ")] for trig in rule.triggers])
            for rule in TEMPORAL_RULES
        ]

    # -- data
    @property
    def inventory(self) -> Mapping[str, frozenset[str]]:
        if self._inventory is None:
            self._inventory = self._inventory_fn() or {}
        return self._inventory

    def _articles_of(self, act_id: str) -> frozenset[str]:
        inv = self.inventory
        if act_id in CIVIL_PARTS:
            return inv.get(CIVIL_PARTS[0], frozenset()) | inv.get(CIVIL_PARTS[1], frozenset())
        return inv.get(act_id, frozenset())

    def _max_article(self, act_id: str) -> int | None:
        nums = [n for a in self._articles_of(act_id) if (n := _base_number(a)) is not None]
        return max(nums) if nums else None

    def act_name(self, act_id: str, lang: Any) -> str:
        from lex_agent.assistant.act_names import en_title
        from lex_agent.language.transliterator import cyrillic_to_latin

        key = _lang_key(lang)
        if act_id in CIVIL_PARTS:
            return {"uz_latn": "Fuqarolik kodeksi", "uz_cyrl": "Фуқаролик кодекси", "ru": "Гражданский кодекс", "en": "Civil Code"}[key]
        d = self.resolver.catalog.get(act_id) or {}
        if key == "en":
            return en_title(act_id) or d.get("short_ru") or act_id
        if key == "ru":
            return d.get("short_ru") or d.get("title_ru") or act_id
        short = d.get("short_uz") or d.get("title_uz") or act_id
        return short if key == "uz_cyrl" else cyrillic_to_latin(short)

    # -- checks
    def check(self, question: str, lang: Any = "uz_latn") -> PremiseReport:
        report = PremiseReport(yes_no=bool(_YES_NO_RE.search(question)))
        if not question or not question.strip():
            return report
        folded = fold_for_match(question)
        try:
            report.issues.extend(self._missing_articles(question, folded))
            report.issues.extend(self._unknown_codes(folded))
            report.issues.extend(self._unknown_numbers(question))
        except Exception:  # pragma: no cover - a premise check must never break answering
            report.issues = []
        report.temporal = self._temporal(folded)
        return report

    def _missing_articles(self, question: str, folded: str) -> list[PremiseIssue]:
        mentions = _article_mentions(folded)
        if not mentions:
            return []
        alias_spans = [(cid, m.start(), m.end()) for cid, rx in self.resolver._aliases for m in rx.finditer(folded)]
        other_acts = [r.canonical_id for r in self.resolver.resolve(question) if r.via != "alias"]
        issues: list[PremiseIssue] = []
        seen: set[tuple[str, str]] = set()
        for art, start, end in mentions:
            candidates: list[str] = []
            if alias_spans:
                def dist(span: tuple[str, int, int]) -> int:
                    _, s, e = span
                    return s - end if s >= end else (start - e if e <= start else 0)

                best = min(alias_spans, key=dist)
                if dist(best) <= 60:
                    candidates = [best[0]]
            if not candidates:
                candidates = list(dict.fromkeys(other_acts))
            if not candidates:
                continue
            known = [cid for cid in candidates if self._articles_of(cid)]
            if not known or any(art in self._articles_of(cid) for cid in known):
                continue
            cid = known[0]
            key = (CIVIL_PARTS[0] if cid in CIVIL_PARTS else cid, art)
            if key in seen:
                continue
            seen.add(key)
            mx = self._max_article(cid)
            base = _base_number(art)
            certain = bool(mx and base and base > mx)
            if not certain:
                # Inside the range only a number that is absent altogether is reported (a repealed article); a missing
                # sub-article next to an existing base number is more likely a gap in the parsed text.
                present = self._articles_of(cid)
                if base is None or str(base) in present or any(a.startswith(f"{base}.") for a in present):
                    continue
            issues.append(PremiseIssue("missing_article", certain, act_id=cid, article=art.replace(".", "-"), max_article=mx))
        return issues

    def _unknown_codes(self, folded: str) -> list[PremiseIssue]:
        issues: list[PremiseIssue] = []
        found: set[str] = set()
        for m in _CODE_UZ_RE.finditer(folded):
            words = m.group(1).split()
            # The code's name stands right before "kodeksi" ("Mehnat kodeksi"), or before "to'g'risidagi kodeks"
            name_words = words[:-1] if words and words[-1] in ("togrisidagi", "haqidagi") else words
            if not name_words:
                continue
            w = name_words[-1]
            if any(w.startswith(k) for k in _KNOWN_UZ) or any(x.startswith(k) for x in name_words for k in _KNOWN_UZ):
                continue
            if w in _GENERIC_UZ or len(w) < 4 or re.match(r"\d", w) or re.search(r"(?:gan|kan|qan|digan|yotgan|ilgan)$", w):
                continue  # "… Respublikasi Kodeksi", "qabul qilingan Kodeks": no code is named
            name = w.capitalize()
            if name not in found:
                found.add(name)
                issues.append(PremiseIssue("unknown_code", True, name=name))
        for m in _CODE_RU_RE.finditer(folded):
            if m.group(2):  # "кодекс об административной ..."
                continue
            words = (m.group(1) or "").split()
            if any(any(w.startswith(k) for k in _KNOWN_RU) for w in words):
                continue
            content = [w for w in words if w not in _GENERIC_RU and len(w) >= 4]
            if content:
                name = content[-1].capitalize()
                if name not in found:
                    found.add(name)
                    issues.append(PremiseIssue("unknown_code", True, name=name))
        if re.search(r"\barticle\b|\blaw\b|\bstatute|\blegal\b|o'?rq|зру", folded):
            for m in _CODE_EN_RE.finditer(folded):
                words = m.group(1).split()
                if any(any(w.startswith(k) for k in _KNOWN_EN) for w in words) or (words and words[-1] in _NON_LEGAL_EN):
                    continue
                content = [w for w in words if w not in _GENERIC_EN and len(w) >= 3 and w.isalpha()]
                if content:
                    name = " ".join(w.capitalize() for w in content[-2:])
                    if name not in found:
                        found.add(name)
                        issues.append(PremiseIssue("unknown_code", True, name=name))
        return issues

    def _unknown_numbers(self, question: str) -> list[PremiseIssue]:
        issues: list[PremiseIssue] = []
        years = [int(y) for y in _YEAR_RE.findall(question)]
        for series, rx in _NUMBER_PATTERNS:
            for m in rx.finditer(question):
                n = int(m.group(1))
                label = m.group(0).strip()
                if series == "law":
                    if n in self._law_numbers:
                        continue
                    certain = self._max_law > 0 and n > self._max_law + 150
                    issues.append(PremiseIssue("unknown_number", certain, name=label, series=series))
                    continue
                certain = n > _MAX_EVER[series] or (bool(years) and max(years) >= 2022 and n > _MAX_NEW_NUMBERING[series])
                if certain:
                    issues.append(PremiseIssue("unknown_number", True, name=label, series=series))
        return issues

    def _temporal(self, folded: str) -> list[TemporalRule]:
        hits: list[TemporalRule] = []
        for rule, alternatives in self._compiled:
            if any(all(rx.search(folded) for rx in parts) for parts in alternatives):
                hits.append(rule)
        # A specific old-article rule already explains the repealed code
        if any(r.id.startswith("lc_old_") or r.id in ("annual_leave_15", "reinstatement_1_month") for r in hits):
            hits = [r for r in hits if r.id != "labour_code_1995"]
        if any(r.id.startswith("const_old_") for r in hits):
            hits = [r for r in hits if r.id != "constitution_1992"]
        # Rules pointing at the same current article say the same thing: keep the first (most specific) one
        kept: list[TemporalRule] = []
        for rule in hits:
            if rule.refs and any(set(rule.refs) <= set(k.refs) for k in kept):
                continue
            kept.append(rule)
        return kept

    # -- rendering
    def notice(self, report: PremiseReport, lang: Any) -> str:
        key = _lang_key(lang)
        lines: list[str] = []
        for issue in report.issues:
            if issue.kind == "missing_article":
                tpl = _NOTICE["missing_certain" if issue.certain else "missing_range"][key]
                lines.append(tpl.format(act=self.act_name(issue.act_id or "", lang), art=issue.article, max=issue.max_article,
                                        articles=_ru_articles(issue.max_article)))
            elif issue.kind == "unknown_code":
                lines.append(_NOTICE["unknown_code"][key].format(name=issue.name))
            elif issue.kind == "unknown_number":
                tpl = _NOTICE["number_certain" if issue.certain else "number_unknown"][key]
                lines.append(tpl.format(name=issue.name, kind=_KIND[issue.series or "law"][key]))
        for rule in report.temporal:
            lines.append(rule.text.get(key) or rule.text["uz_latn"])
        if not lines:
            return ""
        head = _LEAD["no"][key] if report.yes_no and (report.certain_false or report.temporal) else _LEAD["attention"][key]
        body = " ".join(lines)
        if report.certain_false and not report.temporal:
            body = f"{body} {_LEAD['false_tail'][key]}"
        return f"{head} {body}"

    @staticmethod
    def current_label(lang: Any) -> str:
        return _LEAD["current"][_lang_key(lang)]
