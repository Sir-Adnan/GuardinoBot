# ROADMAP — GuardinoBot

> Living plan: phases, status, backlog. **CLAUDE.md** = stable "how to work here"
> (auto-loaded every session, keep it lean). **README.md** = public/user docs.
> **This file** = the changing roadmap — read it only when working on a roadmap item.
> English on purpose (fewer tokens). Bot UI strings stay Persian.

## How to use this file
- New idea → drop a one-liner under **Backlog**. When we commit to it, promote it to a
  **Phase** (own `### Phase N` block: goal, scope, files, decisions) and move to **Now**.
- A phase ships → compress it to one ✅ line under **Done log** (keep just enough so nobody
  re-scans the repo or rebuilds it), and delete its detailed block.
- Status markers: `[ ]` todo · `⏳` in progress · `✅` done · `⚠️` caveat · `⛔` deferred.
- Keep lines short and scannable. Don't paste code here; point to files (`path:sym`).

---

## Now — crypto gateways + payment config (security-first)

The big web-panel + bot-UX push is **largely shipped**: P5 (incl. create-from-scratch), P6, P7,
P8, P9 (incl. Jalali picker), P10 (Discounts/Texts/Audit/Automation-monitor/Force-join), P11
(foundation + most polish), P12 (subscription bar, account page, empty-state CTA, onboarding,
insufficient-balance clarity), P13 (alerts v2 complete). Editor UX (texts insert/preview, button
grouping) + payment-method buttons customizable. Details in **Done log** + the **Pxx blocks**.

**Current focus (in order):**
0. ✅ **Bugfix — Plisio/offline buttons were dead in the bot.** Each gateway must replicate the full
   handler surface (every plugin does its own; there is no generic one). Plisio/offline only had the
   final `SelectPayAmount` handler, so the **charge-account** flow (`ChargePanel.Callback`, no amount)
   + custom-amount sub-flow had no handler, and `select_*` only accepted `CallbackQuery`. Added to both:
   `charge` (ChargePanel entry → amount menu), `custom_amount` (amount==0 prompt) + FSM message capture,
   made the final handler dual-type (`CallbackQuery | Message`). Also the in-bot **⚙️→تنظیمات**
   `pm:settings:{plisio,offline}` button was dead → added a minimal admin screen (masked summary +
   enable/disable toggle, guarded against enabling a misconfigured gateway + "configure fully in web").
0b. ✅ **Bugfix — offline proof loop + reject-after-approve.** (a) The proof step required TXID **and**
   screenshot in one message, so hash-then-screenshot looped forever; now it **accumulates** across
   messages in any order (text=hash, photo=screenshot, photo+caption=both), asks only for what's
   missing, validates the hash, and resets stale progress on a new session. (b) The admin card is now a
   **stateful** keyboard (`OfflineReviewKb`) like card-to-card: rejecting an **already-approved** payment
   asks for confirmation then **reverses the credit + removes the subscription** via the shared
   `revoke_activated_transaction` (handlers split into approve / reject / reject_cancel; web-queue path
   keeps the `apply_offline_review` wrapper). Balance nets back correctly (no double-credit / negative).
1. ✅ **Crypto v2 (Plisio + NowPayments) — reworked by owner, now live.** Both gateways moved to a
   shared **rate service** `crypto/rates.py` (Nobitex USDT/Toman, **Redis-cached** TTL
   `rate_cache_seconds`, `Decimal`, ROUND_UP, `usdt_margin_percent`, `manual_usdt_toman_rate` fallback;
   `get_usdt_toman_rate` / `calculate_payable_usdt` / `PaymentRateError`). Plisio now creates **crypto
   `currency+amount`** invoices (`default_currency`, `currency_codes()`/`invoice_currency()`,
   `expire_min`), shows the payable USDT + rate, has **🔄 check / ❌ cancel** buttons (premium-styled),
   and an idempotent finalizer `crypto/plisio_service.py` (`finalize_plisio_payment` +
   `manual_approve_plisio_payment`, shared by the `/plisio` IPN and the manual-check button; mismatch
   never auto-credits). NowPayments got the same rate service + `crypto/nowpayments_service.py` + premium
   buttons + tracking code + success/cancel URLs. New env: `PUBLIC_BASE_URL`, `PLISIO_DEFAULT_CURRENCY`,
   `PLISIO_EXPIRE_MIN`, `PAYMENT_RATE_PROVIDER`, `PAYMENT_RATE_CACHE_SECONDS`, `PAYMENT_USDT_MARGIN_PERCENT`,
   `MANUAL_USDT_TOMAN_RATE`.
   ✅ **Bugfix (this session): NowPayments invoice crashed** with `ValueError: Cannot specify ',' with 's'`
   — `ShowInvoiceText._allowed_variables["AMOUNT_DOLLARS"]` was `format_number` but the value is a
   pre-formatted string from `_format_decimal`; changed the formatter to `str` (nowpayments.py).
   ✅ **Bugfix (this session): NowPayments "amountTo is too small"** — the hosted invoice let the customer
   pick USDT-TRC20 (high min/fee). Added a configurable **`pay_currency`** (NowPayments `Settings` +
   `create_invoice` param + web gateway field, default `usdtbsc`=BEP20, env `NP_PAY_CURRENCY`); empty =
   customer picks. Fixes the coin on the page to the low-min BEP20.
2. ✅ **Web payment-gateway config** — `GET/PATCH /payment-gateways` (super-admin) reads/writes the
   `payment_*` BotSetting JSON; **secrets masked** (read = is_set + last-4; empty on save = no change,
   never wipes a key), upsert (handles `payment_plisio` pre-restart), `settings:dirty`, audited
   (field names only). Web page `pages/gateways` (NowPayments + Plisio: enabled/title/min/api_key/
   currency/rate fields). ⚠️ enabling **Plisio** still needs a bot restart (to load its plugin +
   create the row); setting the **NowPayments IPN secret** here unblocks crypto crediting.
3. **Offline crypto gateway** — wallet-per-coin (USDT-BEP20/TRX/TON/…), customer picks + sends TXID+screenshot,
   manual admin confirm + optional on-chain auto-check. (needs a model + additive migration)
4. **Admin glass buttons in the bot** — fix/extend the ⚙️ admin-panel inline buttons.
5. Polish leftovers: theme presets/density done; remaining = micro-interactions, broader audit,
   detail-page tabs already done. Deferred infra: brand migration, aiogram 3.4.1 bump, Guardino reserves.

Immediate / carry-over (do anytime):
- [ ] Verify Phase 3/4 premium rendering on a real deploy (Premium owner); if the fields are
      dropped → raw-payload sender (httpx → Bot API) or aiogram bump.
- ✅ Bug-fix plan `delightful-crafting-micali.md` — **all done & verified on deploy**: PasarGuard
      add-server `is_sudo` (panel_type branch → `pg_validate_token`), edit-service "no protocol"
      (Marzban-only inbounds check), Guardino sub-day expiry (block <1d + ceil/min-1 net), FSM clear
      + `ReplyKeyboardRemove` on confirm, month=31d, panel-aware admin service/panel menus.

## Carry-over backlog (folded into the phases below)
- ✅ **Crypto gateways** (payment-critical, security-first) — Plisio + NowPayments v2 live (see Now #1):
  - ✅ **NowPayments IPN security fix** — signature is now **mandatory** (no secret → reject; closes a
    forgery/self-credit hole), constant-time compare, proper HTTP responses, less logging
    (`crypto/views.py`). **Owner action: set the NowPayments *IPN secret* in the bot** or crypto
    crediting (correctly) won't run. Endpoints verified unchanged vs the live v1 API — any create-side
    failure needs the exact `NowPaymentsError` body from logs.
  - ✅ **Plisio gateway v2 (done)** — crypto `currency+amount` invoices (`GET /invoices/new`,
    `https://plisio.net/api/v1`). `crypto/plisio.py` client + `Settings` (`payment_plisio`,
    `default_currency`/`currency_codes()`/`invoice_currency()`/`expire_min` + rate fields) +
    `verify_callback` (HMAC-SHA1 over PHP-`serialize()`, byte-exact self-tested); `Provider.plisio`
    (VARCHAR(11) → **no migration**). Create handler `plisio_payment.py` (premium **pay/check/cancel**
    buttons) uses `rates.py` to price in USDT and shows the payable amount. Idempotent finalizer
    `crypto/plisio_service.py` shared by the `/plisio` IPN (mandatory api-key + `verify_hash`, credit
    only on `completed`, **mismatch never auto-credits** → super-user alert) **and** the manual-check
    button (`get_operation`/`manual_approve_plisio_payment`). Web-configurable.
  - ✅ **Web payment-gateway config** — `GET/PATCH /payment-gateways` + `pages/gateways` (super-admin):
    NowPayments + Plisio enable/title/min/keys; secrets masked (read = is_set+last4, empty save = no
    change), upsert, `settings:dirty`, audited (names only). Set the NowPayments IPN secret here.
  - ✅ **Offline crypto gateway** — **no migration** (reuses `CryptoPayment` + `Provider.offline` +
    `extra_data`). Config: `payment_offline` Settings (`offline/offline.py`: `CoinWallet` list +
    `enabled_coins`/`coin_by_code`, `require_screenshot`), API `GET/PUT /payment-gateways/offline`
    (super-admin, coins list, upsert, audited), web editor `OfflineGateway`. **Bot flow**
    (`offline/handlers.py`, registered in handlers): pick coin → wallet **+ QR** (lazy `gen_qr` to dodge
    the qr→app.main cycle) → customer sends TXID(+screenshot) → pending `CryptoPayment(offline,
    waiting)` + Transaction(waiting) + super-admin **Approve/Reject** card. Approve → `finished` (the
    only credit step; balance = Σ finished `amount`) + activate_service; Reject → `rejected` + user
    notified. **No auto-credit**; idempotent (already-finished guard); cancel button; command-guarded
    FSM. ✅ **Web pending-review** — `apply_offline_review` factored as the single credit path (used by
    the bot card AND the web); `process_offline_review_queue` drains a Redis list (`offline:review:queue`)
    in the 15s sync poll so web approve/reject runs in the BOT (credit+notify+activate). API
    `GET /offline/pending`, `GET /offline/{id}/screenshot` (proxied via the bot's `get_file`),
    `POST /offline/{id}/review` (queues). Web `OfflinePending` table (approve/reject queued + screenshot
    viewer via auth'd blob). **Remaining (optional): on-chain auto-check** (TronGrid/BscScan/TON; the
    `auto_check` flag is modelled).
  - ✅ **Admin glass buttons (⚙️ panel)** — the 8 `AdminPanel` buttons (web-panel/servers/services/
    service-menus/users/payments/settings/status) now route through `premium_button` with `admin_*`
    keys (registered in `INLINE_BUTTONS`), so they're rename/emoji/colour-customizable in the web
    Buttons editor under a new **"Admin panel"** category. (Sub-menu admin keyboards = future extend.)
  - [ ] Extend gateway-config to the rial/card gateways; on-chain auto-check; web pending-offline review.
- ✅ **Broadcast → non-blocking worker [§17.1]**: `app/utils/broadcast.py` (throttled, `TelegramRetryAfter`
  sleep-retry, marks `blocked_bot`, Redis progress + `resume_pending`). Web has read-only monitor/cancel.
  **Web compose/start dropped (owner decision)** — `/broadcast` + `/forward` in the bot (reply → command)
  are simpler and let the owner use Telegram's native premium-emoji editor. Not adding it to the panel.
- [ ] Guardino **reserves** + efficient paginated sync + `on_hold` create (§6 deferred).
- [ ] Brand migration `marzbot`/`Marzdemo` → Guardino (gradual; migration for DB-facing strings).
- [ ] PasarGuard native `reset_proxy_credentials` (currently raises; "smart reconnect" works).
- [ ] aiogram 3.4.1 upgrade (`parse_mode=` ctor → `DefaultBotProperties`) — testing + approval.
- [ ] Observability: structured metrics/logs for panel + gateway errors.

---

## Planned phases — web-panel maturity + bot UX (P5–P13)

> Scope rule (unchanged): web panel = manage/support/report/customize + audit, through the
> §6 adapter. **No manual sell** (provisioning a sub stays bot-only); defining plans/prices is
> management and IS allowed. Never expose panel/payment/DB credentials. Reseller scoping holds.

### P5 — Plans & Sales: full CRUD + ordering (web)
**P5a — ✅ done:** edit (all simple fields + 8 flags + reset_strategy + flow + button emoji/style),
**reorder** (↑↓ → `POST /services/reorder`, priority=index), **delete** (guarded: 409 if proxies/
reserves reference it — Proxy=SET_NULL, Reserve=RESTRICT), **duplicate** (`POST /{id}/duplicate`
clones provisioning as a non-purchaseable draft → edit; M2M not copied). `services` router gained
`GET /{id}` (ServiceDetail) + PATCH/DELETE/duplicate/reorder, all audited; web Services page = full
edit modal (GB/days inputs) + PageHeader. data_limit↔GB, expire↔days handled in the form.
**P5b — ✅ create-from-scratch:** `POST /services` (validates server + fields; provisioning stored
as-shaped) + `GET /services/provisioning?server_id=` — a **live** panel-catalog fetch (`build_panel().
get_inbounds()` with an 8s timeout; errors → non-sensitive codes). Web Services page: **New service**
button → create modal with a **server picker** that lazy-loads the catalog and a **panel-aware
provisioning picker** — Marzban inbounds (+ "all inbounds" switch) · PasarGuard **groups** ·
Guardino **nodes** (+ pricing mode) → assembles `inbounds`/`all_inbounds` or `panel_config`; audited
`service.create`. Reuses the edit modal for all other fields.
**P5b — remaining (minor):** discount/menu attach UI + true drag-and-drop reorder. (↑↓ reorder works.)

### P6 — Panels & Nodes: full CRUD (web)
**P6 core — ✅ done:** add panel (validates the connection via §6 `fetch_token`/`login` +
`validate` BEFORE saving — Marzban/PasarGuard token flow, Guardino reseller login with a clear
"disable 2FA" error), edit (re-connects + refreshes the token when host/port/https/username/
password change), delete (**blocked** if services/proxies attached — FK is CASCADE, would wipe
live subs), `link_policy` (Guardino), health + enable/disable (existing). Credentials stored
encrypted (`PasswordField`), password/token **never returned**; all audited (`server.add/update/
delete`). `servers` router gained `GET /{id}` (ServerDetail) + POST/PATCH/DELETE; web Servers page
= add/edit modal (panel picker, host/port/https, creds, link policy) + PageHeader.
**P6b — remaining:** browse PasarGuard **groups** / Guardino **nodes** endpoints (feed the P5b
service provisioning picker).

### P7 — Users 360°: detail + actions (web) — ✅ done
- **Detail page, tabbed**: Overview · Subscriptions · Transactions · Logs (Logs = super-only,
  via `/audit?target_type=user&target_id=`). List already shows id + username (search by either).
- **Overview actions**: block/unblock; **Edit** (role [super-only escalation guard], postpaid +
  credit, daily-test count, discount %, username prefix → `PATCH /users/{id}`, audit `user.update`);
  **Adjust balance** (super-only: charge→`Transaction(by_admin,finished)` / decharge→`Invoice(by_admin)`,
  mirroring the bot so stats stay exact, audit `balance.adjust`).
- **Subscriptions tab**: their proxies via `/proxies?user_id=` + enable/disable/reset/revoke/delete
  (reuses the §6-backed proxy action/delete endpoints, audited).
- Backend: `users` router gained `PATCH /{id}` + `POST /{id}/balance`; `UserDetail` enriched
  (postpaid credit, test count, discount %, prefix, parent/referrer); `audit` got a `target_id` filter.
- **Remaining (minor):** a dedicated Orders view (currently Transactions covers payments); reseller
  scoping already applies to the detail (resellers see only their subtree).

### P8 — Resellers: full management (web) — ✅ done
- **Promote** an existing user → reseller (`POST /resellers/promote` by id/@username, super-only,
  audited) from the list.
- **Detail = console** (tabbed: Overview · Sub-users · Subscriptions): edit (role/postpaid/credit
  limit/discount %/test count/prefix) + **balance adjust** — reuses the P7 `users` PATCH + balance
  endpoints (super-only, audited, same Transaction/Invoice math). Sub-users via
  `GET /resellers/{id}/children`; subscriptions via `/proxies?user_id=`.
- **Remaining (minor):** dedicated wallet/margin model beyond discount %, explicit permission
  flags, and read-only **"view as reseller"** impersonation (deferred — needs auth scoping).

### P9 — Reports & Analytics: complete + Jalali (web) — ✅ core done
- **Date range**: `/reports/summary` now takes `start`/`end` (ISO) overriding `days`; correct
  `created_at__gte/__lt` bounds + range echoed back. Web: preset Segmented (7/30/90) **+ custom
  RangePicker** + range shown in the header.
- **Metrics**: added **failed/incomplete payments** (non-finished tx in range) as a 5th KPI;
  Sales · Income · Orders · New users · Failed already covered; payment breakdown + top services.
- **Jalali display**: series tooltips + header range render via `formatDay` (P11a util) → follows
  the global calendar toggle. **CSV export** of KPIs + breakdown + series.
- **Remaining (P9b):** a true **Jalali date-picker** for selection (RangePicker is Gregorian for
  now; presets cover most cases) + Reseller/Usage/Refunds report breakdowns + Excel export.

### P10 — Finish the half-done pages (web) — ⏳ in progress
- ✅ **Discounts**: full CRUD — `discounts` router POST/PATCH/DELETE (percentage 0..100 guard,
  auto-generated code, unique-code 409, M2M-safe delete, audited create/update/delete); web page
  = add/edit modal (code·%·max-uses·expiry·flags) + delete + PageHeader. (was list + toggle.)
- ✅ **Automation**: read-only **broadcast monitor/cancel** + **alert run-now/preview/config**
  (texts·colours·cadence). **Broadcast compose/start intentionally NOT in the web** — stays bot-only
  via `/broadcast` + `/forward` (reply → command), which is simpler and keeps Telegram's native
  premium-emoji editor (owner decision).
- ✅ **Texts**: tabbed by area (general/sales/support/access/alerts) + search; per-card save +
  variables + premium-emoji helper. Backend adds `group` to each curated key.
- ✅ **Audit**: added **date-range** filter (`start`/`end`) + **CSV export** (current filters,
  up to 1000 rows) + PageHeader; detail drawer + source/search filters already existed.
- ✅ **Force-join editor** (super-admin): `GET`/`PUT /settings/force-join` read/replace the
  `force_join_chats` dict (key = chat id/@username for the membership check, value = public username
  for the join link); web = a self-contained editor card on the Settings page (add/remove rows, save
  → `settings:dirty` reload). Audited `settings.force_join`.
- **Remaining:** **payment-gateway config** (sensitive, guarded, secrets masked).

### P11 — UI/UX overhaul (web) — split foundation vs polish
**P11a (foundation) — ⏳ in progress:**
- ✅ Calendar-aware dates: `utils/datetime.ts` (Intl, no dep — Jalali/Gregorian) + header toggle;
  `fmtDate` is now calendar-aware so existing pages follow the choice; live via layout re-render.
- ✅ Font setting: `theme.FONTS` (Vazirmatn default · Vazir · Sahel · Samim · System, loaded in
  index.html) + header font picker; persisted (localStorage); applied via AntD token + body.
- ✅ `components/PageHeader.tsx` (consistent title/subtitle/actions) — adopt across pages in P5+.
- [ ] Remaining: tab/section shell + breadcrumbs adoption, dashboard widget scaffold, responsive
  table→card helper, move font/calendar defaults into a Settings "Appearance" tab (server-side).
**P11b (polish):**
- ✅ **Shared `StatCard`** — polished KPI card whose value uses the **inherited (configured) font**
  + tabular-nums (fixes the hard-coded-mono bug where dashboard/report numbers ignored the font
  picker).
- ✅ **Dashboard redesign — minimal/modern** (neumorphism dropped per owner): hover KPI cards
  (lift + shadow, **hover colour = theme accent**, gray→accent icon chips), soft 14px corners,
  configured-font numbers. **14-day bar chart** with hover tooltips + **sibling-fade** (others dim
  on hover) + Jalali axis. **Switchable summary** (Today / 7d / 30d Segmented) showing income /
  sales / orders / **GB sold** — backend `/dashboard/summary` gained `period_today/week/month`
  (`PeriodStat`: income·sales·orders·gb via `Sum(service__data_limit)`). Fixed mislabel
  (active subscriptions, not "active users"). Responsive (xs→xl).
- ✅ **Global button/link polish** (index.css): smooth transitions + subtle primary-button lift.
- ✅ **Shell redesign** (Layout.tsx): **collapsible** desktop sidebar (icon-only mini mode, persisted)
  + drawer on mobile; **consolidated "Appearance" dropdown** in the header (theme · language ·
  calendar · accent · font — declutters the toolbar) keyed to the theme accent; added a **footer**;
  responsive header (xs→xl). Dashboard ops KPIs now wrap to multiple rows on desktop.
- ✅ **Cohesion pass**: moved the shared card/chart CSS into `index.css` (`.stat-card`/`.stat-icon`
  hover-lift + theme-accent icon; `.bars`/`.chart-bar` sibling-fade). `StatCard` upgraded to that
  style; dashboard + reports now share one card + bar-chart look (reports KPIs + chart hover too).
- ✅ **List pages cohesion**: `PageHeader` (title + subtitle + search-in-extra) added to Users,
  Subscriptions, Transactions — now consistent with Services/Servers/Discounts/Resellers/Audit/Texts.
- ✅ **Config pages cohesion**: `PageHeader` added to **menus / buttons / settings / automation**
  (replacing ad-hoc `Title`/`Paragraph` headers). Buttons/Settings full-page `Spin` → **Skeleton**;
  automation `Spin` → Skeleton.
- ✅ **Font fix (IDs/numbers)**: `.mono` no longer hard-pins IBM Plex Mono — it now inherits the
  configured UI font with `tabular-nums` (fixes Users-page IDs etc. ignoring the font picker);
  automation stat numbers de-hardcoded the same way.
- ✅ **Responsive table→card on mobile**: new `ResponsiveTable` (auto-builds a stacked card per row
  from the existing `columns`, label=title/value=render; action columns → card footer) + `useIsMobile`
  hook (AntD `< md`). Adopted on Users, Subscriptions, Transactions, Services, Servers, Discounts,
  Resellers, Audit, Menus. Includes skeleton + empty states on mobile.
- ✅ **Detail pages polish** (users/resellers `show`): already tabbed (Overview / Subs / Payments /
  Logs / Children) + `PageHeader` with back button; now full-page `Spin` → **Skeleton** and inner
  tab tables → `ResponsiveTable` (mobile card view in tabs too).
- ✅ **Theme presets + density**: Appearance menu gained **one-click presets** (Emerald Dark/Light,
  Ocean Dark, Violet Dark, Rose/Amber Light — each sets accent + mode together) and a **density**
  toggle (Default / Compact via AntD `compactAlgorithm`). Both persisted (localStorage `density`);
  context gained `setMode`/`density`/`setDensity`; `makeTheme(accent, mode, font, density)`.
- ✅ **Reports redesign**: `StatCard` KPI row, gradient bar chart + **Jalali x-axis labels**,
  payment-breakdown with **% share bars**, empty states; date range + presets + CSV export kept.
- ✅ **Reports — richer stats**: added **GB sold** (range), an **All-time totals** block (total
  sales / income / orders / users / GB) and a **Subscription (proxy) stats** block (total + per
  status: active / on_hold / disabled / limited / expired with % share). Backend `/reports/summary`
  gained `gb_sold`, `all_*`, `proxies_total/active`, `proxies_by_status` (`_gb` helper via
  `Sum(service__data_limit)`; status counts loop `ProxyStatus`). CSV export includes them.
- ✅ **Jalali date-range picker**: when the calendar pref is **Shamsi**, the reports range picker
  switches to a **dependency-free** `JalaliRangePicker` (year/month/day Selects, Shamsi months) that
  emits Gregorian Dayjs — query stays Gregorian ISO. Conversion in new `utils/jalali.ts` (inlined
  jalaali-js, no new npm dep, consistent with the Intl-based `utils/datetime.ts`).
- ✅ **Panel-health + low-balance dashboard widget**: lazy, self-contained `PanelHealth` card
  (own skeleton + manual refresh) → `GET /dashboard/panel-health` live-pings each **enabled** panel
  (`build_panel().get_admin()` with an 8s timeout, concurrent via `asyncio.gather`) and reads the
  **Guardino reseller balance** (`get_balance`), colour-coded vs the warn/critical thresholds (read
  from `BotSetting`, defaults mirrored). Errors reduced to non-sensitive codes (auth/unreachable/
  error) — no panel URL/creds leak. Kept off `/dashboard/summary` so the summary stays fast.
- [ ] Remaining: micro-interactions, broader audit.

### P12 — Bot (Telegram) UX overhaul
Goal: the customer-facing bot looks premium and converts better (customers browse/buy here).
- ✅ **Subscription view — usage bar**: the proxy detail card gained a text data-usage bar
  (`▰▰▰▱▱ ۶۳٪`, Persian digits, in `<code>` for alignment) + "used / total" line (or "نامحدود ♾") +
  `max(0, …)` remaining. New `helpers.usage_bar()` / `helpers.fa_num()` (empty bar for unlimited).
  Header/usage are now built via list-join so **no stray blank lines** on unlimited plans.
- ~~Tariffs overview in the purchase list~~ — **reverted** at owner's request: the plan buttons
  already convey name·price·data·duration, so the extra text block was redundant + cluttered. The
  `purchase_show_tariffs` setting was removed cleanly (model/API/schema/web/locale; row auto-pruned
  on startup, no migration).
- ✅ **Empty-state CTA**: "my subscriptions" with no subs now shows a friendly message + an inline
  **🛒 خرید اشتراک** button (packs `Services.Callback(action=show)` → straight into the buy flow)
  instead of a dead-end toast. Admins viewing an empty child list keep the plain notice. Also fixed
  the old un-awaited `qmsg.answer(...)` returns here.
- ✅ **Account page — dashboard-style**: restructured into identity / financial / postpaid sections
  with clear separators; shows **active / total subscriptions** from the **local** `Proxy.status`
  (fixed the old "active services" label that actually counted *all* proxies) — cheap, no panel
  calls. Quick actions stay (the `UserPanel` keyboard). *Nearest expiry deferred — expiry isn't
  stored locally (panel-only), so it'd need per-panel calls.*
- ✅ **New-user onboarding**: `/start` for a user with **0 subscriptions** now follows the menu with
  a concise welcome + inline **🛒 خرید اشتراک** CTA (packs the buy callback). Cheap count, skipped on
  `start_only` deep links, no new copy/migration.
- ✅ **Insufficient-balance clarity**: the purchase confirmation now states the exact **shortfall**
  (`💳 مبلغ قابل پرداخت: price − balance`) so the customer sees precisely what to pay (it was only
  passed to the pay button before). One line, no clutter.
- [ ] Purchase/renew: clearer steps, success screen; more empty states + hints; consistent
  iconography; HTML/premium-emoji copy polish.
- All copy editable via the Texts editor (P10).

### P13 — Smart alerts v2: timing + pro control
Was: cron `hour="6,16"` only → an "ended" alert could lag ~10h (the owner's complaint).
- ✅ **Hourly cadence** — `proxy_alerts` now runs `cron minute=0` (top of every hour), so
  ended/limited/expiry fire within ~1h (was twice-daily). Sender stays non-blocking: batched
  `get_users`, ~20 msg/s throttle, `TelegramRetryAfter` sleep-retry, blocked-recipient handling.
- ✅ **Quiet hours** — `_in_quiet()` defers sends during a configurable Iran-local window
  (`alerts_quiet_enabled` / `alerts_quiet_start_hour` / `alerts_quiet_end_hour`, default 23→8,
  UTC+3:30). Self-healing dedup means a deferred alert simply fires the next active hour.
- ✅ **Multi-step expiry** — opt-in `notify_expiry_steps_hours` (e.g. `[72,24,12]` = 3d/1d/12h),
  per-step dedup via `Proxy.notified` keys `expiry:{h}`; the loop sends only the tightest new step
  and marks looser already-passed steps as seen (no stale "3 days left" after "12 hours left").
  Empty list → legacy single step from `notify_expiry_days` (**no behaviour change by default**).
- ✅ **Web-editable** — new settings surfaced in web **Settings → Alerts** (quiet switch + start/end
  hours + expiry-steps tags); API `_BOOL/_INT/_LIST` + `SettingsOut/UpdateIn` extended; bot
  `Settings` model + validator added (rows auto-created on startup, no migration).
- ✅ **Send-now from web** — Automation page got an **Alerts** card: "Run now" (`POST
  /automation/alerts/run` sets Redis `alerts:run_now`; the bot's 15s `sync_settings` poll picks it
  up and fires `proxy_alerts(force=True)` in the background, **bypassing quiet hours**) + live
  last-run status (`GET /automation/alerts` reads the `alerts:status` hash the job writes:
  state/last_run/sent). 409 guard while a scan is running. API never imports the bot.
- ✅ **Alert preview** — Automation Alerts card "Preview" button opens a modal showing each of the 4
  templates (`alert_expiry/low_data/unused/ended`) rendered with sample placeholder values in a
  Telegram-style bubble. `GET /automation/alerts/preview` reads `BotText` directly (no bot import),
  substitutes `{NAME}/{DAYS_LEFT}/{DATA_LEFT}`, flags empty rows as "uses bot default".
- ✅ **Per-type re-send cadence** — `alerts_cadence_{expiry,low_data,unused,ended}_hours` (0 = once,
  default; N = re-remind every N h while the condition holds). Enforced per-proxy via timestamps in
  `Proxy.notified` (`{flag: last_sent_ts}`, legacy bool tolerated); `_cadence`/`_base_of` helpers.
- ✅ **Automation alert-config hub** (super-admin) — `GET/PATCH /automation/alerts/config`: edit the
  4 alert **texts** (→ BotText), the 2 alert glass-button **colour + premium emoji** (→ merged into
  `button_icons`/`button_styles`, never clobbering other buttons) + the inline-premium master switch,
  and the per-type **cadence**. Sets both `texts:dirty`+`settings:dirty`. Web: collapsible
  `AlertConfig` card on the Automation page (lazy-loads on expand, super-admin only).
- [ ] Deferred (low value): the bot settings-FSM mirror. **P13 done.**

---

## Active phase details

### Phase 2 — Web panel UX (⏳ partial)
Done: `makeTheme(accent, mode)` + 5 accents (emerald/blue/violet/rose/amber) with picker,
Settings page refactored to AntD Tabs (General/Values/Advanced/Alerts, `forceRender`).
Remaining: detail-page tabs, skeletons/empty-states, broader polish + responsiveness pass.
Files: `webpanel/src/theme.ts`, `contexts/color-mode.ts`, `App.tsx`,
`components/Layout.tsx`, `pages/settings/index.tsx`.

### Phase 3 — Premium emoji + colour on inline buttons (✅ built, ⏳ unverified on deploy)
Bot API `icon_custom_emoji_id` + `style` on inline (glass) buttons — NOT reply buttons.
Master switch `premium_buttons_enabled` defaults **OFF** → zero behaviour change until owner opts in.
Custom emoji icon needs the **bot owner to have Telegram Premium**; `style` colour does not.
- Helper `app/keyboards/premium.py:premium_button(...)` — injects extras only when enabled,
  build-time try/except fallback to a plain button (a rejecting/old API never breaks the UI).
- `app/utils/buttons.py`: `INLINE_BUTTONS` registry (9 keys) + `DEFAULT_STYLES` +
  `resolve_icon/resolve_style`. Config: `button_icons` / `button_styles` (key→value Settings rows, no migration).
- Applied to alert keyboards + 6 `ProxyPanel` action buttons (`app/keyboards/user/proxy.py`).
- Web: `pages/buttons/index.tsx` 2 tabs (Main-menu labels · Inline premium); router
  `app/api/routers/buttons.py` + schemas (`InlineButtonItem`, `ButtonsOut.inline/premium_enabled`).
⚠️ Can't confirm from here that aiogram 3.4.1 serialises the extra fields. If it doesn't render
on deploy → raw-payload sender (direct httpx to Bot API) or aiogram bump.
- ✅ **Double-emoji fix:** when a premium icon is applied, `buttons.strip_leading_emoji` drops
  the text's own leading emoji so the icon doesn't duplicate it (`app/keyboards/premium.py`).
- ✅ **Inline rename:** `button_texts` setting + per-button text field in the web Buttons page
  (Inline tab). Renaming is NOT premium-gated — any admin can relabel an inline button.

### Phase 4 — Full button customization (planned, staged) ⏳

Goal owner asked for: edit **every** bot button (text + premium emoji + colour), create **new**
buttons with **actions**, group them into **sections**, and fully customize the **main reply
menu** (the post-/start buttons that drive customer first-impression + retention). Big +
architectural → build per stage, confirm each before starting.
- **4a — Cover inline buttons** ✅ (customer-facing): `INLINE_BUTTONS` now covers account /
  purchase / payment / renew / proxy-panel (rename + emoji + colour). Admin keyboards **out of
  scope** (owner decision). Remaining customer back/confirm/reserve buttons → 4a (cont.) above.
- **4a (payment methods)** ✅: the charge-menu gateway buttons (card-to-card / crypto / perfect-money
  / zarinpal / zibal / payping / aqaye-pardakht / swapino / tron) are now keyed
  (`pay_method_key(plugin._name)` → `pay_*` registry entries) and routed through `premium_button` in
  `keyboards/user/payment.ChargePanel`, so each gets colour + premium emoji (+ optional rename) in the
  web Buttons editor. Web labels added; the inline tab gained a **search filter** for the longer list.
- **Editor UX redesign** ✅: **Texts editor** — variable tags are now **clickable to insert** `{VAR}`
  at the cursor, a **live HTML preview** toggle per text (Telegram-style bubble), + a char counter.
  **Buttons editor** — the inline list is **grouped by category** (proxy / account / purchase /
  payment / renew / links / reset / reserve / alerts / common) with the search filtering across
  groups, so the now ~40-button list stays navigable.
- **4b — Main reply-menu builder** ✅: `main_menu_layout` setting (ordered rows of keys, empty =
  default) drives `keyboards/base.MainMenu`. Web editor (Buttons → Main-menu tab): enable/disable
  (remove = hide), reorder (↑↓), row grouping (↵ new-row), + the existing per-button label/emoji.
  Routing stays text-based (no handler change); super-admins always keep the admin button.
  Per-button premium `icon_custom_emoji_id` is inline-only, so reply buttons use unicode emoji in
  the label. `sync_settings.py` reloads via `settings:dirty`. No migration (key-value setting).
- **4c — Dynamic custom buttons + actions** (large, needs design + DB model + migration):
  super-admin defines a NEW button with an **action type** (open URL · open a service menu ·
  show a text/page · trigger support · run a safe whitelisted command) and a **placement**
  (main menu / a section / an inline panel). Needs a `CustomButton` model, an action registry +
  generic callback dispatcher (security: only whitelisted, non-destructive actions; no arbitrary
  handler injection), and web CRUD. **Plan + confirm before building.**
Web panel (all stages): richer Buttons page — sections/tabs per bot area, enable/disable toggles,
drag-reorder, live preview, add/remove. Keep super-admin-gated + audited (`buttons.update`).

---

## Done log (compact — don't rebuild these)
- ✅ **Multi-panel adapter** (`app/panels/`, §6) — Marzban (legacy) + **PasarGuard complete**
  (data-plane + admin UI + webhook). New code never imports a panel client directly.
- ✅ **Guardino Hub** (§6, phase 2) — id-based, GB/days, hub pricing. Stages 0–4: model +
  migration 47, adapter, admin UX, purchase/manage, low-balance job. ⛔ reserves + efficient
  sync + on_hold deferred. ⚠️ 2FA must be OFF on the bot's hub account.
- ✅ **Web panel Phase 1** — FastAPI `app/api/` (`api` service, uvicorn :8000) + `webpanel/`
  (Vite + React + Refine + AntD, RTL, served by nginx :8080, proxies `/api`). Telegram-OTP +
  Web-App auto-login → JWT. Routers: dashboard, users(+block), proxies(+action/delete),
  services, servers(+health/enabled), transactions, reports, resellers, discounts,
  automation(broadcast monitor+cancel), settings, audit, texts, menus, buttons. Reseller
  subtree scoping; credentials never exposed; **no manual sell** (purchases/renew stay bot-only).
- ✅ **Audit log** — `AuditLog` (`app/models/audit.py`, migration **48**) + `app/utils/audit.record_audit`
  (model-layer, API-safe). Every web write-action + key bot admin actions (balance ops, server/
  service add·edit·delete) recorded with actor+role+source+target+amount. Purpose: catch
  financial abuse when a third-party super-admin runs the bot on the owner's panel.
- ✅ **Settings parity** — curated `settings` router writes `BotSetting` directly + `settings:dirty`
  → `app/jobs/sync_settings.py` reloads the bot. Covers access/referral/buttons/reminders/
  username_generator/log-channels/charge-lists/alerts. `payment_*` excluded (secrets).
- ✅ **Texts / Menus / Button-labels editors** — `/texts` (`texts:dirty` reload; `<tg-emoji>` in
  message text), `/menus` (nested ServiceMenu CRUD, cycle-safe), `/buttons` (main-menu labels via
  `button_labels` + `app/middlewares/button_labels.py` remap). All super-admin.
- ✅ **Phase 1 — Smart proxy alerts** — `app/jobs/proxy_alerts.py` (cron `hour="6,16"`),
  migration **49** adds `Proxy.notified` JSON. Batch `get_users`, evaluates expiry-soon /
  low-data / unused / ended with **self-healing dedup** (flag drops when condition clears).
  Throttled non-blocking send + glass renew/links buttons. 4 Persian templates (`texts.alert_*`)
  + 9 settings, both editable in the web panel.
- ✅ **Phase 4a/4b — Button customization (customer-facing)** — inline rename + premium emoji +
  colour across account/purchase/payment/renew/proxy-panel; double-emoji auto-fix; main reply-menu
  builder (`main_menu_layout`: enable/disable + reorder + row layout). Web Buttons page (2 tabs).
  Admin buttons out of scope. No migration (key-value settings).
- ✅ **Per-service + per-category button premium** — `Service.button_icon`/`button_style`
  (migration **50**) and `ServiceMenu.button_icon`/`button_style` (migration **51**) let a named
  service OR a menu/category carry a premium emoji + colour on its button. Service: main reply
  menu (`base.MainMenu`, no emoji-strip → text routing intact) + inline purchase/renew lists.
  Menu/category: inline purchase/renew lists (callback-routed → emoji-strip safe). Both via
  defensive 4-tuples `(id, name, icon, style)`. Edited from the web Services page (modal →
  `PATCH /services/{id}/button`, audit `service.button`) and the web Menus form (existing
  `POST`/`PATCH /menus`, normalized + audited). Bot reads the rows live (no reload flag).
- ✅ **Phase 4 — Colour model + experimental reply premium** — inline colours now raw-by-default
  (only important buttons coloured); web 5-state style picker (default/raw/blue/green/red, `none`
  sentinel = forced no-colour). Main (reply) menu premium emoji/colour behind a separate
  `premium_reply_enabled` flag with build-time fallback + `main_menu_routing_map` so emoji-stripped
  labels still route. Decoupled from inline so it can't break the menu.
- ✅ **Fix §17.2** — reseller test-service counting (`record_purchase_service` uses `user.role`;
  unified Redis key + `count >= limit`).

---

## Locked decisions (don't re-litigate)
- **No manual sell in the web panel** — purchases/renew stay bot-only (user-centric; avoids
  free-provisioning on the owner's panel). Web = manage / support / report / customise + audit.
- **Web panel goal is bot operations, not re-creating upstream panels** (Guardino Hub etc.).
  Cover sales/management/support/reporting through the same §6 adapter for all three panels.
- **Premium buttons** default OFF; safe fallback always; inline-only; emoji needs owner Premium.
- **Button customization targets the customer UI only** — admin buttons + the ⚙️ admin-panel
  menu are deliberately NOT made premium/customizable (focus is customer attraction/retention).
- **Premium emoji/colour on the main (reply) menu is EXPERIMENTAL** — the `KeyboardButton`
  schema this code was written against doesn't list `icon_custom_emoji_id`/`style`, but (per an
  owner-supplied doc + the fact inline used undocumented fields that proved real) it's
  implemented behind a **separate** flag `premium_reply_enabled` (default OFF), with a build-time
  fallback. ⚠️ The fallback CANNOT catch a Telegram **send-time** rejection, so it's deliberately
  decoupled from the proven inline `premium_buttons_enabled` flag — enabling inline never risks
  the menu send. If Telegram rejects the fields, the owner just turns the reply flag off.
- **Inline colours are raw by default** — only important buttons carry a built-in colour (green
  for money/confirm CTAs, red for destructive). Web style picker has 5 states: default
  (recommended = built-in), raw (`none` = force no colour), blue (`primary`), green (`success`),
  red (`danger`).
- **Backend FastAPI + Frontend React/Refine/AntD** (RTL, Vazirmatn, emerald, dark+light, responsive).
- **The API process must never import `app.main`** (it pulls payment plugins). Routers touch
  `BotSetting`/`BotText` directly + dirty-flags.
- Guardino: hub owns base price; bot keeps retail margin. Pre-check with `quote`; never assume
  per-day cost. Link policy admin-configurable (master vs node). Low-balance thresholds in settings.
- **Plan/price CRUD in the web is allowed** (defining plans ≠ selling). The "no manual sell" rule
  only forbids provisioning a subscription from the web; purchases/renew stay bot-only.
- **User/reseller display = numeric id ALWAYS + username next to it** (owner: id is required for
  audits; username is for readability). Search by either.
- **Dates: Jalali (Shamsi) alongside Gregorian** in the web panel — a global toggle + per-Settings
  default; one shared date util (dayjs + jalaali); applies to tables, detail pages, and report ranges.
- **Web fonts are user-selectable** (Vazirmatn default + Vazir + others) from Settings; persisted.
