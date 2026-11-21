"""Rich interactive CLI for the Lex.uz Legal AI Agent."""

from __future__ import annotations

import asyncio
import json
from datetime import date
from pathlib import Path

import typer
import uvicorn
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from lex_agent.models import (
    AgentQueryRequest,
    DocumentAuditRequest,
    Language,
    TemporalLookupRequest,
    TranslationCompareRequest,
)
from lex_agent.runtime import AgentRuntime

app = typer.Typer(name="lex-agent", help="Lex.uz Legal AI Agent — Complete Uzbekistan Legislation CLI (UZ/RU/EN)")
console = Console()


@app.command()
def serve(
    host: str = typer.Option("0.0.0.0", help="Host address"),
    port: int = typer.Option(8000, help="Port number"),
    reload: bool = typer.Option(False, help="Enable auto-reload for development"),
) -> None:
    """Start the FastAPI backend & Legal AI Web UI."""
    uvicorn.run("lex_agent.api.app:app", host=host, port=port, reload=reload)


@app.command("build-index")
def build_index(force: bool = typer.Option(False, help="Rebuild even if the bundled corpora are unchanged")) -> None:
    """Index the bundled open legal corpora (Uzbek Latin, Russian, lex.uz snapshots, curated facts)."""
    rt = AgentRuntime.build()
    stats_payload = rt.build_index(force=force)
    console.print_json(json.dumps(stats_payload, ensure_ascii=False))


@app.command("eval")
def eval_retrieval(
    k: int = typer.Option(5, help="Cut-off rank"),
    gold: Path = typer.Option(None, help="Path to a gold JSONL file (defaults to eval/retrieval_gold.jsonl)"),
    show_all: bool = typer.Option(False, help="Print every query, not only misses"),
) -> None:
    """Measure retrieval quality (hit@1, hit@k, MRR, latency) on the labelled gold set."""
    from lex_agent.evaluation import DEFAULT_GOLD, evaluate_retrieval

    rt = AgentRuntime.build()
    rt.build_index()
    report = asyncio.run(evaluate_retrieval(rt.retriever, gold or DEFAULT_GOLD, k=k))
    table = Table(title=f"Retrieval quality ({report['queries']} questions)")
    for key in ("hit@1", f"hit@{k}", f"mrr@{k}", "p50_ms", "p95_ms"):
        table.add_row(key, str(report[key]))
    console.print(table)
    rows = report["per_query"] if show_all else report["misses"]
    for row in rows:
        console.print(f"[{'green' if row['rank'] else 'red'}]{row['rank'] or '✗'}[/] {row['q']}  →  {row['top']}")


@app.command()
def stats() -> None:
    """Display local knowledge base statistics."""
    rt = AgentRuntime.build()
    try:
        reg = rt.ingestion.registry.stats()
        table = Table(title="Lex.uz Knowledge Base Statistics")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")
        table.add_row("Registered Documents", str(reg["total_documents"]))
        table.add_row("BM25 Indexed Chunks", str(rt.bm25_store.count()))
        table.add_row("Qdrant Vector Chunks", str(rt.vector_store.count()))
        table.add_row("By Language", json.dumps(reg["by_language"], ensure_ascii=False))
        table.add_row("By Document Type", json.dumps(reg["by_type"], ensure_ascii=False))
        table.add_row("By Status", json.dumps(reg["by_status"], ensure_ascii=False))
        console.print(table)
    finally:
        rt.vector_store.close()


@app.command()
def ask(
    query: str = typer.Argument(..., help="Legal question in Uzbek (Latin/Cyrillic), Russian, or English"),
    lang: Language | None = typer.Option(None, help="Force response language: uz_latn | uz_cyrl | ru | en"),
    as_of: str | None = typer.Option(None, help="Temporal lookup date YYYY-MM-DD"),
    max_hops: int = typer.Option(3, help="Multi-hop cross-reference depth"),
    live_lex: bool = typer.Option(True, help="Allow live Lex.uz search fallback"),
    compare_translations: bool = typer.Option(False, help="Flag UZ vs RU/EN discrepancies"),
) -> None:
    """Ask a grounded legal question with multi-hop reasoning and zero-hallucination citation verification."""

    async def _run() -> None:
        rt = AgentRuntime.build()
        try:
            req = AgentQueryRequest(
                query=query,
                response_language=lang,
                as_of_date=date.fromisoformat(as_of) if as_of else None,
                max_hops=max_hops,
                enable_live_lex=live_lex,
                compare_translations=compare_translations,
            )
            resp = await rt.orchestrator.answer(req)
            status = "VERIFIED" if resp.verification.passed else "WARNINGS"
            console.print(Panel(resp.answer, title=f"Lex.uz Legal Analysis [{status} | conf={resp.verification.confidence_score}]"))
            if resp.citations:
                tbl = Table(title="Verified Lex.uz Citations")
                tbl.add_column("Document", style="cyan")
                tbl.add_column("Article", style="magenta")
                tbl.add_column("Status", style="green")
                tbl.add_column("URL", style="blue")
                for c in resp.citations[:10]:
                    tbl.add_row(c.doc_title[:65], c.article or "-", c.status.value, c.url)
                console.print(tbl)
            if resp.verification.unverified_references:
                console.print("[bold red]Unverified references flagged:[/bold red]", resp.verification.unverified_references)
        finally:
            await rt.close()

    asyncio.run(_run())


@app.command()
def chat() -> None:
    """Launch an interactive multilingual Uzbekistan legal consultation session."""

    async def _loop() -> None:
        rt = AgentRuntime.build()
        console.print(Panel("Lex.uz Legal AI Agent Interactive Console (type 'exit' to quit)", style="bold blue"))
        try:
            while True:
                q = console.input("\n[bold cyan]You > [/bold cyan]").strip()
                if not q or q.lower() in ("exit", "quit", ":q"):
                    break
                resp = await rt.orchestrator.answer(AgentQueryRequest(query=q))
                console.print(Panel(resp.answer, title=f"Lex.uz Agent (verified={resp.verification.passed})"))
                for c in resp.citations[:5]:
                    console.print(f"  [dim]• {c.doc_title} | {c.article or ''} | {c.status.value} — {c.url}[/dim]")
        finally:
            await rt.close()

    asyncio.run(_loop())


@app.command("ingest-doc")
def ingest_doc(
    doc_id: str = typer.Argument(..., help="Lex.uz numeric document ID, e.g. 6445147"),
    all_languages: bool = typer.Option(True, help="Also follow and index linked UZ/RU/EN editions"),
) -> None:
    """Fetch and index a specific Lex.uz document live."""

    async def _run() -> None:
        rt = AgentRuntime.build()
        try:
            res = await rt.ingestion.ingest_lex_doc(doc_id, fetch_all_languages=all_languages)
            console.print_json(data=res)
        finally:
            await rt.close()

    asyncio.run(_run())


@app.command("ingest-hf")
def ingest_hf(
    dataset: str = typer.Option("Alii2004/lexuz-legislation", help="HuggingFace dataset ID"),
    max_docs: int = typer.Option(1000, help="Maximum documents to ingest (set higher for full corpus)"),
) -> None:
    """Bootstrap offline Uzbekistan legislation from HuggingFace corpora."""

    async def _run() -> None:
        rt = AgentRuntime.build()
        try:
            res = await rt.ingestion.ingest_huggingface_corpus(dataset_name=dataset, max_docs=max_docs)
            console.print_json(data=res)
        finally:
            await rt.close()

    asyncio.run(_run())


@app.command("ingest-local")
def ingest_local(
    path: Path = typer.Argument(..., help="Local .jsonl, .json, .parquet file or directory"),
    max_docs: int | None = typer.Option(None, help="Optional max documents limit"),
) -> None:
    """Ingest local Lex.uz JSONL/Parquet legislation dumps."""

    async def _run() -> None:
        rt = AgentRuntime.build()
        try:
            res = await rt.ingestion.ingest_local_path(path, max_docs=max_docs)
            console.print_json(data=res)
        finally:
            await rt.close()

    asyncio.run(_run())


@app.command("bootstrap-core")
def bootstrap_core(all_languages: bool = typer.Option(True, help="Fetch UZ/RU/EN editions")) -> None:
    """Fetch and index Uzbekistan's Constitution and foundational Codes live from Lex.uz."""

    async def _run() -> None:
        rt = AgentRuntime.build()
        try:
            res = await rt.ingestion.bootstrap_core_codes(fetch_all_languages=all_languages)
            console.print_json(data=res)
        finally:
            await rt.close()

    asyncio.run(_run())


@app.command()
def audit(
    file_path: Path = typer.Argument(..., help="Path to contract/filing (.txt, .md, .pdf, .docx)"),
    kind: str = typer.Option("contract", help="contract | employment | court_filing | regulation"),
) -> None:
    """Audit a legal document against current Uzbekistan legislation."""
    from lex_agent.capabilities.document_analyzer import (
        extract_text_from_uploaded_bytes,
    )

    text = extract_text_from_uploaded_bytes(file_path.name, file_path.read_bytes())

    async def _run() -> None:
        rt = AgentRuntime.build()
        try:
            resp = await rt.document_analyzer.audit(DocumentAuditRequest(document_text=text, document_kind=kind))
            console.print_json(data=resp.model_dump(mode="json"))
        finally:
            await rt.close()

    asyncio.run(_run())


@app.command()
def translate(
    doc_id: str = typer.Option(..., help="Lex.uz document ID"),
    target: Language = typer.Option(Language.EN, help="Target language: uz_latn | uz_cyrl | ru | en"),
    article: str | None = typer.Option(None, help="Optional article number"),
) -> None:
    """Translate a Lex.uz provision and flag discrepancies against the authoritative Uzbek text."""

    async def _run() -> None:
        rt = AgentRuntime.build()
        try:
            resp = await rt.comparator.translate_and_compare(
                TranslationCompareRequest(doc_id=doc_id, article=article, target_language=target)
            )
            console.print_json(data=resp.model_dump(mode="json"))
        finally:
            await rt.close()

    asyncio.run(_run())


@app.command()
def temporal(
    query: str = typer.Argument(..., help="Legal provision or topic"),
    historical_date: str = typer.Option(..., help="Historical date YYYY-MM-DD"),
    comparison_date: str | None = typer.Option(None, help="Comparison date YYYY-MM-DD (default: today)"),
) -> None:
    """Compare what Uzbekistan legislation provided on a historical date vs. today."""

    async def _run() -> None:
        rt = AgentRuntime.build()
        try:
            resp = await rt.temporal_lookup.compare(
                TemporalLookupRequest(
                    query=query,
                    historical_date=date.fromisoformat(historical_date),
                    comparison_date=date.fromisoformat(comparison_date) if comparison_date else None,
                )
            )
            console.print_json(data=resp.model_dump(mode="json"))
        finally:
            await rt.close()

    asyncio.run(_run())


if __name__ == "__main__":
    app()
