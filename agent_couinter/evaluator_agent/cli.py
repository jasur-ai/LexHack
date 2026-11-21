"""Rich CLI for LEX AUDITOR // Zero-Trust Red-Team Legal Verification Engine."""

from __future__ import annotations

import asyncio
import json

import typer
import uvicorn
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from evaluator_agent.audit_engine import RedTeamAuditEngine
from evaluator_agent.models import (
    AdversarialCategory,
    AuditLanguage,
    BatchAuditRequest,
    SingleAuditRequest,
)

app = typer.Typer(name="lex-auditor", help="LEX AUDITOR // Red-Team & Fact-Verification CLI for Uzbekistan Legal AI")
console = Console()


@app.command()
def serve(
    host: str = typer.Option("0.0.0.0", help="Host bind address"),
    port: int = typer.Option(8001, help="Port number (default 8001 alongside agent/ on 8000)"),
    reload: bool = typer.Option(False, help="Auto-reload on code changes"),
) -> None:
    """Launch the LEX AUDITOR FastAPI server and 3-Column Red-Team Dashboard."""
    uvicorn.run("evaluator_agent.api.app:app", host=host, port=port, reload=reload)


@app.command()
def audit(
    question: str = typer.Argument(..., help="Legal question or adversarial trap to interrogate Target Agent"),
    category: AdversarialCategory = typer.Option(AdversarialCategory.DIRECT_NORM_PRECISION),
    target_url: str | None = typer.Option(None, help="Override Target Agent URL (default http://localhost:8000)"),
) -> None:
    """Run a single zero-trust audit against Target Agent (`agent/`)."""

    async def _run() -> None:
        eng = RedTeamAuditEngine()
        try:
            rec = await eng.audit_single(
                SingleAuditRequest(question=question, category=category, target_agent_url=target_url)
            )
            style = "green" if rec.verdict.value == "PASS" else ("yellow" if rec.verdict.value == "PARTIAL" else "red")
            console.print(
                Panel(
                    f"[bold]Verdict:[/bold] [{style}]{rec.verdict.value}[/{style}] ({rec.total_score}/100)\n"
                    f"[bold]Error Codes:[/bold] {[e.value for e in rec.error_codes]}\n\n"
                    f"[bold]Auditor Critique:[/bold]\n{rec.auditor_critique}\n\n"
                    f"[bold]Benchmark Ground Truth:[/bold]\n{rec.benchmark_re_answer}",
                    title=f"LEX AUDITOR // {rec.audit_id}",
                )
            )
        finally:
            await eng.close()

    asyncio.run(_run())


@app.command()
def batch(
    count: int = typer.Option(10, help="Number of adversarial traps to run"),
    target_url: str | None = typer.Option(None, help="Override Target Agent URL"),
) -> None:
    """Execute an N-case Red-Team Batch Audit Suite."""

    async def _run() -> None:
        eng = RedTeamAuditEngine()
        try:
            async for ev in eng.run_batch_stream(BatchAuditRequest(count=count, target_agent_url=target_url)):
                if ev.get("type") == "verdict":
                    r = ev["record"]
                    console.print(
                        f"[{r['verdict']}] {r['total_score']:>3}/100 | {r['test_case']['category']} | "
                        f"{r['error_codes']} | {r['test_case']['question'][:70]}"
                    )
                elif ev.get("type") == "batch_done":
                    console.print_json(data=ev["analytics"])
        finally:
            await eng.close()

    asyncio.run(_run())


@app.command()
def regression() -> None:
    """Re-run all persisted failure cases from `data/golden_failures.jsonl`."""

    async def _run() -> None:
        eng = RedTeamAuditEngine()
        try:
            async for ev in eng.run_regression_stream():
                if ev.get("type") == "verdict":
                    r = ev["record"]
                    console.print(f"[{r['verdict']}] {r['total_score']:>3}/100 | {r['test_case']['question'][:75]}")
                elif ev.get("type") in ("batch_done", "error"):
                    console.print_json(data=ev)
        finally:
            await eng.close()

    asyncio.run(_run())


@app.command("generate-trap")
def generate_trap(
    category: AdversarialCategory | None = typer.Option(None),
    language: AuditLanguage | None = typer.Option(None),
) -> None:
    """Generate a single adversarial Uzbekistan legal trap question."""

    async def _run() -> None:
        eng = RedTeamAuditEngine()
        try:
            trap = await eng.traps.generate_trap(category=category, language=language)
            console.print_json(data=trap.model_dump(mode="json"))
        finally:
            await eng.close()

    asyncio.run(_run())


@app.command()
def stats() -> None:
    """Display Red-Team audit analytics and weak-spot breakdown."""
    eng = RedTeamAuditEngine()
    a = eng.store.compute_analytics()
    tbl = Table(title="LEX AUDITOR // Analytics Summary")
    tbl.add_column("Metric", style="cyan")
    tbl.add_column("Value", style="bold")
    tbl.add_row("Total Audited", str(a.total_audited))
    tbl.add_row("Pass Rate", f"{a.pass_rate_pct}% (PASS={a.pass_count}, PARTIAL={a.partial_count}, FAIL={a.fail_count})")
    tbl.add_row("Average Score", f"{a.average_score} / 100")
    tbl.add_row("Golden Failures", str(a.golden_failures_count))
    tbl.add_row("Top Error Codes", json.dumps(a.error_code_counts, ensure_ascii=False))
    console.print(tbl)


if __name__ == "__main__":
    app()
