"""Question-type-aware extractive answers (no LLM needed).

Instead of quoting the start of the top article, the answer picks the *sentence that answers the question*:
for "how much / how long / when" questions sentences with amounts and periods win, for yes/no questions the
sentence that states the rule, and every quote is shown in the reader's script. Fines stated in BHM multiples
are converted to soʻm with the current BHM; matched situations add practical steps, a caution with the key
deadline and topic-specific follow-up questions.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from lex_agent.assistant import replies
from lex_agent.assistant.act_names import en_article, en_title
from lex_agent.assistant.calculators import _rub, fines_in_text, som
from lex_agent.assistant.playbooks import Playbook
from lex_agent.chunk_text import article_body, chunk_article_id, display_text, short_act_title
from lex_agent.knowledge.facts import FACTS_DOC_ID, FactsPack
from lex_agent.language.textproc import index_terms
from lex_agent.models import Language, RetrievedChunk

_NUMBERISH = re.compile(
    r"\d|\b(?:bir|ikki|uch|tort|toʻrt|to'rt|besh|olti|yetti|sakkiz|toʻqqiz|to'qqiz|oʻn|o'n|yigirma|oʻttiz|o'ttiz|qirq|ellik|"
    r"yuz|ming|foiz|baravar\w*|kun\w*|oy\w*|yil\w*|hafta\w*|soat\w*|"
    r"один|два|три|четыр|пят|шест|сем|восем|девят|десят|двадцат|тридцат|сорок|пятьдесят|сто|процент\w*|дн\w*|день|"
    r"месяц\w*|год\w*|лет|недел\w*|час\w*)\b",
    re.I,
)
_QTYPES = {
    "amount": re.compile(r"\bqancha\b|\bnecha pul\b|miqdor|stavka|foiz|сколько|размер|ставк|how much|amount|rate", re.I),
    "duration": re.compile(r"necha kun|necha oy|necha yil|qancha muddat|muddat|qachon|qachongacha|necha soat|"
                           r"сколько дней|срок|когда|до какого|how long|when|deadline|how many days", re.I),
    "yesno": re.compile(r"mumkinmi|shartmi|kerakmi|bo'?ladimi|boʻladimi|haqqi bormi|qonuniymi|majburmi|bormi\b|"
                        r"\w+(?:adimi|aydimi|manmi|ladimi|sami)\b|"
                        r"мумкинми|шартми|керакми|бўладими|борми\b|қонунийми|мажбурми|\w+(?:адими|айдими|манми)\b|"
                        r"можно ли|обязан|нужно ли|законно|вправе|\bли\b|\bli\b|"
                        r"^(?:is|can|do|does|must|should|may|am|are)\b", re.I),
    "action": re.compile(r"nima qil|qayerga|qanday qilib|qanday|что делать|куда|как |how (?:do|can|to)|what (?:can|should)", re.I),
}
_SENT_SPLIT = re.compile(r"(?<=[.;!?])\s+|\n+")
_LIST_ITEM = re.compile(r"^\s*(?:\d+\\?\)|[a-zа-я]\)|[-–•])\s*")


# "Can / may / is it allowed ...?" — the only yes/no form a lead's polarity answers. Questions about a duty or a ban
# ("Is consent required?", "Is it forbidden?") or negated ones invert the meaning, so they get no Yes/No prefix.
_PERMISSION_Q = re.compile(
    r"mumkinmi|bo'?ladimi|boʻladimi|\w+(?:adimi|ydimi)\b|ruxsat (?:bormi|etiladimi|beriladimi)|haqqi?m? bormi|"
    r"мумкинми|бўладими|\w+(?:адими|йдими)\b|можно ли|мо(?:жет|гут|жно)\b.*\?|вправе ли|имеет ли право|"
    r"разрешен\w* ли|^\s*\w+ ли\b|"
    r"^(?:can|may|could)\b|\bis it (?:legal|allowed|possible|ok(?:ay)?)\b|\bam i allowed\b|\bdoes (?:a|an|the|my)\b",
    re.I,
)
_DUTY_OR_NEGATION_Q = re.compile(
    r"shartmi|kerakmi|majburmi|taqiqlan\w*mi|emasmi|шартми|керакми|мажбурми|обязан|нужно ли|надо ли|запрещ|"
    r"не (?:мож|могут|вправе|имеет)|\b(?:required|must|need|have to|forbidden|prohibited|illegal|not allowed|"
    r"can'?t|cannot)\b",
    re.I,
)
_PROPER_START = re.compile(r"^(?:Oʻzbek|O'zbek|Ўзбек|Узбек|Uzbek|Markaziy|Центральн|Central|Konstitutsiya|Конституц)")


def asks_permission(query: str) -> bool:
    q = (query or "").strip()
    return bool(_PERMISSION_Q.search(q)) and not _DUTY_OR_NEGATION_Q.search(q)


def _lower_first(text: str) -> str:
    if not text or _PROPER_START.match(text) or (len(text) > 1 and text[1].isupper()):
        return text
    return text[:1].lower() + text[1:]


def question_type(query: str) -> str:
    q = query.lower()
    for name in ("duration", "amount", "yesno", "action"):
        if _QTYPES[name].search(q):
            return name
    return "general"


@dataclass(slots=True)
class Pick:
    sentence: str
    score: float
    item_index: int


@dataclass(slots=True)
class SynthesisInput:
    query: str
    lang: Language
    evidence: list[RetrievedChunk]
    terms: list[str] = field(default_factory=list)
    expansion_terms: set[str] = field(default_factory=set)
    concept_ids: list[str] = field(default_factory=list)
    follow_ups: list[str] = field(default_factory=list)
    playbook: Playbook | None = None
    calc_hint: str | None = None
    lead: dict[str, str] | None = None  # verified one-sentence answer for the situation (uz/ru/en)
    lead_refs: list[int] = field(default_factory=list)  # 1-based evidence numbers that state the lead
    full_text: Callable[[RetrievedChunk], str] | None = None  # whole article text (all parts of a long article)


def _sentences(text: str) -> list[str]:
    """Sentences of an article; a line ending with ',' ':' or a dash is joined with the next one, so the
    disposition of an offence ("Exceeding the speed limit by up to 20 km/h,") keeps its sanction ("— a fine of
    one BHM")."""
    parts = [re.sub(r"\s+", " ", raw).strip() for raw in _SENT_SPLIT.split(text)]
    merged: list[str] = []
    for part in parts:
        if not part:
            continue
        if merged and (merged[-1].endswith((",", "—", "-", "–")) or part.startswith(("—", "–", "-"))) \
                and len(merged[-1]) + len(part) < 520:
            merged[-1] = f"{merged[-1]} {part}"
        else:
            merged.append(part)
    out: list[str] = []
    for s in merged:
        s = s.strip(" —-")
        if 25 <= len(s) <= 520:
            out.append(s)
    return out


def best_sentence(
    item: RetrievedChunk,
    terms: set[str],
    qtype: str,
    expansion: set[str],
    *,
    body: str | None = None,
) -> Pick | None:
    """The sentence of the article that best answers the question (query terms weigh 1, expansions 0.5)."""
    c = item.chunk
    body = body if body is not None else article_body(c, prefer_lead=False)
    compact = re.sub(r"\s+", " ", body).strip()
    if 25 <= len(compact) <= 260 and not _LIST_ITEM.search(body):
        # A short article is quoted whole ("Umumiy daʼvo muddati — uch yil.")
        return Pick(sentence=compact, score=1.0, item_index=0)
    sentences = _sentences(body)[:60]
    if c.canonical_id == FACTS_DOC_ID:
        # A figures card starts with its own name; only the dated values answer anything
        sentences = [x for x in sentences if re.search(r"\d", x)] or sentences
    best: Pick | None = None
    for pos, s in enumerate(sentences):
        sterms = set(index_terms(s, language=c.language.value))
        overlap = len(sterms & terms) + 0.5 * len(sterms - terms & expansion)
        # Length-normalised (BM25-style): a long sentence matches many words by chance
        score = overlap / (0.6 + 0.4 * len(s) / 150) - 0.03 * pos
        if pos == 0:
            score += 0.4  # the first sentence usually states the article's main rule
        if qtype in ("amount", "duration") and _NUMBERISH.search(_latin(s, c.language)):
            score += 1.2
        if qtype == "yesno" and re.search(r"\b(?:mumkin|shart|haqli|majbur|taqiqlan|yoʻl qoʻyilmaydi|мумкин|шарт|ҳақли|"
                                          r"вправе|обязан|запрещ|не допуска|может|не может)\w*", s, re.I):
            score += 0.8
        if _LIST_ITEM.match(s):
            score -= 0.4
        if s.endswith(":"):
            score -= 1.5  # an introduction to a list says nothing by itself
        if best is None or score > best.score:
            best = Pick(sentence=s, score=score, item_index=0)
    return best


def _latin(text: str, lang: Language) -> str:
    if lang != Language.UZ_CYRL:
        return text
    from lex_agent.language.transliterator import cyrillic_to_latin

    return cyrillic_to_latin(text)


def _clip(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 1].rsplit(" ", 1)[0].rstrip(",;:—-") + "…"


def _display(text: str, chunk_lang: Language, lang: Language) -> str:
    return display_text(text, chunk_lang, lang)


def label_for(item: RetrievedChunk, lang: Language) -> str:
    """'Mehnat kodeksi, 217-modda' in the reader's script ('Labour Code, art. 217' for English)."""
    return _label(item, lang)


def _label(item: RetrievedChunk, lang: Language) -> str:
    c = item.chunk
    if c.canonical_id == FACTS_DOC_ID:
        return str(c.article or c.article_title or c.doc_title)
    if lang == Language.EN and en_title(c.canonical_id):
        art = en_article(c.article)
        return f"{en_title(c.canonical_id)}, {art}" if art else str(en_title(c.canonical_id))
    title = _display(short_act_title(c), c.language, lang)
    art = c.article or ""
    if art:
        art = _display(art, c.language, lang)
        return f"{title}, {art}"
    return title


def compose(inp: SynthesisInput, facts: FactsPack | None = None) -> dict[str, Any]:
    """Sections dict for an extractive answer."""
    lang = inp.lang
    lk = replies.lang_key(lang)
    if not inp.evidence:
        return {
            "answer": replies.text("not_found", lang),
            "key_points": [],
            "steps": list(replies.text("not_found_steps", lang)),
            "caution": "",
            "follow_ups": list(inp.follow_ups or replies.EXAMPLES.get(lk, replies.EXAMPLES["uz"]))[:3],
        }
    qtype = question_type(inp.query)
    terms = set(inp.terms)
    top = inp.evidence[0]
    def _body(item: RetrievedChunk) -> str | None:
        if inp.full_text is None:
            return None
        try:
            return inp.full_text(item)
        except Exception:  # pragma: no cover - defensive
            return None

    pick = best_sentence(top, terms, qtype, inp.expansion_terms, body=_body(top))
    quote = _clip(_display(pick.sentence if pick else article_body(top.chunk)[:300], top.chunk.language, lang), 420)
    label = _label(top, lang)
    intro = {
        "uz": {"yesno": "Qonunga koʻra", "default": "{label}"},
        "uz_cyrl": {"yesno": "Қонунга кўра", "default": "{label}"},
        "ru": {"yesno": "По закону", "default": "{label}"},
        "en": {"yesno": "Under the law", "default": "{label}"},
    }[lk]
    if qtype == "yesno":
        answer = f"{intro['yesno']} ({label}): «{quote}» [1]"
    elif lk == "en" and top.chunk.language != Language.EN:
        src = "Russian" if top.chunk.language == Language.RU else "Uzbek"
        answer = f"{label} (official text in {src}): «{quote}» [1]"
    else:
        answer = f"{label}: «{quote}» [1]"

    key_points: list[str] = []
    polarity = (inp.lead or {}).get("polarity")
    use_lead = bool(inp.lead and inp.lead_refs) and qtype in ("action", "general", "amount", "duration", "yesno")
    used: set[int] = {1}
    if use_lead and inp.lead:
        text_lead = inp.lead.get("ru" if lk == "ru" else "en" if lk == "en" else "uz", "")
        if qtype == "yesno" and polarity and asks_permission(inp.query):
            word = {"yes": {"uz": "Ha", "ru": "Да", "en": "Yes"}, "no": {"uz": "Yoʻq", "ru": "Нет", "en": "No"}}[polarity]
            text_lead = f"{word['ru' if lk == 'ru' else 'en' if lk == 'en' else 'uz']} — {_lower_first(text_lead)}"
        if lk == "uz_cyrl":
            from lex_agent.language.transliterator import latin_to_cyrillic

            text_lead = latin_to_cyrillic(text_lead)
        refs = " ".join(f"[{n}]" for n in inp.lead_refs)
        answer = f"{text_lead} {refs}"
        # Quote the articles that state the lead: the sentence closest to the lead's own words
        lead_terms = set(index_terms(inp.lead.get("ru", ""), language="ru")) | set(
            index_terms(inp.lead.get("uz", ""), language="uz_latn")
        )
        used = set()
        for n in inp.lead_refs[:2]:
            item = inp.evidence[n - 1]
            p = best_sentence(item, terms, qtype, inp.expansion_terms | lead_terms, body=_body(item))
            if p:
                q = _clip(_display(p.sentence, item.chunk.language, lang), 300)
                key_points.append(f"{_label(item, lang)}: «{q}» [{n}]")
                used.add(n)
    fine_lines = _fine_lines(top, lang, facts)
    key_points.extend(fine_lines)
    top_score = max(top.final_score, 1e-9)
    shown = used if use_lead else {1}
    seen_articles = {(inp.evidence[n - 1].chunk.canonical_id, chunk_article_id(inp.evidence[n - 1].chunk)) for n in shown}
    for idx, item in enumerate(inp.evidence[:5], start=1):
        if idx in used or (idx == 1 and not use_lead):
            continue
        if len(key_points) >= 3:
            break
        key = (item.chunk.canonical_id, chunk_article_id(item.chunk))
        if key in seen_articles:
            continue
        if top.final_score > 0 and item.final_score < 0.35 * top_score:
            continue
        seen_articles.add(key)
        p = best_sentence(item, terms, qtype, inp.expansion_terms, body=_body(item))
        snippet = _clip(_display(p.sentence if p else article_body(item.chunk)[:200], item.chunk.language, lang), 230)
        if lk == "en" and item.chunk.language != Language.EN:
            snippet = f"«{snippet}»"  # statute wording in another language is always shown as a quote
        key_points.append(f"{_label(item, lang)}: {snippet} [{idx}]")

    steps: list[str] = []
    caution = ""
    if inp.playbook:
        steps = list(inp.playbook.steps.get("ru" if lk == "ru" else "en" if lk == "en" else "uz", ()))
        caution = inp.playbook.caution.get("ru" if lk == "ru" else "en" if lk == "en" else "uz", "")
        if lk == "uz_cyrl":
            from lex_agent.language.transliterator import latin_to_cyrillic

            steps = [latin_to_cyrillic(s) for s in steps]
            caution = latin_to_cyrillic(caution) if caution else ""
    if not caution:
        caution = replies.text("ai_caution", lang)
    follow = list(inp.follow_ups)
    if inp.calc_hint:
        follow = [inp.calc_hint, *follow]
    if not follow:
        follow = list(replies.EXAMPLES.get(lk, replies.EXAMPLES["uz"]))
    return {"answer": answer, "key_points": key_points, "steps": steps[:4], "caution": caution, "follow_ups": follow[:3]}


def _fine_lines(item: RetrievedChunk, lang: Language, facts: FactsPack | None) -> list[str]:
    """'BHMning besh baravari' in an offence article -> the amount in soʻm with the current BHM."""
    if facts is None:
        return []
    multiples = fines_in_text(article_body(item.chunk))
    if not multiples:
        return []
    sv = facts.current("bhm")
    if not sv:
        return []
    bhm = sv.value
    lk = replies.lang_key(lang)
    fmt = _rub if lk == "ru" else (lambda v: som(v).replace("soʻm", "сўм")) if lk == "uz_cyrl" else som
    unit = {"ru": "БРВ", "uz_cyrl": "БҲМ"}.get(lk, "BHM")
    parts: list[str] = []
    for low, high in multiples[:4]:
        if high:
            parts.append(f"{low:g}–{high:g} {unit} = {fmt(low * bhm)} – {fmt(high * bhm)}")
        else:
            parts.append(f"{low:g} {unit} = {fmt(low * bhm)}")
    since = f"{sv.start:%d.%m.%Y}" if sv.start else ""
    head = {
        "uz": f"Jarima soʻmda (1 BHM = {som(bhm)}, {since} dan)",
        "uz_cyrl": f"Жарима сўмда (1 БҲМ = {fmt(bhm)}, {since} дан)",
        "ru": f"Штраф в сумах (1 БРВ = {_rub(bhm)}, с {since})",
        "en": f"Fine in soʻm (1 BHM = {som(bhm)}, since {since})",
    }[lk]
    return [f"{head}: " + "; ".join(parts) + " [1]"]
