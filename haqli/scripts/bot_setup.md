# Haqli Telegram Bot & Pre-Launch Setup Guide

## 1. Pre-Launch Name Hygiene Checklist
- [ ] Run trademark clearance search at the **Intellectual Property Agency of the Republic of Uzbekistan** (Nice classes **9**, **42**, **45**) for `Haqli` / `Ҳақли` / `Хакли`.
- [ ] Reserve Telegram handles: `@haqli_bot`, `@haqli_uz`, `@haqli_support`.
- [ ] Reserve domains: `haqli.uz`, `haqli.app`.
- [ ] Document visual & market differentiation from **HAQQ Legal AI** (Lebanon — different jurisdiction/market, similar phonetics; ensure distinct teal rounded-square checkmark emblem and Uzbekistan focus).
- [ ] Complete legal counsel sign-off on all entries listed by `python scripts/legal_audit.py` before switching `status` from `needs_review` to `verified`.
- [ ] Review hosting localization & State Register compliance under Uzbekistan Law O'RQ-547 (Art. 27-1, Personal Data).

## 2. BotFather Setup Steps
1. Open `@BotFather` in Telegram and run `/newbot`.
2. Name: `Haqli — Huquqiy Hujjatlar` · Username: `@haqli_bot`.
3. Save the bot token into `.env` as `TELEGRAM_BOT_TOKEN=...`.
4. Configure the Mini App:
   - Run `/newapp` → select `@haqli_bot` → title `Haqli` → short name `app` → Web App URL `https://haqli.uz` (must be HTTPS — Caddy handles automatic TLS).
5. Configure the persistent Menu Button:
   - Run `/setmenubutton` → select `@haqli_bot` → URL `https://haqli.uz` → button text `Haqli ochish`.
6. Deep links used by Haqli:
   - Tilxat counterparty signing: `https://t.me/haqli_bot/app?startapp=sign_<token>`
   - Public PDF authenticity verify: `https://haqli.uz/v/<doc_id>`
7. Verify production security:
   - Set `DEMO_MODE=false`
   - Set strong random `JWT_SECRET`, `FERNET_KEY`, and `ED25519_PRIVATE_KEY_B64`
   - Restrict `CORS_ORIGINS` to `https://haqli.uz`
