"""Helpers that turn stored legal chunks into display text (shared by retrieval, answers and the API).

Chunks keep the official text in its original script. Uzbek acts from LawCodex are stored in Cyrillic (as
published on lex.uz), the older open corpus in Latin; both scripts are official. ``display_text`` converts
any Uzbek text to the script the person wrote in, so a Latin-script question gets a Latin-script quote.
"""

from __future__ import annotations

import re
from typing import Any

from lex_agent.language.transliterator import cyrillic_to_latin, latin_to_cyrillic
from lex_agent.models import Language, LegalChunk

_DEFINITION_TITLE_RE = re.compile(
    r"asosiy tushuncha|asosiy atama|tushunchalar|atamalar|асосий тушунча|тушунчалар|атамалар|основные понятия|"
    r"основные термины|понятия|термины",
    re.I,
)


def short_act_title(chunk: Any) -> str:
    extra = getattr(chunk, "extra", None) or {}
    title = extra.get("short_title") or getattr(chunk, "doc_title", "") or ""
    return str(title).strip()


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


def is_uzbek(language: Language | str) -> bool:
    value = language.value if isinstance(language, Language) else str(language)
    return value in (Language.UZ_LATN.value, Language.UZ_CYRL.value)


def display_text(text: str, source_lang: Language | str, target_lang: Language | str) -> str:
    """Convert Uzbek text between Latin and Cyrillic to match the reader's script (other languages unchanged)."""
    if not text:
        return text
    src = source_lang.value if isinstance(source_lang, Language) else str(source_lang)
    dst = target_lang.value if isinstance(target_lang, Language) else str(target_lang)
    if src == Language.UZ_CYRL.value and dst in (Language.UZ_LATN.value, Language.EN.value):
        return _pretty_latin(cyrillic_to_latin(text))
    if src == Language.UZ_LATN.value and dst == Language.UZ_CYRL.value:
        return latin_to_cyrillic(text)
    return text


def _pretty_latin(text: str) -> str:
    """Typographic Uzbek Latin: oʻ / gʻ with the turned comma and ʼ for the tutuq belgisi (as on lex.uz)."""
    text = re.sub(r"([OoGg])'", lambda m: m.group(1) + "ʻ", text)
    return re.sub(r"(?<=[A-Za-z])'(?=[A-Za-z])", "ʼ", text)


def chunk_display_language(chunk: Any, target_lang: Language) -> Language:
    """Script the chunk will be shown in for a reader of ``target_lang``."""
    lang = getattr(chunk, "language", Language.UZ_LATN)
    if is_uzbek(lang) and target_lang in (Language.UZ_LATN, Language.UZ_CYRL):
        return target_lang
    if lang == Language.UZ_CYRL and target_lang == Language.EN:
        return Language.UZ_LATN
    return lang


def is_definitions_article(chunk: Any) -> bool:
    title = str(getattr(chunk, "article_title", "") or "")
    return bool(title) and bool(_DEFINITION_TITLE_RE.search(title)) and len(title) < 60


def chunk_article_id(chunk: LegalChunk) -> str:
    """Stable article id of a chunk: the corpus id when known ("217", "104.1", "annex"), else parsed."""
    extra = chunk.extra or {}
    return str(extra.get("article_id") or "") or article_number(chunk.article)


def article_number(article: str | None) -> str:
    """Canonical article id: '217-modda' -> '217', '104¹-modda' -> '104.1', 'Статья 15²' -> '15.2'."""
    if not article:
        return ""
    s = article.translate(str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹", "0123456789", ""))
    sup = re.search(r"(\d+)\s*[\u2070-\u209f¹²³]+", article)
    if sup:
        base = sup.group(1)
        tail = article[sup.end(1):]
        digits = "".join(ch for ch in tail if ch in "⁰¹²³⁴⁵⁶⁷⁸⁹")
        return f"{base}.{digits.translate(str.maketrans('⁰¹²³⁴⁵⁶⁷⁸⁹', '0123456789'))}" if digits else base
    m = re.search(r"(\d+(?:[.-]\d+)?)", s)
    return m.group(1).replace("-", ".") if m else ""
