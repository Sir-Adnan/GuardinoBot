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

## Now (in progress / next up)
- [ ] Verify Phase 3 (premium emoji on inline buttons) renders on a real deploy with a
      Premium owner account; if aiogram 3.4.1 drops the extra fields, add a raw-payload
      sender (httpx → Bot API) or bump aiogram. See **Phase 3** below.
- [x] **Phase 4a (cont.)** ✅ — links/QR, reset-password variants, reserve activate/cancel,
      show-reserve, generic confirm, and shared `common_back`/`common_cancel` across
      proxy/purchase/payment/account. Remaining (low value, deferred): reseller sub-user
      management backs (ManageUser/ChargeByParent) + proxy-list pagination/sort/filter.
      Admin keyboards **out of scope** (owner: customer UI only).
- [ ] Phase 2 polish: user/proxy **detail pages with tabs** (Overview·Links·Orders·
      Payments·Panel Status·Logs), skeletons + empty states.
- [ ] Plan file `delightful-crafting-micali.md`: add-panel / edit-service bug fixes +
      panel-aware admin menus (PasarGuard add-server `is_sudo`, edit-service "no protocol",
      Guardino sub-day expiry, FSM not cleared, month=31d). **Apply when owner asks.**

## Next (agreed, not started)
- [ ] **Broadcast → non-blocking worker [critical, §17.1]:** throttle ~25–30 msg/s,
      handle `TelegramRetryAfter`, persist progress/resumability in Redis, mark blockers via
      `blocked_bot`, never block polling. (Web monitor/cancel already exists via `broadcast:job`.)
- [ ] Mirror alert thresholds in the bot's settings-FSM menu (web Settings already covers them).
- [ ] Web-initiated text broadcast (cross-process worker trigger from the API).

## Backlog (needs approval before starting)
- [ ] Force-join dict editor in web Settings.
- [ ] Payment-gateway config in web (sensitive — secrets handling first).
- [ ] Broader bot-side admin proxy-op auditing.
- [ ] Guardino **reserves** (`check_reserves`/`renew_proxy_reserve`) + efficient paginated
      reseller-sync + `on_hold` create mapping. (§6 deferred.)
- [ ] Brand migration `marzbot`/`Marzdemo` → GuardinoBot/Guardino (gradual; needs migration
      for any DB-facing string).
- [ ] PasarGuard native `reset_proxy_credentials` (currently raises; "smart reconnect" works).
- [ ] aiogram 3.4.1 upgrade (`parse_mode=` ctor deprecated → `DefaultBotProperties`).
      Testing + approval required.
- [ ] General background worker/queue for heavy tasks (broadcast, panel sync, reporting).
- [ ] Observability: structured metrics/logs for panel + gateway errors.

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
