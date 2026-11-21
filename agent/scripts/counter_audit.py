#!/usr/bin/env python3
"""Run the counter-agent (LEX AUDITOR, ``agent_couinter/``) test suites against a running legal agent.

The auditor's own engine does the work: it interrogates the agent, extracts the claims and citations, verifies
them independently and scores every answer 0-100. This script only feeds it every built-in case and summarises
the verdicts, so the same command works against a local server and a deployed one.

Suites:
* ``curated``: the curated adversarial trap bank (``trap_engine.CURATED_TRAP_BANK`` without the vault part);
* ``golden``: earlier failures saved in ``agent_couinter/data/golden_failures.jsonl`` (vault questions removed);
* ``vault``: the blind adversarial vault (``blind_test_vault.BLIND_ADVERSARIAL_VAULT``). It is a zero-leakage
  holdout, so the report gives only its aggregate numbers, never its questions or answers.

Run it with the counter-agent's interpreter (it imports ``evaluator_agent``)::

    agent_couinter/.venv/bin/python agent/scripts/counter_audit.py --target http://127.0.0.1:8000 \\
        --json-out counter-audit.json --md-out counter-audit.md

The auditor keeps its run history in a temporary data directory, so ``agent_couinter/data`` is never modified.
Without an auditor LLM key the deterministic checks are used. Live lex.uz verification follows
``ENABLE_LIVE_LEX_VERIFY`` (the default here is off, for offline runs).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import shutil
import sys
import tempfile
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
AUDITOR_ROOT = REPO_ROOT / "agent_couinter"


def _prepare_environment(args: argparse.Namespace) -> Path:
    """Point the auditor at the target and at a throwaway data directory before its settings are imported."""
    data_dir = Path(tempfile.mkdtemp(prefix="counter-audit-"))
    golden = AUDITOR_ROOT / "data" / "golden_failures.jsonl"
    if golden.exists():
        shutil.copy(golden, data_dir / "golden_failures.jsonl")
    os.environ["DATA_DIR"] = str(data_dir)
    os.environ["TARGET_AGENT_URL"] = args.target.rstrip("/")
    os.environ.setdefault("TARGET_AGENT_ANSWER_STYLE", args.answer_style)
    os.environ.setdefault("ENABLE_LIVE_LEX_VERIFY", "false")
    if not os.environ.get("AUDITOR_LLM_API_KEY"):
        os.environ.setdefault("AUDITOR_LLM_PROVIDER", "mock")
    if args.corpus_db:
        os.environ["LOCAL_CORPUS_DB_PATH"] = str(Path(args.corpus_db).resolve())
    sys.path.insert(0, str(AUDITOR_ROOT))
    return data_dir


def _cases(suites: list[str], data_dir: Path) -> list[tuple[str, Any]]:
    from evaluator_agent.blind_test_vault import BLIND_ADVERSARIAL_VAULT
    from evaluator_agent.models import AdversarialTestCase
    from evaluator_agent.trap_engine import CURATED_TRAP_BANK

    vault_questions = {str(raw.get("question", "")).strip() for raw in BLIND_ADVERSARIAL_VAULT}
    out: list[tuple[str, Any]] = []
    if "curated" in suites:
        for idx, raw in enumerate(CURATED_TRAP_BANK, start=1):
            if str(raw.get("question", "")).strip() in vault_questions:
                continue  # the trap bank appends the blind vault; it is run (blind) as its own suite
            out.append(("curated", AdversarialTestCase(case_id=f"trap_{idx:03d}", source="curated_trap_bank", **raw)))
    if "vault" in suites:
        for idx, raw in enumerate(BLIND_ADVERSARIAL_VAULT, start=1):
            fields = {k: v for k, v in raw.items() if k in AdversarialTestCase.model_fields and k != "case_id"}
            out.append(("vault", AdversarialTestCase(case_id=f"vault_{idx:03d}", source="manual", **fields)))
    if "golden" in suites:
        from evaluator_agent.config import get_settings
        from evaluator_agent.regression import RegressionAndAuditStore

        for idx, tc in enumerate(RegressionAndAuditStore(get_settings()).load_regression_test_cases(), start=1):
            if tc.question.strip() in vault_questions:
                continue
            out.append(("golden", tc.model_copy(update={"case_id": f"golden_{idx:03d}"})))
    return out


async def _run(args: argparse.Namespace, data_dir: Path) -> dict[str, Any]:
    from evaluator_agent.audit_engine import RedTeamAuditEngine

    cases = _cases(args.suites, data_dir)
    if args.limit:
        cases = cases[: args.limit]
    engine = RedTeamAuditEngine()
    sem = asyncio.Semaphore(max(1, args.concurrency))
    results: list[dict[str, Any]] = []

    async def one(suite: str, tc: Any) -> None:
        async with sem:
            record: dict[str, Any] | None = None
            async for ev in engine.audit_test_case_stream(tc, run_mode="batch"):
                if ev.get("type") == "verdict":
                    record = ev.get("record")
            if record is None:
                record = {"verdict": "ERROR", "total_score": 0, "error_codes": ["NO_VERDICT"], "test_case": tc.model_dump(mode="json")}
            record["suite"] = suite
            results.append(record)

    started = time.perf_counter()
    try:
        await asyncio.gather(*(one(s, tc) for s, tc in cases))
    finally:
        await engine.close()
    elapsed = time.perf_counter() - started
    return _summarise(results, elapsed, args)


def _summarise(results: list[dict[str, Any]], elapsed: float, args: argparse.Namespace) -> dict[str, Any]:
    def bucket(rows: list[dict[str, Any]]) -> dict[str, Any]:
        verdicts = Counter(r["verdict"] for r in rows)
        scores = [int(r.get("total_score") or 0) for r in rows]
        return {
            "n": len(rows),
            "pass": verdicts.get("PASS", 0),
            "partial": verdicts.get("PARTIAL", 0),
            "fail": verdicts.get("FAIL", 0) + verdicts.get("ERROR", 0),
            "mean_score": round(sum(scores) / len(scores), 1) if scores else 0.0,
        }

    by_suite: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_category: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in results:
        by_suite[r["suite"]].append(r)
        if r["suite"] != "vault":
            by_category[r["test_case"]["category"]].append(r)
    codes = Counter(code for r in results if r["suite"] != "vault" for code in r.get("error_codes") or [])
    target_errors = Counter(
        str((r.get("target_observation") or {}).get("error") or "")[:120]
        for r in results
        if (r.get("target_observation") or {}).get("error")
    )
    latencies = sorted(int((r.get("target_observation") or {}).get("latency_ms") or 0) for r in results)
    failures = [
        {
            "suite": r["suite"],
            "case_id": r["test_case"].get("case_id"),
            "category": r["test_case"]["category"],
            "language": r["test_case"].get("language"),
            "question": r["test_case"]["question"],
            "verdict": r["verdict"],
            "score": r.get("total_score"),
            "error_codes": r.get("error_codes") or [],
            "flagged": [str(s)[:240] for s in (r.get("flagged_sentences") or [])[:4]],
            "answer": str((r.get("target_observation") or {}).get("answer_text") or "")[:4000],
            "expected_articles": r["test_case"].get("expected_articles"),
            "expected_key_facts": r["test_case"].get("expected_key_facts"),
            "gold": str(r["test_case"].get("gold_reference_summary") or "")[:400],
        }
        for r in sorted(results, key=lambda x: (x["suite"], str(x["test_case"].get("case_id"))))
        if r["verdict"] != "PASS" and r["suite"] != "vault"
    ]
    return {
        "target": args.target,
        "elapsed_s": round(elapsed, 1),
        "overall": bucket(results),
        "by_suite": {k: bucket(v) for k, v in sorted(by_suite.items())},
        "by_category": {k: bucket(v) for k, v in sorted(by_category.items())},
        "error_codes": dict(codes.most_common()),
        "target_errors": dict(target_errors.most_common(5)),
        "target_latency_ms": {
            "p50": latencies[len(latencies) // 2] if latencies else 0,
            "p95": latencies[int(len(latencies) * 0.95) - 1] if latencies else 0,
        },
        "failures": failures,
    }


def _markdown(report: dict[str, Any]) -> str:
    o = report["overall"]
    lines = [
        f"# Counter-agent audit of {report['target']}",
        "",
        f"{o['n']} cases in {report['elapsed_s']} s: **{o['pass']} PASS · {o['partial']} PARTIAL · {o['fail']} FAIL**, "
        f"mean score {o['mean_score']}/100.",
        "",
        "| Group | Cases | PASS | PARTIAL | FAIL | Mean |",
        "|---|---|---|---|---|---|",
    ]
    for title, groups in (("suite", report["by_suite"]), ("category (dev suites)", report["by_category"])):
        for name, b in groups.items():
            lines.append(f"| {title}: {name} | {b['n']} | {b['pass']} | {b['partial']} | {b['fail']} | {b['mean_score']} |")
    errors = report.get("target_errors") or {}
    lat = report.get("target_latency_ms") or {}
    lines += ["", f"Agent latency p50 {lat.get('p50')} ms, p95 {lat.get('p95')} ms; transport/timeout errors: {sum(errors.values())}"]
    lines += [f"* {count}× {msg}" for msg, count in errors.items()]
    lines += ["", "Error codes (dev suites): " + (", ".join(f"{k} {v}" for k, v in report["error_codes"].items()) or "none"), ""]
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--target", default="http://127.0.0.1:8000", help="Base URL of the legal agent")
    parser.add_argument("--suites", default="curated,vault,golden", help="Comma-separated: curated, vault, golden")
    parser.add_argument("--answer-style", default="concise", choices=["concise", "detailed"])
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--limit", type=int, default=0, help="Run only the first N cases (0 = all)")
    parser.add_argument("--corpus-db", default="", help="Optional agent SQLite index for the auditor's local checks")
    parser.add_argument("--json-out", default="")
    parser.add_argument("--md-out", default="")
    parser.add_argument("--min-mean", type=float, default=0.0, help="Exit 1 if the mean score is below this")
    args = parser.parse_args()
    args.suites = [s.strip() for s in args.suites.split(",") if s.strip()]

    data_dir = _prepare_environment(args)
    try:
        report = asyncio.run(_run(args, data_dir))
    finally:
        shutil.rmtree(data_dir, ignore_errors=True)
    if args.json_out:
        Path(args.json_out).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md = _markdown(report)
    if args.md_out:
        Path(args.md_out).write_text(md, encoding="utf-8")
    print(md)
    return 1 if report["overall"]["mean_score"] < args.min_mean else 0


if __name__ == "__main__":
    raise SystemExit(main())
