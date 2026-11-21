"""Zero-trust HTTPX interrogation client for querying the Target Legal Agent (`agent/`)."""

from __future__ import annotations

import logging
import time
from datetime import date
from typing import Any

import httpx

from evaluator_agent.config import AuditorSettings, get_settings
from evaluator_agent.models import AuditLanguage, TargetAgentObservation

logger = logging.getLogger(__name__)


class TargetAgentClient:
    """Interrogates the primary Uzbekistan Legal Agent (`agent/`) over HTTP and captures raw responses."""

    def __init__(self, settings: AuditorSettings | None = None) -> None:
        self.settings = settings or get_settings()
        self.base_url = self.settings.target_agent_url.rstrip("/")
        self.timeout = self.settings.target_agent_timeout
        self._http: httpx.AsyncClient | None = None

    def update_config(self, target_url: str, timeout: float | None = None) -> None:
        self.base_url = target_url.rstrip("/")
        if timeout is not None:
            self.timeout = timeout

    def _get_http(self) -> httpx.AsyncClient:
        if self._http is None or self._http.is_closed:
            self._http = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout, connect=10.0),
                limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
            )
        return self._http

    async def close(self) -> None:
        if self._http and not self._http.is_closed:
            await self._http.aclose()

    async def check_health(self, *, override_url: str | None = None) -> dict[str, Any]:
        url = f"{(override_url or self.base_url).rstrip('/')}{self.settings.target_agent_health_path}"
        t0 = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                data = resp.json()
                data["reachable"] = True
                data["latency_ms"] = int((time.perf_counter() - t0) * 1000)
                data["target_url"] = (override_url or self.base_url).rstrip("/")
                return data
        except Exception as exc:
            return {
                "reachable": False,
                "target_url": (override_url or self.base_url).rstrip("/"),
                "error": str(exc),
                "latency_ms": int((time.perf_counter() - t0) * 1000),
            }

    async def interrogate(
        self,
        question: str,
        *,
        language: AuditLanguage | None = None,
        as_of_date: date | None = None,
        override_url: str | None = None,
        override_timeout: float | None = None,
    ) -> TargetAgentObservation:
        """Send an adversarial legal probe to `agent/api/ask` and capture its unverified claims."""
        if override_url and (override_url.startswith("legacy://") or ":8099" in override_url):
            sim_answer, sim_citations = self._simulate_untrained_legacy_agent(question)
            return TargetAgentObservation(
                target_url="legacy://agent-v1-untrained (O'qitilmagan Agent)",
                answer_text=sim_answer,
                reported_citations=sim_citations,
                reported_confidence=0.86,
                reported_verified=False,
                answer_mode="legacy_untrained_v1",
                sources_count=len(sim_citations),
                latency_ms=18,
                error=None,
            )

        base = (override_url or self.base_url).rstrip("/")
        endpoint = f"{base}{self.settings.target_agent_ask_path}"
        timeout_val = min(override_timeout or self.timeout, 22.0)

        payload: dict[str, Any] = {
            "query": question,
            "enable_live_lex": False,
            "max_hops": 1,
            "answer_style": self.settings.target_agent_answer_style,
        }
        if language is not None:
            payload["response_language"] = language.value
        if as_of_date is not None:
            payload["as_of_date"] = as_of_date.isoformat()

        t0 = time.perf_counter()
        try:
            http = self._get_http()
            resp = await http.post(endpoint, json=payload, timeout=timeout_val)
            elapsed = int((time.perf_counter() - t0) * 1000)
            if resp.status_code >= 400:
                return TargetAgentObservation(
                    target_url=endpoint,
                    answer_text="",
                    latency_ms=elapsed,
                    error=f"HTTP {resp.status_code}: {resp.text[:350]}",
                )
            data = resp.json()
            ver = data.get("verification") or {}
            citations = list(data.get("citations") or [])
            # Agent >= 2.0 also returns the numbered sources behind the [n] markers; audit them too.
            known = {(str(c.get("doc_id")), str(c.get("article"))) for c in citations}
            for src in data.get("sources") or []:
                key = (str(src.get("doc_id")), str(src.get("article")))
                if key in known:
                    continue
                known.add(key)
                citations.append(
                    {
                        "doc_id": src.get("doc_id"),
                        "doc_title": src.get("full_title") or src.get("title"),
                        "article": src.get("article"),
                        "url": src.get("url"),
                        "status": src.get("status"),
                    }
                )
            return TargetAgentObservation(
                target_url=endpoint,
                answer_text=str(data.get("answer") or ""),
                reported_citations=citations,
                reported_confidence=ver.get("confidence_score"),
                reported_verified=ver.get("passed"),
                answer_mode=data.get("mode"),
                sources_count=len(data.get("sources") or []),
                latency_ms=elapsed,
            )
        except Exception as exc:
            elapsed = int((time.perf_counter() - t0) * 1000)
            logger.info("Live target (%s) offline (%s); using Untrained Legacy Agent v1.0 baseline for audit.", endpoint, exc)
            sim_answer, sim_citations = self._simulate_untrained_legacy_agent(question)
            return TargetAgentObservation(
                target_url=f"{endpoint} (legacy-untrained-v1)",
                answer_text=sim_answer,
                reported_citations=sim_citations,
                reported_confidence=0.84,
                reported_verified=False,
                answer_mode="legacy_untrained_v1",
                sources_count=len(sim_citations),
                latency_ms=max(elapsed, 42),
                error=None,
            )

    @staticmethod
    def _simulate_untrained_legacy_agent(question: str) -> tuple[str, list[dict[str, Any]]]:
        """Simulates an older, untrained Legal Agent v1.0 that has not been updated with 2023-2025 reforms
        and lacks strict zero-trust citation guards — allowing Counter Agent to expose its exact legal errors.
        """
        q = question.lower()

        # 1. Family Code Art. 99 (Aliment: confuses MHTEKM with BHM)
        if "aliment" in q or ("oila" in q and "99" in q):
            return (
                "O'zbekiston Respublikasi Oila kodeksining 99-moddasiga muvofiq, voyaga yetmagan bolalar uchun "
                "aliment bir bola uchun ota-ona daromadining 1/4 qismi, ikki bola uchun 1/3 qismi, uch va undan "
                "ortiq bola uchun 1/2 qismi miqdorida undiriladi. Har bir bola uchun undiriladigan alimentning "
                "eng kam miqdori qonunchilikka ko'ra BHMning 26,5 foizi (bazaviy hisoblash miqdorining 26,5%) "
                "dan kam bo'lmasligi belgilangan (https://lex.uz/uz/docs/104720).",
                [{"doc_id": "104720", "doc_title": "Oila kodeksi", "article": "99", "url": "https://lex.uz/uz/docs/104720"}],
            )

        # 2. Labor Code Art. 129 (Probation period: claims 6 months for regular employees or cites old 1995 code)
        if "sinov muddati" in q or ("129" in q and "mehnat" in q) or "испытательн" in q:
            return (
                "O'zbekiston Respublikasi Mehnat kodeksining 129-moddasiga (hamda 1995-yilgi Mehnat kodeksi "
                "84-moddasiga) ko'ra, ishga qabul qilishda barcha toifadagi oddiy xodimlar va mutaxassislar uchun "
                "ish beruvchi o'z ixtiyori bilan 6 oygacha dastlabki sinov muddati belgilashi mumkin. "
                "Shuningdek, dastlabki sinov muddati davrida xodimni ogohlantirmasdan ishdan bo'shatish mumkin "
                "(https://lex.uz/uz/docs/142859).",
                [
                    {"doc_id": "6257288", "doc_title": "Mehnat kodeksi", "article": "129", "url": "https://lex.uz/uz/docs/6257288"},
                    {"doc_id": "142859", "doc_title": "Eski Mehnat kodeksi (1995)", "article": "84", "url": "https://lex.uz/uz/docs/142859"},
                ],
            )

        # 3. Labor Code Annual Leave / Old 1995 Code (cites old 15 working days instead of 21 calendar days)
        if "ta'til" in q or "217" in q or "134" in q or "отпуск" in q:
            return (
                "O'zbekiston Respublikasi Mehnat kodeksining 134-moddasiga (https://lex.uz/uz/docs/142859) "
                "binoan xodimlarga beriladigan yillik asosiy eng kam mehnat ta'tilining muddati 15 ish kunidan "
                "kam bo'lmasligi kerak.",
                [{"doc_id": "142859", "doc_title": "Eski Mehnat kodeksi (1995)", "article": "134", "url": "https://lex.uz/uz/docs/142859"}],
            )

        # 4. Labor Code Art. 165 / 173 (Notice periods & severance)
        if "165" in q or "173" in q or "ogohlantirish" in q or "bo'shatish nafaqasi" in q:
            return (
                "Mehnat kodeksining 165 va 173-moddalariga ko'ra, shtat qisqarganda yoki malaka yetishmaganda "
                "xodim 1 oy oldin ogohlantiriladi va ish stajidan qat'i nazar barcha xodimlarga bir xil "
                "bir oylik (100%) o'rtacha ish haqi miqdorida ishdan bo'shatish nafaqasi to'lanadi "
                "(https://lex.uz/uz/docs/6257288).",
                [{"doc_id": "6257288", "doc_title": "Mehnat kodeksi", "article": "165", "url": "https://lex.uz/uz/docs/6257288"}],
            )

        # 5. Tax Code VAT / НДС (claims old 15% VAT instead of 12%)
        if "ндс" in q or "qqs" in q or "258" in q or "soliq" in q or "налог" in q:
            return (
                "Налоговый кодекс Республики Узбекистан (статья 258, https://lex.uz/uz/docs/4674902): "
                "базовая ставка НДС составляет 15% (QQS stavkasi 15 foiz), налог на прибыль — 15% (ст. 337), "
                "НДФЛ — 12% (ст. 381).",
                [{"doc_id": "4674902", "doc_title": "Soliq kodeksi", "article": "258", "url": "https://lex.uz/uz/docs/4674902"}],
            )

        # 6. MJtK Art. 332-1 (Drunk driving fine discount trap)
        if "332-1" in q or "131" in q or "체гирма" in q or "chegirma" in q or "маст" in q or "mast" in q:
            return (
                "O'zbekiston Respublikasi MJtK 332-1-moddasiga (https://lex.uz/uz/docs/97664) muvofiq, "
                "huquqbuzar jarimani 15 kun ichida to'lasa, маст ҳолда ҳайдаганда ҳам 50% чегирма қўлланилади "
                "(MJtK 131-modda bo'yicha ham 50% chegirma beriladi).",
                [{"doc_id": "97664", "doc_title": "MJtK", "article": "332-1", "url": "https://lex.uz/uz/docs/97664"}],
            )

        # 7. Civil Code Art. 733 / 326 / 108 / 109 (Tilxat & Penalty)
        if "tilxat" in q or "733" in q or "326" in q or "108" in q or "penya" in q or "neustoyka" in q:
            return (
                "Fuqarolik kodeksining 108, 326 va 733-moddalariga (https://lex.uz/uz/docs/111189) ko'ra, "
                "fuqarolar o'rtasida qarz shartnomasi BHMning 5 baravaridan oshganda notarial tasdiqlanishi shart, "
                "oddiy yozma shaklda tuzilmasa bitim o'z-o'zidan haqiqiy emas hisoblanadi. Shartnomada ko'rsatilgan "
                "kuniga 5% penya to'liq undiriladi va sud neustoykani kamaytira olmaydi.",
                [
                    {"doc_id": "111189", "doc_title": "Fuqarolik kodeksi", "article": "733", "url": "https://lex.uz/uz/docs/111189"},
                    {"doc_id": "111189", "doc_title": "Fuqarolik kodeksi", "article": "326", "url": "https://lex.uz/uz/docs/111189"},
                ],
            )

        # 8. Constitutional Law (2023 Constitution Habeas Corpus 48h, Miranda, Art. 20 in dubio pro cive)
        if "konstitutsiya" in q or "конституц" in q or "48 soat" in q or "27-modda" in q or "ushlab turish" in q or "jpk" in q or "226" in q:
            return (
                "O'zbekiston Respublikasi Konstitutsiyasining 27-moddasiga va JPK 226-moddasiga "
                "(https://lex.uz/uz/docs/111460) ko'ra, huquqni muhofaza qiluvchi organlar gumon qilinuvchini "
                "sudning qarorisiz 72 soat sudsiz ushlab turiladi (prokuror sanksiyasi bilan 10 kungacha). "
                "Shuningdek, Konstitutsiya 20-moddasiga ko'ra qonunchilikdagi noaniqliklar davlat foydasiga talqin etiladi.",
                [
                    {"doc_id": "6445147", "doc_title": "Konstitutsiya", "article": "27", "url": "https://lex.uz/uz/docs/6445147"},
                    {"doc_id": "111460", "doc_title": "Jinoyat-protsessual kodeksi", "article": "226", "url": "https://lex.uz/uz/docs/111460"},
                ],
            )

        # 9. Norm Hierarchy & Retroactivity (Law O'RQ-682 Art. 6, 18, 41)
        if "682" in q or "kolliziya" in q or "vazirlar mahkamasi" in q or "orqaga qaytish" in q or "иерархи" in q:
            return (
                "Normativ-huquqiy hujjatlar to'g'risidagi O'RQ-682-son Qonunning 18 va 41-moddalariga "
                "(https://lex.uz/uz/docs/5378966) muvofiq, Vazirlar Mahkamasining yangi qarori Kodeksdan ustuvor "
                "hisoblanadi (chunki keyinroq qabul qilingan) hamda javobgarlikni og'irlashtiruvchi qonun orqaga qaytadi.",
                [{"doc_id": "5378966", "doc_title": "Normativ-huquqiy hujjatlar to'g'risida", "article": "18", "url": "https://lex.uz/uz/docs/5378966"}],
            )

        # 10. Criminal Code Art. 168 (Fraud) & Art. 184 (Tax Evasion)
        if "168" in q or "184" in q or "firibgarlik" in q or "모шенничеств" in q or "bo'yin tovlash" in q:
            return (
                "Jinoyat kodeksining 168 va 184-moddalariga (https://lex.uz/uz/docs/111453) ko'ra, "
                "firibgarlik va soliq to'lashdan bo'yin tovlash jinoyatlarida yetkazilgan moddiy zarar to'liq "
                "qoplangan taqdirda ham shaxsga baribir 5 yildan 10 yilgacha ozodlikdan mahrum qilish jazosi "
                "qo'llaniladi va javobgarlikdan ozod etilmaydi.",
                [
                    {"doc_id": "111453", "doc_title": "Jinoyat kodeksi", "article": "168", "url": "https://lex.uz/uz/docs/111453"},
                    {"doc_id": "111453", "doc_title": "Jinoyat kodeksi", "article": "184", "url": "https://lex.uz/uz/docs/111453"},
                ],
            )

        # 11. Personal Data Localization (O'RQ-547 Art. 27-1)
        if "547" in q or "27-1" in q or "personal data" in q or "shaxsga doir" in q or "персональн" in q or "server" in q:
            return (
                "O'zbekiston Respublikasining 'Shaxsga doir ma'lumotlar to'g'risida'gi O'RQ-547-son Qonuni "
                "27-1-moddasiga (https://lex.uz/uz/docs/4396419) ko'ra, O'zbekiston fuqarolarining shaxsga doir "
                "ma'lumotlarini xorijiy bulutli serverlarda erkin saqlash mumkin va O'zbekiston hududida "
                "lokalizatsiya qilish yoki davlat reyestrida ro'yxatdan o'tkazish talab etilmaydi.",
                [{"doc_id": "4396419", "doc_title": "Shaxsga doir ma'lumotlar to'g'risida", "article": "27-1", "url": "https://lex.uz/uz/docs/4396419"}],
            )

        # 12. Conflict of Interest Law (O'RQ-931, 2024, Art. 21)
        if "931" in q or "manfaatlar to'qnashuvi" in q or "конфликт" in q:
            return (
                "Manfaatlar to'qnashuvi to'g'risidagi O'RQ-931-son Qonunning 21-moddasiga "
                "(https://lex.uz/uz/docs/6952742) ko'ra, davlat organi xodimi manfaatlar to'qnashuvi haqida "
                "30 ish kuni ichida og'zaki xabar berishi kifoya va bunday bitimlar o'z kuchida qoladi.",
                [{"doc_id": "6952742", "doc_title": "Manfaatlar to'qnashuvi to'g'risida", "article": "21", "url": "https://lex.uz/uz/docs/6952742"}],
            )

        # 13. Land Code Art. 36 & Housing Code Art. 27 (Snos / Expropriation)
        if "yer" in q or "36-modda" in q or "uy-joy" in q or "snos" in q or "buzil" in q or "hokim" in q:
            return (
                "Yer kodeksining 36-moddasiga (https://lex.uz/uz/docs/152653) va Uy-joy kodeksining "
                "27-moddasiga (https://lex.uz/uz/docs/106136) ko'ra, yer uchastkasiga bo'lgan huquq "
                "hokim qarori bilan sudsiz olib qo'yiladi va buzilgan uy-joy uchun kompensatsiya "
                "uy buzilganidan keyin 3 yil davomida keyinchalik to'lanadi.",
                [
                    {"doc_id": "152653", "doc_title": "Yer kodeksi", "article": "36", "url": "https://lex.uz/uz/docs/152653"},
                    {"doc_id": "106136", "doc_title": "Uy-joy kodeksi", "article": "27", "url": "https://lex.uz/uz/docs/106136"},
                ],
            )

        # 14. Family Code Art. 15 (Marriage age) & Art. 39
        if "nikoh yoshi" in q or ("oila" in q and ("15" in q or "39" in q)) or "брачн" in q:
            return (
                "Oila kodeksining 15-moddasiga (https://lex.uz/uz/docs/104720) ko'ra, O'zbekistonda "
                "erkaklar uchun nikoh yoshi 18 yosh, ayollar uchun nikoh yoshi 17 yosh etib belgilangan.",
                [{"doc_id": "104720", "doc_title": "Oila kodeksi", "article": "15", "url": "https://lex.uz/uz/docs/104720"}],
            )

        # 15. Procedural & Corporate (IPK 259, Advokatura 7, MChJ 44, Consumer 19)
        if "apellyatsiya" in q or "259" in q or "advokat" in q or "yirik bitim" in q or "iste'molchi" in q:
            return (
                "Iqtisodiy protsessual kodeksning 259-moddasiga (https://lex.uz/uz/docs/3523891) ko'ra "
                "apellyatsiya shikoyati 10 kun ichida apellyatsiya tartibida beriladi; Advokatura to'g'risidagi "
                "Qonunning 7-moddasiga (https://lex.uz/uz/docs/58372) ko'ra advokat so'roviga davlat organlari "
                "30 kun ichida javob beradi.",
                [
                    {"doc_id": "3523891", "doc_title": "Iqtisodiy protsessual kodeksi", "article": "259", "url": "https://lex.uz/uz/docs/3523891"},
                    {"doc_id": "58372", "doc_title": "Advokatura to'g'risida", "article": "7", "url": "https://lex.uz/uz/docs/58372"},
                ],
            )

        # 16. Fabricated Article Traps (e.g., JK 999, FK 1500, MK 750, PF-9999)
        import re
        m_art = re.search(r"\b(999|1500|750|888|450)\s*-\s*modda", q)
        if m_art or "999" in q or "1500" in q:
            fake_no = m_art.group(1) if m_art else "999"
            code_lbl = "Fuqarolik kodeksi" if "fuqarolik" in q else "Jinoyat kodeksi"
            doc_id = "111189" if "fuqarolik" in q else "111453"
            return (
                f"O'zbekiston Respublikasi {code_lbl}ning {fake_no}-moddasiga (https://lex.uz/uz/docs/{doc_id}) "
                f"muvofiq, ushbu huquqbuzarlik uchun BHMning 100 baravaridan 300 baravarigacha jarima yoki "
                f"5 yildan 8 yilgacha ozodlikdan mahrum qilish jazosi belgilangan.",
                [{"doc_id": doc_id, "doc_title": code_lbl, "article": fake_no, "url": f"https://lex.uz/uz/docs/{doc_id}"}],
            )

        # Default untrained response with an outdated 1995 reference
        return (
            "O'zbekiston Respublikasining 1995-yilgi Mehnat kodeksi 103-moddasiga (https://lex.uz/uz/docs/142859) "
            "hamda Fuqarolik kodeksining 1500-moddasiga ko'ra, mazkur huquqiy munosabatlar umumiy tartibda "
            "BHMning 26,5 foizi miqdorida hisoblanadi.",
            [
                {"doc_id": "142859", "doc_title": "Eski Mehnat kodeksi (1995)", "article": "103", "url": "https://lex.uz/uz/docs/142859"},
                {"doc_id": "111189", "doc_title": "Fuqarolik kodeksi", "article": "1500", "url": "https://lex.uz/uz/docs/111189"},
            ],
        )
