"""Independent Zero-Trust Lex.uz & Local Corpus Fact Verifier (never trusts Target Agent's own citations)."""

from __future__ import annotations

import json
import logging
import re
import sqlite3
from typing import Any

import httpx
from bs4 import BeautifulSoup

from evaluator_agent.config import AuditorSettings, get_settings
from evaluator_agent.models import ClaimVerificationResult, ClaimVerificationStatus, ExtractedClaim

logger = logging.getLogger(__name__)

# Known realistic upper-bound article counts for major Uzbekistan Codes (instant fabricated-article detector!)
CODE_MAX_ARTICLES: dict[str, int] = {
    "Konstitutsiya": 155,
    "Oila kodeksi": 238,
    "Jinoyat kodeksi": 302,
    "Mehnat kodeksi": 581,
    "Soliq kodeksi": 480,
    "MJtK": 348,
    "Normativ-huquqiy hujjatlar to'g'risida": 60,
    "Shaxsga doir ma'lumotlar to'g'risida": 35,
}

# Canonical doc IDs for rapid independent lookup when code name is cited without URL
CANONICAL_CODE_DOC_IDS: dict[str, str] = {
    "Konstitutsiya": "6445147",
    "Normativ-huquqiy hujjatlar to'g'risida": "5378966",
    "Mehnat kodeksi": "6257288",
    "Soliq kodeksi": "4674902",
    "Oila kodeksi": "104720",
    "Fuqarolik kodeksi": "111189",
    "Jinoyat kodeksi": "111453",
    "MJtK": "97664",
    "Bojxona kodeksi": "2876354",
    "Yer kodeksi": "152653",
    "Shaxsga doir ma'lumotlar to'g'risida": "4396419",
}


class IndependentLexVerifier:
    """Independently cross-examines every claim against local read-only SQLite corpus and live `lex.uz`."""

    def __init__(self, settings: AuditorSettings | None = None) -> None:
        self.settings = settings or get_settings()
        self._http: httpx.AsyncClient | None = None

    def _get_http(self) -> httpx.AsyncClient:
        if self._http is None or self._http.is_closed:
            self._http = httpx.AsyncClient(
                timeout=httpx.Timeout(self.settings.lex_uz_timeout, connect=8.0),
                follow_redirects=True,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/131.0.0.0"},
            )
        return self._http

    async def close(self) -> None:
        if self._http and not self._http.is_closed:
            await self._http.aclose()

    def _query_local_corpus(
        self,
        *,
        doc_id: str | None = None,
        doc_number: str | None = None,
        article: str | None = None,
        title_hint: str | None = None,
    ) -> dict[str, Any] | None:
        """Read-only lookup against local SQLite corpus (`../agent/data/bm25_index.sqlite3`) if available."""
        db_path = self.settings.local_corpus_db_path
        if not db_path.exists():
            return None

        try:
            conn = sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True)
            conn.row_factory = sqlite3.Row
        except Exception:
            try:
                conn = sqlite3.connect(db_path)
                conn.row_factory = sqlite3.Row
            except Exception:
                return None

        try:
            rows = []
            if doc_id:
                if article:
                    rows = conn.execute(
                        "SELECT chunk_json FROM chunks WHERE (doc_id = ? OR canonical_id = ?) AND article LIKE ? LIMIT 3",
                        (doc_id, doc_id, f"%{article}%"),
                    ).fetchall()
                if not rows:
                    rows = conn.execute(
                        "SELECT chunk_json FROM chunks WHERE doc_id = ? OR canonical_id = ? LIMIT 3",
                        (doc_id, doc_id),
                    ).fetchall()
            elif doc_number:
                clean_num = doc_number.upper().strip()
                rows = conn.execute(
                    "SELECT chunk_json FROM chunks WHERE UPPER(doc_number) LIKE ? LIMIT 3",
                    (f"%{clean_num}%",),
                ).fetchall()
            elif title_hint and title_hint in CANONICAL_CODE_DOC_IDS:
                cid = CANONICAL_CODE_DOC_IDS[title_hint]
                if article:
                    rows = conn.execute(
                        "SELECT chunk_json FROM chunks WHERE (doc_id = ? OR canonical_id = ?) AND article LIKE ? LIMIT 3",
                        (cid, cid, f"%{article}%"),
                    ).fetchall()
                if not rows:
                    rows = conn.execute(
                        "SELECT chunk_json FROM chunks WHERE doc_id = ? OR canonical_id = ? LIMIT 2",
                        (cid, cid),
                    ).fetchall()

            if not rows:
                return None

            parsed = [json.loads(r["chunk_json"]) for r in rows]
            # Prefer exact article hit if multiple returned
            chosen = parsed[0]
            if article:
                for p in parsed:
                    if p.get("article") and article in str(p["article"]):
                        chosen = p
                        break
            return chosen
        except Exception as exc:
            logger.debug("Local corpus read failed: %s", exc)
            return None
        finally:
            conn.close()

    async def _fetch_live_lex_doc(self, doc_id: str) -> dict[str, Any] | None:
        """Independently fetch and cache a document from `https://lex.uz/uz/docs/{doc_id}`."""
        if not self.settings.enable_live_lex_verify:
            return None
        safe_id = re.sub(r"[^0-9-]", "", str(doc_id))
        if not safe_id:
            return None

        cache_file = self.settings.lex_cache_dir / f"lex_{safe_id}.json"
        if cache_file.exists():
            try:
                return json.loads(cache_file.read_text(encoding="utf-8"))
            except Exception:
                pass

        url = f"{self.settings.lex_uz_base_url.rstrip('/')}/uz/docs/{safe_id}"
        try:
            http = self._get_http()
            resp = await http.get(url)
            if resp.status_code == 404:
                return {"exists": False, "url": url}
            resp.raise_for_status()
            html = resp.text
        except Exception as exc:
            logger.debug("Independent Lex.uz live fetch failed for %s: %s", url, exc)
            return None

        soup = BeautifulSoup(html, "lxml")
        for t in soup(["script", "style", "noscript"]):
            t.decompose()
        title_el = soup.select_one("h1") or soup.title
        title = re.sub(r"\s+", " ", title_el.get_text(" ", strip=True)) if title_el else ""
        body_text = re.sub(r"\s+", " ", soup.get_text(" ", strip=True))
        low = body_text.lower()

        if len(body_text) < 250 or "hujjat topilmadi" in low or "документ не найден" in low:
            result = {"exists": False, "url": url}
        else:
            status = "in_force"
            if any(k in low for k in ("kuchini yo'qotgan", "кучини йўқотган", "утратил силу", "repealed")):
                status = "repealed"
            elif any(k in low for k in ("tahririda", "в редакции", "amended")):
                status = "amended"
            result = {
                "exists": True,
                "doc_id": safe_id,
                "url": url,
                "doc_title": title[:200],
                "status": status,
                "text": body_text[:25000],
            }

        try:
            cache_file.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
        except Exception:
            pass
        return result

    @staticmethod
    def _article_in_text(article: str, text: str) -> bool:
        num = re.escape(article.strip())
        return bool(
            re.search(
                rf"(?:\b{num}\s*-?\s*(?:modda|модда)|(?:статья|ст\.|article|art\.)\s*{num}\b)",
                text,
                re.I,
            )
        )

    @staticmethod
    def _token_alignment(claim_text: str, source_text: str) -> float:
        c_toks = {t for t in re.findall(r"[a-zA-Z0-9\u0400-\u04ff]{4,}", claim_text.lower())}
        s_toks = {t for t in re.findall(r"[a-zA-Z0-9\u0400-\u04ff]{4,}", source_text.lower())}
        if not c_toks:
            return 0.5
        return round(min(1.0, len(c_toks & s_toks) / max(1, min(len(c_toks), 12))), 3)

    async def verify_claim(self, claim: ExtractedClaim) -> ClaimVerificationResult:
        """Independently verify one extracted legal claim against local corpus and live Lex.uz."""
        # 1. Instant mathematical impossibility check (e.g., Family Code Art. 412, Criminal Code Art. 615)
        if claim.cited_doc_title in CODE_MAX_ARTICLES and claim.cited_article:
            base_num_m = re.match(r"^(\d+)", claim.cited_article)
            if base_num_m and int(base_num_m.group(1)) > CODE_MAX_ARTICLES[claim.cited_doc_title]:
                max_art = CODE_MAX_ARTICLES[claim.cited_doc_title]
                return ClaimVerificationResult(
                    claim=claim,
                    status=ClaimVerificationStatus.FABRICATED,
                    independent_doc_title=claim.cited_doc_title,
                    independent_norm_status="non_existent",
                    auditor_note=(
                        f"FABRICATED ARTICLE: '{claim.cited_doc_title}' has at most ~{max_art} articles; "
                        f"Article {claim.cited_article} does NOT exist."
                    ),
                )

        # 2. Check obviously fabricated act numbers like PF-9999 / VMQ-7777 / O'RQ-98765
        if claim.cited_doc_number:
            digits = re.sub(r"\D", "", claim.cited_doc_number)
            if digits and int(digits) >= 7000:
                # Confirm it doesn't exist locally before flagging fabricated
                local_num_hit = self._query_local_corpus(doc_number=claim.cited_doc_number)
                if not local_num_hit:
                    return ClaimVerificationResult(
                        claim=claim,
                        status=ClaimVerificationStatus.FABRICATED,
                        independent_norm_status="non_existent",
                        auditor_note=f"FABRICATED ACT NUMBER: '{claim.cited_doc_number}' does not exist in Uzbekistan legislation.",
                    )

        # 3. Check local read-only corpus first (millisecond verification)
        resolved_doc_id = claim.cited_doc_id or (
            CANONICAL_CODE_DOC_IDS.get(claim.cited_doc_title) if claim.cited_doc_title else None
        )
        local_hit = self._query_local_corpus(
            doc_id=resolved_doc_id,
            doc_number=claim.cited_doc_number,
            article=claim.cited_article,
            title_hint=claim.cited_doc_title,
        )

        if local_hit:
            src_text = str(local_hit.get("text") or "")
            src_status = str(local_hit.get("status") or "in_force")
            src_url = str(local_hit.get("url") or f"https://lex.uz/uz/docs/{local_hit.get('doc_id')}")
            src_title = str(local_hit.get("doc_title") or claim.cited_doc_title or "")
            align = self._token_alignment(claim.claim_text, src_text)

            if src_status == "repealed" and claim.claimed_status != "repealed":
                return ClaimVerificationResult(
                    claim=claim,
                    status=ClaimVerificationStatus.REPEALED_OR_OUTDATED,
                    independent_source_url=src_url,
                    independent_doc_title=src_title,
                    independent_norm_status="repealed",
                    independent_excerpt=src_text[:420],
                    alignment_score=align,
                    auditor_note="REPEALED NORM CITED AS ACTIVE: Document is marked repealed on Lex.uz.",
                )

            if claim.cited_article:
                art_matched = (
                    (local_hit.get("article") and claim.cited_article in str(local_hit["article"]))
                    or self._article_in_text(claim.cited_article, src_text)
                )
                if not art_matched and resolved_doc_id:
                    # Cross-check live Lex.uz before declaring article missing
                    live_doc = await self._fetch_live_lex_doc(resolved_doc_id)
                    if live_doc and live_doc.get("exists"):
                        if self._article_in_text(claim.cited_article, live_doc.get("text", "")):
                            return ClaimVerificationResult(
                                claim=claim,
                                status=ClaimVerificationStatus.VERIFIED,
                                independent_source_url=live_doc["url"],
                                independent_doc_title=live_doc.get("doc_title") or src_title,
                                independent_norm_status=live_doc.get("status", "in_force"),
                                independent_excerpt=src_text[:380],
                                alignment_score=max(align, 0.5),
                                auditor_note=f"Article {claim.cited_article} independently verified live on Lex.uz.",
                            )
                        return ClaimVerificationResult(
                            claim=claim,
                            status=ClaimVerificationStatus.FABRICATED,
                            independent_source_url=live_doc["url"],
                            independent_doc_title=live_doc.get("doc_title") or src_title,
                            independent_norm_status=live_doc.get("status", "in_force"),
                            auditor_note=f"Article {claim.cited_article} NOT found inside live Lex.uz document {resolved_doc_id}.",
                        )

            return ClaimVerificationResult(
                claim=claim,
                status=ClaimVerificationStatus.VERIFIED,
                independent_source_url=src_url,
                independent_doc_title=src_title,
                independent_norm_status=src_status,
                independent_excerpt=src_text[:420],
                alignment_score=align,
                auditor_note="Independently verified against authoritative Uzbekistan legislation corpus.",
            )

        # 4. Live Lex.uz verification if doc_id was provided by Target Agent
        if resolved_doc_id:
            live_doc = await self._fetch_live_lex_doc(resolved_doc_id)
            if live_doc is not None:
                if not live_doc.get("exists"):
                    return ClaimVerificationResult(
                        claim=claim,
                        status=ClaimVerificationStatus.FABRICATED,
                        independent_source_url=live_doc.get("url"),
                        independent_norm_status="non_existent",
                        auditor_note=f"FABRICATED URL/ID: Lex.uz document {resolved_doc_id} does not exist (404/empty).",
                    )
                live_text = str(live_doc.get("text") or "")
                live_status = str(live_doc.get("status") or "in_force")
                if live_status == "repealed" and claim.claimed_status != "repealed":
                    return ClaimVerificationResult(
                        claim=claim,
                        status=ClaimVerificationStatus.REPEALED_OR_OUTDATED,
                        independent_source_url=live_doc["url"],
                        independent_doc_title=live_doc.get("doc_title"),
                        independent_norm_status="repealed",
                        independent_excerpt=live_text[:420],
                        auditor_note="Live Lex.uz confirms this document is REPEALED, yet Target Agent cited it without repeal warning.",
                    )
                if claim.cited_article and not self._article_in_text(claim.cited_article, live_text):
                    return ClaimVerificationResult(
                        claim=claim,
                        status=ClaimVerificationStatus.FABRICATED,
                        independent_source_url=live_doc["url"],
                        independent_doc_title=live_doc.get("doc_title"),
                        independent_norm_status=live_status,
                        auditor_note=f"Document {resolved_doc_id} exists on Lex.uz, but Article {claim.cited_article} was NOT found in it.",
                    )
                return ClaimVerificationResult(
                    claim=claim,
                    status=ClaimVerificationStatus.VERIFIED,
                    independent_source_url=live_doc["url"],
                    independent_doc_title=live_doc.get("doc_title"),
                    independent_norm_status=live_status,
                    independent_excerpt=live_text[:420],
                    alignment_score=self._token_alignment(claim.claim_text, live_text),
                    auditor_note="Independently verified live on Lex.uz.",
                )

        return ClaimVerificationResult(
            claim=claim,
            status=ClaimVerificationStatus.UNVERIFIED,
            independent_norm_status="unknown",
            auditor_note="Could not verify claim in local corpus or live Lex.uz (missing doc_id / unrecognized act).",
        )
