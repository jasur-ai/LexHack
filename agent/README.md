# Lex.uz Legal Agent (`agent/`)

A legal assistant for Uzbekistan's legislation. It answers everyday legal questions in **Uzbek (Latin and
Cyrillic), Russian and English**, cites the exact articles of the official texts it relies on, calculates fines,
alimony, compensation and deadlines, drafts standard documents, and says plainly when it cannot help.

* **Without an LLM key** it answers in *extractive* mode: short answer cards built from quoted articles,
  typically **35–85 ms** per question.
* **With a Gemini key** the answer is written by the model from the retrieved articles and streamed token by token.
  Citations are checked against the evidence. If the model is slow or fails, the agent falls back to the
  extractive answer automatically.
* It fits a **512 MB** instance (Render Starter). There is no torch and no vector DB: a ~95 MB SQLite FTS5 index
  plus a trained CPU reranker do the retrieval.

> **Qisqacha (o'zbekcha).** Agent O'zbekiston qonunchiligi bo'yicha savollarga o'zbek (lotin/kirill), rus va
> ingliz tillarida javob beradi. Har bir javobda aniq modda keltiriladi. Agent jarima, aliment, kompensatsiya va
> muddatlarni hisoblaydi, ariza namunalarini tayyorlaydi. LLM kalitisiz ham ishlaydi (rasmiy matndan iqtibos,
> ~50 ms). Gemini kaliti bilan javob oqim tarzida yoziladi. Render'da 512 MB xotira yetadi. Matnlarni lex.uz
> bilan har tunda yangilash GitHub Actions orqali ishlaydi.

**Contents:** [What it handles](#what-it-handles) · [Architecture](#architecture) ·
[Knowledge base](#knowledge-base) · [Quick start](#quick-start) · [Configuration](#configuration) · [CLI](#cli) ·
[HTTP API](#http-api) · [Deploy](#deploy) · [Keeping texts fresh](#keeping-texts-fresh-lexuz-sync) ·
[Quality and tests](#quality-and-tests) · [Limitations](#limitations)

---

## What it handles

Every question first goes through a router. Direct routes are answered without the search pipeline.

| Route | Example | What the user gets |
|---|---|---|
| `legal` | "Ishdan bo'shatishdi, kompensatsiya bormi?" | Answer card: direct answer first, key points with `[n]` citations, practical steps, caution, follow-ups |
| `calculation` | "aliment hisoblab ber: oylik 6 mln, 2 bola" | Exact figure with the formula and its legal basis. Calculators: fine (in BHM), state duty, alimony, late-wage compensation, tax penalty (penya), severance, vacation pay, income tax, deadlines (holiday-aware) |
| `template` | "da'vo arizasi namunasi" | Fill-in template: lawsuit, alimony claim, reinstatement claim, resignation, consumer claim, appeal to a state body |
| `figures` | "BHM qancha?" | Current figure with its effective date and source decree (BHM, minimum wage, pension base, CB rate…) |
| `clarify` | "menga yordam bering", "помогите", "help me" | A request for the situation (who, what, when, amounts) with example questions, instead of guessing a topic |
| `emergency` | "eri urayapti" | Emergency numbers first (112, 102, 103, 1146 trust line), then the law |
| `illegal` | "soliqdan qanday yashirsam bo'ladi" | Polite refusal, then the liability for that act (e.g. Criminal Code art. 184, 225, 228) and the lawful alternative. Questions *about* liability, or reports of someone else's wrongdoing, stay `legal` |
| `off_topic`, `greeting`, `thanks`, `farewell`, `about` | "salom", "ob-havo qanday" | Short reply in the user's language, with suggested questions |
| `not_found` | (no relevant article) | An honest "not found" with a next step (which body or lawyer to contact) |

How it copes with any wording:

* **Language and script detection:** the answer comes back in the language and script of the question
  (`uz_latn`, `uz_cyrl`, `ru`, `en`).
* **Uzbek morphology:** suffix stripping (ishdan/ishga/ishimni → ish).
* **Typo tolerance:** "boshatishdi", "tatil" and "alimet" still find the right articles.
* **Colloquial → legal lexicon:** ~355 situation concepts. "Ishdan haydashdi" maps to the Labour Code articles
  on termination.
* **English bridge:** English questions are mapped to Russian statute terms.
* **Act and article resolution:** "Mehnat kodeksi 131-modda" and "ст. 131 ТК" resolve to the right article.
* **Conversation memory:** `history` resolves follow-ups ("unda qancha to'lashadi?").
* **Prompt-injection guard:** instructions hidden in the question or `context` are ignored.
* **False and outdated premises are corrected first:**
  * articles that do not exist ("Oila kodeksining 412-moddasi": the Family Code has 238 articles);
  * codes that were never adopted ("Kriptovalyuta kodeksi") and invented act numbers ("PF-9999");
  * repealed editions and figures that changed: the 1995 Labour Code, the 1992 Constitution, old article numbers
    such as Labour Code art. 100 → 161, VAT 15% → 12%, marriage age 17 → 18, 15 working days of leave → 21 calendar
    days, 72 hours of detention → 48.

  The answer then cites the current article. A non-existent act number is never repeated as if it were a citation
  (`lex_agent/assistant/premises.py`).
* **Follow-up suggestions:** answers offer three next questions. When the situation is recognised they are
  topic-specific (each legal domain has its own list, in all four languages) and never repeat the topic just asked
  about.

## Architecture

```
question ─► router (language/script, intent, entities: sums, dates, children, days…)
             ├─► direct answers ─ calculators · templates · figures · emergency · small talk     (steps 1, 5)
             └─► legal pipeline
                   query analysis ─ spelling (surface vocabulary) · Uzbek suffix stripping · RU/EN stemming
                                    · colloquial→legal lexicon · act/article resolver · EN→RU bridge
                   BM25 search    ─ SQLite FTS5, contentless, 48 745 article chunks (uz + ru)
                   rerank         ─ trained gradient-boosted trees, 31 features, ~1 ms (lex_agent/data/reranker_model.json)
                   leads          ─ 67 verified "lead articles" for the most common situations
                   answer         ─ Gemini (streamed, citation guard) │ extractive synthesis (question-type aware)
                   checks         ─ cited articles exist in the evidence · language · no invented articles · length
             └─► answer cache (similar questions) · warm-up of frequent questions at startup
```

CPU-bound search steps (analysis, lexical rounds, reranking) run in a bounded thread pool (`AGENT_THREADS`), so
the event loop keeps streaming other answers meanwhile.

| Folder | Role |
|---|---|
| `lex_agent/api/` | FastAPI app, web UI, SSE streaming |
| `lex_agent/assistant/` | router, entities, calculators, templates, replies, playbooks (lead articles), extractive synthesis, answer checks |
| `lex_agent/reasoning/` | orchestrator (routing → retrieval → answer → checks), answer cache, citation guard |
| `lex_agent/retrieval/` | BM25 store, hybrid retriever, reranker, spelling, query expansion, act resolver |
| `lex_agent/knowledge/` | situation lexicon (`rows_*.py`), synonyms, practical facts |
| `lex_agent/language/` | text processing, stemming, stop words, transliteration and language detection |
| `lex_agent/ingestion/` | bundled corpora, lex.uz sync (`lex_sync.py`), live lex.uz fetcher |
| `lex_agent/llm/` | OpenAI-compatible client (Gemini by default; OpenAI, OpenRouter, Ollama) |
| `data/corpus/` | bundled official texts and `practical_facts.json` |
| `eval/` | 576 labelled questions (`retrieval_gold.jsonl`) |
| `scripts/` | eval gate, SSE smoke test, load test, reranker training, corpus tools |

## Knowledge base

| Source | Content | Size in the index |
|---|---|---|
| [LawCodex/uz](https://github.com/LawCodex/uz) (lex.uz texts) | In-force Constitution, all codes and the main laws, **Uzbek** | 410 acts, 24 481 chunks |
| same | the same acts in **Russian** | 410 acts, 24 083 chunks |
| lex.uz historical editions | 1992 Constitution (for "what did the law say then" questions) | 142 chunks |
| `data/corpus/practical_facts.json` | BHM and minimum-wage history, pension base, CB rate, state duties, deadlines, holidays. Every item has a source decree and an effective date | 39 cards |
| lex.uz sync (`lex-agent sync`) | 200 most-needed acts, including 10 decrees and resolutions (traffic rules, pensions, benefits, PF-115…) | fills in after the first sync run |
| live lex.uz lookup (optional) | When nothing local matches, lex.uz search is queried within a 4 s budget; failures open a 5-minute circuit breaker | on demand |

Official legislative texts are not objects of copyright (Law ZRU-42, art. 8). Current figures:
BHM is 440 000 so'm and the minimum wage 1 360 000 so'm, both from 01.09.2026 (PF-115). The pension base is
504 000 so'm from 01.07.2026. The CB rate is 14%.

## Quick start

Requires Python 3.11.

```bash
cd agent
python3.11 -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt && pip install -e . --no-deps
cp .env.example .env            # optional: put your Gemini key into LLM_API_KEY
lex-agent build-index           # ~35 s once; skipped while the corpora are unchanged
lex-agent serve                 # http://localhost:8000 (web UI), http://localhost:8000/docs (OpenAPI)
```

```bash
lex-agent ask "Yillik mehnat ta'tili necha kun?"
curl -s localhost:8000/api/ask -H 'content-type: application/json' -d '{"query":"BHM qancha?"}'
```

## Configuration

All settings are environment variables (or `agent/.env`); see `.env.example` for the full list.

| Variable | Default | Meaning |
|---|---|---|
| `LLM_PROVIDER` | `gemini` | `gemini`, `openai`, `openrouter`, `ollama`, `mock` (tests) |
| `LLM_API_KEY` / `GEMINI_API_KEY` | empty | Without a key the agent answers extractively. Keep the key server-side only |
| `LLM_MODEL` / `LLM_FALLBACK_MODEL` | `gemini-3.8-flash` / `gemini-2.5-flash` | The fallback is used when the primary model is unavailable |
| `LLM_FIRST_TOKEN_TIMEOUT` / `LLM_REQUEST_TIMEOUT` | `20` / `45` s | No first token in time → extractive answer instead |
| `ANSWER_STYLE_DEFAULT` | `concise` | `concise` answer cards or `detailed` |
| `ANSWER_CACHE_SIZE` / `ANSWER_CACHE_TTL_SEC` | `512` / `21600` | Similar-question cache. LLM fallbacks are never cached |
| `WARMUP_ON_START` | `true` | Load the vocabulary, lexicon and figures and pre-answer suggested questions |
| `AGENT_THREADS` | `4` | Worker threads for CPU-bound search steps |
| `SQLITE_READER_MMAP_MB` | `256` | Memory-mapped index reads per thread. Use **0 on 512 MB** instances: RSS ~240 MB, ~10 ms slower |
| `LEX_UZ_ENABLE_LIVE_FALLBACK` | `true` | Live lex.uz lookup when nothing local matches |
| `LEX_SYNC_RPS` / `LEX_SYNC_BUDGET` | `0.5` / `80` | lex.uz sync pace (one request per 2 s) and max requests per run |
| `LEX_SYNC_CHECK_ENABLED` / `LEX_SYNC_HOUR` | `false` / `3` | In-process nightly freshness check (Asia/Tashkent hour). It changes no text |
| `ADMIN_TOKEN` | empty | Required (`X-Admin-Token`) for `/api/ingest/*`. Ingestion is closed while empty |
| `CORS_ORIGINS` | `*` | Comma-separated allowed origins |
| `INDEX_DIR` | `data/.cache` | Where the generated index lives |

## CLI

| Command | Purpose |
|---|---|
| `lex-agent serve [--port 8000]` | API and web UI |
| `lex-agent build-index [--force]` | Index the bundled corpora |
| `lex-agent ask "..."` / `lex-agent chat` | One question / an interactive session in the terminal |
| `lex-agent eval [--split all\|dev\|test\|holdout\|holdout2] [--show-wrong] [--json-out f.json]` | Retrieval quality: hit@1, hit@5, MRR, latency, broken down by language, domain and typos |
| `python scripts/check_eval.py f.json --min-hit1 0.88 --min-hit5 0.97 [--max-p95-ms 400]` | Quality gate used by CI |
| `lex-agent sync [--only slug\|id] [--check-only] [--force] [--budget N] [--rps R] [--report-json f]` | Refresh the 200 catalogue acts from lex.uz |
| `lex-agent sync-status` | Last run, acts synced, acts due, failures |
| `python scripts/sse_smoke.py [url]` | Post-deploy check of health, JSON answers and the SSE contract |
| `python scripts/load_test.py [url] --users 20 --duration 60 --stream 0.5 [--pid PID]` | Concurrent load with real questions; reports latency, errors, answer modes and server RSS |
| `lex-agent stats`, `audit`, `translate`, `temporal`, `ingest-*`, `bootstrap-core` | Index stats, document audit, translation comparison, historical comparison, admin ingestion |

## HTTP API

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/ask` | Full answer as JSON |
| `POST` | `/api/ask/stream` | The same answer as Server-Sent Events |
| `GET` | `/api/health` | Readiness, answer mode, index size, cache stats, lex.uz sync freshness |
| `GET` | `/api/sources` | Knowledge sources with document and chunk counts |
| `POST` | `/api/search` | Raw hybrid search (debugging, other agents) |
| `POST` | `/api/audit`, `/api/audit/upload` | Check a contract or filing (text, PDF, DOCX) against the law |
| `POST` | `/api/translate`, `/api/temporal` | Translation comparison; historical vs. current wording |
| `POST` | `/api/ingest/*` | Admin-only ingestion (`X-Admin-Token`) |

**Request** (`/api/ask`, `/api/ask/stream`):

```json
{
  "query": "Ish haqi 2 oy kechikdi, nima qilsam bo'ladi?",
  "response_language": null,
  "history": [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}],
  "context": null,
  "answer_style": "concise"
}
```

`response_language` (`uz_latn`, `uz_cyrl`, `ru`, `en`) overrides detection. `history` holds the previous turns
and `context` takes extra facts (e.g. from another agent).

**Response** (main fields):

```json
{
  "answer": "…markdown…",
  "sections": {"answer": "…", "key_points": ["… [1]"], "steps": ["…"], "caution": "…", "follow_ups": ["…"]},
  "sources": [{"n": 1, "title": "Mehnat kodeksi", "article": "333", "excerpt": "…", "url": "https://lex.uz/docs/6257288", "language": "uz_cyrl"}],
  "verification": {"…": "citation check report"},
  "route": "legal",
  "calculation": null,
  "mode": "extractive",
  "response_language": "uz_latn",
  "elapsed_ms": 41
}
```

`mode` is `llm`, `extractive` or `cache`. `calculation` holds the inputs, result, formula and basis on the
`calculation` route.

**SSE contract** (`/api/ask/stream`). Every event is a line `data: {json}`:

1. `{"type":"step", ...}`: live progress. Legal questions get steps 1–5, direct routes only steps 1 and 5.
   Cached answers replay exactly the same sequence.
2. `{"type":"sources", ...}`: the cited articles, sent before the answer text.
3. `{"type":"token", ...}`: answer text chunks.
4. `{"type":"replace_answer", ...}` (optional): the final text after the citation check.
5. `{"type":"done","elapsed_ms":…,"response":{…}}`: the full response object, same as `/api/ask`.

On failure the stream ends with `{"type":"error","detail":"…","code":"internal_error"}`. `detail` is a friendly
message in the question's language and never contains internal exception text. `/api/ask` returns the same body
with HTTP 500. These are the contracts the haqli proxy and the counter-agent rely on; keep them compatible.

## Deploy

### Render (recommended)

The whole product (haqli + this agent) is deployed by `.github/workflows/deploy.yml`; see `deploy/README.md`.
For the agent alone:

1. In Render choose **New → Blueprint**, select this repository and set the blueprint path to `agent/render.yaml`.
2. Set `GEMINI_API_KEY`. This step is optional: without it, answers are extractive.
3. Every push to `main` redeploys (`autoDeploy`). Merging the nightly sync pull request publishes fresh texts the
   same way.

The blueprint uses the **Starter** plan (0.5 CPU, 512 MB, no sleep) and builds the Docker image, which already
contains the index, so a new instance serves within seconds. It also sets `SQLITE_READER_MMAP_MB=0` and
`AGENT_THREADS=4`. The free plan also works, but it sleeps after 15 minutes idle (the first request then takes
~30–60 s).

### Docker / Compose

```bash
docker build -t lex-agent agent
docker run -p 8000:8000 -e GEMINI_API_KEY=... lex-agent
# or, from agent/:
docker compose up --build        # 512 MB limit, persistent volume for runtime-ingested documents
```

About the image:
* base `python:3.11-slim`, running as non-root user 10001;
* the index is built at image build time;
* `HEALTHCHECK` polls `/api/health`;
* `PORT` and `WEB_CONCURRENCY` are honoured, so keep 1 worker per 512 MB.

## Keeping texts fresh (lex.uz sync)

`lex_agent/ingestion/lex_sync.py` keeps the 200 most-needed acts current.

**Catalogue** (`lex_agent/data/lex_sync_catalog.json`), in three priority tiers:
* **P1 (47 acts):** Constitution, codes and the most-used laws.
* **P2 (68 acts):** lexicon targets, plus 10 decrees and resolutions found through lex.uz search and verified by
  number and title.
* **P3 (85 acts):** everyday laws.

**Polite client:**
* 0.5 requests/s with a request budget per run;
* `Retry-After` is honoured;
* ETag and SHA-256 change detection;
* each act is re-checked every 2, 7 or 14 days, depending on its tier.

**Safety:**
* A page that yields fewer than half of the stored articles is marked *suspect*, and the old text stays.
* Superscript article numbers are converted, never guessed.

**Output:** `data/corpus/lex_sync_{uz,ru}.jsonl.gz` plus the catalogue and state files. Synced texts take
precedence over the bundled snapshot when indexing.

**Nightly workflow** (`.github/workflows/lex-sync.yml`):
1. It runs at 03:00 Tashkent time.
2. It syncs, commits the data to the branch `lex-sync/data` and opens a pull request when texts changed.
3. Merging the pull request triggers the Render redeploy.

The workflow needs *Settings → Actions → General → Allow GitHub Actions to create and approve pull requests*. If
lex.uz refuses GitHub's runners, run the same job on a self-hosted runner in Uzbekistan.

On a live server `LEX_SYNC_CHECK_ENABLED=true` runs a nightly *check only*: `/api/health → lex_sync` then shows
which acts changed. No text changes without review.

## Quality and tests

**CI** (`.github/workflows/agent-ci.yml`) runs on every push and pull request that touches `agent/`:

1. Lint with `ruff` (E9, F).
2. Unit, route and API tests: **228** tests. They cover:
   * thread-safety and the SSE contract;
   * a router battery of real phrasings (emergency, illegal, vague requests and look-alike legal questions);
   * false and outdated premises;
   * lex.uz sync on HTML fixtures.
3. Build the index.
4. **Retrieval quality gate:** the test split needs hit@1 ≥ 0.88, hit@5 ≥ 0.97 and p95 ≤ 400 ms; the blind
   holdout2 split needs hit@1 ≥ 0.60 and hit@5 ≥ 0.85.
5. Start a live server, run the SSE smoke test, then a 20-user load test. Zero errors and no tracebacks are
   allowed.
6. A **Docker job** builds the production image and runs it with a **512 MB limit**. It repeats the smoke test and
   a 30-user load test, and checks the container was not OOM-killed.

**Retrieval quality** (`lex-agent eval`, 576 labelled questions; 15 domains; 4 languages; 53 with typos):

| Slice | hit@1 | hit@5 |
|---|---|---|
| **All** (MRR 0.935) | **0.901** | **0.983** |
| dev (315; used while tuning) | 0.96 | 1.00 |
| test (116) | 0.94 | 0.99 |
| holdout (61) | 0.80 | 1.00 |
| **holdout2** (84; written blind, after development) | **0.68** | **0.89** |
| by language: en / ru / uz_cyrl / uz_latn | 0.95 / 0.90 / 0.94 / 0.89 | 1.00 / 0.97 / 0.98 / 0.98 |
| with typos | 0.89 | 0.98 |

Single-user latency, extractive: p50 ≈ 36 ms, p95 ≈ 85 ms.

holdout2 is the honest figure for question styles nobody tuned for. Expect roughly 7 in 10 such questions to have
the best article first, and about 9 in 10 to have it among the five cited.

**Answer checks** cover the 550 legal questions of the eval set:
* every answer passes the automatic checks: cited articles exist in the evidence, the language matches, no
  invented articles, length within limits;
* 539 of 550 answers (98%) cite an expected article.

**Counter-agent audit** (`scripts/counter_audit.py`, run with the counter-agent's interpreter): the red-team
auditor in `agent_couinter/` interrogates the agent with its trap suites. It verifies every citation and scores
each answer 0–100, without an auditor LLM and without the answer cache:

| Suite | Before the premise checks | Now |
|---|---|---|
| curated traps (51) | mean 65.0, 4 PASS / 17 FAIL | mean 77.8, 17 PASS / 3 FAIL |
| saved failures (22) | mean 62.5, 1 PASS / 8 FAIL | mean 79.3, 8 PASS / 0 FAIL |
| **blind vault** (68; never shown while developing) | mean 69.3, 15 PASS / 16 FAIL | **mean 77.1, 26 PASS / 6 FAIL** |

* fabricated-citation traps: mean 39 → 88;
* repealed-norm traps: mean 53 → 89.

The auditor gives extractive answers at most 6 of its 15 cross-lingual points, so without an LLM key a PASS needs
an almost perfect answer; many answers are therefore PARTIAL. The deploy workflow runs the same audit against the
deployed agent.

**Load test** (`scripts/load_test.py`) setup:
* server: Docker-equivalent, 1 worker, `AGENT_THREADS=4`, `SQLITE_READER_MMAP_MB=0`;
* machine: 2 vCPU, mock LLM;
* traffic: 50% streaming; the pool has 646 questions, so ~60% of answers came from the cache.

| Users | Throughput | Errors | `/api/ask` p50 / p95 | First SSE event p50 / p95 | Peak RSS |
|---|---|---|---|---|---|
| 20 | 74.6 req/s | 0 | 36 / 804 ms | 47 / 276 ms | 229 MB |
| 50 | 84.7 req/s | 0 | 47 / 1845 ms | 77 / 668 ms | 239 MB |

Render Starter has 0.5 CPU, so expect roughly a quarter of this throughput there; the memory figures carry over.
LLM answers add the model's own time on top (Gemini Flash typically starts streaming in 1–2 s). Re-run the
script against your deployment to get real numbers.

## Limitations

* **Not legal advice.** The agent quotes and explains the law. For disputes with real stakes it points the user
  to a lawyer or the competent body.
* **Unseen phrasings are weaker:** see holdout2 (0.68 / 0.89). Paraphrased civil and procedural questions are
  the weakest area.
* **Sync not yet run live.** The lex.uz sync is tested on recorded HTML fixtures only; it has never run against
  live lex.uz from the development environment. The first scheduled run fills `lex_sync_*`. Until then decrees
  and resolutions are limited to what the bundled corpora contain. No open dataset of decrees or Supreme Court
  plenum resolutions exists.
* **English.** No official English texts exist. English questions are bridged to Russian statute terms, and
  answers quote the Russian or Uzbek text.
* **Figures need manual updates.** When a decree changes them (BHM, minimum wage, CB rate), edit
  `data/corpus/practical_facts.json`. Every entry lists its source and effective date. The 2027 Hayit dates are
  provisional until the official decision.
* **Extractive mode has limits.** It quotes the most relevant sentences; it does not reason over complex,
  multi-party facts. A Gemini key gives fuller answers.
