"""False and outdated premises: articles that do not exist, invented codes and numbers, repealed rules."""

from __future__ import annotations

from pathlib import Path

import pytest

from lex_agent.assistant.premises import TEMPORAL_RULES, PremiseChecker
from lex_agent.config import get_settings
from lex_agent.retrieval.act_resolver import ActResolver, _article_ids
from lex_agent.retrieval.bm25_store import BM25Store

CORPUS = Path(__file__).resolve().parents[1] / "data" / "corpus"


def _span(first: int, last: int) -> frozenset[str]:
    return frozenset(str(i) for i in range(first, last + 1))


# Article ranges of the real acts (the bundled index has the same last articles)
INVENTORY = {
    "104720": _span(1, 238), "111453": _span(1, 302), "111189": _span(1, 385), "180552": _span(386, 1199),
    "4674902": _span(1, 483), "6445145": _span(1, 155), "6257288": _span(1, 593), "97664": _span(1, 348),
    "152653": _span(1, 91), "106136": _span(1, 141), "4396419": _span(1, 36) | {"27.1"},
}


@pytest.fixture(scope="module")
def checker() -> PremiseChecker:
    return PremiseChecker(ActResolver.from_corpus(CORPUS), lambda: INVENTORY)


@pytest.mark.parametrize(
    ("lang", "question", "needles"),
    [
        ("uz_latn", "Oila kodeksining 412-moddasiga ko'ra ajrashganda uy hayvonlari qanday bo'linadi?", ["412", "mavjud emas", "238"]),
        ("ru", "Какое наказание предусмотрено статьей 510 Уголовного кодекса за VPN?", ["510", "не существует", "302 статьи"]),
        ("en", "Explain the penalties under Article 615 of the Criminal Code of Uzbekistan.", ["615", "There is no article", "302 articles"]),
        ("uz_cyrl", "Фуқаролик кодексининг 1850-моддасига кўра ер участкалари қандай хусусийлаштирилади?", ["1850", "мавжуд эмас", "1199"]),
        ("uz_latn", "Kriptovalyuta kodeksining 88-moddasiga ko'ra mayning uchun soliq stavkasi qancha?", ["Kriptovalyuta kodeksi", "mavjud emas"]),
        ("en", "Under Uzbekistan's Artificial Intelligence Code (Law O'RQ-9999, Article 14), what licence fee applies?",
         ["Artificial Intelligence", "does not exist"]),
        ("uz_latn", "Prezidentning 2025-yil 19-fevraldagi PF-9999-son Farmoni nima deydi?", ["farmoni raqami mavjud emas"]),
    ],
)
def test_non_existent_references_are_reported(checker, lang, question, needles):
    report = checker.check(question, lang)
    notice = checker.notice(report, lang)
    assert report.certain_false
    for needle in needles:
        assert needle in notice
    # a non-existent act number is never repeated as if it were a citation
    assert "9999" not in notice


@pytest.mark.parametrize(
    ("question", "rule_id", "ref"),
    [
        ("1995-yilgi Mehnat kodeksining 134-moddasiga ko'ra ta'til 15 ish kuni — bugun ham amaldami?", "lc_old_134", ("6257288", "217")),
        ("Правда ли, что ставка НДС по-прежнему 15%?", "vat_rate", ("4674902", "258")),
        ("Ayollar uchun nikoh yoshi 17 yoshmi?", "marriage_age_17", ("104720", "15")),
        ("Ish beruvchi Mehnat kodeksining 100-moddasi bilan shtat qisqarishi sababli bo'shatdi", "lc_old_100", ("6257288", "161")),
        ("Ushlangan odamni 72 soat sudsiz ushlab turish mumkinmi?", "detention_72h", ("6445145", "27")),
        ("Ishga tiklash uchun sudga 1 oy ichida murojaat qilish kerakmi?", "reinstatement_1_month", ("6257288", "560")),
        ("As of June 1, 2020, what was the minimum annual paid labor leave compared to today?", "annual_leave_history", ("6257288", "217")),
    ],
)
def test_outdated_rules_point_at_the_current_article(checker, question, rule_id, ref):
    report = checker.check(question, "uz_latn")
    assert [r.id for r in report.temporal] == [rule_id]
    assert ref in report.refs


@pytest.mark.parametrize(
    "question",
    [
        "Mehnat kodeksining 217-moddasi nima deydi?",
        "Статья 158 УК РУз — что за неё грозит?",
        "MJtK 128-modda bo'yicha jarima qancha?",
        "Shaxsga doir ma'lumotlar to'g'risidagi qonun (O'RQ-547) 27-1-moddasi nima deydi?",
        "Fuqarolik kodeksining 733-moddasiga ko'ra qarz tilxati yozma bo'lishi shartmi?",
        "Статья 1199 ГК: что там написано?",
        "Konstitutsiyaning 27-moddasi bo'yicha 48 soatdan ortiq ushlab turish mumkinmi?",
        "Agar Vazirlar Mahkamasining qarori bilan ilgari qabul qilingan O'zbekiston Respublikasi Kodeksi o'rtasida ziddiyat bo'lsa?",
        "What is the zip code of Tashkent under Uzbekistan law?",
        "Ish haqimni 2 oydan beri bermayapti, nima qilay?",
        "Prezidentning PF-6247-son Farmoni bo'yicha ochiq ma'lumotlar",
    ],
)
def test_ordinary_questions_get_no_notice(checker, question):
    report = checker.check(question, "uz_latn")
    assert not report, checker.notice(report, "uz_latn")


def test_every_rule_is_translated():
    for rule in TEMPORAL_RULES:
        assert set(rule.text) == {"uz_latn", "uz_cyrl", "ru", "en"}, rule.id


def test_every_current_article_cited_by_a_rule_exists_in_the_index():
    db = get_settings().bm25_db_path
    if not db.exists():
        pytest.skip("full index not built (lex-agent build-index)")
    inventory = BM25Store(db, reader_mmap_mb=0).article_inventory()
    for rule in TEMPORAL_RULES:
        for doc, article in rule.refs:
            assert article in inventory.get(doc, frozenset()), (rule.id, doc, article)
    # and the ranges used above match the real acts
    for doc, arts in INVENTORY.items():
        nums = [int(a) for a in inventory.get(doc, frozenset()) if a.isdigit()]
        assert nums and max(nums) == max(int(a) for a in arts if a.isdigit()), doc


def test_article_ranges_and_lists_are_read_in_order():
    assert _article_ids("Fuqarolik kodeksining 108 va 109-moddalariga ko'ra") == ["108", "109"]
    assert _article_ids("O'RQ-395, Articles 18–19") == ["18", "19"]
    assert _article_ids("статьям 260 и 326 ГК") == ["260", "326"]
    assert _article_ids("104-1-modda") == ["104.1"]


def test_the_notice_leads_and_unknown_numbers_are_not_repeated(checker):
    report = checker.check("Правда ли, что по статье 899 Налогового кодекса и ПКМ-7777 все платят 35%?", "ru")
    notice = checker.notice(report, "ru")
    assert notice.startswith("Нет.") and "483 статьи" in notice and "7777" not in notice
