"""Practical figures pack (``data/corpus/practical_facts.json``): BHM, minimum wage, pension base, Central Bank
rate, key statutory rules, deadlines and state-duty rates — each with its source and effective date.

The pack powers three things: direct answers to "how much is the BHM now?", the calculators
(:mod:`lex_agent.knowledge.calculators`) and searchable chunks in the index (so the figures are cited like any
other norm).
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

FACTS_FILE = "practical_facts.json"
FACTS_DOC_ID = "practical-facts"


@dataclass(frozen=True, slots=True)
class SeriesValue:
    series: str
    value: float
    start: date | None
    end: date | None
    source: str
    url: str
    as_of: date | None = None

    def label(self, unit: str) -> str:
        if unit == "%":
            return f"{self.value:g}%"
        return f"{int(self.value):,}".replace(",", " ") + " so'm"


def _d(value: str | None) -> date | None:
    return date.fromisoformat(value) if value else None


class FactsPack:
    def __init__(self, data: dict[str, Any]) -> None:
        self.data = data
        self.updated = data.get("updated")
        self.series: dict[str, dict[str, Any]] = dict(data.get("series") or {})
        self.rules = {r["id"]: r for r in data.get("rules", [])}
        self.deadlines = {d["id"]: d for d in data.get("deadlines", [])}
        self.state_duty = {s["id"]: s for s in data.get("state_duty", [])}

    @classmethod
    def empty(cls) -> FactsPack:
        return cls({})

    # ------------------------------------------------------------------ series
    def unit(self, series: str) -> str:
        return str((self.series.get(series) or {}).get("unit", ""))

    def name(self, series: str, lang: str = "uz") -> str:
        names = (self.series.get(series) or {}).get("names") or {}
        return str(names.get(_lang_key(lang)) or names.get("uz") or series)

    def value_on(self, series: str, on: date | None = None) -> SeriesValue | None:
        """Value in force on ``on`` (default: today); None when the pack has no value for that date."""
        spec = self.series.get(series)
        if not spec:
            return None
        on = on or date.today()
        complete_from = _d(spec.get("complete_from"))
        for v in spec.get("values", []):
            start, end = _d(v.get("from")), _d(v.get("to"))
            if start is None and end is None:  # a "current" figure without validity dates (e.g. CB rate)
                if on >= (_d(v.get("as_of")) or on):
                    return self._sv(series, v)
                continue
            if (start is None or start <= on) and (end is None or on <= end):
                return self._sv(series, v)
        if complete_from and on < complete_from:
            return None
        return None

    def current(self, series: str) -> SeriesValue | None:
        return self.value_on(series, date.today())

    def history(self, series: str) -> list[SeriesValue]:
        spec = self.series.get(series) or {}
        return [self._sv(series, v) for v in spec.get("values", [])]

    @staticmethod
    def _sv(series: str, v: dict[str, Any]) -> SeriesValue:
        return SeriesValue(
            series=series,
            value=float(v["value"]),
            start=_d(v.get("from")),
            end=_d(v.get("to")),
            source=str(v.get("source", "")),
            url=str(v.get("url", "")),
            as_of=_d(v.get("as_of")),
        )

    # ------------------------------------------------------------------ texts for answers and the index
    def text(self, item: dict[str, Any], lang: str) -> str:
        return str(item.get(_lang_key(lang)) or item.get("uz") or "")

    def series_text(self, series: str, lang: str) -> str:
        spec = self.series.get(series) or {}
        key = _lang_key(lang)
        unit = spec.get("unit", "")
        parts: list[str] = []
        for v in spec.get("values", []):
            sv = self._sv(series, v)
            amount = sv.label(unit)
            if sv.start and sv.end:
                period = {"uz": f"{sv.start:%d.%m.%Y}–{sv.end:%d.%m.%Y}", "ru": f"с {sv.start:%d.%m.%Y} по {sv.end:%d.%m.%Y}",
                          "en": f"{sv.start:%d.%m.%Y}–{sv.end:%d.%m.%Y}"}[key]
            elif sv.start:
                period = {"uz": f"{sv.start:%d.%m.%Y} dan", "ru": f"с {sv.start:%d.%m.%Y}", "en": f"from {sv.start:%d.%m.%Y}"}[key]
            else:
                period = {"uz": f"{sv.as_of:%d.%m.%Y} holatiga", "ru": f"на {sv.as_of:%d.%m.%Y}",
                          "en": f"as of {sv.as_of:%d.%m.%Y}"}[key] if sv.as_of else ""
            parts.append(f"{period}: {amount} ({sv.source})")
        usage = (spec.get("usage") or {}).get(key, "")
        head = self.name(series, lang)
        return f"{head}. " + "; ".join(parts) + (f". {usage}" if usage else "")


def _lang_key(lang: str) -> str:
    if lang.startswith("ru"):
        return "ru"
    if lang.startswith("en"):
        return "en"
    return "uz"


def load_facts(corpus_dir: Path) -> FactsPack:
    path = Path(corpus_dir) / FACTS_FILE
    return _load(str(path), path.stat().st_mtime if path.exists() else 0.0)


@lru_cache(maxsize=4)
def _load(path: str, _mtime: float) -> FactsPack:
    p = Path(path)
    if not p.exists():
        return FactsPack.empty()
    try:
        return FactsPack(json.loads(p.read_text(encoding="utf-8")))
    except (OSError, ValueError) as exc:
        logger.warning("Practical facts pack %s is unreadable: %s", p, exc)
        return FactsPack.empty()
