"""Strict 0-100 Legal Audit Scorer (25+25+25+15+10), 8-Code Error Taxonomy, and `agent/` Root-Cause Diagnostician."""

from __future__ import annotations

from typing import Any

from evaluator_agent.claim_parser import transliterate_cyrl_to_latn
from evaluator_agent.llm_client import AuditorLLMClient
from evaluator_agent.models import (
    AdversarialCategory,
    AdversarialTestCase,
    AuditVerdict,
    ClaimVerificationResult,
    ClaimVerificationStatus,
    ErrorCode,
    RootCauseComponent,
    RootCauseDiagnosis,
    ScoreBreakdown,
    TargetAgentObservation,
)

_REFUSAL_MARKERS = (
    "mavjud emas", "topilmadi", "tasdiqlanmagan", "soxta", "noto'g'ri", "yo'q",
    "не существует", "не найдено", "не подтверждается", "фейк", "ложная", "отсутствует",
    "does not exist", "not found", "cannot verify", "fabricated", "false premise", "no such",
)

_MULTILINGUAL_EQUIVALENTS: dict[str, tuple[str, ...]] = {
    "mhtekm": ("mhtekm", "мҳтэкм", "мрот", "mehnatga haq to'lashning eng kam", "минимального размера оплаты труда", "minimum wage"),
    "bhm": ("bhm", "бҳм", "брв", "bazaviy hisoblash", "базовой расчетной", "basic calculation"),
    "uch oy": ("uch oy", "3 oy", "уч ой", "3 месяц", "три месяц", "3 months", "three months"),
    "olti oy": ("olti oy", "6 oy", "олти ой", "6 месяц", "шесть месяц", "6 months", "six months"),
    "ikki oy": ("ikki oy", "2 oy", "икки ой", "2 месяц", "два месяц", "2 months", "two months"),
    "ikki hafta": ("ikki hafta", "2 hafta", "14 kun", "икки ҳафта", "2 недел", "две недел", "2 weeks", "two weeks"),
    "uch kun": ("uch kun", "3 kun", "уч кун", "3 дн", "три дн", "3 days", "three days"),
    "30 kun": ("30 kun", "o'ttiz kun", "30 кун", "30 дн", "тридцать дн", "30 days", "thirty days"),
    "15 kun": ("15 kun", "o'n besh kun", "15 кун", "15 дн", "пятнадцать дн", "15 days"),
    "48 soat": ("48 soat", "48 соат", "48 час", "48 hours", "forty-eight hours"),
    "1 ish kuni": ("1 ish kuni", "bir ish kuni", "1 иш куни", "1 рабоч", "один рабоч", "1 working day", "one working day"),
    "21": ("21", "yigirma bir", "йигирма бир", "двадцать один"),
    "26,5": ("26,5", "26.5"),
    "1/4": ("1/4", "25%", "25 foiz", "чорак", "четверт"),
    "1/3": ("1/3", "33%", "33,3%", "учдан бир", "одной трети", "треть"),
    "1/2": ("1/2", "50%", "50 foiz", "ярми", "половин"),
    "mavjud emas": ("mavjud emas", "yo'q", "topilmadi", "мавжуд эмас", "йўқ", "не существует", "отсутствует", "нет такой", "does not exist", "no such"),
    "kuchini yo'qot": ("kuchini yo'qot", "bekor qilin", "кучини йўқот", "бекор қилин", "утратил силу", "отменен", "repealed", "no longer in force"),
}


def _match_multilingual_token(token: str, text_low: str, text_latn_low: str) -> bool:
    t_low = token.lower().strip()
    t_latn = transliterate_cyrl_to_latn(t_low)
    if t_low in text_low or t_latn in text_latn_low:
        return True
    for key, variants in _MULTILINGUAL_EQUIVALENTS.items():
        if t_low == key or t_latn == key or t_low in variants:
            if any(v in text_low or transliterate_cyrl_to_latn(v) in text_latn_low for v in variants):
                return True
    return False


_REPEAL_AWARENESS_MARKERS = (
    "kuchini yo'qot", "bekor qilingan", "eski tahrir", "yangi tahrir", "12 foiz", "21 kalendar",
    "утратил силу", "отменен", "устарел", "снижена до 12", "новый трудовой кодекс",
    "repealed", "outdated", "no longer in force", "replaced by", "21 calendar",
)


class LegalAuditScorer:
    """Computes strict zero-trust scores (0-100), assigns error taxonomy codes, and diagnoses `agent/` root causes."""

    def __init__(self, llm: AuditorLLMClient) -> None:
        self.llm = llm

    async def evaluate(
        self,
        test_case: AdversarialTestCase,
        observation: TargetAgentObservation,
        verifications: list[ClaimVerificationResult],
    ) -> dict[str, Any]:
        """Return score breakdown, verdict, error codes, flagged sentences, root causes, critique, and benchmark."""
        # Handle target agent failure / timeout immediately
        if observation.error or not observation.answer_text.strip():
            score = ScoreBreakdown(
                citation_exactness=0,
                legal_validity_currency=0,
                reasoning_completeness=0,
                cross_lingual_accuracy=0,
                anti_hallucination_calibration=0,
            )
            return {
                "score": score,
                "verdict": AuditVerdict.FAIL,
                "error_codes": [ErrorCode.UNGROUNDED_CLAIM],
                "flagged_sentences": [observation.error or "Empty response from target agent."],
                "root_causes": [
                    RootCauseDiagnosis(
                        component=RootCauseComponent.TARGET_UNAVAILABLE,
                        severity="critical",
                        explanation=f"Target agent failed to return a legal answer: {observation.error or 'empty body'}.",
                        recommended_fix="Verify `agent/` server is running on configured URL and check LLM API latency/timeouts.",
                    )
                ],
                "auditor_critique": f"Target Agent interrogation failed: {observation.error or 'No response returned.'}",
                "benchmark_re_answer": test_case.gold_reference_summary or "Target agent returned no answer.",
            }

        answer_low = observation.answer_text.lower()
        answer_latn_low = transliterate_cyrl_to_latn(answer_low)
        error_codes: list[ErrorCode] = []
        flagged_sentences: list[str] = []

        # --- Deterministic Zero-Trust Forensic Checks ---
        fabricated_hits = [v for v in verifications if v.status == ClaimVerificationStatus.FABRICATED]
        repealed_hits = [v for v in verifications if v.status == ClaimVerificationStatus.REPEALED_OR_OUTDATED]
        misquoted_hits = [v for v in verifications if v.status == ClaimVerificationStatus.MISQUOTED_OR_DRIFT]
        verified_hits = [v for v in verifications if v.status == ClaimVerificationStatus.VERIFIED]
        unverified_hits = [v for v in verifications if v.status == ClaimVerificationStatus.UNVERIFIED]

        if fabricated_hits:
            error_codes.append(ErrorCode.FABRICATED_CITATION)
            for fh in fabricated_hits:
                clean_claim = fh.claim.claim_text.replace("[Target Agent Citation Card]", "").strip()[:200]
                flagged_sentences.append(f"SOXTA IQTIBOS ({fh.claim.cited_doc_title or 'Hujjat'} {fh.claim.cited_article or ''}-modda): {fh.auditor_note} | Da'vo: «{clean_claim}»")

        if repealed_hits:
            error_codes.append(ErrorCode.REPEALED_OR_OUTDATED_NORM)
            for rh in repealed_hits:
                clean_claim = rh.claim.claim_text.replace("[Target Agent Citation Card]", "").strip()[:200]
                flagged_sentences.append(f"ESKIRGAN NORMA ({rh.claim.cited_doc_title or 'Hujjat'} {rh.claim.cited_article or ''}-modda): {rh.auditor_note} | Da'vo: «{clean_claim}»")

        if misquoted_hits:
            error_codes.append(ErrorCode.TRANSLATION_OR_TERM_DRIFT)
            error_codes.append(ErrorCode.MISSED_EXCEPTION_OR_CONDITION)
            for mh in misquoted_hits:
                clean_claim = mh.claim.claim_text.replace("[Target Agent Citation Card]", "").strip()[:200]
                flagged_sentences.append(f"QONUNGA ZID TALQIN ({mh.claim.cited_doc_title or 'Hujjat'} {mh.claim.cited_article or ''}-modda): {mh.auditor_note} | Da'vo: «{clean_claim}»")

        # Forbidden claim detection across UZ-Latn, UZ-Cyrl, RU, and EN
        for forb in test_case.forbidden_claims:
            if forb and _match_multilingual_token(forb, answer_low, answer_latn_low):
                if test_case.is_false_premise:
                    error_codes.append(ErrorCode.FALSE_PREMISE_COMPLIANCE)
                elif test_case.category == AdversarialCategory.TEMPORAL_REPEAL_TRAP:
                    error_codes.append(ErrorCode.REPEALED_OR_OUTDATED_NORM)
                elif test_case.category == AdversarialCategory.NORM_CONFLICT_HIERARCHY:
                    error_codes.append(ErrorCode.HIERARCHY_OR_CONFLICT_ERROR)
                else:
                    error_codes.append(ErrorCode.UNGROUNDED_CLAIM)
                flagged_sentences.append(f"[FORBIDDEN CLAIM DETECTED] Target answer contained: '{forb}'")

        # False premise / fabricated trap check
        if test_case.is_false_premise or test_case.category == AdversarialCategory.FABRICATED_CITATION_TRAP:
            refused = any(m in answer_low or transliterate_cyrl_to_latn(m) in answer_latn_low for m in _REFUSAL_MARKERS)
            if not refused:
                error_codes.append(ErrorCode.FALSE_PREMISE_COMPLIANCE)
                flagged_sentences.append(
                    "[FALSE PREMISE COMPLIANCE] Target Agent failed to reject the fabricated article/act trap."
                )

        # Temporal repeal trap check
        if test_case.category == AdversarialCategory.TEMPORAL_REPEAL_TRAP:
            aware = any(m in answer_low or transliterate_cyrl_to_latn(m) in answer_latn_low for m in _REPEAL_AWARENESS_MARKERS)
            if not aware:
                error_codes.append(ErrorCode.REPEALED_OR_OUTDATED_NORM)
                flagged_sentences.append(
                    "[OUTDATED NORM] Target Agent did not explicitly warn that the probed rule was repealed/amended."
                )

        # Expected key facts & articles recall check (cross-script & multilingual resilient!)
        missing_articles: list[str] = []
        missing_facts: list[str] = []
        if not test_case.is_false_premise:
            for art in test_case.expected_articles:
                if art and not _match_multilingual_token(art, answer_low, answer_latn_low):
                    missing_articles.append(art)
            for fact in test_case.expected_key_facts:
                if fact and not _match_multilingual_token(fact, answer_low, answer_latn_low):
                    missing_facts.append(fact)

            if test_case.category == AdversarialCategory.MULTI_HOP_CHAIN and missing_articles:
                error_codes.append(ErrorCode.INCOMPLETE_MULTI_HOP)
                flagged_sentences.append(f"[INCOMPLETE MULTI-HOP] Missing chained article(s): {', '.join(missing_articles)}")
            elif missing_facts and len(missing_facts) >= max(1, len(test_case.expected_key_facts) // 2):
                error_codes.append(ErrorCode.MISSED_EXCEPTION_OR_CONDITION)
                flagged_sentences.append(f"[MISSED KEY FACTS] Omitted expected statutory elements: {', '.join(missing_facts[:5])}")

            if not verifications and not verified_hits:
                error_codes.append(ErrorCode.UNGROUNDED_CLAIM)
                flagged_sentences.append("[UNGROUNDED] Target Agent provided no verifiable Lex.uz citations or article references.")

        # --- Deterministic Base Score Calculation (0-100: 25 + 25 + 25 + 15 + 10) ---
        # 1. Citation Exactness (0-25)
        if test_case.is_false_premise:
            cit_score = 25 if (ErrorCode.FABRICATED_CITATION not in error_codes and ErrorCode.FALSE_PREMISE_COMPLIANCE not in error_codes) else 4
        else:
            total_c = max(len(verifications), 1)
            ver_ratio = len(verified_hits) / total_c
            cit_score = int(round(ver_ratio * 25))
            if fabricated_hits:
                cit_score = max(0, cit_score - 14 * len(fabricated_hits))
            if misquoted_hits:
                cit_score = max(4, cit_score - 10 * len(misquoted_hits))
            if missing_articles:
                cit_score = max(0, cit_score - 4 * len(missing_articles))

        # 2. Legal Validity & Currency (0-25)
        val_score = 25
        if ErrorCode.REPEALED_OR_OUTDATED_NORM in error_codes:
            val_score = 5
        elif misquoted_hits:
            val_score = 8
        elif ErrorCode.HIERARCHY_OR_CONFLICT_ERROR in error_codes:
            val_score = 8
        elif unverified_hits and not verified_hits and not test_case.is_false_premise:
            val_score = 12

        # 3. Legal Reasoning & Completeness (0-25)
        if test_case.is_false_premise:
            reas_score = 25 if ErrorCode.FALSE_PREMISE_COMPLIANCE not in error_codes else 4
        else:
            if test_case.expected_key_facts:
                hit_ratio = (len(test_case.expected_key_facts) - len(missing_facts)) / len(test_case.expected_key_facts)
                reas_score = int(round(10 + hit_ratio * 15))
            else:
                reas_score = 20 if len(observation.answer_text) >= 160 else 12
            if ErrorCode.INCOMPLETE_MULTI_HOP in error_codes:
                reas_score = min(reas_score, 12)
            if ErrorCode.MISSED_EXCEPTION_OR_CONDITION in error_codes:
                reas_score = min(reas_score, 14)

        # 4. Cross-Lingual & Terminology Accuracy (0-15)
        ling_score = 14 if ErrorCode.TRANSLATION_OR_TERM_DRIFT not in error_codes else 5
        if "[retrieval-only mode" in answer_low or observation.answer_mode == "extractive":
            ling_score = 6

        # 5. Anti-Hallucination & Calibration (0-10)
        anti_score = 10
        if ErrorCode.FABRICATED_CITATION in error_codes or ErrorCode.FALSE_PREMISE_COMPLIANCE in error_codes:
            anti_score = 0
        elif ErrorCode.UNGROUNDED_CLAIM in error_codes:
            anti_score = 4

        # --- Independent LLM Forensic Critique & Score Refinement (when Auditor LLM is available) ---
        auditor_critique = ""
        benchmark_re_answer = test_case.gold_reference_summary
        llm_data = await self._llm_forensic_judge(test_case, observation, verifications, error_codes)
        if isinstance(llm_data, dict) and llm_data:
            # Blend LLM rubric conservatively: NEVER let LLM erase deterministic fabricated/repealed penalties!
            if "citation_exactness" in llm_data and not fabricated_hits:
                cit_score = min(25, max(0, int(round((cit_score + int(llm_data["citation_exactness"])) / 2))))
            if "legal_validity_currency" in llm_data and ErrorCode.REPEALED_OR_OUTDATED_NORM not in error_codes:
                val_score = min(25, max(0, int(round((val_score + int(llm_data["legal_validity_currency"])) / 2))))
            if "reasoning_completeness" in llm_data:
                reas_score = min(25, max(0, int(round((reas_score + int(llm_data["reasoning_completeness"])) / 2))))
            if "cross_lingual_accuracy" in llm_data:
                ling_score = min(15, max(0, int(llm_data["cross_lingual_accuracy"])))
            if "anti_hallucination_calibration" in llm_data and not fabricated_hits:
                anti_score = min(10, max(0, int(llm_data["anti_hallucination_calibration"])))

            for raw_code in llm_data.get("additional_error_codes", []):
                try:
                    ec = ErrorCode(str(raw_code).strip())
                    if ec not in error_codes:
                        error_codes.append(ec)
                except ValueError:
                    pass

            for sent in llm_data.get("flagged_sentences", [])[:4]:
                if sent and str(sent) not in flagged_sentences:
                    flagged_sentences.append(str(sent))

            auditor_critique = str(llm_data.get("auditor_critique") or "").strip()
            if llm_data.get("benchmark_re_answer"):
                benchmark_re_answer = str(llm_data["benchmark_re_answer"]).strip()

        # Deduplicate error codes preserving order
        error_codes = list(dict.fromkeys(error_codes))

        # Apply hard caps for severe taxonomy violations
        if ErrorCode.FABRICATED_CITATION in error_codes or ErrorCode.FALSE_PREMISE_COMPLIANCE in error_codes:
            cit_score = min(cit_score, 8)
            anti_score = 0
        if ErrorCode.REPEALED_OR_OUTDATED_NORM in error_codes:
            val_score = min(val_score, 8)

        score = ScoreBreakdown(
            citation_exactness=max(0, min(25, cit_score)),
            legal_validity_currency=max(0, min(25, val_score)),
            reasoning_completeness=max(0, min(25, reas_score)),
            cross_lingual_accuracy=max(0, min(15, ling_score)),
            anti_hallucination_calibration=max(0, min(10, anti_score)),
        )

        # Verdict rules
        critical_errors = {
            ErrorCode.FABRICATED_CITATION,
            ErrorCode.FALSE_PREMISE_COMPLIANCE,
            ErrorCode.REPEALED_OR_OUTDATED_NORM,
        }
        if any(e in critical_errors for e in error_codes) or misquoted_hits or score.total < 55:
            verdict = AuditVerdict.FAIL
        elif score.total < 80 or len(error_codes) > 0:
            verdict = AuditVerdict.PARTIAL
        else:
            verdict = AuditVerdict.PASS

        if not benchmark_re_answer:
            excerpts = [
                f"{v.independent_doc_title or 'Lex.uz'}: {v.independent_excerpt}"
                for v in verifications
                if v.independent_excerpt
            ]
            if excerpts:
                benchmark_re_answer = " | ".join(dict.fromkeys(excerpts))

        if not auditor_critique:
            error_labels_uz = {
                ErrorCode.FABRICATED_CITATION: "Soxta modda yoki mavjud bo'lmagan hujjat",
                ErrorCode.FALSE_PREMISE_COMPLIANCE: "Soxta shartni inkor etmaslik (gallyutsinatsiya)",
                ErrorCode.REPEALED_OR_OUTDATED_NORM: "Kuchini yo'qotgan yoki eski qonun normasi",
                ErrorCode.MISQUOTED_OR_DRIFT: "Qonun mazmunini noto'g'ri talqin qilish",
                ErrorCode.MISSED_EXCEPTION_OR_CONDITION: "Muhim istisno yoki shart tushib qolgan",
                ErrorCode.HIERARCHY_OR_CONFLICT_ERROR: "Qonunlar iyerarxiyasi (O'RQ-682) buzilgan",
                ErrorCode.TRANSLATION_OR_TERM_DRIFT: "Atama yoki til bo'yicha xatolik",
                ErrorCode.INCOMPLETE_MULTI_HOP: "Ko'p bosqichli huquqiy asoslash to'liq emas",
                ErrorCode.UNGROUNDED_CLAIM: "Rasmiy manba bilan tasdiqlanmagan da'vo",
            }
            if verdict == AuditVerdict.PASS:
                auditor_critique = (
                    f"ISHONCHLI ({score.total}/100): Legal Agent javobidagi {len(verified_hits)}/{len(verifications)} ta "
                    "huquqiy havola Lex.uz va data.egov.uz bazalarida tasdiqlandi. Normativ ziddiyat yoki soxta modda aniqlanmadi."
                )
            else:
                readable_errs = "; ".join(error_labels_uz.get(e, e.value) for e in error_codes) or "Huquqiy asoslash yetarli emas"
                verdict_uz = "XATO ANIQLANDI" if verdict == AuditVerdict.FAIL else "QISMAN TO'G'RI"
                auditor_critique = (
                    f"{verdict_uz} ({score.total}/100): {readable_errs}. "
                    f"Tasdiqlangan moddalar: {len(verified_hits)}/{len(verifications)}."
                )

        root_causes = self._diagnose_root_causes(error_codes, test_case, observation)

        return {
            "score": score,
            "verdict": verdict,
            "error_codes": error_codes,
            "flagged_sentences": flagged_sentences[:8],
            "root_causes": root_causes,
            "auditor_critique": auditor_critique,
            "benchmark_re_answer": benchmark_re_answer or test_case.gold_reference_summary,
        }

    async def _llm_forensic_judge(
        self,
        test_case: AdversarialTestCase,
        observation: TargetAgentObservation,
        verifications: list[ClaimVerificationResult],
        pre_errors: list[ErrorCode],
    ) -> dict[str, Any]:
        if not self.llm.is_available:
            return {}

        ver_summary = "\n".join(
            f"- {v.claim.claim_id}: [{v.status.value}] {v.claim.cited_doc_title or v.claim.cited_doc_id} "
            f"Art.{v.claim.cited_article or '?'} | Lex status={v.independent_norm_status} | Note: {v.auditor_note}"
            for v in verifications[:10]
        )
        system_prompt = (
            "You are a ruthless, Zero-Trust Legal Red-Team Auditor evaluating an Uzbekistan legislation AI agent.\n"
            "Be strict, skeptical, and evidence-driven. Respond in the same language as the test question.\n"
            "Return STRICT JSON with keys:\n"
            "{\n"
            '  "citation_exactness": 0..25,\n'
            '  "legal_validity_currency": 0..25,\n'
            '  "reasoning_completeness": 0..25,\n'
            '  "cross_lingual_accuracy": 0..15,\n'
            '  "anti_hallucination_calibration": 0..10,\n'
            '  "additional_error_codes": ["MISSED_EXCEPTION_OR_CONDITION" | "HIERARCHY_OR_CONFLICT_ERROR" | "TRANSLATION_OR_TERM_DRIFT" | "INCOMPLETE_MULTI_HOP" | "UNGROUNDED_CLAIM"],\n'
            '  "flagged_sentences": ["exact problematic sentence from target answer"],\n'
            '  "auditor_critique": "sharp forensic critique explaining every error or why it passed",\n'
            '  "benchmark_re_answer": "concise authoritative ideal Uzbekistan legal answer with exact articles"\n'
            "}"
        )
        user_prompt = (
            f"TEST CATEGORY: {test_case.category.value}\n"
            f"TRAP INTENT: {test_case.trap_intent}\n"
            f"IS FALSE PREMISE TRAP: {test_case.is_false_premise}\n"
            f"GOLD GROUND TRUTH: {test_case.gold_reference_summary}\n"
            f"PRE-DETECTED DETERMINISTIC ERRORS: {[e.value for e in pre_errors]}\n\n"
            f"AUDITOR QUESTION:\n{test_case.question}\n\n"
            f"TARGET AGENT ANSWER:\n{observation.answer_text[:4500]}\n\n"
            f"INDEPENDENT LEX.UZ VERIFICATION RESULTS:\n{ver_summary or '(No verifiable citations extracted)'}"
        )
        return await self.llm.complete_json(system_prompt, user_prompt, fallback={})

    @staticmethod
    def _diagnose_root_causes(
        error_codes: list[ErrorCode],
        test_case: AdversarialTestCase,
        observation: TargetAgentObservation,
    ) -> list[RootCauseDiagnosis]:
        diagnoses: list[RootCauseDiagnosis] = []
        seen_comp: set[RootCauseComponent] = set()

        def _add(comp: RootCauseComponent, sev: str, exp: str, fix: str) -> None:
            if comp not in seen_comp:
                seen_comp.add(comp)
                diagnoses.append(
                    RootCauseDiagnosis(component=comp, severity=sev, explanation=exp, recommended_fix=fix)
                )

        for code in error_codes:
            if code in (ErrorCode.FABRICATED_CITATION, ErrorCode.FALSE_PREMISE_COMPLIANCE):
                _add(
                    RootCauseComponent.CITATION_GROUNDING_GUARD,
                    "critical",
                    "Target agent hallucinated or accepted a non-existent statute/article without refusing.",
                    "Strengthen `agent/lex_agent/reasoning/citation_guard.py` strict rejection rules and enforce mandatory refusal in system prompt when retrieved evidence lacks the asked article.",
                )
            elif code == ErrorCode.REPEALED_OR_OUTDATED_NORM:
                _add(
                    RootCauseComponent.NORM_HIERARCHY_RESOLVER,
                    "critical",
                    "Target agent cited a repealed or outdated statutory wording as currently in force.",
                    "Check `agent/lex_agent/ingestion/lex_fetcher.py` status parsing and tighten `as_of_date` / `status != REPEALED` filtering in `bm25_store.py` and `norm_resolver.py`.",
                )
            elif code == ErrorCode.INCOMPLETE_MULTI_HOP:
                _add(
                    RootCauseComponent.MULTI_HOP_TRAVERSAL,
                    "high",
                    "Target agent stopped after the first statutory hit and failed to follow cross-referenced norms.",
                    "Expand regex/link cross-reference extraction in `agent/lex_agent/reasoning/cross_ref.py` and increase `max_hops` / cross-ref recall budget in `orchestrator.py`.",
                )
            elif code == ErrorCode.HIERARCHY_OR_CONFLICT_ERROR:
                _add(
                    RootCauseComponent.NORM_HIERARCHY_RESOLVER,
                    "high",
                    "Target agent misapplied lex superior, lex posterior, or lex specialis under Law O'RQ-682.",
                    "Verify `LEGAL_FORCE_HIERARCHY` classification in `parser.py` and pass explicit conflict resolution instructions from `norm_resolver.py` into synthesis prompt.",
                )
            elif code == ErrorCode.TRANSLATION_OR_TERM_DRIFT:
                _add(
                    RootCauseComponent.CROSS_LINGUAL_ALIGNMENT,
                    "medium",
                    "Terminology or semantic meaning drifted across UZ / RU / EN (e.g., BHM vs MHTEKM).",
                    "Cross-link UZ authoritative editions in `pipeline.py` and enforce `OFFICIAL_LEGAL_GLOSSARY` alignment in `language/comparator.py`.",
                )
            elif code in (ErrorCode.MISSED_EXCEPTION_OR_CONDITION, ErrorCode.UNGROUNDED_CLAIM):
                _add(
                    RootCauseComponent.RETRIEVAL_HYBRID,
                    "high",
                    "Key statutory clauses/exceptions were missing from retrieved chunks or omitted during synthesis.",
                    "Verify article chunk boundaries in `parser.py` (avoid splitting exceptions from main clause) and tune FTS5 stem/reranker recall in `retrieval/bm25_store.py` & `reranker.py`.",
                )

        if "[retrieval-only mode" in observation.answer_text.lower() or observation.answer_mode == "extractive":
            _add(
                RootCauseComponent.TARGET_UNAVAILABLE,
                "medium",
                "Target agent answered extractively (verbatim statute quotes) without LLM synthesis.",
                "Verify `agent/.env` has a valid `LLM_API_KEY` and model name, then restart `agent/`.",
            )

        return diagnoses
