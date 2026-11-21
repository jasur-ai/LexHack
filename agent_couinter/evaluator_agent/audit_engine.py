"""End-to-end Zero-Trust Red-Team Audit Engine: Single, Batch Suite (with Stop/Pause), and Regression Re-Run."""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator
from typing import Any

from evaluator_agent.claim_parser import parse_claims_and_citations
from evaluator_agent.config import AuditorSettings, get_settings
from evaluator_agent.independent_verifier import IndependentLexVerifier
from evaluator_agent.llm_client import AuditorLLMClient
from evaluator_agent.models import (
    AdversarialTestCase,
    AuditLanguage,
    AuditRecord,
    BatchAuditRequest,
    SingleAuditRequest,
)
from evaluator_agent.regression import RegressionAndAuditStore
from evaluator_agent.scorer import LegalAuditScorer
from evaluator_agent.target_client import TargetAgentClient
from evaluator_agent.trap_engine import AdversarialTrapEngine


def _detect_lang_simple(text: str) -> AuditLanguage:
    cyr = sum(1 for c in text if "\u0400" <= c <= "\u04ff")
    lat = sum(1 for c in text if ("a" <= c.lower() <= "z"))
    if cyr >= lat and cyr > 0:
        if any(c in "ўқғҳЎҚҒҲ" for c in text):
            return AuditLanguage.UZ_CYRL
        return AuditLanguage.RU
    low = text.lower()
    if any(k in low for k in ("modda", "kodeks", "qonun", "qancha", "qanday", "o'zbekiston", "shartnoma")):
        return AuditLanguage.UZ_LATN
    return AuditLanguage.EN


class RedTeamAuditEngine:
    """Orchestrates live adversarial interrogation, independent Lex.uz verification, scoring, and regression runs."""

    def __init__(self, settings: AuditorSettings | None = None) -> None:
        self.settings = settings or get_settings()
        self.llm = AuditorLLMClient(self.settings)
        self.target = TargetAgentClient(self.settings)
        self.traps = AdversarialTrapEngine(self.llm)
        self.verifier = IndependentLexVerifier(self.settings)
        self.scorer = LegalAuditScorer(self.llm)
        self.store = RegressionAndAuditStore(self.settings)

        # Shared cooperative cancellation/pause flags for active batch & regression runs
        self._stop_requested = False
        self._pause_requested = False

    def request_stop(self) -> None:
        self._stop_requested = True

    def request_pause(self, paused: bool) -> None:
        self._pause_requested = paused

    async def close(self) -> None:
        await self.llm.close()
        await self.target.close()
        await self.verifier.close()

    async def audit_test_case_stream(
        self,
        test_case: AdversarialTestCase,
        *,
        run_mode: str = "single",
        override_url: str | None = None,
        override_timeout: float | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """Execute full zero-trust interrogation & verification pipeline, emitting real-time Auditor phase events."""
        yield {
            "type": "phase",
            "phase": "INTERROGATING",
            "detail": f"Probing Target Agent with [{test_case.category.value}] ({test_case.language.value})...",
            "case_id": test_case.case_id,
        }
        observation = await self.target.interrogate(
            test_case.question,
            language=test_case.language,
            as_of_date=test_case.as_of_date,
            override_url=override_url,
            override_timeout=override_timeout,
        )

        yield {
            "type": "phase",
            "phase": "SCANNING",
            "detail": f"Parsing atomic claims & citations ({observation.latency_ms}ms target latency)...",
            "case_id": test_case.case_id,
        }
        extracted_claims = parse_claims_and_citations(
            observation.answer_text,
            observation.reported_citations,
        )

        yield {
            "type": "phase",
            "phase": "CROSS-CHECKING LEX.UZ",
            "detail": f"Independently verifying {len(extracted_claims)} extracted claim(s) against Lex.uz & local corpus...",
            "case_id": test_case.case_id,
        }
        verifications = await asyncio.gather(*[self.verifier.verify_claim(c) for c in extracted_claims])

        yield {
            "type": "phase",
            "phase": "SCORING",
            "detail": "Running 0-100 forensic rubric, error taxonomy classification & root-cause diagnosis...",
            "case_id": test_case.case_id,
        }
        eval_res = await self.scorer.evaluate(test_case, observation, list(verifications))

        record = AuditRecord(
            audit_id=f"AUD-{uuid.uuid4().hex[:8].upper()}",
            run_mode=run_mode,
            test_case=test_case,
            target_observation=observation,
            extracted_claims=extracted_claims,
            verifications=list(verifications),
            flagged_sentences=eval_res["flagged_sentences"],
            score=eval_res["score"],
            total_score=eval_res["score"].total,
            verdict=eval_res["verdict"],
            error_codes=eval_res["error_codes"],
            auditor_critique=eval_res["auditor_critique"],
            benchmark_re_answer=eval_res["benchmark_re_answer"],
            root_causes=eval_res["root_causes"],
        )
        record = self.store.save_audit_record(record)

        yield {
            "type": "verdict",
            "phase": "VERDICT READY",
            "record": record.model_dump(mode="json"),
        }

    async def audit_single(self, req: SingleAuditRequest) -> AuditRecord:
        tc = self._request_to_test_case(req)
        final_dict: dict[str, Any] | None = None
        async for ev in self.audit_test_case_stream(
            tc,
            run_mode="single",
            override_url=req.target_agent_url,
            override_timeout=req.target_timeout,
        ):
            if ev.get("type") == "verdict":
                final_dict = ev["record"]
        assert final_dict is not None
        return AuditRecord.model_validate(final_dict)

    async def audit_single_stream(self, req: SingleAuditRequest) -> AsyncIterator[dict[str, Any]]:
        tc = self._request_to_test_case(req)
        async for ev in self.audit_test_case_stream(
            tc,
            run_mode="single",
            override_url=req.target_agent_url,
            override_timeout=req.target_timeout,
        ):
            yield ev

    async def run_batch_stream(self, req: BatchAuditRequest) -> AsyncIterator[dict[str, Any]]:
        """Run an N-case Red-Team Batch Suite with cooperative Pause/Stop controls and live SSE progress."""
        self._stop_requested = False
        self._pause_requested = False

        yield {"type": "phase", "phase": "SCANNING", "detail": f"Assembling {req.count}-case adversarial suite..."}
        suite = await self.traps.build_batch_suite(
            count=req.count,
            categories=req.categories,
            languages=req.languages,
            use_llm_generation=req.use_llm_generation,
        )
        total = len(suite)
        yield {"type": "batch_start", "total": total}

        completed = 0
        for idx, tc in enumerate(suite, start=1):
            while self._pause_requested and not self._stop_requested:
                yield {"type": "phase", "phase": "PAUSED", "detail": f"Batch paused at {idx - 1}/{total}..."}
                await asyncio.sleep(0.5)
            if self._stop_requested:
                yield {"type": "batch_stopped", "completed": completed, "total": total}
                return

            yield {"type": "batch_progress", "index": idx, "total": total, "question": tc.question, "category": tc.category.value}
            async for ev in self.audit_test_case_stream(
                tc,
                run_mode="batch",
                override_url=req.target_agent_url,
                override_timeout=req.target_timeout,
            ):
                yield ev
            completed += 1

        analytics = self.store.compute_analytics()
        yield {"type": "batch_done", "completed": completed, "total": total, "analytics": analytics.model_dump(mode="json")}

    async def run_regression_stream(
        self,
        *,
        override_url: str | None = None,
        override_timeout: float | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """Re-run ONLY previously failed cases recorded in `golden_failures.jsonl`."""
        self._stop_requested = False
        self._pause_requested = False

        cases = self.store.load_regression_test_cases()
        if not cases:
            yield {"type": "error", "detail": "golden_failures.jsonl bo'sh — avval audit o'tkazing."}
            return

        total = len(cases)
        yield {"type": "batch_start", "total": total, "mode": "regression"}
        fixed = 0
        still_failing = 0

        for idx, tc in enumerate(cases, start=1):
            while self._pause_requested and not self._stop_requested:
                await asyncio.sleep(0.5)
            if self._stop_requested:
                yield {"type": "batch_stopped", "completed": idx - 1, "total": total}
                return

            yield {"type": "batch_progress", "index": idx, "total": total, "question": tc.question, "category": tc.category.value}
            async for ev in self.audit_test_case_stream(
                tc,
                run_mode="regression",
                override_url=override_url,
                override_timeout=override_timeout,
            ):
                if ev.get("type") == "verdict":
                    if ev["record"].get("verdict") == "PASS":
                        fixed += 1
                    else:
                        still_failing += 1
                yield ev

        analytics = self.store.compute_analytics()
        yield {
            "type": "batch_done",
            "mode": "regression",
            "completed": fixed + still_failing,
            "total": total,
            "fixed": fixed,
            "still_failing": still_failing,
            "analytics": analytics.model_dump(mode="json"),
        }

    def _request_to_test_case(self, req: SingleAuditRequest) -> AdversarialTestCase:
        lang = req.language or _detect_lang_simple(req.question)
        inferred = self.verifier.knowledge.infer_ground_truth_for_question(req.question)

        exp_docs = req.expected_doc_ids or inferred.get("expected_doc_ids", [])
        exp_arts = req.expected_articles or inferred.get("expected_articles", [])
        exp_facts = req.expected_key_facts or inferred.get("expected_key_facts", [])
        forb_claims = req.forbidden_claims or inferred.get("forbidden_claims", [])
        gold_sum = req.gold_reference_summary or inferred.get("gold_reference_summary", "")
        is_fp = req.is_false_premise or bool(inferred.get("is_false_premise")) or (req.category.value == "FABRICATED_CITATION_TRAP")
        cat = AdversarialCategory.FABRICATED_CITATION_TRAP if is_fp else req.category

        return AdversarialTestCase(
            case_id=f"man_{uuid.uuid4().hex[:8]}",
            category=cat,
            language=lang,
            legal_branch=req.legal_branch,
            difficulty="manual",
            question=req.question.strip(),
            as_of_date=req.as_of_date,
            trap_intent=req.trap_intent or f"Zero-trust statutory audit ({cat.value})",
            is_false_premise=is_fp,
            expected_doc_ids=exp_docs,
            expected_articles=exp_arts,
            expected_key_facts=exp_facts,
            forbidden_claims=forb_claims,
            gold_reference_summary=gold_sum,
            source="manual",
        )
