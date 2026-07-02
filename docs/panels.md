# Panels — multi-panel adapter (Marzban + PasarGuard + Guardino)

> Detail for the panel adapter layer. CLAUDE.md carries the golden rule + a one-line status;
> read this file before any adapter work. Verify against the code — versions may have changed.

Don't extend the bot as Marzban-only. New panel support goes through one adapter layer:

```text
Telegram Bot / Web Panel → Business Services → Panel Adapter Interface
        → Marzban Adapter / PasarGuard Adapter / Guardino Adapter
```

**Golden rule:** new code **never** imports `marzban_client` or a panel httpx client directly; always go through `app.panels` (`get_panel(server_id)` + neutral methods).

**`BasePanel`** (`app/panels/base.py`): `get_admin`, `get_inbounds`, `create_user`, `modify_user(ModifyUserParams)`, `get_user`, `get_users` (batch), `remove_user`, `reset_usage`, `revoke_subscription`, `set_status`, `reset_proxy_credentials`, and `service_modify_params(service, existing)` which hides the provisioning difference (Marzban: inbounds/proxies preserving UUID; PasarGuard: group_ids; Guardino: none). DTOs: `PanelUser`, `ModifyUserParams` (sentinel `UNSET`), `PanelUserStatus`, `AdminInfo`. Errors are unified as `PanelError`/`PanelAuthError` (with `status_code`). `PanelRegistry` builds/caches an adapter per `Server.panel_type`.

**PasarGuard (phase 1 — done):** full lightweight-httpx adapter. Data-plane fully migrated: `handlers/user/purchase.py` (create), `handlers/user/proxy.py` (view/enable-disable/delete/revoke/reset/links/renew), `jobs/check_reserves.py`, `jobs/refresh_proxies.py`, `utils/proxy_management.py` (bulk), `models/service.get_inbounds`. Admin UI: add-server `panel_type` step + service builder with **group selection** (`SelectGroups` → `Service.panel_config.group_ids`). Webhook in `views/notifications.py` is panel-agnostic.
Remaining (minor): `reset_proxy_credentials` unsupported on PasarGuard (raises) — "change password" button is a no-op, but "smart reconnect" (revoke_sub) works; `add_user_from_subscription` (sub-token lookup) intentionally left on the Marzban legacy path. Manage token/session inside the adapter (refresh/expiry); don't re-fetch a reusable token; read large user lists with pagination/cache.

## Fundamental differences (per the specs — read before adapter work)

| | Marzban (legacy) | PasarGuard v5 | Guardino Hub v0.1 |
| --- | --- | --- | --- |
| Auth | `/api/admin/token` (OAuth2 password → Bearer) | `/api/admin/token` (same as Marzban) | `/api/v1/auth/login` (JSON user/pass, **2FA**, api-token) |
| Bot connection | base_url + admin token | base_url + admin token | base_url + **reseller user/pass** → access_token |
| User identity | `username` | `username` | **`user_id` (int)** + `label` |
| Create user | `POST /api/user` (inbounds + proxies) | `POST /api/user` (**group_ids** + **proxy_settings**) | `POST /api/v1/reseller/user-ops` (label, **total_gb**, **days**, node_ids, pricing_mode) |
| Volume/time | bytes / seconds (epoch) | bytes / seconds | **GB / days** |
| Pricing | bot computes | bot computes | **hub computes** (`quote`, `charged_amount`, `balance_after`) |
| Network unit | inbounds | **groups** (`group_ids`) | **nodes** (`node_ids`) |
| Subscription | `/sub/{token}` | `/sub/{token}` | `master_sub_token` → `/api/v1/sub/{token}` + per-node links |
| Key ops | modify/reset/revoke/remove | + `set_status`, `active_next` | extend/renew/add-traffic/decrease-time/change-nodes/refund/set-status/reset-usage/revoke |

## Guardino status (phase 2 — core done)

- ✅ Stage 0 (model + migration 47): `Server.link_policy`, `Proxy.panel_user_id`+`sub_token`, widen `Server.username`.
- ✅ Stage 1 (adapter `app/panels/guardino.py`): login (2FA-aware) with token cache + 401 re-auth; GB↔bytes, days↔seconds mapping; BasePanel methods (`get_admin`, `get_inbounds`=catalog, `create_user`, `modify_user`=status only, `get_user/get_users` by id, `remove_user`=refund-delete, `reset_usage`, `revoke`); Guardino-only methods: **`quote`, `get_balance`, `renew_user`, `extend`, `add_traffic`, `change_nodes`, `get_links(policy)`**. Id-based: pass `str(user_id)` in the username slot; `create_user` returns it as `PanelUser.remote_id` and stashes `master_sub_token`/`charged_amount`/`balance_after` in `raw`. Module helpers `login()/validate()` for the connect flow.
- ✅ Stage 2 (admin UX): `handlers/admin/server.py` add-server flow has a **Guardino** option → reseller user/pass login (`guardino.login`+`validate`) + **link_policy** step (master_first/node_first), stored on the new `Server` row; `ping_servers` is now panel-agnostic via `get_panel().get_admin()`. `handlers/admin/service.py` + `keyboards/admin/service.py` add a **`SelectNodes`** picker (parallel to `SelectGroups`) → `Service.panel_config = {node_ids, pricing_mode}`; node selection is optional (empty → hub default node mode); volume/time reuse the standard `data_limit`/`expire_duration` fields (adapter derives total_gb/days).
- ✅ Stage 3 (purchase + manage): `purchase.py` Guardino create stores `panel_user_id`/`sub_token` and pre-checks hub balance via `quote`/`get_balance`. The adapter resolves a passed label→user_id (cached) and `get_user` enriches `subscription_url`/`links` from `get_links`, so the existing display/QR/enable/disable/delete/revoke/reset-usage paths work for Guardino **unchanged**; `proxy.py` renew has a Guardino branch (`renew_user`).
- ✅ Stage 4 (low-balance alerts): `jobs/check_hub_balance.py` — every 30 min reads each Guardino server's reseller balance (`get_balance`) and warns super-users (`config.SUPER_USERS`) on two thresholds (`guardino_balance_warn`=1,000,000 / `guardino_balance_critical`=500,000 in settings), with Redis anti-spam (alert only on worsening severity).
- **Known gaps (deferred):** Guardino **reserves** (`check_reserves`/`renew_proxy_reserve`) still use the modify(expire/data_limit) path → not supported for Guardino; the generic `refresh_proxies` sync works but is per-user (resolve+fetch) — a dedicated paginated reseller-sync would be more efficient. Guardino **on_hold** create isn't mapped (services with `create_on_hold_users` shouldn't target Guardino yet).
- ⚠️ **2FA must be OFF for the bot account** (unattended re-login can't solve a TOTP challenge) or the adapter raises a clear error. `modify_user` only supports `status`; volume/time changes go through `renew_user/add_traffic/extend`.

### Guardino — locked decisions (agreed with owner)

- **Credentials:** set up with **reseller or super-admin** hub user/pass (owner has no api-token). Store password **encrypted** (`PasswordField`); never reveal in messages/logs. Login via `/api/v1/auth/login`; token/session + 2FA handled inside the adapter (api-token optional later). Don't connect to the hub's internal DB.
- **Link policy (admin-configurable):** prefer "node link (underlying panel: PasarGuard/WireGuard)" or "Guardino master" — admin setting on Server/Service. Source: `GET /api/v1/reseller/users/{id}/links` (`master_link` + `node_links[]`). If master is off → auto node_links. QR is built from the chosen link.
- **Low-balance alert:** a periodic job reads reseller balance (`/api/v1/auth/me` or `/reseller/stats`) and warns super-users: **< 1,000,000 toman warn, < 500,000 stronger warn** (thresholds configurable in settings). Avoid double-alerts with a Redis flag.
- **Pricing:** the **hub** sets base cost (`charged_amount`/`balance_after`); the bot keeps its retail price (`Service.price`, toman) separate and adds margin. **Each reseller's tariff differs and per-day cost is often zero/disabled** — never assume days cost anything; always rely on `quote`/`charged_amount`. Pre-check balance with `quote` before create to avoid a failed/loss-making purchase.

## Auto-generated clients

- `marzban_client/` is generated by `openapi-python-client` from the Marzban spec at `docs/references/upstream-apis/Marzban-API.json` (moved from the old root `openapi.json`). **Don't hand-edit.**
- Regenerate (only with approval — touches many files): `make generate-client`. ⚠️ The `Makefile` `--path` must point at the moved spec path before regenerating.
- PasarGuard and Guardino deliberately use a small hand-written httpx client (`app/panels/pasarguard.py`, `app/panels/guardino.py`) behind `BasePanel` — no codegen needed.

**Before a big panel refactor, present a migration plan and get approval.**
