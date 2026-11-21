"""Core Pydantic domain models for Uzbekistan legislation, hybrid retrieval, and legal reasoning."""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


class Language(str, Enum):
    """Supported languages and scripts on Lex.uz."""

    UZ_LATN = "uz_latn"
    UZ_CYRL = "uz_cyrl"
    RU = "ru"
    EN = "en"

    @property
    def lex_path_prefix(self) -> str:
        if self in (Language.UZ_LATN, Language.UZ_CYRL):
            return "uz"
        return self.value


class DocumentType(str, Enum):
    """Types of normative-legal acts and judicial interpretations in Uzbekistan."""

    CONSTITUTION = "constitution"
    CONSTITUTIONAL_LAW = "constitutional_law"
    CODE = "code"
    LAW = "law"
    OLIY_MAJLIS_RESOLUTION = "oliy_majlis_resolution"
    PRESIDENTIAL_DECREE = "presidential_decree"          # Farmon / Указ (PF / УП)
    PRESIDENTIAL_RESOLUTION = "presidential_resolution"  # Qaror / Постановление (PQ / ПП)
    PRESIDENTIAL_ORDER = "presidential_order"            # Farmoyish / Распоряжение
    SUPREME_COURT_PLENUM = "supreme_court_plenum"        # Oliy sud Plenumi qarori
    CABINET_RESOLUTION = "cabinet_resolution"            # VMQ / ПКМ
    CABINET_ORDER = "cabinet_order"                      # VMF / РКМ
    DEPARTMENTAL_ACT = "departmental_act"                # Ministry / Committee / Agency order
    LOCAL_GOVERNMENT_ACT = "local_government_act"        # Hokim / Kengash decision
    INTERNATIONAL_TREATY = "international_treaty"
    OTHER = "other"


# Normative hierarchy per Law of the Republic of Uzbekistan "On Normative-Legal Acts" (O'RQ-682, 20.04.2021)
LEGAL_FORCE_HIERARCHY: dict[DocumentType, int] = {
    DocumentType.CONSTITUTION: 100,
    DocumentType.CONSTITUTIONAL_LAW: 95,
    DocumentType.INTERNATIONAL_TREATY: 92,
    DocumentType.CODE: 90,
    DocumentType.LAW: 85,
    DocumentType.OLIY_MAJLIS_RESOLUTION: 80,
    DocumentType.PRESIDENTIAL_DECREE: 75,
    DocumentType.PRESIDENTIAL_RESOLUTION: 74,
    DocumentType.PRESIDENTIAL_ORDER: 72,
    DocumentType.SUPREME_COURT_PLENUM: 70,  # Binding judicial interpretation across courts
    DocumentType.CABINET_RESOLUTION: 65,
    DocumentType.CABINET_ORDER: 62,
    DocumentType.DEPARTMENTAL_ACT: 50,
    DocumentType.LOCAL_GOVERNMENT_ACT: 40,
    DocumentType.OTHER: 20,
}


class NormStatus(str, Enum):
    """Lifecycle status of a normative-legal act or article on Lex.uz."""

    IN_FORCE = "in_force"
    AMENDED = "amended"
    REPEALED = "repealed"
    PARTIALLY_REPEALED = "partially_repealed"
    NOT_YET_EFFECTIVE = "not_yet_effective"
    UNKNOWN = "unknown"


class LegalBranch(str, Enum):
    """Unrestricted taxonomy covering all branches of Uzbekistan legislation."""

    CONSTITUTIONAL = "constitutional"
    CIVIL = "civil"
    CRIMINAL = "criminal"
    ADMINISTRATIVE = "administrative"
    TAX = "tax"
    LABOR = "labor"
    CORPORATE_COMMERCIAL = "corporate_commercial"
    BANKING_FINANCE = "banking_finance"
    CUSTOMS = "customs"
    LAND_REAL_ESTATE = "land_real_estate"
    FAMILY = "family"
    HOUSING = "housing"
    INTELLECTUAL_PROPERTY = "intellectual_property"
    DIGITAL_IT_DATA = "digital_it_data"
    ENVIRONMENTAL_NATURAL = "environmental_natural"
    PROCEDURAL_CIVIL = "procedural_civil"
    PROCEDURAL_ECONOMIC = "procedural_economic"
    PROCEDURAL_CRIMINAL = "procedural_criminal"
    PROCEDURAL_ADMIN = "procedural_admin"
    INTERNATIONAL_TRADE = "international_trade"
    INVESTMENT_PPP = "investment_ppp"
    SOCIAL_EDUCATION_HEALTH = "social_education_health"
    DEFENSE_SECURITY = "defense_security"
    GENERAL = "general"


class RiskSeverity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class AmendmentRecord(BaseModel):
    """Tracks an amending or repealing normative act affecting a document."""

    amending_doc_id: str | None = None
    amending_doc_number: str | None = None
    amending_doc_title: str = ""
    amendment_date: date | None = None
    effective_date: date | None = None
    summary: str = ""
    url: str | None = None


class CrossReference(BaseModel):
    """Structured legal cross-reference detected inside an article or clause."""

    raw_text: str
    target_doc_id: str | None = None
    target_doc_hint: str | None = None
    target_doc_number: str | None = None
    target_article: str | None = None
    target_clause: str | None = None
    target_url: str | None = None


class DocumentMetadata(BaseModel):
    """Canonical metadata for a Lex.uz legal document across languages."""

    doc_id: str = Field(..., description="Lex.uz numeric document ID (may be negative for native UZ Latin)")
    canonical_id: str = Field(..., description="Shared cross-lingual ID linking UZ/RU/EN editions")
    title: str
    doc_type: DocumentType = DocumentType.OTHER
    doc_number: str | None = None
    language: Language = Language.UZ_LATN
    issuing_body: str | None = None
    adoption_date: date | None = None
    effective_date: date | None = None
    expiry_date: date | None = None
    status: NormStatus = NormStatus.UNKNOWN
    legal_force_rank: int = 20
    branches: list[LegalBranch] = Field(default_factory=lambda: [LegalBranch.GENERAL])
    url: str
    linked_doc_ids: dict[str, str] = Field(
        default_factory=dict,
        description="Map of language code ('uz_latn', 'uz_cyrl', 'ru', 'en') -> Lex.uz doc_id",
    )
    linked_urls: dict[str, str] = Field(
        default_factory=dict,
        description="Map of language code -> direct Lex.uz URL",
    )
    amendments: list[AmendmentRecord] = Field(default_factory=list)
    fetched_at: datetime = Field(default_factory=datetime.utcnow)
    source: str = Field(default="lex.uz", description="Origin: lex.uz, Alii2004/lexuz-legislation, etc.")


class LegalChunk(BaseModel):
    """Structure-aware hierarchical chunk (Section -> Chapter -> Article -> Clause)."""

    chunk_id: str
    doc_id: str
    canonical_id: str
    language: Language
    doc_type: DocumentType = DocumentType.OTHER
    doc_number: str | None = None
    doc_title: str
    issuing_body: str | None = None
    adoption_date: date | None = None
    effective_date: date | None = None
    expiry_date: date | None = None
    status: NormStatus = NormStatus.UNKNOWN
    legal_force_rank: int = 20
    branches: list[LegalBranch] = Field(default_factory=lambda: [LegalBranch.GENERAL])

    # Hierarchical position
    section: str | None = None
    chapter: str | None = None
    article: str | None = None
    article_title: str | None = None
    clause: str | None = None

    # Content
    text: str
    normalized_text: str = Field(
        default="",
        description="Latin-normalized searchable mirror for seamless UZ Cyrillic <-> Latin matching",
    )
    url: str
    anchor: str | None = None
    cross_references: list[CrossReference] = Field(default_factory=list)
    extra: dict[str, Any] = Field(default_factory=dict)

    @property
    def citation_url(self) -> str:
        if self.anchor and "#" not in self.url:
            return f"{self.url}#{self.anchor}"
        return self.url

    @property
    def hierarchical_path(self) -> str:
        parts = [p for p in (self.section, self.chapter, self.article, self.clause) if p]
        return " > ".join(parts) if parts else "Document Body"


class RetrievalFilter(BaseModel):
    """Structured filters for hybrid search."""

    languages: list[Language] | None = None
    doc_types: list[DocumentType] | None = None
    branches: list[LegalBranch] | None = None
    statuses: list[NormStatus] | None = None
    min_legal_force_rank: int | None = None
    as_of_date: date | None = None
    doc_ids: list[str] | None = None
    article_number: str | None = None
    include_repealed: bool = False


class RetrievedChunk(BaseModel):
    """A chunk returned from hybrid search with transparent score breakdown."""

    chunk: LegalChunk
    dense_score: float = 0.0
    bm25_score: float = 0.0
    rrf_score: float = 0.0
    rerank_score: float = 0.0
    final_score: float = 0.0
    retrieval_hop: int = 1
    retrieval_source: str = "hybrid"


class SubQuery(BaseModel):
    """Single decomposed legal sub-issue."""

    issue: str
    search_queries_uz: list[str] = Field(default_factory=list)
    search_queries_ru: list[str] = Field(default_factory=list)
    search_queries_en: list[str] = Field(default_factory=list)
    branches: list[LegalBranch] = Field(default_factory=list)
    suspected_doc_types: list[DocumentType] = Field(default_factory=list)
    suspected_articles: list[str] = Field(default_factory=list)


class QueryPlan(BaseModel):
    """Output of query decomposition & legal classification."""

    original_query: str
    detected_language: Language
    sub_queries: list[SubQuery]
    branches: list[LegalBranch] = Field(default_factory=list)
    as_of_date: date | None = None
    requires_translation_comparison: bool = False
    requires_historical_comparison: bool = False
    potential_norm_conflict: bool = False


class NormConflictResolution(BaseModel):
    """Explicit resolution of conflicting legal norms."""

    higher_norm_doc_id: str
    higher_norm_title: str
    lower_or_older_doc_id: str
    lower_or_older_title: str
    principle_applied: str = Field(..., description="lex_superior | lex_posterior | lex_specialis")
    explanation: str


class Citation(BaseModel):
    """Structured legal citation backed by a verified Lex.uz document."""

    doc_id: str
    doc_title: str
    doc_number: str | None = None
    adoption_date: date | None = None
    article: str | None = None
    clause: str | None = None
    status: NormStatus = NormStatus.UNKNOWN
    url: str
    language: Language = Language.UZ_LATN
    verified: bool = False
    verification_note: str = ""


class VerificationReport(BaseModel):
    """Result of the zero-hallucination citation & grounding guard."""

    passed: bool
    total_claims_checked: int = 0
    verified_citations: list[Citation] = Field(default_factory=list)
    unverified_references: list[str] = Field(default_factory=list)
    repealed_or_amended_warnings: list[str] = Field(default_factory=list)
    translation_discrepancy_warnings: list[str] = Field(default_factory=list)
    confidence_score: float = Field(default=0.0, ge=0.0, le=1.0)
    checks: dict[str, bool] = Field(
        default_factory=dict, description="Automatic answer checks: citations, articles, language, length"
    )
    warnings: list[str] = Field(default_factory=list, description="Human-readable notes from the answer checks")


class HopTrace(BaseModel):
    """Execution trace for one retrieval hop in the multi-hop reasoning pipeline."""

    hop: int
    queries: list[str]
    cross_refs_followed: list[str] = Field(default_factory=list)
    live_lex_fetched: list[str] = Field(default_factory=list)
    chunks_added: int = 0


class ChatTurn(BaseModel):
    """One previous conversation turn."""

    role: Literal["user", "assistant"]
    content: str = Field(..., max_length=2000)


class AgentQueryRequest(BaseModel):
    """API request for legal Q&A."""

    query: str = Field(..., min_length=2)
    response_language: Language | None = None
    as_of_date: date | None = None
    include_repealed: bool = False
    max_hops: int | None = None
    enable_live_lex: bool = True
    compare_translations: bool = False
    answer_style: Literal["concise", "detailed"] | None = Field(
        default=None, description="concise = short scannable answer cards (default); detailed = long legal memo"
    )
    context: str | None = Field(
        default=None,
        max_length=600,
        description="Previous question of the conversation; lets short follow-ups ('What are the deadlines?') "
        "be searched and answered in the right topic.",
    )
    history: list[ChatTurn] | None = Field(
        default=None,
        max_length=12,
        description="Optional recent turns (oldest first) for conversation memory; the last user turn is used like "
        "`context` when `context` is not given.",
    )


class AnswerSections(BaseModel):
    """Parsed concise answer: direct answer, rules with [n] citations, steps, caution, follow-up prompts."""

    structured: bool = False
    answer: str = ""
    key_points: list[str] = Field(default_factory=list)
    steps: list[str] = Field(default_factory=list)
    caution: str = ""
    follow_ups: list[str] = Field(default_factory=list)


class SourceItem(BaseModel):
    """A numbered evidence source shown next to the answer (n matches the [n] markers)."""

    n: int
    doc_id: str
    title: str
    full_title: str
    article: str | None = None
    article_title: str | None = None
    excerpt: str = ""
    lead: str | None = None
    url: str
    language: str
    status: str
    source: str = "lex.uz"
    snapshot: str | None = None
    doc_type: str = "other"


class AgentResponse(BaseModel):
    """Comprehensive grounded legal answer."""

    answer: str
    response_language: Language
    query_plan: QueryPlan
    citations: list[Citation]
    verification: VerificationReport
    conflict_resolutions: list[NormConflictResolution] = Field(default_factory=list)
    hop_traces: list[HopTrace] = Field(default_factory=list)
    evidence_count: int = 0
    as_of_date: date | None = None
    answer_style: str = "concise"
    sections: AnswerSections | None = None
    sources: list[SourceItem] = Field(default_factory=list)
    mode: str = Field(default="llm", description="llm | extractive | cache")
    elapsed_ms: int = 0
    route: str = Field(
        default="legal",
        description="Turn type: legal | calculation | template | figures | emergency | illegal | greeting | thanks | "
        "farewell | about | off_topic | clarify | not_found",
    )
    calculation: dict[str, Any] | None = Field(default=None, description="Structured calculator result, when used")


class ClauseFinding(BaseModel):
    """Compliance finding for a specific clause in a contract, filing, or regulation."""

    clause_reference: str
    excerpt: str
    severity: RiskSeverity
    issue_summary: str
    applicable_citations: list[Citation] = Field(default_factory=list)
    recommendation: str


class DocumentAuditRequest(BaseModel):
    """Request to audit a contract, court filing, or regulatory draft against UZ law."""

    document_text: str = Field(..., min_length=20)
    document_kind: str = Field(default="contract", description="contract | court_filing | corporate_charter | regulation")
    response_language: Language | None = None
    as_of_date: date | None = None
    focus_areas: list[str] = Field(default_factory=list)


class DocumentAuditResponse(BaseModel):
    """Structured legal audit report."""

    overall_risk: RiskSeverity
    executive_summary: str
    findings: list[ClauseFinding]
    missing_mandatory_provisions: list[str] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    verification: VerificationReport


class TranslationCompareRequest(BaseModel):
    """Request to translate or compare a Lex.uz norm across UZ / RU / EN."""

    doc_id: str | None = None
    article: str | None = None
    source_text: str | None = None
    source_language: Language | None = None
    target_language: Language = Language.EN
    verify_against_uz_primary: bool = True


class DiscrepancyItem(BaseModel):
    """Detected legal/semantic discrepancy between Uzbek authoritative text and RU/EN edition."""

    article_or_clause: str
    uzbek_authoritative_excerpt: str
    compared_language: Language
    compared_excerpt: str
    severity: RiskSeverity
    legal_impact: str


class TranslationCompareResponse(BaseModel):
    """Result of official-terminology translation & cross-lingual discrepancy audit."""

    translated_text: str
    source_language: Language
    target_language: Language
    doc_id: str | None = None
    urls_compared: dict[str, str] = Field(default_factory=dict)
    discrepancies: list[DiscrepancyItem] = Field(default_factory=list)
    legal_note: str = (
        "Under the Law of the Republic of Uzbekistan 'On Normative-Legal Acts' (O'RQ-682), "
        "the official state-language (Uzbek) text is authoritative in case of divergence."
    )


class TemporalLookupRequest(BaseModel):
    """Request to compare what a legal norm provided on a historical date vs. today."""

    query: str
    historical_date: date
    comparison_date: date | None = None
    response_language: Language | None = None


class TemporalLookupResponse(BaseModel):
    """Comparison of historical vs. current legal regime."""

    query: str
    historical_date: date
    comparison_date: date
    historical_regime_summary: str
    current_regime_summary: str
    key_changes: list[str]
    historical_citations: list[Citation] = Field(default_factory=list)
    current_citations: list[Citation] = Field(default_factory=list)
    verification: VerificationReport
