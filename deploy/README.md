# Deploying LexHack

The public product is **haqli** (the citizen web app with its AI-lawyer chat) backed by the **legal agent**.
Both run on Render as Docker web services in Frankfurt:

| Service | Source | What it serves |
|---|---|---|
| `haqli` | `haqli/Dockerfile` (root dir `haqli/`) | React app + FastAPI API on one origin; `/api/agent/*` proxies to the agent |
| `lexhack-agent` | `agent/Dockerfile` (root dir `agent/`) | Legal agent API (`/api/ask`, `/api/ask/stream`, `/api/health`); the index is built into the image |

The browser only talks to haqli. haqli calls the agent server-to-server (`AGENT_BASE_URL`), with its own guest
sessions and per-user rate limits. The counter-agent (`agent_couinter/`) is a test tool: it audits the agent before
release and is not part of the user-facing path.

## Deploy or update

1. Repository secrets (recommended): add `RENDER_API_KEY` (and optionally `GEMINI_API_KEY`) under
   **Settings → Secrets and variables → Actions**.
2. Change `deploy/request.json` (for example bump `nonce`) and push, or run the **deploy** workflow by hand.

The workflow (`.github/workflows/deploy.yml`) runs `deploy/render_stack.py`, which creates missing services and
updates existing ones (secrets are generated once and kept). It waits until every deploy is live, then runs
`deploy/smoke.py` against the live URLs and the counter-agent suites against the deployed agent
(`agent/scripts/counter_audit.py`). Results are in the job summary and the `deploy-results` artifact.

Without repository secrets the workflow waits for a one-time sealed handshake (`deploy/handshake.py`). The run
publishes an ephemeral public key as a commit status. The deployer encrypts the token for that run only
(`python deploy/handshake.py seal --repo … --run-id … --sha …` with the token in the environment) and pushes
`deploy/sealed/<run id>.json`. Only that run can decrypt it, and the token never appears in plain text in the
repository or the logs.

## Plans and data

`deploy/stack.json` asks for the Starter plan (always on, 512 MB) and a 1 GB disk for haqli's SQLite database,
uploads and PDFs. If the Render workspace has no payment method, the services are created on the free plan
instead. Free instances sleep after 15 idle minutes, so the first request then takes up to a minute, and haqli's
data is reset on every deploy. The result file records which plan each service got.

Settings that matter:
* agent: `SQLITE_READER_MMAP_MB=0` and `AGENT_THREADS=4` keep it at about 235 MB RSS. `GEMINI_API_KEY` (optional)
  switches answers from extractive to LLM-written.
* haqli: `AGENT_BASE_URL` points at the agent. `PUBLIC_BASE_URL` and `CORS_ORIGINS` default to Render's external
  URL. `JWT_SECRET`, `FERNET_KEY` and `ED25519_PRIVATE_KEY_B64` are random per deployment and stay stable.
