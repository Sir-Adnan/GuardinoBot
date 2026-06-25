#!/usr/bin/env bash
#
# GuardinoBot installer / manager
# Repo:   https://github.com/Sir-Adnan/GuardinoBot
# Author: UnknownZero
#
# Usage:
#   bash <(curl -Ls --ipv4 https://raw.githubusercontent.com/Sir-Adnan/GuardinoBot/main/installer/guardinobot.sh)
#
# Menu: install | update | domain | logs | backup | restart | status | edit env | uninstall
#
# What it deploys (docker compose):
#   bot · api (web-panel API) · webpanel (React SPA) · redis · mariadb · phpmyadmin
#   (+ caddy with automatic HTTPS when a domain is configured)
#
set -euo pipefail

# ----------------------------------------------------------------------------- constants
APP_NAME="GuardinoBot"
REPO_URL="https://github.com/Sir-Adnan/GuardinoBot.git"
REPO_BRANCH="main"
RAW_SCRIPT="https://raw.githubusercontent.com/Sir-Adnan/GuardinoBot/main/installer/guardinobot.sh"

APP_DIR="/opt/GuardinoBot"        # holds generated compose + .env
SRC_DIR="${APP_DIR}/src"          # git clone of the repo (build context)
DATA_DIR="/var/lib/guardinobot"   # persistent docker volumes + backups
COMPOSE_FILE="${APP_DIR}/docker-compose.yml"
ENV_FILE="${APP_DIR}/.env"
CADDY_DIR="${DATA_DIR}/caddy"
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
        die "This script must run as root. Use sudo."
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
    info "Installing prerequisites (${pkgs[*]}) ..."
    case "$PKG" in
        apt) apt-get update -y >/dev/null 2>&1 || true; DEBIAN_FRONTEND=noninteractive apt-get install -y "${pkgs[@]}" >/dev/null 2>&1 || true ;;
        dnf) dnf install -y "${pkgs[@]}" >/dev/null 2>&1 || true ;;
        yum) yum install -y "${pkgs[@]}" >/dev/null 2>&1 || true ;;
        *)   warn "Unknown package manager; make sure curl/git/tar/openssl are installed." ;;
    esac
}

install_docker() {
    if command -v docker >/dev/null 2>&1; then
        info "Docker is already installed."
    else
        info "Installing Docker ..."
        curl -fsSL --ipv4 https://get.docker.com | sh || die "Docker installation failed."
        systemctl enable --now docker >/dev/null 2>&1 || true
    fi
    if docker compose version >/dev/null 2>&1; then
        DC="docker compose"
    elif command -v docker-compose >/dev/null 2>&1; then
        DC="docker-compose"
    else
        warn "docker compose plugin not found; trying to install ..."
        detect_pkg_manager
        case "$PKG" in
            apt) apt-get install -y docker-compose-plugin >/dev/null 2>&1 || true ;;
            dnf) dnf install -y docker-compose-plugin >/dev/null 2>&1 || true ;;
            yum) yum install -y docker-compose-plugin >/dev/null 2>&1 || true ;;
        esac
        if docker compose version >/dev/null 2>&1; then DC="docker compose"; else die "Docker Compose is not available."; fi
    fi
}

DC="docker compose"
dc() { $DC -f "$COMPOSE_FILE" --project-directory "$APP_DIR" "$@"; }

rand() { tr -dc 'A-Za-z0-9' </dev/urandom | head -c "${1:-24}"; echo; }

public_ip() { curl -fsSL --ipv4 https://api.ipify.org 2>/dev/null || hostname -I 2>/dev/null | awk '{print $1}'; }

# read a decouple-style key (KEY = "value") from .env; never fails (set -e safe)
env_val() {
    grep -E "^\s*${1}\s*=" "$ENV_FILE" 2>/dev/null | head -1 | sed -E 's/^[^=]*=\s*"?([^"]*)"?\s*$/\1/' || true
}

# add KEY only if absent (append-only; used on update so existing values stay)
ensure_kv() {
    local key="$1" def="$2"
    grep -qE "^\s*${key}\s*=" "$ENV_FILE" 2>/dev/null || printf '%s = "%s"\n' "$key" "$def" >> "$ENV_FILE"
}

# set/replace KEY = "value" in .env (escapes sed-special chars in value)
set_env_kv() {
    local key="$1" val="$2" esc
    esc="${val//\\/\\\\}"; esc="${esc//|/\\|}"; esc="${esc//&/\\&}"
    if grep -qE "^\s*${key}\s*=" "$ENV_FILE" 2>/dev/null; then
        sed -i -E "s|^\s*${key}\s*=.*|${key} = \"${esc}\"|" "$ENV_FILE"
    else
        printf '%s = "%s"\n' "$key" "$val" >> "$ENV_FILE"
    fi
}

# ensure every key the current app version needs exists (append missing only).
# THIS is what makes 'update' pick up new env vars from new releases.
ensure_env_keys() {
    [[ -f "$ENV_FILE" ]] || return 0
    ensure_kv WEB_JWT_SECRET "$(rand 32)"
    ensure_kv WEB_CORS_ORIGINS "*"
    ensure_kv DOMAIN ""
    ensure_kv DEFAULT_USERNAME_PREFIX "Guardino"
}

# DB / secret credentials + domain, shared between compose and .env.
# On update we reuse what's already in .env so nothing rotates.
DB_NAME="guardino"; DB_USER="guardino"; DB_PASS=""; ROOT_PASS=""; SECRET=""; WEB_JWT=""; DOMAIN=""
load_or_make_creds() {
    if [[ -f "$ENV_FILE" ]]; then
        DB_PASS="$(env_val MYSQL_PASSWORD)"
        ROOT_PASS="$(env_val MYSQL_ROOT_PASSWORD)"
        DB_NAME="$(env_val MYSQL_DATABASE)"; DB_NAME="${DB_NAME:-guardino}"
        DB_USER="$(env_val MYSQL_USER)";     DB_USER="${DB_USER:-guardino}"
        SECRET="$(env_val SECRET_KEY_STRING)"
        WEB_JWT="$(env_val WEB_JWT_SECRET)"
        DOMAIN="$(env_val DOMAIN)"
    fi
    [[ -n "$DB_PASS"   ]] || DB_PASS="$(rand 24)"
    [[ -n "$ROOT_PASS" ]] || ROOT_PASS="$(rand 24)"
    [[ -n "$SECRET"    ]] || SECRET="$(rand 32)"
    [[ -n "$WEB_JWT"   ]] || WEB_JWT="$(rand 32)"
}

# ----------------------------------------------------------------------------- domain
prompt_domain() {
    echo
    echo "${CYAN}Domain for the bot + web panel${NC} (e.g. panel.example.com or example.com)."
    echo "  - Point the domain's A record to THIS server's IP first."
    echo "  - Ports 80 and 443 must be free & open (Caddy fetches HTTPS automatically)."
    echo "  - Leave empty to keep current, or type '-' to run on IP without HTTPS."
    local cur="$DOMAIN" ans
    read -rp "Domain [${cur:-none}]: " ans || true
    if   [[ "$ans" == "-" ]]; then DOMAIN=""
    elif [[ -n "$ans" ]];    then DOMAIN="$(echo "$ans" | tr -d ' ' | sed -E 's#^https?://##; s#/.*$##')"
    else DOMAIN="$cur"; fi
    if [[ -n "$DOMAIN" ]]; then info "Domain: ${DOMAIN} (HTTPS via Caddy)"; else info "No domain: serving on IP (no HTTPS)."; fi
}

sync_domain_env() {
    set_env_kv DOMAIN "$DOMAIN"
    if [[ -n "$DOMAIN" ]]; then
        set_env_kv WEBHOOK_BASE_URL "https://${DOMAIN}"
    else
        set_env_kv WEBHOOK_BASE_URL "http://$(public_ip):3333"
    fi
}

# ----------------------------------------------------------------------------- repo
clone_or_update_src() {
    mkdir -p "$APP_DIR" "$DATA_DIR" "$BACKUP_DIR"
    if [[ -d "${SRC_DIR}/.git" ]]; then
        info "Updating source from GitHub ..."
        git -C "$SRC_DIR" fetch --depth 1 origin "$REPO_BRANCH" >/dev/null 2>&1 || die "git fetch failed."
        git -C "$SRC_DIR" reset --hard "origin/${REPO_BRANCH}" >/dev/null 2>&1 || die "git reset failed."
    else
        info "Cloning source from ${REPO_URL} ..."
        rm -rf "$SRC_DIR"
        git clone --depth 1 -b "$REPO_BRANCH" "$REPO_URL" "$SRC_DIR" >/dev/null 2>&1 || die "git clone failed."
    fi
}

# ----------------------------------------------------------------------------- compose
write_compose() {
    local pub_bot="" pub_panel=""
    if [[ -z "$DOMAIN" ]]; then
        # no reverse proxy: expose the bot webhook port + the panel to the host
        pub_bot=$'    ports:\n      - "0.0.0.0:3333:3333"'
        pub_panel=$'    ports:\n      - "0.0.0.0:8080:80"'
    fi

    cat > "$COMPOSE_FILE" <<YAML
# Generated by the GuardinoBot installer. Regenerated on every install/update.
name: guardinobot

services:
  bot:
    build:
      context: ./src
    image: guardinobot:local
    restart: on-failure
    env_file:
      - .env
    expose:
      - "3333"
${pub_bot}
    depends_on:
      mariadb:
        condition: service_healthy
      redis:
        condition: service_started

  api:
    build:
      context: ./src
    image: guardinobot:local
    restart: on-failure
    command: uvicorn app.api.main:app --host 0.0.0.0 --port 8000
    env_file:
      - .env
    expose:
      - "8000"
    depends_on:
      mariadb:
        condition: service_healthy
      redis:
        condition: service_started

  webpanel:
    build:
      context: ./src/webpanel
    image: guardinobot-webpanel:local
    restart: on-failure
    expose:
      - "80"
${pub_panel}
    depends_on:
      - api

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

  phpmyadmin:
    image: phpmyadmin:latest
    restart: on-failure
    environment:
      PMA_HOST: mariadb
      PMA_PORT: 3306
      UPLOAD_LIMIT: 256M
    ports:
      # localhost only — reach it over an SSH tunnel (secure by default)
      - "127.0.0.1:8081:80"
    depends_on:
      mariadb:
        condition: service_healthy
YAML

    if [[ -n "$DOMAIN" ]]; then
        cat >> "$COMPOSE_FILE" <<YAML

  caddy:
    image: caddy:2-alpine
    restart: on-failure
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - "${CADDY_DIR}/Caddyfile:/etc/caddy/Caddyfile:ro"
      - "${CADDY_DIR}/data:/data"
      - "${CADDY_DIR}/config:/config"
    depends_on:
      - bot
      - api
      - webpanel
YAML
    fi
    info "Wrote ${COMPOSE_FILE}"
}

write_caddyfile() {
    [[ -n "$DOMAIN" ]] || return 0
    mkdir -p "${CADDY_DIR}/data" "${CADDY_DIR}/config"
    # bot owns: /webhook, /qr and the payment-gateway callback paths.
    # everything else (/, /api) goes to the web panel (nginx serves the SPA
    # and proxies /api -> api internally).
    cat > "${CADDY_DIR}/Caddyfile" <<CADDY
${DOMAIN} {
    encode zstd gzip

    @bot path /webhook/* /npipn /npipn/* /pay-json /pay-json/* /payping /payping/* /aqaye_pardakht /aqaye_pardakht/* /zibal /zibal/* /zarinpal /zarinpal/* /tronseller /tronseller/* /qr/*
    handle @bot {
        reverse_proxy bot:3333
    }

    handle {
        reverse_proxy webpanel:80
    }
}
CADDY
    info "Wrote Caddyfile for ${DOMAIN}"
}

# ----------------------------------------------------------------------------- .env
write_env() {
    if [[ -f "$ENV_FILE" ]]; then
        info ".env already exists; keeping your values."
        return
    fi

    echo
    read -rp "${CYAN}Telegram bot token (BOT_TOKEN): ${NC}" BOT_TOKEN
    [[ -n "$BOT_TOKEN" ]] || die "BOT_TOKEN is required."

    echo "${CYAN}Super-admin numeric ID(s). One per line, empty line to finish:${NC}"
    local SUPER_USERS="" line
    while true; do
        read -rp "  user id: " line || true
        [[ -z "$line" ]] && break
        SUPER_USERS+="${line}"$'\n'
    done
    [[ -n "$SUPER_USERS" ]] || warn "No super-admin entered; add one later in .env."

    local base
    if [[ -n "$DOMAIN" ]]; then base="https://${DOMAIN}"; else base="http://$(public_ip):3333"; fi

    umask 077
    cat > "$ENV_FILE" <<ENV
# ---- GuardinoBot env (generated by installer) ----
LOG_LEVEL = "info"

BOT_TOKEN = "${BOT_TOKEN}"

SUPER_USERS = "
${SUPER_USERS}"

# public base url for payment callbacks / panel webhooks
WEBHOOK_BASE_URL = "${base}"

# domain the panel/bot are served on ("" = IP mode, no HTTPS)
DOMAIN = "${DOMAIN}"

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

# web admin/reseller panel (§9)
WEB_JWT_SECRET = "${WEB_JWT}"
WEB_CORS_ORIGINS = "*"

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
    info "Wrote .env: ${ENV_FILE} (secrets were generated randomly)."
}

install_cli() {
    install -m 0755 -D "$SRC_DIR/installer/guardinobot.sh" "$BIN_PATH" 2>/dev/null || {
        curl -fsSL --ipv4 "$RAW_SCRIPT" -o "$BIN_PATH" 2>/dev/null && chmod 0755 "$BIN_PATH" || true
    }
    [[ -f "$BIN_PATH" ]] && info "Management command installed: ${CYAN}guardinobot${NC}"
}

print_access_info() {
    hr
    info "${APP_NAME} is up."
    if [[ -n "$DOMAIN" ]]; then
        echo "  Web panel:     ${CYAN}https://${DOMAIN}/${NC}"
        echo "  Payment/webhook base: ${CYAN}https://${DOMAIN}${NC}"
        echo "  ${YELLOW}DNS A record must point to this server and 80/443 must be open${NC}"
        echo "  (Caddy may take ~30s on first run to issue the certificate.)"
    else
        local ip; ip="$(public_ip)"
        echo "  Web panel:     ${CYAN}http://${ip}:8080/${NC}"
        echo "  Payment/webhook base: ${CYAN}http://${ip}:3333${NC}"
        echo "  ${YELLOW}Tip: set a domain (menu option) to get HTTPS automatically.${NC}"
    fi
    echo "  phpMyAdmin:    open an SSH tunnel, then browse ${CYAN}http://localhost:8081${NC}"
    echo "                 ${CYAN}ssh -L 8081:localhost:8081 root@<server-ip>${NC}"
    echo "                 (login: db user '${DB_USER}' — credentials are in ${ENV_FILE})"
    echo "  Panel login:   enter a super-admin's Telegram ID; the code is sent by the bot."
    echo "  DB migrations apply automatically on start (aerich upgrade)."
    hr
}

# ----------------------------------------------------------------------------- actions
do_install() {
    need_root
    install_prereqs
    install_docker
    clone_or_update_src
    load_or_make_creds
    prompt_domain
    write_env
    sync_domain_env       # apply domain-derived keys (covers reinstall w/ changed domain)
    ensure_env_keys       # make sure any newer keys exist too
    write_compose
    write_caddyfile
    install_cli
    info "Building images and starting (this may take a few minutes) ..."
    dc up -d --build
    print_access_info
}

require_installed() {
    [[ -f "$COMPOSE_FILE" ]] || die "${APP_NAME} is not installed. Run the install option first."
    if docker compose version >/dev/null 2>&1; then DC="docker compose"
    elif command -v docker-compose >/dev/null 2>&1; then DC="docker-compose"; fi
}

do_update() {
    need_root; require_installed; install_docker
    clone_or_update_src
    load_or_make_creds      # also loads existing DOMAIN, so the proxy stays as-is
    ensure_env_keys         # append any NEW env keys this release added
    write_compose           # regenerate compose (picks up new services like api/webpanel)
    write_caddyfile
    info "Rebuilding images and starting ..."
    dc up -d --build
    dc image prune -f >/dev/null 2>&1 || true
    info "Update complete. (Migrations applied on start.)"
    print_access_info
}

do_set_domain() {
    need_root; require_installed
    load_or_make_creds
    prompt_domain
    sync_domain_env
    write_compose
    write_caddyfile
    info "Applying domain configuration ..."
    dc up -d --build
    print_access_info
}

do_logs() {
    require_installed
    echo "Service? [bot] / api / webpanel / caddy / mariadb / redis / phpmyadmin  (Enter = bot, Ctrl+C to exit)"
    read -rp "service: " svc || true
    svc="${svc:-bot}"
    dc logs -f --tail=200 "$svc"
}

do_backup() {
    require_installed
    mkdir -p "$BACKUP_DIR"
    local ts; ts="$(date +%Y%m%d-%H%M%S)"
    local tmp; tmp="$(mktemp -d)"
    info "Creating backup ..."

    local url user pass db
    url="$(grep -E '^\s*DATABASE_URL' "$ENV_FILE" | head -1 | sed -E 's/.*=\s*"?([^"]*)"?\s*$/\1/')"
    user="$(echo "$url" | sed -E 's#^mysql://([^:]+):.*#\1#')"
    pass="$(echo "$url" | sed -E 's#^mysql://[^:]+:([^@]+)@.*#\1#')"
    db="$(echo "$url"   | sed -E 's#.*/([^/?]+)(\?.*)?$#\1#')"

    if [[ -n "$db" && -n "$user" ]]; then
        info "Dumping database ${db} ..."
        dc exec -T mariadb sh -c "exec mysqldump -u'${user}' -p'${pass}' --single-transaction --routines --triggers '${db}'" \
            > "${tmp}/database.sql" 2>/dev/null || warn "Database dump failed (is the container up?)."
    fi
    cp -f "$ENV_FILE" "${tmp}/.env" 2>/dev/null || true
    cp -f "$COMPOSE_FILE" "${tmp}/docker-compose.yml" 2>/dev/null || true
    dc exec -T redis sh -c "redis-cli save >/dev/null 2>&1" || true
    cp -f "${DATA_DIR}/redis/dump.rdb" "${tmp}/redis-dump.rdb" 2>/dev/null || true

    local out="${BACKUP_DIR}/guardinobot-backup-${ts}.tar.gz"
    tar -czf "$out" -C "$tmp" . 2>/dev/null
    rm -rf "$tmp"
    info "Backup created: ${CYAN}${out}${NC}"
    ls -1t "$BACKUP_DIR"/*.tar.gz 2>/dev/null | tail -n +11 | xargs -r rm -f   # keep last 10
}

do_restart() { require_installed; dc restart; info "Restarted."; }
do_stop()    { require_installed; dc down; info "Stopped."; }
do_start()   { require_installed; dc up -d; info "Started."; }
do_status()  { require_installed; dc ps; }
do_edit_env(){ require_installed; "${EDITOR:-nano}" "$ENV_FILE"; warn "Restart the bot to apply changes (menu -> Restart)."; }

do_uninstall() {
    need_root; require_installed
    warn "This will remove the containers."
    read -rp "Continue? (yes/no): " a; [[ "$a" == "yes" ]] || { info "Cancelled."; return; }
    dc down || true
    read -rp "${RED}Also delete database and data (${DATA_DIR})? This is irreversible (yes/no): ${NC}" b
    if [[ "$b" == "yes" ]]; then
        rm -rf "$DATA_DIR" "$APP_DIR"
        rm -f "$BIN_PATH"
        info "Everything removed."
    else
        info "Containers removed; data kept in ${DATA_DIR}."
    fi
}

# ----------------------------------------------------------------------------- menu
menu() {
    while true; do
        echo
        hr
        echo "  ${CYAN}${APP_NAME}${NC} - management"
        hr
        echo "  1) Install / Reinstall"
        echo "  2) Update (git pull + rebuild, keeps data & .env)"
        echo "  3) Set / change domain (HTTPS via Caddy)"
        echo "  4) View logs"
        echo "  5) Backup"
        echo "  6) Restart"
        echo "  7) Stop"
        echo "  8) Start"
        echo "  9) Status"
        echo " 10) Edit config (.env)"
        echo " 11) Uninstall"
        echo "  0) Exit"
        hr
        read -rp "Choice: " choice || exit 0
        case "$choice" in
            1) do_install ;;
            2) do_update ;;
            3) do_set_domain ;;
            4) do_logs ;;
            5) do_backup ;;
            6) do_restart ;;
            7) do_stop ;;
            8) do_start ;;
            9) do_status ;;
            10) do_edit_env ;;
            11) do_uninstall ;;
            0) exit 0 ;;
            *) warn "Invalid option." ;;
        esac
    done
}

# allow non-interactive subcommands
case "${1:-}" in
    install)   do_install ;;
    update)    do_update ;;
    domain)    do_set_domain ;;
    logs)      do_logs ;;
    backup)    do_backup ;;
    restart)   do_restart ;;
    stop)      do_stop ;;
    start)     do_start ;;
    status)    do_status ;;
    uninstall) do_uninstall ;;
    "")        menu ;;
    *)         die "Unknown subcommand: ${1}. Allowed: install|update|domain|logs|backup|restart|stop|start|status|uninstall" ;;
esac
