"""Question routing: decide what kind of turn this is before spending time on retrieval.

Kinds: ``greeting``, ``thanks``, ``farewell``, ``about`` (who are you / what can you do / requests for the system
prompt), ``off_topic``, ``emergency`` (immediate danger: violence, suicide, abduction), ``illegal`` (asks how to
break the law or evade liability), ``template`` (document samples), ``calculation``, ``figures`` (BHM, minimum
wage, CB rate) and ``legal`` (everything else). Prompt-injection attempts are flagged (``injection``) and simply
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


def classify(query: str, *, language: str, concepts: list[ConceptMatch] | None = None) -> Route:
    """Route one question (concepts from the situation lexicon sharpen the calculation decision)."""
    q = (query or "").strip()
    v = _V(_views(q, language))
    flags: set[str] = set()
    if v.search(_INJECTION):
        flags.add("injection")
    if not q:
        return Route("greeting", flags=flags)
    if v.search(_EMERGENCY):
        return Route("emergency", flags=flags)
    if v.search(_GREETING):
        return Route("greeting", flags=flags)
    if v.search(_THANKS):
        return Route("thanks", flags=flags)
    if v.search(_FAREWELL):
        return Route("farewell", flags=flags)
    if v.search(_ABOUT) and not v.replace("bot", "").search(_LEGAL_HINT):
        return Route("about", flags=flags)
    if v.search(_ILLEGAL):
        return Route("illegal", flags=flags)
    concepts = concepts or []
    if v.search(_CALC_TOPICS["fine"]):
        return Route("calculation", calc="fine", flags=flags)
    if any(m.concept.domain == "figures" for m in concepts[:1]) and not v.search(_CALC_VERB):
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
