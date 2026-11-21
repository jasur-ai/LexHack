"""Synthetic multilingual evaluation fixtures (§12): >=30/type docs, >=40 TD1/TD3 MRZ, >=50 voice, 60 numerals."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from app.engines.recognition.parsers.mrz import mrz_check_digit

# 60-case spoken & written numeral table across uz_lat, uz_cyr, ru, and mixed phrases (§6.5, §12)
NUMERAL_60_TABLE: list[tuple[str, Decimal]] = [
    ("nol", Decimal("0")),
    ("bir", Decimal("1")),
    ("ikki", Decimal("2")),
    ("uch", Decimal("3")),
    ("to'rt", Decimal("4")),
    ("besh", Decimal("5")),
    ("olti", Decimal("6")),
    ("yetti", Decimal("7")),
    ("sakkiz", Decimal("8")),
    ("to'qqiz", Decimal("9")),
    ("o'n", Decimal("10")),
    ("o'n besh", Decimal("15")),
    ("yigirma uch", Decimal("23")),
    ("o'ttiz yetti", Decimal("37")),
    ("qirq to'rt", Decimal("44")),
    ("ellik sakkiz", Decimal("58")),
    ("oltmish to'qqiz", Decimal("69")),
    ("yetmish ikki", Decimal("72")),
    ("sakson bir", Decimal("81")),
    ("to'qson to'qqiz", Decimal("99")),
    ("yuz", Decimal("100")),
    ("ikki yuz ellik", Decimal("250")),
    ("besh yuz ming", Decimal("500000")),
    ("bir million", Decimal("1000000")),
    ("besh million", Decimal("5000000")),
    ("o'n ikki million uch yuz ming", Decimal("12300000")),
    ("bir yarim million", Decimal("1500000")),
    ("uch yarim ming", Decimal("3500")),
    ("yarim million", Decimal("500000")),
    ("ikki million yarim", Decimal("2500000")),
    ("bir milliard", Decimal("1000000000")),
    ("5 mln", Decimal("5000000")),
    ("5mln", Decimal("5000000")),
    ("5 млн", Decimal("5000000")),
    ("5,5 million", Decimal("5500000")),
    ("5 000 000", Decimal("5000000")),
    ("5.000.000", Decimal("5000000")),
    ("5000k", Decimal("5000000")),
    ("250k", Decimal("250000")),
    ("12.500.000", Decimal("12500000")),
    ("беш миллион", Decimal("5000000")),
    ("икки юз эллик минг", Decimal("250000")),
    ("тўрт миллион беш юз минг", Decimal("4500000")),
    ("бир ярим миллион", Decimal("1500000")),
    ("ўн миллион", Decimal("10000000")),
    ("ноль", Decimal("0")),
    ("один миллион", Decimal("1000000")),
    ("два миллиона пятьсот тысяч", Decimal("2500000")),
    ("три миллиона двести тысяч", Decimal("3200000")),
    ("пять миллионов", Decimal("5000000")),
    ("десять тысяч", Decimal("10000")),
    ("сто пятьдесят тысяч", Decimal("150000")),
    ("четыреста тысяч", Decimal("400000")),
    ("семьсот пятьдесят тысяч", Decimal("750000")),
    ("полтора миллиона", Decimal("1500000")),
    ("две тысячи пятьсот", Decimal("2500")),
    ("одна тысяча двести", Decimal("1200")),
    ("besh млн", Decimal("5000000")),
    ("три million", Decimal("3000000")),
    ("ikki миллион besh yuz ming", Decimal("2500000")),
]


def build_document_fixtures() -> list[dict[str, Any]]:
    """Build >= 30 documents per type (150 total across rental, employment, microloan, receipt, fine) in uz_lat, uz_cyr, ru."""
    docs: list[dict[str, Any]] = []
    for i in range(30):
        day = (i % 25) + 1
        month = (i % 9) + 1
        dt_iso = f"2026-{month:02d}-{day:02d}"
        dt_dmy = f"{day:02d}.{month:02d}.2026"
        amt = (i + 1) * 500_000
        amt_str = f"{amt:,}".replace(",", " ")
        noisy = i >= 24  # 20% degraded/OCR-noisy fixtures
        noise_amt = amt_str.replace("0", "O", 1) if noisy else amt_str

        lang_slot = i % 3
        # 1. Rental contract
        if lang_slot == 0:
            txt = f"Turar joy ijara shartnomasi #{i+1}\n1. Kvartira ijaraga beruvchi va ijarachi o'rtasida.\n2. Sana: {dt_dmy}. Depozit: {noise_amt} so'm."
        elif lang_slot == 1:
            txt = f"Ижара шартномаси #{i+1}\n1. Квартира ижарага берилади.\n2. Сана: {dt_dmy}. Сумма: {noise_amt} сўм."
        else:
            txt = f"Договор аренды квартиры #{i+1}\n1. Арендодатель передает квартиру арендатору.\n2. Дата: {dt_dmy}. Залоговый депозит: {noise_amt} сум."
        docs.append({"doc_type": "rental_contract", "text": txt, "amount": Decimal(amt), "date": date.fromisoformat(dt_iso), "degraded": noisy})

        # 2. Employment contract
        if lang_slot == 0:
            txt = f"Mehnat shartnomasi #{i+1}\n1. Ish beruvchi va xodim o'rtasida.\n2. Oylik ish haqi: {noise_amt} so'm. Sana: {dt_dmy}."
        elif lang_slot == 1:
            txt = f"Меҳнат шартномаси #{i+1}\n1. Ходим иш ҳақи {noise_amt} сўм.\n2. Сана: {dt_dmy}."
        else:
            txt = f"Трудовой договор #{i+1}\n1. Работодатель принимает работника на оклад {noise_amt} сум.\n2. Дата: {dt_dmy}."
        docs.append({"doc_type": "employment_contract", "text": txt, "amount": Decimal(amt), "date": date.fromisoformat(dt_iso), "degraded": noisy})

        # 3. Microloan contract
        if lang_slot == 0:
            txt = f"Mikroqarz shartnomasi #{i+1}\n1. Kredit yillik foiz stavkasi 42%.\n2. Summa: {noise_amt} so'm. Sana: {dt_dmy}."
        elif lang_slot == 1:
            txt = f"Микроқарз шартномаси #{i+1}\n1. Кредит суммаси {noise_amt} сўм.\n2. Сана: {dt_dmy}."
        else:
            txt = f"Договор микрозайма #{i+1}\n1. Процентная ставка 40% годовых.\n2. Сумма займа: {noise_amt} сум. Дата: {dt_dmy}."
        docs.append({"doc_type": "microloan_contract", "text": txt, "amount": Decimal(amt), "date": date.fromisoformat(dt_iso), "degraded": noisy})

        # 4. Receipt
        if lang_slot == 0:
            txt = f"Savdo MCHJ #{i+1}\nSTIR: 304567891\nKassa cheki\nSana: {dt_dmy}\nTo'lov: Uzcard\nJami: {noise_amt} so'm"
        elif lang_slot == 1:
            txt = f"Савдо МЧЖ #{i+1}\nСТИР: 304567891\nКасса чеки\nСана: {dt_dmy}\nЖами: {noise_amt} сўм"
        else:
            txt = f"ООО Маркет #{i+1}\nИНН: 304567891\nКассовый чек\nДата: {dt_dmy}\nИтого: {noise_amt} сум"
        docs.append({"doc_type": "receipt", "text": txt, "amount": Decimal(amt), "date": date.fromisoformat(dt_iso), "degraded": noisy})

        # 5. Traffic fine
        plate = f"01 A {100 + i} AA"
        if lang_slot == 0:
            txt = f"Toshkent shahar IIBB YHXB\nJarima qarori № YHX-2026-{1000+i}\nSana: {dt_dmy}\nMJtK 128-modda, davlat raqami {plate}.\nJarima: {noise_amt} so'm"
        elif lang_slot == 1:
            txt = f"Тошкент ИИББ ЙҲХБ\nЖарима қарори № YHX-{1000+i}\nСана: {dt_dmy}\n128-модда {plate}\nЖарима: {noise_amt} сўм"
        else:
            txt = f"Постановление о наложении административного штрафа № ПДД-{1000+i}\nДата: {dt_dmy}\nст. 128 ПДД, авто {plate}.\nШтраф: {noise_amt} сум"
        docs.append({"doc_type": "fine_decision", "text": txt, "amount": Decimal(amt), "date": date.fromisoformat(dt_iso), "degraded": noisy})

    return docs


def make_td3(surname: str, given: str, doc_num: str, dob: str, exp: str, *, corrupt_count: int = 0) -> str:
    l1 = f"P<UZB{surname.upper()}<<{given.upper()}".ljust(44, "<")[:44]
    df = doc_num.upper().ljust(9, "<")[:9]
    cd1 = mrz_check_digit(df)
    cd2 = mrz_check_digit(dob)
    cd3 = mrz_check_digit(exp)
    opt = "<" * 14
    cd4 = mrz_check_digit(opt)
    cd5 = mrz_check_digit(df + cd1 + dob + cd2 + exp + cd3 + opt + cd4)
    if corrupt_count >= 1:
        cd1 = str((int(cd1) + 1) % 10)
    if corrupt_count >= 2:
        cd2 = str((int(cd2) + 1) % 10)
    l2 = f"{df}{cd1}UZB{dob}{cd2}M{exp}{cd3}{opt}{cd4}{cd5}"
    return f"{l1}\n{l2}"


def make_td1(surname: str, given: str, doc_num: str, dob: str, exp: str, *, corrupt_count: int = 0) -> str:
    df = doc_num.upper().ljust(9, "<")[:9]
    cd1 = mrz_check_digit(df)
    opt1 = "<" * 15
    cd2 = mrz_check_digit(dob)
    cd3 = mrz_check_digit(exp)
    opt2 = "<" * 11
    cd4 = mrz_check_digit(df + cd1 + opt1 + dob + cd2 + exp + cd3 + opt2)
    if corrupt_count >= 1:
        cd1 = str((int(cd1) + 1) % 10)
    if corrupt_count >= 2:
        cd3 = str((int(cd3) + 1) % 10)
    l1 = f"IDUZB{df}{cd1}{opt1}"
    l2 = f"{dob}{cd2}M{exp}{cd3}UZB{opt2}{cd4}"
    l3 = f"{surname.upper()}<<{given.upper()}".ljust(30, "<")[:30]
    return f"{l1}\n{l2}\n{l3}"


def build_mrz_fixtures() -> list[dict[str, Any]]:
    """Build 50 TD1/TD3 MRZ fixtures (35 valid including OCR confusions + 15 invalid with >=2 check-digit errors)."""
    fixtures: list[dict[str, Any]] = []
    for i in range(25):
        doc_num = f"AD{1000000 + i}"
        dob = f"9{i % 10}0{(i % 9) + 1}1{(i % 8) + 1}"
        exp = f"3{i % 10}0{(i % 9) + 1}1{(i % 8) + 1}"
        mrz = make_td3(f"KARIMOV", f"AZIZBEK", doc_num, dob, exp)
        if i % 5 == 0:
            # Inject repairable filler OCR noise
            mrz = mrz.replace("<<<", "««<", 1)
        fixtures.append({"raw": mrz, "expect_valid": True, "doc_number": doc_num, "format": "TD3"})

    for i in range(10):
        doc_num = f"ID{2000000 + i}"
        dob = f"9{i % 10}0{(i % 8) + 1}1{(i % 7) + 1}"
        exp = f"3{i % 10}0{(i % 8) + 1}1{(i % 7) + 1}"
        mrz = make_td1("ALIMOVA", "DILNOZA", doc_num, dob, exp)
        fixtures.append({"raw": mrz, "expect_valid": True, "doc_number": doc_num, "format": "TD1"})

    for i in range(15):
        doc_num = f"AD{9000000 + i}"
        mrz = make_td3("BADUSER", "INVALID", doc_num, "950101", "320101", corrupt_count=2)
        fixtures.append({"raw": mrz, "expect_valid": False, "doc_number": doc_num, "format": "TD3"})

    return fixtures


def build_voice_fixtures() -> list[dict[str, Any]]:
    """Build 54 labeled uz_lat, uz_cyr, ru, and mixed voice utterances (§12)."""
    fixtures: list[dict[str, Any]] = []
    names = ["Alisher Rahimov", "Dilshod Karimov", "Sardor Alimov", "Madina Usmonova", "Bobur Saidov", "Timur Petrov"]
    for i in range(54):
        name = names[i % len(names)]
        day = (i % 24) + 1
        dt_iso = f"2026-06-{day:02d}"
        amt = Decimal((i % 9 + 1) * 1_000_000)
        slot = i % 3
        if slot == 0:
            txt = f"Men {name}ga {int(amt // 1_000_000)} million so'm qarz berdim, {day:02d}.06.2026 kuni qaytaradi"
            role = "lender"
        elif slot == 1:
            txt = f"Я одолжил {name} {int(amt // 1_000_000)} млн сум до {day:02d}.06.2026"
            role = "lender"
        else:
            txt = f"Men {name}dan {int(amt // 1_000_000)} mln so'm qarz oldim, {day} iyun 2026 gacha qaytaraman"
            role = "borrower"
        fixtures.append({"text": txt, "amount": amt, "date": date.fromisoformat(dt_iso), "name": name, "role": role})
    return fixtures
