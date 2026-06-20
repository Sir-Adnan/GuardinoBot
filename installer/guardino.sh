#!/usr/bin/env bash
#
# GuardinoBot installer / manager
# Usage:
#   bash <(curl -Ls --ipv4 https://raw.githubusercontent.com/Sir-Adnan/GuardinoBot/main/installer/guardino.sh)
#
# Menu: install · update · logs · backup · restart · status · edit env · uninstall
#
set -euo pipefail

# ----------------------------------------------------------------------------- constants
APP_NAME="GuardinoBot"
REPO_URL="https://github.com/Sir-Adnan/GuardinoBot.git"
REPO_BRANCH="main"
RAW_SCRIPT="https://raw.githubusercontent.com/Sir-Adnan/GuardinoBot/main/installer/guardino.sh"

APP_DIR="/opt/GuardinoBot"        # holds generated compose + .env
SRC_DIR="${APP_DIR}/src"          # git clone of the repo (build context)
DATA_DIR="/var/lib/guardinobot"   # persistent docker volumes + backups
COMPOSE_FILE="${APP_DIR}/docker-compose.yml"
ENV_FILE="${APP_DIR}/.env"
BACKUP_DIR="${DATA_DIR}/backups"
BIN_PATH="/usr/local/bin/guardinobot"

# ----------------------------------------------------------------------------- colors / log
if [[ -t 1 ]]; then
    RED=$'\e[1;31m'; GREEN=$'\e[1;32m'; YELLOW=$'\e[1;33m'; BLUE=$'\e[1;34m'; CYAN=$'\e[1;36m'; NC=$'\e[0m'
else
    RED=""; GREEN=""; YELLOW=""; BLUE=""; CYAN=""; NC=""
fi
info()  { echo "${GREEN}[+]${NC} $*"; }
warn()  { echo "${YELLOW}[!]${NC} $*"; }
err()   { echo "${RED}[x]${NC} $*" >&2; }
die()   { err "$*"; exit 1; }
hr()    { echo "${BLUE}--------------------------------------------------${NC}"; }

# ----------------------------------------------------------------------------- preflight
need_root() {
    if [[ "$(id -u)" -ne 0 ]]; then
        die "این اسکریپت باید با کاربر root اجرا شود. از sudo استفاده کنید."
    fi
}

PKG=""
detect_pkg_manager() {
    if   command -v apt-get >/dev/null 2>&1; then PKG="apt"
    elif command -v dnf     >/dev/null 2>&1; then PKG="dnf"
    elif command -v yum     >/dev/null 2>&1; then PKG="yum"
    else PKG=""; fi
}

install_prereqs() {
    detect_pkg_manager
    local pkgs=(curl git tar openssl ca-certificates)
    info "نصب پیش‌نیازها (${pkgs[*]}) ..."
    case "$PKG" in
        apt) apt-get update -y >/dev/null 2>&1 || true; DEBIAN_FRONTEND=noninteractive apt-get install -y "${pkgs[@]}" >/dev/null 2>&1 || true ;;
        dnf) dnf install -y "${pkgs[@]}" >/dev/null 2>&1 || true ;;
        yum) yum install -y "${pkgs[@]}" >/dev/null 2>&1 || true ;;
        *)   warn "پکیج‌منیجر ناشناخته؛ مطمئن شوید curl/git/tar/openssl نصب‌اند." ;;
    esac
}

install_docker() {
    if command -v docker >/dev/null 2>&1; then
        info "Docker از قبل نصب است."
    else
        info "نصب Docker ..."
        curl -fsSL --ipv4 https://get.docker.com | sh || die "نصب Docker ناموفق بود."
        systemctl enable --now docker >/dev/null 2>&1 || true
    fi
    # docker compose v2 plugin / fallback to v1
    if docker compose version >/dev/null 2>&1; then
        DC="docker compose"
    elif command -v docker-compose >/dev/null 2>&1; then
        DC="docker-compose"
    else
        warn "افزونهٔ docker compose یافت نشد؛ تلاش برای نصب ..."
        detect_pkg_manager
        case "$PKG" in
            apt) apt-get install -y docker-compose-plugin >/dev/null 2>&1 || true ;;
            dnf) dnf install -y docker-compose-plugin >/dev/null 2>&1 || true ;;
            yum) yum install -y docker-compose-plugin >/dev/null 2>&1 || true ;;
        esac
        if docker compose version >/dev/null 2>&1; then DC="docker compose"; else die "Docker Compose در دسترس نیست."; fi
    fi
}

DC="docker compose"
dc() { $DC -f "$COMPOSE_FILE" --project-directory "$APP_DIR" "$@"; }

rand() { tr -dc 'A-Za-z0-9' </dev/urandom | head -c "${1:-24}"; echo; }

public_ip() { curl -fsSL --ipv4 https://api.ipify.org 2>/dev/null || hostname -I 2>/dev/null | awk '{print $1}'; }

env_val() {  # read a decouple-style key (KEY = "value") from .env
    grep -E "^\s*${1}\s*=" "$ENV_FILE" 2>/dev/null | head -1 | sed -E 's/^[^=]*=\s*"?([^"]*)"?\s*$/\1/'
}

# DB / secret credentials shared between docker-compose.yml and .env.
# On update we reuse the values already stored in .env so passwords never change.
DB_NAME="guardino"; DB_USER="guardino"; DB_PASS=""; ROOT_PASS=""; SECRET=""
load_or_make_creds() {
    if [[ -f "$ENV_FILE" ]]; then
        DB_PASS="$(env_val MYSQL_PASSWORD)"
        ROOT_PASS="$(env_val MYSQL_ROOT_PASSWORD)"
        DB_NAME="$(env_val MYSQL_DATABASE)"; DB_NAME="${DB_NAME:-guardino}"
        DB_USER="$(env_val MYSQL_USER)";     DB_USER="${DB_USER:-guardino}"
        SECRET="$(env_val SECRET_KEY_STRING)"
    fi
    [[ -n "$DB_PASS"  ]] || DB_PASS="$(rand 24)"
    [[ -n "$ROOT_PASS" ]] || ROOT_PASS="$(rand 24)"
    [[ -n "$SECRET"   ]] || SECRET="$(rand 32)"
}

# ----------------------------------------------------------------------------- repo
clone_or_update_src() {
    mkdir -p "$APP_DIR" "$DATA_DIR" "$BACKUP_DIR"
    if [[ -d "${SRC_DIR}/.git" ]]; then
        info "به‌روزرسانی سورس از گیت‌هاب ..."
        git -C "$SRC_DIR" fetch --depth 1 origin "$REPO_BRANCH" >/dev/null 2>&1 || die "git fetch ناموفق."
        git -C "$SRC_DIR" reset --hard "origin/${REPO_BRANCH}" >/dev/null 2>&1 || die "git reset ناموفق."
    else
        info "دریافت سورس از ${REPO_URL} ..."
        rm -rf "$SRC_DIR"
        git clone --depth 1 -b "$REPO_BRANCH" "$REPO_URL" "$SRC_DIR" >/dev/null 2>&1 || die "git clone ناموفق."
    fi
}

# ----------------------------------------------------------------------------- compose
write_compose() {
    cat > "$COMPOSE_FILE" <<YAML
# Generated by the GuardinoBot installer. Edit with care.
name: guardinobot

services:
  bot:
    build:
      context: ./src
    image: guardinobot:local
    restart: on-failure
    env_file:
      - .env
    ports:
      - "127.0.0.1:3333:3333"
    depends_on:
      mariadb:
        condition: service_healthy
      redis:
        condition: service_started

  redis:
    image: redis:alpine
    restart: always
    command: redis-server --appendonly yes --replica-read-only no
    volumes:
      - "${DATA_DIR}/redis:/data"

  mariadb:
    image: mariadb:11
    restart: always
    environment:
      MYSQL_ROOT_PASSWORD: "${ROOT_PASS}"
      MYSQL_DATABASE: "${DB_NAME}"
      MYSQL_USER: "${DB_USER}"
      MYSQL_PASSWORD: "${DB_PASS}"
    volumes:
      - "${DATA_DIR}/mariadb:/var/lib/mysql"
    healthcheck:
      test: ["CMD", "healthcheck.sh", "--connect", "--innodb_initialized"]
      interval: 10s
      timeout: 5s
      retries: 12
YAML
    info "docker-compose.yml ساخته شد: ${COMPOSE_FILE}"
}

# ----------------------------------------------------------------------------- .env
write_env() {
    if [[ -f "$ENV_FILE" ]]; then
        warn ".env از قبل وجود دارد؛ حفظ شد (برای تغییر از گزینهٔ «ویرایش .env» استفاده کنید)."
        return
    fi

    echo
    read -rp "${CYAN}توکن ربات تلگرام (BOT_TOKEN): ${NC}" BOT_TOKEN
    [[ -n "$BOT_TOKEN" ]] || die "BOT_TOKEN الزامی است."

    echo "${CYAN}آیدی عددی سوپر-ادمین(ها) را وارد کنید (هر کدام در یک خط، با Enter خالی پایان دهید):${NC}"
    local SUPER_USERS="" line
    while true; do
        read -rp "  user id: " line || true
        [[ -z "$line" ]] && break
        SUPER_USERS+="${line}"$'\n'
    done
    [[ -n "$SUPER_USERS" ]] || warn "هیچ سوپر-ادمینی وارد نشد؛ بعداً در .env اضافه کنید."

    local ip; ip="$(public_ip)"
    read -rp "${CYAN}آدرس پایهٔ وب‌هوک/کال‌بک (WEBHOOK_BASE_URL) [http://${ip}:3333]: ${NC}" WEBHOOK_BASE_URL
    WEBHOOK_BASE_URL="${WEBHOOK_BASE_URL:-http://${ip}:3333}"

    umask 077
    cat > "$ENV_FILE" <<ENV
# ---- GuardinoBot env (generated by installer) ----
LOG_LEVEL = "info"

BOT_TOKEN = "${BOT_TOKEN}"

SUPER_USERS = "
${SUPER_USERS}"

WEBHOOK_BASE_URL = "${WEBHOOK_BASE_URL}"

# database (matches the mariadb service in docker-compose.yml)
DATABASE_URL = "mysql://${DB_USER}:${DB_PASS}@mariadb:3306/${DB_NAME}"

# redis (service name in docker-compose.yml)
REDIS_HOST = "redis"
REDIS_PORT = 6379
REDIS_DB = 0

# webapp (payment IPN / panel webhooks)
WEBAPP_HOST = "0.0.0.0"
WEBAPP_PORT = 3333

# key used to encrypt secrets stored in DB (max 32 chars) - DO NOT change after install
SECRET_KEY_STRING = "${SECRET}"

# default username prefix for created proxies
DEFAULT_USERNAME_PREFIX = "Guardino"

# ---- DB credentials (also baked into docker-compose.yml; kept here so the
# installer can reuse the same passwords on update/backup) ----
MYSQL_ROOT_PASSWORD = "${ROOT_PASS}"
MYSQL_DATABASE = "${DB_NAME}"
MYSQL_USER = "${DB_USER}"
MYSQL_PASSWORD = "${DB_PASS}"
ENV
    chmod 600 "$ENV_FILE"
    info ".env ساخته شد: ${ENV_FILE} (اسرار به‌صورت تصادفی تولید شدند)."
}

install_cli() {
    # save a local copy + a convenience command
    install -m 0755 -D "$SRC_DIR/installer/guardino.sh" "$BIN_PATH" 2>/dev/null || {
        # fallback: fetch fresh copy
        curl -fsSL --ipv4 "$RAW_SCRIPT" -o "$BIN_PATH" 2>/dev/null && chmod 0755 "$BIN_PATH" || true
    }
    [[ -f "$BIN_PATH" ]] && info "دستور مدیریت نصب شد: ${CYAN}guardinobot${NC}"
}

# ----------------------------------------------------------------------------- actions
do_install() {
    need_root
    install_prereqs
    install_docker
    clone_or_update_src
    load_or_make_creds
    write_compose
    write_env
    install_cli
    info "ساخت ایمیج و اجرا (ممکن است چند دقیقه طول بکشد) ..."
    dc up -d --build
    hr
    info "${APP_NAME} نصب و اجرا شد."
    echo "  • مدیریت بعدی:    ${CYAN}guardinobot${NC}"
    echo "  • لاگ زنده:        ${CYAN}guardinobot${NC} → گزینهٔ لاگ"
    echo "  • فایل تنظیمات:    ${ENV_FILE}"
    echo "  • migration دیتابیس به‌صورت خودکار هنگام استارت اعمال می‌شود (aerich upgrade)."
    hr
}

require_installed() {
    [[ -f "$COMPOSE_FILE" ]] || die "${APP_NAME} نصب نشده است. ابتدا گزینهٔ نصب را اجرا کنید."
    # pick the available compose command for management actions
    if docker compose version >/dev/null 2>&1; then DC="docker compose"
    elif command -v docker-compose >/dev/null 2>&1; then DC="docker-compose"; fi
}

do_update() {
    need_root; require_installed; install_docker
    clone_or_update_src
    load_or_make_creds
    write_compose   # refresh compose in case the template changed
    info "ساخت مجدد ایمیج و راه‌اندازی ..."
    dc up -d --build
    dc image prune -f >/dev/null 2>&1 || true
    info "به‌روزرسانی کامل شد. (migration هنگام استارت اعمال شد.)"
}

do_logs() {
    require_installed
    echo "سرویس؟ [bot] / mariadb / redis  (Enter = bot، خروج با Ctrl+C)"
    read -rp "service: " svc || true
    svc="${svc:-bot}"
    dc logs -f --tail=200 "$svc"
}

do_backup() {
    require_installed
    mkdir -p "$BACKUP_DIR"
    local ts; ts="$(date +%Y%m%d-%H%M%S)"
    local tmp; tmp="$(mktemp -d)"
    info "تهیهٔ بکاپ ..."

    # parse DB creds from .env DATABASE_URL: mysql://user:pass@host:port/db
    local url user pass db
    url="$(grep -E '^\s*DATABASE_URL' "$ENV_FILE" | head -1 | sed -E 's/.*=\s*"?([^"]*)"?\s*$/\1/')"
    user="$(echo "$url" | sed -E 's#^mysql://([^:]+):.*#\1#')"
    pass="$(echo "$url" | sed -E 's#^mysql://[^:]+:([^@]+)@.*#\1#')"
    db="$(echo "$url"   | sed -E 's#.*/([^/?]+)(\?.*)?$#\1#')"

    if [[ -n "$db" && -n "$user" ]]; then
        info "دامپ دیتابیس ${db} ..."
        dc exec -T mariadb sh -c "exec mysqldump -u'${user}' -p'${pass}' --single-transaction --routines --triggers '${db}'" \
            > "${tmp}/database.sql" 2>/dev/null || warn "دامپ دیتابیس ناموفق بود (آیا کانتینر بالا است؟)."
    fi
    cp -f "$ENV_FILE" "${tmp}/.env" 2>/dev/null || true
    cp -f "$COMPOSE_FILE" "${tmp}/docker-compose.yml" 2>/dev/null || true
    # redis snapshot (best effort)
    dc exec -T redis sh -c "redis-cli save >/dev/null 2>&1" || true
    cp -f "${DATA_DIR}/redis/dump.rdb" "${tmp}/redis-dump.rdb" 2>/dev/null || true

    local out="${BACKUP_DIR}/guardinobot-backup-${ts}.tar.gz"
    tar -czf "$out" -C "$tmp" . 2>/dev/null
    rm -rf "$tmp"
    info "بکاپ ساخته شد: ${CYAN}${out}${NC}"
    ls -1t "$BACKUP_DIR"/*.tar.gz 2>/dev/null | tail -n +11 | xargs -r rm -f   # keep last 10
}

do_restart() { require_installed; dc restart; info "ری‌استارت شد."; }
do_stop()    { require_installed; dc down; info "متوقف شد."; }
do_start()   { require_installed; dc up -d; info "اجرا شد."; }
do_status()  { require_installed; dc ps; }
do_edit_env(){ require_installed; "${EDITOR:-nano}" "$ENV_FILE"; warn "برای اعمال تغییرات، ربات را ری‌استارت کنید."; }

do_uninstall() {
    need_root; require_installed
    warn "این کار کانتینرها را حذف می‌کند."
    read -rp "ادامه؟ (yes/no): " a; [[ "$a" == "yes" ]] || { info "لغو شد."; return; }
    dc down || true
    read -rp "${RED}دیتابیس و داده‌ها (${DATA_DIR}) هم پاک شوند؟ این کار برگشت‌ناپذیر است (yes/no): ${NC}" b
    if [[ "$b" == "yes" ]]; then
        rm -rf "$DATA_DIR" "$APP_DIR"
        rm -f "$BIN_PATH"
        info "همه‌چیز حذف شد."
    else
        info "کانتینرها حذف شدند؛ داده‌ها در ${DATA_DIR} حفظ شد."
    fi
}

# ----------------------------------------------------------------------------- menu
menu() {
    while true; do
        echo
        hr
        echo "  ${CYAN}${APP_NAME}${NC} — مدیریت نصب"
        hr
        echo "  1) نصب / نصب مجدد"
        echo "  2) به‌روزرسانی (git pull + rebuild)"
        echo "  3) مشاهدهٔ لاگ"
        echo "  4) تهیهٔ بکاپ"
        echo "  5) ری‌استارت"
        echo "  6) توقف"
        echo "  7) اجرا"
        echo "  8) وضعیت سرویس‌ها"
        echo "  9) ویرایش فایل تنظیمات (.env)"
        echo " 10) حذف نصب"
        echo "  0) خروج"
        hr
        read -rp "انتخاب: " choice || exit 0
        case "$choice" in
            1) do_install ;;
            2) do_update ;;
            3) do_logs ;;
            4) do_backup ;;
            5) do_restart ;;
            6) do_stop ;;
            7) do_start ;;
            8) do_status ;;
            9) do_edit_env ;;
            10) do_uninstall ;;
            0) exit 0 ;;
            *) warn "گزینهٔ نامعتبر." ;;
        esac
    done
}

# allow non-interactive subcommands: guardinobot install|update|logs|backup|...
case "${1:-}" in
    install)   do_install ;;
    update)    do_update ;;
    logs)      do_logs ;;
    backup)    do_backup ;;
    restart)   do_restart ;;
    stop)      do_stop ;;
    start)     do_start ;;
    status)    do_status ;;
    uninstall) do_uninstall ;;
    "")        menu ;;
    *)         die "زیردستور ناشناخته: ${1}. مجاز: install|update|logs|backup|restart|stop|start|status|uninstall" ;;
esac
