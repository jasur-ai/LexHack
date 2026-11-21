"""Nightly synchronisation of the most-needed acts with lex.uz (National Database of Legislation of Uzbekistan).

The bundled corpus is a dated snapshot. ``lex-agent sync`` keeps the ~200 acts people ask about most
(:data:`CATALOG_PATH`, built by ``scripts/build_sync_catalog.py``) in step with the consolidated texts on lex.uz:

* **polite client** — one request every 2 s by default (``LEX_SYNC_RPS``), a per-run request budget
  (``LEX_SYNC_BUDGET``), ``Retry-After`` honoured on 429/503, exponential back-off on network errors, and an honest
  User-Agent. A full pass is spread over several nights: priority-1 acts are re-checked every 2 days, priority 2 every
  7 and priority 3 every 14 (oldest check first), so a night costs a few dozen requests;
* **cache** — conditional requests (``ETag`` / ``Last-Modified`` when lex.uz sends them) and a SHA-256 of the parsed
  article texts: an unchanged act costs one request and is never rewritten;
* **safety** — a page that suddenly has far fewer articles than the stored version (layout change, error page,
  partial download) is marked *suspect* and the stored text is kept; nothing is deleted on a failed fetch;
* **output** — ``data/corpus/lex_sync_uz.jsonl.gz`` / ``lex_sync_ru.jsonl.gz`` in the same article-record format as
  the LawCodex bundle (the index builder prefers them over the snapshot for the same act),
  ``lex_sync_catalog.json`` (titles, numbers, ids of the synced acts) and ``lex_sync_state.json`` (per-act checks).

Decrees and government resolutions are not in the LawCodex export; their entries carry a ``find`` spec (search words,
required title words, act number) and are resolved through the lex.uz search at sync time, then verified before any
text is stored.

lex.uz page structure used here (the same as LawCodex/uz's converter): the act text lives in ``#divCont`` as
``div.<CLASS>`` blocks — ``ACT_FORM`` / ``ACT_TITLE``, ``TEXT_HEADER_DEFAULT`` (parts, sections, chapters),
``CLAUSE_DEFAULT`` (article headings "1-модда." / "Статья 1."), body classes, amendment notes (``CHANGES_ORIGINS``,
``FOOTNOTE`` …) and editorial blocks that are dropped (``COMMENT``, ``INDEXES_ON_REF``).
"""

from __future__ import annotations

import asyncio
import gzip
import hashlib
import json
import logging
import os
import re
import time
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone, tzinfo
from html import unescape
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

import httpx
from bs4 import BeautifulSoup, NavigableString, Tag

logger = logging.getLogger(__name__)

SYNC_SOURCE = "lex_uz_sync"
BUNDLES = {"uz": "lex_sync_uz.jsonl.gz", "ru": "lex_sync_ru.jsonl.gz"}
STATE_FILE = "lex_sync_state.json"
CATALOG_OUT = "lex_sync_catalog.json"
CATALOG_PATH = Path(__file__).resolve().parents[1] / "data" / "lex_sync_catalog.json"
USER_AGENT = "HaqliLexAgent/1.0 (+https://github.com/jasur-ai/LexHack; legal information assistant; nightly sync)"
MAX_AGE_DAYS = {1: 2, 2: 7, 3: 14}
SUSPECT_RATIO = 0.5  # a new version with fewer than half the stored articles is not trusted

_SUP = str.maketrans("0123456789", "⁰¹²³⁴⁵⁶⁷⁸⁹")
_UNSUP = str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹", "0123456789")
_SKIP_CLASSES = {"COMMENT", "INDEXES_ON_REF", "COMMENTLEXUZ", "UNOFFIAL"}
_NOTE_CLASSES = {"CHANGES_ORIGINS", "FOOTNOTE", "PUBLICATION_ORIGIN", "NEW_EDITION", "OFFICIAL_SOUR_TEXT"}
_HEADING_CLASSES = {"TEXT_HEADER_DEFAULT", "ACT_TITLE_APPL", "TEXT_BOLD_CENTER"}
_UZ_ART = re.compile(r"^(\d+(?:[¹²³⁴⁵⁶⁷⁸⁹⁰]+|[-.]\d+)?)\s*-\s*модда\.?\s*(.*)$", re.I)
_RU_ART = re.compile(r"^Статья\s+(\d+(?:[¹²³⁴⁵⁶⁷⁸⁹⁰]+|[-.]\d+)?)\.?\s*(.*)$", re.I)
_CHAPTER = re.compile(r"^(?:\d+[-\s]*боб|глава\s+[\dIVXLC]+|[IVXLC]+\s*боб|боб\s+\d+)", re.I)
_SECTION = re.compile(r"^(?:[IVXLC\d]+[-\s]*бўлим|раздел\s+[IVXLC\d]+|бўлим)", re.I)
_PART = re.compile(r"^(?:умумий қисм|махсус қисм|общая часть|особенная часть|[IVXLC\d]+[-\s]*қисм|часть\s+[IVXLC\d]+)", re.I)
_ANNEX = re.compile(r"^(?:\d+\s*-?\s*)?(?:ИЛОВА|Илова|ПРИЛОЖЕНИЕ|Приложение)(?:\s*(?:№\s*)?\d+)?\.?$")
_SIGNATURE = re.compile(
    r"^(?:Ўзбекистон Республикаси(?:нинг)? Президенти|Президент Республики Узбекистан|Ўзбекистон Республикаси Олий "
    r"Мажлиси|Председатель Олий Мажлиса|Ўзбекистон Республикаси Бош вазири|Премьер-министр Республики Узбекистан)\b"
)
_ACT_NUMBER = re.compile(r"(?<![\w-])(ЎРҚ|ЗРУ|ПФ|УП|ПҚ|ПП|ВМҚ|ПКМ|O['ʻ‘]?RQ|PF|PQ)\s*[-–]\s*(\d+)", re.I)
_PLAIN_NUMBER = re.compile(r"№\s*(\d+[\w-]*)|(\d+)\s*-\s*сон\b")
_MONTHS = {
    "январ": 1, "феврал": 2, "март": 3, "апрел": 4, "май": 5, "мая": 5, "июн": 6, "июл": 7, "август": 8,
    "сентябр": 9, "октябр": 10, "ноябр": 11, "декабр": 12,
}
_DATE_UZ = re.compile(r"(\d{4})\s+йил\s+(\d{1,2})\s+([а-яўқғҳё]+)", re.I)
_DATE_RU = re.compile(r"(\d{1,2})\s+([а-яё]+)\s+(\d{4})\s+г", re.I)
_DATE_NUM = re.compile(r"\b(\d{2})\.(\d{2})\.(\d{4})\b")
_LANG_LINK_TEXT = {
    "ru": re.compile(r"^(?:рус(?:ский|ча)?|ru|на русском)$", re.I),
    "uz": re.compile(r"^(?:ўзб(?:екча)?|узб(?:екча)?|o['ʻ‘]?zb(?:ekcha)?|uzb?|ўзбек тилида|кирилл)$", re.I),
}
_DOC_HREF = re.compile(r"^(?:https?://(?:www\.)?lex\.uz)?/(?:(ru|uz|en)/)?docs/(-?\d+)/?$")
_SEARCH_ROW = re.compile(
    r'<a[^>]+class="lx_link[^"]*"[^>]+href="/(?:(?:ru|uz|en)/)?docs/(-?\d+)"[^>]*>(.*?)</a>(?:.*?badge-nine">(.*?)</span>)?',
    re.S,
)
_GENERIC_DOC_LINK = re.compile(r'href="/(?:(?:ru|uz|en)/)?docs/(-?\d+)"[^>]*>(.*?)</a>', re.S)


# ------------------------------------------------------------------------------------------------ catalog


@dataclass(slots=True)
class CatalogEntry:
    slug: str
    key: str | None
    kind: str
    priority: int
    short_uz: str = ""
    short_ru: str = ""
    ru_id: str | None = None
    branches: list[str] = field(default_factory=list)
    verified: bool = True
    find: dict[str, Any] | None = None
    hint_id: str | None = None


def load_sync_catalog(path: Path = CATALOG_PATH) -> list[CatalogEntry]:
    data = json.loads(path.read_text(encoding="utf-8"))
    out: list[CatalogEntry] = []
    for e in data.get("entries", []):
        out.append(
            CatalogEntry(
                slug=str(e.get("slug") or e.get("key")),
                key=str(e["key"]) if e.get("key") else None,
                kind=str(e.get("kind") or "law"),
                priority=int(e.get("priority") or 3),
                short_uz=e.get("short_uz") or "",
                short_ru=e.get("short_ru") or "",
                ru_id=str(e["ru_id"]) if e.get("ru_id") else None,
                branches=list(e.get("branches") or []),
                verified=bool(e.get("verified", True)),
                find=e.get("find"),
                hint_id=str(e["hint_id"]) if e.get("hint_id") else None,
            )
        )
    return out


# ------------------------------------------------------------------------------------------------ parsing


@dataclass(slots=True)
class ArticleBlock:
    raw_id: str
    title: str
    section: str | None
    chapter: str | None
    lines: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    article_id: str = ""
    display: str = ""


@dataclass(slots=True)
class ParsedAct:
    lang: str
    form: str | None
    title: str | None
    preamble: list[str]
    articles: list[ArticleBlock]
    notes: list[str]
    number: str | None
    adopted: str | None
    editions: dict[str, str]

    @property
    def has_text(self) -> bool:
        return bool(self.articles) or sum(len(x) for x in self.preamble) >= 80


def _clean(text: str) -> str:
    text = text.replace("\xa0", " ")
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    return text.strip()


def _text_of(node: Tag) -> str:
    out: list[str] = []
    for d in node.descendants:
        if isinstance(d, NavigableString):
            if d.parent is not None and d.parent.name in ("script", "style"):
                continue
            out.append(str(d))
        elif isinstance(d, Tag) and d.name == "br":
            out.append("\n")
        elif isinstance(d, Tag) and d.name in ("p", "div") and out and not out[-1].endswith("\n"):
            out.append("\n")
    return "".join(out)


def _table_lines(table: Tag) -> list[str]:
    lines: list[str] = []
    for tr in table.find_all("tr"):
        cells = [_clean(_text_of(td)).replace("\n", " ") for td in tr.find_all(["td", "th"])]
        cells = [c for c in cells if c]
        if cells:
            lines.append(" — ".join(cells))
    return lines


def _iso_date(text: str) -> str | None:
    for rx, order in ((_DATE_UZ, "ydm"), (_DATE_RU, "dmy")):
        m = rx.search(text)
        if m:
            if order == "ydm":
                year, day, month_word = m.group(1), m.group(2), m.group(3)
            else:
                day, month_word, year = m.group(1), m.group(2), m.group(3)
            month = next((n for stem, n in _MONTHS.items() if month_word.lower().startswith(stem)), None)
            if month:
                return f"{int(year):04d}-{month:02d}-{int(day):02d}"
    m = _DATE_NUM.search(text)
    if m:
        return f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
    return None


def _act_number(text: str) -> str | None:
    m = _ACT_NUMBER.search(text)
    if m:
        return f"{m.group(1).upper()}-{m.group(2)}"
    m = _PLAIN_NUMBER.search(text)
    if m:
        return m.group(1) or m.group(2)
    return None


def _language_editions(soup: BeautifulSoup, container: Tag | None) -> dict[str, str]:
    """lex.uz ids of the other language editions, from the language switcher (links outside the act text whose
    caption is a language name)."""
    found: dict[str, str] = {}
    for a in soup.find_all("a", href=True):
        if container is not None and container in a.parents:
            continue
        m = _DOC_HREF.match(str(a["href"]).strip())
        if not m:
            continue
        caption = re.sub(r"\s+", " ", a.get_text(" ", strip=True))
        for lang, rx in _LANG_LINK_TEXT.items():
            if rx.match(caption) and lang not in found:
                doc_id = m.group(2)
                if lang == "uz" and doc_id.startswith("-"):
                    doc_id = doc_id[1:]  # the Latin edition id is the negative of the Cyrillic one
                found[lang] = doc_id
    return found


def _resolve_ids(articles: list[ArticleBlock], lang: str) -> None:
    """Article ids: "128³" -> "128.3", "385-1" -> "385.1". The page keeps superscripts as <sup> (turned into
    superscript digits before parsing), so numbers are never guessed from flattened digits."""
    for art in articles:
        raw = art.raw_id
        sup: int | None = None
        m = re.match(r"(\d+)([¹²³⁴⁵⁶⁷⁸⁹⁰]+)$", raw)
        if m:
            base, sup = int(m.group(1)), int(m.group(2).translate(_UNSUP))
        elif re.match(r"^\d+[-.]\d+$", raw):
            a, b = re.split(r"[-.]", raw)
            base, sup = int(a), int(b)
        else:
            base = int(re.sub(r"\D", "", raw) or 0)
        art.article_id = f"{base}.{sup}" if sup else str(base)
        sup_txt = str(sup).translate(_SUP) if sup else ""
        art.display = f"{base}{sup_txt}-модда" if lang == "uz" else f"Статья {base}{sup_txt}"


def parse_act_html(html: str, *, lang: str) -> ParsedAct:
    """Parse a lex.uz act page (``/docs/<id>`` for Uzbek, ``/ru/docs/<id>`` for Russian)."""
    soup = BeautifulSoup(html, "lxml")
    cont = soup.find(id="divCont")
    editions = _language_editions(soup, cont if isinstance(cont, Tag) else None)
    act = ParsedAct(lang=lang, form=None, title=None, preamble=[], articles=[], notes=[], number=None, adopted=None,
                    editions=editions)
    if not isinstance(cont, Tag):
        return act
    for sup in cont.find_all("sup"):
        digits = sup.get_text("", strip=True)
        sup.replace_with(NavigableString(digits.translate(_SUP) if digits.isdigit() else digits))
    art_re = _UZ_ART if lang == "uz" else _RU_ART
    section: str | None = None
    chapter: str | None = None
    current: ArticleBlock | None = None
    tail_lines: list[str] = []
    for el in cont.find_all("div", recursive=False):
        classes = [c for c in (el.get("class") or []) if c.isupper()]
        if not classes:
            continue
        cls = classes[0]
        if cls in _SKIP_CLASSES:
            continue
        for x in el.select(".lx_elem2"):
            x.decompose()
        table_lines: list[str] = []
        for table in el.find_all("table"):
            table_lines.extend(_table_lines(table))
            table.extract()
        txt = _clean(_text_of(el))
        if cls == "ACT_FORM":
            act.form = txt or act.form
            continue
        if cls == "ACT_TITLE" and act.title is None:
            act.title = re.sub(r"\s+", " ", txt)
            continue
        if cls in _NOTE_CLASSES:
            if txt:
                (current.notes if current else act.notes).append(re.sub(r"\s+", " ", txt))
            continue
        one_line = re.sub(r"\s+", " ", txt)
        m = art_re.match(one_line) if txt else None
        if cls == "CLAUSE_DEFAULT" or (m and len(m.group(2)) < 400 and cls not in _HEADING_CLASSES):
            if m:
                current = ArticleBlock(raw_id=m.group(1), title=m.group(2).strip().rstrip("."), section=section,
                                       chapter=chapter)
                act.articles.append(current)
                continue
        if cls in _HEADING_CLASSES and txt:
            current = None
            if _CHAPTER.match(one_line):
                chapter = one_line
            elif _SECTION.match(one_line) or _PART.match(one_line):
                section, chapter = one_line, None
            else:
                chapter = one_line
            continue
        lines = [ln.strip() for ln in txt.split("\n") if ln.strip()] + table_lines
        if current is not None:
            current.lines.extend(lines)
        else:
            act.preamble.extend(lines)
        tail_lines = (tail_lines + lines)[-25:]
    _resolve_ids(act.articles, lang)
    # The signature line at the very end ("Тошкент ш., 2022 йил 28 октябрь, ЎРҚ-798-сон") carries the date and
    # the number; the body may mention other dates and acts, so lines are read from the end
    for line in reversed(tail_lines):
        act.number = act.number or _act_number(line)
        act.adopted = act.adopted or _iso_date(line)
        if act.number and act.adopted:
            break
    act.number = act.number or _act_number(f"{act.title or ''} {act.form or ''}")
    return act


def _split_signature_and_annexes(act: ParsedAct) -> list[ArticleBlock]:
    """Drop the signature block of the last article; turn the annexes after it into their own records."""
    articles = list(act.articles)
    if not articles:
        return []
    # work on a copy: the parsed act stays intact (records can be built from it again)
    src = articles[-1]
    last = ArticleBlock(raw_id=src.raw_id, title=src.title, section=src.section, chapter=src.chapter,
                        lines=list(src.lines), notes=list(src.notes), article_id=src.article_id, display=src.display)
    articles[-1] = last
    sig = next((i for i, line in enumerate(last.lines) if _SIGNATURE.match(line)), None)
    annexes: list[ArticleBlock] = []
    if sig is not None:
        tail = last.lines[sig:]
        last.lines = last.lines[:sig]
        current: ArticleBlock | None = None
        for line in tail:
            if _ANNEX.match(line):
                n = len(annexes) + 1
                current = ArticleBlock(raw_id=f"annex{n}", title="", section=None, chapter=None)
                current.article_id = "annex" if n == 1 else f"annex{n}"
                current.display = ("Илова" if act.lang == "uz" else "Приложение") + (f" {n}" if n > 1 else "")
                annexes.append(current)
                continue
            if current is not None:
                current.lines.append(line)
    return articles + [a for a in annexes if a.lines]


def _note_summary(notes: list[str]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for note in notes[-6:]:
        acts = re.findall(r"(?:ЎРҚ|ЗРУ|O'RQ)-\d+", note)
        dates = re.findall(r"(\d{1,2}\.\d{2}\.\d{4})", note)
        eff = re.search(r"(?:Кучга кириш санаси|Дата вступления в силу)\s*[—-]\s*([^)]+)", note)
        out.append({"act": acts[0] if acts else "", "published": dates[0] if dates else "",
                    "effective": eff.group(1).strip() if eff else "", "text": note[:400]})
    return out


_KIND_TO_DOC_TYPE = {
    "constitution": "constitution", "constitutional_law": "constitutional_law", "code": "code", "law": "law",
    "presidential_decree": "presidential_decree", "presidential_resolution": "presidential_resolution",
    "cabinet_resolution": "cabinet_resolution",
}


def build_records(act: ParsedAct, *, key: str, lex_id: str, entry: CatalogEntry, snapshot: str) -> list[dict[str, Any]]:
    """Article records in the bundle format shared with the LawCodex export."""
    lang_code = "uz_cyrl" if act.lang == "uz" else "ru"
    title = act.title or (entry.short_uz if act.lang == "uz" else entry.short_ru) or key
    short = (entry.short_uz if act.lang == "uz" else entry.short_ru) or title
    base = {
        "source": SYNC_SOURCE,
        "lang": lang_code,
        "doc_key": key,
        "lex_doc_id": lex_id,
        "doc_title": title,
        "short_title": short,
        "doc_number": act.number,
        "doc_type": _KIND_TO_DOC_TYPE.get(entry.kind, "law"),
        "adopted": act.adopted,
        "snapshot": snapshot,
    }
    records: list[dict[str, Any]] = []
    pre_text = "\n".join(act.preamble).strip()
    articles = _split_signature_and_annexes(act)
    if articles:
        if len(pre_text) >= 160:
            records.append({**base, "article_id": "_front", "article_display": None, "article_title": None,
                            "section": None, "chapter": None, "text": pre_text})
        seen: dict[str, int] = {}
        for art in articles:
            text = "\n".join(art.lines).strip()
            if not text and not art.title:
                continue
            seen[art.article_id] = seen.get(art.article_id, 0) + 1
            rec = {**base, "article_id": art.article_id, "article_display": art.display,
                   "article_title": art.title or None, "section": art.section, "chapter": art.chapter,
                   "text": text or art.title}
            if seen[art.article_id] > 1:
                rec["occurrence"] = seen[art.article_id]
            if art.notes:
                rec["notes"] = _note_summary(art.notes)
            records.append(rec)
    elif pre_text:
        records.append({**base, "article_id": None, "article_display": None, "article_title": None,
                        "section": None, "chapter": None, "text": pre_text})
    return records


def records_digest(records: Iterable[dict[str, Any]]) -> str:
    """Content hash of an edition: article ids, titles and texts (not ids, dates or snapshot labels)."""
    h = hashlib.sha256()
    for r in records:
        h.update(json.dumps([r.get("article_id"), r.get("occurrence"), r.get("article_title"), r.get("text")],
                            ensure_ascii=False).encode("utf-8"))
    return h.hexdigest()


def parse_search_results(html: str) -> list[tuple[str, str, str]]:
    """(lex.uz id, title, badge) rows of a lex.uz search page."""
    rows: list[tuple[str, str, str]] = []
    seen: set[str] = set()

    def _plain(fragment: str | None) -> str:
        return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", fragment or ""))).strip()

    for doc_id, title, badge in _SEARCH_ROW.findall(html):
        if doc_id not in seen:
            seen.add(doc_id)
            rows.append((doc_id, _plain(title), _plain(badge)))
    if not rows:
        for doc_id, title in _GENERIC_DOC_LINK.findall(html):
            t = _plain(title)
            if doc_id not in seen and len(t) >= 12:
                seen.add(doc_id)
                rows.append((doc_id, t, ""))
    return rows


# ------------------------------------------------------------------------------------------------ polite client


class SyncBudgetExhausted(Exception):
    """The per-run request budget is used up; the remaining acts wait for the next run."""


@dataclass(slots=True)
class FetchResult:
    status: int
    text: str
    etag: str | None
    last_modified: str | None
    url: str


class PoliteClient:
    """Rate-limited lex.uz client: fixed spacing between requests, a request budget, Retry-After and back-off."""

    def __init__(
        self,
        *,
        base_url: str = "https://lex.uz",
        rps: float = 0.5,
        max_requests: int = 80,
        timeout: float = 60.0,
        max_retries: int = 3,
        transport: httpx.AsyncBaseTransport | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        clock: Callable[[], float] = time.monotonic,
        user_agent: str = USER_AGENT,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.min_interval = 1.0 / max(rps, 0.01)
        self.max_requests = max_requests
        self.max_retries = max_retries
        self.requests = 0
        self.bytes = 0
        self._sleep = sleep
        self._clock = clock
        self._next_at = 0.0
        self._client = httpx.AsyncClient(
            transport=transport,
            timeout=timeout,
            follow_redirects=True,
            headers={"User-Agent": user_agent, "Accept": "text/html,application/xhtml+xml",
                     "Accept-Language": "uz,ru;q=0.9,en;q=0.5"},
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def _space(self) -> None:
        wait = self._next_at - self._clock()
        if wait > 0:
            await self._sleep(wait)
        self._next_at = self._clock() + self.min_interval

    @staticmethod
    def _retry_after(resp: httpx.Response) -> float | None:
        raw = resp.headers.get("Retry-After")
        if raw and raw.strip().isdigit():
            return float(raw.strip())
        return None

    async def get(self, path: str, *, etag: str | None = None, last_modified: str | None = None) -> FetchResult:
        url = path if path.startswith("http") else f"{self.base_url}{path}"
        headers: dict[str, str] = {}
        if etag:
            headers["If-None-Match"] = etag
        if last_modified:
            headers["If-Modified-Since"] = last_modified
        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            if self.requests >= self.max_requests:
                raise SyncBudgetExhausted(f"request budget of {self.max_requests} used")
            await self._space()
            self.requests += 1
            try:
                resp = await self._client.get(url, headers=headers)
            except httpx.TransportError as exc:
                last_error = exc
                await self._sleep(min(120.0, 5.0 * 2**attempt))
                continue
            if resp.status_code == 429 or resp.status_code >= 500:
                last_error = httpx.HTTPStatusError(f"HTTP {resp.status_code}", request=resp.request, response=resp)
                await self._sleep(min(300.0, self._retry_after(resp) or 5.0 * 2**attempt))
                continue
            self.bytes += len(resp.content)
            return FetchResult(status=resp.status_code, text=resp.text if resp.status_code == 200 else "",
                               etag=resp.headers.get("ETag"), last_modified=resp.headers.get("Last-Modified"),
                               url=str(resp.url))
        raise last_error or httpx.HTTPError(f"GET {url} failed")


# ------------------------------------------------------------------------------------------------ state and bundles


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)


class SyncState:
    """Per-act sync bookkeeping in ``lex_sync_state.json``."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.data: dict[str, Any] = {"acts": {}, "runs": []}
        if path.exists():
            try:
                self.data = json.loads(path.read_text(encoding="utf-8"))
                self.data.setdefault("acts", {})
                self.data.setdefault("runs", [])
            except (OSError, ValueError) as exc:
                logger.warning("Unreadable sync state %s (%s); starting fresh", path, exc)

    def act(self, slug: str) -> dict[str, Any]:
        return self.data["acts"].setdefault(slug, {"editions": {}})

    def edition(self, slug: str, lang: str) -> dict[str, Any]:
        return self.act(slug)["editions"].setdefault(lang, {})

    def last_checked(self, slug: str) -> datetime | None:
        eds = self.data["acts"].get(slug, {}).get("editions", {})
        stamps = [e.get("checked_at") for e in eds.values() if e.get("checked_at")]
        if not stamps:
            return None
        return min(datetime.fromisoformat(s) for s in stamps)

    def add_run(self, summary: dict[str, Any]) -> None:
        self.data["runs"] = (self.data.get("runs", []) + [summary])[-30:]

    def save(self) -> None:
        _atomic_write(self.path, (json.dumps(self.data, ensure_ascii=False, indent=1) + "\n").encode("utf-8"))


class SyncBundles:
    """The synced article records, grouped by act, in ``lex_sync_{uz,ru}.jsonl.gz``."""

    def __init__(self, corpus_dir: Path) -> None:
        self.corpus_dir = corpus_dir
        self.records: dict[str, dict[str, list[dict[str, Any]]]] = {"uz": {}, "ru": {}}
        for lang, name in BUNDLES.items():
            path = corpus_dir / name
            if not path.exists():
                continue
            with gzip.open(path, "rt", encoding="utf-8") as fh:
                for line in fh:
                    if line.strip():
                        rec = json.loads(line)
                        self.records[lang].setdefault(str(rec["doc_key"]), []).append(rec)
        self.dirty = False

    def get(self, lang: str, key: str) -> list[dict[str, Any]]:
        return self.records[lang].get(key, [])

    def replace(self, lang: str, key: str, records: list[dict[str, Any]]) -> None:
        self.records[lang][key] = records
        self.dirty = True

    def write(self) -> None:
        for lang, name in BUNDLES.items():
            buf = "".join(
                json.dumps(rec, ensure_ascii=False) + "\n"
                for key in sorted(self.records[lang])
                for rec in self.records[lang][key]
            )
            _atomic_write(self.corpus_dir / name, gzip.compress(buf.encode("utf-8"), compresslevel=9, mtime=0))
        self.dirty = False


# ------------------------------------------------------------------------------------------------ the sync


@dataclass(slots=True)
class SyncReport:
    started: str
    finished: str = ""
    check_only: bool = False
    requests: int = 0
    bytes: int = 0
    checked: int = 0
    unchanged: int = 0
    updated: int = 0
    added: int = 0
    failed: int = 0
    suspect: int = 0
    unresolved: int = 0
    deferred: int = 0
    changes: list[dict[str, Any]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {k: getattr(self, k) for k in self.__slots__}  # type: ignore[attr-defined]


class LexSync:
    """Keeps the catalog's acts in step with lex.uz (see the module docstring)."""

    def __init__(
        self,
        corpus_dir: Path,
        *,
        catalog: list[CatalogEntry] | None = None,
        client: PoliteClient | None = None,
        rps: float = 0.5,
        max_requests: int = 80,
        now: Callable[[], datetime] = _now,
    ) -> None:
        self.corpus_dir = corpus_dir
        self.catalog = catalog if catalog is not None else load_sync_catalog()
        self.client = client or PoliteClient(rps=rps, max_requests=max_requests)
        self._owns_client = client is None
        self._now = now
        self.state = SyncState(corpus_dir / STATE_FILE)
        # Article counts of the bundled snapshot: the first synced version of an act must not be much shorter
        self._baseline: dict[tuple[str, str], int] = {}
        snapshot = corpus_dir / "catalog.json"
        if snapshot.exists():
            try:
                for d in json.loads(snapshot.read_text(encoding="utf-8")).get("documents", []):
                    for lang in ("uz", "ru"):
                        if d.get(f"articles_{lang}"):
                            self._baseline[(str(d["doc_key"]), lang)] = int(d[f"articles_{lang}"])
            except (OSError, ValueError, KeyError) as exc:
                logger.debug("Snapshot catalog unreadable for baselines: %s", exc)

    async def close(self) -> None:
        if self._owns_client:
            await self.client.close()

    # -------------------------------------------------------------- scheduling
    def due(self, *, only: set[str] | None = None, force: bool = False) -> list[CatalogEntry]:
        """Catalog entries to check now, oldest check first within each priority."""
        now = self._now()
        picked: list[tuple[int, datetime, CatalogEntry]] = []
        for e in self.catalog:
            if only and e.slug not in only and (e.key or "") not in only:
                continue
            last = self.state.last_checked(e.slug)
            max_age = timedelta(days=MAX_AGE_DAYS.get(e.priority, 14))
            if force or only or last is None or now - last >= max_age:
                picked.append((e.priority, last or datetime.min.replace(tzinfo=timezone.utc), e))
        picked.sort(key=lambda t: (t[1], t[0]))
        return [e for _p, _l, e in picked]

    # -------------------------------------------------------------- resolution of decrees and resolutions
    async def _resolve(self, entry: CatalogEntry, report: SyncReport) -> tuple[str | None, str | None]:
        """(Uzbek id, Russian id) of an entry: catalog ids first, then ids resolved earlier, a hint id, the search."""
        st = self.state.act(entry.slug)
        if entry.key:
            return entry.key, entry.ru_id or st.get("ru_id")
        if st.get("uz_id") or st.get("ru_id"):
            return st.get("uz_id"), st.get("ru_id")
        spec = entry.find or {}
        if entry.hint_id:
            res = await self.client.get(f"/docs/{entry.hint_id}")
            if res.status == 200:
                act = parse_act_html(res.text, lang="uz")
                if act.has_text and _matches(spec, f"{act.title or ''} {act.number or ''}", lang="uz"):
                    st.update({"uz_id": entry.hint_id, "ru_id": act.editions.get("ru"), "resolved_by": "hint"})
                    return entry.hint_id, act.editions.get("ru")
        query = spec.get("query_ru")
        if query:
            for path in (f"/ru/search/all?searchtitle={quote_plus(query)}", f"/ru/search?query={quote_plus(query)}"):
                res = await self.client.get(path)
                if res.status != 200:
                    continue
                for doc_id, title, badge in parse_search_results(res.text):
                    if _matches(spec, f"{title} {badge}", lang="ru"):
                        st.update({"ru_id": doc_id.lstrip("-"), "resolved_by": "search", "search_title": title})
                        st.pop("status", None)
                        return None, doc_id.lstrip("-")
        report.unresolved += 1
        st["status"] = "unresolved"
        return None, None

    # -------------------------------------------------------------- one edition
    async def _sync_edition(
        self, entry: CatalogEntry, key: str, lang: str, lex_id: str, report: SyncReport, *, check_only: bool, force: bool
    ) -> ParsedAct | None:
        ed = self.state.edition(entry.slug, lang)
        path = f"/docs/{lex_id}" if lang == "uz" else f"/ru/docs/{lex_id}"
        stamp = self._now().isoformat()
        res = await self.client.get(path, etag=None if force else ed.get("etag"),
                                    last_modified=None if force else ed.get("last_modified"))
        report.checked += 1
        ed["checked_at"] = stamp
        ed["lex_id"] = lex_id
        if res.status == 304:
            report.unchanged += 1
            ed["status"] = "unchanged"
            return None
        if res.status != 200:
            report.failed += 1
            ed["status"], ed["error"] = "failed", f"HTTP {res.status}"
            report.errors.append(f"{entry.slug}/{lang}: HTTP {res.status}")
            return None
        act = parse_act_html(res.text, lang=lang)
        if not act.has_text:
            report.failed += 1
            ed["status"], ed["error"] = "failed", "page has no act text"
            report.errors.append(f"{entry.slug}/{lang}: no act text on the page")
            return None
        if entry.find and not _matches(entry.find, f"{act.title or ''} {act.number or ''}", lang=lang):
            report.failed += 1
            ed["status"], ed["error"] = "failed", "page does not match the expected act"
            report.errors.append(f"{entry.slug}/{lang}: page does not match the catalog entry")
            return None
        records = build_records(act, key=key, lex_id=lex_id, entry=entry, snapshot=stamp[:10])
        digest = records_digest(records)
        ed["etag"], ed["last_modified"] = res.etag, res.last_modified
        n_articles = sum(1 for r in records if r.get("article_display"))
        if digest == ed.get("sha256") and not force:
            report.unchanged += 1
            ed["status"] = "unchanged"
            return act
        previous = int(ed.get("articles") or self._baseline.get((key, lang)) or 0)
        if previous >= 10 and n_articles < SUSPECT_RATIO * previous:
            report.suspect += 1
            ed["status"], ed["error"] = "suspect", f"{n_articles} articles instead of {previous}; stored text kept"
            report.errors.append(f"{entry.slug}/{lang}: suspect page ({n_articles} vs {previous} articles)")
            return None
        change = {"act": entry.slug, "lang": lang, "lex_id": lex_id, "title": act.title,
                  "articles": n_articles, "previous_articles": int(ed.get("articles") or 0) or None}
        if ed.get("sha256"):
            report.updated += 1
            change["kind"] = "updated"
        else:
            report.added += 1
            change["kind"] = "added"
        report.changes.append(change)
        if not check_only:
            self._bundles().replace(lang, key, records)
            ed.update({"sha256": digest, "articles": n_articles, "changed_at": stamp, "status": change["kind"],
                       "title": act.title, "number": act.number, "adopted": act.adopted})
            ed.pop("error", None)
        else:
            ed["status"] = "changed (not applied)"
        return act

    def _bundles(self) -> SyncBundles:
        if not hasattr(self, "_bundle_cache"):
            self._bundle_cache = SyncBundles(self.corpus_dir)
        return self._bundle_cache

    # -------------------------------------------------------------- run
    async def run(
        self,
        *,
        only: Iterable[str] | None = None,
        check_only: bool = False,
        force: bool = False,
        max_requests: int | None = None,
    ) -> SyncReport:
        if max_requests is not None:
            self.client.max_requests = self.client.requests + max_requests
        report = SyncReport(started=self._now().isoformat(), check_only=check_only)
        queue = self.due(only=set(only) if only else None, force=force)
        done = 0
        try:
            for entry in queue:
                uz_id, ru_id = await self._resolve(entry, report)
                if not uz_id and not ru_id:
                    done += 1
                    continue
                st = self.state.act(entry.slug)
                # The record key stays the same across runs: the catalog id, else the first id ever resolved
                canonical = entry.key or st.get("key") or uz_id or ru_id or ""
                st["key"] = canonical
                if uz_id:
                    uz_act = await self._sync_edition(entry, canonical, "uz", uz_id, report, check_only=check_only,
                                                      force=force)
                    if not ru_id and uz_act is not None and uz_act.editions.get("ru"):
                        ru_id = uz_act.editions["ru"]
                if ru_id:
                    ru_act = await self._sync_edition(entry, canonical, "ru", ru_id, report, check_only=check_only,
                                                      force=force)
                    if not uz_id and ru_act is not None and ru_act.editions.get("uz"):
                        uz_id = ru_act.editions["uz"]
                        await self._sync_edition(entry, canonical, "uz", uz_id, report, check_only=check_only,
                                                 force=force)
                st.update({"uz_id": uz_id, "ru_id": ru_id})
                done += 1
        except SyncBudgetExhausted:
            report.deferred = len(queue) - done
        except httpx.HTTPError as exc:
            report.errors.append(f"network: {exc}")
            report.deferred = len(queue) - done
        report.requests = self.client.requests
        report.bytes = self.client.bytes
        report.finished = self._now().isoformat()
        if not check_only and hasattr(self, "_bundle_cache") and self._bundle_cache.dirty:
            self._bundle_cache.write()
            self._write_catalog()
        self.state.add_run({k: v for k, v in report.as_dict().items() if k not in ("changes", "errors")})
        self.state.save()
        return report

    def _write_catalog(self) -> None:
        """Titles, numbers and ids of the synced acts (merged into the act catalog by the index builder)."""
        docs = []
        for e in self.catalog:
            st = self.state.data["acts"].get(e.slug) or {}
            key = st.get("key") or e.key
            eds = st.get("editions") or {}
            if not key or not any(ed.get("sha256") for ed in eds.values()):
                continue
            uz, ru = eds.get("uz", {}), eds.get("ru", {})
            docs.append({
                "doc_key": key, "uz_id": uz.get("lex_id"), "ru_id": ru.get("lex_id") or st.get("ru_id"),
                "doc_type": _KIND_TO_DOC_TYPE.get(e.kind, "law"), "number_uz": uz.get("number"),
                "number_ru": ru.get("number"), "date": uz.get("adopted") or ru.get("adopted"),
                "title_uz": uz.get("title"), "title_ru": ru.get("title"), "short_uz": e.short_uz or uz.get("title"),
                "short_ru": e.short_ru or ru.get("title"), "articles_uz": uz.get("articles"),
                "articles_ru": ru.get("articles"), "branches": e.branches or ["general"],
                "last_synced": max(ed.get("changed_at") or "" for ed in eds.values()),
            })
        _atomic_write(self.corpus_dir / CATALOG_OUT,
                      (json.dumps({"source": "https://lex.uz (lex-agent sync)", "documents": docs},
                                  ensure_ascii=False, indent=1) + "\n").encode("utf-8"))

    def status(self) -> dict[str, Any]:
        return sync_status(self.corpus_dir, catalog=self.catalog, now=self._now())


def _matches(spec: dict[str, Any], text: str, *, lang: str) -> bool:
    """Whether a found title fits a ``find`` spec: all required words (Russian titles) and the act number."""
    low = text.lower()
    number = str(spec.get("number") or "").strip()
    if number and not re.search(rf"(?<!\d){re.escape(number)}(?!\d)", low):
        return False
    if lang == "ru":
        return all(t.lower() in low for t in spec.get("terms") or [])
    return True  # Uzbek pages are verified by the act number


def sync_status(corpus_dir: Path, *, catalog: list[CatalogEntry] | None = None, now: datetime | None = None) -> dict[str, Any]:
    """Short summary for ``/api/health`` and ``lex-agent sync-status``."""
    path = corpus_dir / STATE_FILE
    catalog = catalog if catalog is not None else (load_sync_catalog() if CATALOG_PATH.exists() else [])
    if not path.exists():
        return {"enabled": True, "last_run": None, "acts_in_catalog": len(catalog), "acts_synced": 0, "due": len(catalog)}
    state = SyncState(path)
    now = now or _now()
    synced = sum(1 for a in state.data["acts"].values() if any(e.get("sha256") for e in a.get("editions", {}).values()))
    due = 0
    for e in catalog:
        last = state.last_checked(e.slug)
        if last is None or now - last >= timedelta(days=MAX_AGE_DAYS.get(e.priority, 14)):
            due += 1
    runs = state.data.get("runs") or []
    statuses = [ed.get("status") for a in state.data["acts"].values() for ed in a.get("editions", {}).values()]
    return {
        "enabled": True,
        "last_run": runs[-1].get("finished") if runs else None,
        "last_run_summary": runs[-1] if runs else None,
        "acts_in_catalog": len(catalog),
        "acts_synced": synced,
        "due": due,
        "failed": statuses.count("failed"),
        "suspect": statuses.count("suspect"),
    }


_UZ_FIXED_ZONE = timezone(timedelta(hours=5), "UTC+05:00")  # Uzbekistan: UTC+5 all year, no DST since 1992


def local_zone(tz_name: str = "Asia/Tashkent") -> tzinfo:
    """IANA time zone, falling back to UTC+05:00 when the system has no zone data (slim containers)."""
    try:
        from zoneinfo import ZoneInfo

        return ZoneInfo(tz_name)
    except Exception:  # ZoneInfoNotFoundError, missing tzdata, invalid key
        logger.warning("Time zone %r is unavailable (install tzdata); using UTC+05:00", tz_name)
        return _UZ_FIXED_ZONE


def next_check_at(now: datetime, hour: int, minute: int = 7) -> datetime:
    """Next local ``hour:minute`` strictly after ``now`` (an aware datetime)."""
    nxt = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    return nxt if nxt > now else nxt + timedelta(days=1)


async def nightly_check_loop(corpus_dir: Path, *, hour: int, rps: float, budget: int,
                             tz_name: str = "Asia/Tashkent") -> None:  # pragma: no cover - long-running
    """In-process nightly *check* (no text is changed on a live server): records which acts changed on lex.uz so
    ``/api/health`` shows how fresh the corpus is. Updates are applied by ``lex-agent sync`` + a redeploy."""
    tz = local_zone(tz_name)
    while True:
        now = datetime.now(tz)
        await asyncio.sleep((next_check_at(now, hour) - now).total_seconds())
        sync = None
        try:
            sync = LexSync(corpus_dir, rps=rps, max_requests=budget)
            report = await sync.run(check_only=True)
            logger.info("Nightly lex.uz check: %s checked, %s changed, %s failed", report.checked,
                        report.updated + report.added, report.failed)
        except Exception as exc:
            logger.warning("Nightly lex.uz check failed: %s", exc)
        finally:
            if sync is not None:
                await sync.close()
