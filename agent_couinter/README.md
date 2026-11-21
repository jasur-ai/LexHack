# LEX AUDITOR // Red-Team & Fact-Verification Engine (`agent_couinter/`)

**Part 2: Zero-Trust Adversarial Legal Auditor** designed to relentlessly interrogate, trap, fact-check, score (0–100), diagnose root causes, and run regression suites against the primary Uzbekistan Legal AI Agent (`../agent/`).

---

## Architecture

```text
agent_couinter/
├── pyproject.toml
├── requirements.txt
├── .env.example / .env
├── evaluator_agent/
│   ├── config.py                 # AuditorSettings (port 8001, auto-inherits API key from ../agent/.env)
│   ├── models.py                 # 7 categories, 8 error taxonomy codes, 5-part rubric (25+25+25+15+10)
│   ├── llm_client.py             # Independent Auditor LLM (Gemini AQ./AIza native REST, OpenAI, Ollama)
│   ├── target_client.py          # Async HTTPX interrogator for Target Agent (`agent/` on :8000)
│   ├── trap_engine.py            # 7-category Adversarial Trap Bank (UZ/RU/EN) + dynamic LLM trap generator
│   ├── claim_parser.py           # Zero-Trust Atomic Claim & Citation Extractor
│   ├── independent_verifier.py   # Read-only local SQLite corpus + live Lex.uz independent verifier
│   ├── scorer.py                 # 0-100 Scorer + 8 Error Codes + `agent/` Root-Cause Diagnostician
│   ├── regression.py             # `data/golden_failures.jsonl`, Analytics Heatmap & JSON/MD/CSV Export
│   ├── audit_engine.py           # Single, Batch (Pause/Stop), and Regression SSE Orchestrator
│   ├── api/
│   │   ├── app.py                # FastAPI Backend (port 8001)
│   │   └── static/index.html     # 3-Column LEX AUDITOR Red-Team Command Center UI
│   └── cli.py                    # Typer CLI (`lex-auditor`)
└── tests/
    ├── test_claim_parser.py
    ├── test_trap_engine.py
    └── test_scorer_and_regression.py
```

---

## Quick Start

> **Important:** Run **Target Agent (`agent/`)** on port `8000` in Terminal 1, and **LEX AUDITOR (`agent_couinter/`)** on port `8001` in Terminal 2!

### Terminal 1 — Primary Legal Agent (`agent/`)
```powershell
cd d:\Hackathon\LexHack\agent
.\.venv\Scripts\python.exe -m lex_agent.cli serve --port 8000
```

### Terminal 2 — Zero-Trust Red-Team Auditor (`agent_couinter/`)
You can reuse `agent\.venv` or create a dedicated `.venv`:
```powershell
cd d:\Hackathon\LexHack\agent_couinter
..\agent\.venv\Scripts\python.exe -m pip install -e . --no-deps
..\agent\.venv\Scripts\python.exe -m evaluator_agent.cli serve --port 8001
```

Open the **3-Column Red-Team Audit Command Center**:
- **Dashboard:** `http://localhost:8001/`
- **OpenAPI Docs:** `http://localhost:8001/docs`

### Keyboard Shortcuts in Dashboard
- `Ctrl + Enter` — Interrogate Target Agent & Run Zero-Trust Audit
- `G` — Generate fresh Adversarial Trap Question
- `R` — Re-run Regression Suite (`data/golden_failures.jsonl`)
- `/` — Focus instant Search & Filter

### CLI Commands
```powershell
# Single adversarial audit
..\agent\.venv\Scripts\python.exe -m evaluator_agent.cli audit "Oila kodeksining 412-moddasi bo'yicha javobgarlik qanday?" --category FABRICATED_CITATION_TRAP

# Run a 10-case Red-Team Batch Suite
..\agent\.venv\Scripts\python.exe -m evaluator_agent.cli batch --count 10

# Re-run all Golden Failures from golden_failures.jsonl
..\agent\.venv\Scripts\python.exe -m evaluator_agent.cli regression

# Run unit tests
..\agent\.venv\Scripts\python.exe -m pytest -v
```
