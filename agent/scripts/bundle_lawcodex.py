#!/usr/bin/env python3
"""Bundle the LawCodex/uz Markdown export of lex.uz into the agent's compact article-level corpus.

Source: https://github.com/LawCodex/uz — every code and every law of the Republic of Uzbekistan that the
National Database of Legislation (lex.uz) marks as in force, in the current consolidated version, in Uzbek
(Cyrillic, as published) and Russian. Official texts are not objects of copyright (Law O'RQ-42, art. 8).

The script keeps what helps people get answers and drops what only adds noise:

* kept: the Constitution, all codes, every substantive law (constitutional laws included), recent budget laws;
* dropped: amending laws ("... ўзгартиш ва қўшимчалар киритиш тўғрисида" — their content already lives in the
  consolidated texts), treaty ratification laws, old budget laws and Karakalpak-language texts.

Output (``--out``, default ``data/corpus``):

* ``lawcodex_uz.jsonl.gz`` / ``lawcodex_ru.jsonl.gz`` — one JSON record per article (or per document body for
  acts without articles), with amendment provenance notes split from the norm text;
* ``catalog.json`` — one entry per act: Uzbek and Russian lex.uz ids, number, date, type, short titles, branches.

Usage::

    python scripts/bundle_lawcodex.py --src /path/to/LawCodex-uz-checkout --out data/corpus
    python scripts/bundle_lawcodex.py --download            # fetches the pinned commit from GitHub

The optional ``--lex-cache data/lex_cache`` adds the 1992 Constitution (in force until 2023-05-01) from the
live-fetch cache as a historical edition used for questions about earlier dates.
"""

from __future__ import annotations

import argparse
import gzip
import io
import json
import re
import sys
import tarfile
import urllib.request
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

LAWCODEX_REPO = "LawCodex/uz"
LAWCODEX_COMMIT = "4d5c4b381352f860f5b4b93dc72a1fb9e13a0a43"  # retrieved 2026-10-12
SNAPSHOT = "2026-10-12"

_SUP = str.maketrans("0123456789", "⁰¹²³⁴⁵⁶⁷⁸⁹")
_UNSUP = str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹", "0123456789")

# Codes: Uzbek lex.uz id -> Russian lex.uz id (each language edition has its own id on lex.uz)
CODE_RU_IDS: dict[str, str] = {
    "6445145": "6445147",  # Constitution
    "2304138": "2304140",  # Budget
    "3523891": "3523895",  # Economic procedure
    "5307951": "5307955",  # Urban planning
    "111189": "111181",  # Civil, part I
    "180552": "180550",  # Civil, part II
    "3517337": "3517334",  # Civil procedure
    "4386848": "4386846",  # Election
    "106136": "106134",  # Housing
    "3527353": "3527365",  # Administrative court procedure
    "97664": "97661",  # Administrative responsibility
    "4674902": "4674893",  # Tax
    "104720": "104723",  # Family
    "2876354": "2876352",  # Customs
    "6257288": "6257291",  # Labour
    "111453": "111457",  # Criminal
    "163629": "163627",  # Criminal-executive
    "111460": "111463",  # Criminal procedure
    "7655343": "7658581",  # Water
    "55594": "55599",  # Air
    "152653": "149947",  # Land
}

# Short names people actually use (Uzbek Cyrillic as on lex.uz, Russian) for codes, keyed by Uzbek id.
CODE_SHORT: dict[str, tuple[str, str]] = {
    "6445145": ("Конституция", "Конституция"),
    "2304138": ("Бюджет кодекси", "Бюджетный кодекс"),
    "3523891": ("Иқтисодий процессуал кодекс", "Экономический процессуальный кодекс"),
    "5307951": ("Шаҳарсозлик кодекси", "Градостроительный кодекс"),
    "111189": ("Фуқаролик кодекси (1-қисм)", "Гражданский кодекс (часть I)"),
    "180552": ("Фуқаролик кодекси (2-қисм)", "Гражданский кодекс (часть II)"),
    "3517337": ("Фуқаролик процессуал кодекси", "Гражданский процессуальный кодекс"),
    "4386848": ("Сайлов кодекси", "Избирательный кодекс"),
    "106136": ("Уй-жой кодекси", "Жилищный кодекс"),
    "3527353": ("Маъмурий суд ишларини юритиш тўғрисидаги кодекс", "Кодекс об административном судопроизводстве"),
    "97664": ("Маъмурий жавобгарлик тўғрисидаги кодекс", "Кодекс об административной ответственности"),
    "4674902": ("Солиқ кодекси", "Налоговый кодекс"),
    "104720": ("Оила кодекси", "Семейный кодекс"),
    "2876354": ("Божхона кодекси", "Таможенный кодекс"),
    "6257288": ("Меҳнат кодекси", "Трудовой кодекс"),
    "111453": ("Жиноят кодекси", "Уголовный кодекс"),
    "163629": ("Жиноят-ижроия кодекси", "Уголовно-исполнительный кодекс"),
    "111460": ("Жиноят-процессуал кодекси", "Уголовно-процессуальный кодекс"),
    "7655343": ("Сув кодекси", "Водный кодекс"),
    "55594": ("Ҳаво кодекси", "Воздушный кодекс"),
    "152653": ("Ер кодекси", "Земельный кодекс"),
}

CODE_BRANCHES: dict[str, list[str]] = {
    "6445145": ["constitutional"],
    "111189": ["civil"],
    "180552": ["civil"],
    "111453": ["criminal"],
    "111460": ["procedural_criminal"],
    "163629": ["criminal"],
    "97664": ["administrative"],
    "6257288": ["labor"],
    "4674902": ["tax"],
    "3517337": ["procedural_civil"],
    "3523891": ["procedural_economic"],
    "3527353": ["procedural_admin"],
    "2876354": ["customs"],
    "104720": ["family"],
    "106136": ["housing"],
    "2304138": ["banking_finance"],
    "7655343": ["environmental_natural"],
    "55594": ["general"],
    "4386848": ["constitutional"],
    "152653": ["land_real_estate"],
    "5307951": ["land_real_estate"],
}

# Branch tagging for laws: (Uzbek-Cyrillic / Russian title regex, branch). First matches win (max 2 branches).
_BRANCH_RULES: list[tuple[str, str]] = [
    (r"меҳнат|бандлик|касаба|трудов|занятост|профсоюз|меҳнатни муҳофаза|охрана труда", "labor"),
    (r"оила|никоҳ|болалар|бола ҳуқуқ|ёшлар|семь|брак|ребен|детей|молодеж", "family"),
    (r"солиқ|налог", "tax"),
    (r"божхона|ташқи иқтисодий|таможен|внешнеэкономическ", "customs"),
    (r"жиноят|терроризм|экстремизм|коррупция|гиёҳванд|одам савдоси|уголовн|террориз|экстремиз|коррупци|наркот|торговл\w* людьми|оператив-қидирув|оперативно-розыскн", "criminal"),
    (r"банк|кредит|валюта|суғурта|қимматли қоғоз|тўлов|молия|аудит|бухгалтер|лизинг|микромолия|страхов|ценных бумаг|платеж|финанс|бухгалтерск|лизинг|микрофинанс", "banking_finance"),
    (r"уй-жой|турар жой|коммунал|кўп квартирали|жилищ|жил\w* помещ|коммунальн|многоквартирн", "housing"),
    (r"ер |ерга|ердан|кадастр|кўчмас мулк|давлат рўйхатидан ўтказиш|земел|кадастр|недвижим", "land_real_estate"),
    (r"таълим|соғлиқ|тиббий|ижтимоий|пенсия|ногирон|фуқароларнинг соғлиғи|санитария|образован|здоровь|медицин|социальн|пенси|инвалид|санитарн", "social_education_health"),
    (r"тадбиркор|корхона|акциядорлик|масъулияти чекланган|рақобат|истеъмолчи|хўжалик юритувчи|лицензия|рухсат бериш|предприним|акционерн|ограниченной ответственност|конкуренц|потребител|хозяйствующ|лицензир|разрешительн", "corporate_commercial"),
    (r"ахборот|электрон|шахсга доир|телекоммуникация|рақамли|киберхавфсизлик|информац|электронн|персональн|телекоммуникац|цифров|кибербезопасност", "digital_it_data"),
    (r"экология|атроф-муҳит|табиат|ўрмон|ҳайвонот|ўсимлик|чиқинди|сув |экологич|окружающ|природ|лес|животн|растительн|отход", "environmental_natural"),
    (r"суд|адвокат|нотариат|прокуратура|ички ишлар|ижро|ҳуқуқни муҳофаза|нотариат|адвокат|прокуратур|внутренних дел|исполнени\w* судебн|правоохранит", "procedural_admin"),
    (r"мудофаа|ҳарбий|чегара|давлат хавфсизлиги|оборон|воинск|военн|границ|государственной безопасност", "defense_security"),
    (r"инвестиция|давлат-хусусий шериклик|эркин иқтисодий|инвестиц|государственно-частн|свободн\w* экономическ", "investment_ppp"),
    (r"интеллектуал|муаллифлик|ихтиро|товар белгиси|интеллектуальн|авторск|изобретен|товарн\w* знак", "intellectual_property"),
    (r"сайлов|референдум|конституциявий|парламент|олий мажлис|выбор|референдум|конституционн|олий мажлис", "constitutional"),
    (r"маъмурий|маъмурий тартиб|мурожаат|административн|обращени", "administrative"),
    (r"фуқаролик|мулк|шартнома|граждан|собственност|договор", "civil"),
]
_BRANCH_COMPILED = [(re.compile(rx, re.I), br) for rx, br in _BRANCH_RULES]

_AMEND_RE = re.compile(
    r"ўзгартиш|ўзгартириш|қўшимча\w*\s+киритиш|кучини йўқотган|изменени|дополнени|утратившим|признании утратив",
    re.I,
)
_RATIFY_RE = re.compile(r"ратификац|ратифика|қўшилиш|присоединени", re.I)
_BUDGET_RE = re.compile(r"(?:(\d{4})\s+йил учун .*давлат бюджети|государственном бюджете .* на (\d{4}) год)", re.I)

_ADOPTION_LINE_RE = re.compile(
    r"^(?:Қонунчилик палатаси томонидан|Сенат томонидан|Принят Законодательной палатой|Одобрен Сенатом|"
    r"Ўзбекистон Республикаси Олий Мажлиси|Олий Мажлис)",
    re.I,
)

# Article markers (headings or plain paragraphs). Superscripts were flattened by the export (104¹ -> 1041),
# so ids are resolved against the running article sequence afterwards.
_UZ_ART_RE = re.compile(r"^(\d+(?:[¹²³⁴⁵⁶⁷⁸⁹⁰]+|[-.]\d+)?)\s*-\s*модда\.?\s*(.*)$", re.I)
_RU_ART_RE = re.compile(r"^Статья\s+(\d+(?:[¹²³⁴⁵⁶⁷⁸⁹⁰]+|[-.]\d+)?)\.?\s*(.*)$", re.I)
_CHAPTER_RE = re.compile(r"^(?:\d+[-\s]*боб|глава\s+\d+|[IVXLC]+\s*боб|боб\s+\d+)", re.I)
_SECTION_RE = re.compile(r"^(?:[IVXLC\d]+[-\s]*бўлим|раздел\s+[IVXLC\d]+|бўлим)", re.I)
_PART_RE = re.compile(r"^(?:умумий қисм|махсус қисм|общая часть|особенная часть|[IVXLC\d]+[-\s]*қисм|часть\s+[IVXLC\d]+)", re.I)


@dataclass
class Article:
    raw_id: str
    title: str
    section: str | None
    chapter: str | None
    lines: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    article_id: str = ""
    display: str = ""


@dataclass
class Doc:
    lang: str  # "uz" | "ru"
    lex_id: str
    path: str
    meta: dict[str, str]
    body: str
    title: str = ""
    number: str | None = None
    date: str | None = None
    doc_type: str = "law"
    category: str = "substantive"


def parse_front_matter(text: str) -> tuple[dict[str, str], str]:
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not m:
        return {}, text
    meta: dict[str, str] = {}
    for line in m.group(1).splitlines():
        key, _, value = line.partition(":")
        meta[key.strip()] = value.strip().strip('"')
    return meta, text[m.end():]


def _fix_case(title: str, lang: str) -> str:
    """Sentence-case ALL-CAPS titles while keeping proper names capitalised."""
    t = re.sub(r"\s+", " ", title).strip()
    letters = [c for c in t if c.isalpha()]
    if not letters or sum(c.isupper() for c in letters) / len(letters) < 0.8:
        return t
    low = t.lower()
    low = low[:1].upper() + low[1:]
    proper_uz = [
        "ўзбекистон", "қорақалпоғистон", "тошкент", "олий мажлис", "вазирлар маҳкамаси", "конституция",
        "республикаси", "республикасининг", "республикасида", "республикасига", "республикасидан", "россия",
        "қозоғистон", "қирғизистон", "тожикистон", "туркманистон", "мустақил давлатлар ҳамдўстлиги",
    ]
    proper_ru = [
        "республики узбекистан", "республике узбекистан", "республикой узбекистан", "республика узбекистан",
        "узбекистан", "узбекской сср", "узбекская сср", "олий мажлис", "кабинет министров", "каракалпакстан",
        "конституци", "ташкент", "российской федерации", "содружества независимых государств",
    ]
    for word in proper_uz if lang == "uz" else proper_ru:
        low = re.sub(
            rf"(?<![\w]){re.escape(word)}",
            lambda m: " ".join(w[:1].upper() + w[1:] for w in m.group(0).split(" ")),
            low,
        )
    return low


def _short_title(doc: Doc, uz_key: str) -> str:
    if uz_key in CODE_SHORT:
        return CODE_SHORT[uz_key][0 if doc.lang == "uz" else 1]
    t = doc.title
    t = t[:1].upper() + t[1:]
    if doc.lang == "uz":
        t = re.sub(r"^Ўзбекистон Республикасининг\s+", "", t)
        t = t[:1].upper() + t[1:]
        if re.search(r"тўғрисида$", t):
            return re.sub(r"тўғрисида$", "тўғрисидаги Қонун", t)
        if re.search(r"ҳақида$", t):
            return re.sub(r"ҳақида$", "ҳақидаги Қонун", t)
        return f"{t} (Қонун)"
    t = re.sub(r"\s*Республики Узбекистан$", "", t)
    if t.lower().startswith(("о ", "об ", "обо ")):
        return f"Закон «{t}»"
    return f"{t} (Закон)"


def _branches(uz_key: str, titles: list[str]) -> list[str]:
    if uz_key in CODE_BRANCHES:
        return CODE_BRANCHES[uz_key]
    out: list[str] = []
    text = " ".join(titles).lower()
    for rx, br in _BRANCH_COMPILED:
        if rx.search(text) and br not in out:
            out.append(br)
        if len(out) >= 2:
            break
    return out or ["general"]


def _norm_number(number: str | None) -> str | None:
    if not number:
        return None
    n = number.upper().replace(" ", "")
    n = n.replace("ЎРҚ", "ORQ").replace("ЗРУ", "ORQ").replace("Х", "X").replace("І", "I")
    n = n.strip("-")
    return n


_KARAKALPAK_RE = re.compile(r"^Өзбекстан|Қарақалпақстан Республикасы|\bӨРН-", re.I)
# Laws that only enact a code ("…кодексини тасдиқлаш тўғрисида", "Об утверждении … кодекса"): a few procedural
# articles that would otherwise compete with the code itself in search results.
_ENACT_CODE_RE = re.compile(
    r"кодекс\w*(?:\s+[\w-]+){0,2}\s+тасдиқлаш|кодекс\w*\s+амалга киритиш|утверждении\s+[\w\s-]*кодекса|"
    r"введении в действие",
    re.I,
)


def classify(doc: Doc) -> str:
    title = doc.title
    path = doc.path
    if "/karakalpakstan/" in path or "/qoraqalpogiston/" in path or "saylao-kodeksi" in path:
        return "karakalpak"
    if _KARAKALPAK_RE.search(title) or _KARAKALPAK_RE.search(doc.number or "") or "Ө" in (doc.number or ""):
        return "karakalpak"
    if doc.meta.get("type") in ("code", "constitution"):
        return "substantive"
    if _ENACT_CODE_RE.search(title):
        return "enact"
    if _AMEND_RE.search(title):
        return "amend"
    if _RATIFY_RE.search(title):
        return "ratify"
    m = _BUDGET_RE.search(title)
    if m:
        year = int(m.group(1) or m.group(2))
        return "budget" if year >= 2025 else "old_budget"
    return "substantive"


# Laws that restate another law "in a new edition" print the full current text as an annex, introduced by a
# "(янги таҳрири)" / "(новая редакция)" line (e.g. ЎРҚ-445 = the in-force law on appeals of individuals and legal
# entities, ЎРҚ-580 = the banking law). Those annexes are substantive law, not amendments.
_EDITION_MARK_RE = re.compile(r"^>?\s*\((?:янги\s+таҳрири|новая\s+редакция)\)\s*$", re.M | re.I)
_QUOTED_TITLE_RE = re.compile(r"«(.+?)»")


def new_edition_annex(doc: Doc) -> tuple[str, str] | None:
    """(annex body, restated law title) for a new-edition law, else None."""
    if doc.category != "amend":
        return None
    marks = list(_EDITION_MARK_RE.finditer(doc.body))
    m_title = _QUOTED_TITLE_RE.search(doc.title)
    if len(marks) != 1 or not m_title:
        return None
    annex = doc.body[marks[0].end():]
    articles, _pre, _notes = parse_articles(annex, doc.lang)
    if len(articles) < 10:
        return None
    title = m_title.group(1).strip()
    return annex, title[:1].upper() + title[1:]


def _resolve_ids(articles: list[Article], lang: str) -> None:
    """Rebuild article numbers whose superscript was flattened (104¹ exported as '1041')."""
    last_base: int | None = None
    for idx, art in enumerate(articles):
        raw = art.raw_id.translate(_UNSUP) if any(ch in art.raw_id for ch in "¹²³⁴⁵⁶⁷⁸⁹⁰") else art.raw_id
        base: int
        sup: int | None = None
        if any(ch in art.raw_id for ch in "¹²³⁴⁵⁶⁷⁸⁹⁰"):
            digits = re.match(r"(\d+)([¹²³⁴⁵⁶⁷⁸⁹⁰]+)", art.raw_id)
            assert digits is not None
            base, sup = int(digits.group(1)), int(digits.group(2).translate(_UNSUP))
        elif re.match(r"^\d+[-.]\d+$", raw):
            a, b = re.split(r"[-.]", raw)
            base, sup = int(a), int(b)
        else:
            n = int(raw)
            base = n
            if last_base is not None and not (last_base < n <= last_base + 6):
                # "1411" after article 141 is 141¹; "1861" after 185² is 186¹ (186 itself may be repealed)
                for cand in range(last_base, last_base + 7):
                    prefix = str(cand)
                    rest = raw[len(prefix):]
                    if raw.startswith(prefix) and 0 < len(rest) <= 2 and not rest.startswith("0"):
                        base, sup = cand, int(rest)
                        break
        last_base = base
        art.article_id = f"{base}.{sup}" if sup else str(base)
        sup_txt = str(sup).translate(_SUP) if sup else ""
        art.display = f"{base}{sup_txt}-модда" if lang == "uz" else f"Статья {base}{sup_txt}"


def parse_articles(body: str, lang: str) -> tuple[list[Article], list[str], list[str]]:
    """Split a LawCodex Markdown body into articles; returns (articles, preamble lines, document notes)."""
    art_re = _UZ_ART_RE if lang == "uz" else _RU_ART_RE
    articles: list[Article] = []
    preamble: list[str] = []
    doc_notes: list[str] = []
    section: str | None = None
    chapter: str | None = None
    current: Article | None = None
    for raw_line in body.splitlines():
        s = raw_line.strip()
        if not s:
            continue
        if s.startswith("#"):
            level = len(s) - len(s.lstrip("#"))
            heading = s.lstrip("#").strip()
            if level == 1:
                continue
            m = art_re.match(heading)
            if m:
                current = Article(raw_id=m.group(1), title=m.group(2).strip().rstrip("."), section=section, chapter=chapter)
                articles.append(current)
                continue
            current = None
            if _CHAPTER_RE.match(heading):
                chapter = heading
            elif _SECTION_RE.match(heading) or _PART_RE.match(heading):
                section = heading
                chapter = None
            else:
                chapter = heading
            continue
        if s.startswith(">"):
            note = s.lstrip("> ").strip()
            if note:
                (current.notes if current else doc_notes).append(note)
            continue
        m = art_re.match(s)
        if m and (len(m.group(2)) < 400):
            current = Article(raw_id=m.group(1), title=m.group(2).strip().rstrip("."), section=section, chapter=chapter)
            articles.append(current)
            continue
        if current is not None:
            current.lines.append(s)
        elif not _ADOPTION_LINE_RE.match(s):
            preamble.append(s)
    _resolve_ids(articles, lang)
    return articles, preamble, doc_notes


_SIGNATURE_RE = re.compile(
    r"^(?:Ўзбекистон Республикаси(?:нинг)? Президенти|Президент Республики Узбекистан|"
    r"Ўзбекистон Республикаси Олий Мажлиси|Председатель Олий Мажлиса)\b",
)
_ANNEX_RE = re.compile(r"^(?:\d+\s*-?\s*)?(?:ИЛОВА|Илова|ПРИЛОЖЕНИЕ|Приложение)(?:\s*(?:№\s*)?\d+)?\.?$")
_TAG_RE = re.compile(r"<[^>]+>")
_TR_RE = re.compile(r"<tr[^>]*>(.*?)</tr>", re.S | re.I)
_TD_RE = re.compile(r"<t[dh][^>]*>(.*?)</t[dh]>", re.S | re.I)


def html_tables_to_text(line: str) -> list[str]:
    """Rows of an HTML table as plain text lines ("cell — cell"); other markup is stripped."""
    if "<" not in line:
        return [line]
    out: list[str] = []
    rows = _TR_RE.findall(line)
    if rows:
        for row in rows:
            cells = [re.sub(r"\s+", " ", _TAG_RE.sub(" ", c)).strip() for c in _TD_RE.findall(row)]
            cells = [c for c in cells if c]
            if cells:
                out.append(" — ".join(cells))
        return out
    text = re.sub(r"\s+", " ", _TAG_RE.sub(" ", line.replace("<br>", "\n"))).strip()
    return [text] if text else []


def split_signature_and_annexes(articles: list[Article], lang: str) -> list[Article]:
    """Drop the signature block of the last article and turn trailing annexes into their own records."""
    if not articles:
        return []
    last = articles[-1]
    sig = next((i for i, line in enumerate(last.lines) if _SIGNATURE_RE.match(line)), None)
    annexes: list[Article] = []
    if sig is not None:
        tail = last.lines[sig:]
        last.lines = last.lines[:sig]
        current: Article | None = None
        header: list[str] = []
        for line in tail:
            if _ANNEX_RE.match(line):
                n = len(annexes) + 1
                current = Article(raw_id=f"annex{n}", title="", section=None, chapter=None)
                current.article_id = f"annex{n}" if n > 1 else "annex"
                current.display = ("Илова" if lang == "uz" else "Приложение") + (f" {n}" if n > 1 else "")
                annexes.append(current)
                header = []
                continue
            if current is None:
                header.append(line)  # place, date and number of the signed act; dropped
                continue
            if not current.title and line.startswith("**"):
                current.title = line.strip("* ").strip()
                continue
            current.lines.append(line)
    for art in articles + annexes:
        cleaned: list[str] = []
        for line in art.lines:
            cleaned.extend(html_tables_to_text(line))
        art.lines = cleaned
    return articles + [a for a in annexes if a.lines]


def _note_summary(notes: list[str]) -> list[dict[str, str]]:
    """Keep amendment provenance compact: the amending act number and the dates it mentions."""
    out: list[dict[str, str]] = []
    for note in notes[-6:]:
        acts = re.findall(r"(?:ЎРҚ|ЗРУ|O'RQ)-\d+", note)
        dates = re.findall(r"(\d{1,2}\.\d{2}\.\d{4})", note)
        eff = re.search(r"(?:Кучга кириш санаси|Дата вступления в силу)\s*[—-]\s*([^)]+)", note)
        out.append(
            {
                "act": acts[0] if acts else "",
                "published": dates[0] if dates else "",
                "effective": eff.group(1).strip() if eff else "",
                "text": note[:400],
            }
        )
    return out


def load_docs(src: Path) -> list[Doc]:
    docs: list[Doc] = []
    for lang in ("uz", "ru"):
        for path in sorted((src / lang).rglob("*.md")):
            text = path.read_text(encoding="utf-8")
            meta, body = parse_front_matter(text)
            ident = meta.get("identifier", "")
            m = re.search(r"(\d+)$", ident)
            if not m:
                continue
            doc = Doc(lang=lang, lex_id=m.group(1), path=str(path.relative_to(src)), meta=meta, body=body)
            doc.title = _fix_case(meta.get("title", "").strip(), lang)
            doc.number = (meta.get("number") or "").strip() or None
            doc.date = (meta.get("date") or "").strip() or None
            citation = (meta.get("citation") or "").lower()
            if meta.get("type") == "constitution":
                doc.doc_type = "constitution"
            elif meta.get("type") == "code":
                doc.doc_type = "code"
            elif "конституциявий" in citation or "конституционный" in citation:
                doc.doc_type = "constitutional_law"
            else:
                doc.doc_type = "law"
            doc.category = classify(doc)
            if doc.category == "amend":
                annex = new_edition_annex(doc)
                if annex is not None:
                    doc.category = "new_edition"
                    doc.body = annex[0]
                    restated = annex[1]
                    if lang == "uz" and not restated.startswith("Ўзбекистон"):
                        restated = f"Ўзбекистон Республикасининг {restated}"
                    doc.title = restated
            docs.append(doc)
    return docs


def link_editions(docs: list[Doc]) -> dict[str, str]:
    """Map Russian lex.uz ids to the Uzbek id of the same act (codes by table, laws by number + date)."""
    ru_to_uz: dict[str, str] = {ru: uz for uz, ru in CODE_RU_IDS.items()}
    uz_by_key: dict[tuple[str | None, str | None], str] = {}
    uz_by_num: dict[str, list[str]] = defaultdict(list)
    for d in docs:
        if d.lang == "uz" and d.doc_type not in ("code", "constitution"):
            n = _norm_number(d.number)
            uz_by_key[(n, d.date)] = d.lex_id
            if n:
                uz_by_num[n].append(d.lex_id)
    for d in docs:
        if d.lang != "ru" or d.lex_id in ru_to_uz or d.doc_type in ("code", "constitution"):
            continue
        n = _norm_number(d.number)
        uz = uz_by_key.get((n, d.date))
        if uz is None and n and len(uz_by_num.get(n, [])) == 1:
            uz = uz_by_num[n][0]
        if uz:
            ru_to_uz[d.lex_id] = uz
    return ru_to_uz


def build(src: Path, out: Path, lex_cache: Path | None) -> dict[str, Any]:
    docs = load_docs(src)
    ru_to_uz = link_editions(docs)
    uz_docs = {d.lex_id: d for d in docs if d.lang == "uz"}
    cats = Counter((d.lang, d.category) for d in docs)

    catalog: dict[str, dict[str, Any]] = {}
    writers = {
        "uz": gzip.open(out / "lawcodex_uz.jsonl.gz", "wt", encoding="utf-8", compresslevel=9),
        "ru": gzip.open(out / "lawcodex_ru.jsonl.gz", "wt", encoding="utf-8", compresslevel=9),
    }
    counts: Counter[str] = Counter()
    try:
        for d in docs:
            if d.category not in ("substantive", "budget", "new_edition"):
                continue
            uz_key = d.lex_id if d.lang == "uz" else ru_to_uz.get(d.lex_id, f"ru{d.lex_id}")
            entry = catalog.setdefault(
                uz_key,
                {
                    "doc_key": uz_key,
                    "uz_id": None,
                    "ru_id": None,
                    "doc_type": d.doc_type,
                    "number_uz": None,
                    "number_ru": None,
                    "date": d.date,
                    "title_uz": None,
                    "title_ru": None,
                    "short_uz": None,
                    "short_ru": None,
                    "articles_uz": 0,
                    "articles_ru": 0,
                    "last_amended": None,
                },
            )
            short = _short_title(d, uz_key)
            entry[f"{d.lang}_id"] = d.lex_id
            entry[f"title_{d.lang}"] = d.title
            entry[f"short_{d.lang}"] = short
            entry[f"number_{d.lang}"] = d.number
            entry["date"] = entry["date"] or d.date

            articles, preamble, doc_notes = parse_articles(d.body, d.lang)
            articles = split_signature_and_annexes(articles, d.lang)
            if d.category == "new_edition":
                preamble = []  # the enacting formula of the amending act is not part of the restated law
            lang_code = "uz_cyrl" if d.lang == "uz" else "ru"
            base = {
                "source": f"lawcodex_{d.lang}",
                "lang": lang_code,
                "doc_key": uz_key,
                "lex_doc_id": d.lex_id,
                "doc_title": d.title,
                "short_title": short,
                "doc_number": d.number,
                "doc_type": d.doc_type,
                "adopted": d.date,
                "snapshot": SNAPSHOT,
            }
            records: list[dict[str, Any]] = []
            pre_text = "\n".join(preamble).strip()
            if articles:
                if len(pre_text) >= 160:
                    records.append({**base, "article_id": "_front", "article_display": None, "article_title": None,
                                    "section": None, "chapter": None, "text": pre_text})
                seen_ids: Counter[str] = Counter()
                for art in articles:
                    text = "\n".join(art.lines).strip()
                    if not text and not art.title:
                        continue
                    seen_ids[art.article_id] += 1
                    rec = {
                        **base,
                        "article_id": art.article_id,
                        "article_display": art.display,
                        "article_title": art.title or None,
                        "section": art.section,
                        "chapter": art.chapter,
                        "text": text or art.title,
                    }
                    if seen_ids[art.article_id] > 1:
                        # Annexes restart numbering ("1-модда" again): keep both, with a unique record key
                        rec["occurrence"] = seen_ids[art.article_id]
                    if art.notes:
                        rec["notes"] = _note_summary(art.notes)
                        last = rec["notes"][-1]
                        if last.get("published"):
                            entry["last_amended"] = max(
                                entry["last_amended"] or "", "-".join(reversed(last["published"].split(".")))
                            )
                    records.append(rec)
            elif pre_text:
                records.append({**base, "article_id": None, "article_display": None, "article_title": None,
                                "section": None, "chapter": None, "text": pre_text})
            if doc_notes:
                entry.setdefault("notes", _note_summary(doc_notes)[-2:])
            entry[f"articles_{d.lang}"] = sum(1 for r in records if r.get("article_display"))
            for rec in records:
                writers[d.lang].write(json.dumps(rec, ensure_ascii=False) + "\n")
                counts[d.lang] += 1
    finally:
        for w in writers.values():
            w.close()

    for key, entry in catalog.items():
        titles = [entry.get("title_uz") or "", entry.get("title_ru") or ""]
        entry["branches"] = _branches(key, titles)

    historical = 0
    if lex_cache is not None:
        historical = bundle_historical_constitution(lex_cache, out)

    catalog_list = sorted(catalog.values(), key=lambda e: (e["doc_type"] != "constitution", e["doc_type"] != "code", e.get("date") or ""))
    (out / "catalog.json").write_text(
        json.dumps(
            {
                "source": f"https://github.com/{LAWCODEX_REPO}/tree/{LAWCODEX_COMMIT}",
                "snapshot": SNAPSHOT,
                "license": "Official texts are not objects of copyright (Law of the Republic of Uzbekistan "
                "'On Copyright and Related Rights', art. 8)",
                "documents": catalog_list,
            },
            ensure_ascii=False,
            indent=1,
        ),
        encoding="utf-8",
    )
    return {
        "categories": {f"{k[0]}:{k[1]}": v for k, v in sorted(cats.items())},
        "documents": len(catalog),
        "linked_ru": sum(1 for e in catalog.values() if e.get("uz_id") and e.get("ru_id")),
        "records": dict(counts),
        "historical_records": historical,
        "uz_only": sum(1 for e in catalog.values() if e.get("uz_id") and not e.get("ru_id")),
        "ru_only": sum(1 for e in catalog.values() if e.get("ru_id") and not e.get("uz_id")),
        "uz_docs_total": len(uz_docs),
    }


def bundle_historical_constitution(lex_cache: Path, out: Path) -> int:
    """The 1992 Constitution (Uzbek, Cyrillic) from the live-fetch cache, valid until 2023-05-01."""
    path = next((p for p in (lex_cache / f"doc_{lang}_20596.json" for lang in ("uz", "ru", "en")) if p.exists()), None)
    if path is None:
        return 0
    data = json.loads(path.read_text(encoding="utf-8"))
    noise = (
        "hujjatga taklif yuborish", "audioni tinglash", "hujjat elementidan havola olish",
        "предложения по документу", "прослушать аудио", "получить ссылку из элемента документа",
        "suggestion to the document", "listen to audio", "get a link from a document element",
        "олдинги таҳрирга қаранг",
    )
    lines = []
    skip_commentary = False
    for line in str(data.get("raw_text") or "").splitlines():
        s = line.strip()
        low = s.lower()
        if not s or any(n in low for n in noise):
            continue
        if low.startswith("lexuz шарҳи") or low.startswith("lexuz sharhi"):
            skip_commentary = True  # the next "Қаранг: ..." line is an editorial cross-reference
            continue
        if skip_commentary and low.startswith(("қаранг", "qarang")):
            skip_commentary = False
            continue
        skip_commentary = False
        if re.match(r"^\d+\.\s+(?:\d{2}\.){3}\d{2}\s", s) or re.match(r"^\d+\.\s+[^\n]{3,120}/[^\n]{3,200}\]$", s):
            continue
        lines.append(s)
    body = "\n".join(lines)
    articles, _, _ = parse_articles(body, "uz")
    base = {
        "source": "lex_uz_historical",
        "lang": "uz_cyrl",
        "doc_key": "20596",
        "lex_doc_id": "20596",
        "doc_title": "Ўзбекистон Республикасининг Конституцияси (1992 йил 8 декабрь, 2023 йил 1 майгача амал қилган)",
        "short_title": "Конституция (1992 йилги таҳрир)",
        "doc_number": None,
        "doc_type": "constitution",
        "adopted": "1992-12-08",
        "expiry": "2023-05-01",
        "status": "repealed",
        "snapshot": "2023-04-30",
    }
    n = 0
    with gzip.open(out / "historical_uz.jsonl.gz", "wt", encoding="utf-8", compresslevel=9) as fh:
        for art in articles:
            text = "\n".join(art.lines).strip()
            if not text:
                continue
            rec = {**base, "article_id": art.article_id, "article_display": art.display,
                   "article_title": art.title or None, "section": art.section, "chapter": art.chapter, "text": text}
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            n += 1
    return n


def download(dest: Path) -> Path:
    url = f"https://codeload.github.com/{LAWCODEX_REPO}/tar.gz/{LAWCODEX_COMMIT}"
    print(f"Downloading {url} ...", file=sys.stderr)
    with urllib.request.urlopen(url, timeout=300) as resp:  # noqa: S310 - pinned https URL
        payload = resp.read()
    dest.mkdir(parents=True, exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(payload), mode="r:gz") as tar:
        members = []
        for m in tar.getmembers():
            parts = m.name.split("/", 1)
            if len(parts) < 2 or not parts[1]:
                continue
            m.name = parts[1]
            members.append(m)
        tar.extractall(dest, members=members, filter="data")
    return dest


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--src", type=Path, help="Path to a LawCodex/uz checkout")
    ap.add_argument("--download", action="store_true", help="Download the pinned LawCodex/uz commit first")
    ap.add_argument("--out", type=Path, default=Path("data/corpus"))
    ap.add_argument("--lex-cache", type=Path, default=None, help="data/lex_cache (adds the 1992 Constitution)")
    args = ap.parse_args()
    src = args.src
    if args.download:
        src = download(Path(args.src or "/tmp/lawcodex-uz"))
    if src is None or not (src / "uz").exists():
        ap.error("Provide --src pointing to a LawCodex/uz checkout, or --download")
    args.out.mkdir(parents=True, exist_ok=True)
    stats = build(src, args.out, args.lex_cache)
    print(json.dumps(stats, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
