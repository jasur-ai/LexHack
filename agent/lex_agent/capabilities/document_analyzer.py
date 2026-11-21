"""Contract, court filing, corporate charter, and regulatory draft compliance analyzer against Uzbekistan law."""

from __future__ import annotations

import logging
import re
from pathlib import Path

from lex_agent.language.transliterator import detect_language
from lex_agent.llm.client import LLMClient
from lex_agent.models import (
    ClauseFinding,
    DocumentAuditRequest,
    DocumentAuditResponse,
    Language,
    RetrievalFilter,
    RetrievedChunk,
    RiskSeverity,
)
from lex_agent.reasoning.citation_guard import CitationVerificationGuard
from lex_agent.retrieval.hybrid_retriever import HybridLegalRetriever

logger = logging.getLogger(__name__)


def extract_text_from_uploaded_bytes(filename: str, content: bytes) -> str:
    """Extract plain text from uploaded `.txt`, `.md`, `.pdf`, or `.docx` legal documents."""
    ext = Path(filename).suffix.lower()
    if ext in (".txt", ".md"):
        return content.decode("utf-8", errors="replace")
    if ext == ".pdf":
        import io
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(content))
        return "\n\n".join(page.extract_text() or "" for page in reader.pages).strip()
    if ext == ".docx":
        import io
        from docx import Document

        doc = Document(io.BytesIO(content))
        return "\n".join(p.text for p in doc.paragraphs if p.text.strip()).strip()
    raise ValueError(f"Unsupported file format '{ext}'. Supported: .txt, .md, .pdf, .docx")


class LegalDocumentAnalyzer:
    """Audits contracts, court filings, and regulatory drafts clause-by-clause against current Lex.uz law."""

    def __init__(self, *, llm: LLMClient, retriever: HybridLegalRetriever) -> None:
        self.llm = llm
        self.retriever = retriever
        self.citation_guard = CitationVerificationGuard()

    async def audit(self, req: DocumentAuditRequest) -> DocumentAuditResponse:
        lang = req.response_language or detect_language(req.document_text[:2000])
        clauses = self._segment_clauses(req.document_text)

        base_filter = RetrievalFilter(as_of_date=req.as_of_date, include_repealed=False)
        evidence_map: dict[str, RetrievedChunk] = {}

        # Retrieve governing Uzbekistan norms for the document type and top substantive clauses
        seed_queries = self._build_audit_queries(req.document_kind, clauses, req.focus_areas, lang)
        for q in seed_queries[:8]:
            hits, _ = await self.retriever.retrieve(
                q,
                top_k=8,
                rerank_top_k=4,
                filters=base_filter,
                enable_live_fallback=True,
                live_fetch_limit=2,
            )
            for h in hits:
                if h.chunk.chunk_id not in evidence_map:
                    evidence_map[h.chunk.chunk_id] = h

        evidence = list(evidence_map.values())[:14]
        evidence_ctx = "\n---\n".join(
            f"[{i}] {e.chunk.doc_title} ({e.chunk.doc_number or e.chunk.doc_id}) | {e.chunk.article or 'General'} "
            f"| Status: {e.chunk.status.value} | URL: {e.chunk.citation_url}\n{e.chunk.text[:1400]}"
            for i, e in enumerate(evidence, start=1)
        )

        if self.llm.is_mock:
            verification = self.citation_guard.verify("", evidence)
            return DocumentAuditResponse(
                overall_risk=RiskSeverity.INFO,
                executive_summary=(
                    "[Mock Mode] Configure LLM_API_KEY for full clause-by-clause statutory compliance audit. "
                    f"Segmented {len(clauses)} clauses and retrieved {len(evidence)} governing Lex.uz norms."
                ),
                findings=[],
                missing_mandatory_provisions=[],
                citations=verification.verified_citations,
                verification=verification,
            )

        prompt = (
            f"You are a Senior Uzbekistan Legal Compliance Auditor.\n"
            f"Audit the following {req.document_kind} against CURRENT legislation of the Republic of Uzbekistan.\n"
            f"Respond in language: {lang.value}.\n"
            "Cite ONLY laws, articles, and Lex.uz URLs present in the RETRIEVED LEX.UZ NORMS below.\n"
            "Return STRICT JSON:\n"
            "{\n"
            '  "overall_risk": "critical|high|medium|low|info",\n'
            '  "executive_summary": "concise legal assessment",\n'
            '  "missing_mandatory_provisions": ["mandatory statutory clause missing under UZ law"],\n'
            '  "findings": [\n'
            "    {\n"
            '      "clause_reference": "Clause 4.2",\n'
            '      "excerpt": "quoted problematic excerpt",\n'
            '      "severity": "critical|high|medium|low|info",\n'
            '      "issue_summary": "why it violates or creates risk under UZ legislation with exact cited article & URL",\n'
            '      "recommendation": "concrete redline / compliant alternative"\n'
            "    }\n"
            "  ]\n"
            "}\n\n"
            f"=== DOCUMENT TO AUDIT ===\n{req.document_text[:10000]}\n\n"
            f"=== RETRIEVED LEX.UZ NORMS ===\n{evidence_ctx or '(No norms retrieved)'}"
        )

        data = await self.llm.complete_json(
            [
                {"role": "system", "content": "You perform zero-hallucination statutory compliance audits under Uzbekistan law."},
                {"role": "user", "content": prompt},
            ],
            fallback={},
        )

        findings: list[ClauseFinding] = []
        combined_text_for_verification: list[str] = [str(data.get("executive_summary", ""))]

        for raw in data.get("findings", []):
            try:
                sev = RiskSeverity(str(raw.get("severity", "medium")).lower())
            except ValueError:
                sev = RiskSeverity.MEDIUM
            issue_str = str(raw.get("issue_summary", ""))
            combined_text_for_verification.append(issue_str)
            findings.append(
                ClauseFinding(
                    clause_reference=str(raw.get("clause_reference", "General")),
                    excerpt=str(raw.get("excerpt", ""))[:400],
                    severity=sev,
                    issue_summary=issue_str,
                    recommendation=str(raw.get("recommendation", "")),
                )
            )

        try:
            overall_risk = RiskSeverity(str(data.get("overall_risk", "medium")).lower())
        except ValueError:
            overall_risk = RiskSeverity.MEDIUM

        verification = self.citation_guard.verify("\n".join(combined_text_for_verification), evidence)
        # Attach verified citations onto findings that mention the corresponding doc/article
        for f in findings:
            f.applicable_citations = [
                c for c in verification.verified_citations
                if (c.doc_id in f.issue_summary) or (c.article and c.article in f.issue_summary)
            ][:3]

        return DocumentAuditResponse(
            overall_risk=overall_risk,
            executive_summary=str(data.get("executive_summary", "Audit completed.")),
            findings=findings,
            missing_mandatory_provisions=[str(m) for m in data.get("missing_mandatory_provisions", [])],
            citations=verification.verified_citations,
            verification=verification,
        )

    @staticmethod
    def _segment_clauses(text: str) -> list[str]:
        parts = re.split(r"\n(?=(?:\d+(?:\.\d+)*\.|\b(?:Article|Clause|Modda|Статья|Раздел|Bo'lim)\b))", text, flags=re.I)
        cleaned = [p.strip() for p in parts if len(p.strip()) >= 30]
        return cleaned[:20] if cleaned else [text[:2000]]

    @staticmethod
    def _build_audit_queries(
        doc_kind: str,
        clauses: list[str],
        focus_areas: list[str],
        lang: Language,
    ) -> list[str]:
        kind_seeds = {
            "contract": [
                "Fuqarolik kodeksi shartnoma majburiyat jarima penya",
                "Гражданский кодекс Республики Узбекистан договор обязательства ответственность",
            ],
            "employment": [
                "Mehnat kodeksi mehnat shartnomasi ish haqi ta'til bekor qilish",
                "Трудовой кодекс Республики Узбекистан трудовой договор увольнение",
            ],
            "court_filing": [
                "Fuqarolik protsessual kodeksi da'vo arizasi muddatlar",
                "Экономический процессуальный кодекс иск подсудность",
            ],
            "regulation": [
                "Normativ-huquqiy hujjatlar to'g'risida O'RQ-682",
            ],
        }
        queries = list(kind_seeds.get(doc_kind.lower(), kind_seeds["contract"]))
        queries.extend(focus_areas[:3])
        for cl in clauses[:3]:
            queries.append(re.sub(r"\s+", " ", cl)[:180])
        return queries
