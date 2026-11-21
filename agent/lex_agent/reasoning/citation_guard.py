"""Zero-hallucination strict citation and grounding verification guard."""

from __future__ import annotations

import re

from lex_agent.language.transliterator import normalize_uzbek_apostrophes
from lex_agent.models import Citation, NormStatus, RetrievedChunk, VerificationReport

_URL_DOC_RE = re.compile(r"https?://(?:www\.)?lex\.uz/(?:(?:uz|ru|en)/)?docs/(-?\d+)", re.I)
_ACT_NUM_RE = re.compile(
    r"\b((?:O'RQ|ЎРҚ|ЗРУ|PF|ПФ|УП|PQ|ПҚ|ПП|VMQ|ВМҚ|ПКМ)-?\d{1,5})\b",
    re.I,
)
_ARTICLE_CITE_RE = re.compile(
    r"\b(\d+(?:[-.]\d+)?)\s*-?\s*(?:modda\w*|модда\w*)|\b(?:стать[еёяйюяи]\w*|ст\.|Article|Art\.)\s*(\d+(?:[-.]\d+)?)\b",
    re.I,
)


class CitationVerificationGuard:
    """Strictly verifies every legal citation in an LLM answer against retrieved Lex.uz evidence."""

    def verify(
        self,
        answer_text: str,
        evidence: list[RetrievedChunk],
        *,
        temporal_warnings: list[str] | None = None,
        translation_warnings: list[str] | None = None,
    ) -> VerificationReport:
        """Audit answer text against retrieved chunks to prevent fabricated articles, act numbers, or URLs."""
        norm_answer = normalize_uzbek_apostrophes(answer_text)

        # Build verified evidence lookup tables
        ev_doc_ids: set[str] = set()
        ev_doc_numbers: set[str] = set()
        ev_articles: set[str] = set()
        ev_chunks_by_doc: dict[str, list[RetrievedChunk]] = {}

        for item in evidence:
            c = item.chunk
            ev_doc_ids.add(c.doc_id)
            ev_doc_ids.add(c.canonical_id)
            ev_chunks_by_doc.setdefault(c.doc_id, []).append(item)
            if c.doc_number:
                ev_doc_numbers.add(normalize_uzbek_apostrophes(c.doc_number).upper())
            if c.article:
                m = re.search(r"(\d+(?:[-.]\d+)?)", c.article)
                if m:
                    ev_articles.add(m.group(1))
            # Also allow articles explicitly quoted inside the chunk text itself
            for a, b in _ARTICLE_CITE_RE.findall(c.text):
                num = a or b
                if num:
                    ev_articles.add(num)

        unverified: list[str] = []
        total_checked = 0

        # 1. Verify every Lex.uz URL mentioned in answer
        cited_url_ids: set[str] = set()
        for m in _URL_DOC_RE.finditer(norm_answer):
            total_checked += 1
            doc_id = m.group(1)
            cited_url_ids.add(doc_id)
            if doc_id not in ev_doc_ids:
                unverified.append(f"Unverified Lex.uz URL doc_id={doc_id} ({m.group(0)}) not present in retrieved evidence.")

        # 2. Verify every act number (O'RQ-xxx, PF-xxx, VMQ-xxx) mentioned in answer
        for m in _ACT_NUM_RE.finditer(norm_answer):
            total_checked += 1
            num = m.group(1).upper()
            # Match loosely by numeric suffix across UZ/RU prefixes (e.g. O'RQ-682 == ЗРУ-682)
            digits = re.sub(r"\D", "", num)
            matched = any(num == ev_num or (digits and ev_num.endswith(digits)) for ev_num in ev_doc_numbers)
            if not matched:
                # Also check if act number appears inside any retrieved chunk body text
                in_body = any(num in normalize_uzbek_apostrophes(e.chunk.text).upper() for e in evidence)
                if not in_body:
                    unverified.append(f"Unverified normative act number '{num}' not found in retrieved Lex.uz evidence.")

        # 3. Verify every article number cited in answer
        cited_articles: set[str] = set()
        for a, b in _ARTICLE_CITE_RE.findall(norm_answer):
            art = a or b
            if not art:
                continue
            cited_articles.add(art)
        for art in sorted(cited_articles):
            total_checked += 1
            if art not in ev_articles:
                unverified.append(f"Unverified article citation 'Article/{art}-modda' not grounded in retrieved evidence.")

        # 4. Assemble verified Citation objects from retrieved evidence that supports the answer
        verified_citations: list[Citation] = []
        seen_cite_keys: set[tuple[str, str | None]] = set()
        repealed_warnings = list(temporal_warnings or [])

        for item in evidence:
            c = item.chunk
            cite_key = (c.doc_id, c.article)
            if cite_key in seen_cite_keys:
                continue
            seen_cite_keys.add(cite_key)

            status_note = ""
            if c.status == NormStatus.REPEALED:
                status_note = "WARNING: Repealed / Lost force on Lex.uz."
                warn = f"{c.doc_title} ({c.doc_id}) is REPEALED."
                if warn not in repealed_warnings:
                    repealed_warnings.append(warn)
            elif c.status == NormStatus.AMENDED:
                status_note = "In force (as amended)."
            elif c.status == NormStatus.IN_FORCE:
                status_note = "In force."

            verified_citations.append(
                Citation(
                    doc_id=c.doc_id,
                    doc_title=c.doc_title,
                    doc_number=c.doc_number,
                    adoption_date=c.adoption_date,
                    article=c.article,
                    clause=c.clause,
                    status=c.status,
                    url=c.citation_url,
                    language=c.language,
                    verified=True,
                    verification_note=status_note,
                )
            )

        unverified = list(dict.fromkeys(unverified))
        passed = len(unverified) == 0 and (len(verified_citations) > 0 or total_checked == 0)

        if total_checked == 0:
            confidence = 0.7 if verified_citations else 0.2
        else:
            grounded_ratio = max(0.0, (total_checked - len(unverified)) / total_checked)
            confidence = round(min(1.0, grounded_ratio * (0.95 if verified_citations else 0.4)), 3)

        return VerificationReport(
            passed=passed,
            total_claims_checked=total_checked,
            verified_citations=verified_citations[:15],
            unverified_references=unverified,
            repealed_or_amended_warnings=repealed_warnings,
            translation_discrepancy_warnings=list(translation_warnings or []),
            confidence_score=confidence,
        )
