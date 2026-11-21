"""Regression tests for the second counter-audit round (false concept triggers, quotes, labels)."""

from __future__ import annotations

import pytest

from lex_agent.assistant.playbooks import lead_for
from lex_agent.assistant.synthesis import _clip, _sentences
from lex_agent.knowledge.lexicon import get_lexicon
from lex_agent.reasoning.answer_composer import as_sentence


def _ids(q: str) -> list[str]:
    return [m.id for m in get_lexicon().match(q, limit=5)]


@pytest.mark.parametrize(
    ("question", "absent"),
    [
        ("Shaxsni 48 soatdan ortiq ushlab turish mumkinmi?", "labour.working_hours"),
        ("Mehnat kodeksining qaysi moddalari va qanday buzilgan?", "consumer.defective"),
        ("MCHJ bosh buxgalteri uchun sinov muddati qancha?", "business.accounting"),
        ("Chet elga chiqish uchun mahalladan ruxsatnoma kerakmi?", "business.license"),
        ("Ta'tilga chiqdim, keyin direktor bilan janjallashdim, oxiri meni boshqa sabab bilan ishdan bo'shatishdi, "
         "lekin bu juda uzoq gap", "labour.dismissal.prohibited"),
    ],
)
def test_false_triggers_are_gone(question: str, absent: str) -> None:
    assert absent not in _ids(question)


@pytest.mark.parametrize(
    ("question", "expected"),
    [
        ("Ish vaqti kuniga 8 soatdan oshishi mumkinmi?", "labour.working_hours"),
        ("Telefonim buzilib qoldi, do'kon almashtirib bermayapti", "consumer.defective"),
        ("Испытательный срок сколько?", "labour.probation"),
        ("Kasal bo'lganimda ishdan bo'shatishdi", "labour.dismissal.prohibited"),
        ("Чет элга чиқиш учун рухсат керакми?", "rights.freedom_of_movement"),
        ("Hokimiyat boshqa organda bor ma'lumotnomani olib kelishni talab qilyapti", "rights.one_window"),
        ("Is an agency allowed to demand paper certificates it can get from another state body?", "rights.one_window"),
        ("Договор устанавливает срок исковой давности 6 месяцев — это законно?", "civil.limitation.agreement"),
        ("Qarzga pul berdim, tilxat kerakmi? Qarz yozma shaklda bo'lishi shartmi?", "civil.loan.form"),
    ],
)
def test_situations_still_recognised(question: str, expected: str) -> None:
    assert expected in _ids(question)


def test_debtor_exit_ban_is_not_freedom_of_movement() -> None:
    ids = _ids("Aliment qarzi bo'lsa chet elga chiqib ketsa bo'ladimi?")
    assert "rights.freedom_of_movement" not in ids


def test_new_leads_cite_their_articles() -> None:
    texts, basis = lead_for(["rights.one_window"])
    assert texts["en"].startswith("No") and ("2833860", "8") in basis
    texts, basis = lead_for(["rights.freedom_of_movement"])
    assert ("6445145", "32") in basis
    texts, basis = lead_for(["civil.limitation.agreement"])
    assert ("111189", "152") in basis and "3" in texts["uz"]


def test_key_point_bullets_end_as_sentences() -> None:
    assert as_sentence("- Mehnat kodeksi, 217-modda: «21 kalendar kun» [1]") == "- Mehnat kodeksi, 217-modda: «21 kalendar kun» [1]."
    assert as_sentence("- Kodeks, 5-modda: matn tugadi; [2]").endswith("tugadi [2].")


def test_sanction_survives_clipping() -> None:
    long_offence = "Qonunchilikni buzganlik " + "juda uzoq tavsif " * 30 + "— mansabdor shaxslarga BHMning uch baravaridan besh baravarigacha jarima solishga sabab boʻladi."
    out = _clip(long_offence, 230)
    assert len(out) <= 240 and out.endswith("sabab boʻladi.")


def test_colon_lists_become_statements() -> None:
    text = ("Quyidagi maʼlumotlar hududda saqlanishi shart:\nbiometrik maʼlumotlar;\ngenetik maʼlumotlar;\n"
            "telekommunikatsiya foydalanuvchilari maʼlumotlari.")
    sents = _sentences(text)
    assert any(s.startswith("Quyidagi") and "biometrik" in s and "genetik" in s for s in sents)
