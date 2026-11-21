"""Question routing: decide what kind of turn this is before spending time on retrieval.

Kinds: ``greeting``, ``thanks``, ``farewell``, ``about`` (who are you / what can you do / requests for the system
prompt), ``off_topic``, ``emergency`` (immediate danger: violence, suicide, abduction, fire), ``clarify`` (a bare
"help me" with no facts), ``illegal`` (asks how to break the law or evade liability; questions about the liability
itself stay legal), ``template`` (document samples), ``calculation``, ``figures`` (BHM, minimum wage, CB rate) and
``legal`` (everything else). Prompt-injection attempts are flagged (``injection``) and simply
treated as text. Matching is done on folded text, so Latin/Cyrillic Uzbek, Russian and English all work.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from lex_agent.knowledge.lexicon import _GAP, ConceptMatch, fold_ru, fold_uz


def _rx(pattern: str) -> re.Pattern[str]:
    return re.compile(pattern.replace("~", _GAP), re.I)


_GREETING = _rx(r"^\s*(?:assalomu? ?alaykum|asalomu? ?aleykum|salom(?:lar)?|hayrli (?:kun|tong|kech)|privet|zdravstvuyte|"
                r"привет|здравствуй\w*|добр\w+ (?:день|утро|вечер)|hello|hi|hey|good (?:morning|afternoon|evening))\b[\s!.,?]*"
                r"(?:\w+[\s!.,?]*){0,3}$")
_THANKS = _rx(r"^\s*(?:katta )?(?:rahmat|tashakkur|sag bol|spasibo|спасибо|благодарю|thank(?:s| you)|thx)\b[\s!.,]*(?:\w+[\s!.,]*){0,4}$")
_FAREWELL = _rx(r"^\s*(?:hayr|hayrli kun|korishguncha|poka|пока|до свидания|bye|goodbye|see you)\b[\s!.,]*(?:\w+[\s!.,]*){0,3}$")
_ABOUT = _rx(r"\b(?:sen|siz) kim(?:san|siz)|kimsan|nima (?:kila olasan|kilasan|kila olasiz)|kanday yordam ber|"
             r"бот\b|кто ты|что ты умеешь|чем (?:ты )?можешь помочь|who are you|what can you do|are you (?:a )?(?:bot|ai|human)|"
             r"system prompt|tizim (?:korsatma|prompt)|sistemn\w* promt|системн\w* (?:промпт|инструкц)|your (?:instructions|prompt)")
_INJECTION = _rx(r"ignore (?:all |the )?(?:previous|above|prior) (?:instructions|rules)|disregard (?:all |the )?(?:previous|above)|"
                 r"forget (?:all )?(?:your|previous) instructions|you are now|act as (?:a|an) |developer mode|jailbreak|\bdan mode|"
                 r"oldingi (?:korsatma|buyruk|koida)\w*~(?:unut|etibor berma|bekor)|endi sen\w*~(?:boshka|emas)|"
                 r"игнорируй\w*~(?:инструкц|правил)|забудь\w*~(?:инструкц|правил)|ты теперь|притворись|"
                 r"reveal (?:your|the) (?:system|hidden) prompt|print (?:your|the) (?:system )?prompt")
_PROMPT_LEAK = _rx(r"system prompt|tizim (?:korsatma|prompt)|системн\w* (?:промпт|инструкц)|your (?:instructions|prompt)|"
                   r"(?:print|reveal|show) (?:your|the)")
_EMERGENCY = _rx(r"ozimni oldir|ozimga kasd|joniga kasd|yashagim kelmay|hayotim\w*~havf|meni oldir\w*|oldirmokchi|"
                 r"oldiraman de|oldirib kuyaman|oldirishi mumkin|"
                 r"\b(?:meni|bizni|bolam\w*|onam\w*|hotinim\w*|singlim\w*)~(?:uryapti|uryap|urayap|kaltaklayap\w*|"
                 r"dopposlayap\w*|uradi|urdi|kaltakladi)|\b(?:eri|erim|otam|otasi|kuyovim|akam)~(?:uryapti|uradi|urdi|kaltakla\w*)|"
                 r"hozir (?:uryapti|uryap|kaltaklayap|urayap)|uyga bostirib|garovga ol\w*|bolani olib kochi|odam ogirla\w*~hozir|"
                 r"zorla(?:di|yapti|moqchi|mokchi)|nomusiga teg|"
                 r"yordam bering\W*(?:tez|hozir)|tez yordam kerak|"
                 r"покончить с собой|суицид|не хочу жить|убивают|угрожа\w* убить|убью|избива\w*|бь[её]т (?:меня|нас|реб)|"
                 r"муж бь[её]т|похитил|изнасилова\w*|"
                 r"помогите\W*(?:срочно|скорее)|kill myself|suicid|want to die|being (?:beaten|attacked)|kidnapp|"
                 r"(?:husband|wife|partner|father) (?:beats|hits|is beating)|threaten\w* to kill|beats me|raped")
# Violence: a perpetrator or victim word followed (within a few words) by a hitting verb in any tense, on folded Uzbek
_UZ_PERSON = (r"(?:\b(?:eri|erim|erimni|uni|meni|bizni|seni)\b|\b(?:turmush ortog|ogay ota|ogay ona|kaynona|kaynota|kuyov|"
              r"sherig|bolam|bolalarim|hotinim|singlim|kizim|oglim|akam|ukam|otam|otasi|onam|onasi|opam)\w*)")
_UZ_HIT = (r"(?:ur(?:a?yap|vot|ayot|mokda|ishyap|ishvot)\w*|urib (?:tashla|yubor|ket)\w*|urdi\w*|uradi\w*|urishdi\w*|"
           r"kaltakla\w*|doppos\w*|tep(?:yap|di|adi|ib)\w*)")
_EMERGENCY_MORE = _rx(
    _UZ_PERSON + "~" + _UZ_HIT + r"|\b(?:uryap|urayap|urvot|urayot|kaltaklayap|kaltaklayvot|dopposlayap)\w*|"
    r"\b(?:kizim|oglim|bolam|bolalarim|kelin|singlim|ukam|meni|uni)\w*~ogirla(?:b ket|shdi|di|ndi|yap)\w*|"
    r"oldiris\w* bilan kork\w*|\b(?:uy|kvartira|bino)\w*~yon(?:yap|ayap|vot|mokda)\w*|yongin chik\w*|gaz\w*~(?:hidi|siz)\w*|"
    r"\b(?:муж|отец|отчим|сожител|парень|брат|свекр|свекров|сын)\w*~(?:бь[её]т|избива\w*|избил\w*|ударил\w*|душ(?:ит|ил)\w*)|"
    r"избил\w*|меня~(?:бь[её]т|ударил\w*)|угрож\w*~(?:убийств|убить|расправ)|украл\w*~(?:реб[её]н|дочь|дочку|сына)|"
    r"\bгорит\b|утечк\w* газа|"
    r"\b(?:husband|wife|partner|boyfriend|girlfriend|father|stepfather|mother|brother|son|ex)(?:'s|s)?\b~"
    r"(?:hits?|hitting|beat\w*|punch\w*|chok\w*|kick\w*|abus\w*)\b|"
    r"\b(?:hit|hits|hitting|beat|beats|beating|punched|choked|kicked|attacked|abusing|abuses) me\b|"
    r"house is on fire|gas leak|\b(?:muzh|muj)\w*~(?:bet|byot|izbil\w*|udaril\w*)\b"
)
# Asking for help with wrongdoing = a wrongful act + a "how / a way to" intent, unless it asks about the liability
_ILLEGAL_ACT_WEAK = _rx(
    r"\b(?:solik|daromad)\w*~(?:yashir|koch|kutul|kamaytirib korsat)\w*|aliment\w*dan~(?:koch|kutul|yashir|bosh tort)\w*|"
    r"\b(?:harbiy hizmat|armiya|askar)\w*~(?:koch|kutul|yashir|bosh tort)\w*|\bpora\w*~(?:ber|uzat)\w*|"
    r"\b(?:soht?a|kalbaki)\w*~(?:hujjat|diplom|spravka|malumotnoma|guvohnoma|pasport|imzo|muhr|chek|prava)\w*|"
    r"\b(?:diplom|spravka|malumotnoma|guvohnoma|prava|sertifikat|attestat)\w*~(?:sotib ol|pulga ol)\w*|"
    r"\b(?:mol-?mulk|mulk|uy|mashina|avtomobil|pul|kvartira)\w*~yashir\w*|"
    r"(?:спрятать|скрыть|укрыть|переписать)\w*~(?:имуществ|деньг|доход|квартир|машин|актив)|откосить|"
    r"(?:уклониться|избежать|уйти) от (?:армии|службы|призыва)|купить~(?:диплом|справк|права|аттестат)|"
    r"(?:фальшив|поддельн)\w*~(?:справк|документ|диплом|паспорт|подпис|печат)|обмануть~(?:налогов|суд|полици|гаи|страхов)|"
    r"dodge (?:the )?(?:tax|taxes|draft|military)|(?:avoid|get out of|stop) paying (?:child support|alimony|tax\w*)|"
    r"hide (?:my )?(?:money|income|assets|property) from|buy (?:a )?(?:fake )?(?:diploma|degree|certificate|licen[cs]e)|"
    r"fake (?:a )?(?:certificate|diploma|sick note|document)|(?:avoid|dodge|escape) (?:military service|the draft|conscription)|"
    r"cheat (?:on )?(?:my )?tax\w*"
)
# "not paying" is lawful in some cases (exemptions), so it needs an explicit "how / which way"
_ILLEGAL_ACT_STRONG = _rx(r"\b(?:solik|aliment|kredit|karz)\w*~tolamas\w*|не платить~(?:алимент|кредит)")
_HOW_STRONG = _rx(r"\bkanday|\bkalay|\bkanaka|\busul|\byol(?:i|lari)?\b|\bкак\b|способ|\bhow\b|\bways? to\b")
_HOW_WEAK = _rx(r"mumkin|bolad|bulad|kerak|можно|\bcan i\b|\bpossible\b")
# Questions about the liability, or reports of someone else's wrongdoing (complaints, searches, recovery), stay legal
# Asking for the lawful way ("qonuniy yo'l bilan", "legally") is a legitimate question about exemptions and options
_LAWFUL = _rx(r"konuniy (?:yol|ravishda|asos)|konun doirasida|legal(?:ly)?\b|lawful(?:ly)?\b|законн\w*|легальн\w*")
_LIABILITY = _rx(r"javobgar|jazo|jarima|nima bolad|ответствен|наказан|штраф|что будет|liabil|penalt|punish|what happens|"
                 r"shikoyat|murojaat|habar ber|kidirt|undir|ariza|жалоб|сообщить|заявлени|розыск|взыска|report|complain|sue\b")
# A bare request for help with no facts at all: ask for the situation instead of guessing a topic
_VAGUE_HELP = _rx(
    r"^\W*(?:iltimos\W+)?(?:menga\W+|bizga\W+|sizdan\W+)?(?:(?:yuridik|hukukiy)\W+)?(?:yordam|maslahat|konsultatsiya|komak)\w*"
    r"(?:\W+(?:bering\w*|ber|bera olasizmi|berasizmi|bera olasanmi|kerak\w*|kere|sorayman|surayman|zarur))?"
    r"(?:\W+iltimos)?\W*$|"
    r"^\W*(?:bir\W+)?savol(?:im|imiz)?\W+(?:bor|bor edi|bermokchi\w*|bersam\w*)\W*$|"
    r"^\W*(?:пожалуйста\W+)?(?:помогите|помоги|нужна помощь|нужна (?:юридическая )?консультация(?: юриста)?|"
    r"нужен (?:совет|юрист)|подскажите|у меня (?:есть )?вопрос|есть вопрос|вопрос к юристу)(?:\W+пожалуйста)?\W*$|"
    r"^\W*(?:please\W+)?(?:help(?: me)?(?: please)?|i need (?:some )?help|(?:can|could) you help(?: me)?|"
    r"i have a (?:legal )?question|i need (?:legal )?advice|need (?:legal )?advice)(?:\W+please)?\W*$"
)
_ILLEGAL = _rx(r"(?:solik\w*dan|aliment\w*dan|jarima\w*dan|javobgarlik\w*dan|harbiy hizmat\w*dan)~"
               r"(?:kochish|kochib kutul|kutulish|kutulsa|bosh tort\w*|kochsa) (?:mumkin|yoli|usul|bolad)|"
               r"(?:kanday kilib|kanday|kalay kilib|kanaka kilib|usul\w*)~(?:solik\w*dan koch|soliki?ni? (?:tolama|yashir)|"
               r"pora ber(?!ish uchun javob)|soht?a (?:hujjat|diplom|spravka|guvohnoma)|kalbaki|ogirla|aldab (?:pul|ol)|"
               r"izni? yashir|dalil\w*~yok kil|guvoh\w*~korkit|kochib ket\w*~javobgarlik|chegara\w*~nokonuniy|"
               r"jazodan kutul|militsiya\w*~aldab|narkotik\w*~(?:sot|olib otish)|giyohvand\w*~sot)|"
               r"как (?:уйти|уклониться) от (?:налог|ответственност|алимент)|как (?:дать|передать) взятку|"
               r"как (?:подделать|сделать поддельн)|как (?:не платить|скрыть) (?:налог|доход)|как украсть|"
               r"how (?:can i|do i|to) (?:avoid paying tax|evade tax|bribe|forge|fake (?:a )?document|launder|steal|"
               r"hide (?:income|assets) from)")
_TEMPLATE = _rx(r"namuna|shablon|obrazets|blank|kanday yoziladi|yozib ber|tuzib ber|образец|шаблон|бланк|как написать|"
                r"составь|напиши (?:заявлени|жалоб|иск)|template|sample (?:letter|claim|application)|draft (?:a|an|my)")
_CALC_VERB = _rx(r"hisobla|hisoblab ber|hisob-?kitob kil|kancha bo(?:la)?di|nechpul|kancha tolanadi|kancha chikadi|"
                 r"рассчита|посчита|сколько (?:будет|получится|составит|платить|положено)|calculat|how much (?:is|will|do)")
# Names of the figures themselves contain "calculation" words ("bazaviy hisoblash miqdori" = base calculation amount)
_FIGURE_NAMES = _rx(r"bazaviy hisoblash\w*(?: mikdor\w*)?|hisoblashning bazaviy|bazaviy mikdor\w*|"
                    r"базов\w* расч[её]тн\w* величин\w*|base calculation amount")
_QUANT = _rx(r"\bkancha\b|\bnecha\b|\bnechta\b|\bсколько\b|\bhow much\b|\bhow many\b")
_OFF_TOPIC = _rx(r"ob-?havo|pogoda|погод|weather|futbol|футбол|football|retsept|рецепт|recipe|kino|фильм|movie|"
                 r"anekdot|анекдот|joke|sher\b|стих|poem|kod yoz|напиши код|write (?:a )?code|matematika|математик|"
                 r"tarjima kil|переведи|translate this|valyuta kurs|курс доллара|exchange rate|bitkoin|bitcoin")
_LEGAL_HINT = _rx(r"konun|modda|kodeks|huku|sud|jarima|shartnoma|ariza|shikoyat|aliment|meros|soliq|solik|ish haki|"
                  r"закон|стать|кодекс|прав|суд|штраф|договор|иск|жалоб|налог|law|article|court|fine|contract|legal|right")

_TEMPLATE_KINDS = [
    ("lawsuit", r"davo ariza|sudga ariza|isk|исков|иск\b|lawsuit|claim"),
    ("alimony_claim", r"aliment|алимент|child support"),
    ("reinstatement_claim", r"ishga tiklash|восстановлени\w* на работ|reinstat"),
    ("resignation", r"ishdan bo?shash|ishdan ket|oz hohish|увольнени\w* по собствен|resign"),
    ("consumer_claim", r"pretenziya|istemolchi|dokon|sotuvchi|претензи|продавц|consumer|refund"),
    ("appeal_state_body", r"muroja+t|shikoyat|hokim|davlat organ|обращени|жалоб|complaint|petition"),
]

_CALC_TOPICS = {
    "alimony": _rx(r"aliment|алимент|child support"),
    "wage_delay": _rx(r"(?:oylik|maosh|ish haki|zarplat)\w*~(?:kechik|bermay|tolamay|kompensatsiya)|задерж\w*~зарплат|зарплат\w*~задерж|late (?:salary|wages)"),
    "tax_penalty": _rx(r"solik\w*~penya|penya\w*~solik|пен\w*~налог|tax penalt"),
    "severance": _rx(r"boshatish nafaka|ishdan boshat\w*~(?:nafaka|kompensatsiya)|выходн\w* пособи|severance"),
    "vacation_pay": _rx(r"tatil (?:puli|haki)|otpuskn|отпускн|holiday pay|vacation pay"),
    "state_duty": _rx(r"davlat boj|poshlin|госпошлин|state duty|court fee"),
    "income_tax": _rx(r"daromad solig|kolga (?:kancha|tegadi)|на руки|подоходн|ндфл|income tax|take-?home"),
    "deadline": _rx(r"muddat\w*~(?:kachon|tugaydi|tugashi|kancha kun)|kachongacha|срок\w*~(?:истека|когда|до какого)|deadline|until when"),
    "fine": _rx(r"\d+\s*(?:bhm|brv|брв)\b"),
}


@dataclass(slots=True)
class Route:
    kind: str
    calc: str | None = None
    template: str | None = None
    flags: set[str] = field(default_factory=set)

    @property
    def needs_retrieval(self) -> bool:
        return self.kind in ("legal", "illegal", "emergency", "calculation", "template", "figures")


def _views(query: str, language: str) -> list[str]:
    # Both views always: a Russian-looking Cyrillic text may be Uzbek ("сен кимсан?") and patterns exist in both forms
    return [fold_uz(query), fold_ru(query)]


class _V:
    """Several folded views of one question; a pattern matches when it matches any view."""

    def __init__(self, views: list[str]) -> None:
        self.views = views

    def search(self, rx: re.Pattern[str]) -> bool:
        return any(rx.search(v) for v in self.views)

    def replace(self, old: str, new: str) -> _V:
        return _V([v.replace(old, new) for v in self.views])

    def sub(self, rx: re.Pattern[str], new: str) -> _V:
        return _V([rx.sub(new, v) for v in self.views])


def classify(query: str, *, language: str, concepts: list[ConceptMatch] | None = None) -> Route:
    """Route one question (concepts from the situation lexicon sharpen the calculation decision)."""
    q = (query or "").strip()
    v = _V(_views(q, language))
    flags: set[str] = set()
    if v.search(_INJECTION):
        flags.add("injection")
    if not q:
        return Route("greeting", flags=flags)
    if v.search(_EMERGENCY) or v.search(_EMERGENCY_MORE):
        return Route("emergency", flags=flags)
    if v.search(_GREETING):
        return Route("greeting", flags=flags)
    if v.search(_THANKS):
        return Route("thanks", flags=flags)
    if v.search(_FAREWELL):
        return Route("farewell", flags=flags)
    if v.search(_ABOUT) and not v.replace("bot", "").search(_LEGAL_HINT):
        return Route("about", flags=flags)
    if v.search(_VAGUE_HELP):
        return Route("clarify", flags=flags)
    if v.search(_ILLEGAL) or (
        not v.search(_LIABILITY)
        and not v.search(_LAWFUL)
        and (
            (v.search(_ILLEGAL_ACT_WEAK) and (v.search(_HOW_STRONG) or v.search(_HOW_WEAK)))
            or (v.search(_ILLEGAL_ACT_STRONG) and v.search(_HOW_STRONG))
        )
    ):
        return Route("illegal", flags=flags)
    concepts = concepts or []
    if v.search(_CALC_TOPICS["fine"]):
        return Route("calculation", calc="fine", flags=flags)
    if any(m.concept.domain == "figures" for m in concepts[:1]) and not v.sub(_FIGURE_NAMES, " ").search(_CALC_VERB):
        return Route("figures", flags=flags)
    if v.search(_TEMPLATE):
        kind = next((k for k, p in _TEMPLATE_KINDS if v.search(_rx(p))), "appeal_state_body")
        return Route("template", template=kind, flags=flags)
    calc = _calc_kind(v, concepts)
    if calc:
        return Route("calculation", calc=calc, flags=flags)
    if v.search(_OFF_TOPIC) and not v.search(_LEGAL_HINT) and not concepts:
        return Route("off_topic", flags=flags)
    return Route("legal", flags=flags)


# Numbers that are references, not inputs: "161-modda", "статья 161", "ЎРҚ-782", "1-qism", years, dates
_REFERENCE_NUMBERS = re.compile(
    r"\d+(?:[.-]\d+)?\s*-?\s*(?:modda|moda|mod|qism|band|bob|son|модда|қисм|банд|боб|сон|стат|част|пункт|глав)\w*|"
    r"(?:modda|статья|стать[иеюя]|ст\.|article|art\.|qism|band|пункт|част[ьи])\s*\d+|"
    r"\b(?:o?r?q|zru|pf|pq|vmq|орқ|зру|пф|пқ|вмқ|зрк|ук|гк|тк|нк)\s*-?\s*\d+|"
    r"\b(?:19|20)\d{2}\s*-?\s*(?:yil|йил|год|г\.)?\w*|\d{1,2}[./-]\d{1,2}[./-]\d{2,4}"
)


def _has_input_number(v: _V) -> bool:
    return any(re.search(r"\d", _REFERENCE_NUMBERS.sub(" ", view)) for view in v.views)


def _calc_kind(v: _V, concepts: list[ConceptMatch]) -> str | None:
    has_number = _has_input_number(v)
    explicit = v.search(_CALC_VERB)
    quant = v.search(_QUANT)
    has_date = v.search(re.compile(r"\d{1,2}[./-]\d{1,2}[./-]\d{4}"))
    for kind, rx in _CALC_TOPICS.items():
        if kind == "fine" or not v.search(rx):
            continue
        if kind == "deadline" and not has_date:
            continue  # a deadline needs a start date; otherwise answer the rule itself
        if explicit or has_number or (quant and kind in ("state_duty", "income_tax")):
            return kind
    concept_calc = next((m.concept.calc for m in concepts[:2] if m.concept.calc), None)
    if concept_calc and concept_calc not in ("fine", "penalty", "pension", "alimony_debt") and (explicit or has_number):
        return concept_calc
    return None


def strip_injection(query: str, language: str = "uz_latn") -> str:
    """The question without sentences that address the assistant itself ("ignore previous instructions ...")."""
    parts = re.split(r"(?<=[.!?\n])\s+", query or "")
    keep = [p for p in parts if p.strip() and not _V(_views(p, language)).search(_INJECTION)
            and not _V(_views(p, language)).search(_PROMPT_LEAK)]
    return " ".join(keep).strip()
