"""Authoritative Uzbekistan Legislation Knowledge Base & Trainable SQLite FTS5 Corpus for LEX AUDITOR."""

from __future__ import annotations

import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from evaluator_agent.claim_parser import normalize_article_number


def _clean_article_id(raw_art: str) -> str:
    """Normalize '99-modda', '47⁷-modda', 'Статья 129' -> canonical '99', '47-7', '129'."""
    s = normalize_article_number(raw_art or "")
    s = re.sub(r"^(?:статья|ст\.|article|art\.)\s*", "", s, flags=re.I)
    s = re.sub(r"\s*-?\s*(?:modda\w*|модда\w*)$", "", s, flags=re.I)
    return s.strip()

# ==============================================================================
# 1. COMPLETE REGISTRY OF 26+ UZBEKISTAN CODES, CONSTITUTION & ORGANIC LAWS
# ==============================================================================
UZBEKISTAN_STATUTE_REGISTRY: dict[str, dict[str, Any]] = {
    "Konstitutsiya": {
        "doc_id": "6445147",
        "doc_number": "Konstitutsiya-2023",
        "title_uz": "O'zbekiston Respublikasining Konstitutsiyasi (2023-yil yangi tahriri)",
        "title_ru": "Конституция Республики Узбекистан (новая редакция 2023 г.)",
        "branch": "constitutional",
        "rank": 100,
        "max_article": 155,
        "status": "in_force",
        "effective_date": "2023-05-01",
    },
    "Normativ-huquqiy hujjatlar to'g'risida": {
        "doc_id": "5378966",
        "doc_number": "O'RQ-682",
        "title_uz": "Normativ-huquqiy hujjatlar to'g'risida O'RQ-682-son Qonun",
        "title_ru": "Закон РУз «О нормативно-правовых актах» ЗРУ-682",
        "branch": "constitutional",
        "rank": 90,
        "max_article": 60,
        "status": "in_force",
        "effective_date": "2021-04-21",
    },
    "Mehnat kodeksi": {
        "doc_id": "6257288",
        "doc_number": "O'RQ-798",
        "title_uz": "O'zbekiston Respublikasining Mehnat kodeksi (2022/2023 yangi tahrir)",
        "title_ru": "Трудовой кодекс Республики Узбекистан (ЗРУ-798)",
        "branch": "labor",
        "rank": 88,
        "max_article": 581,
        "status": "in_force",
        "effective_date": "2023-04-30",
    },
    "Eski Mehnat kodeksi (1995)": {
        "doc_id": "142859",
        "doc_number": "MK-1995",
        "title_uz": "1995-yilgi Mehnat kodeksi (Kuchini yo'qotgan)",
        "title_ru": "Трудовой кодекс 1995 г. (Утратил силу 30.04.2023)",
        "branch": "labor",
        "rank": 0,
        "max_article": 294,
        "status": "repealed",
        "effective_date": "1996-04-01",
    },
    "Fuqarolik kodeksi": {
        "doc_id": "111189",
        "doc_number": "FK",
        "title_uz": "O'zbekiston Respublikasining Fuqarolik kodeksi (1 va 2-qismlar)",
        "title_ru": "Гражданский кодекс Республики Узбекистан",
        "branch": "civil",
        "rank": 88,
        "max_article": 1199,
        "status": "in_force",
        "effective_date": "1997-03-01",
    },
    "Soliq kodeksi": {
        "doc_id": "4674902",
        "doc_number": "O'RQ-599",
        "title_uz": "O'zbekiston Respublikasining Soliq kodeksi (yangi tahrir)",
        "title_ru": "Налоговый кодекс Республики Узбекистан (ЗРУ-599)",
        "branch": "tax",
        "rank": 88,
        "max_article": 483,
        "status": "in_force",
        "effective_date": "2020-01-01",
    },
    "Oila kodeksi": {
        "doc_id": "104720",
        "doc_number": "OK",
        "title_uz": "O'zbekiston Respublikasining Oila kodeksi",
        "title_ru": "Семейный кодекс Республики Узбекистан",
        "branch": "family",
        "rank": 88,
        "max_article": 238,
        "status": "in_force",
        "effective_date": "1998-09-01",
    },
    "Jinoyat kodeksi": {
        "doc_id": "111453",
        "doc_number": "JK",
        "title_uz": "O'zbekiston Respublikasining Jinoyat kodeksi",
        "title_ru": "Уголовный кодекс Республики Узбекистан",
        "branch": "criminal",
        "rank": 88,
        "max_article": 302,
        "status": "in_force",
        "effective_date": "1995-04-01",
    },
    "Jinoyat-protsessual kodeksi": {
        "doc_id": "111460",
        "doc_number": "JPK",
        "title_uz": "O'zbekiston Respublikasining Jinoyat-protsessual kodeksi",
        "title_ru": "Уголовно-процессуальный кодекс Республики Узбекистан",
        "branch": "procedural",
        "rank": 88,
        "max_article": 616,
        "status": "in_force",
        "effective_date": "1995-04-01",
    },
    "MJtK": {
        "doc_id": "97664",
        "doc_number": "MJtK",
        "title_uz": "Ma'muriy javobgarlik to'g'risidagi kodeks (MJtK)",
        "title_ru": "Кодекс об административной ответственности РУз (КоАО)",
        "branch": "administrative",
        "rank": 88,
        "max_article": 348,
        "status": "in_force",
        "effective_date": "1995-04-01",
    },
    "Fuqarolik protsessual kodeksi": {
        "doc_id": "3517337",
        "doc_number": "FPK",
        "title_uz": "O'zbekiston Respublikasining Fuqarolik protsessual kodeksi",
        "title_ru": "Гражданский процессуальный кодекс Республики Узбекистан",
        "branch": "procedural",
        "rank": 88,
        "max_article": 464,
        "status": "in_force",
        "effective_date": "2018-04-01",
    },
    "Iqtisodiy protsessual kodeksi": {
        "doc_id": "3523891",
        "doc_number": "IPK",
        "title_uz": "O'zbekiston Respublikasining Iqtisodiy protsessual kodeksi",
        "title_ru": "Экономический процессуальный кодекс Республики Узбекистан",
        "branch": "procedural",
        "rank": 88,
        "max_article": 347,
        "status": "in_force",
        "effective_date": "2018-04-01",
    },
    "Ma'muriy sud ishlarini yuritish kodeksi": {
        "doc_id": "3527353",
        "doc_number": "MSIYuTK",
        "title_uz": "Ma'muriy sud ishlarini yuritish to'g'risidagi kodeks",
        "title_ru": "Кодекс об административном судопроизводстве РУз",
        "branch": "administrative",
        "rank": 88,
        "max_article": 286,
        "status": "in_force",
        "effective_date": "2018-04-01",
    },
    "Yer kodeksi": {
        "doc_id": "152653",
        "doc_number": "YK",
        "title_uz": "O'zbekiston Respublikasining Yer kodeksi",
        "title_ru": "Земельный кодекс Республики Узбекистан",
        "branch": "land",
        "rank": 88,
        "max_article": 91,
        "status": "in_force",
        "effective_date": "1998-07-01",
    },
    "Uy-joy kodeksi": {
        "doc_id": "106136",
        "doc_number": "UJK",
        "title_uz": "O'zbekiston Respublikasining Uy-joy kodeksi",
        "title_ru": "Жилищный кодекс Республики Узбекистан",
        "branch": "civil",
        "rank": 88,
        "max_article": 141,
        "status": "in_force",
        "effective_date": "1999-04-01",
    },
    "Bojxona kodeksi": {
        "doc_id": "2876354",
        "doc_number": "BK",
        "title_uz": "O'zbekiston Respublikasining Bojxona kodeksi",
        "title_ru": "Таможенный кодекс Республики Узбекистан",
        "branch": "customs",
        "rank": 88,
        "max_article": 412,
        "status": "in_force",
        "effective_date": "2016-04-21",
    },
    "Budjet kodeksi": {
        "doc_id": "2304138",
        "doc_number": "BudjetK",
        "title_uz": "O'zbekiston Respublikasining Budjet kodeksi",
        "title_ru": "Бюджетный кодекс Республики Узбекистан",
        "branch": "tax",
        "rank": 88,
        "max_article": 192,
        "status": "in_force",
        "effective_date": "2014-01-01",
    },
    "Shaharsozlik kodeksi": {
        "doc_id": "5307951",
        "doc_number": "O'RQ-676",
        "title_uz": "O'zbekiston Respublikasining Shaharsozlik kodeksi",
        "title_ru": "Градостроительный кодекс Республики Узбекистан",
        "branch": "land",
        "rank": 88,
        "max_article": 85,
        "status": "in_force",
        "effective_date": "2021-05-23",
    },
    "Saylov kodeksi": {
        "doc_id": "4386848",
        "doc_number": "O'RQ-544",
        "title_uz": "O'zbekiston Respublikasining Saylov kodeksi",
        "title_ru": "Избирательный кодекс Республики Узбекистан",
        "branch": "constitutional",
        "rank": 88,
        "max_article": 103,
        "status": "in_force",
        "effective_date": "2019-06-26",
    },
    "Havo kodeksi": {
        "doc_id": "55594",
        "doc_number": "HK",
        "title_uz": "O'zbekiston Respublikasining Havo kodeksi",
        "title_ru": "Воздушный кодекс Республики Узбекистан",
        "branch": "general",
        "rank": 88,
        "max_article": 134,
        "status": "in_force",
        "effective_date": "1993-05-07",
    },
    "Shaxsga doir ma'lumotlar to'g'risida": {
        "doc_id": "4396419",
        "doc_number": "O'RQ-547",
        "title_uz": "Shaxsga doir ma'lumotlar to'g'risida O'RQ-547-son Qonun",
        "title_ru": "Закон РУз «О персональных данных» ЗРУ-547",
        "branch": "digital_it_data",
        "rank": 85,
        "max_article": 35,
        "status": "in_force",
        "effective_date": "2019-10-01",
    },
    "Iste'molchilarning huquqlarini himoya qilish to'g'risida": {
        "doc_id": "4704",
        "doc_number": "221-I",
        "title_uz": "Iste'molchilarning huquqlarini himoya qilish to'g'risida Qonun",
        "title_ru": "Закон РУз «О защите прав потребителей»",
        "branch": "civil",
        "rank": 85,
        "max_article": 30,
        "status": "in_force",
        "effective_date": "1996-04-26",
    },
    "Mas'uliyati cheklangan jamiyatlar to'g'risida": {
        "doc_id": "18793",
        "doc_number": "310-II",
        "title_uz": "Mas'uliyati cheklangan hamda qo'shimcha mas'uliyatli jamiyatlar to'g'risida Qonun",
        "title_ru": "Закон РУз «Об обществах с ограниченной и дополнительной ответственностью»",
        "branch": "corporate",
        "rank": 85,
        "max_article": 58,
        "status": "in_force",
        "effective_date": "2002-03-01",
    },
    "Manfaatlar to'qnashuvi to'g'risida": {
        "doc_id": "6952742",
        "doc_number": "O'RQ-931",
        "title_uz": "Manfaatlar to'qnashuvi to'g'risida O'RQ-931-son Qonun (2024)",
        "title_ru": "Закон РУз «О конфликте интересов» ЗРУ-931 (2024)",
        "branch": "administrative",
        "rank": 85,
        "max_article": 31,
        "status": "in_force",
        "effective_date": "2024-12-06",
    },
    "Sudlar to'g'risida": {
        "doc_id": "5534923",
        "doc_number": "O'RQ-703",
        "title_uz": "Sudlar to'g'risida O'RQ-703-son Qonun",
        "title_ru": "Закон РУз «О судах» ЗРУ-703",
        "branch": "procedural",
        "rank": 85,
        "max_article": 101,
        "status": "in_force",
        "effective_date": "2021-07-29",
    },
    "Advokatura to'g'risida": {
        "doc_id": "58372",
        "doc_number": "349-I",
        "title_uz": "Advokatura to'g'risida O'zbekiston Respublikasi Qonuni",
        "title_ru": "Закон РУз «Об адвокатуре»",
        "branch": "procedural",
        "rank": 85,
        "max_article": 18,
        "status": "in_force",
        "effective_date": "1997-01-01",
    },
    "Davlat hokimiyati va boshqaruvi organlari faoliyatining ochiqligi to'g'risida": {
        "doc_id": "2381133",
        "doc_number": "O'RQ-369",
        "title_uz": "Davlat hokimiyati va boshqaruvi organlari faoliyatining ochiqligi to'g'risida O'RQ-369-son Qonun (data.egov.uz)",
        "title_ru": "Закон РУз «Об открытости деятельности органов государственной власти и управления» ЗРУ-369 (data.egov.uz)",
        "branch": "administrative",
        "rank": 85,
        "max_article": 25,
        "status": "in_force",
        "effective_date": "2014-05-05",
    },
    "Elektron hukumat to'g'risida": {
        "doc_id": "2833860",
        "doc_number": "O'RQ-395",
        "title_uz": "Elektron hukumat to'g'risida O'RQ-395-son Qonun (egov.uz / my.gov.uz / data.egov.uz)",
        "title_ru": "Закон РУз «Об электронном правительстве» ЗРУ-395",
        "branch": "digital_it_data",
        "rank": 85,
        "max_article": 34,
        "status": "in_force",
        "effective_date": "2016-06-10",
    },
    "Elektron tijorat to'g'risida": {
        "doc_id": "6213382",
        "doc_number": "O'RQ-792",
        "title_uz": "Elektron tijorat to'g'risida O'RQ-792-son Qonun (yangi tahrir, 2022)",
        "title_ru": "Закон РУз «Об электронной коммерции» ЗРУ-792",
        "branch": "digital_it_data",
        "rank": 85,
        "max_article": 30,
        "status": "in_force",
        "effective_date": "2022-12-31",
    },
    "Ochiq ma'lumotlar portali va davlat organlari ochiqligi (PF-6247)": {
        "doc_id": "5459107",
        "doc_number": "PF-6247",
        "title_uz": "Davlat organlari va tashkilotlarining faoliyati ochiqligini ta'minlash to'g'risida PF-6247-son Prezident Farmoni (data.egov.uz)",
        "title_ru": "Указ Президента РУз УП-6247 «Об обеспечении открытости деятельности госорганов и Портале открытых данных data.egov.uz»",
        "branch": "digital_it_data",
        "rank": 80,
        "max_article": 25,
        "status": "in_force",
        "effective_date": "2021-06-16",
    },
    "Jinoyat-ijroiya kodeksi": {
        "doc_id": "163629",
        "doc_number": "JIK",
        "title_uz": "O'zbekiston Respublikasining Jinoyat-ijroiya kodeksi",
        "title_ru": "Уголовно-исполнительный кодекс Республики Узбекистан",
        "branch": "criminal",
        "rank": 88,
        "max_article": 200,
        "status": "in_force",
        "effective_date": "1997-08-01",
    },
}

# ==============================================================================
# 2. AUTHORITATIVE ARTICLE-LEVEL GOLDEN VERIFICATION CORPUS (80+ KEY ARTICLES)
# ==============================================================================
AUTHORITATIVE_ARTICLES: list[dict[str, Any]] = [
    # --- KONSTITUTSIYA (2023) ---
    {
        "code": "Konstitutsiya",
        "doc_id": "6445147",
        "article": "15",
        "status": "in_force",
        "summary_uz": "O'zbekiston Respublikasida Konstitutsiya va qonunlarning ustunligi so'zsiz tan olinadi. Konstitutsiya oliy yuridik kuchga ega va to'g'ridan-to'g'ri amal qiladi.",
        "summary_ru": "В Республике Узбекистан признается безусловное верховенство Конституции и законов. Конституция имеет высшую юридическую силу и прямое действие.",
        "key_tokens": ["oliy yuridik kuch", "to'g'ridan-to'g'ri", "прямое действие", "высшую юридическую силу"],
        "forbidden_tokens": [],
    },
    {
        "code": "Konstitutsiya",
        "doc_id": "6445147",
        "article": "16",
        "status": "in_force",
        "summary_uz": "Birorta ham qonun yoki boshqa normativ-huquqiy hujjat Konstitutsiya prinsip va normalariga zid kelishi mumkin emas.",
        "summary_ru": "Ни один закон или иной нормативно-правовой акт не может противоречить принципам и нормам Конституции.",
        "key_tokens": ["zid kelishi mumkin emas", "противоречить"],
        "forbidden_tokens": [],
    },
    {
        "code": "Konstitutsiya",
        "doc_id": "6445147",
        "article": "20",
        "status": "in_force",
        "summary_uz": "Inson bilan davlat organlarining o'zaro munosabatlarida yuzaga keladigan qonunchilikdagi barcha ziddiyatlar va noaniqliklar inson foydasiga talqin etiladi (in dubio pro cive). Huquqiy ta'sir choralari mutanosiblik prinsipiga asoslanishi va yetarli bo'lishi kerak.",
        "summary_ru": "Все противоречия и неясности в законодательстве, возникающие во взаимоотношениях человека с госорганами, толкуются в пользу человека. Меры правового воздействия должны быть соразмерными.",
        "key_tokens": ["inson foydasiga", "mutanosiblik", "в пользу человека", "соразмерн"],
        "forbidden_tokens": ["davlat foydasiga talqin etiladi"],
    },
    {
        "code": "Konstitutsiya",
        "doc_id": "6445147",
        "article": "27",
        "status": "in_force",
        "summary_uz": "Hibsga olishga, qamoqqa olishga va qamoqda saqlashga faqat sudning qaroriga ko'ra yo'l qo'yiladi. Sudning qarorisiz shaxsni 48 soatdan ortiq ushlab turish mumkin emas (Habeas corpus).",
        "summary_ru": "Арест, заключение под стражу и содержание под стражей допускаются только по решению суда. Без решения суда лицо не может быть задержано более чем на 48 часов (Хабеас корпус).",
        "key_tokens": ["48 soat", "48 час", "sudning qarori", "Habeas"],
        "forbidden_tokens": ["72 soat sudsiz", "10 kun sudsiz"],
    },
    {
        "code": "Konstitutsiya",
        "doc_id": "6445147",
        "article": "28",
        "status": "in_force",
        "summary_uz": "Aybsizlik prezumpsiyasi: shaxsning aybi qonuniy kuchga kirgan sud hukmi bilan aniqlanmaguncha u aybsiz hisoblanadi. Gumon qilinuvchi o'z aybsizligini isbotlashi shart emas; barcha shubhalar uning foydasiga hal qilinadi.",
        "summary_ru": "Презумпция невиновности: обвиняемый считается невиновным, пока его виновность не будет установлена вступившим в законную силу приговором суда.",
        "key_tokens": ["aybsizlik", "sud hukmi", "презумпция невиновности", "приговором суда"],
        "forbidden_tokens": [],
    },
    {
        "code": "Konstitutsiya",
        "doc_id": "6445147",
        "article": "29",
        "status": "in_force",
        "summary_uz": "Miranda qoidasi va malakali yuridik yordam: shaxs ushlangan paytdan boshlab harakatlanish erkinligi cheklanganda unga huquqlari va ushlab turish asoslari tushuntirilishi, sukut saqlash va advokat yordamidan foydalanish huquqi ta'minlanishi shart.",
        "summary_ru": "Правило Миранды: с момента задержания лицу разъясняются его права, право хранить молчание и право на помощь адвоката.",
        "key_tokens": ["advokat", "sukut saqlash", "ushlangan paytdan", "Миранд"],
        "forbidden_tokens": [],
    },
    {
        "code": "Konstitutsiya",
        "doc_id": "6445147",
        "article": "31",
        "status": "in_force",
        "summary_uz": "Har kim shaxsiy hayotining daxlsizligi, yozishmalar sir saqlanishi va o'z shaxsga doir ma'lumotlarining himoya qilinishi hamda noto'g'ri ma'lumotlar tuzatilishini yoki o'chirilishini talab qilish huquqiga ega.",
        "summary_ru": "Каждый имеет право на неприкосновенность частной жизни, защиту персональных данных и требование исправления или удаления недостоверных данных.",
        "key_tokens": ["shaxsiy hayot", "shaxsga doir", "персональных данных"],
        "forbidden_tokens": [],
    },
    {
        "code": "Konstitutsiya",
        "doc_id": "6445147",
        "article": "41",
        "status": "in_force",
        "summary_uz": "Har kim mulkdor bo'lishga haqli. Bank operatsiyalarining, omonatlarning va hisobvaraqlarning sir tutilishi, shuningdek meros huquqi qonun bilan kafolatlanadi.",
        "summary_ru": "Каждый имеет право на собственность. Тайна банковских операций, вкладов и счетов, а также право наследования гарантируются законом.",
        "key_tokens": ["bank", "omonat", "meros", "банковских"],
        "forbidden_tokens": [],
    },
    {
        "code": "Konstitutsiya",
        "doc_id": "6445147",
        "article": "55",
        "status": "in_force",
        "summary_uz": "Har kimga o'z huquq va erkinliklarini sud orqali himoya qilish, davlat organlarining qonunga xilof qarorlari ustidan sudga shikoyat qilish hamda Konstitutsiyaviy sudga murojaat qilish huquqi kafolatlanadi.",
        "summary_ru": "Каждому гарантируется судебная защита его прав и свобод, право обжалования в суд незаконных решений госорганов и обращения в Конституционный суд.",
        "key_tokens": ["sud orqali", "Konstitutsiyaviy sud", "судебная защита"],
        "forbidden_tokens": [],
    },
    # --- NORMATIV-HUQUQIY HUJJATLAR TO'G'RISIDA (O'RQ-682) ---
    {
        "code": "Normativ-huquqiy hujjatlar to'g'risida",
        "doc_id": "5378966",
        "article": "6",
        "status": "in_force",
        "summary_uz": "Normativ-huquqiy hujjatlar turlari va ierarxiyasi: 1) Konstitutsiya; 2) Qonunlar va kodekslar; 3) Oliy Majlis palatalari qarorlari; 4) Prezident farmon va qarorlari; 5) Vazirlar Mahkamasi qarorlari; 6) Vazirlik/idora buyruqlari; 7) Mahalliy hokimiyat qarorlari.",
        "summary_ru": "Виды и иерархия НПА (ст. 6 ЗРУ-682): Конституция -> Законы и кодексы -> Постановления палат Олий Мажлиса -> Указы/постановления Президента -> Постановления Кабмина -> Ведомственные акты -> Решения хокимиятов.",
        "key_tokens": ["Konstitutsiya", "kodeks", "Vazirlar Mahkamasi"],
        "forbidden_tokens": [],
    },
    {
        "code": "Normativ-huquqiy hujjatlar to'g'risida",
        "doc_id": "5378966",
        "article": "18",
        "status": "in_force",
        "summary_uz": "Kolliziyalarni hal etish: 1) Yuqori yuridik kuchga ega hujjat ustuvor (lex superior: Qonun/Kodeks > Prezident hujjati > VM qarori); 2) Teng kuchga ega hujjatlarda keyinroq qabul qilingani amal qiladi (lex posterior), maxsus qonun bundan mustasno (lex specialis).",
        "summary_ru": "Разрешение коллизий НПА (ст. 18 ЗРУ-682): акт более высокой юридической силы имеет приоритет (lex superior); при равной силе действует более поздний акт (lex posterior), кроме специального акта (lex specialis).",
        "key_tokens": ["yuqori", "keyinroq", "maxsus", "специальн", "высшей"],
        "forbidden_tokens": ["Vazirlar Mahkamasining yangi qarori Kodeksdan ustuvor"],
    },
    {
        "code": "Normativ-huquqiy hujjatlar to'g'risida",
        "doc_id": "5378966",
        "article": "41",
        "status": "in_force",
        "summary_uz": "Orqaga qaytish kuchi: normativ-huquqiy hujjatlar orqaga qaytish kuchiga ega emas, javobgarlikni yengillashtiruvchi yoki bartaraf etuvchi normalar yoxud hujjatning o'zida to'g'ridan-to'g'ri ko'rsatilgan hollar bundan mustasno.",
        "summary_ru": "Обратная сила НПА (ст. 41 ЗРУ-682): акты не имеют обратной силы, за исключением норм, смягчающих или устраняющих ответственность.",
        "key_tokens": ["orqaga qaytish", "yengillashtir", "обратной силы", "смягчающ"],
        "forbidden_tokens": ["og'irlashtiruvchi qonun orqaga qaytadi"],
    },
    # --- MEHNAT KODEKSI (NEW O'RQ-798, eff. 30.04.2023) ---
    {
        "code": "Mehnat kodeksi",
        "doc_id": "6257288",
        "article": "129",
        "status": "in_force",
        "summary_uz": "Dastlabki sinov muddati: oddiy xodimlar uchun 3 oydan, tashkilot rahbarlari, ularning o'rinbosarlari, bosh buxgalterlar va alohida bo'linma rahbarlari uchun 6 oydan oshmasligi shart. Homilador ayollar, 3 yoshgacha bolasi bor shaxslar va 18 yoshga to'lmaganlarga sinov belgilanmaydi.",
        "summary_ru": "Предварительное испытание (ст. 129 ТК РУз): не более 3 месяцев для обычных работников и не более 6 месяцев для руководителей организаций, их заместителей и главных бухгалтеров.",
        "key_tokens": ["uch oy", "olti oy", "3", "6", "bosh buxgalter"],
        "forbidden_tokens": ["oddiy xodimga 6 oy sinov"],
    },
    {
        "code": "Mehnat kodeksi",
        "doc_id": "6257288",
        "article": "161",
        "status": "in_force",
        "summary_uz": "Mehnat shartnomasini ish beruvchi tashabbusiga ko'ra bekor qilish asoslari: 1) tashkilot tugatilishi; 2) texnologiya/ishlab chiqarish o'zgarishi yoki shtat qisqarishi; 3) xodim malakasi yetarli emasligi; 4) mehnat majburiyatlarini muntazam buzish; 5) bir marta qo'pol buzish.",
        "summary_ru": "Основания прекращения трудового договора по инициативе работодателя (ст. 161 ТК РУз): ликвидация, сокращение штата, несоответствие квалификации, систематическое или однократное грубое нарушение.",
        "key_tokens": ["shtat", "malaka", "qo'pol", "сокращен"],
        "forbidden_tokens": [],
    },
    {
        "code": "Mehnat kodeksi",
        "doc_id": "6257288",
        "article": "165",
        "status": "in_force",
        "summary_uz": "Ishdan bo'shatish haqida yozma ogohlantirish muddatlari: 1) shtat qisqarishi yoki tashkilot tugatilishi — kamida 2 oy oldin; 2) malaka yetishmasligi — kamida 2 hafta oldin; 3) aybli harakatlar (mehnat intizomini buzish) — kamida 3 kun oldin. Ogohlantirish muddati pullik kompensatsiya bilan almashtirilishi mumkin (aybli asoslardan tashqari).",
        "summary_ru": "Сроки письменного предупреждения работника (ст. 165 ТК РУз): при сокращении штата/ликвидации — не менее 2 месяцев; при несоответствии квалификации — не менее 2 недель; за виновные действия — не менее 3 дней.",
        "key_tokens": ["ikki oy", "ikki hafta", "uch kun", "2 месяц", "2 недел", "3 дн"],
        "forbidden_tokens": [],
    },
    {
        "code": "Mehnat kodeksi",
        "doc_id": "6257288",
        "article": "173",
        "status": "in_force",
        "summary_uz": "Ishdan bo'shatish nafaqasi (stajga bog'liq): 3 yilgacha staj — o'rtacha oylik ish haqining 50% dan kam bo'lmagan; 3–5 yil — 75%; 5–10 yil — 100%; 10–15 yil — 150%; 15 yildan ortiq — 200% dan kam bo'lmagan miqdorda to'lanadi.",
        "summary_ru": "Выходное пособие (ст. 173 ТК РУз) зависит от стажа: до 3 лет — 50% среднего месячного заработка; 3–5 лет — 75%; 5–10 лет — 100%; 10–15 лет — 150%; свыше 15 лет — 200%.",
        "key_tokens": ["50", "75", "100", "150", "200", "staj", "выходное пособие"],
        "forbidden_tokens": [],
    },
    {
        "code": "Mehnat kodeksi",
        "doc_id": "6257288",
        "article": "217",
        "status": "in_force",
        "summary_uz": "Yillik asosiy eng kam mehnat ta'tili davomiyligi 21 kalendar kunni tashkil etadi (eski 1995-yilgi kodeksdagi 15 ish kuni normasi 2023-yil 30-apreldan o'z kuchini yo'qotgan).",
        "summary_ru": "Продолжительность ежегодного основного минимального трудового отпуска составляет 21 календарный день (ст. 217 нового ТК РУз; старая норма 15 рабочих дней утратила силу).",
        "key_tokens": ["21", "kalendar", "календарн"],
        "forbidden_tokens": ["hozir ham 15 ish kuni amalda"],
    },
    {
        "code": "Mehnat kodeksi",
        "doc_id": "6257288",
        "article": "333",
        "status": "in_force",
        "summary_uz": "Ish haqi, ta'til to'lovlari va boshqa to'lovlar muddati buzilganda ish beruvchining moddiy javobgarligi: kechiktirilgan har bir kun uchun Markaziy bank qayta moliyalash stavkasining 10 foizi miqdorida pullik kompensatsiya to'lanadi (ish beruvchining aybi bor-yo'qligidan qat'i nazar).",
        "summary_ru": "Материальная ответственность работодателя за задержку зарплаты (ст. 333 ТК РУз): денежная компенсация за каждый день просрочки в размере 10% от ставки рефинансирования ЦБ РУз независимо от вины работодателя.",
        "key_tokens": ["Markaziy bank", "10 foiz", "har bir kun", "ставки рефинансирования"],
        "forbidden_tokens": [],
    },
    {
        "code": "Mehnat kodeksi",
        "doc_id": "6257288",
        "article": "560",
        "status": "in_force",
        "summary_uz": "Yakka mehnat nizolari bo'yicha sudga murojaat qilish muddatlari: ishga tiklash to'g'risidagi nizolar bo'yicha — mehnat shartnomasi bekor qilingan buyruq nusxasi topshirilgan kundan 3 oy (eski kodeksda 1 oy edi); boshqa mehnat nizolari bo'yicha — 6 oy; ma'naviy zararni qoplash va ish haqi undirish muddatlari.",
        "summary_ru": "Сроки обращения в суд по трудовым спорам (ст. 560 ТК РУз): по спорам о восстановлении на работе — 3 месяца; по другим индивидуальным трудовым спорам — 6 месяцев.",
        "key_tokens": ["3 oy", "6 oy", "3 месяц", "6 месяц", "ishga tiklash"],
        "forbidden_tokens": [],
    },
    # --- SOLIQ KODEKSI (O'RQ-599) ---
    {
        "code": "Soliq kodeksi",
        "doc_id": "4674902",
        "article": "258",
        "status": "in_force",
        "summary_uz": "Qo'shilgan qiymat solig'i (QQS / НДС) bazaviy stavkasi 12 foiz (2023-yil 1-yanvardan O'RQ-812 bilan 15 foizdan 12 foizga tushirilgan; eksport operatsiyalari uchun 0 foiz).",
        "summary_ru": "Ставка налога на добавленную стоимость (НДС, ст. 258 НК РУз) составляет 12% (снижена с 15% с 1 января 2023 года).",
        "key_tokens": ["12", "2023", "QQS", "НДС"],
        "forbidden_claims": ["QQS stavkasi 15 foiz", "ставка НДС составляет 15%"],
    },
    {
        "code": "Soliq kodeksi",
        "doc_id": "4674902",
        "article": "337",
        "status": "in_force",
        "summary_uz": "Foyda solig'ining bazaviy stavkasi — 15 foiz. Banklar, mobil aloqa operatorlari, polietilen granulalar va sement ishlab chiqaruvchilar uchun — 20 foiz. Eksport ulushi uchun 0 foiz.",
        "summary_ru": "Базовая ставка налога на прибыль (ст. 337 НК РУз) — 15% (для банков, операторов мобильной связи, производителей цемента и полиэтилена — 20%).",
        "key_tokens": ["15", "20", "foyda solig'i", "налог на прибыль"],
        "forbidden_tokens": [],
    },
    {
        "code": "Soliq kodeksi",
        "doc_id": "4674902",
        "article": "381",
        "status": "in_force",
        "summary_uz": "Jismoniy shaxslardan olinadigan daromad solig'i (JShODS / НДФЛ) O'zbekiston rezidentlari uchun 12 foiz, dividendlar va foizlar ko'rinishidagi daromadlar uchun 5 foiz stavkada soliqqa tortiladi.",
        "summary_ru": "Ставка НДФЛ для резидентов РУз (ст. 381 НК РУз) — 12%, по доходам в виде дивидендов и процентов — 5%.",
        "key_tokens": ["12", "5", "dividend", "НДФЛ"],
        "forbidden_tokens": [],
    },
    {
        "code": "Soliq kodeksi",
        "doc_id": "4674902",
        "article": "467",
        "status": "in_force",
        "summary_uz": "Aylanmadan olinadigan soliq bazaviy stavkasi — 4 foiz (yillik jami daromadi 1 milliard so'mdan oshmaydigan tadbirkorlar uchun).",
        "summary_ru": "Базовая ставка налога с оборота (ст. 467 НК РУз) — 4% (для налогоплательщиков с совокупным годовым доходом до 1 млрд сум).",
        "key_tokens": ["4", "1 milliard", "1 млрд", "aylanmadan", "налог с оборота"],
        "forbidden_tokens": [],
    },
    # --- FUQAROLIK KODEKSI ---
    {
        "code": "Fuqarolik kodeksi",
        "doc_id": "111189",
        "article": "108",
        "status": "in_force",
        "summary_uz": "Oddiy yozma shaklda tuziladigan bitimlar: 1) yuridik shaxslar o'zaro va fuqarolar bilan tuzadigan bitimlar; 2) fuqarolarning o'zaro BHMning 10 baravaridan (10 BHM) ortiq summaga tuzadigan bitimlari yozma shaklda tuzilishi shart. Yozma shaklga rioya qilmaslik taraflarni guvohlar ko'rsatuviga asoslanish huquqidan mahrum qiladi (109-modda).",
        "summary_ru": "Простая письменная форма сделок (ст. 108 ГК РУз): обязательна для сделок юрлиц и сделок граждан между собой на сумму свыше 10 БРВ. Несоблюдение лишает права ссылаться на свидетельские показания (ст. 109).",
        "key_tokens": ["10", "BHM", "БРВ", "yozma", "guvoh", "свидетель"],
        "forbidden_tokens": [],
    },
    {
        "code": "Fuqarolik kodeksi",
        "doc_id": "111189",
        "article": "150",
        "status": "in_force",
        "summary_uz": "Umumiy da'vo muddati — 3 yil. Da'vo muddatlari va ularni hisoblash tartibi qonun bilan belgilanadi va taraflarning kelishuvi bilan o'zgartirilishi mumkin emas (153-modda).",
        "summary_ru": "Общий срок исковой давности (ст. 150 ГК РУз) — 3 года. Сроки исковой давности императивны и не могут быть изменены соглашением сторон (ст. 153).",
        "key_tokens": ["3 yil", "3 года", "uch yil", "o'zgartirilishi mumkin emas"],
        "forbidden_tokens": ["shartnoma bilan da'vo muddatini 6 oyga qisqartirish qonuniy"],
    },
    {
        "code": "Fuqarolik kodeksi",
        "doc_id": "111189",
        "article": "260",
        "status": "in_force",
        "summary_uz": "Neustoyka (jarima, penya) — majburiyat bajarilmaganda yoki kechiktirilganda qarzdor kreditorga to'lashi shart bo'lgan qonun yoki shartnomada belgilangan pul summasi. Neustoyka to'g'risidagi kelishuv asosiy majburiyat shaklidan qat'i nazar YOZMA shaklda tuzilishi shart (262-modda).",
        "summary_ru": "Неустойка (штраф, пеня, ст. 260–262 ГК РУз) — денежная сумма за неисполнение обязательства; соглашение о неустойке должно быть совершено в письменной форме независимо от формы основного обязательства.",
        "key_tokens": ["neustoyka", "jarima", "penya", "yozma", "неустойк"],
        "forbidden_tokens": [],
    },
    {
        "code": "Fuqarolik kodeksi",
        "doc_id": "111189",
        "article": "326",
        "status": "in_force",
        "summary_uz": "Neustoykani kamaytirish: agar to'lanishi lozim bo'lgan neustoyka kreditorning majburiyatni buzish oqibatlariga nomutanosib darajada katta bo'lsa, sud neustoykani kamaytirishga haqli.",
        "summary_ru": "Уменьшение неустойки судом (ст. 326 ГК РУз): если подлежащая уплате неустойка явно несоразмерна последствиям нарушения обязательства, суд вправе уменьшить неустойку.",
        "key_tokens": ["kamaytirish", "nomutanosib", "sud", "уменьшить", "несоразмерн"],
        "forbidden_tokens": ["sud neustoykani hech qachon kamaytira olmaydi"],
    },
    {
        "code": "Fuqarolik kodeksi",
        "doc_id": "111189",
        "article": "354",
        "status": "in_force",
        "summary_uz": "Shartnoma erkinligi: fuqarolar va yuridik shaxslar shartnoma tuzishda erkindirlar, biroq shartnoma qonunchilikdagi imperativ normalarga muvofiq bo'lishi shart (353-modda).",
        "summary_ru": "Свобода договора (ст. 354 ГК РУз) с обязательным соблюдением императивных норм закона (ст. 353).",
        "key_tokens": ["shartnoma erkinligi", "imperativ", "свобода договора"],
        "forbidden_tokens": [],
    },
    # --- OILA KODEKSI ---
    {
        "code": "Oila kodeksi",
        "doc_id": "104720",
        "article": "15",
        "status": "in_force",
        "summary_uz": "Nikoh yoshi erkaklar va ayollar uchun bir xil — 18 yosh etib belgilangan (2019-yildan ayollar uchun eski 17 yosh normasi bekor qilinib 18 yoshga tenglashtirilgan). Uzrli sabablar bo'lganda tuman/shahar hokimi nikoh yoshini ko'pi bilan 1 yilga kamaytirishi mumkin.",
        "summary_ru": "Брачный возраст (ст. 15 СК РУз) устанавливается для мужчин и женщин в 18 лет (прежняя норма 17 лет для женщин отменена). Хоким района/города при уважительных причинах может снизить возраст не более чем на 1 год.",
        "key_tokens": ["18 yosh", "18 лет", "1 yilga", "hokim"],
        "forbidden_tokens": ["ayollar uchun nikoh yoshi 17 yosh"],
    },
    {
        "code": "Oila kodeksi",
        "doc_id": "104720",
        "article": "39",
        "status": "in_force",
        "summary_uz": "Xotinining homiladorlik vaqtida va bola tug'ilganidan keyin 1 yil mobaynida er xotinining roziligisiz nikohdan ajratish to'g'risida ish qo'zg'atishga haqli emas.",
        "summary_ru": "Недопустимость предъявления мужем требования о расторжении брака (ст. 39 СК РУз) во время беременности жены и в течение 1 года после рождения ребенка без согласия жены.",
        "key_tokens": ["homilador", "1 yil", "roziligisiz", "беременност"],
        "forbidden_tokens": [],
    },
    {
        "code": "Oila kodeksi",
        "doc_id": "104720",
        "article": "99",
        "status": "in_force",
        "summary_uz": "Voyaga yetmagan bolalar ta'minoti uchun aliment miqdori: 1 bola — daromadning 1/4 (25%) qismi; 2 bola — 1/3 (33.3%); 3 va undan ortiq bola — 1/2 (50%). Har bir bola uchun undiriladigan eng kam aliment miqdori Mehnatga haq to'lashning eng kam miqdori (MHTEKM / МРОТ) ning 26,5 foizidan kam bo'lmasligi shart (BHMga emas!).",
        "summary_ru": "Размер алиментов (ст. 99 СК РУз): на 1 ребенка — 1/4, на 2 детей — 1/3, на 3 и более — 1/2 заработка. Минимальный размер на каждого ребенка — не менее 26,5% МРОТ (МҲТЭКМ, а не БРВ!).",
        "key_tokens": ["1/4", "1/3", "1/2", "26,5", "MHTEKM", "МРОТ"],
        "forbidden_tokens": ["BHMning 26,5 foizi"],
    },
    # --- JINOYAT KODEKSI ---
    {
        "code": "Jinoyat kodeksi",
        "doc_id": "111453",
        "article": "168",
        "status": "in_force",
        "summary_uz": "Firibgarlik (aldash yoki ishonchni suiiste'mol qilish yo'li bilan o'zganing mulkini qo'lga kiritish). Muhim rag'batlantiruvchi norma: yetkazilgan moddiy zararning o'rni to'liq qoplangan taqdirda ozodlikni cheklash va ozodlikdan mahrum qilish tariqasidagi jazo qo'llanilmaydi.",
        "summary_ru": "Мошенничество (ст. 168 УК РУз): в случае полного возмещения причиненного материального ущерба наказание в виде ограничения свободы и лишения свободы не применяется.",
        "key_tokens": ["qoplangan", "ozodlikdan mahrum qilish", "возмещения", "лишения свободы не применяется"],
        "forbidden_tokens": [],
    },
    {
        "code": "Jinoyat kodeksi",
        "doc_id": "111453",
        "article": "184",
        "status": "in_force",
        "summary_uz": "Soliqlar yoki yig'imlarni to'lashdan bo'yin tovlash. Muhim istisno: birinchi marta jinoyat sodir etgan shaxs davlat soliq xizmati qarorini olgan kundan 30 kun ichida soliqlar, penya va moliyaviy sanksiyalar tarzida davlatga yetkazilgan zararning o'rnini to'liq qoplasa, javobgarlikdan ozod qilinadi.",
        "summary_ru": "Уклонение от уплаты налогов (ст. 184 УК РУз): лицо, впервые совершившее преступление, освобождается от ответственности, если в течение 30 дней полностью возместило ущерб в виде налогов, пени и санкций.",
        "key_tokens": ["30 kun", "30 дней", "birinchi marta", "javobgarlikdan ozod"],
        "forbidden_tokens": [],
    },
    # --- MA'MURIY JAVOBGARLIK TO'G'RISIDAGI KODEKS (MJtK) ---
    {
        "code": "MJtK",
        "doc_id": "97664",
        "article": "332-1",
        "status": "in_force",
        "summary_uz": "Jarimani to'lashning soddalashtirilgan tartibi: qaror topshirilgan kundan 15 kun ichida jarima miqdorining 50% (50% chegirma), 30 kun ichida 70% (30% chegirma) ixtiyoriy to'lansa, qolgan qismidan ozod qilinadi. ISTISNO: mast holda transport boshqarish (131-modda), tibbiy ko'rikdan bo'yin tovlash (136-modda) va sud tomonidan tayinlangan jarimalarga chegirma qo'llanilmaydi!",
        "summary_ru": "Упрощенный порядок уплаты штрафа (ст. 332-1 КоАО РУз): 50% в течение 15 дней, 70% (скидка 30%) в течение 30 дней. ИСКЛЮЧЕНИЕ: не применяется при вождении в состоянии опьянения (ст. 131, 136) и по постановлениям суда!",
        "key_tokens": ["15", "30", "50", "70", "131"],
        "forbidden_tokens": ["mast holda haydaganda ham 50% chegirma bor"],
    },
    # --- SHAXSGA DOIR MA'LUMOTLAR TO'G'RISIDA (O'RQ-547) ---
    {
        "code": "Shaxsga doir ma'lumotlar to'g'risida",
        "doc_id": "4396419",
        "article": "27-1",
        "status": "in_force",
        "summary_uz": "O'zbekiston fuqarolarining shaxsga doir ma'lumotlariga IT orqali ishlov berishda mulkdor va operator ularni jisman O'zbekiston Respublikasi hududida joylashgan texnik vositalarda (serverlarda) hamda Shaxsga doir ma'lumotlar bazalarining davlat reyestrida ro'yxatdan o'tkazilgan bazalarda yig'ish va saqlashni ta'minlashi shart.",
        "summary_ru": "Локализация персональных данных граждан РУз (ст. 27-1 ЗРУ-547): сбор, систематизация и хранение должны осуществляться на технических средствах, физически размещенных на территории Узбекистана, с регистрацией в Государственном реестре баз персональных данных.",
        "key_tokens": ["O'zbekiston", "hududida", "davlat reyestr", "территории Узбекистана"],
        "forbidden_tokens": [],
    },
    # --- ISTE'MOLCHILAR HUQUQLARINI HIMOYA QILISH TO'G'RISIDA ---
    {
        "code": "Iste'molchilarning huquqlarini himoya qilish to'g'risida",
        "doc_id": "4704",
        "article": "19",
        "status": "in_force",
        "summary_uz": "Nuqsonli tovarni almashtirish, qaytarish yoki ta'mirlash muddatlari buzilganda sotuvchi (ishlab chiqaruvchi) iste'molchiga kechiktirilgan har bir kun uchun tovar bahosining 1 foizi miqdorida neustoyka (penya) to'laydi.",
        "summary_ru": "За просрочку выполнения требований потребителя (ст. 19 Закона «О защите прав потребителей») продавец уплачивает неустойку (пеню) в размере 1% цены товара за каждый день просрочки.",
        "key_tokens": ["1 foiz", "1%", "har bir kun", "неустойк"],
        "forbidden_tokens": [],
    },
    # --- MANFAATLAR TO'QNASHUVI TO'G'RISIDA (O'RQ-931, 2024) ---
    {
        "code": "Manfaatlar to'qnashuvi to'g'risida",
        "doc_id": "6952742",
        "article": "21",
        "status": "in_force",
        "summary_uz": "2024-yil 5-iyundagi O'RQ-931-son 'Manfaatlar to'qnashuvi to'g'risida'gi Qonun: davlat organi xodimi mavjud manfaatlar to'qnashuvi haqida 1 ish kuni ichida o'z rahbariga yozma xabar berishi shart; manfaatlar to'qnashuviga yo'l qo'yib tuzilgan bitimlar va qabul qilingan qarorlar sud tartibida haqiqiy emas deb topiladi.",
        "summary_ru": "Закон РУз «О конфликте интересов» ЗРУ-931 от 05.06.2024: сотрудник госоргана обязан уведомить о реальном конфликте интересов в течение 1 рабочего дня; сделки и решения, принятые в условиях конфликта интересов, признаются недействительными в судебном порядке.",
        "key_tokens": ["O'RQ-931", "1 ish kuni", "haqiqiy emas", "конфликте интересов"],
        "forbidden_tokens": [],
    },
    # --- FUQAROLIK KODEKSI: QARZ VA TILXAT (732-735, 109, 327) ---
    {
        "code": "Fuqarolik kodeksi",
        "doc_id": "111189",
        "article": "109",
        "status": "in_force",
        "summary_uz": "Bitimning oddiy yozma shakliga rioya qilmaslik uning haqiqiy emasligiga olib kelmaydi (qonunda to'g'ridan-to'g'ri ko'rsatilgan hollardan tashqari), biroq nizo chiqqan taqdirda taraflarni bitim tuzilganligini tasdiqlash uchun guvohlar ko'rsatuviga asoslanish huquqidan mahrum qiladi.",
        "summary_ru": "Несоблюдение простой письменной формы сделки (ст. 109 ГК РУз) не влечет ее недействительности, но лишает стороны права в случае спора ссылаться в подтверждение сделки на свидетельские показания.",
        "key_tokens": ["guvohlar", "haqiqiy emasligiga olib kelmaydi", "свидетельские показания"],
        "forbidden_tokens": ["o'z-o'zidan haqiqiy emas hisoblanadi"],
    },
    {
        "code": "Fuqarolik kodeksi",
        "doc_id": "111189",
        "article": "327",
        "status": "in_force",
        "summary_uz": "Boshqa shaxsning pul mablag'larini qonunsiz ushlab qolish, qaytarib bermaslik yoki kechiktirish natijasida ular uchun foizlar to'lanishi lozim. Foiz miqdori kreditor yashaydigan joyda bank hisob stavkasi (Markaziy bank asosiy stavkasi) bilan belgilanadi.",
        "summary_ru": "Ответственность за неисполнение денежного обязательства (ст. 327 ГК РУз): уплата процентов на сумму этих средств по учетной ставке Центрального банка.",
        "key_tokens": ["327", "bank hisob stavkasi", "Markaziy bank", "процентов"],
        "forbidden_tokens": [],
    },
    {
        "code": "Fuqarolik kodeksi",
        "doc_id": "111189",
        "article": "732",
        "status": "in_force",
        "summary_uz": "Qarz shartnomasi bo'yicha bir taraf (qarz beruvchi) ikkinchi tarafga (qarz oluvchiga) pul yoki ashyolarni mulk qilib beradi, qarz oluvchi esa bir xil miqdordagi pulni (qarz summasini) qaytarib berish majburiyatini oladi. Qarz shartnomasi pul yoki ashyolar topshirilgan paytdan boshlab tuzilgan hisoblanadi (real shartnoma).",
        "summary_ru": "Договор займа (ст. 732 ГК РУз) считается заключенным с момента передачи денег или других вещей (реальный договор).",
        "key_tokens": ["732", "topshirilgan paytdan", "real shartnoma", "передачи денег"],
        "forbidden_tokens": [],
    },
    {
        "code": "Fuqarolik kodeksi",
        "doc_id": "111189",
        "article": "733",
        "status": "in_force",
        "summary_uz": "Fuqarolar o'rtasida qarz shartnomasi, agar bu qarzning summasi bazaviy hisoblash miqdorining (BHM) o'n baravaridan ortiq bo'lsa, oddiy yozma shaklda tuzilishi shart; shartnomada taraflardan biri yuridik shaxs bo'lganida esa summasidan qat'i nazar yozma tuziladi. Qarz oluvchining tilxati qarz shartnomasini tasdiqlaydi.",
        "summary_ru": "Форма договора займа (ст. 733 ГК РУз): между гражданами должен быть заключен в письменной форме, если его сумма превышает 10 БРВ. В подтверждение договора займа может быть представлена расписка заемщика (тилхат).",
        "key_tokens": ["733", "o'n baravar", "10", "tilxat", "расписка"],
        "forbidden_tokens": ["notarial tasdiqlanishi shart"],
    },
    {
        "code": "Fuqarolik kodeksi",
        "doc_id": "111189",
        "article": "734",
        "status": "in_force",
        "summary_uz": "Qarz shartnomasi bo'yicha foizlar: agar qonunda yoki shartnomada boshqacha tartib nazarda tutilgan bo'lmasa, qarz beruvchi qarz oluvchidan qarz summasiga foizlar olish huquqiga ega. Fuqarolar o'rtasida BHMning 50 baravaridan oshmaydigan va tadbirkorlik bilan bog'liq bo'lmagan qarz shartnomasi foizsiz deb hisoblanadi (agar shartnomada foiz to'g'ridan-to'g'ri yozilmagan bo'lsa).",
        "summary_ru": "Проценты по договору займа (ст. 734 ГК РУз): договор займа между гражданами на сумму не свыше 50 БРВ, не связанный с предпринимательством, предполагается беспроцентным.",
        "key_tokens": ["734", "50 baravar", "foizsiz", "беспроцентным"],
        "forbidden_tokens": [],
    },
    {
        "code": "Fuqarolik kodeksi",
        "doc_id": "111189",
        "article": "735",
        "status": "in_force",
        "summary_uz": "Qarz oluvchining qarz summasini qaytarish majburiyati: agar qaytarish muddati shartnomada belgilangan bo'lmasa, qarz oluvchi uni qarz beruvchi talab qo'ygan kundan boshlab 30 kun ichida qaytarishi shart.",
        "summary_ru": "Обязанность заемщика возвратить сумму займа (ст. 735 ГК РУз): если срок возврата не установлен договором, сумма займа должна быть возвращена в течение 30 дней со дня предъявления требования.",
        "key_tokens": ["735", "30 kun", "30 дней", "talab qo'ygan"],
        "forbidden_tokens": [],
    },
    # --- MEHNAT KODEKSI (O'RQ-798): QO'SHIMCHA OLTIN MODDALAR ---
    {
        "code": "Mehnat kodeksi",
        "doc_id": "6257288",
        "article": "130",
        "status": "in_force",
        "summary_uz": "Dastlabki sinov davrida mehnat shartnomasini bekor qilish: sinov muddati tugagunga qadar har bir taraf ikkinchi tarafni kamida 3 kun oldin yozma ravishda ogohlantirib mehnat shartnomasini bekor qilishga haqli (ogohlantirmasdan bo'shatish taqiqlanadi!).",
        "summary_ru": "Прекращение трудового договора в период предварительного испытания (ст. 130 ТК РУз): каждая из сторон вправе прекратить договор, письменно предупредив другую сторону не менее чем за 3 дня.",
        "key_tokens": ["130", "3 kun", "uch kun", "yozma", "3 дня"],
        "forbidden_tokens": ["ogohlantirmasdan ishdan bo'shatish mumkin"],
    },
    {
        "code": "Mehnat kodeksi",
        "doc_id": "6257288",
        "article": "405",
        "status": "in_force",
        "summary_uz": "Homilador ayollar bilan tuzilgan mehnat shartnomasini ish beruvchining tashabbusiga ko'ra bekor qilishga yo'l qo'yilmaydi, tashkilot (yakka tartibdagi tadbirkor) to'liq tugatilgan hollar bundan mustasno.",
        "summary_ru": "Гарантии беременным женщинам при прекращении трудового договора (ст. 405 ТК РУз): увольнение беременных женщин по инициативе работодателя не допускается, кроме полной ликвидации организации.",
        "key_tokens": ["405", "homilador", "yo'l qo'yilmaydi", "tugatilgan"],
        "forbidden_tokens": [],
    },
    # --- JINOYAT-PROTSESSUAL KODEKSI (JPK) ---
    {
        "code": "Jinoyat-protsessual kodeksi",
        "doc_id": "111460",
        "article": "226",
        "status": "in_force",
        "summary_uz": "Ushlab turish muddati shaxs ichki ishlar organiga yoki huquqni muhofaza qiluvchi organga keltirilgan paytdan e'tiboran ko'pi bilan 48 soatni tashkil etadi. Sud tomonidan qamoqqa olish tarzidagi ehtiyot chorasi qo'llanilmasa, shaxs darhol ozod qilinishi shart.",
        "summary_ru": "Срок задержания (ст. 226 УПК РУз) составляет не более 48 часов с момента доставления задержанного. Без решения суда о заключении под стражу лицо подлежит немедленному освобождению.",
        "key_tokens": ["226", "48 soat", "48 часов", "sud"],
        "forbidden_tokens": ["72 soat ushlab turiladi"],
    },
    # --- FUQAROLIK PROTSESSUAL KODEKSI (FPK) ---
    {
        "code": "Fuqarolik protsessual kodeksi",
        "doc_id": "3517337",
        "article": "140",
        "status": "in_force",
        "summary_uz": "Sud buyrug'i chiqariladigan talablar: 1) notarial tasdiqlangan bitimga asoslangan talab; 2) oddiy yozma bitimga (tilxatga) asoslangan va qarzdor tomonidan tan olingan talab; 3) voyaga yetmagan bolalar uchun aliment undirish haqidagi talab; 4) hisoblangan lekin to'lanmagan ish haqini undirish talabi.",
        "summary_ru": "Требования, по которым выдается судебный приказ (ст. 140 ГПК РУз): по нотариальной сделке, по простой письменной сделке (расписке), о взыскании алиментов на несовершеннолетних детей, о взыскании начисленной зарплаты.",
        "key_tokens": ["140", "sud buyrug'i", "aliment", "yozma", "судебный приказ"],
        "forbidden_tokens": [],
    },
    # --- YER KODEKSI (YK) ---
    {
        "code": "Yer kodeksi",
        "doc_id": "152653",
        "article": "36",
        "status": "in_force",
        "summary_uz": "Yer uchastkalariga bo'lgan huquqlarni bekor qilish asoslari va tartibi: yerdan belgilangan maqsaddan tashqari foydalanilganda yoki qonunchilik buzilganda yerga bo'lgan huquqni bekor qilish faqat SUD tartibida amalga oshiriladi (hokim qarori bilan bir tomonlama olib qo'yish taqiqlangan).",
        "summary_ru": "Прекращение прав на земельные участки (ст. 36–37 ЗК РУз) за нарушение земельного законодательства осуществляется исключительно в СУДЕБНОМ порядке.",
        "key_tokens": ["36", "sud tartibida", "судебном порядке"],
        "forbidden_tokens": ["hokim qarori bilan sudsiz olib qo'yiladi"],
    },
    # --- MJtK 131-MODDA ---
    {
        "code": "MJtK",
        "doc_id": "97664",
        "article": "131",
        "status": "in_force",
        "summary_uz": "Transport vositalarini mast holda boshqarish: transport vositasini boshqarish huquqidan 1 yilu 6 oydan 3 yilgacha muddatga mahrum qilib, BHMning 25 baravari miqdorida jarima solishga sabab bo'ladi. Ushbu modda bo'yicha MJtK 332-1-moddadagi 50%/30% jarima chegirmasi QO'LLANILMAYDI.",
        "summary_ru": "Управление транспортными средствами в состоянии опьянения (ст. 131 КоАО РУз): лишение права управления от 1,5 до 3 лет со штрафом 25 БРВ. Скидка 50%/30% по ст. 332-1 НЕ ПРИМЕНЯЕТСЯ.",
        "key_tokens": ["131", "25 baravar", "3 yil", "chegirma qo'llanilmaydi"],
        "forbidden_tokens": ["50% chegirma beriladi"],
    },
    # --- IQTISODIY PROTSESSUAL KODEKSI (IPK), MSIYuTK, BOJXONA, UY-JOY, MChJ, ADVOKATURA, SUDLAR ---
    {
        "code": "Iqtisodiy protsessual kodeksi",
        "doc_id": "3523891",
        "article": "259",
        "status": "in_force",
        "summary_uz": "Birinchi instansiya iqtisodiy sudining hal qiluv qarori ustidan apellyatsiya shikoyati (protesti) hal qiluv qarori qabul qilingan kundan e'tiboran 1 oy ichida berilishi mumkin.",
        "summary_ru": "Апелляционная жалоба (протест) на решение экономического суда первой инстанции подается в течение 1 месяца со дня принятия решения (ст. 259 ЭПК РУз).",
        "key_tokens": ["259", "1 oy", "apellyatsiya", "1 месяц"],
        "forbidden_tokens": ["10 kun ichida apellyatsiya"],
    },
    {
        "code": "Ma'muriy sud ishlarini yuritish kodeksi",
        "doc_id": "3527353",
        "article": "186",
        "status": "in_force",
        "summary_uz": "Ma'muriy organning, fuqarolar o'zini o'zi boshqarish organining qarorlari, mansabdor shaxslarning harakatlari (harakatsizligi) ustidan ma'muriy sudga ariza (shikoyat) manfaatdor shaxsga o'z huquqlari buzilganligi ma'lum bo'lgan kundan e'tiboran 3 oy ichida beriladi.",
        "summary_ru": "Заявление (жалоба) на решения административного органа подается в административный суд в течение 3 месяцев со дня, когда лицу стало известно о нарушении его прав (ст. 186 КоАС РУз).",
        "key_tokens": ["186", "3 oy", "ma'muriy sud", "3 месяца"],
        "forbidden_tokens": [],
    },
    {
        "code": "Uy-joy kodeksi",
        "doc_id": "106136",
        "article": "27",
        "status": "in_force",
        "summary_uz": "Yer uchastkalari davlat va jamoat ehtiyojlari uchun olib qo'yilishi munosabati bilan fuqarolar mulkidagi uylar (kvartiralar) buzilganda mulkdorlarga ularning tanloviga ko'ra oldindan va to'liq hajmda teng qiymatli uy-joy yoki bozor qiymati hamda barcha zararlar qoplanishi shart.",
        "summary_ru": "При сносе жилых домов в связи с изъятием земельного участка для государственных и общественных нужд (ст. 27–32 ЖК РУз) собственникам предоставляется предварительное и полное возмещение по рыночной стоимости.",
        "key_tokens": ["27", "oldindan", "to'liq", "bozor qiymati"],
        "forbidden_tokens": ["keyinchalik to'lanadi"],
    },
    {
        "code": "Bojxona kodeksi",
        "doc_id": "2876354",
        "article": "297",
        "status": "in_force",
        "summary_uz": "Bojxona to'lovlarini to'lash majburiyati bojxona deklaratsiyasi qabul qilingan paytdan e'tiboran yuzaga keladi; kechiktirilgan har bir kun uchun penya hisoblanadi.",
        "summary_ru": "Обязанность по уплате таможенных платежей возникает с момента принятия таможенной декларации (ст. 297 ТК РУз).",
        "key_tokens": ["297", "bojxona deklaratsiyasi"],
        "forbidden_tokens": [],
    },
    {
        "code": "Mas'uliyati cheklangan jamiyatlar to'g'risida",
        "doc_id": "18793",
        "article": "44",
        "status": "in_force",
        "summary_uz": "Yirik bitim: qiymati jamiyat mol-mulki balans qiymatining 25 foizidan ortiq bo'lgan mol-mulkni olish yoki boshqa shaxsga berish bilan bog'liq bitim yirik bitim hisoblanadi va ishtirokchilar umumiy yig'ilishi (yoki kuzatuv kengashi) qarori bilan ma'qullanishi shart.",
        "summary_ru": "Крупная сделка ООО (ст. 44 Закона об ООО): сделка, связанная с приобретением или отчуждением имущества стоимостью более 25% балансовой стоимости имущества общества, требует одобрения общего собрания участников.",
        "key_tokens": ["44", "25 foiz", "yirik bitim", "25%"],
        "forbidden_tokens": [],
    },
    {
        "code": "Advokatura to'g'risida",
        "doc_id": "58372",
        "article": "7",
        "status": "in_force",
        "summary_uz": "Advokat so'rovi: davlat organlari, korxonalar va muassasalar advokatning yuridik yordam ko'rsatish bilan bog'liq yozma so'roviga so'rov olingan kundan e'tiboran kechi bilan 15 kun ichida ma'lumotlar va hujjatlar taqdim etishi shart.",
        "summary_ru": "Адвокатский запрос (ст. 7 Закона «Об адвокатуре»): госорганы и организации обязаны дать письменный ответ на запрос адвоката не позднее 15 дней со дня его получения.",
        "key_tokens": ["7", "15 kun", "advokat so'rovi", "15 дней"],
        "forbidden_tokens": ["30 kun ichida javob beradi"],
    },
    {
        "code": "Sudlar to'g'risida",
        "doc_id": "5534923",
        "article": "9",
        "status": "in_force",
        "summary_uz": "Sudyalarning mustaqilligi: sudyalar mustaqildirlar, faqat Konstitutsiya va qonunga bo'ysunadilar. Sudyalarning odil sudlovni amalga oshirish borasidagi faoliyatiga biror-bir tarzda aralashishga yo'l qo'yilmaydi va bunday aralashuv qonunga muvofiq javobgarlikka sabab bo'ladi.",
        "summary_ru": "Независимость судей (ст. 9 ЗРУ-703 «О судах»): судьи независимы и подчиняются только Конституции и закону. Вмешательство в деятельность судей недопустимо.",
        "key_tokens": ["9", "mustaqil", "Konstitutsiya va qonun"],
        "forbidden_tokens": [],
    },
    # --- DATA.EGOV.UZ (OPEN DATA PORTAL, E-GOVERNMENT, MACRO-INDICATORS BHM/MHTEKM, PF-6247, O'RQ-369, O'RQ-395, O'RQ-792) ---
    {
        "code": "Ochiq ma'lumotlar portali va davlat organlari ochiqligi (PF-6247)",
        "doc_id": "5459107",
        "article": "1",
        "status": "in_force",
        "summary_uz": "O'zbekiston Respublikasi Ochiq ma'lumotlar portali (https://data.egov.uz) va PF-6247-son Prezident Farmoni: barcha davlat organlari va tashkilotlari ijtimoiy ahamiyatga molik ma'lumotlarni (davlat xaridlari, byudjet xarajatlari, litsenziyalar, bo'sh ish o'rinlari, statistika) data.egov.uz portalida mashinada o'qiladigan formatda (JSON/CSV/XML/API) joylashtirib borishi va belgilangan muddatlarda yangilashi majburiy. Ochiqlik talablarini buzish MJtK 215-7-modda bo'yicha ma'muriy javobgarlikka sabab bo'ladi.",
        "summary_ru": "Портал открытых данных Республики Узбекистан (https://data.egov.uz, УП-6247 от 16.06.2021): все государственные органы обязаны публиковать социально значимые сведения (госзакупки, расходы бюджета, реестры, статистику) на data.egov.uz в машиночитаемых форматах. Нарушение влечет ответственность по ст. 215-7 КоАО РУз.",
        "key_tokens": ["data.egov.uz", "PF-6247", "ochiq ma'lumotlar", "215-7", "открытых данных"],
        "forbidden_tokens": ["data.egov.uz da joylashtirish ixtiyoriy"],
    },
    {
        "code": "Davlat hokimiyati va boshqaruvi organlari faoliyatining ochiqligi to'g'risida",
        "doc_id": "2381133",
        "article": "19",
        "status": "in_force",
        "summary_uz": "O'RQ-369-son Qonun 19-modda: axborotdan foydalanuvchining davlat hokimiyati va boshqaruvi organlari faoliyati to'g'risida axborot olishga doir so'rovi ro'yxatdan o'tkazilgan kundan e'tiboran ko'pi bilan 15 kun muddatda ko'rib chiqilishi shart (OAV so'rovlari — ko'pi bilan 7 kun muddatda).",
        "summary_ru": "Ст. 19 Закона ЗРУ-369 «Об открытости деятельности органов государственной власти и управления»: запрос пользователя информации подлежит рассмотрению в срок не более 15 дней со дня регистрации (запрос СМИ — не более 7 дней).",
        "key_tokens": ["19", "15 kun", "7 kun", "O'RQ-369", "15 дней", "7 дней"],
        "forbidden_tokens": ["30 kun ichida ko'rib chiqiladi"],
    },
    {
        "code": "Elektron hukumat to'g'risida",
        "doc_id": "2833860",
        "article": "18",
        "status": "in_force",
        "summary_uz": "O'RQ-395-son 'Elektron hukumat to'g'risida'gi Qonun 18–19-moddalari ('Bir darcha' prinsipi va idoralararo integratsiya): elektron davlat xizmatlari ko'rsatishda boshqa davlat organlarida va data.egov.uz / elektron hukumat bazalarida mavjud bo'lgan hujjat va ma'lumotlarni arizachidan (fuqarolardan va tadbirkorlardan) talab qilish QAT'IYAN TAQIQLANADI.",
        "summary_ru": "Ст. 18–19 Закона ЗРУ-395 «Об электронном правительстве» (принцип «одно окно»): госорганам запрещается требовать от заявителей документы и сведения, имеющиеся в других государственных органах и базах электронного правительства.",
        "key_tokens": ["18", "bir darcha", "talab qilish taqiqlanadi", "O'RQ-395", "одно окно"],
        "forbidden_tokens": ["fuqarolardan qog'oz ma'lumotnoma olib kelishni talab qilishga haqli"],
    },
    {
        "code": "Elektron tijorat to'g'risida",
        "doc_id": "6213382",
        "article": "13",
        "status": "in_force",
        "summary_uz": "O'RQ-792-son 'Elektron tijorat to'g'risida'gi Qonun 13–15-moddalari: elektron tijoratdagi elektron shartnoma (oferta va aksept, ERI yoki elektron tasdiq orqali tuzilgan bitim) qog'ozda tuzilgan va o'z qo'li bilan imzolangan shartnomaga teng yuridik kuchga ega bo'lib, faqat elektron shaklda tuzilganligi sababli haqiqiy emas deb topilishi mumkin emas.",
        "summary_ru": "Ст. 13–15 Закона ЗРУ-792 «Об электронной коммерции»: электронный договор в электронной коммерции приравнивается к договору на бумажном носителе, подписанному собственноручно, и не может быть признан недействительным только на том основании, что он заключен в электронной форме.",
        "key_tokens": ["13", "elektron shartnoma", "yuridik kuchga ega", "O'RQ-792", "электронный договор"],
        "forbidden_tokens": ["elektron shartnoma sudda dalil bo'la olmaydi"],
    },
    # --- EXTENDED GOLDEN ARTICLES (BLIND TRAINING CORE: LABOR, FAMILY, CIVIL, TAX, CRIMINAL, MJTK, APPEALS) ---
    {
        "code": "Mehnat kodeksi",
        "doc_id": "6257288",
        "article": "160",
        "status": "in_force",
        "summary_uz": "Yangi Mehnat kodeksi 160-modda: xodim mehnat shartnomasini o'z tashabbusi bilan bekor qilish to'g'risida ish beruvchini kamida 14 kalendar kun oldin yozma shaklda ogohlantirishga haqli (tashkilot rahbari, o'rinbosari va bosh buxgalter uchun — 2 oy).",
        "summary_ru": "Ст. 160 Трудового кодекса РУз: работник вправе расторгнуть трудовой договор по своей инициативе, письменно предупредив работодателя не менее чем за 14 календарных дней.",
        "key_tokens": ["160", "14 kalendar kun", "14 календарных дней"],
        "forbidden_tokens": ["1 oy oldin ogohlantirishi shart"],
    },
    {
        "code": "Mehnat kodeksi",
        "doc_id": "6257288",
        "article": "188",
        "status": "in_force",
        "summary_uz": "Mehnat kodeksi 188 va 264-moddalar: soat 22:00 dan to soat 06:00 gacha bo'lgan vaqt tungi ish vaqti hisoblanadi. Tungi vaqtdagi ishning har bir soati uchun kamida bir yarim (1,5) baravar miqdorda haq to'lanadi.",
        "summary_ru": "Ст. 188 и 264 Трудового кодекса РУз: ночным считается время с 22:00 до 06:00. Каждый час работы в ночное время оплачивается не менее чем в полуторном (1,5) размере.",
        "key_tokens": ["188", "264", "22:00", "06:00", "1,5"],
        "forbidden_tokens": ["tungi ish oddiy stavkada to'lanadi"],
    },
    {
        "code": "Mehnat kodeksi",
        "doc_id": "6257288",
        "article": "333",
        "status": "in_force",
        "summary_uz": "Mehnat kodeksi 333-modda: ish beruvchi ish haqini to'lash muddatini buzgan taqdirda, to'lov kechiktirilgan har bir kun uchun O'zbekiston Respublikasi Markaziy banki qayta moliyalashtirish (asosiy) stavkasining 10 foizi miqdorida xodimga pulli kompensatsiya to'lashi shart.",
        "summary_ru": "Ст. 333 Трудового кодекса РУз: при нарушении срока выплаты зарплаты работодатель обязан выплатить денежную компенсацию в размере 10% основной ставки ЦБ РУз за каждый день просрочки.",
        "key_tokens": ["333", "10", "Markaziy bank", "kompensatsiya"],
        "forbidden_tokens": ["ish haqi kechiktirilganda kompensatsiya to'lanmaydi"],
    },
    {
        "code": "Mehnat kodeksi",
        "doc_id": "6257288",
        "article": "408",
        "status": "in_force",
        "summary_uz": "Mehnat kodeksi 408-modda: homilador ayollar bilan tuzilgan mehnat shartnomasini ish beruvchi tashabbusi bilan bekor qilish (shu jumladan shtat qisqarishi sababli) qat'iyan taqiqlanadi, tashkilot to'liq tugatilgan hollar bundan mustasno.",
        "summary_ru": "Ст. 408 Трудового кодекса РУз: расторжение трудового договора с беременными женщинами по инициативе работодателя запрещается, кроме случаев полной ликвидации организации.",
        "key_tokens": ["408", "homilador", "taqiqlanadi", "tugatil"],
        "forbidden_tokens": ["homilador ayolni shtat qisqarishi bilan bo'shatish mumkin"],
    },
    {
        "code": "Mehnat kodeksi",
        "doc_id": "6257288",
        "article": "415",
        "status": "in_force",
        "summary_uz": "Mehnat kodeksi 415–417-moddalar: 16 yoshdan 18 yoshgacha bo'lgan xodimlar uchun ish vaqti haftasiga 36 soatdan oshmaydigan qisqartirilgan muddatda belgilanadi; ularni tungi va ish vaqtidan tashqari ishlarga jalb qilish taqiqlanadi.",
        "summary_ru": "Ст. 415–417 Трудового кодекса РУз: для работников от 16 до 18 лет рабочее время не превышает 36 часов в неделю; привлечение к ночным и сверхурочным работам запрещено.",
        "key_tokens": ["415", "36 soat", "tungi"],
        "forbidden_tokens": ["17 yoshli xodim haftasiga 40 soat"],
    },
    {
        "code": "Mehnat kodeksi",
        "doc_id": "6257288",
        "article": "452",
        "status": "in_force",
        "summary_uz": "Mehnat kodeksi 452–463-moddalar: masofadan turib ishlovchi xodimlar barcha mehnat huquqlari va kafolatlaridan, shu jumladan kamida 21 kalendar kunlik haq to'lanadigan yillik mehnat ta'tilidan to'liq foydalanadilar.",
        "summary_ru": "Ст. 452–463 Трудового кодекса РУз: дистанционные работники пользуются всеми трудовыми правами и гарантиями, включая оплачиваемый ежегодный отпуск не менее 21 календарного дня.",
        "key_tokens": ["452", "masofaviy", "21"],
        "forbidden_tokens": ["masofaviy xodimga ta'til berilmaydi"],
    },
    {
        "code": "Oila kodeksi",
        "doc_id": "104720",
        "article": "23",
        "status": "in_force",
        "summary_uz": "Oila kodeksi 23-modda: er va xotinning nikoh davomida orttirgan mol-mulklari ularning umumiy birgalikdagi mulkidir. Uy-ro'zg'or va bolalar parvarishi bilan band bo'lib mustaqil daromadga ega bo'lmagan er (xotin) ham umumiy mulkka nisbatan teng huquqqa ega.",
        "summary_ru": "Ст. 23 Семейного кодекса РУз: имущество, нажитое супругами во время брака, является их общей совместной собственностью; супруг, занимавшийся домашним хозяйством и уходом за детьми, имеет равное право на имущество.",
        "key_tokens": ["23", "umumiy", "teng"],
        "forbidden_tokens": ["uy bekasi bo'lgani uchun ulushga haqli emas"],
    },
    {
        "code": "Oila kodeksi",
        "doc_id": "104720",
        "article": "30",
        "status": "in_force",
        "summary_uz": "Oila kodeksi 30-modda: nikoh shartnomasi yozma shaklda tuziladi va notarial tartibda tasdiqlanishi shart.",
        "summary_ru": "Ст. 30 Семейного кодекса РУз: брачный договор заключается в письменной форме и подлежит обязательному нотариальному удостоверению.",
        "key_tokens": ["30", "notarial"],
        "forbidden_tokens": ["notarial tasdiqlash shart emas"],
    },
    {
        "code": "Oila kodeksi",
        "doc_id": "104720",
        "article": "39",
        "status": "in_force",
        "summary_uz": "Oila kodeksi 39-modda: xotinining homiladorlik vaqtida va bola tug'ilgandan keyin bir yil mobaynida er xotinining roziligisiz nikohdan ajratish to'g'risida ish qo'zg'atishga haqli emas.",
        "summary_ru": "Ст. 39 Семейного кодекса РУз: муж не имеет права без согласия жены возбуждать дело о расторжении брака во время беременности жены и в течение года после рождения ребенка.",
        "key_tokens": ["39", "homilador", "roziligisiz", "bir yil"],
        "forbidden_tokens": ["er homilador xotinining roziligisiz ajrashishi mumkin"],
    },
    {
        "code": "Fuqarolik kodeksi",
        "doc_id": "111189",
        "article": "150",
        "status": "in_force",
        "summary_uz": "Fuqarolik kodeksi 150-modda: umumiy da'vo muddati uch yil (3 yil) qilib belgilanadi.",
        "summary_ru": "Ст. 150 Гражданского кодекса РУз: общий срок исковой давности устанавливается в три года (3 года).",
        "key_tokens": ["150", "3 yil", "три года"],
        "forbidden_tokens": ["umumiy da'vo muddati 5 yil"],
    },
    {
        "code": "Fuqarolik kodeksi",
        "doc_id": "111189",
        "article": "293",
        "status": "in_force",
        "summary_uz": "Fuqarolik kodeksi 293 va 295-moddalar: qarzdor kafil bilan ta'minlangan majburiyatni bajarmagan taqdirda kafil va qarzdor kreditor oldida solidar (birgalikda) javobgar bo'ladilar; qarzni to'lagan kafilga kreditor huquqlari o'tadi.",
        "summary_ru": "Ст. 293 и 295 Гражданского кодекса РУз: поручитель и должник отвечают перед кредитором солидарно; к поручителю, исполнившему обязательство, переходят права кредитора.",
        "key_tokens": ["293", "solidar", "kafil"],
        "forbidden_tokens": [],
    },
    {
        "code": "Fuqarolik kodeksi",
        "doc_id": "180552",
        "article": "1021",
        "status": "in_force",
        "summary_uz": "Fuqarolik kodeksi 1021 va 1022-moddalar: ma'naviy zarar pul bilan qoplanadi; ma'naviy zararni qoplash miqdori jabrlanuvchiga yetkazilgan jismoniy va ma'naviy azoblar xususiyatiga qarab sud tomonidan belgilanadi.",
        "summary_ru": "Ст. 1021 и 1022 Гражданского кодекса РУз: моральный вред компенсируется в денежной форме, размер компенсации определяется судом.",
        "key_tokens": ["1021", "1022", "ma'naviy zarar", "sud"],
        "forbidden_tokens": [],
    },
    {
        "code": "Fuqarolik kodeksi",
        "doc_id": "180552",
        "article": "1135",
        "status": "in_force",
        "summary_uz": "Fuqarolik kodeksi 1135 va 1146-moddalar: qonun bo'yicha birinchi navbatdagi merosxo'rlar — meros qoldiruvchining bolalari, eri (xotini) va ota-onasi teng ulushlarda; meros ochilgan kundan e'tiboran 6 oy ichida qabul qilinadi.",
        "summary_ru": "Ст. 1135 и 1146 Гражданского кодекса РУз: наследники первой очереди — дети, супруг и родители в равных долях; срок принятия наследства — 6 месяцев со дня открытия наследства.",
        "key_tokens": ["1135", "1146", "6 oy", "6 месяцев"],
        "forbidden_tokens": ["meros qabul qilish muddati 1 yil"],
    },
    {
        "code": "Soliq kodeksi",
        "doc_id": "4674902",
        "article": "467",
        "status": "in_force",
        "summary_uz": "Soliq kodeksi 461 va 467-moddalar: soliq davrida jami daromadi 1 milliard so'mdan oshmagan yuridik shaxslar aylanmadan olinadigan soliq to'lovchisi bo'lishga haqli bo'lib, yagona bazaviy stavka 4 foizni tashkil etadi.",
        "summary_ru": "Ст. 461 и 467 Налогового кодекса РУз: налог с оборота применяется при совокупном доходе до 1 млрд сумов по единой базовой ставке 4%.",
        "key_tokens": ["461", "467", "1 milliard", "4"],
        "forbidden_tokens": ["aylanmadan soliq 12 foiz"],
    },
    {
        "code": "Soliq kodeksi",
        "doc_id": "4674902",
        "article": "405",
        "status": "in_force",
        "summary_uz": "Soliq kodeksi 405-modda: ijtimoiy soliq stavkasi xususiy yuridik shaxslar uchun 12 foiz, byudjet tashkilotlari va davlat ulushi 50% dan yuqori bo'lgan ayrim korxonalar uchun 25 foiz etib belgilangan.",
        "summary_ru": "Ст. 405 Налогового кодекса РУз: ставка социального налога составляет 12% для частных юридических лиц (25% для бюджетных организаций).",
        "key_tokens": ["405", "12", "ijtimoiy soliq"],
        "forbidden_tokens": [],
    },
    {
        "code": "Jinoyat kodeksi",
        "doc_id": "111453",
        "article": "17",
        "status": "in_force",
        "summary_uz": "Jinoyat kodeksi 17-modda: jinoiy javobgarlikka tortishning umumiy yoshi 16 yosh; javobgarlikni og'irlashtiruvchi holatlarda qasddan odam o'ldirish (JK 97-modda 2-qism) uchun 14 yoshdan boshlanadi.",
        "summary_ru": "Ст. 17 Уголовного кодекса РУз: общий возраст уголовной ответственности — 16 лет; за умышленное убийство при отягчающих обстоятельствах (ч. 2 ст. 97) — с 14 лет.",
        "key_tokens": ["17", "16", "14"],
        "forbidden_tokens": [],
    },
    {
        "code": "Jinoyat kodeksi",
        "doc_id": "111453",
        "article": "37",
        "status": "in_force",
        "summary_uz": "Jinoyat kodeksi 37-modda: zaruriy mudofaa holatida — ya'ni shaxsni yoki uning huquqlarini g'ayriqonuniy tajovuzdan himoya qilishda tajovuz qiluvchiga zarar yetkazish jinoyat hisoblanmaydi (zaruriy mudofaa chegarasidan chetga chiqilmagan bo'lsa).",
        "summary_ru": "Ст. 37 Уголовного кодекса РУз: не является преступлением деяние, совершенное в состоянии необходимой обороны без превышения ее пределов.",
        "key_tokens": ["37", "zaruriy mudofaa"],
        "forbidden_tokens": [],
    },
    {
        "code": "Jinoyat kodeksi",
        "doc_id": "111453",
        "article": "66-1",
        "status": "in_force",
        "summary_uz": "Jinoyat kodeksi 66-1-modda: yarashuv munosabati bilan jinoiy javobgarlikdan ozod qilish — aybiga iqror bo'lgan, jabrlanuvchi bilan yarashgan va yetkazilgan zararni bartaraf etgan shaxs ro'yxatdagi jinoyatlar bo'yicha javobgarlikdan ozod qilinishi mumkin.",
        "summary_ru": "Ст. 66-1 Уголовного кодекса РУз: освобождение от уголовной ответственности в связи с примирением при признании вины, примирении с потерпевшим и заглаживании вреда.",
        "key_tokens": ["66-1", "yarashuv"],
        "forbidden_tokens": [],
    },
    {
        "code": "Jinoyat kodeksi",
        "doc_id": "111453",
        "article": "211",
        "status": "in_force",
        "summary_uz": "Jinoyat kodeksi 211-modda 4-qism: pora bergan shaxsga nisbatan pora so'rab tovlamachilik qilingan bo'lsa yoki u 30 sutka mobaynida o'z ixtiyori bilan arz qilib, jinoyatni ochishda faol yordam bersa, jinoiy javobgarlikdan ozod etiladi.",
        "summary_ru": "Ч. 4 ст. 211 Уголовного кодекса РУз: лицо, давшее взятку, освобождается от ответственности при вымогательстве взятки либо добровольном заявлении в течение 30 суток и активном содействии раскрытию.",
        "key_tokens": ["211", "30 sutka", "ozod"],
        "forbidden_tokens": [],
    },
    {
        "code": "MJtK",
        "doc_id": "97664",
        "article": "47-4",
        "status": "in_force",
        "summary_uz": "MJtK 47-4-modda: voyaga yetmagan yoki mehnatga layoqatsiz shaxslarni moddiy ta'minlashdan (aliment to'lashdan) jami 2 oydan ortiq muddat mobaynida bo'yin tovlash 15 sutkagacha ma'muriy qamoqqa olishga sabab bo'ladi.",
        "summary_ru": "Ст. 47-4 КоАО РУз: уклонение от уплаты алиментов свыше 2 месяцев влечет административный арест до 15 суток (или штраф).",
        "key_tokens": ["47-4", "2 oy", "15 sutka"],
        "forbidden_tokens": [],
    },
    {
        "code": "MJtK",
        "doc_id": "97664",
        "article": "59-2",
        "status": "in_force",
        "summary_uz": "MJtK 59-2-modda: oilaviy (maishiy) zo'ravonlik — xotiniga (eriga) nisbatan jismoniy yoki ruhiy zo'ravonlik, haqorat yoki yengil tan jarohati yetkazish ma'muriy jarima yoki 15 sutkagacha ma'muriy qamoqqa sabab bo'ladi.",
        "summary_ru": "Ст. 59-2 КоАО РУз: семейное (бытовое) насилие влечет административный штраф либо административный арест до 15 суток.",
        "key_tokens": ["59-2", "oilaviy", "15 sutka"],
        "forbidden_tokens": [],
    },
    {
        "code": "MJtK",
        "doc_id": "97664",
        "article": "46-2",
        "status": "in_force",
        "summary_uz": "MJtK 46-2-modda: shaxsga doir ma'lumotlar to'g'risidagi qonunchilikni buzish (ruxsatsiz yig'ish, tarqatish, uzatish) fuqarolarga va mansabdor shaxslarga ma'muriy jarima solishga sabab bo'ladi.",
        "summary_ru": "Ст. 46-2 КоАО РУз: нарушение законодательства о персональных данных влечет наложение административного штрафа.",
        "key_tokens": ["46-2", "shaxsga doir"],
        "forbidden_tokens": [],
    },
    {
        "code": "Jismoniy va yuridik shaxslarning murojaatlari to'g'risida",
        "doc_id": "3336169",
        "article": "28",
        "status": "in_force",
        "summary_uz": "O'RQ-445-son Qonun 28-modda: ariza yoki shikoyat masalani mazmunan hal etishi shart bo'lgan davlat organiga kelib tushgan kundan e'tiboran 15 kun ichida, qo'shimcha o'rganish va tekshirish talab etilganda esa 1 oygacha bo'lgan muddatda ko'rib chiqiladi.",
        "summary_ru": "Ст. 28 Закона ЗРУ-445 «Об обращениях физических и юридических лиц»: заявление или жалоба рассматривается в течение 15 дней, а при необходимости дополнительного изучения — до 1 месяца.",
        "key_tokens": ["28", "15 kun", "1 oy", "O'RQ-445"],
        "forbidden_tokens": ["umumiy muddat 30 kun"],
    },
    {
        "code": "Fuqarolik protsessual kodeksi",
        "doc_id": "3517337",
        "article": "385-1",
        "status": "in_force",
        "summary_uz": "Fuqarolik protsessual kodeksi 385-1-modda: birinchi instansiya sudining hal qiluv qarori ustidan apellyatsiya shikoyati qaror qabul qilingan kundan e'tiboran 1 oy ichida berilishi mumkin.",
        "summary_ru": "Ст. 385-1 ГПК РУз: апелляционная жалоба на решение суда первой инстанции подается в течение 1 месяца со дня принятия решения.",
        "key_tokens": ["385-1", "1 oy", "apellyatsiya"],
        "forbidden_tokens": ["apellyatsiya muddati 10 kun"],
    },
    {
        "code": "Iste'molchilarning huquqlarini himoya qilish to'g'risida",
        "doc_id": "4704",
        "article": "14",
        "status": "in_force",
        "summary_uz": "Iste'molchilarning huquqlarini himoya qilish to'g'risidagi Qonun 14–18-moddalari: nuqsonli tovarni almashtirish 7 kun (qo'shimcha tekshiruvda 20 kun) ichida, bepul ta'mirlash esa 20 kun ichida amalga oshirilishi shart.",
        "summary_ru": "Ст. 14–18 Закона «О защите прав потребителей»: замена некачественного товара — в течение 7 дней (при проверке — 20 дней), бесплатный ремонт — в течение 20 дней.",
        "key_tokens": ["14", "7 kun", "20 kun"],
        "forbidden_tokens": ["sotuvchi 2 oy ichida ta'mirlashga haqli"],
    },
]


class AuditorKnowledgeStore:
    """Trainable SQLite + FTS5 knowledge base inside `agent_couinter` for zero-trust statutory verification."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        self._seed_builtin_knowledge()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS knowledge_articles (
                    id TEXT PRIMARY KEY,
                    code_name TEXT NOT NULL,
                    doc_id TEXT NOT NULL,
                    doc_number TEXT,
                    article TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'in_force',
                    branch TEXT NOT NULL DEFAULT 'general',
                    summary_uz TEXT NOT NULL,
                    summary_ru TEXT NOT NULL DEFAULT '',
                    url TEXT NOT NULL,
                    source TEXT NOT NULL DEFAULT 'builtin_golden',
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_ka_doc_art ON knowledge_articles(doc_id, article)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_ka_code_art ON knowledge_articles(code_name, article)")

    def _seed_builtin_knowledge(self) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            for item in AUTHORITATIVE_ARTICLES:
                code = item["code"]
                doc_id = item["doc_id"]
                art = item["article"]
                reg = UZBEKISTAN_STATUTE_REGISTRY.get(code, {})
                rec_id = f"{doc_id}:art:{art}"
                conn.execute(
                    """
                    INSERT OR REPLACE INTO knowledge_articles (
                        id, code_name, doc_id, doc_number, article, status, branch,
                        summary_uz, summary_ru, url, source, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        rec_id,
                        code,
                        doc_id,
                        reg.get("doc_number", ""),
                        art,
                        item.get("status", "in_force"),
                        reg.get("branch", "general"),
                        item["summary_uz"],
                        item.get("summary_ru", ""),
                        f"https://lex.uz/uz/docs/{doc_id}",
                        "builtin_golden",
                        now,
                    ),
                )

    def sync_from_local_bm25_corpus(self, bm25_db_path: Path, limit: int = 20000) -> int:
        """Auto-train Counter Agent on all 15,000+ articles, parts & clauses from sibling `bm25_index.sqlite3`."""
        if not bm25_db_path.exists():
            return 0
        now = datetime.now(timezone.utc).isoformat()
        try:
            src_conn = sqlite3.connect(f"file:{bm25_db_path.as_posix()}?mode=ro", uri=True)
            src_conn.row_factory = sqlite3.Row
            rows = src_conn.execute(
                "SELECT chunk_json FROM chunks WHERE article IS NOT NULL AND article != '' LIMIT ?",
                (limit,),
            ).fetchall()
            src_conn.close()
        except Exception:
            return 0

        doc_id_to_reg_name = {str(v["doc_id"]): k for k, v in UZBEKISTAN_STATUTE_REGISTRY.items() if v.get("doc_id")}
        batch_params: list[tuple[Any, ...]] = []
        with self._connect() as conn:
            golden_ids = {
                r[0]
                for r in conn.execute(
                    "SELECT id FROM knowledge_articles WHERE source = 'builtin_golden'"
                ).fetchall()
            }
            # Remove old un-normalized `-modda` rows so canonical IDs stay clean
            conn.execute("DELETE FROM knowledge_articles WHERE source = 'corpus_auto_synced' AND article LIKE '%modda%'")

            for r in rows:
                try:
                    data = json.loads(r["chunk_json"])
                    doc_id = str(data.get("doc_id") or data.get("canonical_id") or "").strip()
                    raw_art = str(data.get("article") or "").strip()
                    art = _clean_article_id(raw_art)
                    text = str(data.get("text") or "").strip()
                    lang = str(data.get("language") or "uz_latn")
                    if not doc_id or not art or len(text) < 25:
                        continue
                    rec_id = f"{doc_id}:art:{art}"
                    if rec_id in golden_ids:
                        continue
                    code_title = doc_id_to_reg_name.get(doc_id) or str(data.get("doc_title") or "Qonunchilik hujjati").strip()[:140]
                    branches = data.get("branches") or []
                    branch_str = str(branches[0]) if branches else "general"
                    batch_params.append(
                        (
                            rec_id,
                            code_title,
                            doc_id,
                            str(data.get("doc_number") or ""),
                            art,
                            str(data.get("status") or "in_force"),
                            branch_str,
                            text[:1800] if lang != "ru" else "",
                            text[:1800] if lang == "ru" else "",
                            str(data.get("url") or f"https://lex.uz/uz/docs/{doc_id}"),
                            "corpus_auto_synced",
                            now,
                        )
                    )
                except Exception:
                    continue

            if batch_params:
                conn.executemany(
                    """
                    INSERT OR REPLACE INTO knowledge_articles (
                        id, code_name, doc_id, doc_number, article, status, branch,
                        summary_uz, summary_ru, url, source, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    batch_params,
                )

            # Also ingest curated_facts.json (official BHM, MHTEKM, pension rates, open data indicators) if available
            curated_path = bm25_db_path.parent.parent / "corpus" / "curated_facts.json"
            if curated_path.exists():
                try:
                    c_data = json.loads(curated_path.read_text(encoding="utf-8"))
                    for fact in c_data.get("facts", []):
                        f_id = str(fact.get("doc_id") or fact.get("id") or "macro")
                        f_art = _clean_article_id(str(fact.get("article") or fact.get("id") or "1"))
                        f_text = str(fact.get("text") or "").strip()
                        if not f_text:
                            continue
                        conn.execute(
                            """
                            INSERT OR REPLACE INTO knowledge_articles (
                                id, code_name, doc_id, doc_number, article, status, branch,
                                summary_uz, summary_ru, url, source, updated_at
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                f"egov:{f_id}:{f_art}:{fact.get('lang','uz')}",
                                str(fact.get("short_title") or fact.get("title") or "data.egov.uz / Rasmiy ko'rsatkich"),
                                f_id,
                                str(fact.get("doc_number") or "PF/PQ"),
                                f_art,
                                "in_force",
                                "general",
                                f_text if fact.get("lang") != "ru" else "",
                                f_text if fact.get("lang") == "ru" else "",
                                str(fact.get("url") or "https://data.egov.uz/eng"),
                                "data_egov_curated",
                                now,
                            ),
                        )
                except Exception:
                    pass
        return len(batch_params)

    def lookup_article(
        self,
        *,
        doc_id: str | None = None,
        code_name: str | None = None,
        doc_number: str | None = None,
        article: str | None = None,
    ) -> dict[str, Any] | None:
        clean_art = _clean_article_id(article) if article else None
        raw_variants = [clean_art, f"{clean_art}-modda", f"Статья {clean_art}"] if clean_art else []
        with self._connect() as conn:
            row = None
            if doc_id and clean_art:
                row = conn.execute(
                    "SELECT * FROM knowledge_articles WHERE doc_id = ? AND (article = ? OR article = ? OR article = ?) LIMIT 1",
                    (doc_id, raw_variants[0], raw_variants[1], raw_variants[2]),
                ).fetchone()
            if not row and code_name and clean_art:
                row = conn.execute(
                    "SELECT * FROM knowledge_articles WHERE LOWER(code_name) LIKE ? AND (article = ? OR article = ? OR article = ?) LIMIT 1",
                    (f"%{code_name.lower()}%", raw_variants[0], raw_variants[1], raw_variants[2]),
                ).fetchone()
            if not row and doc_number and clean_art:
                row = conn.execute(
                    "SELECT * FROM knowledge_articles WHERE UPPER(doc_number) = UPPER(?) AND (article = ? OR article = ?) LIMIT 1",
                    (doc_number, raw_variants[0], raw_variants[1]),
                ).fetchone()
            if not row and clean_art:
                row = conn.execute(
                    "SELECT * FROM knowledge_articles WHERE article = ? LIMIT 1",
                    (clean_art,),
                ).fetchone()
            if not row and doc_id and not clean_art:
                row = conn.execute(
                    "SELECT * FROM knowledge_articles WHERE doc_id = ? LIMIT 1",
                    (doc_id,),
                ).fetchone()
            if not row and doc_number and not clean_art:
                row = conn.execute(
                    "SELECT * FROM knowledge_articles WHERE UPPER(doc_number) = UPPER(?) LIMIT 1",
                    (doc_number,),
                ).fetchone()
            return dict(row) if row else None

    def train_article(
        self,
        *,
        code_name: str,
        doc_id: str,
        article: str,
        summary_uz: str,
        summary_ru: str = "",
        doc_number: str = "",
        status: str = "in_force",
        branch: str = "general",
        url: str | None = None,
        source: str = "user_trained",
    ) -> dict[str, Any]:
        """Train/teach the Counter Agent a new or updated Uzbekistan statutory article."""
        now = datetime.now(timezone.utc).isoformat()
        clean_id = re.sub(r"[^0-9A-Za-z_-]", "", doc_id) or "custom"
        clean_art = article.strip() or "general"
        rec_id = f"{clean_id}:art:{clean_art}"
        final_url = url or f"https://lex.uz/uz/docs/{clean_id}"
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO knowledge_articles (
                    id, code_name, doc_id, doc_number, article, status, branch,
                    summary_uz, summary_ru, url, source, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    rec_id,
                    code_name.strip(),
                    clean_id,
                    doc_number.strip(),
                    clean_art,
                    status,
                    branch,
                    summary_uz.strip(),
                    summary_ru.strip(),
                    final_url,
                    source,
                    now,
                ),
            )
        return self.lookup_article(doc_id=clean_id, article=clean_art) or {}

    def train_bulk_document_text(
        self,
        *,
        code_name: str,
        doc_id: str,
        raw_text: str,
        doc_number: str = "",
        status: str = "in_force",
        branch: str = "general",
        url: str | None = None,
        source: str = "user_trained_bulk",
    ) -> int:
        """Split a full legal document or code chapter by `N-modda` / `Статья N` and train all articles."""
        pattern = re.compile(
            r"(?m)(?:^|\n)\s*(?:(\d+(?:[-.]\d+)?)\s*-\s*(?:modda|модда)|(?:Статья|ст\.)\s*(\d+(?:[-.]\d+)?))[.\s:]+",
            re.IGNORECASE,
        )
        matches = list(pattern.finditer(raw_text))
        if not matches:
            self.train_article(
                code_name=code_name,
                doc_id=doc_id,
                article="1",
                summary_uz=raw_text[:2500],
                doc_number=doc_number,
                status=status,
                branch=branch,
                url=url,
                source=source,
            )
            return 1

        trained = 0
        for idx, m in enumerate(matches):
            art_num = (m.group(1) or m.group(2) or "1").strip()
            start = m.start()
            end = matches[idx + 1].start() if idx + 1 < len(matches) else min(len(raw_text), start + 3000)
            excerpt = re.sub(r"\s+", " ", raw_text[start:end]).strip()[:2200]
            if len(excerpt) >= 20:
                self.train_article(
                    code_name=code_name,
                    doc_id=doc_id,
                    article=art_num,
                    summary_uz=excerpt,
                    doc_number=doc_number,
                    status=status,
                    branch=branch,
                    url=url,
                    source=source,
                )
                trained += 1
        return trained

    def search_knowledge(self, query: str = "", branch: str = "", limit: int = 100) -> list[dict[str, Any]]:
        with self._connect() as conn:
            q = (query or "").strip().lower()
            br = (branch or "").strip().lower()
            rows = conn.execute("SELECT * FROM knowledge_articles ORDER BY code_name, CAST(article AS INTEGER)").fetchall()
            out: list[dict[str, Any]] = []
            for r in rows:
                d = dict(r)
                if br and d["branch"].lower() != br:
                    continue
                if q:
                    hay = f"{d['code_name']} {d['doc_id']} {d['doc_number']} {d['article']}-modda {d['summary_uz']} {d['summary_ru']}".lower()
                    if q not in hay:
                        continue
                out.append(d)
            return out[:limit]

    def stats(self) -> dict[str, Any]:
        with self._connect() as conn:
            total_articles = conn.execute("SELECT COUNT(*) FROM knowledge_articles").fetchone()[0]
            user_trained = conn.execute(
                "SELECT COUNT(*) FROM knowledge_articles WHERE source != 'builtin_golden'"
            ).fetchone()[0]
            by_branch = dict(
                conn.execute("SELECT branch, COUNT(*) FROM knowledge_articles GROUP BY branch").fetchall()
            )
        return {
            "registered_statutes_count": len(UZBEKISTAN_STATUTE_REGISTRY),
            "total_verified_articles": total_articles,
            "user_trained_articles": user_trained,
            "by_branch": by_branch,
            "statutes": [
                {"name": k, **v} for k, v in UZBEKISTAN_STATUTE_REGISTRY.items()
            ],
        }

    def infer_ground_truth_for_question(self, question: str) -> dict[str, Any]:
        """Automatically match any user question against the 26+ Uzbekistan Codes Registry,
        AUTHORITATIVE_ARTICLES, and `auditor_knowledge.sqlite3` so Counter Agent always has
        authoritative ground truth (`expected_articles`, `forbidden_claims`, `gold_reference_summary`).
        """
        q_low = (question or "").lower()
        explicit_arts = [
            a or b
            for a, b in re.findall(
                r"\b(\d+(?:[-.]\d+)?)\s*-?\s*(?:modda\w*|модда\w*)|\b(?:стать[еёяйюяи]\w*|ст\.|article|art\.)\s*(\d+(?:[-.]\d+)?)\b",
                question,
                re.I,
            )
            if (a or b)
        ]

        # 1. Detect if the question mentions a specific statute from UZBEKISTAN_STATUTE_REGISTRY
        detected_code: str | None = None
        for code_name, meta in UZBEKISTAN_STATUTE_REGISTRY.items():
            if code_name.lower() in q_low or meta.get("doc_number", "").lower() in q_low:
                detected_code = code_name
                break
        if not detected_code:
            alias_map = [
                ("konstitutsiya", "Konstitutsiya"),
                ("конституц", "Konstitutsiya"),
                ("mehnat", "Mehnat kodeksi"),
                ("трудов", "Mehnat kodeksi"),
                ("fuqarolik protsessual", "Fuqarolik protsessual kodeksi"),
                ("iqtisodiy protsessual", "Iqtisodiy protsessual kodeksi"),
                ("jinoyat-protsessual", "Jinoyat-protsessual kodeksi"),
                ("fuqarolik", "Fuqarolik kodeksi"),
                ("гражданск", "Fuqarolik kodeksi"),
                ("tilxat", "Fuqarolik kodeksi"),
                ("soliq", "Soliq kodeksi"),
                ("налог", "Soliq kodeksi"),
                ("ндс", "Soliq kodeksi"),
                ("qqs", "Soliq kodeksi"),
                ("oila", "Oila kodeksi"),
                ("семейн", "Oila kodeksi"),
                ("aliment", "Oila kodeksi"),
                ("алимент", "Oila kodeksi"),
                ("jinoyat", "Jinoyat kodeksi"),
                ("уголовн", "Jinoyat kodeksi"),
                ("mjtk", "MJtK"),
                ("мжтк", "MJtK"),
                ("коао", "MJtK"),
                ("ma'muriy javobgarlik", "MJtK"),
                ("yer kodeks", "Yer kodeksi"),
                ("uy-joy", "Uy-joy kodeksi"),
                ("bojxona", "Bojxona kodeksi"),
                ("manfaatlar to'qnashuvi", "Manfaatlar to'qnashuvi to'g'risida"),
                ("shaxsga doir", "Shaxsga doir ma'lumotlar to'g'risida"),
                ("персональн", "Shaxsga doir ma'lumotlar to'g'risida"),
                ("iste'molchi", "Iste'molchilarning huquqlarini himoya qilish to'g'risida"),
                ("advokat", "Advokatura to'g'risida"),
                ("sudlar to'g'risida", "Sudlar to'g'risida"),
                ("mas'uliyati cheklangan", "Mas'uliyati cheklangan jamiyatlar to'g'risida"),
                ("normativ-huquqiy", "Normativ-huquqiy hujjatlar to'g'risida"),
            ]
            for kw, c_name in alias_map:
                if kw in q_low:
                    detected_code = c_name
                    break

        # 2. Check if question is a FALSE PREMISE trap asking about an article > max_article
        if detected_code and detected_code in UZBEKISTAN_STATUTE_REGISTRY and explicit_arts:
            reg = UZBEKISTAN_STATUTE_REGISTRY[detected_code]
            max_art = int(reg.get("max_article") or 9999)
            for art_str in explicit_arts:
                m_num = re.match(r"^(\d+)", art_str)
                if m_num and int(m_num.group(1)) > max_art:
                    return {
                        "is_false_premise": True,
                        "expected_doc_ids": [str(reg["doc_id"])],
                        "expected_articles": [],
                        "expected_key_facts": ["mavjud emas"],
                        "forbidden_claims": [f"{art_str}-moddasiga muvofiq"],
                        "gold_reference_summary": (
                            f"SOXTA MODDA TUZOG'I: '{reg['title_uz']}' (Lex.uz #{reg['doc_id']}) jami {max_art} ta moddadan iborat. "
                            f"Unda {art_str}-modda mavjud emas! Agent soxta moddani rad etishi shart."
                        ),
                    }

        # 3. Score AUTHORITATIVE_ARTICLES + SQLite knowledge_articles against the question
        q_tokens = {t for t in re.findall(r"[a-zA-Z0-9\u0400-\u04ff']{3,}", q_low)}
        scored_matches: list[tuple[float, dict[str, Any]]] = []

        for item in AUTHORITATIVE_ARTICLES:
            score = 0.0
            if detected_code and item["code"].lower() == detected_code.lower():
                score += 4.0
            if item["article"] in explicit_arts:
                score += 8.0
            hay = f"{item['code']} {item['article']}-modda {item['summary_uz']} {item.get('summary_ru', '')}".lower()
            for kt in item.get("key_tokens", []):
                if kt.lower() in q_low:
                    score += 3.5
            common = sum(1 for tok in q_tokens if len(tok) >= 4 and tok in hay)
            score += common * 1.2
            if score >= 3.5:
                scored_matches.append((score, item))

        scored_matches.sort(key=lambda x: x[0], reverse=True)
        top_golden = [m[1] for m in scored_matches[:3]]

        if top_golden:
            doc_ids = list(dict.fromkeys(g["doc_id"] for g in top_golden))
            articles = list(dict.fromkeys(g["article"] for g in top_golden))
            key_facts: list[str] = []
            forbidden: list[str] = []
            summaries: list[str] = []
            for g in top_golden:
                key_facts.extend(g.get("key_tokens", [])[:3])
                forbidden.extend(g.get("forbidden_tokens", []))
                Forbidden2 = g.get("forbidden_claims", [])
                forbidden.extend(Forbidden2)
                summaries.append(f"{g['code']} {g['article']}-modda (https://lex.uz/uz/docs/{g['doc_id']}): {g['summary_uz']}")
            return {
                "is_false_premise": False,
                "expected_doc_ids": doc_ids,
                "expected_articles": articles,
                "expected_key_facts": list(dict.fromkeys(key_facts))[:6],
                "forbidden_claims": list(dict.fromkeys(forbidden)),
                "gold_reference_summary": " | ".join(summaries),
            }

        # 4. Fallback search in SQLite `knowledge_articles` (including 2,500 synced BM25 corpus articles)
        with self._connect() as conn:
            rows = []
            if detected_code and explicit_arts:
                rows = conn.execute(
                    "SELECT * FROM knowledge_articles WHERE LOWER(code_name) LIKE ? AND article = ? LIMIT 2",
                    (f"%{detected_code.lower()}%", explicit_arts[0]),
                ).fetchall()
            if not rows and explicit_arts:
                rows = conn.execute(
                    "SELECT * FROM knowledge_articles WHERE article = ? LIMIT 3",
                    (explicit_arts[0],),
                ).fetchall()
            if not rows and q_tokens:
                longest_tok = sorted(q_tokens, key=len, reverse=True)[0]
                rows = conn.execute(
                    "SELECT * FROM knowledge_articles WHERE LOWER(summary_uz) LIKE ? LIMIT 2",
                    (f"%{longest_tok}%",),
                ).fetchall()

            if rows:
                dicts = [dict(r) for r in rows]
                return {
                    "is_false_premise": False,
                    "expected_doc_ids": list(dict.fromkeys(d["doc_id"] for d in dicts)),
                    "expected_articles": list(dict.fromkeys(d["article"] for d in dicts)),
                    "expected_key_facts": list(dict.fromkeys(d["article"] for d in dicts)),
                    "forbidden_claims": [],
                    "gold_reference_summary": " | ".join(
                        f"{d['code_name']} {d['article']}-modda ({d['url']}): {d['summary_uz'][:360]}"
                        for d in dicts
                    ),
                }

        return {
            "is_false_premise": False,
            "expected_doc_ids": [],
            "expected_articles": explicit_arts,
            "expected_key_facts": explicit_arts,
            "forbidden_claims": [],
            "gold_reference_summary": "",
        }
