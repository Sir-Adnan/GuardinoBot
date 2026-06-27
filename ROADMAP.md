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
- **Automation**: broadcast compose (text/media + target filters) + schedule + reminders config
  + low-balance config + job monitor + logs. (Actual broadcast send = the §17.1 bot worker;
  add the cross-process trigger.)
- ✅ **Texts**: tabbed by area (general/sales/support/access/alerts) + search; per-card save +
  variables + premium-emoji helper. Backend adds `group` to each curated key.
- ✅ **Audit**: added **date-range** filter (`start`/`end`) + **CSV export** (current filters,
  up to 1000 rows) + PageHeader; detail drawer + source/search filters already existed.
- **Remaining:** **Automation** (broadcast compose + schedule + reminders/low-balance config +
  job monitor — needs the §17.1 bot worker + a cross-process trigger); Force-join editor;
  payment-gateway config (sensitive, guarded, secrets masked).

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
- [ ] Remaining: low-balance/panel-health dashboard widgets, micro-interactions, broader audit.

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
