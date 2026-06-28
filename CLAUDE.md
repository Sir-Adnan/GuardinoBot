# CLAUDE.md — GuardinoBot

> Guide for Claude Code in this repo. Read before changing anything. Keep changes safe, targeted,
> modular, token-efficient. (English on purpose — fewer tokens; bot UI strings stay Persian.)

**Docs map** — this file = stable rules, auto-loaded every session (keep it lean). Read the rest on demand:

- `ROADMAP.md` — the changing plan (phases, status, backlog). Read when picking up a roadmap item.
- `docs/architecture.md` — directory map, data models, commands/installer.
- `docs/panels.md` — multi-panel adapter (Marzban/PasarGuard/Guardino), differences table, decisions.
- `docs/webpanel.md` — web-panel design spec (stack, theme, menu, UX rules).
- `README.md` — public docs.

---

## Token economy (most important — always)

Max quality, min tokens. The repo is large; blind/whole-file reads are banned.

**Read/Search**
- Never read a whole dir or big file "to be safe". Grep/Glob to the exact spot, then Read with `offset`/`limit`.
- Do NOT read these unless strictly required (100KB+, repetitive): `marzban_client/`, `Dashboard-Example-Theme-UI/` (visual-only mockup — theme captured in `docs/webpanel.md`), and `docs/references/upstream-apis/*.json` (vendor specs Marzban/Pasarguard/Guardino/NOWPayments/Plisio, 100–760KB — **parse with a `python -c json` script to the one endpoint you need; never Read whole**). For panel behavior read `app/panels/base.py`, not the raw spec.
- Don't read all of `migrations/models/`; only the one you need.
- For codebase-wide search where you only need a conclusion, use the `Explore` subagent so raw output stays out of context.

**Edit**
- Small change → `Edit`, not full `Write`. Read a file once before editing; don't re-read to "confirm" after a successful edit.
- Batch independent edits to one file in one message; `replace_all` for a repeated identical pattern.
- Match surrounding style; never rewrite unrelated sections.

**Replies** — short and direct; don't re-summarize what's settled. When the decision is clear, act — one recommendation, not a long option list. Don't echo tool output. Plan + confirm before expensive work (big refactor, client regen, whole-file rewrite).

**Parallelism:** send independent tool calls together in one message.
**Bot runtime cost:** batch panel API calls (`get_users` with a username list); no per-item loops; use Redis cache; don't refetch large remote user lists.

---

## Never auto-run heavy commands

After a normal edit, **never** auto-run: `docker compose up/build/down/logs`, `docker compose down -v`, `pip install …`, `aerich migrate/upgrade/init-db`, `python -m compileall .`, `make generate-client`, `openapi-python-client update`.

Run a heavy command only when the user types exactly one of: `FULL TEST`, `FULL BUILD`, `DEPLOY CHECK`. **Destructive** (never without an explicit request — they wipe DB/Redis/volumes): `docker compose down -v`, `docker volume rm`, `docker system prune`. Before any long command, say why and get confirmation.

**Targeted checks (default):** small Python change → that file only (`python -m py_compile path/to/file.py`); a few related files → just those; whole-repo compile only on explicit request. Missing local dependency → report and ask, don't auto-install.

---

## Project goal & status

**GuardinoBot** — a Telegram subscription-sales bot (proxy/VPN), **proprietary**. Repo <https://github.com/Sir-Adnan/GuardinoBot>; owner **UnknownZero**. UI language is **Persian** (keep user-facing strings Persian unless asked).

- **Naming:** official name **GuardinoBot**. Legacy brand strings (`marzbot`/`Marzdemo`) still linger — migrate gradually. Don't change DB table/column names without a migration + approval.
- **Status:** core runs on **Marzban** (kept as a stable **legacy** path, no new dev); new development targets **PasarGuard** + **Guardino Hub** as primary sales panels — connect **exactly like Marzban** (same create/renew/manage flow). See `docs/panels.md`.
- **Web panel** for admin + resellers, separate from the Telegram UI → `docs/webpanel.md`.
- **Two deploy modes:** (a) **owner self-host** — owner runs their bot + own panel(s); (b) **Guardino reseller (multi-tenant)** — a hub reseller runs an instance logging in with their own reseller user/pass via `/api/v1/reseller/...`; the hub owns base pricing/wallet, the bot adds a resale margin.

Verify current code before assuming a path, model name, DB table, migration state, or runtime behavior.

---

## Architecture & stack

| Area | Tech |
|---|---|
| Bot | aiogram 3.4.1 (**polling**) |
| Lang/runtime | Python 3.11 on Docker (`python:3.11-alpine`) |
| DB | MariaDB/MySQL via **Tortoise ORM 0.20** + **aerich** |
| Cache/queue/state | **Redis** — FSM, APScheduler jobstore, cache |
| Scheduler | APScheduler (`AsyncIOScheduler` + RedisJobStore) |
| Web server | aiohttp (`app/views`) — payment IPN + panel webhooks on `WEBAPP_PORT` (3333) |
| Web panel | **FastAPI** (`app/api/`, JWT, separate process — must NOT import `app.main`) + **React/Vite/Refine/AntD** (`webpanel/`) → `docs/webpanel.md` |
| Panel layer | **`app/panels/`** neutral adapter → `docs/panels.md` |
| Config | `python-decouple` from `.env` (`.env.example`) |
| Crypto | `pycryptodomex` + `SECRET_KEY_STRING` (`PasswordField`) |

Entry: `bot.py` → `app/main.py:main()`. **Full directory map / data models / commands → `docs/architecture.md`.**

High-level tree: `app/{main,marzban}.py · panels/ · api/ · handlers/{admin,user}/ · keyboards/ · models/ · plugins/payment/ · jobs/ · middlewares/ · utils/ · views/` · `webpanel/` · `marzban_client/` (gen) · `migrations/` · `docs/`.

---

## DB & migrations (aerich)

- Every model change **needs a migration**: `aerich migrate` → `aerich upgrade` (applied in `prestart.sh` on start). Don't auto-run aerich; explain first, then ask.
- Keep migrations backward-compatible and additive. **Without explicit approval, never:** drop column/table, delete rows, reset reseller balance/data, rewrite proxy/user ownership, or rewrite financial history.
- For M2M / model changes, mind the `_m2m_order` pattern + `describe` override in `models/__init__.py` (aerich workaround).
- Panel migrations `46_*`/`47_*` are additive (details in `docs/architecture.md`).

---

## Safety — read every time

**Payment & financial.** Be very careful with balance, invoice, transaction, gateway, callback, order state, purchase/renew, refund, failed payments.
- Don't rewrite financial history; don't create duplicate transactions/invoices.
- Payment callbacks must be **idempotent** — a callback twice must not double-credit.
- All crypto IPNs MUST verify the provider signature **mandatorily** (no secret → reject; a missing check is a self-credit forgery hole). Balance credits on `transaction.status = finished` via `Sum("amount")`, so **never mark finished on a mismatch (under/over-paid) callback** — flag it for manual review.
- Never show gateway secrets or raw gateway errors to the user.

**Secrets & bot.**
- Never show internal errors/traces to the Telegram user. **Never log:** bot token, payment/panel tokens, `DATABASE_URL`, credentials, API keys, private user data.
- Keep sensitive values encrypted in DB (`PasswordField`). Mind admin/reseller-only commands, force-join, callback authorization, FSM/Redis state, payment confirmation, proxy renew/reset/delete. Preserve existing conversation flow when editing a handler unless a redesign is asked.
- Don't commit secrets. Never expose `.env`/`.env.*`, `BOT_TOKEN`, `DATABASE_URL`, `SECRET_KEY_STRING`, gateway creds, panel tokens, Guardino API key, Redis/MariaDB creds. Keep sample files committed; new env → register in `config.py` + `.env.example` with an empty/safe value.

**Production data.** May deploy with real users/payments/panels. Don't make changes that could delete/reset/overwrite/duplicate/detach/corrupt production data. Recommend a backup before sensitive changes. Don't run backup/migration/reset/cleanup/destructive commands on production unless explicitly asked.

---

## Coding conventions

- **async/await** everywhere; no blocking sync in handlers/jobs/views.
- Telegram handlers do I/O only; business logic in services/helpers; panel logic inside adapters (`docs/panels.md`); gateway logic inside payment modules.
- User strings are **Persian**, mostly in `app/utils/texts.py` (reloadable from Redis); runtime settings in `app/utils/settings.py`.
- Keyboards in `app/keyboards/` mirror `handlers/`; add the matching keyboard when you add a handler.
- Admin handlers register via `*_command` + docstring for auto-help (`generate_commands_help`).
- Money in **toman**, volume in **bytes**.
- Handle panel errors via `PanelError`/`PanelAuthError` (+ `status_code`) (409 retry pattern in `purchase.py`).
- Don't hand-edit generated code; don't log sensitive data.

---

## Git

- The user usually commits manually via VS Code. You may inspect status/diff, but **no commit/push/tag/branch change** unless explicitly asked.
- Before suggesting a commit: `git diff --check` + `git status --short`; summarize changed files + propose a message.
- Don't auto-run: `git commit/push/tag/checkout/switch/branch`.

---

## Before finishing a change

Report: what changed, what was checked, what was **not** checked, whether a migration / Docker rebuild / manual test is needed.
- Model changed → create a migration and announce it. New env → `config.py` + `.env.example`. New dependency → `requirements.txt` (pinned) + announce rebuild.
- Keep multi-panel points behind the interface; don't import `marzban_client` in new code.
- If you didn't run a full build, say so. Prefer small backward-compatible changes. Don't invent details; check the repo. When unsure about architecture/migration/Docker/payment/panel, ask first.

---

## Backlog

The live backlog (phases, status, decisions) lives in **`ROADMAP.md`** — read it when you pick up an item; don't grow a list here. **Broadcast** is resolved (non-blocking worker `app/utils/broadcast.py`). Crypto gateways, offline gateway, web gateway-config, admin glass buttons, etc. → see ROADMAP.
