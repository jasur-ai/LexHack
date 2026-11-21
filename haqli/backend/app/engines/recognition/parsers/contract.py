"""Contract header & clause segmenter (§6.3) feeding POST /api/scanner/audit without judging legality."""

from __future__ import annotations

import re
from typing import Any

from app.engines.recognition.entities.money import extract_money
from app.engines.recognition.entities.names import extract_names
from app.engines.recognition.normalize import NormalizedText
from app.engines.recognition.types import Field, RouteHint

_CLAUSE_START_RE = re.compile(
    r"(?m)^\s*(?:(\d+(?:\.\d+)*)[.)]\s+|((?:Shartnoma\s+predmeti|Tomonlarning\s+huquq\w*|To['ʻ’]?lov\s+tartibi|Предмет\s+договора|Права\s+и\s+обязанности|Ответственность\s+сторон)[^\n]*))"
)
_TERM_RE = re.compile(r"\b(\d+\s*(?:oy|yil|kun|месяц\w*|год\w*|лет|дн\w*))\b", re.IGNORECASE)
_DEPOSIT_RE = re.compile(r"(?:depozit|zalog|депозит|залог)[^\n]{0,40}?(\d[\d\s.,]*(?:\s*(?:mln|million|ming|млн|usd|\$|so['ʻ’]?m|сум))?)", re.IGNORECASE)
_PENALTY_RE = re.compile(r"(\d+(?:[.,]\d+)?\s*%)\s*(?:kuniga|har\s+bir\s+kun|в\s+день|за\s+каждый\s+день|per\s+day)", re.IGNORECASE)


def parse_contract(
    norm: NormalizedText,
    *,
    job_id: str | None = None,
) -> tuple[list[Field], list[dict[str, Any]], RouteHint, list[str]]:
    """Segment contract into numbered clauses with spans & bbox unions, plus extract header metadata."""
    text = norm.text
    clauses: list[dict[str, Any]] = []
    matches = list(_CLAUSE_START_RE.finditer(text))

    for idx, m in enumerate(matches):
        start = m.start()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        cid = m.group(1) or f"sec_{idx + 1}"
        clause_txt = text[start:end].strip()
        if len(clause_txt) < 5:
            continue
        clauses.append(
            {
                "clauseId": cid,
                "text": clause_txt,
                "span": [start, end],
                "bboxUnion": norm.span_to_bbox(start, end),
            }
        )

    fields: list[Field] = []
    warnings: list[str] = []

    names = extract_names(text)
    if len(names) >= 1:
        fields.append(Field(key="partyA", value=names[0].name, display=names[0].name, confidence=names[0].confidence, source="rule", span=names[0].span))
    if len(names) >= 2:
        fields.append(Field(key="partyB", value=names[1].name, display=names[1].name, confidence=names[1].confidence, source="rule", span=names[1].span))

    moneys = extract_money(text)
    if moneys:
        top = max(moneys, key=lambda mm: mm.amount)
        fields.append(
            Field(
                key="contractAmount",
                value=top.amount,
                display=f"{top.amount} {top.currency}",
                confidence=top.confidence,
                source="rule",
                span=top.span,
                needs_confirm=top.needs_confirm,
            )
        )
        if top.currency != "UZS":
            warnings.append("rec.warn.foreign_currency")

    term_m = _TERM_RE.search(text)
    if term_m:
        fields.append(Field(key="termDuration", value=term_m.group(1), display=term_m.group(1), confidence=0.86, source="rule", span=term_m.span(1)))

    dep_m = _DEPOSIT_RE.search(text)
    if dep_m:
        fields.append(Field(key="deposit", value=dep_m.group(1).strip(), display=dep_m.group(1).strip(), confidence=0.84, source="rule", span=dep_m.span(1)))

    pen_m = _PENALTY_RE.search(text)
    if pen_m:
        fields.append(Field(key="dailyPenalty", value=pen_m.group(1), display=pen_m.group(1), confidence=0.90, source="rule", span=pen_m.span(1)))

    fields.append(Field(key="clauseCount", value=str(len(clauses)), display=str(len(clauses)), confidence=0.95, source="rule"))

    prefill: dict[str, Any] = {"recognitionJobId": job_id, "clauseCount": len(clauses)}
    route = RouteHint(target="skaner", category=None, prefill={k: v for k, v in prefill.items() if v is not None})
    return fields, clauses, route, warnings
