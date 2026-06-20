# CLAUDE.md — GuardinoBot

> راهنمای کار با این پروژه برای Claude Code. قبل از هر تغییر بخوان و رعایت کن.
> This guides Claude when working in this repo. Read it before making changes.
> Keep changes safe, targeted, modular, and token-efficient.

---

## 0) قوانین صرفه‌جویی توکن (مهم‌ترین بخش — همیشه)

هدف: حداکثر کیفیت با حداقل مصرف توکن. پروژه بزرگ است؛ خواندن کور و کامل فایل‌ها ممنوع.

**خواندن/جستجو (Read/Search):**
- هرگز کل دایرکتوری یا فایل بزرگ را «برای اطمینان» نخوان. اول با `Grep`/`Glob` نقطهٔ دقیق را پیدا کن، بعد فقط همان محدوده را با `Read` (`offset`/`limit`) بخوان.
- این‌ها را **نخوان مگر ضرورت مطلق** (هرکدام ۱۰۰KB+، تکراری): `openapi.json`, `openapi-pasarguard.json`, `openapi-guardino.json`, و محتوای `marzban_client/`. برای فهم رفتار پنل به‌جای spec خام، اینترفیس خنثی را از `app/panels/base.py` بخوان.
- `migrations/models/` (ده‌ها فایل) را کامل نخوان؛ فقط جدیدترین migration یا مورد لازم.
- اگر جستجوی سطح کدبیس لازم شد و فقط «جمع‌بندی» می‌خواهی (نه محتوای خام)، از subagent `Explore` استفاده کن تا خروجی خام وارد context اصلی نشود.

**نوشتن/ویرایش (Edit):**
- برای تغییر جزئی همیشه `Edit` (نه بازنویسی کامل با `Write`). فایل را قبل از Edit فقط یک‌بار بخوان.
- بعد از Edit موفق، فایل را دوباره «برای تأیید» نخوان.
- چند ویرایش مستقل روی یک فایل را در یک پیام با چند `Edit` بفرست (به‌ترتیب اعمال می‌شوند)؛ برای الگوی یکسانِ پرتکرار از `replace_all` استفاده کن.
- با سبک کد اطراف هماهنگ شو؛ بازنویسی بخش‌های نامرتبط ممنوع.

**پاسخ‌دهی:**
- جواب‌ها کوتاه و مستقیم؛ از خلاصه‌سازی دوبارهٔ چیز مشخص‌شده پرهیز کن.
- وقتی تصمیم روشن است عمل کن؛ فهرست بلند گزینه نده — یک پیشنهاد بده.
- خروجی tool را عیناً کپی نکن؛ فقط نتیجهٔ مهم را بگو.
- قبل از کار پرهزینه (refactor بزرگ، تولید مجدد client) اول نقشه بده و تأیید بگیر.

**موازی‌کاری:** فراخوانی‌های مستقل tool را در یک پیام با چند tool-call بفرست، نه پشت‌سرهم.

**هزینهٔ runtime ربات:** فراخوانی API پنل‌ها را batch کن (مثل `get_users` با لیست username)؛ در حلقه فراخوانی تکی نزن؛ از کش Redis استفاده کن؛ لیست بزرگ کاربران ریموت را بی‌دلیل تکرار نکن.

---

## 1) قانون اصلی: دستورهای سنگین را خودکار اجرا نکن

بعد از ویرایش عادی، **هرگز** این دستورها را خودکار اجرا نکن:

```bash
docker compose up --build
docker compose up -d --build
docker compose build
docker compose logs -f
docker compose down
docker compose down -v
pip install -r requirements.txt
pip install <package>
aerich migrate
aerich upgrade
aerich init-db
python -m compileall .
make generate-client
openapi-python-client update
```

فقط وقتی کاربر دقیقاً یکی از این عبارت‌ها را گفت، دستور سنگین اجرا کن:

```text
FULL TEST
FULL BUILD
DEPLOY CHECK
```

دستورهای **مخرب** را حتی با اصرار بدون درخواست صریح اجرا نکن (دیتابیس/Redis/volume را پاک می‌کنند):

```bash
docker compose down -v
docker volume rm
docker system prune
```

قبل از هر دستور طولانی، کوتاه توضیح بده چرا لازم است و تأیید بگیر.

**چک‌های هدفمند (پیش‌فرض):**
- تغییر کوچک پایتون → فقط همان فایل: `python -m py_compile path/to/changed_file.py`
- چند فایل مرتبط → فقط همان‌ها: `python -m py_compile file1.py file2.py`
- compile کل ریپو فقط با درخواست صریح.
- اگر وابستگی محلی نصب نیست، خودکار نصب نکن؛ واضح گزارش بده و قبل از نصب بپرس.

---

## 2) هدف پروژه و وضعیت

**GuardinoBot** یک ربات تلگرامی فروش اشتراک (پروکسی/VPN) است؛ fork توسعه‌یافته از `marzbot`.
ریپو: <https://github.com/Sir-Adnan/GuardinoBot> — مالک فعلی: Sir-Adnan (سورس از مالک قبلی خریداری شده و حدود ۱ سال آپدیت نشده).

**نام‌گذاری:** نام رسمی پروژه **GuardinoBot** است. نام قدیمی `marzbot`/`Marzdemo` از مالک قبلی است و باید تدریجی (نه یکجا) به GuardinoBot/Guardino مهاجرت کند — شامل image داکر (`ghcr.io/.../marzbot`)، prefix پیش‌فرض username (`Marzdemo`)، و رشته‌های برند. نام جدول/متغیرهای DB را بدون migration و تأیید تغییر نده.

**وضعیت فعلی:** فقط پنل **Marzban** پشتیبانی می‌شود. **Marzban عملاً متوقف شده (legacy)** و بیش از ۱ سال آپدیت نگرفته؛ تمرکز توسعه روی پنل‌های جدید است.

**اهداف (در حال انجام، به ترتیب اولویت):**
1. افزودن **PasarGuard** و **Guardino Hub** به‌عنوان پنل‌های اصلی فروش (مرزبان به‌عنوان legacy باقی می‌ماند). ربات باید **دقیقاً مثل مرزبان** به این پنل‌ها وصل شود (همان جریان ساخت/تمدید/مدیریت پروکسی).
2. **وب‌پنل پیشرفته** برای ادمین اصلی و رسلرها، جدا از رابط تلگرام (بخش ۹).
3. رفع باگ‌ها و بهبودها (بخش ۱۷) — مهم‌ترین: ارسال پیام همگانی غیرمسدودکننده.

**دو حالت استقرار (deployment) که ربات باید پشتیبانی کند:**
- **حالت مالک (self-host):** مالک اصلی ربات تلگرام خودش را اجرا می‌کند و پنل(های) خودش (Marzban/PasarGuard/Guardino) را وصل می‌کند.
- **حالت رسلر Guardino (multi-tenant):** رسلرهای موجود در **Guardino Hub** می‌توانند نمونهٔ ربات راه بیندازند که با **یوزر/پسورد رسلر خودشان در Guardino Hub** لاگین کند و به سهمیه/پنل خودشان در هاب وصل شود (endpointهای `/api/v1/reseller/...`). در این حالت قیمت‌گذاری/کیف‌پول پایه را **خود هاب** مدیریت می‌کند و ربات روی آن مارجین فروش به مشتری نهایی می‌گذارد.

زبان رابط ربات **فارسی** است؛ متن‌های کاربر را فارسی نگه دار مگر کاربر بخواهد.

قبل از تغییر معماری، ساختار و کد فعلی را بررسی کن. مسیر فایل، نام مدل، جدول DB، وضعیت migration یا رفتار runtime را بدون چک‌کردن کد فرض نکن.

---

## 3) معماری و استک

| بخش | فناوری |
|---|---|
| ربات | aiogram 3.4.1 (حالت **polling**، نه webhook) |
| زبان/اجرا | Python 3.11 روی Docker (`python:3.11-alpine`) |
| دیتابیس | MariaDB/MySQL با **Tortoise ORM 0.20** + migrations با **aerich** |
| کش/صف/state | **Redis** — FSM storage، APScheduler jobstore، cache |
| زمان‌بند | APScheduler (`AsyncIOScheduler` + RedisJobStore) |
| وب سرور | aiohttp (`app/views`) برای webhook پرداخت و اعلان پنل، روی `WEBAPP_PORT` (پیش‌فرض 3333) |
| لایهٔ پنل | **`app/panels/`** adapter خنثی (بخش ۶). Marzban روی `marzban_client/` (auto-gen)؛ PasarGuard کلاینت httpx سبک دستی. specهای رسمی: `openapi-pasarguard.json`/`openapi-guardino.json` (سنگین — نخوان مگر لازم) |
| پیکربندی | `python-decouple` از `.env` (نمونه: `.env.example`) |
| رمزنگاری | `pycryptodomex` + `SECRET_KEY_STRING` (فیلد `PasswordField`) |

نقطهٔ ورود: `bot.py` → `app/main.py:main()`.
ترتیب راه‌اندازی: DB → webapp → plugins → routers → middlewares → API servers → scheduler → `run_polling`.

> همیشه قبل از اتکا به این جزئیات، کد فعلی را تأیید کن (نسخه‌ها ممکن است تغییر کرده باشند).

---

## 4) ساختار دایرکتوری (نقشهٔ سریع)

```text
app/
  main.py            # bootstrap: bot, dp, redis, scheduler
  marzban.py         # رجیستری legacy (Marzban.servers) + setup_api؛ PanelRegistry را هم در startup refresh می‌کند
  panels/            # ★ لایهٔ adapter خنثی (بخش ۶): base, marzban, pasarguard, guardino(stub), registry
  handlers/
    admin/           # admin, user, server, service, service_menu, setting, payment, discount
    user/            # account, payment, proxy, purchase, ...
    start.py, base.py, prebase.py, errors.py
  keyboards/         # آینهٔ ساختار handlers (admin/* و user/*)
  models/            # Tortoise: user, server, service, proxy, setting
  plugins/
    payment/         # crypto/nowpayments, card_to_card, perfect_money,
                     # rial_gateway (zarinpal/zibal/payping/aqaye_pardakht), tronseller
    referral/
  jobs/              # check_reserves, del_unpaid_payments, refresh_proxies, remind_invoices
  middlewares/       # acl, rate_limit
  utils/             # helpers, settings, texts, encryption, proxy_management, qr, ...
  views/             # aiohttp: status, notifications (webhook مرزبان)
  templates/         # jinja2 (فعلاً فقط payment.html)
marzban_client/      # ❗ auto-generated — دستی ویرایش نکن (بخش ۷)
migrations/models/   # migrationهای aerich
scripts/             # import/migrate و backup
config.py            # خواندن env و TORTOISE_ORM
```

نقشه را کامل فرض نکن؛ قبل از تغییر، ریپو را جستجو کن.

---

## 5) مدل‌های داده (کلیدی)

- **User** — نقش‌ها در `User.Role`: `user(0)`, `reseller(1)`, `admin(2)`, `super_user(3)`. سیستم رسلر (parent/child)، referrer، balance/postpaid، `UserSetting`.
- **Server** — اتصال پنل: `host`, `port`, `https`, `token`, `username/password` (رمزنگاری‌شده), `is_enabled`, `total_proxies`، و **`panel_type`** (enum: `marzban`/`pasarguard`/`guardino`، پیش‌فرض `marzban`).
- **Service / ServiceMenu** — پلن‌ها: `data_limit`, `expire_duration`, `inbounds`(مرزبان: dict protocol→tags), `flow`, `price`, تخفیف، منوهای تودرتو، فیلتر؛ و **`panel_config`** (JSON nullable — PasarGuard: `{"group_ids":[...], "proxy_settings":{...}}`؛ Guardino فاز ۲).
- **Proxy** — اشتراک کاربر روی یک Server؛ `username` یکتا، `status`(ProxyStatus هم‌ارز PanelUserStatus), `service`, `user`, `server`, `reserve`.
- **Invoice / Transaction (+زیرنوع پرداخت) / Discount / Reserve / PurchaseLog**.

موجودی کاربر **محاسباتی** است (`User.get_balance` = مجموع تراکنش‌ها منهای فاکتورها)، نه مقدار ذخیره‌شدهٔ خام.

> `Server.panel_type` و `Service.panel_config` به مدل اضافه شده‌اند و migration آن‌ها ساخته شده: `migrations/models/46_*_update.py`. روی استارت کانتینر (`prestart.sh` → `aerich upgrade`) خودکار اعمال می‌شود — اسکریپت نصب/آپدیت هم همین مسیر را می‌رود.

---

## 6) چندپنلی و Panel Adapter (Marzban + PasarGuard + Guardino)

ربات را Marzban-only گسترش نده. پشتیبانی پنل جدید باید از یک لایهٔ adapter بگذرد:

```text
Telegram Bot / Web Panel → Business Services → Panel Adapter Interface
        → Marzban Adapter / PasarGuard Adapter / Guardino Adapter
```

**قانون طلایی:** کد جدید **هرگز** `marzban_client` یا کلاینت httpx پنل را مستقیم import نکند؛ همیشه از `app.panels` (`get_panel(server_id)` + متدهای خنثی) عبور کن.

**اینترفیس `BasePanel`** (`app/panels/base.py`): `get_admin`, `get_inbounds`, `create_user`, `modify_user(ModifyUserParams)`, `get_user`, `get_users`(batch), `remove_user`, `reset_usage`, `revoke_subscription`, `set_status`, `reset_proxy_credentials`، و `service_modify_params(service, existing)` که تفاوت provisioning را پنهان می‌کند (مرزبان: inbounds/proxies با حفظ UUID؛ PasarGuard: group_ids). DTOها: `PanelUser`، `ModifyUserParams` (sentinel `UNSET`)، `PanelUserStatus`، `AdminInfo`. خطاها در `PanelError`/`PanelAuthError` (با `status_code`) یکنواخت‌اند. `PanelRegistry` بر اساس `Server.panel_type` adapter می‌سازد/کش می‌کند.

**وضعیت PasarGuard (فاز ۱ — انجام‌شده):** adapter کامل با httpx سبک. data-plane کاملاً منتقل شده: `handlers/user/purchase.py` (ساخت)، `handlers/user/proxy.py` (نمایش/فعال‌غیرفعال/حذف/revoke/reset/links/renew)، `jobs/check_reserves.py`، `jobs/refresh_proxies.py`، `utils/proxy_management.py` (bulk)، `models/service.get_inbounds`. افزودن سرور PasarGuard: گام انتخاب `panel_type` در `handlers/admin/server.py` (token/validate مشترک با مرزبان).

- **admin UI:** افزودن سرور (انتخاب `panel_type`) و ساخت/ویرایش سرویس با **انتخاب group** (`SelectGroups` در `keyboards/admin/service.py` → `Service.panel_config.group_ids`) پیاده شد. webhook در `views/notifications.py` panel-agnostic شد (status را مستقیم از payload می‌خواند).

**باقی‌مانده PasarGuard (جزئی):**
- `reset_proxy_credentials` روی PasarGuard پشتیبانی نمی‌شود (raise)؛ دکمهٔ «تغییر پسوورد» کار نمی‌کند ولی «تغییر اتصال هوشمند» (revoke_sub) کار می‌کند.
- `add_user_from_subscription` (lookup با sub-token) عمداً روی مسیر legacy مرزبان مانده.

### تفاوت بنیادی سه پنل (طبق specها — حتماً قبل از طراحی adapter بخوان)

| | Marzban (legacy) | PasarGuard v5 | Guardino Hub v0.1 |
|---|---|---|---|
| Auth | `/api/admin/token` (OAuth2 password → Bearer) | `/api/admin/token` (همان مرزبان) | `/api/v1/auth/login` (JSON یوزر/پسورد، **2FA**، api-token) |
| اتصال ربات | base_url + توکن ادمین | base_url + توکن ادمین (مثل مرزبان) | base_url + **یوزر/پسورد رسلر** → access_token |
| شناسهٔ کاربر | `username` | `username` | **`user_id` (int)** + `label` (username اختیاری/auto) |
| ساخت کاربر | `POST /api/user` (inbounds dict + proxies) | `POST /api/user` (**`group_ids`** + **`proxy_settings`**) | `POST /api/v1/reseller/user-ops` (label, **total_gb**, **days**, node_ids, pricing_mode) |
| واحد حجم/زمان | بایت / ثانیه (timestamp) | بایت / ثانیه | **GB / روز** |
| قیمت‌گذاری | ربات حساب می‌کند | ربات حساب می‌کند | **هاب حساب می‌کند** (`quote`, `charged_amount`, `balance_after`) |
| مفهوم شبکه | inbounds | **groups** (`group_ids`) | **nodes** (`node_ids`) |
| ساب‌اسکریپشن | `/sub/{token}` | `/sub/{token}` | `master_sub_token` → `/api/v1/sub/{token}` |
| ops کلیدی | modify/reset/revoke/remove | همان + `set_status`, `active_next` | extend/renew/add-traffic/decrease-time/change-nodes/refund/set-status/reset-usage/revoke |

**نتیجهٔ طراحی:**
- **PasarGuard ≈ Marzban-next:** adapter آن نزدیک به Marzban است؛ فقط نگاشت `inbounds → group_ids` و `proxies → proxy_settings`. اتصال و توکن یکسان. می‌توان کلاینت را با همان `openapi-python-client` ساخت.
- **Guardino فرق اساسی دارد:** id-محور، GB/روز، و قیمت‌گذاری سمت هاب. DTO خنثیِ adapter باید هم مدل username-محور (Marzban/PasarGuard، قیمت توسط ربات) و هم مدل id-محور (Guardino، قیمت توسط هاب) را پوشش دهد. برای Guardino، «Service» ربات به `(total_gb, days, node_ids)` نگاشت می‌شود و هزینهٔ پایه از endpoint `quote` گرفته می‌شود؛ مارجین فروش را ربات اضافه می‌کند.
- مدل **Service/Server** باید فیلدهای پنل‌محور بپذیرد (`panel_type` و پارامترهای متفاوت per-panel). مقادیر مخصوص مرزبان (inbounds/flow) را به‌عنوان تنها حالت فرض نکن.

**Guardino:** ترجیحاً با api-token (`/api/v1/auth/api-tokens`) به‌جای نگه‌داشتن پسورد؛ اگر یوزر/پسورد رسلر لازم شد (حالت multi-tenant) **رمزنگاری‌شده** ذخیره کن و هرگز در پیام/لاگ نشان نده؛ 2FA را در نظر بگیر؛ به DB داخلی هاب مستقیم وصل نشو.
**PasarGuard:** مدیریت token/session داخل adapter (refresh/expiry)؛ توکن قابل‌استفادهٔ مجدد را بی‌دلیل دوباره نگیر؛ لیست بزرگ کاربران را با pagination/کش بخوان.

قبل از refactor بزرگ پنل، پلن مهاجرت بده و تأیید بگیر.

---

## 7) کلاینت‌های auto-generated

- `marzban_client/` با `openapi-python-client` از `openapi.json` تولید شده. **دستی ویرایش نکن.**
- بازتولید (فقط با تأیید، چون فایل‌های زیادی تغییر می‌کند): `make generate-client`.
- PasarGuard عمداً **کلاینت httpx سبک دستی** دارد (`app/panels/pasarguard.py`) — نیاز به codegen نیست. اگر Guardino هم کلاینت لازم داشت، همین الگوی httpx پشت `BasePanel`.

---

## 8) دیتابیس و migrations (aerich)

- هر تغییر مدل **نیازمند migration** است: `aerich migrate` (ساخت) → `aerich upgrade` (اعمال، در `prestart.sh` هنگام استارت).
- دستورهای aerich را خودکار اجرا نکن (بخش ۱)؛ اول توضیح بده، بعد بپرس.
- migration را backward-compatible و additive نگه دار. **بدون تأیید صریح کاربر** این کارها ممنوع: drop column/table، پاک‌کردن ردیف، reset موجودی/داده رسلر، بازنویسی ownership پروکسی/کاربر، بازنویسی تاریخچهٔ مالی.
- مراقب مدل‌های users، resellers/roles، proxies، servers/panels، services، invoices، transactions، payments، settings، texts باش.
- هنگام M2M یا تغییر مدل به الگوی `_m2m_order` و override متد `describe` در `models/__init__.py` دقت کن (workaround باگ aerich).
- اگر migration برای deploy لازم است، صریح گزارش کن. روی production خودکار اجرا نکن مگر کاربر بخواهد.
- migration پنل (`46_*`) برای `Server.panel_type` + `Service.panel_config` ساخته شده و افزایشی است؛ با `aerich upgrade` اعمال می‌شود.

---

## 9) وب‌پنل پیشرفته (ادمین اصلی + رسلر)

وضعیت فعلی: `app/views` فقط webhook است؛ هیچ پنل احراز‌هویت‌شده‌ای نیست.

قبل از شروع، کد فعلی را بررسی کن: `app/views`، templates، auth، models، config، ساختار Docker/runtime.

**استک پیشنهادی (توافق‌شده — قبل از scaffold اول پلن بده و تأیید بگیر):**
- **Backend: FastAPI** (سرویس مجزا کنار ربات، با همان DB/Redis و **همان لایهٔ adapter بخش ۶**). دلیل انتخاب: کاملاً async و هم‌خانوادهٔ کد فعلی؛ Pydantic + OpenAPI خودکار؛ JWT؛ و خودِ PasarGuard/Guardino هم FastAPI هستند (هم‌خوانی ذهنی تیم). Tortoise از طریق `tortoise.contrib.fastapi` وصل می‌شود.
- **Frontend: React + TypeScript + Vite + Refine + Ant Design.** دلیل: پنل CRUD-محور (کاربران، سفارش‌ها، پنل‌ها، سرویس‌ها، رسلرها) با Refine خیلی سریع ساخته می‌شود (data provider + auth provider + RBAC آماده)؛ Ant Design جدول/فرم/داشبورد آماده و **RTL داخلی** برای فارسی دارد. state با TanStack Query.
- **Auth:** JWT (access + refresh)؛ نقش از `User.Role`. در حالت multi-tenant Guardino، لاگین وب‌پنل رسلر می‌تواند به اعتبارسنجی Guardino Hub هم وصل شود.
- **استقرار:** سرویس‌های جدید (`api` + فرانت build-شده پشت nginx یا serve از همان api) در `docker-compose` اضافه شوند؛ همان DB/Redis. ربات تلگرام و وب‌پنل از یک منبع حقیقت (مدل‌ها + adapterها) استفاده کنند.
- **اجرای جایگزین سبک:** اگر کاربر استک سبک‌تر خواست، ادامهٔ aiohttp + jinja2 موجود هم ممکن است؛ تصمیم نهایی با کاربر.

**اصول مشترک (مستقل از استک):**
- کد وب‌پنل را از handlerهای تلگرام جدا نگه دار. ساختار پیشنهادی: `app/web/` یا `app/api/` (وب/API)، `app/services/` (business logic مشترک ربات و وب)، `app/panels/` (adapterها).
- قابلیت‌های ادمین اصلی: داشبورد، مدیریت سفارش‌ها، مدیریت پنل‌های متصل (Marzban/PasarGuard/Guardino)، سرویس‌های فروش، رسلرها، تخفیف‌ها، گزارش مالی، تنظیمات.
- قابلیت‌های رسلر: نسخهٔ محدودشده با مرزبندی داده.
- **مرزبندی داده:** رسلر فقط کاربران/پروکسی‌های زیرمجموعهٔ خود (`parent`) را ببیند و مدیریت کند؛ اکشن‌های مخصوص ادمین به رسلر نشان داده نشود.
- اسرار/توکن پنل/credential پرداخت/توکن ربات/جزئیات DB در پاسخ‌های وب فاش نشود.
- از همان مدل‌های Tortoise و لایهٔ پنل (بخش ۶) استفاده کن؛ منطق را تکرار نکن.

---

## 10) ایمنی مالی و پرداخت

با هر چیز مرتبط با موجودی کاربر/رسلر، invoice، transaction، درگاه، callback پرداخت، وضعیت سفارش، خرید/تمدید، refund و پرداخت ناموفق **بسیار محتاط** باش.

- تاریخچهٔ مالی را بدون درخواست صریح بازنویسی نکن.
- transaction/invoice تکراری نساز.
- هندلرهای callback پرداخت تا حد ممکن **idempotent** باشند؛ اگر callback ممکن است بیش از یک‌بار برسد، کد نباید کاربر را double-credit کند.
- اسرار درگاه یا خطای خام آن را به کاربر نشان نده.

---

## 11) ایمنی ربات، اسرار و env

- خطای داخلی/trace را به کاربر تلگرام نشان نده.
- **هرگز لاگ نکن:** bot token، توکن پرداخت، توکن پنل، `DATABASE_URL`، داده خصوصی کاربر، credential، API key.
- مقادیر حساس را رمزنگاری‌شده در DB نگه دار (`PasswordField`).
- مراقب: دستورهای admin/reseller-only، force-join، مجوز callback query، FSM/Redis state، job‌ها، تأیید پرداخت، اکشن‌های renew/reset/delete پروکسی. هنگام تغییر handler، جریان مکالمهٔ موجود را حفظ کن مگر کاربر redesign بخواهد.
- اسرار را commit نکن. این‌ها هرگز فاش نشوند: `.env`/`.env.*`, `BOT_TOKEN`, `DATABASE_URL`, `SECRET_KEY_STRING`, credential درگاه‌ها، توکن Marzban/PasarGuard، API key گاردینو، credential Redis و MariaDB/MySQL.
- فایل‌های نمونه (`​.env.example`, `.env.*.example`) commit بمانند. env جدید → در `config.py` و `.env.example` با مقدار خالی/امن ثبت و مستند کن (بدون مقدار واقعی).

---

## 12) ایمنی داده production

پروژه ممکن است با کاربران، رسلرها، پرداخت‌ها و سرورهای پنل واقعی deploy شود.

- تغییری نده که بتواند داده production را به‌طور تصادفی حذف، reset، overwrite، duplicate، detach یا corrupt کند (به‌ویژه users, resellers, proxies, services, servers, payments, invoices, transactions, migrations, Redis state, Docker volumes, اسکریپت‌های deploy).
- برای تغییرات حساس production، اول backup را توصیه کن.
- دستور backup/migration/reset/cleanup/update/مخرب را روی production اجرا نکن مگر کاربر صریحاً بخواهد.

---

## 13) قراردادهای کدنویسی

- **async/await** همه‌جا؛ از فراخوانی sync مسدودکننده در handler/job/view پرهیز کن.
- handlerهای تلگرام را روی I/O نگه دار؛ business logic در services/helpers. منطق API پنل داخل adapter؛ منطق درگاه داخل ماژول‌های پرداخت.
- متن‌های کاربر **فارسی** و عمدتاً در `app/utils/texts.py` (قابل reload از Redis)؛ runtime settings در `app/utils/settings.py`.
- کیبوردها در `app/keyboards/` آینهٔ `handlers/`؛ هنگام افزودن handler، کیبورد متناظر را همان‌جا بساز.
- هندلرهای ادمین با `*_command` + docstring برای help خودکار ثبت می‌شوند (`generate_commands_help`).
- پول به **تومان** و حجم به **بایت** ذخیره می‌شود (طبق قرارداد موجود).
- خطاهای پنل را با `PanelError`/`PanelAuthError` (و `status_code`) مدیریت کن (الگوی retry برای 409 در `purchase.py`).
- کد generated را دستی ویرایش نکن؛ داده حساس را لاگ نکن.

---

## 14) Git

- کاربر معمولاً دستی با VS Code Source Control کامیت می‌کند.
- می‌توانی status/diff را بررسی کنی، اما **commit/push/tag/تغییر برنچ ممنوع** مگر کاربر صریحاً بخواهد.
- قبل از پیشنهاد commit: `git diff --check` و `git status --short`؛ سپس فایل‌های تغییریافته را خلاصه و یک پیام commit پیشنهاد بده.
- خودکار اجرا نکن: `git commit`, `git push`, `git tag`, `git checkout`, `git switch`, `git branch`.

---

## 15) دستورها و گردش‌کار (همگی gated با بخش ۱)

```bash
docker compose up -d --build               # اجرا (production-like)
docker compose -f docker-compose.debug.yml up   # توسعه/دیباگ
aerich migrate && aerich upgrade           # migration
make generate-client                       # بازتولید کلاینت مرزبان
make tag && make push                      # انتشار (CI روی tag v*.*.* ایمیج می‌سازد)
```

نسخه در `app/__init__.py` (`__version__`). CI: `.github/workflows/` روی push تگ `v*.*.*` ایمیج را به ghcr.io می‌فرستد.

**نصب روی سرور** — `installer/guardino.sh` (منو: نصب/آپدیت/لاگ/بکاپ/ری‌استارت/وضعیت/حذف):
```bash
bash <(curl -Ls --ipv4 https://raw.githubusercontent.com/Sir-Adnan/GuardinoBot/main/installer/guardino.sh)
```
سورس را در `/opt/GuardinoBot/src` clone و **محلی build** می‌کند (مستقل از ایمیج ghcr)؛ `.env` و `docker-compose.yml` در `/opt/GuardinoBot`، دیتا در `/var/lib/guardinobot`. migrationها هنگام استارت با `aerich upgrade` اعمال می‌شوند.

---

## 16) قبل از تمام‌کردن هر تغییر

گزارش بده: چه تغییر کرد، چه چک شد، چه چک **نشد**، آیا migration لازم است، آیا rebuild داکر لازم است، آیا تست دستی/کامل هنوز لازم است.

- مدل تغییر کرد → migration بساز و اعلام کن.
- env جدید → `config.py` و `.env.example`.
- وابستگی جدید → `requirements.txt` با نسخهٔ pin‌شده + اعلام نیاز به rebuild.
- نقاط چندپنلی را پشت interface نگه دار؛ `marzban_client` را مستقیم وارد کد جدید نکن.
- اگر build کامل اجرا نشد، صادقانه بگو. تغییرات کوچک و backward-compatible را بر تغییرات بزرگ مخلوط ترجیح بده.
- جزئیات را اختراع نکن؛ اول ریپو را چک کن. در صورت تردید دربارهٔ معماری/migration/Docker/پرداخت/پنل، اول بپرس.

---

## 17) باگ‌های شناسایی‌شده و backlog بهبود

> قبل از کار روی هر مورد، کد فعلی را تأیید کن (ممکن است جزئیات تغییر کرده باشد). مورد به مورد و با migration/تأیید لازم پیش برو.

**باگ‌های اولویت‌دار:**
1. **ارسال پیام همگانی (broadcast) مسدودکننده [بحرانی]:** با تعداد زیاد کاربر، ارسال در حلقهٔ همگام انجام می‌شود؛ تلگرام rate-limit می‌کند و کل ربات تا پایان ارسال هنگ می‌کند. راه‌حل: broadcast را به یک **worker پس‌زمینهٔ غیرمسدودکننده** ببر (job APScheduler یا `asyncio.create_task`) که: نرخ را کنترل کند (~۲۵–۳۰ پیام/ثانیه سراسری)، خطای `TelegramRetryAfter` را با `await asyncio.sleep(e.retry_after)` مدیریت کند، پیشرفت/ادامه‌پذیری را در Redis نگه دارد، کاربران مسدودکننده را با فیلد موجود `blocked_bot` علامت بزند، و هرگز loop اصلی polling را بلاک نکند.
2. **شمارش سرویس تست رسلر:** در `app/handlers/user/purchase.py` تابع `record_purchase_service` شرط `if user.Role == User.Role.reseller:` دارد که کلاس enum را با عضو مقایسه می‌کند و **همیشه False** است (باید `user.role` باشد) — یعنی سقف تست روزانهٔ رسلر هرگز increment نمی‌شود. هنگام اصلاح، شرط `count > limit` در `can_get_test_service` را هم بازبینی کن (احتمالاً باید `>=`).

**backlog بهبود (پیشنهادی، با تأیید کاربر):**
- ✅ لایهٔ adapter چندپنلی + **PasarGuard کامل** (data-plane + admin UI + webhook) — بخش ۶. باقی‌مانده فقط reset_proxy_credentials بومی.
- پیاده‌سازی Guardino Hub (فاز ۲، بخش ۶): id-محور، GB/روز، قیمت سمت هاب.
- مهاجرت برند `marzbot`/`Marzdemo` → GuardinoBot/Guardino (بخش ۲) به‌صورت تدریجی.
- وب‌پنل ادمین/رسلر (بخش ۹).
- بازبینی نسخهٔ `aiogram==3.4.1` (قدیمی)؛ `parse_mode=` روی constructor در نسخه‌های جدیدتر deprecated است (`DefaultBotProperties`). ارتقا فقط با تست و تأیید.
- صف کار/worker پس‌زمینهٔ عمومی برای کارهای سنگین (broadcast، sync پنل، گزارش‌گیری) تا loop ربات سبک بماند.
- بهبود observability: متریک/لاگ ساخت‌یافته برای خطاهای پنل و درگاه.
