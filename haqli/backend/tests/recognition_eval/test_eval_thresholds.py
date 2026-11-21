"""Recognition evaluation suite (§14.3): asserts >=90% doc-type, >=95% amount/date, >=99% MRZ accuracy."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.engines.intake import extract_amount_uzs, extract_date_uz_ru
from app.engines.recognition.parsers import classify_document, mrz_check_digit, parse_mrz_td3


DOC_CLASSIFICATION_FIXTURES: list[tuple[str, str]] = [
    ("Toshkent shahar IIBB YHXB jarima qarori MJtK 128-modda 01 A 111 AA", "jarima_qarori"),
    ("Постановление о наложении административного штрафа за нарушение ПДД", "jarima_qarori"),
    ("YHXX jarima qarori davlat raqami 10 B 234 CD", "jarima_qarori"),
    ("Mikroqarz shartnomasi yillik foiz stavkasi 42% kredit", "mikroqarz_shartnomasi"),
    ("Договор микрозайма и процентная ставка по кредиту", "mikroqarz_shartnomasi"),
    ("Kredit va mikroqarz shartnomasi bo'yicha to'lov grafigi", "mikroqarz_shartnomasi"),
    ("Turar joy ijara shartnomasi kvartira depozit 300 USD", "ijara_shartnomasi"),
    ("Договор аренды квартиры с залоговым депозитом", "ijara_shartnomasi"),
    ("Ijara shartnomasi 12 oy kvartira to'lovi", "ijara_shartnomasi"),
    ("Mehnat shartnomasi xodim oylik ish haqi 7 000 000 so'm", "mehnat_shartnomasi"),
    ("Трудовой договор работник оклад испытательный срок", "mehnat_shartnomasi"),
    ("Sudgacha talabnoma 10 kun ichida qaytarish haqida", "talabnoma"),
    ("Досудебная претензия о возврате денежных средств", "talabnoma"),
    ("Qarz tilxati men 5 mln qarz oldim qaytaraman", "tilxat"),
    ("Долговая расписка я получил в долг 10 000 000 сум", "tilxat"),
    ("Kassa cheki Jami 450 000 so'm QQS 12%", "chek_kvitansiya"),
    ("Кассовый чек Итого к оплате 1 200 000 сум НДС", "chek_kvitansiya"),
    ("Kvitansiya to'lov cheki Jami 800 000 so'm", "chek_kvitansiya"),
    ("Jarima qarori YHXX 128-3-modda", "jarima_qarori"),
    ("Mehnat shartnomasi bo'yicha xodim ish haqi", "mehnat_shartnomasi"),
]

AMOUNT_DATE_FIXTURES: list[tuple[str, Decimal, date]] = [
    ("15.01.2026 kuni 5 mln so'm to'landi", Decimal("5000000.00"), date(2026, 1, 15)),
    ("2026-02-20 da 3 250 000 so'm qarz berildi", Decimal("3250000.00"), date(2026, 2, 20)),
    ("10 mart 2026 yil 750 ming so'm", Decimal("750000.00"), date(2026, 3, 10)),
    ("05.04.2026 сумма 12 000 000 сум", Decimal("12000000.00"), date(2026, 4, 5)),
    ("18 мая 2026 года оплачено 2,5 млн сум", Decimal("2500000.00"), date(2026, 5, 18)),
    ("2026-06-30 gacha 9 500 000 so'm", Decimal("9500000.00"), date(2026, 6, 30)),
    ("01.07.2026 ish haqi 6 800 000 so'm", Decimal("6800000.00"), date(2026, 7, 1)),
    ("14 avgust 2026 depozit 4 mln so'm", Decimal("4000000.00"), date(2026, 8, 14)),
    ("22.09.2026 jarima 1 875 000 so'm", Decimal("1875000.00"), date(2026, 9, 22)),
    ("11 октября 2026 г. долг 15 000 000 сум", Decimal("15000000.00"), date(2026, 10, 11)),
]


def _synth_mrz(idx: int) -> tuple[str, str]:
    doc_num = f"AD{1000000 + idx}"
    dob = f"9{idx % 10}0{(idx % 9) + 1}1{(idx % 8) + 1}"
    exp = f"3{idx % 10}0{(idx % 9) + 1}1{(idx % 8) + 1}"
    line1 = f"P<UZBTESTER{idx}<<CITIZEN{idx}".ljust(44, "<")[:44]
    doc_f = doc_num.ljust(9, "<")[:9]
    cd1 = mrz_check_digit(doc_f)
    cd2 = mrz_check_digit(dob)
    cd3 = mrz_check_digit(exp)
    opt = "<" * 14
    cd4 = mrz_check_digit(opt)
    cd5 = mrz_check_digit(doc_f + cd1 + dob + cd2 + exp + cd3 + opt + cd4)
    line2 = f"{doc_f}{cd1}UZB{dob}{cd2}M{exp}{cd3}{opt}{cd4}{cd5}"
    return f"{line1}\n{line2}", doc_num


def test_recognition_eval_accuracy_thresholds() -> None:
    # 1. Document type classification >= 90%
    cls_hits = sum(1 for txt, expected in DOC_CLASSIFICATION_FIXTURES if classify_document(txt)["type"] == expected)
    cls_acc = cls_hits / len(DOC_CLASSIFICATION_FIXTURES)
    assert cls_acc >= 0.90, f"Document classification accuracy {cls_acc:.2%} below 90%"

    # 2. Amount & Date extraction >= 95%
    amt_hits = 0
    dt_hits = 0
    for txt, exp_amt, exp_dt in AMOUNT_DATE_FIXTURES:
        a, _ = extract_amount_uzs(txt)
        d, _ = extract_date_uz_ru(txt)
        if a == exp_amt:
            amt_hits += 1
        if d == exp_dt:
            dt_hits += 1
    assert amt_hits / len(AMOUNT_DATE_FIXTURES) >= 0.95
    assert dt_hits / len(AMOUNT_DATE_FIXTURES) >= 0.95

    # 3. MRZ extraction >= 99% across 100 synthetic passports
    mrz_hits = 0
    for i in range(100):
        raw, exp_doc = _synth_mrz(i)
        res = parse_mrz_td3(raw)
        if res["valid"] and res["fields"]["documentNumber"] == exp_doc:
            mrz_hits += 1
    assert mrz_hits / 100 >= 0.99
