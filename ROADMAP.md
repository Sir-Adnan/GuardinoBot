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

## Now — the big push: web-panel maturity + bot UX

Recommended order (full blocks under **Planned phases** below):
**P11a UI foundation → P5 Plans CRUD → P6 Panels CRUD → P7 Users 360° →
P9 Reports + Jalali → P10 finish half-done pages → P8 Resellers →
P12 Bot UX → P13 Alerts v2 → P11b polish.**

Reasoning: land the shared UI foundation (tab shell, font setting, Jalali date util,
dashboard widgets) first so every later page adopts it; then close the biggest management
gaps (plans, panels, users); then reporting; then polish.

Immediate / carry-over (do anytime):
- [ ] Verify Phase 3/4 premium rendering on a real deploy (Premium owner); if the fields are
      dropped → raw-payload sender (httpx → Bot API) or aiogram bump.
- [ ] Bug-fix plan `delightful-crafting-micali.md` (PasarGuard add-server `is_sudo`,
      edit-service "no protocol", Guardino sub-day expiry, FSM clear, month=31d) — when owner asks.

## Carry-over backlog (folded into the phases below)
- [ ] **Broadcast → non-blocking worker [critical, §17.1]** → in **P10** (Automation) + bot worker.
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
**P5b — remaining:** create-from-scratch with the **panel-aware provisioning picker** (Marzban
inbounds · PasarGuard groups · Guardino nodes — needs adapter `get_inbounds`/groups/nodes
endpoints) + discount/menu attach UI + true drag-and-drop reorder. (Duplicate covers "new plan" for now.)

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

### P8 — Resellers: full management (web)
Today: list/detail read-only.
- Add/edit reseller; set wallet/credit + postpaid limit; margin/pricing; permissions;
  subtree view; **"view as reseller"** (read-only support); reseller-scoped reports.
- New: `resellers` POST/PATCH + wallet ops (audited, idempotent).

### P9 — Reports & Analytics: complete + Jalali (web)
Today: a single summary endpoint + CSS bar-chart.
- **Date-range picker** (from→to) + presets (today/7d/30d/this month/custom).
- Reports: Sales · Revenue · Reseller · Usage · Payment-breakdown · Top plans · New users ·
  Failed payments · Refunds. Lightweight charts + CSV/Excel export.
- **Jalali (Shamsi) dates** everywhere (toggle Gregorian/Jalali), incl. range pickers + axes.
  Shared date util (dayjs + jalaali plugin); default from Settings; numbers locale-aware.

### P10 — Finish the half-done pages (web)
- **Discounts**: full CRUD + usage stats (today: list + toggle).
- **Automation**: broadcast compose (text/media + target filters) + schedule + reminders config
  + low-balance config + job monitor + logs. (Actual broadcast send = the §17.1 bot worker;
  add the cross-process trigger.)
- **Audit**: complete filters (date range·actor·action·source) + detail drawer + export.
- **Texts**: tabbed by area (start/purchase/account/alerts/errors/…), search, live preview,
  premium-emoji helper.
- Force-join editor; payment-gateway config (sensitive, guarded, secrets masked).

### P11 — UI/UX overhaul (web) — split foundation vs polish
**P11a (foundation) — ⏳ in progress:**
- ✅ Calendar-aware dates: `utils/datetime.ts` (Intl, no dep — Jalali/Gregorian) + header toggle;
  `fmtDate` is now calendar-aware so existing pages follow the choice; live via layout re-render.
- ✅ Font setting: `theme.FONTS` (Vazirmatn default · Vazir · Sahel · Samim · System, loaded in
  index.html) + header font picker; persisted (localStorage); applied via AntD token + body.
- ✅ `components/PageHeader.tsx` (consistent title/subtitle/actions) — adopt across pages in P5+.
- [ ] Remaining: tab/section shell + breadcrumbs adoption, dashboard widget scaffold, responsive
  table→card helper, move font/calendar defaults into a Settings "Appearance" tab (server-side).
**P11b (polish, do LAST):** dashboard pro (KPI cards: today sales · orders ok/fail · active
users · revenue · Guardino balance · panel health · job status; mini-charts; recent activity;
low-balance alerts); **minimal/cleaner icon set** (one family, consistent weight); more theme
presets + density (compact/comfortable); full responsive audit (mobile drawer nav); empty/skeleton
states; micro-interactions.

### P12 — Bot (Telegram) UX overhaul
Goal: the customer-facing bot looks premium and converts better (customers browse/buy here).
- Plan/tariff list: distinct buttons (premium emoji per service/category — done), clear
  price·data·duration, category grouping, a formatted **"tariffs" overview** message.
- Account page: dashboard-style (balance · active subs · nearest expiry · quick actions).
- Subscription view: status badge + **text usage bar** (▰▰▰▱▱ %) · days left · data left · renew CTA.
- Purchase/renew: clearer steps, summary confirmation, success screen; onboarding for new users;
  better empty states + hints; consistent iconography; HTML/premium-emoji copy polish.
- All copy editable via the Texts editor (P10).

### P13 — Smart alerts v2: timing + pro control
Today: cron `hour="6,16"` only → an "ended" alert can lag ~10h (the owner's complaint).
- Run the alert job **hourly** (or a configurable cadence) so "ended/limited" fires within ~1h.
- **Quiet hours** (defer night sends to morning) + per-type cadence + "best time" default.
- Pro per-indicator controls: multiple expiry steps (e.g. 3d/1d/12h), data % AND absolute GB,
  unused, ended — extend the existing 9 alert settings.
- Manual **send-now / preview** from the web Automation page.
- Editable in web Settings (+ deferred bot settings-FSM mirror).

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
