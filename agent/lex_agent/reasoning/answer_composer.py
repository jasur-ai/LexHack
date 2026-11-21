"""Concise, scannable answer format shared by the LLM prompt, the extractive fallback and the API/UI.

Answers follow the "truncated pyramid" pattern recommended for chat UIs (NN/g, 2026): the direct answer first,
supporting rules with inline source numbers, optional next steps, one caution and suggested follow-ups —
instead of a long memo. Sections use fixed English markers so every client can parse them reliably:

    ### ANSWER / ### KEY POINTS / ### STEPS / ### CAUTION / ### FOLLOW-UPS
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any

from lex_agent.language.transliterator import latin_to_cyrillic
from lex_agent.models import Language, LegalBranch, RetrievedChunk

SECTION_MARKERS = ("ANSWER", "KEY POINTS", "STEPS", "CAUTION", "FOLLOW-UPS")

_SECTION_ALIASES: dict[str, str] = {
    "answer": "answer",
    "short answer": "answer",
    "javob": "answer",
    "qisqa javob": "answer",
    "жавоб": "answer",
    "ответ": "answer",
    "key points": "key_points",
    "asosiy qoidalar": "key_points",
    "asosiy nuqtalar": "key_points",
    "основные положения": "key_points",
    "steps": "steps",
    "next steps": "steps",
    "nima qilish kerak": "steps",
    "qadamlar": "steps",
    "что делать": "steps",
    "шаги": "steps",
    "caution": "caution",
    "diqqat": "caution",
    "важно": "caution",
    "внимание": "caution",
    "follow-ups": "follow_ups",
    "follow ups": "follow_ups",
    "followups": "follow_ups",
    "savollar": "follow_ups",
    "вопросы": "follow_ups",
}

LANGUAGE_NAMES: dict[Language, str] = {
    Language.UZ_LATN: "Uzbek in Latin script (Oʻzbek lotin yozuvi)",
    Language.UZ_CYRL: "Uzbek in Cyrillic script (Ўзбек кирилл ёзуви)",
    Language.RU: "Russian",
    Language.EN: "English",
}


def short_act_title(chunk: Any) -> str:
    extra = getattr(chunk, "extra", None) or {}
    title = extra.get("short_title") or getattr(chunk, "doc_title", "") or ""
    return str(title).strip()


def citation_label(chunk: Any) -> str:
    title = short_act_title(chunk)
    art = getattr(chunk, "article", None)
    return f"{title}, {art}" if art else title


def article_body(chunk: Any, *, prefer_lead: bool = False) -> str:
    """Article text without the synthetic header line added at indexing time."""
    extra = getattr(chunk, "extra", None) or {}
    if prefer_lead and extra.get("lead_text"):
        return str(extra["lead_text"]).strip()
    text = str(getattr(chunk, "text", "") or "")
    first, sep, rest = text.partition("\n")
    if sep and rest.strip() and (" · " in first or first.strip() == short_act_title(chunk)):
        return rest.strip()
    return text.strip()


def lead_excerpt(text: str, limit: int = 320) -> str:
    """First complete sentences of a norm, cut on a sentence boundary."""
    clean = re.sub(r"\s+", " ", text).strip()
    if len(clean) <= limit:
        return clean
    cut = -1
    # A colon introduces a list or examples, so stopping there leaves a dangling quote; cut mid-sentence with "…".
    for m in re.finditer(r"[.;!?](?=\s)", clean[: limit + 1]):
        cut = m.end()
    if cut < limit // 3:
        cut = clean.rfind(" ", 0, limit)
        return clean[: cut if cut > 0 else limit].rstrip(",;: ") + "…"
    return clean[:cut].strip()


# --------------------------------------------------------------------------------------------- prompt


def build_concise_messages(
    *,
    query: str,
    response_lang: Language,
    evidence: list[RetrievedChunk],
    warnings: list[str],
    as_of_date: date | None,
    context: str | None = None,
) -> list[dict[str, str]]:
    """Single, compact prompt optimised for time-to-first-token and short, verifiable answers."""
    blocks: list[str] = []
    for idx, item in enumerate(evidence, start=1):
        c = item.chunk
        header = citation_label(c)
        if c.article_title:
            header += f" — {c.article_title}"
        status = c.status.value.replace("_", " ")
        blocks.append(f"[{idx}] {header} ({status})\n{article_body(c)[:900]}")
    evidence_text = "\n\n".join(blocks) if blocks else "(no evidence found)"

    system = (
        "You are Haqli, a legal assistant for people in the Republic of Uzbekistan. Answer ONLY from the numbered "
        "EVIDENCE excerpts (official legal texts).\n"
        f"Write in {LANGUAGE_NAMES[response_lang]}, in plain friendly words for a non-lawyer. "
        "No greetings, no filler, no generic disclaimers.\n"
        "Output exactly these sections, keeping the English markers verbatim (never translate the markers):\n"
        "### ANSWER\n"
        "1-3 short sentences that directly answer the question (start with yes/no when it applies) and include the "
        "key number, term or deadline when the evidence has it.\n"
        "### KEY POINTS\n"
        "2-4 bullets '- ...', each at most 25 words, naming the act and article (e.g. 'Mehnat kodeksi, 161-modda') "
        "and ending with the evidence number(s) in square brackets, e.g. [1] or [1][3].\n"
        "### STEPS\n"
        "1-4 numbered practical next steps '1. ...' only if the person needs to act; otherwise omit the section.\n"
        "### CAUTION\n"
        "One sentence about an important exception, deadline or when to consult a lawyer; omit if not needed.\n"
        "### FOLLOW-UPS\n"
        "2-3 short follow-up questions (max 8 words each) as '- ...' bullets.\n"
        "Rules: never invent article numbers, amounts, deadlines, act numbers or links that are not in the EVIDENCE. "
        "Ignore excerpts unrelated to the question. If the evidence does not answer the question, say so in one "
        "sentence in ANSWER and say what detail is missing. Keep everything except FOLLOW-UPS under 170 words."
    )
    user = (
        (f"PREVIOUS QUESTION (context for this follow-up): {context.strip()}\n" if context else "")
        + f"QUESTION: {query.strip()}\n"
        f"DATE: {(as_of_date or date.today()).isoformat()}\n"
        + (f"WARNINGS: {' | '.join(warnings[:4])}\n" if warnings else "")
        + f"\nEVIDENCE:\n{evidence_text}"
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


# --------------------------------------------------------------------------------------------- parsing


def parse_answer_sections(text: str) -> dict[str, Any]:
    """Parse the fixed-marker answer format; tolerant to translated headings and missing sections."""
    sections: dict[str, list[str]] = {}
    current = "answer"
    found_marker = False
    for raw_line in (text or "").splitlines():
        line = raw_line.rstrip()
        m = re.match(r"^\s*(?:#{1,4}\s*|\*\*)\s*([^#*:]{3,40}?)\s*:?\s*(?:\*\*)?\s*:?\s*$", line)
        if m:
            key = _SECTION_ALIASES.get(m.group(1).strip().lower())
            if key:
                current = key
                found_marker = True
                sections.setdefault(current, [])
                continue
        sections.setdefault(current, []).append(line)

    def _bullets(lines: list[str]) -> list[str]:
        items: list[str] = []
        for ln in lines:
            s = ln.strip()
            if not s:
                continue
            m2 = re.match(r"^(?:[-*•]|\d+[.)])\s+(.*)$", s)
            if m2:
                items.append(m2.group(1).strip())
            elif items:
                items[-1] = f"{items[-1]} {s}"
            else:
                items.append(s)
        return [i for i in items if i]

    def _para(lines: list[str]) -> str:
        return re.sub(r"\n{3,}", "\n\n", "\n".join(lines).strip())

    answer = _para(sections.get("answer", []))
    return {
        "structured": found_marker,
        "answer": answer,
        "key_points": _bullets(sections.get("key_points", [])),
        "steps": _bullets(sections.get("steps", [])),
        "caution": _para(sections.get("caution", [])),
        "follow_ups": [f.rstrip("?") + "?" for f in _bullets(sections.get("follow_ups", []))][:3],
    }


def render_sections(sections: dict[str, Any]) -> str:
    """Serialize sections back to the canonical marker format."""
    out: list[str] = ["### ANSWER", sections.get("answer", "").strip()]
    if sections.get("key_points"):
        out += ["", "### KEY POINTS", *[f"- {p}" for p in sections["key_points"]]]
    if sections.get("steps"):
        out += ["", "### STEPS", *[f"{i}. {s}" for i, s in enumerate(sections["steps"], start=1)]]
    if sections.get("caution"):
        out += ["", "### CAUTION", sections["caution"].strip()]
    if sections.get("follow_ups"):
        out += ["", "### FOLLOW-UPS", *[f"- {q}" for q in sections["follow_ups"]]]
    return "\n".join(out).strip()


# --------------------------------------------------------------------------------------------- extractive

_TEMPLATES: dict[Language, dict[str, str]] = {
    Language.UZ_LATN: {
        "lead": "{label} boʻyicha: “{quote}”",
        "lead_title": "Bu masala {label} («{title}») bilan tartibga solinadi: “{quote}”",
        "none": "Bu savol boʻyicha qonunchilik bazasidan aniq norma topilmadi. Savolni aniqroq yozing: kim, qachon, "
        "qanday hujjat yoki summa haqida gap ketmoqda?",
        "caution": "Bu javob qonun matnidan avtomatik ajratib olindi. Muhim qaror qabul qilishdan oldin toʻliq "
        "matnni oʻqing yoki advokat bilan maslahatlashing.",
    },
    Language.UZ_CYRL: {
        "lead": "{label} бўйича: “{quote}”",
        "lead_title": "Бу масала {label} («{title}») билан тартибга солинади: “{quote}”",
        "none": "Бу савол бўйича қонунчилик базасидан аниқ норма топилмади. Саволни аниқроқ ёзинг: ким, қачон, "
        "қандай ҳужжат ёки сумма ҳақида гап кетмоқда?",
        "caution": "Бу жавоб қонун матнидан автоматик ажратиб олинди. Муҳим қарор қабул қилишдан олдин тўлиқ "
        "матнни ўқинг ёки адвокат билан маслаҳатлашинг.",
    },
    Language.RU: {
        "lead": "Согласно норме «{label}»: “{quote}”",
        "lead_title": "Этот вопрос регулирует {label} («{title}»): “{quote}”",
        "none": "В базе законодательства не найдена точная норма по этому вопросу. Уточните: кто, когда, о каком "
        "документе или сумме идёт речь?",
        "caution": "Ответ автоматически составлен из текста закона. Перед важным решением прочитайте норму "
        "полностью или проконсультируйтесь с юристом.",
    },
    Language.EN: {
        "lead": "According to {label}: “{quote}”",
        "lead_title": "This is governed by {label} (“{title}”): “{quote}”",
        "none": "No specific legal norm was found for this question. Please clarify who, when, and which document or "
        "amount is involved.",
        "caution": "This answer was extracted automatically from the legal text. Read the full norm or consult a "
        "lawyer before making an important decision.",
    },
}

_FOLLOW_UPS: dict[Language, dict[str, list[str]]] = {
    Language.UZ_LATN: {
        LegalBranch.LABOR.value: ["Qanday kompensatsiya olishim mumkin?", "Qayerga shikoyat qilsam boʻladi?"],
        LegalBranch.FAMILY.value: ["Sudga qanday hujjatlar kerak?", "Bu jarayon qancha vaqt oladi?"],
        LegalBranch.CIVIL.value: ["Talabnoma qanday yoziladi?", "Sudga murojaat muddati qancha?"],
        LegalBranch.CRIMINAL.value: ["Qanday jazo choralari bor?", "Jabrlanuvchi qayerga murojaat qiladi?"],
        LegalBranch.ADMINISTRATIVE.value: ["Jarima qancha boʻladi?", "Qarorni qanday shikoyat qilaman?"],
        "default": ["Qanday hujjatlar kerak?", "Muddatlar qanday?"],
    },
    Language.UZ_CYRL: {
        LegalBranch.LABOR.value: ["Қандай компенсация олишим мумкин?", "Қаерга шикоят қилсам бўлади?"],
        LegalBranch.FAMILY.value: ["Судга қандай ҳужжатлар керак?", "Бу жараён қанча вақт олади?"],
        LegalBranch.CIVIL.value: ["Талабнома қандай ёзилади?", "Судга мурожаат муддати қанча?"],
        LegalBranch.CRIMINAL.value: ["Қандай жазо чоралари бор?", "Жабрланувчи қаерга мурожаат қилади?"],
        LegalBranch.ADMINISTRATIVE.value: ["Жарима қанча бўлади?", "Қарорни қандай шикоят қиламан?"],
        "default": ["Қандай ҳужжатлар керак?", "Муддатлар қандай?"],
    },
    Language.RU: {
        LegalBranch.LABOR.value: ["Какую компенсацию я могу получить?", "Куда можно пожаловаться?"],
        LegalBranch.FAMILY.value: ["Какие документы нужны для суда?", "Сколько длится процесс?"],
        LegalBranch.CIVIL.value: ["Как составить претензию?", "Какой срок обращения в суд?"],
        LegalBranch.CRIMINAL.value: ["Какое предусмотрено наказание?", "Куда обратиться потерпевшему?"],
        LegalBranch.ADMINISTRATIVE.value: ["Какой будет штраф?", "Как обжаловать постановление?"],
        "default": ["Какие документы нужны?", "Какие сроки?"],
    },
    Language.EN: {
        "default": ["Which documents do I need?", "What are the deadlines?"],
    },
}


def _localize_quote(text: str, chunk_lang: Language, response_lang: Language) -> str:
    if response_lang == Language.UZ_CYRL and chunk_lang == Language.UZ_LATN:
        return latin_to_cyrillic(text)
    return text


def compose_extractive_answer(
    *,
    query: str,
    response_lang: Language,
    evidence: list[RetrievedChunk],
    branches: list[LegalBranch] | None = None,
) -> str:
    """Deterministic, citation-backed answer used when no LLM is configured or the LLM fails/times out."""
    tpl = _TEMPLATES.get(response_lang, _TEMPLATES[Language.UZ_LATN])
    lang_key = response_lang if response_lang in _FOLLOW_UPS else Language.UZ_LATN
    branch_values = [b.value for b in (branches or [])]
    if evidence:
        branch_values = branch_values or [b.value for b in evidence[0].chunk.branches]
    follow_pool = _FOLLOW_UPS[lang_key]
    follow_ups = next((follow_pool[b] for b in branch_values if b in follow_pool), follow_pool["default"])

    if not evidence:
        return render_sections({"answer": tpl["none"], "follow_ups": follow_ups})

    top = evidence[0].chunk
    quote = _localize_quote(lead_excerpt(article_body(top, prefer_lead=True), 340), top.language, response_lang)
    label = citation_label(top)
    if top.article_title and len(top.article_title) < 110:
        title = _localize_quote(top.article_title, top.language, response_lang)
        answer = tpl["lead_title"].format(label=label, title=title, quote=quote) + " [1]"
    else:
        answer = tpl["lead"].format(label=label, quote=quote) + " [1]"

    key_points: list[str] = []
    top_score = max(evidence[0].final_score, 1e-9)
    for idx, item in enumerate(evidence[1:4], start=2):
        if item.final_score < 0.55 * top_score:
            continue  # keep the card focused: skip weakly related norms
        c = item.chunk
        snippet = _localize_quote(lead_excerpt(article_body(c, prefer_lead=True), 190), c.language, response_lang)
        key_points.append(f"{citation_label(c)}: {snippet} [{idx}]")

    return render_sections(
        {
            "answer": answer,
            "key_points": key_points,
            "caution": tpl["caution"],
            "follow_ups": follow_ups,
        }
    )


def source_items(evidence: list[RetrievedChunk]) -> list[dict[str, Any]]:
    """Numbered sources for the UI (number = index used in [n] citations)."""
    items: list[dict[str, Any]] = []
    for idx, item in enumerate(evidence, start=1):
        c = item.chunk
        extra = c.extra or {}
        items.append(
            {
                "n": idx,
                "doc_id": c.doc_id,
                "title": short_act_title(c),
                "full_title": c.doc_title,
                "article": c.article,
                "article_title": c.article_title,
                "excerpt": lead_excerpt(article_body(c), 700),
                "lead": lead_excerpt(article_body(c, prefer_lead=True), 300) if extra.get("lead_text") else None,
                "url": c.citation_url,
                "language": c.language.value,
                "status": c.status.value,
                "source": extra.get("source") or "lex.uz",
                "snapshot": extra.get("snapshot"),
                "doc_type": c.doc_type.value,
            }
        )
    return items
