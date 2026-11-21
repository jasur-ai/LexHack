"""Strict Pydantic models for Red-Team Legal Auditing, 0-100 Scoring, Error Taxonomy, and Regression Tracking."""

from __future__ import annotations

from datetime import date, datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class AdversarialCategory(str, Enum):
    """7 mandatory complex red-team evaluation categories for Uzbekistan legislation."""

    DIRECT_NORM_PRECISION = "DIRECT_NORM_PRECISION"
    MULTI_HOP_CHAIN = "MULTI_HOP_CHAIN"
    NORM_CONFLICT_HIERARCHY = "NORM_CONFLICT_HIERARCHY"
    TEMPORAL_REPEAL_TRAP = "TEMPORAL_REPEAL_TRAP"
    CROSS_LINGUAL_DRIFT_TRAP = "CROSS_LINGUAL_DRIFT_TRAP"
    FABRICATED_CITATION_TRAP = "FABRICATED_CITATION_TRAP"
    COMPLEX_PRACTICAL_CASE = "COMPLEX_PRACTICAL_CASE"


class ErrorCode(str, Enum):
    """Mandatory 8-code legal audit failure taxonomy."""

    FABRICATED_CITATION = "FABRICATED_CITATION"
    REPEALED_OR_OUTDATED_NORM = "REPEALED_OR_OUTDATED_NORM"
    MISSED_EXCEPTION_OR_CONDITION = "MISSED_EXCEPTION_OR_CONDITION"
    HIERARCHY_OR_CONFLICT_ERROR = "HIERARCHY_OR_CONFLICT_ERROR"
    TRANSLATION_OR_TERM_DRIFT = "TRANSLATION_OR_TERM_DRIFT"
    INCOMPLETE_MULTI_HOP = "INCOMPLETE_MULTI_HOP"
    FALSE_PREMISE_COMPLIANCE = "FALSE_PREMISE_COMPLIANCE"
    UNGROUNDED_CLAIM = "UNGROUNDED_CLAIM"


class AuditVerdict(str, Enum):
    PASS = "PASS"
    PARTIAL = "PARTIAL"
    FAIL = "FAIL"


class AuditLanguage(str, Enum):
    UZ_LATN = "uz_latn"
    UZ_CYRL = "uz_cyrl"
    RU = "ru"
    EN = "en"


class ClaimVerificationStatus(str, Enum):
    VERIFIED = "VERIFIED"
    FABRICATED = "FABRICATED"
    REPEALED_OR_OUTDATED = "REPEALED_OR_OUTDATED"
    MISQUOTED_OR_DRIFT = "MISQUOTED_OR_DRIFT"
    UNVERIFIED = "UNVERIFIED"


class RootCauseComponent(str, Enum):
    """Exact subsystem inside `agent/` diagnosed as root cause of a failure."""

    CHUNKING_METADATA = "agent/ingestion/parser.py (Chunking & Metadata)"
    RETRIEVAL_HYBRID = "agent/retrieval/ (BM25 / Dense Hybrid Recall)"
    MULTI_HOP_TRAVERSAL = "agent/reasoning/cross_ref.py & orchestrator.py (Multi-Hop Chain)"
    NORM_HIERARCHY_RESOLVER = "agent/reasoning/norm_resolver.py (Hierarchy & Temporal Filter)"
    CITATION_GROUNDING_GUARD = "agent/reasoning/citation_guard.py & System Prompt (Refusal/Grounding)"
    CROSS_LINGUAL_ALIGNMENT = "agent/language/ (UZ/RU/EN Translation & Terminology)"
    TARGET_UNAVAILABLE = "Target Agent Runtime / Timeout"


class AdversarialTestCase(BaseModel):
    """A single adversarial probe or trap crafted to interrogate the target legal agent."""

    case_id: str
    category: AdversarialCategory
    language: AuditLanguage = AuditLanguage.UZ_LATN
    legal_branch: str = "general"
    difficulty: str = Field(default="hard", description="medium | hard | extreme")
    question: str
    as_of_date: date | None = None
    trap_intent: str = Field(default="", description="What specific weakness or trap this probe targets")
    is_false_premise: bool = Field(default=False, description="True for fabricated citation / hoax traps")
    expected_doc_ids: list[str] = Field(default_factory=list)
    expected_articles: list[str] = Field(default_factory=list)
    expected_key_facts: list[str] = Field(default_factory=list)
    forbidden_claims: list[str] = Field(default_factory=list)
    gold_reference_summary: str = ""
    source: str = Field(default="curated_trap_bank", description="curated_trap_bank | llm_generated | manual | regression")


class ExtractedClaim(BaseModel):
    """Single atomic legal claim or citation parsed from the Target Agent's response."""

    claim_id: str
    claim_text: str
    cited_doc_id: str | None = None
    cited_doc_number: str | None = None
    cited_doc_title: str | None = None
    cited_article: str | None = None
    cited_url: str | None = None
    claimed_status: str | None = None


class ClaimVerificationResult(BaseModel):
    """Independent zero-trust verification outcome for one extracted claim/citation."""

    claim: ExtractedClaim
    status: ClaimVerificationStatus
    independent_source_url: str | None = None
    independent_doc_title: str | None = None
    independent_norm_status: str = "unknown"
    independent_excerpt: str = ""
    alignment_score: float = Field(default=0.0, ge=0.0, le=1.0)
    auditor_note: str = ""


class ScoreBreakdown(BaseModel):
    """Strict 0-100 multi-criteria legal audit rubric (25 + 25 + 25 + 15 + 10)."""

    citation_exactness: int = Field(..., ge=0, le=25)
    legal_validity_currency: int = Field(..., ge=0, le=25)
    reasoning_completeness: int = Field(..., ge=0, le=25)
    cross_lingual_accuracy: int = Field(..., ge=0, le=15)
    anti_hallucination_calibration: int = Field(..., ge=0, le=10)

    @property
    def total(self) -> int:
        return (
            self.citation_exactness
            + self.legal_validity_currency
            + self.reasoning_completeness
            + self.cross_lingual_accuracy
            + self.anti_hallucination_calibration
        )


class RootCauseDiagnosis(BaseModel):
    """Actionable engineering diagnosis pointing to the exact module in `agent/` to fix."""

    component: RootCauseComponent
    severity: str = Field(default="high", description="critical | high | medium | low")
    explanation: str
    recommended_fix: str


class TargetAgentObservation(BaseModel):
    """Raw interrogation response captured from `agent/`."""

    target_url: str
    answer_text: str
    reported_citations: list[dict[str, Any]] = Field(default_factory=list)
    reported_confidence: float | None = None
    reported_verified: bool | None = None
    latency_ms: int = 0
    error: str | None = None


class AuditRecord(BaseModel):
    """Complete zero-trust audit dossier for one interrogated test case."""

    audit_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    run_mode: str = Field(default="single", description="single | batch | regression")
    test_case: AdversarialTestCase
    target_observation: TargetAgentObservation
    extracted_claims: list[ExtractedClaim] = Field(default_factory=list)
    verifications: list[ClaimVerificationResult] = Field(default_factory=list)
    flagged_sentences: list[str] = Field(
        default_factory=list,
        description="Suspicious or erroneous sentences in the target answer highlighted in UI Diff Inspector",
    )
    score: ScoreBreakdown
    total_score: int = Field(..., ge=0, le=100)
    verdict: AuditVerdict
    error_codes: list[ErrorCode] = Field(default_factory=list)
    auditor_critique: str = ""
    benchmark_re_answer: str = ""
    root_causes: list[RootCauseDiagnosis] = Field(default_factory=list)
    saved_to_golden_failures: bool = False


class SingleAuditRequest(BaseModel):
    """Run a zero-trust audit on a manual question or pre-generated trap case."""

    question: str = Field(..., min_length=3)
    category: AdversarialCategory = AdversarialCategory.DIRECT_NORM_PRECISION
    language: AuditLanguage | None = None
    legal_branch: str = "general"
    as_of_date: date | None = None
    trap_intent: str = ""
    is_false_premise: bool = False
    expected_doc_ids: list[str] = Field(default_factory=list)
    expected_articles: list[str] = Field(default_factory=list)
    expected_key_facts: list[str] = Field(default_factory=list)
    forbidden_claims: list[str] = Field(default_factory=list)
    gold_reference_summary: str = ""
    target_agent_url: str | None = None
    target_timeout: float | None = None


class GenerateTrapRequest(BaseModel):
    """Generate a fresh adversarial trap question."""

    category: AdversarialCategory | None = None
    language: AuditLanguage | None = None
    legal_branch: str | None = None
    use_llm: bool = True


class BatchAuditRequest(BaseModel):
    """Run a multi-case adversarial audit suite against the target agent."""

    count: int = Field(default=10, ge=1, le=150)
    categories: list[AdversarialCategory] | None = None
    languages: list[AuditLanguage] | None = None
    use_llm_generation: bool = True
    target_agent_url: str | None = None
    target_timeout: float | None = None


class TargetConfigUpdate(BaseModel):
    """Live runtime update of target endpoint and timeout from UI."""

    target_agent_url: str
    target_agent_timeout: float = Field(default=90.0, ge=5.0, le=300.0)


class AuditAnalytics(BaseModel):
    """Aggregated Red-Team dashboard metrics & branch weak-spot heatmap."""

    total_audited: int = 0
    pass_count: int = 0
    partial_count: int = 0
    fail_count: int = 0
    pass_rate_pct: float = 0.0
    average_score: float = 0.0
    golden_failures_count: int = 0
    error_code_counts: dict[str, int] = Field(default_factory=dict)
    category_avg_scores: dict[str, float] = Field(default_factory=dict)
    branch_heatmap: list[dict[str, Any]] = Field(default_factory=list)
    language_avg_scores: dict[str, float] = Field(default_factory=dict)
