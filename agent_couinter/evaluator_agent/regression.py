"""Golden Failures Regression Store (`golden_failures.jsonl`), Audit History, Analytics Heatmap & JSON/MD/CSV Export."""

from __future__ import annotations

import csv
import io
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from evaluator_agent.config import AuditorSettings, get_settings
from evaluator_agent.models import (
    AdversarialTestCase,
    AuditAnalytics,
    AuditRecord,
    AuditVerdict,
)


class RegressionAndAuditStore:
    """Manages persistent `golden_failures.jsonl`, `audit_runs.jsonl`, analytics, and multi-format exports."""

    def __init__(self, settings: AuditorSettings | None = None) -> None:
        self.settings = settings or get_settings()
        self.settings.ensure_directories()

    @property
    def golden_path(self) -> Path:
        return self.settings.golden_failures_path

    @property
    def history_path(self) -> Path:
        return self.settings.audit_history_path

    def save_audit_record(self, record: AuditRecord) -> AuditRecord:
        """Append audit dossier to history and automatically record failures into `golden_failures.jsonl`."""
        if record.verdict in (AuditVerdict.FAIL, AuditVerdict.PARTIAL):
            self._append_golden_failure(record)
            record.saved_to_golden_failures = True

        with self.history_path.open("a", encoding="utf-8") as fh:
            fh.write(record.model_dump_json() + "\n")
        return record

    def _append_golden_failure(self, record: AuditRecord) -> None:
        existing_questions: set[str] = set()
        if self.golden_path.exists():
            for line in self.golden_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    q = str(obj.get("question") or "").strip().lower()
                    if q:
                        existing_questions.add(q)
                except Exception:
                    continue

        q_norm = record.test_case.question.strip().lower()
        if q_norm in existing_questions:
            return

        entry = {
            "audit_id": record.audit_id,
            "timestamp": record.timestamp.isoformat(),
            "question": record.test_case.question,
            "category": record.test_case.category.value,
            "language": record.test_case.language.value,
            "legal_branch": record.test_case.legal_branch,
            "trap_intent": record.test_case.trap_intent,
            "is_false_premise": record.test_case.is_false_premise,
            "expected_doc_ids": record.test_case.expected_doc_ids,
            "expected_articles": record.test_case.expected_articles,
            "expected_key_facts": record.test_case.expected_key_facts,
            "forbidden_claims": record.test_case.forbidden_claims,
            "gold_reference_summary": record.test_case.gold_reference_summary,
            "target_answer": record.target_observation.answer_text,
            "auditor_evidence": [v.model_dump(mode="json") for v in record.verifications],
            "error_codes": [e.value for e in record.error_codes],
            "total_score": record.total_score,
            "verdict": record.verdict.value,
            "auditor_critique": record.auditor_critique,
            "root_causes": [rc.model_dump(mode="json") for rc in record.root_causes],
        }
        with self.golden_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def list_golden_failures(self) -> list[dict[str, Any]]:
        if not self.golden_path.exists():
            return []
        items: list[dict[str, Any]] = []
        for line in self.golden_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                items.append(json.loads(line))
            except Exception:
                continue
        return list(reversed(items))

    def load_regression_test_cases(self) -> list[AdversarialTestCase]:
        """Convert persisted `golden_failures.jsonl` entries back into executable regression test cases."""
        cases: list[AdversarialTestCase] = []
        for idx, raw in enumerate(self.list_golden_failures(), start=1):
            try:
                cases.append(
                    AdversarialTestCase(
                        case_id=f"reg_{idx:03d}_{raw.get('audit_id', '')[:6]}",
                        category=raw["category"],
                        language=raw.get("language", "uz_latn"),
                        legal_branch=raw.get("legal_branch", "general"),
                        difficulty="regression",
                        question=raw["question"],
                        trap_intent=raw.get("trap_intent", ""),
                        is_false_premise=bool(raw.get("is_false_premise", False)),
                        expected_doc_ids=raw.get("expected_doc_ids", []),
                        expected_articles=raw.get("expected_articles", []),
                        expected_key_facts=raw.get("expected_key_facts", []),
                        forbidden_claims=raw.get("forbidden_claims", []),
                        gold_reference_summary=raw.get("gold_reference_summary", ""),
                        source="regression",
                    )
                )
            except Exception:
                continue
        return cases

    def list_audits(
        self,
        *,
        category: str | None = None,
        error_code: str | None = None,
        verdict: str | None = None,
        language: str | None = None,
        min_score: int | None = None,
        max_score: int | None = None,
        search: str | None = None,
        limit: int = 200,
    ) -> list[AuditRecord]:
        if not self.history_path.exists():
            return []
        records: list[AuditRecord] = []
        for line in self.history_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rec = AuditRecord.model_validate_json(line)
            except Exception:
                continue
            if category and rec.test_case.category.value != category:
                continue
            if verdict and rec.verdict.value != verdict:
                continue
            if language and rec.test_case.language.value != language:
                continue
            if error_code and error_code not in [e.value for e in rec.error_codes]:
                continue
            if min_score is not None and rec.total_score < min_score:
                continue
            if max_score is not None and rec.total_score > max_score:
                continue
            if search:
                q_low = search.lower()
                haystack = f"{rec.test_case.question} {rec.target_observation.answer_text} {rec.auditor_critique}".lower()
                if q_low not in haystack:
                    continue
            records.append(rec)
        return list(reversed(records))[:limit]

    def compute_analytics(self) -> AuditAnalytics:
        records = self.list_audits(limit=2000)
        golden_count = len(self.list_golden_failures())
        if not records:
            return AuditAnalytics(golden_failures_count=golden_count)

        total = len(records)
        pass_c = sum(1 for r in records if r.verdict == AuditVerdict.PASS)
        partial_c = sum(1 for r in records if r.verdict == AuditVerdict.PARTIAL)
        fail_c = sum(1 for r in records if r.verdict == AuditVerdict.FAIL)
        avg_score = round(sum(r.total_score for r in records) / total, 1)

        err_counter: Counter[str] = Counter()
        cat_scores: dict[str, list[int]] = defaultdict(list)
        lang_scores: dict[str, list[int]] = defaultdict(list)
        branch_stats: dict[str, dict[str, Any]] = defaultdict(lambda: {"scores": [], "fails": 0, "total": 0})

        for r in records:
            for e in r.error_codes:
                err_counter[e.value] += 1
            cat_scores[r.test_case.category.value].append(r.total_score)
            lang_scores[r.test_case.language.value].append(r.total_score)
            br = r.test_case.legal_branch or "general"
            branch_stats[br]["scores"].append(r.total_score)
            branch_stats[br]["total"] += 1
            if r.verdict == AuditVerdict.FAIL:
                branch_stats[br]["fails"] += 1

        heatmap = []
        for branch, info in branch_stats.items():
            avg_b = round(sum(info["scores"]) / len(info["scores"]), 1)
            fail_rate = round((info["fails"] / info["total"]) * 100, 1)
            heatmap.append(
                {
                    "branch": branch,
                    "total": info["total"],
                    "fails": info["fails"],
                    "avg_score": avg_b,
                    "fail_rate_pct": fail_rate,
                }
            )
        heatmap.sort(key=lambda x: x["avg_score"])

        return AuditAnalytics(
            total_audited=total,
            pass_count=pass_c,
            partial_count=partial_c,
            fail_count=fail_c,
            pass_rate_pct=round((pass_c / total) * 100, 1),
            average_score=avg_score,
            golden_failures_count=golden_count,
            error_code_counts=dict(err_counter.most_common()),
            category_avg_scores={k: round(sum(v) / len(v), 1) for k, v in cat_scores.items()},
            branch_heatmap=heatmap,
            language_avg_scores={k: round(sum(v) / len(v), 1) for k, v in lang_scores.items()},
        )

    def export_report(self, fmt: str) -> tuple[str, str, str]:
        """Export audited records as JSON, Markdown, or CSV. Returns `(content, media_type, filename)`."""
        records = self.list_audits(limit=500)
        analytics = self.compute_analytics()
        fmt = fmt.lower().strip()

        if fmt == "json":
            payload = {
                "analytics": analytics.model_dump(mode="json"),
                "audits": [r.model_dump(mode="json") for r in records],
            }
            return json.dumps(payload, ensure_ascii=False, indent=2), "application/json", "lex-auditor-report.json"

        if fmt == "csv":
            buf = io.StringIO()
            writer = csv.writer(buf)
            writer.writerow(
                [
                    "audit_id", "timestamp", "category", "language", "branch", "verdict",
                    "total_score", "citation_25", "validity_25", "reasoning_25",
                    "cross_lingual_15", "anti_hallucination_10", "error_codes",
                    "latency_ms", "question", "auditor_critique",
                ]
            )
            for r in records:
                writer.writerow(
                    [
                        r.audit_id, r.timestamp.isoformat(), r.test_case.category.value,
                        r.test_case.language.value, r.test_case.legal_branch, r.verdict.value,
                        r.total_score, r.score.citation_exactness, r.score.legal_validity_currency,
                        r.score.reasoning_completeness, r.score.cross_lingual_accuracy,
                        r.score.anti_hallucination_calibration,
                        ";".join(e.value for e in r.error_codes),
                        r.target_observation.latency_ms,
                        r.test_case.question, r.auditor_critique,
                    ]
                )
            return buf.getvalue(), "text/csv; charset=utf-8", "lex-auditor-report.csv"

        # Default: Markdown forensic dossier
        lines = [
            "# LEX AUDITOR // RED-TEAM & FACT-VERIFICATION REPORT",
            "",
            f"- **Total Audited:** {analytics.total_audited}",
            f"- **Pass Rate:** {analytics.pass_rate_pct}% (PASS: {analytics.pass_count} | PARTIAL: {analytics.partial_count} | FAIL: {analytics.fail_count})",
            f"- **Average Score:** {analytics.average_score} / 100",
            f"- **Golden Failures Logged:** {analytics.golden_failures_count}",
            "",
            "## Error Taxonomy Breakdown",
        ]
        for code, cnt in analytics.error_code_counts.items():
            lines.append(f"- `{code}`: {cnt}")
        lines.append("\n## Detailed Audit Verdicts\n")
        for r in records[:50]:
            codes = ", ".join(f"`{e.value}`" for e in r.error_codes) or "None"
            lines.extend(
                [
                    f"### [{r.verdict.value} · {r.total_score}/100] {r.test_case.category.value} ({r.audit_id})",
                    f"- **Question:** {r.test_case.question}",
                    f"- **Error Codes:** {codes}",
                    f"- **Auditor Critique:** {r.auditor_critique}",
                    f"- **Benchmark Ground Truth:** {r.benchmark_re_answer}",
                    "",
                ]
            )
        return "\n".join(lines), "text/markdown; charset=utf-8", "lex-auditor-report.md"
