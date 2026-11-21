# haqli — Haqqingiz hujjat bilan

**Telegram Mini App + FastAPI Backend + Deterministic Legal Rules Engine + Recognition Engine** for the Republic of Uzbekistan (Specification v2.1).

Haqli turns everyday legal pain in Uzbekistan into court-ready documents in under 60 seconds:
- **Himoya (Dispute Engine):** Deterministic `Decimal` legal math from versioned JSON constants (`constants.json`), exact BHM ratios, consumer/labor penalties, limitation windows, official pre-trial demand (**Talabnoma**) PDF, and copyable `my.gov.uz` state-organ complaints.
- **Tilxat (Safe P2P Receipts):** Loan/deposit/service receipts with live Civil Code Art. 108 written-form warning (`> 10 BHM`), Fernet-encrypted passports, real-time WebSocket Telegram co-confirmation, SHA-256 hash chain, and Ed25519 cryptographic seals.
- **Tanib olish (Recognition Engine):** Multi-mode document, receipt, ICAO 9303 TD3 passport MRZ (with strict check digits — image never persisted), voice intake, and PDF seal authenticity verification (`/v/{doc_id}`).
- **Skaner (Contract Auditor):** Deterministic 7-rule red-flag scanner for rental, microloan, and employment contracts with safe replacement clauses and contextual grounded clause Q&A.
- **Radar (Law-Change Alerts):** Profile-tagged legislative alerts deep-linking directly into Himoya/Tilxat wizards.
- **Advokat (MSO Workspace):** Invite-gated partner workspace (`HAQLI-ADV-2026`) delivering 1-page briefs to independent licensed advocates with client contacts unlocked only after acceptance.

> **Legal Data Integrity & E-Signature Transparency:**
> - All seeded legal constants and articles start as `status: "needs_review"` and display an amber chip + PDF footer until verified by an Uzbekistan lawyer (`python scripts/legal_audit.py`).
> - Telegram co-confirmation + SHA-256/Ed25519 seals are presented strictly as *simple electronic confirmation with evidentiary support*, never equivalent to qualified EDS (ЭЦП) or notarization.

---

## Quick Start (Zero API Keys Required — `DEMO_MODE=true`)

### Option 1: Local Dev (No Docker)

1. **Start Backend (port `8002`):**
   ```powershell
   cd d:\Hackathon\LexHack\haqli\backend
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   uvicorn app.main:app --reload --port 8002
   ```
   *(Or reuse the existing Python 3.12 venv at `d:\Hackathon\LexHack\agent\.venv\Scripts\python.exe` after installing `backend/requirements.txt`.)*

2. **Start Frontend (port `5173`, proxying `/api` & `/ws` to `:8002`):**
   ```powershell
   cd d:\Hackathon\LexHack\haqli\web
   npm install
   npm run dev
   ```
   Open **http://localhost:5173** in your browser (or via Telegram Bot Mini App).

### Option 2: One-Command Docker Compose

```bash
cd haqli
docker compose up --build
```
Open **http://localhost:8080** (Caddy proxies `/api`, `/ws` to FastAPI `:8002` and serves the built React app).

---

## Verification & Test Commands

```powershell
# 1. Backend unit, Hypothesis property, PDF Cyrillic glyph, API integration & recognition eval tests
cd d:\Hackathon\LexHack\haqli\backend
pytest -q

# 2. Audit unverified legal data entries (Rule 3)
python ..\scripts\legal_audit.py

# 3. Verify PDF Unicode Cyrillic glyph coverage (Ў Қ Ғ Ҳ)
python ..\scripts\gen_fonts_check.py

# 4. Frontend typecheck, unit tests & production bundle
cd d:\Hackathon\LexHack\haqli\web
npm run typecheck
npm test
npm run build
```

---

## Key Environment Variables (`.env`)

| Variable | Default | Purpose |
|---|---|---|
| `DEMO_MODE` | `true` | Enables deterministic offline fallbacks, demo login, and simulated 2nd-party signing |
| `APP_PORT` | `8002` | FastAPI listen port |
| `DATABASE_URL` | `sqlite+aiosqlite:///./storage/haqli.db` | Async SQLite (dev) or `postgresql+asyncpg://` (prod) |
| `PUBLIC_BASE_URL` | `http://localhost:5173` | Base URL embedded in PDF verification QR codes (`/v/{doc_id}`) |
| `TELEGRAM_BOT_TOKEN` | `""` | Telegram Bot API token for HMAC `initData` validation & notifications |
| `ADVOCATE_INVITE_CODES` | `HAQLI-ADV-2026` | Comma-separated invite codes unlocking Advokat MSO mode |
| `LLM_PROVIDER` | `none` | Optional: `none`, `openai`, `gemini`, `anthropic`, `local` |
| `FERNET_KEY` | auto-dev | Base64 Fernet key encrypting sensitive passport & OCR fields at rest |
| `ED25519_PRIVATE_KEY` | auto-dev | Base64 Ed25519 private key signing document verification seals |

---

## 3-Minute Live Demo Script

1. **Himoya (0:00–0:50):** Tap **Iste'molchi huquqi**, click **Hujjat / Ovoz orqali to'ldirish** → **Chek** → **Namuna bilan sinash** → **Tanib olishni boshlash** → **Himoya ustasiga o'tkazish**. Complete wizard → observe deterministic `1% / kun` penalty formula, Case Strength gauge, `needs_review` citations, simulated payment, and downloadable Cyrillic/Latin sealed PDF.
2. **Tilxat + MRZ + Verify (0:50–1:45):** Switch to **Tilxat** → tap **Pasport MRZ skanerlash** → test ICAO 9303 check-digit extraction → enter `8 000 000 so'm` (triggers live Civil Code Art. 108 `> 10 BHM` warning) → create Tilxat → tap **DEMO: 2-tomon sifatida tasdiqlash** → download sealed PDF and verify via **Tanib olish → PDF Tekshir**.
3. **Skaner & Radar (1:45–2:25):** Open **Skaner** → tap the risky **Mikroqarz shartnomasi** sample → inspect red flags, copy safe alternatives, and ask a grounded question via **Shu band haqida so'rash**. Open **Radar** → toggle profile tags and run **DEMO: Yangi ogohlantirish yaratish**.
4. **Advokat MSO (2:25–3:00):** Toggle **Advokat** in the top header → enter `HAQLI-ADV-2026` → inspect pre-seeded 1-page briefs (note masked client contact) → click **Ishni qabul qilish** to unlock the client contact.

---

## Recognition Engine ("Tanib olish") v1.0 Add-On

### Environment Flags

| Variable | Default | Options / Purpose |
|---|---|---|
| `RECOGNITION_OCR` | `auto` | `off \| paddle \| tesseract \| vision \| auto` — controls OCR engine cascade |
| `RECOGNITION_STT` | `auto` | `off \| local \| cloud \| auto` — controls voice STT engine cascade |
| `WHISPER_MODEL` | `large-v3` | `faster-whisper` model size (`base`, `medium`, `large-v3`) |
| `WHISPER_COMPUTE_TYPE` | `int8` | CPU quantization (`int8`, `float32`) |
| `RECOGNITION_OCR_CONCURRENCY` | `2` | Global concurrent OCR semaphore limit |
| `RECOGNITION_STT_CONCURRENCY` | `1` | Global concurrent STT semaphore limit |
| `RECOGNITION_RETENTION_HOURS` | `24` | Auto-purge TTL for unattached uploads and recognition jobs |

### Installing Optional Local OCR / STT Models

1. **System packages (Ubuntu / Docker):**
   ```bash
   sudo apt-get install -y ffmpeg tesseract-ocr tesseract-ocr-uzb tesseract-ocr-uzb-cyrl tesseract-ocr-rus
   ```
2. **Optional Python ML backends (when enabling local OCR/STT):**
   ```bash
   pip install paddlepaddle paddleocr pytesseract opencv-python-headless pypdfium2 faster-whisper
   ```
   *(All flows continue working offline without HTTP 500 when any engine is omitted or set to `off`.)*

### Running the Recognition Evaluation Harness & CI Gates

```powershell
cd d:\Hackathon\LexHack\haqli\backend
python -m app.engines.recognition.eval
python -m app.engines.recognition.eval --json
pytest tests/recognition -q
```

### Adding Real Voice or Document Fixtures Locally

Keep real user/team audio recordings and scanned documents **out of git** (add them under `backend/tests/recognition/fixtures/local/` which is gitignored) and load them into `eval/runner.py` when benchmarking real-world WER/CER.

### Recognition Demo Script

1. **Traffic Fine → Prefilled Appeal:** Tap **Tanib olish** → **Hujjat** → **Namuna bilan sinash** → inspect extracted plate `01 A 777 AA`, fine amount, and `traffic_appeal_window` → tap **Himoya'da davom etish**.
2. **Spoken Loan → Prefilled Tilxat:** Tap **Tanib olish** → **Ovoz** → record voice or tap **Namuna bilan sinash** → verify parsed Uzbek numeral (`besh million` → `5 000 000`), date, counterparty & `lender` role → tap **Tilxatni to'ldirish**.
3. **PDF Authenticity Check (Valid vs. Tampered):** Download any signed Tilxat PDF → open **Tanib olish → PDF Tekshir** → upload the PDF (`VALID`) → alter one digit in the PDF amount and re-upload (`TAMPERED`, listing `amount` in `mismatchedFields`).
