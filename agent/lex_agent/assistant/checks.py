"""Automatic answer checks run on every answer (LLM and extractive) before it is returned.

* **citations** — every ``[n]`` points at an existing source; dangling markers are removed;
* **invented articles** — article numbers named in the answer must belong to the cited sources (or exist in the
  index for the same act);
* **language** — the answer is written in the requested language and script;
* **length** — concise answers stay short (the answer section is trimmed at a sentence boundary).

Results are returned as warnings plus a confidence adjustment; the text is repaired where that is safe.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field

from lex_agent.chunk_text import chunk_article_id
from lex_agent.models import Language, RetrievedChunk

_CITE_RE = re.compile(r"\[(\d{1,2})\]")
_ART_RE = re.compile(r"(\d{1,4})(?:\s*[-.]\s*(\d{1,2})|[¹²³⁴⁵⁶⁷⁸⁹]+)?\s*-?\s*(?:modda|модда|moddasi|моддаси)|"
                     r"(?:стать[яиеюё]\w*|ст\.|article|art\.)\s*(\d{1,4})", re.I)
_CYR = re.compile(r"[\u0400-\u04ff]")
_LAT = re.compile(r"[A-Za-z]")
_UZ_CYR_ONLY = re.compile(r"[ўқғҳЎҚҒҲ]")
_EN_WORDS = re.compile(r"\b(?:the|and|of|to|is|you|your|for|with|under|law|article)\b", re.I)


@dataclass(slots=True)
class CheckReport:
    passed: bool = True
    warnings: list[str] = field(default_factory=list)
    fixed_text: str = ""
    confidence_delta: float = 0.0
    checks: dict[str, bool] = field(default_factory=dict)


def _script_ok(text: str, lang: Language) -> bool:
    letters_cyr = len(_CYR.findall(text))
    letters_lat = len(_LAT.findall(text))
    total = letters_cyr + letters_lat
    if total < 20:
        return True
    cyr_share = letters_cyr / total
    if lang == Language.UZ_LATN:
        return cyr_share < 0.35
    if lang == Language.UZ_CYRL:
        return cyr_share > 0.6
    if lang == Language.RU:
        return cyr_share > 0.6 and not _UZ_CYR_ONLY.search(text[:400])
    if lang == Language.EN:
        return cyr_share < 0.35 and bool(_EN_WORDS.search(text))
    return True


def _answer_body(text: str) -> str:
    """Text of the ANSWER and KEY POINTS sections (quotes of the law are allowed in the source script)."""
    parts = re.split(r"^###\s*", text, flags=re.M)
    keep = [p for p in parts if p.upper().startswith(("ANSWER", "KEY POINTS", "STEPS"))] or [text]
    joined = "\n".join(keep)
    return re.sub(r"[«“\"][^»”\"]{0,600}[»”\"]", " ", joined)  # ignore quoted statute text


def run_checks(
    text: str,
    *,
    evidence: list[RetrievedChunk],
    lang: Language,
    concise: bool = True,
    article_exists: Callable[[str, str], bool] | None = None,
    resolve_acts: Callable[[str], list[str]] | None = None,
    max_answer_words: int = 170,
) -> CheckReport:
    report = CheckReport(fixed_text=text)
    n_sources = len(evidence)

    # 1. citations point at real sources
    bad = sorted({int(m.group(1)) for m in _CITE_RE.finditer(text) if not 1 <= int(m.group(1)) <= n_sources})
    if bad:
        report.fixed_text = _CITE_RE.sub(lambda m: m.group(0) if 1 <= int(m.group(1)) <= n_sources else "", report.fixed_text)
        report.warnings.append(f"Removed citation markers without a source: {', '.join(f'[{b}]' for b in bad)}")
        report.confidence_delta -= 0.1
    report.checks["citations"] = not bad

    # 2. article numbers belong to the cited acts
    cited = {(e.chunk.canonical_id, chunk_article_id(e.chunk)) for e in evidence}
    cited_articles = {a for _, a in cited}
    acts = {d for d, _ in cited}
    invented: list[str] = []
    body = _answer_body(text)
    for m in _ART_RE.finditer(body):
        base = m.group(1) or m.group(3)
        sub = m.group(2)
        art = f"{base}.{sub}" if sub else base
        # The act named right before the article ("Mehnat kodeksi, 245-modda") decides where it must exist
        clause = re.split(r"[.;\n(]", body[max(0, m.start() - 90): m.start()])[-1]
        named = resolve_acts(clause) if resolve_acts and clause.strip() else []
        if named:
            if article_exists and any(article_exists(doc, art) or article_exists(doc, base) for doc in named):
                continue
            if not article_exists and any((doc, art) in cited or (doc, base) in cited for doc in named):
                continue
            invented.append(art)
            continue
        if art in cited_articles or base in cited_articles:
            continue
        if article_exists and any(article_exists(doc, art) for doc in acts):
            continue
        invented.append(art)
    if invented:
        report.warnings.append(f"Article numbers not found in the sources: {', '.join(sorted(set(invented)))}")
        report.confidence_delta -= 0.2
    report.checks["articles"] = not invented

    # 3. language and script
    script_ok = _script_ok(_answer_body(text), lang)
    if not script_ok:
        report.warnings.append(f"Answer language/script does not match {lang.value}")
        report.confidence_delta -= 0.15
    report.checks["language"] = script_ok

    # 4. length of the direct answer
    length_ok = True
    if concise:
        m = re.search(r"###\s*ANSWER\s*\n(.*?)(?=\n###|\Z)", report.fixed_text, re.S)
        if m:
            words = m.group(1).split()
            if len(words) > max_answer_words:
                length_ok = False
                trimmed = " ".join(words[:max_answer_words])
                cut = max(trimmed.rfind(". "), trimmed.rfind("» "), trimmed.rfind("; "))
                trimmed = trimmed[: cut + 1] if cut > len(trimmed) // 2 else trimmed + "…"
                report.fixed_text = report.fixed_text.replace(m.group(1), trimmed + "\n", 1)
                report.warnings.append("Answer shortened to keep it scannable")
    report.checks["length"] = length_ok
    report.passed = all(report.checks.values()) or (report.checks["citations"] and report.checks["articles"])
    return report
