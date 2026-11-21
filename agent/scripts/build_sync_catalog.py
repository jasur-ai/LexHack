#!/usr/bin/env python3
"""Build ``lex_agent/data/lex_sync_catalog.json`` — the ~200 acts the nightly lex.uz sync keeps fresh.

Selection (reproducible from files in the repository):

1. priority 1 — the Constitution, every code, and the laws the situation lexicon or the evaluation set use most;
2. priority 2 — every other act the situation lexicon points to, plus decrees and government resolutions that people
   ask about all the time (traffic rules, pensions, benefits, the minimum wage decrees). Those are not in the
   LawCodex export, so their lex.uz ids are resolved at sync time through the lex.uz search (``find``) and checked
   against the expected number/words before anything is stored;
3. priority 3 — laws on everyday subjects (housing, health, education, transport, consumer and digital matters,
   courts and law enforcement, social protection, business) picked by title keywords.

Each catalog entry carries the Uzbek (canonical) and Russian lex.uz ids from ``data/corpus/catalog.json``.

Usage::

    python scripts/build_sync_catalog.py            # writes lex_agent/data/lex_sync_catalog.json
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lex_agent.knowledge.lexicon import get_lexicon  # noqa: E402

TARGET = 200

# Laws on everyday subjects (Uzbek Cyrillic title words, as in catalog.json)
KEYWORDS = [
    r"мулкчилик", r"ижара", r"ипотека", r"гаров", r"суғурта", r"банк", r"кредит", r"валюта", r"тўлов",
    r"адвокат", r"нотариат", r"суд", r"прокуратура", r"ички ишлар", r"ҳакамлик", r"медиация", r"юридик ёрдам",
    r"ахборот", r"электрон", r"шахсга доир", r"муаллифлик", r"ихтиро", r"товар белги", r"реклама", r"истеъмолчи",
    r"озиқ-овқат", r"соғлиғ", r"тиббий", r"дори", r"наркологик", r"психологик", r"репродуктив", r"ногирон",
    r"таълим", r"мактабгача", r"ёшлар", r"бола", r"хотин-қиз", r"оила", r"пенсия", r"ижтимоий", r"бандлик",
    r"касаба", r"меҳнат", r"уй-жой", r"коммунал", r"кўп квартирали", r"хусусийлаштириш", r"риэлтор",
    r"транспорт", r"автомобиль", r"йўл ҳаракат", r"почта", r"телекоммуникация", r"фуқаролар йиғини", r"маҳалла",
    r"жамоатчилик назорати", r"коррупция", r"манфаатлар тўқнашуви", r"давлат фуқаролик хизмати", r"ҳуқуқий ахборот",
    r"норматив-ҳуқуқий", r"маъмурий тартиб", r"маъмурий қамоқ", r"виждон эркинлиги", r"нодавлат нотижорат",
    r"волонтёр", r"ҳомийлик", r"туризм", r"спорт", r"ёнғин", r"фавқулодда", r"солиқ маслаҳат", r"баҳолаш",
    r"инвестиция", r"тадбиркор", r"хусусий корхона", r"фермер", r"деҳқон", r"кооператив", r"божхона",
    r"фуқаролик ҳолати", r"рўйхатга олиш", r"суд-экспертлик", r"чиқинди", r"ветеринария", r"ҳайвон", r"сув",
    r"атроф-муҳит", r"табиатни муҳофаза", r"жиноят", r"жазо", r"пробация", r"ҳуқуқбузарлик", r"лицензия",
    r"рухсат", r"ўзини ўзи банд",
]
SKIP = re.compile(r"кунини белгилаш|орденини|медалини|унвонини|байрами|ратификац|бюджети|регламенти|депутат|сайлов|"
                  r"Олий Мажлис|мадҳия|байроғи|герби|дипломатия|чақириб олиш|мудофаа доктринаси|Халқаро валюта фонди|"
                  r"Экспорт назорати|аккредитация|Мустақил Давлатлар Ҳамдўстлиги|Автоматлаштирилган банк|"
                  r"экспертизаси тўғрисида|пай фондлари|санация", re.I)

# Decrees and government resolutions people need; resolved by lex.uz search at sync time and verified by
# the expected words (``terms``, all required, matched in lowercase) and, when known, the act number.
FIND = [
    {"slug": "traffic-rules", "kind": "cabinet_resolution", "priority": 2,
     "short_uz": "Йўл ҳаракати қоидалари", "short_ru": "Правила дорожного движения",
     "find": {"query_ru": "Правила дорожного движения", "terms": ["правил", "дорожного движения"]}},
    {"slug": "pension-regulation", "kind": "cabinet_resolution", "priority": 2,
     "short_uz": "Давлат пенсияларини тайинлаш ва тўлаш тартиби", "short_ru": "Порядок назначения и выплаты государственных пенсий",
     "find": {"query_ru": "порядке назначения и выплаты государственных пенсий", "terms": ["назначени", "пенси"]}},
    {"slug": "civil-registry-rules", "kind": "cabinet_resolution", "priority": 2,
     "short_uz": "Фуқаролик ҳолати далолатномаларини қайд этиш қоидалари", "short_ru": "Правила регистрации актов гражданского состояния",
     "find": {"query_ru": "регистрации актов гражданского состояния", "terms": ["актов гражданского состояния"]}},
    {"slug": "low-income-benefits", "kind": "cabinet_resolution", "priority": 2,
     "short_uz": "Кам таъминланган оилаларга ижтимоий нафақа", "short_ru": "Социальные пособия малообеспеченным семьям",
     "find": {"query_ru": "пособий малообеспеченным семьям", "terms": ["малообеспеченн", "пособи"]}},
    {"slug": "unemployment-benefit", "kind": "cabinet_resolution", "priority": 2,
     "short_uz": "Ишсизлик нафақасини тайинлаш ва тўлаш тартиби", "short_ru": "Порядок назначения и выплаты пособия по безработице",
     "find": {"query_ru": "пособия по безработице", "terms": ["пособи", "безработиц"]}},
    {"slug": "social-insurance-benefits", "kind": "cabinet_resolution", "priority": 2,
     "short_uz": "Давлат ижтимоий суғуртаси бўйича нафақалар", "short_ru": "Пособия по государственному социальному страхованию",
     "find": {"query_ru": "пособий по государственному социальному страхованию", "terms": ["пособи", "социальному страхованию"]}},
    {"slug": "driver-licences", "kind": "cabinet_resolution", "priority": 2,
     "short_uz": "Ҳайдовчилик гувоҳномаларини бериш тартиби", "short_ru": "Порядок выдачи водительских удостоверений",
     "find": {"query_ru": "водительских удостоверений", "terms": ["водительск", "удостоверени"]}},
    {"slug": "utilities-rules", "kind": "cabinet_resolution", "priority": 2,
     "short_uz": "Коммунал хизматлардан фойдаланиш қоидалари", "short_ru": "Правила пользования коммунальными услугами",
     "find": {"query_ru": "коммунальных услуг правила", "terms": ["коммунальн", "правил"]}},
    {"slug": "minimum-wage-2026", "kind": "presidential_decree", "priority": 2,
     "short_uz": "Иш ҳақи, пенсия ва нафақалар миқдорини ошириш тўғрисидаги Фармон (ПФ-115)",
     "short_ru": "Указ о повышении заработной платы, пенсий и пособий (УП-115)",
     "find": {"query_ru": "о повышении размеров заработной платы пенсий стипендий и пособий", "number": "115",
              "terms": ["заработной платы", "пенси"]}},
    {"slug": "minimum-wage-2025", "kind": "presidential_decree", "priority": 2, "hint_id": "7553322",
     "short_uz": "Иш ҳақи, пенсия ва нафақалар миқдорини ошириш тўғрисидаги Фармон (ПФ-91)",
     "short_ru": "Указ о повышении заработной платы, пенсий и пособий (УП-91)",
     "find": {"query_ru": "о повышении размеров заработной платы пенсий стипендий и пособий", "number": "91",
              "terms": ["заработной платы", "пенси"]}},
]


def main() -> None:
    catalog = {d["doc_key"]: d for d in json.loads((ROOT / "data/corpus/catalog.json").read_text(encoding="utf-8"))["documents"]}
    lex_use: Counter[str] = Counter()
    for c in get_lexicon().concepts:
        for d in c.target_docs:
            lex_use[d] += 1
    gold_use: Counter[str] = Counter()
    for line in (ROOT / "eval/retrieval_gold.jsonl").read_text(encoding="utf-8").splitlines():
        if line.strip():
            for d, _arts in json.loads(line)["expect"]:
                gold_use[d] += 1

    chosen: dict[str, int] = {}
    for key, d in catalog.items():
        if d["doc_type"] in ("constitution", "code") or lex_use[key] >= 2 or gold_use[key] >= 3:
            chosen[key] = 1
    for key in lex_use:
        if key in catalog and key not in chosen:
            chosen[key] = 2
    keyword_rx = re.compile("|".join(KEYWORDS), re.I)
    room = TARGET - len(chosen) - len(FIND)
    picks = []
    for key, d in catalog.items():
        title = d.get("title_uz") or d.get("short_uz") or ""
        if key in chosen or d["doc_type"] == "constitutional_law" or SKIP.search(title):
            continue
        hits = len(keyword_rx.findall(title))
        if hits:
            picks.append((-hits, -(int((d.get("date") or "0000")[:4]) or 0), key))
    for _h, _y, key in sorted(picks)[: max(0, room)]:
        chosen[key] = 3

    entries = []
    for key, prio in sorted(chosen.items(), key=lambda kv: (kv[1], catalog[kv[0]]["doc_type"] != "constitution",
                                                            catalog[kv[0]]["doc_type"] != "code", kv[0])):
        d = catalog[key]
        entries.append({
            "slug": key,
            "key": key,
            "ru_id": d.get("ru_id"),
            "kind": d["doc_type"],
            "priority": prio,
            "short_uz": d.get("short_uz"),
            "short_ru": d.get("short_ru"),
            "branches": d.get("branches") or [],
            "verified": True,
        })
    for item in FIND:
        entries.append({"key": None, "ru_id": None, "branches": [], "verified": False, **item})

    out = ROOT / "lex_agent/data/lex_sync_catalog.json"
    out.write_text(json.dumps({
        "about": "Acts kept fresh by the nightly lex.uz sync (lex-agent sync). Built by scripts/build_sync_catalog.py.",
        "entries": entries,
    }, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    by_prio = Counter(e["priority"] for e in entries)
    print(f"{len(entries)} acts -> {out} (priority 1: {by_prio[1]}, 2: {by_prio[2]}, 3: {by_prio[3]}; "
          f"resolved by search: {len(FIND)})")


if __name__ == "__main__":
    main()
