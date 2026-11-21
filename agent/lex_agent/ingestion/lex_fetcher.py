"""Live asynchronous Lex.uz search & document fetcher with disk caching, rate limiting, and Playwright fallback."""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from urllib.parse import quote_plus, urljoin

import httpx
from bs4 import BeautifulSoup
from tenacity import retry, stop_after_attempt, wait_exponential

from lex_agent.config import Settings, get_settings
from lex_agent.ingestion.parser import classify_branches, classify_document_type, parse_date_string
from lex_agent.language.transliterator import detect_language, normalize_uzbek_apostrophes
from lex_agent.models import (
    AmendmentRecord,
    DocumentMetadata,
    LEGAL_FORCE_HIERARCHY,
    Language,
    NormStatus,
)

logger = logging.getLogger(__name__)

_DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "uz-UZ,uz;q=0.9,ru-RU;q=0.8,en-US;q=0.7",
}


@dataclass
class LexSearchResult:
    """Single item returned from a live Lex.uz search query."""

    doc_id: str
    title: str
    url: str
    language: Language
    doc_number: str | None = None
    adoption_date: date | None = None
    status: NormStatus = NormStatus.UNKNOWN
    snippet: str = ""


@dataclass
class FetchedDocument:
    """Raw & parsed Lex.uz document payload ready for hierarchical chunking."""

    metadata: DocumentMetadata
    raw_text: str
    raw_html: str = ""
    html_links: list[tuple[str, str]] = field(default_factory=list)
    article_anchors: dict[str, str] = field(default_factory=dict)


class _RateLimiter:
    """Simple async token-spacing rate limiter to avoid hammering Lex.uz."""

    def __init__(self, rps: float) -> None:
        self._min_interval = 1.0 / max(rps, 0.2)
        self._last = 0.0
        self._lock = asyncio.Lock()

    async def wait(self) -> None:
        async with self._lock:
            now = time.monotonic()
            delta = now - self._last
            if delta < self._min_interval:
                await asyncio.sleep(self._min_interval - delta)
            self._last = time.monotonic()


class LexUzFetcher:
    """Async client for live Lex.uz search and document retrieval across UZ, RU, and EN."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.base_url = self.settings.lex_uz_base_url.rstrip("/")
        self._limiter = _RateLimiter(self.settings.lex_uz_rate_limit_rps)
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                headers=_DEFAULT_HEADERS,
                timeout=self.settings.lex_uz_timeout,
                follow_redirects=True,
                http2=False,
            )
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    def _cache_path(self, doc_id: str, lang_prefix: str) -> Path:
        safe_id = re.sub(r"[^0-9-]", "", str(doc_id))
        return self.settings.cache_dir / f"doc_{lang_prefix}_{safe_id}.json"

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=6), reraise=True)
    async def _get_html(self, url: str) -> str:
        await self._limiter.wait()
        client = await self._get_client()
        resp = await client.get(url)
        resp.raise_for_status()
        html = resp.text

        # Optional Playwright rendering fallback when ASP.NET/JS body appears empty
        if self.settings.lex_uz_use_playwright and len(html) < 2500:
            pw_html = await self._fetch_with_playwright(url)
            if pw_html:
                return pw_html
        return html

    async def _fetch_with_playwright(self, url: str) -> str | None:
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            logger.debug("Playwright not installed; skipping JS rendering fallback.")
            return None

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                await page.goto(url, wait_until="networkidle", timeout=int(self.settings.lex_uz_timeout * 1000))
                content = await page.content()
                await browser.close()
                return content
        except Exception as exc:
            logger.warning("Playwright fallback failed for %s: %s", url, exc)
            return None

    async def search(
        self,
        query: str,
        *,
        language: Language = Language.UZ_LATN,
        limit: int = 10,
        status_in_force_only: bool = False,
    ) -> list[LexSearchResult]:
        """Search Lex.uz live across `https://lex.uz/{uz|ru|en}/search`."""
        lang_prefix = language.lex_path_prefix
        encoded = quote_plus(query.strip())
        candidate_urls = [
            f"{self.base_url}/{lang_prefix}/search/all?searchtitle={encoded}&searchtext={encoded}",
            f"{self.base_url}/search/all?searchtitle={encoded}&searchtext={encoded}",
            f"{self.base_url}/{lang_prefix}/search?query={encoded}",
        ]

        html = ""
        for url in candidate_urls:
            try:
                html = await self._get_html(url)
                if "/docs/" in html:
                    break
            except Exception as exc:
                logger.debug("Lex.uz search endpoint %s failed: %s", url, exc)

        if not html:
            return []

        return self._parse_search_results(html, language=language, limit=limit, in_force_only=status_in_force_only)

    def _parse_search_results(
        self,
        html: str,
        *,
        language: Language,
        limit: int,
        in_force_only: bool,
    ) -> list[LexSearchResult]:
        soup = BeautifulSoup(html, "lxml")
        results: list[LexSearchResult] = []
        seen_ids: set[str] = set()

        for a in soup.find_all("a", href=re.compile(r"/(?:(?:uz|ru|en)/)?docs/-?\d+")):
            href = a.get("href", "")
            m = re.search(r"/docs/(-?\d+)", href)
            if not m:
                continue
            doc_id = m.group(1)
            if doc_id in seen_ids:
                continue
            title = re.sub(r"\s+", " ", a.get_text(" ", strip=True))
            if len(title) < 6:
                continue

            parent_text = ""
            if a.parent and a.parent.parent:
                parent_text = re.sub(r"\s+", " ", a.parent.parent.get_text(" ", strip=True))

            status = self._infer_status(parent_text)
            if in_force_only and status == NormStatus.REPEALED:
                continue

            doc_num = self._extract_doc_number(f"{title} {parent_text}")
            adoption_date = self._extract_first_date(parent_text)
            full_url = urljoin(self.base_url, href)

            seen_ids.add(doc_id)
            results.append(
                LexSearchResult(
                    doc_id=doc_id,
                    title=normalize_uzbek_apostrophes(title),
                    url=full_url,
                    language=detect_language(title) if title else language,
                    doc_number=doc_num,
                    adoption_date=adoption_date,
                    status=status,
                    snippet=parent_text[:300],
                )
            )
            if len(results) >= limit:
                break

        return results

    async def fetch_document(
        self,
        doc_id: str,
        *,
        language: Language = Language.UZ_LATN,
        use_cache: bool = True,
    ) -> FetchedDocument | None:
        """Fetch and parse a full Lex.uz document including metadata, status, language links, and body text."""
        lang_prefix = language.lex_path_prefix
        cache_file = self._cache_path(doc_id, lang_prefix)

        if use_cache and cache_file.exists():
            try:
                cached = json.loads(cache_file.read_text(encoding="utf-8"))
                return FetchedDocument(
                    metadata=DocumentMetadata.model_validate(cached["metadata"]),
                    raw_text=cached["raw_text"],
                    html_links=[tuple(x) for x in cached.get("html_links", [])],
                    article_anchors=cached.get("article_anchors", {}),
                )
            except Exception:
                pass

        url = f"{self.base_url}/{lang_prefix}/docs/{doc_id}"
        try:
            html = await self._get_html(url)
        except Exception as exc:
            logger.warning("Failed to fetch Lex.uz document %s: %s", url, exc)
            return None

        parsed = self.parse_document_html(html, doc_id=str(doc_id), url=url, requested_language=language)
        if parsed and parsed.raw_text and use_cache:
            try:
                cache_file.write_text(
                    json.dumps(
                        {
                            "metadata": parsed.metadata.model_dump(mode="json"),
                            "raw_text": parsed.raw_text,
                            "html_links": parsed.html_links,
                            "article_anchors": parsed.article_anchors,
                        },
                        ensure_ascii=False,
                    ),
                    encoding="utf-8",
                )
            except Exception as exc:
                logger.debug("Cache write failed for %s: %s", cache_file, exc)
        return parsed

    async def fetch_all_languages(
        self,
        doc_id: str,
        *,
        use_cache: bool = True,
    ) -> dict[Language, FetchedDocument]:
        """Fetch a document and follow its Lex.uz language switcher links across UZ, RU, and EN."""
        docs: dict[Language, FetchedDocument] = {}
        primary = await self.fetch_document(doc_id, language=Language.UZ_LATN, use_cache=use_cache)
        if not primary:
            primary = await self.fetch_document(doc_id, language=Language.RU, use_cache=use_cache)
        if not primary:
            return docs

        docs[primary.metadata.language] = primary
        # Follow discovered language links + try standard prefixes on same doc_id
        targets: list[tuple[Language, str]] = []
        for lang_str, linked_id in primary.metadata.linked_doc_ids.items():
            try:
                l_enum = Language(lang_str)
                if l_enum not in docs:
                    targets.append((l_enum, linked_id))
            except ValueError:
                pass

        for fallback_lang in (Language.UZ_LATN, Language.RU, Language.EN):
            if fallback_lang not in docs and not any(t[0] == fallback_lang for t in targets):
                targets.append((fallback_lang, doc_id))

        for lang_enum, target_id in targets:
            fetched = await self.fetch_document(target_id, language=lang_enum, use_cache=use_cache)
            if fetched and len(fetched.raw_text) > 120:
                docs[fetched.metadata.language] = fetched

        # Cross-populate linked URLs and doc IDs across all fetched editions
        shared_ids = {k.value: v.metadata.doc_id for k, v in docs.items()}
        shared_urls = {k.value: v.metadata.url for k, v in docs.items()}
        canonical_id = str(abs(int(re.sub(r"[^0-9-]", "", doc_id) or "0"))) if re.search(r"\d", doc_id) else doc_id
        for fetched in docs.values():
            fetched.metadata.canonical_id = canonical_id
            fetched.metadata.linked_doc_ids.update(shared_ids)
            fetched.metadata.linked_urls.update(shared_urls)

        return docs

    def parse_document_html(
        self,
        html: str,
        *,
        doc_id: str,
        url: str,
        requested_language: Language = Language.UZ_LATN,
    ) -> FetchedDocument:
        """Parse a Lex.uz HTML page into structured metadata, status, language links, anchors, and clean text."""
        soup = BeautifulSoup(html, "lxml")

        # Remove scripts/styles/navigation noise
        for tag in soup(["script", "style", "noscript", "iframe"]):
            tag.decompose()

        # Extract language switcher links before removing header/nav
        linked_doc_ids: dict[str, str] = {}
        linked_urls: dict[str, str] = {}
        for a in soup.find_all("a", href=re.compile(r"/(?:uz|ru|en)/docs/-?\d+")):
            href = a.get("href", "")
            m = re.search(r"/(uz|ru|en)/docs/(-?\d+)", href)
            if not m:
                continue
            prefix, lid = m.group(1), m.group(2)
            full = urljoin(self.base_url, href)
            if prefix == "uz":
                key = "uz_latn" if lid.startswith("-") else "uz_cyrl"
            else:
                key = prefix
            linked_doc_ids[key] = lid
            linked_urls[key] = full

        # Locate main document container on Lex.uz (supports multiple template generations)
        body_container = (
            soup.select_one("#divCont")
            or soup.select_one(".docBody")
            or soup.select_one(".act-body")
            or soup.select_one(".lx_doc_body")
            or soup.select_one("main")
            or soup.body
            or soup
        )

        # Extract header / card metadata text
        meta_container = (
            soup.select_one(".docHeader")
            or soup.select_one(".lx_doc_info")
            or soup.select_one(".card-info")
            or soup.select_one("header")
        )
        meta_text = meta_container.get_text(" ", strip=True) if meta_container else soup.get_text(" ", strip=True)[:1500]

        # Extract title
        title_el = (
            soup.select_one("h1")
            or soup.select_one(".ACT_TITLE")
            or soup.select_one(".doc-title")
            or soup.title
        )
        title = re.sub(r"\s+", " ", title_el.get_text(" ", strip=True)) if title_el else f"Lex.uz Document {doc_id}"
        title = normalize_uzbek_apostrophes(re.sub(r"\s*\|\s*Lex\.uz.*$", "", title, flags=re.I))

        # Collect embedded Lex.uz cross-reference links and article anchors
        html_links: list[tuple[str, str]] = []
        article_anchors: dict[str, str] = {}

        for a in body_container.find_all("a", href=re.compile(r"/docs/-?\d+")):
            href = a.get("href", "")
            link_text = re.sub(r"\s+", " ", a.get_text(" ", strip=True))
            if href:
                html_links.append((href, link_text))

        # Extract structured lines + anchors
        lines: list[str] = []
        for elem in body_container.find_all(["p", "div", "h1", "h2", "h3", "h4", "li", "tr"]):
            # Avoid duplicating parent div text when it wraps p/div children
            if elem.name == "div" and elem.find(["p", "div", "table"]):
                continue
            txt = re.sub(r"\s+", " ", elem.get_text(" ", strip=True))
            if not txt:
                continue
            elem_id = elem.get("id") or ""
            if elem_id and re.match(r"^\d+$", str(elem_id)):
                art_m = re.match(
                    r"^(?:(\d+(?:[-.]\d+)?)\s*-?\s*(?:modda|модда)|(?:Статья|Article)\s+(\d+(?:[-.]\d+)?))",
                    txt,
                    re.I,
                )
                if art_m:
                    art_num = art_m.group(1) or art_m.group(2)
                    article_anchors[art_num] = str(elem_id)
            lines.append(txt)

        raw_text = "\n".join(lines).strip()
        if not raw_text:
            raw_text = re.sub(r"\n{3,}", "\n\n", body_container.get_text("\n", strip=True))

        detected_lang = detect_language(raw_text[:2500] or title) if raw_text else requested_language
        doc_type = classify_document_type(title, raw_text[:1500])
        branches = classify_branches(title, raw_text[:3000])
        status = self._infer_status(f"{meta_text}\n{raw_text[:1000]}")
        doc_number = self._extract_doc_number(f"{title}\n{meta_text}")
        adoption_date, effective_date, expiry_date = self._extract_lifecycle_dates(meta_text)
        amendments = self._extract_amendments(raw_text, html_links)

        canonical_id = str(abs(int(doc_id))) if re.fullmatch(r"-?\d+", str(doc_id)) else str(doc_id)
        linked_doc_ids.setdefault(detected_lang.value, str(doc_id))
        linked_urls.setdefault(detected_lang.value, url)

        metadata = DocumentMetadata(
            doc_id=str(doc_id),
            canonical_id=canonical_id,
            title=title,
            doc_type=doc_type,
            doc_number=doc_number,
            language=detected_lang,
            adoption_date=adoption_date,
            effective_date=effective_date or adoption_date,
            expiry_date=expiry_date,
            status=status,
            legal_force_rank=LEGAL_FORCE_HIERARCHY.get(doc_type, 20),
            branches=branches,
            url=url,
            linked_doc_ids=linked_doc_ids,
            linked_urls=linked_urls,
            amendments=amendments,
            source="lex.uz",
        )
        return FetchedDocument(
            metadata=metadata,
            raw_text=raw_text,
            raw_html=html,
            html_links=html_links,
            article_anchors=article_anchors,
        )

    @staticmethod
    def _infer_status(text: str) -> NormStatus:
        low = normalize_uzbek_apostrophes(text).lower()
        if any(
            kw in low
            for kw in (
                "o'z kuchini yo'qotgan",
                "kuchini yo'qotgan",
                "ўз кучини йўқотган",
                "кучини йўқотган",
                "утратил силу",
                "утратила силу",
                "утратило силу",
                "repealed",
                "lost force",
                "invalidated",
            )
        ):
            if any(kw in low for kw in ("qisman", "қисман", "частично", "partially")):
                return NormStatus.PARTIALLY_REPEALED
            return NormStatus.REPEALED
        if any(kw in low for kw in ("kuchga kirmagan", "кучга кирмаган", "не вступил в силу", "not yet in force")):
            return NormStatus.NOT_YET_EFFECTIVE
        if any(
            kw in low
            for kw in (
                "o'zgartirish",
                "ўзгартириш",
                "в редакции",
                "с изменениями",
                "amended",
            )
        ):
            if any(kw in low for kw in ("amalda", "амалда", "действующий", "in force")):
                return NormStatus.AMENDED
        if any(kw in low for kw in ("amalda", "амалда", "действующий", "действует", "in force")):
            return NormStatus.IN_FORCE
        return NormStatus.UNKNOWN

    @staticmethod
    def _extract_doc_number(text: str) -> str | None:
        norm = normalize_uzbek_apostrophes(text)
        m = re.search(
            r"\b((?:O'RQ|ЎРҚ|ЗРУ|PF|ПФ|УП|PQ|ПҚ|ПП|VMQ|ВМҚ|ПКМ|F|Ф)-?\s*\d{1,5}(?:-[A-Za-zА-Яа-я0-9]+)?)\b",
            norm,
            re.I,
        )
        if m:
            return re.sub(r"\s+", "", m.group(1).upper())
        m2 = re.search(r"(?:№|No\.?)\s*([0-9A-Za-zА-Яа-яЎҚҒҲ'/-]{1,20})", norm)
        return m2.group(1) if m2 else None

    @staticmethod
    def _extract_first_date(text: str) -> date | None:
        m = re.search(r"\b(\d{2}\.\d{2}\.\d{4}|\d{4}-\d{2}-\d{2})\b", text)
        return parse_date_string(m.group(1)) if m else None

    @staticmethod
    def _extract_lifecycle_dates(meta_text: str) -> tuple[date | None, date | None, date | None]:
        low = normalize_uzbek_apostrophes(meta_text)
        adoption = None
        effective = None
        expiry = None

        adopt_m = re.search(
            r"(?:qabul qilingan|қабул қилинган|дата принятия|adopted|от)\D{0,25}(\d{2}\.\d{2}\.\d{4}|\d{4}-\d{2}-\d{2})",
            low,
            re.I,
        )
        if adopt_m:
            adoption = parse_date_string(adopt_m.group(1))

        eff_m = re.search(
            r"(?:kuchga kirish|кучга кириш|вступления в силу|effective|введен)\D{0,25}(\d{2}\.\d{2}\.\d{4}|\d{4}-\d{2}-\d{2})",
            low,
            re.I,
        )
        if eff_m:
            effective = parse_date_string(eff_m.group(1))

        exp_m = re.search(
            r"(?:kuchini yo'qotgan|кучини йўқотган|утрат\w+ силу|repealed|expiry)\D{0,25}(\d{2}\.\d{2}\.\d{4}|\d{4}-\d{2}-\d{2})",
            low,
            re.I,
        )
        if exp_m:
            expiry = parse_date_string(exp_m.group(1))

        if not adoption:
            all_dates = re.findall(r"\b(\d{2}\.\d{2}\.\d{4}|\d{4}-\d{2}-\d{2})\b", low)
            if all_dates:
                adoption = parse_date_string(all_dates[0])
        return adoption, effective, expiry

    @staticmethod
    def _extract_amendments(raw_text: str, html_links: list[tuple[str, str]]) -> list[AmendmentRecord]:
        records: list[AmendmentRecord] = []
        # Look for inline Lex.uz editorial notes "(O'RQ-xxx-son Qonuni tahririda / в редакции Закона ...)"
        pattern = re.compile(
            r"\(([^()]{10,220}?(?:tahririda|таҳририда|в редакции|kiritilgan|киритилган|дополнен|изменен|amended)[^()]{0,120})\)",
            re.I,
        )
        seen: set[str] = set()
        for m in pattern.finditer(raw_text):
            note = re.sub(r"\s+", " ", m.group(1)).strip()
            if note in seen:
                continue
            seen.add(note)
            num_m = re.search(r"\b((?:O'RQ|ЎРҚ|ЗРУ|PF|ПФ|УП|PQ|ПҚ|ПП|VMQ|ПКМ)-?\d+)\b", note, re.I)
            date_m = re.search(r"\b(\d{2}\.\d{2}\.\d{4}|\d{4}-\d{2}-\d{2})\b", note)
            records.append(
                AmendmentRecord(
                    amending_doc_number=num_m.group(1).upper() if num_m else None,
                    amendment_date=parse_date_string(date_m.group(1)) if date_m else None,
                    summary=note[:240],
                )
            )
            if len(records) >= 15:
                break
        return records
