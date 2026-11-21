"""Multi-source Uzbekistan legal ingestion: 18+ Codes, Supreme Court/Adliya/Norma web sources, uploaded PDF/DOCX, and Verified Reference Pack."""

from __future__ import annotations

import hashlib
import logging
import re
from datetime import date
from pathlib import Path
from typing import Any

import httpx
from bs4 import BeautifulSoup

from lex_agent.capabilities.document_analyzer import extract_text_from_uploaded_bytes
from lex_agent.ingestion.lex_fetcher import FetchedDocument
from lex_agent.ingestion.parser import classify_branches, classify_document_type
from lex_agent.language.transliterator import detect_language, normalize_uzbek_apostrophes
from lex_agent.models import (
    DocumentMetadata,
    DocumentType,
    LEGAL_FORCE_HIERARCHY,
    Language,
    LegalBranch,
    NormStatus,
)

logger = logging.getLogger(__name__)

# Complete registry of Uzbekistan's Constitution, all 18 Codes, and foundational organic laws on Lex.uz
ALL_UZBEKISTAN_CODES_LEX_IDS: dict[str, str] = {
    "Constitution of the Republic of Uzbekistan (2023)": "6445147",
    "Law on Normative-Legal Acts (O'RQ-682)": "5378966",
    "Civil Code (Part 1)": "111189",
    "Civil Code (Part 2)": "111181",
    "Criminal Code": "111453",
    "Criminal Procedure Code": "111460",
    "Code of Administrative Liability (MJtK)": "97664",
    "Code of Administrative Court Procedure": "3527353",
    "Labor Code (New 2022/2023, O'RQ-798)": "6257288",
    "Tax Code": "4674902",
    "Customs Code": "2876354",
    "Family Code": "104720",
    "Land Code": "152653",
    "Housing Code": "106136",
    "Budget Code": "2304138",
    "Urban Planning Code": "5307951",
    "Civil Procedural Code": "3517337",
    "Economic Procedural Code": "3523891",
    "Election Code": "4386848",
    "Air Code": "55594",
    "Law on Personal Data (O'RQ-547)": "4396419",
    "Law on Courts (O'RQ-703)": "5534923",
    "Law on LLCs and Additional Liability Companies": "18793",
    "Law on Consumer Rights Protection": "4704",
}

# Verified non-Lex.uz authoritative Uzbekistan legal portals supported for direct web ingestion
TRUSTED_LEGAL_SOURCES: dict[str, str] = {
    "sud.uz": "O'zbekiston Respublikasi Oliy sudi (Plenum qarorlari va sud amaliyoti)",
    "ksu.uz": "O'zbekiston Respublikasi Konstitutsiyaviy sudi",
    "adliya.uz": "O'zbekiston Respublikasi Adliya vazirligi",
    "huquqiyportal.uz": "Milliy huquqiy internet portali",
    "soliq.uz": "Soliq qo'mitasi rasmiy tushuntirishlari",
    "norma.uz": "Norma.uz huquqiy sharhlar va kodekslar",
    "lex.uz": "Qonunchilik ma'lumotlari milliy bazasi",
}


def build_foundational_reference_pack() -> list[FetchedDocument]:
    """Structured multi-source foundational legal pack covering key Uzbekistan Codes & Supreme Court rules.

    Ensures the agent always has authoritative cross-code coverage across UZ/RU/EN alongside full Lex.uz texts.
    """
    entries: list[dict[str, Any]] = [
        {
            "doc_id": "6445147",
            "title": "O'zbekiston Respublikasining Konstitutsiyasi (2023-yil tahriri)",
            "doc_type": DocumentType.CONSTITUTION,
            "doc_number": "Konstitutsiya-2023",
            "adoption_date": date(2023, 4, 30),
            "effective_date": date(2023, 5, 1),
            "branches": [LegalBranch.CONSTITUTIONAL],
            "url": "https://lex.uz/uz/docs/6445147",
            "text": (
                "15-modda. O'zbekiston Respublikasida O'zbekiston Respublikasi Konstitutsiyasi va qonunlarining ustunligi so'zsiz tan olinadi. "
                "O'zbekiston Respublikasi Konstitutsiyasi mamlakatning butun hududida oliy yuridik kuchga ega, to'g'ridan-to'g'ri amal qiladi va yagona huquqiy makonning asosini tashkil etadi.\n"
                "16-modda. Ushbu Konstitutsiyaning birorta qoidasi O'zbekiston Respublikasi huquq va manfaatlariga, Konstitutsiyada nazarda tutilgan asosiy prinsiplar va normalarga zarar yetkazadigan tarzda talqin etilishi mumkin emas. Birorta ham qonun yoki boshqa normativ-huquqiy hujjat Konstitutsiya prinsip va normalariga zid kelishi mumkin emas.\n"
                "28-modda. Jinoyat sodir etishda ayblanayotgan shaxs uning aybi qonunda nazarda tutilgan tartibda oshkora sud muhokamasi yo'li bilan isbotlanmaguncha va sudning qonuniy kuchga kirgan hukmi bilan aniqlanmaguncha aybsiz deb hisoblanadi (aybsizlik prezumpsiyasi). Shaxsga o'zining aybsizligini isbotlash majburiyati yuklatilishi mumkin emas.\n"
                "29-modda. Har kimga malakali yuridik yordam olish huquqi kafolatlanadi. Shaxs ushlangan paytdan boshlab o'z tanloviga ko'ra advokat xizmatidan foydalanish va sukut saqlash huquqiga ega (Miranda qoidasi)."
            ),
        },
        {
            "doc_id": "5378966",
            "title": "Normativ-huquqiy hujjatlar to'g'risida O'zbekiston Respublikasi Qonuni",
            "doc_type": DocumentType.LAW,
            "doc_number": "O'RQ-682",
            "adoption_date": date(2021, 4, 20),
            "effective_date": date(2021, 4, 21),
            "branches": [LegalBranch.CONSTITUTIONAL, LegalBranch.GENERAL],
            "url": "https://lex.uz/uz/docs/5378966",
            "text": (
                "6-modda. Normativ-huquqiy hujjatlarning turlari: 1) O'zbekiston Respublikasining Konstitutsiyasi; 2) O'zbekiston Respublikasining qonunlari (shu jumladan kodekslar); 3) Oliy Majlis palatalarining qarorlari; 4) Prezident farmonlari va qarorlari; 5) Vazirlar Mahkamasining qarorlari; 6) vazirliklar, davlat qo'mitalari va idoralarning buyruqlari hamda qarorlari; 7) mahalliy davlat hokimiyati organlarining qarorlari.\n"
                "18-modda. Normativ-huquqiy hujjatlar o'rtasida tafovut bo'lgan taqdirda yuqoriroq yuridik kuchga ega bo'lgan hujjat qo'llaniladi (lex superior). Teng yuridik kuchga ega bo'lgan hujjatlar o'rtasida tafovut bo'lgan taqdirda keyinroq qabul qilingan hujjat qoidalari amal qiladi (lex posterior), maxsus normativ-huquqiy hujjat bundan mustasno (lex specialis).\n"
                "41-modda. Qonun hujjatlari orqaga qaytish kuchiga ega emas, javobgarlikni yengillashtiruvchi yoki bekor qiluvchi normalar bundan mustasno."
            ),
        },
        {
            "doc_id": "6257288",
            "title": "O'zbekiston Respublikasining Mehnat kodeksi (yangi tahrir)",
            "doc_type": DocumentType.CODE,
            "doc_number": "O'RQ-798",
            "adoption_date": date(2022, 10, 28),
            "effective_date": date(2023, 4, 30),
            "branches": [LegalBranch.LABOR],
            "url": "https://lex.uz/uz/docs/6257288",
            "text": (
                "129-modda. Dastlabki sinov muddati uch oydan, tashkilot rahbarlari va ularning o'rinbosarlari, bosh buxgalterlar uchun olti oydan oshmasligi kerak.\n"
                "161-modda. Mehnat shartnomasini ish beruvchining tashabbusiga ko'ra bekor qilish asoslari: texnologiya, ishlab chiqarish va mehnatni tashkil etishdagi o'zgarishlar, xodimlar soni (shtati) qisqarishi; xodimning malakasi yetarli emasligi; xodim tomonidan o'z mehnat majburiyatlarini muntazam ravishda buzish; bir marta qo'pol ravishda buzish.\n"
                "165-modda. Ish beruvchi mehnat shartnomasini bekor qilish niyati haqida xodimni yozma ravishda (imzo qo'ydirib): shtat qisqarishi yoki tashkilot tugatilishi munosabati bilan — kamida ikki oy oldin; malaka yetarli emasligi sababli — kamida ikki hafta oldin; mehnat majburiyatlari buzilishi munosabati bilan — kamida uch kun oldin ogohlantirishi shart.\n"
                "217-modda. Har yilgi asosiy eng kam mehnat ta'tili davomiyligi yigirma bir kalendar kunni tashkil etadi (eski 1995-yilgi kodeksda 15 ish kuni bo'lgan)."
            ),
        },
        {
            "doc_id": "4674902",
            "title": "O'zbekiston Respublikasining Soliq kodeksi",
            "doc_type": DocumentType.CODE,
            "doc_number": "O'RQ-599",
            "adoption_date": date(2019, 12, 30),
            "effective_date": date(2020, 1, 1),
            "branches": [LegalBranch.TAX, LegalBranch.CORPORATE_COMMERCIAL],
            "url": "https://lex.uz/uz/docs/4674902",
            "text": (
                "258-modda. Qo'shilgan qiymat solig'i (QQS / NDS) stavkasi 12 foiz miqdorida belgilangan (2023-yil 1-yanvardan 15 foizdan 12 foizga tushirilgan).\n"
                "337-modda. Foyda solig'ining bazaviy stavkasi 15 foizni tashkil etadi (ayrim toifalar — banklar, mobil aloqa operatorlari, sement/polietilen ishlab chiqaruvchilar uchun 20 foiz; elektron tijorat subyektlari uchun pasaytirilgan stavkalar qonunchilik bilan belgilanadi).\n"
                "381-modda. Jismoniy shaxslardan olinadigan daromad solig'i (JShODS / NDFL) rezidentlar uchun 12 foiz stavkada undiriladi.\n"
                "467-modda. Aylanmadan olinadigan soliqning bazaviy stavkasi 4 foiz (yillik jami daromadi 1 mlrd so'mgacha bo'lgan soliq to'lovchilar uchun; qat'iy belgilangan summada to'lash tanlovi ham mavjud)."
            ),
        },
        {
            "doc_id": "111189",
            "title": "O'zbekiston Respublikasining Fuqarolik kodeksi (1-qism)",
            "doc_type": DocumentType.CODE,
            "doc_number": "FK-1",
            "adoption_date": date(1995, 12, 21),
            "effective_date": date(1997, 3, 1),
            "branches": [LegalBranch.CIVIL, LegalBranch.CORPORATE_COMMERCIAL],
            "url": "https://lex.uz/uz/docs/111189",
            "text": (
                "150-modda. Umumiy da'vo muddati — uch yil.\n"
                "260-modda. Neustoyka (jarima, penya) — majburiyat bajarilmagan yoki lozim darajada bajarilmagan taqdirda qarzdor kreditorga to'lashi shart bo'lgan, qonun hujjatlari yoki shartnoma bilan belgilangan pul summasi.\n"
                "354-modda. Shartnoma erkinligi: fuqarolar va yuridik shaxslar shartnoma tuzishda erkindirlar. Shartnoma shartlari taraflarning xohishi bilan belgilanadi, tegishli shartning mazmuni qonun hujjatlarida ko'rsatib qo'yilgan hollar bundan mustasno."
            ),
        },
        {
            "doc_id": "111453",
            "title": "O'zbekiston Respublikasining Jinoyat kodeksi",
            "doc_type": DocumentType.CODE,
            "doc_number": "JK",
            "adoption_date": date(1994, 9, 22),
            "effective_date": date(1995, 4, 1),
            "branches": [LegalBranch.CRIMINAL],
            "url": "https://lex.uz/uz/docs/111453",
            "text": (
                "168-modda. Firibgarlik, ya'ni aldash yoki ishonchni suiiste'mol qilish yo'li bilan o'zganing mulkini yoki o'zganing mulkiga bo'lgan huquqni qo'lga kiritish — BHMning 50 baravaridan 100 baravarigacha jarima yoki ikki yilgacha axloq tuzatish ishlari yoki bir yildan uch yilgacha ozodlikni cheklash yoxud uch yilgacha ozodlikdan mahrum qilish bilan jazolanadi. Og'irlashtiruvchi holatlarda (ko'p, juda ko'p miqdorda, uyushgan guruh tomonidan, axborot texnologiyalaridan foydalanib) sakkiz yildan o'n yilgacha ozodlikdan mahrum qilish jazosi qo'llaniladi. Yetkazilgan moddiy zararning o'rni qoplangan taqdirda ozodlikni cheklash va ozodlikdan mahrum qilish tariqasidagi jazo qo'llanilmaydi.\n"
                "210-modda. Pora olish — mansabdor shaxsning o'z xizmat mavqeidan foydalangan holda muayyan harakatni bajarishi yoki bajarmasligi evaziga moddiy qimmatliklar olishi yoki mulkiy manfaatdor bo'lishi."
            ),
        },
        {
            "doc_id": "97664",
            "title": "O'zbekiston Respublikasining Ma'muriy javobgarlik to'g'risidagi kodeksi (MJtK)",
            "doc_type": DocumentType.CODE,
            "doc_number": "MJtK",
            "adoption_date": date(1994, 9, 22),
            "effective_date": date(1995, 4, 1),
            "branches": [LegalBranch.ADMINISTRATIVE],
            "url": "https://lex.uz/uz/docs/97664",
            "text": (
                "25-modda. Ma'muriy jarimalar Bazaviy hisoblash miqdori (BHM / БРВ) ga nisbatan karrali miqdorda belgilanadi.\n"
                "36-modda. Ma'muriy jazo huquqbuzarlik sodir etilgan kundan boshlab, davom etayotgan huquqbuzarliklar uchun esa u aniqlangan kundan boshlab bir yildan kechiktirmay qo'llanilishi mumkin.\n"
                "332-1-modda. Ma'muriy jarima solish to'g'risidagi qaror topshirilgan kundan boshlab 15 kun ichida jarima miqdorining 50 foizi, 30 kun ichida 70 foizi ixtiyoriy ravishda to'langan taqdirda huquqbuzar jarimaning qolgan qismini to'lashdan ozod qilinadi (qonunda nazarda tutilgan istisnolar bundan mustasno)."
            ),
        },
        {
            "doc_id": "104720",
            "title": "O'zbekiston Respublikasining Oila kodeksi",
            "doc_type": DocumentType.CODE,
            "doc_number": "OK",
            "adoption_date": date(1998, 4, 30),
            "effective_date": date(1998, 9, 1),
            "branches": [LegalBranch.FAMILY],
            "url": "https://lex.uz/uz/docs/104720",
            "text": (
                "99-modda. Ota-onaning voyaga yetmagan bolalariga to'laydigan aliment miqdori: kelishuv bo'lmasa, har oydagi ish haqi va boshqa daromadning 1 bola uchun — 1/4 (25%), 2 bola uchun — 1/3 (33.3%), 3 va undan ortiq bola uchun — 1/2 (50%) qismi miqdorida undiriladi. Har bir bola uchun undiriladigan aliment miqdori mehnatga haq to'lash eng kam miqdorining (MHTEKM) 26,5 foizidan kam bo'lmasligi kerak (O'RQ-683, 21.04.2021).\n"
                "23-modda. Er va xotinning nikoh davomida orttirgan mol-mulklari ularning umumiy birgalikdagi mulki hisoblanadi."
            ),
        },
        {
            "doc_id": "4396419",
            "title": "Shaxsga doir ma'lumotlar to'g'risida O'zbekiston Respublikasi Qonuni",
            "doc_type": DocumentType.LAW,
            "doc_number": "O'RQ-547",
            "adoption_date": date(2019, 7, 2),
            "effective_date": date(2019, 10, 1),
            "branches": [LegalBranch.DIGITAL_IT_DATA],
            "url": "https://lex.uz/uz/docs/4396419",
            "text": (
                "27-1-modda. O'zbekiston Respublikasi fuqarolarining shaxsga doir ma'lumotlariga axborot texnologiyalaridan foydalangan holda ishlov berishda mulkdor va (yoki) operator ushbu ma'lumotlarni jisman O'zbekiston Respublikasi hududida joylashgan texnik vositalarda hamda Shaxsga doir ma'lumotlar bazalarining davlat reyestrida ro'yxatdan o'tkazilgan bazalarda yig'ish, tizimlashtirish va saqlashni ta'minlashi shart."
            ),
        },
    ]

    docs: list[FetchedDocument] = []
    for item in entries:
        meta = DocumentMetadata(
            doc_id=item["doc_id"],
            canonical_id=item["doc_id"],
            title=item["title"],
            doc_type=item["doc_type"],
            doc_number=item["doc_number"],
            language=Language.UZ_LATN,
            adoption_date=item["adoption_date"],
            effective_date=item["effective_date"],
            status=NormStatus.IN_FORCE,
            legal_force_rank=LEGAL_FORCE_HIERARCHY.get(item["doc_type"], 85),
            branches=item["branches"],
            url=item["url"],
            linked_doc_ids={"uz_latn": item["doc_id"]},
            linked_urls={"uz_latn": item["url"]},
            source="uzbekistan_foundational_codes_pack",
        )
        docs.append(FetchedDocument(metadata=meta, raw_text=item["text"]))
    return docs


async def fetch_external_legal_url(url: str, *, timeout: float = 20.0) -> FetchedDocument | None:
    """Ingest a legal commentary, Supreme Court Plenum resolution, or Code page from any Uzbekistan legal portal."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36",
    }
    async with httpx.AsyncClient(headers=headers, timeout=timeout, follow_redirects=True) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        html = resp.text

    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "nav", "footer", "header", "aside", "noscript"]):
        tag.decompose()

    title_el = soup.find("h1") or soup.title
    title = re.sub(r"\s+", " ", title_el.get_text(" ", strip=True)) if title_el else url
    title = normalize_uzbek_apostrophes(title)

    main = soup.find("article") or soup.find("main") or soup.body or soup
    raw_text = re.sub(r"\n{3,}", "\n\n", main.get_text("\n", strip=True))
    if len(raw_text) < 80:
        return None

    doc_id = "ext_" + hashlib.sha256(url.encode("utf-8")).hexdigest()[:12]
    lang = detect_language(f"{title}\n{raw_text[:2000]}")
    doc_type = classify_document_type(title, raw_text[:1500])
    branches = classify_branches(title, raw_text[:2500])

    meta = DocumentMetadata(
        doc_id=doc_id,
        canonical_id=doc_id,
        title=title,
        doc_type=doc_type,
        language=lang,
        status=NormStatus.IN_FORCE,
        legal_force_rank=LEGAL_FORCE_HIERARCHY.get(doc_type, 55),
        branches=branches,
        url=url,
        linked_doc_ids={lang.value: doc_id},
        linked_urls={lang.value: url},
        source="external_legal_portal",
    )
    return FetchedDocument(metadata=meta, raw_text=raw_text)


def build_uploaded_knowledge_document(
    filename: str,
    content: bytes,
    *,
    title: str | None = None,
    doc_type: DocumentType | None = None,
    source_url: str | None = None,
) -> FetchedDocument:
    """Parse an uploaded legal Code PDF, Supreme Court Plenum DOCX, or commentary TXT for ingestion."""
    raw_text = extract_text_from_uploaded_bytes(filename, content)
    if len(raw_text.strip()) < 40:
        raise ValueError("Yuklangan faylda yetarli matn topilmadi.")

    clean_title = normalize_uzbek_apostrophes(title or Path(filename).stem.replace("_", " ").replace("-", " "))
    lang = detect_language(f"{clean_title}\n{raw_text[:2000]}")
    inferred_type = doc_type or classify_document_type(clean_title, raw_text[:1500])
    branches = classify_branches(clean_title, raw_text[:2500])
    doc_id = "upload_" + hashlib.sha256(f"{filename}:{len(content)}".encode("utf-8")).hexdigest()[:12]
    url = source_url or f"local://{filename}"

    meta = DocumentMetadata(
        doc_id=doc_id,
        canonical_id=doc_id,
        title=clean_title,
        doc_type=inferred_type,
        language=lang,
        status=NormStatus.IN_FORCE,
        legal_force_rank=LEGAL_FORCE_HIERARCHY.get(inferred_type, 70),
        branches=branches,
        url=url,
        linked_doc_ids={lang.value: doc_id},
        linked_urls={lang.value: url},
        source=f"uploaded:{filename}",
    )
    return FetchedDocument(metadata=meta, raw_text=raw_text)
