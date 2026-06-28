#!/usr/bin/env bash
#
# GuardinoBot multi-instance installer / manager
# Repo:   https://github.com/Sir-Adnan/GuardinoBot
# Author: UnknownZero
#
# Runs MANY independent bots on one server. One shared "platform" (MariaDB + Redis
# + Caddy + phpMyAdmin) + one isolated app stack (bot · api · webpanel) per bot,
# each with its own database, its own Redis logical DB, its own .env/token, and its
# own HTTPS subdomain. No bot can see another's data; backup/restore is per-bot.
#
# Usage:
#   bash <(curl -Ls --ipv4 https://raw.githubusercontent.com/Sir-Adnan/GuardinoBot/main/installer/guardino.sh)
#   guardino <add|update|backup|restore|list|remove|logs|...> [name] [args]
#
set -euo pipefail

# ----------------------------------------------------------------------------- constants
APP_NAME="GuardinoBot"
REPO_URL="https://github.com/Sir-Adnan/GuardinoBot.git"
REPO_BRANCH="main"
RAW_SCRIPT="https://raw.githubusercontent.com/Sir-Adnan/GuardinoBot/main/installer/guardino.sh"

ROOT_DIR="/opt/guardino"
SRC_DIR="${ROOT_DIR}/src"                 # ONE shared git clone (build context)
PLATFORM_DIR="${ROOT_DIR}/platform"
INSTANCES_DIR="${ROOT_DIR}/instances"
REGISTRY="${ROOT_DIR}/registry.tsv"
PLATFORM_COMPOSE="${PLATFORM_DIR}/docker-compose.platform.yml"
PLATFORM_ENV="${PLATFORM_DIR}/.env.platform"
CADDY_DIR="${PLATFORM_DIR}/caddy"

DATA_DIR="/var/lib/guardino"
PLATFORM_DATA="${DATA_DIR}/platform"
BACKUP_ROOT="${DATA_DIR}/backups"

NET="guardino_net"
PLATFORM_PROJECT="guardino-platform"
BOT_IMAGE="guardinobot:local"
WEB_IMAGE="guardinobot-webpanel:local"
BIN_PATH="/usr/local/bin/guardino"

# legacy single-instance install (source for migrate-legacy)
LEGACY_APP_DIR="/opt/GuardinoBot"
LEGACY_DATA_DIR="/var/lib/guardinobot"

# Every bot-owned webapp path (Caddy routes these to the bot; everything else to
# the web panel). Keep COMPLETE — a missing path = a silently dead IPN/webhook.
# Audited from app/views/* + app/plugins/payment/*/views.py.
WEBHOOK_PATHS='/webhook/* /qr/* /npipn /npipn/* /plisio /plisio/* /payments/* /pay-json /pay-json/* /payping /payping/* /aqaye_pardakht /aqaye_pardakht/* /zibal /zibal/* /zarinpal /zarinpal/* /tronseller /tronseller/*'

# ----------------------------------------------------------------------------- colors / log
if [[ -t 1 ]]; then
    RED=$'\e[1;31m'; GREEN=$'\e[1;32m'; YELLOW=$'\e[1;33m'; BLUE=$'\e[1;34m'; CYAN=$'\e[1;36m'; NC=$'\e[0m'
else
    RED=""; GREEN=""; YELLOW=""; BLUE=""; CYAN=""; NC=""
fi
info() { echo "${GREEN}[+]${NC} $*"; }
warn() { echo "${YELLOW}[!]${NC} $*"; }
err()  { echo "${RED}[x]${NC} $*" >&2; }
die()  { err "$*"; exit 1; }
hr()   { echo "${BLUE}--------------------------------------------------${NC}"; }

# ----------------------------------------------------------------------------- preflight
need_root() { [[ "$(id -u)" -eq 0 ]] || die "This script must run as root. Use sudo."; }

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
        *)   warn "Unknown package manager; ensure curl/git/tar/openssl are installed." ;;
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
    docker compose version >/dev/null 2>&1 || {
        warn "docker compose plugin not found; trying to install ..."
        detect_pkg_manager
        case "$PKG" in
            apt) apt-get install -y docker-compose-plugin >/dev/null 2>&1 || true ;;
            dnf) dnf install -y docker-compose-plugin >/dev/null 2>&1 || true ;;
            yum) yum install -y docker-compose-plugin >/dev/null 2>&1 || true ;;
        esac
        docker compose version >/dev/null 2>&1 || die "Docker Compose is not available."
    }
}

rand()      { tr -dc 'A-Za-z0-9' </dev/urandom | head -c "${1:-24}"; echo; }
public_ip() { curl -fsSL --ipv4 https://api.ipify.org 2>/dev/null || hostname -I 2>/dev/null | awk '{print $1}'; }

# ----------------------------------------------------------------------------- env file helpers (KEY = "value")
env_get() { # <file> <key>
    [[ -f "$1" ]] || return 0
    grep -E "^\s*$2\s*=" "$1" 2>/dev/null | head -1 | sed -E 's/^[^=]*=\s*"?([^"]*)"?\s*$/\1/' || true
}
env_set() { # <file> <key> <value>
    local f="$1" key="$2" val="$3" esc
    esc="${val//\\/\\\\}"; esc="${esc//|/\\|}"; esc="${esc//&/\\&}"
    if grep -qE "^\s*${key}\s*=" "$f" 2>/dev/null; then
        sed -i -E "s|^\s*${key}\s*=.*|${key} = \"${esc}\"|" "$f"
    else
        printf '%s = "%s"\n' "$key" "$val" >> "$f"
    fi
}

# ----------------------------------------------------------------------------- name validation
sanitize() { echo "$1" | tr '[:upper:]' '[:lower:]' | tr -c 'a-z0-9' '_' | sed -E 's/_+/_/g; s/^_+//; s/_+$//'; }
validate_name() { # DNS-safe instance name
    [[ "$1" =~ ^[a-z0-9]([a-z0-9-]{0,30})?$ ]] || die "Invalid name '$1' (use a-z, 0-9, '-'; start alphanumeric; max 31)."
}

# ----------------------------------------------------------------------------- registry
reg_ensure() { mkdir -p "$ROOT_DIR"; [[ -f "$REGISTRY" ]] || : > "$REGISTRY"; }
reg_row()   { reg_ensure; awk -F'\t' -v n="$1" '$1==n{print; exit}' "$REGISTRY" || true; }
reg_has()   { [[ -n "$(reg_row "$1")" ]]; }
reg_field() { reg_row "$1" | cut -f"$2"; }      # 1name 2domain 3db 4user 5redisdb 6created
reg_names() { reg_ensure; cut -f1 "$REGISTRY" 2>/dev/null | grep -v '^$' || true; }
reg_del()   { reg_ensure; awk -F'\t' -v n="$1" '$1!=n' "$REGISTRY" > "${REGISTRY}.tmp" 2>/dev/null || true; mv -f "${REGISTRY}.tmp" "$REGISTRY"; }
reg_add()   { # name domain db user redisdb
    reg_del "$1"
    printf '%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "$2" "$3" "$4" "$5" "$(date +%Y-%m-%dT%H:%M:%S)" >> "$REGISTRY"
}
alloc_redis_db() { # lowest free index in 0..63
    reg_ensure
    local used i; used="$(cut -f5 "$REGISTRY" 2>/dev/null | grep -E '^[0-9]+$' || true)"
    for i in $(seq 0 63); do
        grep -qxF "$i" <<<"$used" || { echo "$i"; return 0; }
    done
    die "No free Redis DB index (max 64 bots per Redis). Add a second Redis or use a new server."
}

# ----------------------------------------------------------------------------- docker compose wrappers
dcp() { docker compose -p "$PLATFORM_PROJECT" -f "$PLATFORM_COMPOSE" --project-directory "$PLATFORM_DIR" "$@"; }
dci() { local n="$1"; shift; docker compose -p "guardino-${n}" -f "$(inst_compose "$n")" --project-directory "$(inst_dir "$n")" "$@"; }

inst_dir()     { echo "${INSTANCES_DIR}/$1"; }
inst_compose() { echo "${INSTANCES_DIR}/$1/docker-compose.yml"; }
inst_env()     { echo "${INSTANCES_DIR}/$1/.env"; }

# ----------------------------------------------------------------------------- mariadb (shared)
ROOT_PASS=""
load_platform_creds() {
    [[ -f "$PLATFORM_ENV" ]] && ROOT_PASS="$(env_get "$PLATFORM_ENV" ROOT_PASS)"
    [[ -n "$ROOT_PASS" ]] || ROOT_PASS="$(rand 28)"
}
mysql_root() { docker exec -i -e MYSQL_PWD="$ROOT_PASS" "${PLATFORM_PROJECT}-mariadb" mariadb -uroot -N "$@"; }
wait_mariadb() {
    info "Waiting for the shared database ..."
    local i
    for i in $(seq 1 60); do
        echo "SELECT 1" | mysql_root >/dev/null 2>&1 && { info "Database is ready."; return 0; }
        sleep 2
    done
    die "Shared MariaDB did not become ready."
}
create_db() { # db user pass
    mysql_root <<SQL
CREATE DATABASE IF NOT EXISTS \`$1\` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS '$2'@'%' IDENTIFIED BY '$3';
ALTER USER '$2'@'%' IDENTIFIED BY '$3';
GRANT ALL PRIVILEGES ON \`$1\`.* TO '$2'@'%';
FLUSH PRIVILEGES;
SQL
}
drop_db() { # db user
    mysql_root <<SQL || true
DROP DATABASE IF EXISTS \`$1\`;
DROP USER IF EXISTS '$2'@'%';
FLUSH PRIVILEGES;
SQL
}

# ----------------------------------------------------------------------------- platform stack
ensure_net() { docker network inspect "$NET" >/dev/null 2>&1 || { info "Creating shared network ${NET} ..."; docker network create "$NET" >/dev/null; }; }

write_platform_env() {
    mkdir -p "$PLATFORM_DIR"; umask 077
    [[ -f "$PLATFORM_ENV" ]] || : > "$PLATFORM_ENV"
    env_set "$PLATFORM_ENV" ROOT_PASS "$ROOT_PASS"
    [[ -n "$(env_get "$PLATFORM_ENV" BASE_DOMAIN)" ]] || env_set "$PLATFORM_ENV" BASE_DOMAIN ""
    chmod 600 "$PLATFORM_ENV"
}

write_platform_compose() {
    mkdir -p "$PLATFORM_DIR" "${PLATFORM_DATA}/mariadb" "${PLATFORM_DATA}/redis" "${CADDY_DIR}/data" "${CADDY_DIR}/config"
    cat > "$PLATFORM_COMPOSE" <<YAML
# Generated by the GuardinoBot installer. Shared platform (do not hand-edit).
name: ${PLATFORM_PROJECT}

services:
  mariadb:
    image: mariadb:11
    container_name: ${PLATFORM_PROJECT}-mariadb
    restart: always
    command: --max-connections=500
    environment:
      MYSQL_ROOT_PASSWORD: "${ROOT_PASS}"
    volumes:
      - "${PLATFORM_DATA}/mariadb:/var/lib/mysql"
    networks:
      ${NET}:
        aliases: [mariadb]
    healthcheck:
      test: ["CMD", "healthcheck.sh", "--connect", "--innodb_initialized"]
      interval: 10s
      timeout: 5s
      retries: 12

  redis:
    image: redis:alpine
    container_name: ${PLATFORM_PROJECT}-redis
    restart: always
    command: redis-server --appendonly yes --databases 64 --replica-read-only no
    volumes:
      - "${PLATFORM_DATA}/redis:/data"
    networks:
      ${NET}:
        aliases: [redis]

  caddy:
    image: caddy:2-alpine
    container_name: ${PLATFORM_PROJECT}-caddy
    restart: on-failure
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - "${CADDY_DIR}/Caddyfile:/etc/caddy/Caddyfile:ro"
      - "${CADDY_DIR}/data:/data"
      - "${CADDY_DIR}/config:/config"
    networks:
      - ${NET}

  phpmyadmin:
    image: phpmyadmin:latest
    container_name: ${PLATFORM_PROJECT}-phpmyadmin
    restart: on-failure
    environment:
      PMA_HOST: mariadb
      PMA_PORT: 3306
      UPLOAD_LIMIT: 256M
    ports:
      - "127.0.0.1:8081:80"
    networks:
      - ${NET}

networks:
  ${NET}:
    external: true
YAML
    chmod 600 "$PLATFORM_COMPOSE"
    info "Wrote ${PLATFORM_COMPOSE}"
}

assemble_caddyfile() {
    mkdir -p "$CADDY_DIR"
    {
        echo "# Generated by the GuardinoBot installer — one site block per bot."
        local name domain
        while IFS= read -r name; do
            [[ -n "$name" ]] || continue
            domain="$(reg_field "$name" 2)"
            [[ -n "$domain" ]] || continue
            cat <<CADDY

${domain} {
    encode zstd gzip
    @bot path ${WEBHOOK_PATHS}
    handle @bot {
        reverse_proxy guardino-${name}-bot:3333
    }
    handle {
        reverse_proxy guardino-${name}-webpanel:80
    }
}
CADDY
        done < <(reg_names)
    } > "${CADDY_DIR}/Caddyfile"
    info "Assembled Caddyfile ($(reg_names | grep -c . || true) site[s])."
}

caddy_reload() {
    docker ps --format '{{.Names}}' | grep -qx "${PLATFORM_PROJECT}-caddy" || return 0
    docker exec "${PLATFORM_PROJECT}-caddy" caddy reload --config /etc/caddy/Caddyfile >/dev/null 2>&1 \
        || dcp restart caddy >/dev/null 2>&1 || true
    info "Caddy reloaded."
}

clone_or_update_src() {
    mkdir -p "$ROOT_DIR"
    if [[ -d "${SRC_DIR}/.git" ]]; then
        info "Updating shared source from GitHub ..."
        git -C "$SRC_DIR" fetch --depth 1 origin "$REPO_BRANCH" >/dev/null 2>&1 || die "git fetch failed."
        git -C "$SRC_DIR" reset --hard "origin/${REPO_BRANCH}" >/dev/null 2>&1 || die "git reset failed."
    else
        info "Cloning shared source ..."
        rm -rf "$SRC_DIR"
        git clone --depth 1 -b "$REPO_BRANCH" "$REPO_URL" "$SRC_DIR" >/dev/null 2>&1 || die "git clone failed."
    fi
}

build_images() {
    info "Building shared images (this may take a few minutes) ..."
    docker build -t "$BOT_IMAGE" "$SRC_DIR" >/dev/null || die "bot image build failed."
    docker build -t "$WEB_IMAGE" "${SRC_DIR}/webpanel" >/dev/null || die "webpanel image build failed."
    info "Images built: ${BOT_IMAGE} · ${WEB_IMAGE}"
}

platform_up() {
    need_root; install_docker
    ensure_net
    load_platform_creds
    write_platform_env
    [[ -f "${CADDY_DIR}/Caddyfile" ]] || { mkdir -p "$CADDY_DIR"; echo "# (no bots yet)" > "${CADDY_DIR}/Caddyfile"; }
    write_platform_compose
    assemble_caddyfile
    info "Starting the shared platform ..."
    dcp up -d
    wait_mariadb
    install_cli
    info "Platform is up (MariaDB · Redis · Caddy · phpMyAdmin)."
}

ensure_platform() {
    [[ -f "$PLATFORM_COMPOSE" ]] || die "Platform not initialized. Run: ${CYAN}guardino platform-up${NC}"
    load_platform_creds
    docker ps --format '{{.Names}}' | grep -qx "${PLATFORM_PROJECT}-mariadb" || { info "Platform not running; starting ..."; dcp up -d; wait_mariadb; }
}

prompt_base_domain() {
    local cur; cur="$(env_get "$PLATFORM_ENV" BASE_DOMAIN)"
    echo
    echo "${CYAN}Base domain for bots${NC} (e.g. bots.example.com). Each bot becomes <name>.<base>."
    echo "  - Point a WILDCARD DNS record  ${CYAN}*.<base> -> $(public_ip)${NC}  first."
    echo "  - Ports 80 and 443 must be free & open (Caddy issues HTTPS automatically)."
    local ans; read -rp "Base domain [${cur:-none}]: " ans || true
    [[ -n "$ans" ]] && env_set "$PLATFORM_ENV" BASE_DOMAIN "$(echo "$ans" | tr -d ' ' | sed -E 's#^https?://##; s#/.*$##')"
    BASE_DOMAIN="$(env_get "$PLATFORM_ENV" BASE_DOMAIN)"
    [[ -n "$BASE_DOMAIN" ]] && info "Base domain: ${BASE_DOMAIN}" || warn "No base domain set yet."
}

# ----------------------------------------------------------------------------- instance files
write_instance_compose() { # name
    local n="$1" d; d="$(inst_dir "$n")"; mkdir -p "$d"
    cat > "$(inst_compose "$n")" <<YAML
# Generated by the GuardinoBot installer for instance '${n}' (do not hand-edit).
name: guardino-${n}

services:
  bot:
    image: ${BOT_IMAGE}
    container_name: guardino-${n}-bot
    restart: on-failure
    env_file: [.env]
    mem_limit: 512m
    networks: [default, ${NET}]

  api:
    image: ${BOT_IMAGE}
    container_name: guardino-${n}-api
    restart: on-failure
    command: uvicorn app.api.main:app --host 0.0.0.0 --port 8000
    env_file: [.env]
    mem_limit: 384m
    networks: [default, ${NET}]

  webpanel:
    image: ${WEB_IMAGE}
    container_name: guardino-${n}-webpanel
    restart: on-failure
    mem_limit: 96m
    depends_on: [api]
    networks: [default, ${NET}]

networks:
  default:
  ${NET}:
    external: true
YAML
}

write_instance_env() { # name token superusers domain db_user db_pass db_name redis_db [secret] [webjwt]
    local n="$1" token="$2" su="$3" domain="$4" du="$5" dp="$6" db="$7" rdb="$8"
    local secret="${9:-$(rand 32)}" webjwt="${10:-$(rand 32)}"
    local d; d="$(inst_dir "$n")"; mkdir -p "$d"; umask 077
    cat > "$(inst_env "$n")" <<ENV
# ---- GuardinoBot env for instance '${n}' (generated by installer) ----
LOG_LEVEL = "info"

BOT_TOKEN = "${token}"

SUPER_USERS = "
${su}"

# public base url for payment callbacks / panel webhooks
WEBHOOK_BASE_URL = "https://${domain}"
PUBLIC_BASE_URL = "https://${domain}"
DOMAIN = "${domain}"

# shared MariaDB — this bot's own database + least-privilege user
DATABASE_URL = "mysql://${du}:${dp}@mariadb:3306/${db}"

# shared Redis — this bot's own logical DB index (isolated keyspace)
REDIS_HOST = "redis"
REDIS_PORT = 6379
REDIS_DB = ${rdb}

# webapp (payment IPN / panel webhooks)
WEBAPP_HOST = "0.0.0.0"
WEBAPP_PORT = 3333

# encrypts secrets stored in DB (max 32 chars) — DO NOT change after install
SECRET_KEY_STRING = "${secret}"

# web admin/reseller panel
WEB_JWT_SECRET = "${webjwt}"
WEB_CORS_ORIGINS = "*"

DEFAULT_USERNAME_PREFIX = "Guardino"
ENV
    chmod 600 "$(inst_env "$n")"
}

prompt_superusers() {
    echo "${CYAN}Super-admin numeric ID(s). One per line, empty line to finish:${NC}" >&2
    local out="" line
    while true; do
        read -rp "  user id: " line || true
        [[ -z "$line" ]] && break
        out+="${line}"$'\n'
    done
    printf '%s' "$out"
}

# ----------------------------------------------------------------------------- actions
do_platform_up() {
    platform_up
    prompt_base_domain
    hr; info "Next: ${CYAN}guardino add <name>${NC} to create a bot."; hr
}

do_add() {
    need_root; ensure_platform
    local name="${1:-}"
    [[ -n "$name" ]] || read -rp "Instance name (a-z0-9-): " name
    validate_name "$name"
    reg_has "$name" && die "An instance named '$name' already exists."

    BASE_DOMAIN="$(env_get "$PLATFORM_ENV" BASE_DOMAIN)"
    [[ -n "$BASE_DOMAIN" ]] || { prompt_base_domain; BASE_DOMAIN="$(env_get "$PLATFORM_ENV" BASE_DOMAIN)"; }
    [[ -n "$BASE_DOMAIN" ]] || die "A base domain is required (run platform-up and set it)."
    local domain="${name}.${BASE_DOMAIN}"

    local token; read -rp "${CYAN}Telegram bot token for '${name}': ${NC}" token
    [[ -n "$token" ]] || die "BOT_TOKEN is required."
    local su; su="$(prompt_superusers)"; [[ -n "$su" ]] || warn "No super-admin entered; add one later in the .env."

    local sani db user pass rdb
    sani="$(sanitize "$name")"; db="guardino_${sani}"; user="gb_${sani:0:24}"; pass="$(rand 24)"; rdb="$(alloc_redis_db)"

    info "Creating database ${db} + Redis DB ${rdb} ..."
    create_db "$db" "$user" "$pass"
    write_instance_env "$name" "$token" "$su" "$domain" "$user" "$pass" "$db" "$rdb"
    write_instance_compose "$name"
    reg_add "$name" "$domain" "$db" "$user" "$rdb"
    assemble_caddyfile; caddy_reload

    info "Starting bot '${name}' ..."
    dci "$name" up -d
    hr
    info "Bot '${name}' is up."
    echo "  Panel / webhooks: ${CYAN}https://${domain}/${NC}"
    echo "  DB: ${db}  ·  Redis DB: ${rdb}  ·  (migrations apply on start)"
    echo "  ${YELLOW}Ensure *.${BASE_DOMAIN} resolves to this server.${NC}"
    hr
}

do_update() {
    need_root; ensure_platform
    local target="${1:-all}"
    clone_or_update_src
    build_images
    local n
    if [[ "$target" == "all" ]]; then
        while IFS= read -r n; do [[ -n "$n" ]] || continue; info "Updating '${n}' ..."; dci "$n" up -d; done < <(reg_names)
    else
        reg_has "$target" || die "No instance '$target'."
        info "Updating '${target}' ..."; dci "$target" up -d
    fi
    docker image prune -f >/dev/null 2>&1 || true
    info "Update complete (migrations applied on start)."
}

do_list() {
    ensure_platform
    hr; printf "%-16s %-30s %-18s %-8s\n" "NAME" "DOMAIN" "DB" "REDIS_DB"; hr
    local n
    while IFS= read -r n; do
        [[ -n "$n" ]] || continue
        printf "%-16s %-30s %-18s %-8s\n" "$n" "$(reg_field "$n" 2)" "$(reg_field "$n" 3)" "$(reg_field "$n" 5)"
    done < <(reg_names)
    hr
}

pick_instance() { # echoes a chosen instance name (arg or prompt)
    local name="${1:-}"
    [[ -n "$name" ]] || { echo "Instances: $(reg_names | tr '\n' ' ')" >&2; read -rp "Instance name: " name; }
    reg_has "$name" || die "No instance '$name'."
    echo "$name"
}

do_logs() {
    ensure_platform; local n; n="$(pick_instance "${1:-}")"
    local svc="${2:-bot}"
    dci "$n" logs -f --tail=200 "$svc"
}

do_restart() { ensure_platform; local n; n="$(pick_instance "${1:-}")"; dci "$n" restart; info "Restarted '$n'."; }
do_stop()    { ensure_platform; local n; n="$(pick_instance "${1:-}")"; dci "$n" down; info "Stopped '$n'."; }
do_start()   { ensure_platform; local n; n="$(pick_instance "${1:-}")"; dci "$n" up -d; info "Started '$n'."; }
do_status()  { ensure_platform; info "Platform:"; dcp ps; local n; while IFS= read -r n; do [[ -n "$n" ]] || continue; echo; info "Instance ${n}:"; dci "$n" ps; done < <(reg_names); }
do_edit_env(){ ensure_platform; local n; n="$(pick_instance "${1:-}")"; "${EDITOR:-nano}" "$(inst_env "$n")"; warn "Restart the bot to apply: guardino restart $n"; }

backup_one() { # name -> path
    local n="$1" db ts out tmp
    db="$(reg_field "$n" 3)"
    ts="$(date +%Y%m%d-%H%M%S)"; tmp="$(mktemp -d)"
    mkdir -p "${BACKUP_ROOT}/${n}"
    info "Backing up '${n}' (db ${db}) ..."
    dump_db "$db" > "${tmp}/database.sql" 2>/dev/null || warn "  DB dump failed (is the platform up?)."
    cp -f "$(inst_env "$n")"     "${tmp}/.env"               2>/dev/null || true
    cp -f "$(inst_compose "$n")" "${tmp}/docker-compose.yml" 2>/dev/null || true
    reg_row "$n" > "${tmp}/meta" 2>/dev/null || true
    out="${BACKUP_ROOT}/${n}/guardino-${n}-${ts}.tar.gz"
    tar -czf "$out" -C "$tmp" . 2>/dev/null
    rm -rf "$tmp"
    # retention: keep last 10 per instance
    ls -1t "${BACKUP_ROOT}/${n}"/*.tar.gz 2>/dev/null | tail -n +11 | xargs -r rm -f
    info "  -> ${CYAN}${out}${NC}"
}
dump_db() { docker exec -e MYSQL_PWD="$ROOT_PASS" "${PLATFORM_PROJECT}-mariadb" mariadb-dump -uroot --single-transaction --routines --triggers "$1"; }

do_backup() {
    ensure_platform; local target="${1:-}"
    if [[ "$target" == "all" ]]; then
        local n; while IFS= read -r n; do [[ -n "$n" ]] || continue; backup_one "$n"; done < <(reg_names)
        cp -f "$PLATFORM_ENV" "${BACKUP_ROOT}/platform-env-$(date +%Y%m%d-%H%M%S).bak" 2>/dev/null || true
        info "All instances backed up under ${BACKUP_ROOT}."
    else
        n="$(pick_instance "$target")"; backup_one "$n"
    fi
}

do_restore() { # name file
    need_root; ensure_platform
    local name="${1:-}" file="${2:-}"
    [[ -n "$name" ]] || read -rp "Instance name to restore as: " name
    validate_name "$name"
    [[ -n "$file" ]] || { ls -1t "${BACKUP_ROOT}/${name}"/*.tar.gz 2>/dev/null | head; read -rp "Backup file path: " file; }
    [[ -f "$file" ]] || die "Backup file not found: $file"

    local tmp; tmp="$(mktemp -d)"; tar -xzf "$file" -C "$tmp" || die "Cannot extract $file"
    [[ -f "${tmp}/.env" ]] || die "Backup missing .env"
    local url du dp db rdb
    url="$(env_get "${tmp}/.env" DATABASE_URL)"
    du="$(sed -E 's#^mysql://([^:]+):.*#\1#'      <<<"$url")"
    dp="$(sed -E 's#^mysql://[^:]+:([^@]+)@.*#\1#' <<<"$url")"
    db="$(sed -E 's#.*/([^/?]+)(\?.*)?$#\1#'       <<<"$url")"
    rdb="$(env_get "${tmp}/.env" REDIS_DB)"
    # never share a Redis logical DB with a different live instance
    if [[ -z "$rdb" ]] || awk -F'\t' -v n="$name" -v r="$rdb" '$1!=n && $5==r{f=1} END{exit !f}' "$REGISTRY"; then
        rdb="$(alloc_redis_db)"
    fi

    warn "Restoring '${name}' into DB '${db}' (Redis DB ${rdb})."
    read -rp "Continue? (yes/no): " a; [[ "$a" == "yes" ]] || { info "Cancelled."; rm -rf "$tmp"; return; }

    info "Creating DB + user ..."; create_db "$db" "$du" "$dp"
    if [[ -f "${tmp}/database.sql" ]]; then
        info "Importing database dump ..."
        docker exec -i -e MYSQL_PWD="$ROOT_PASS" "${PLATFORM_PROJECT}-mariadb" mariadb -uroot "$db" < "${tmp}/database.sql" || die "DB import failed."
    fi
    mkdir -p "$(inst_dir "$name")"
    cp -f "${tmp}/.env" "$(inst_env "$name")"
    env_set "$(inst_env "$name")" REDIS_DB "$rdb"
    write_instance_compose "$name"
    local domain; domain="$(env_get "$(inst_env "$name")" DOMAIN)"; [[ -n "$domain" ]] || domain="$name"
    reg_add "$name" "$domain" "$db" "$du" "$rdb"
    assemble_caddyfile; caddy_reload
    dci "$name" up -d
    rm -rf "$tmp"
    info "Restored '${name}'. Panel: ${CYAN}https://${domain}/${NC}"
}

do_remove() {
    need_root; ensure_platform
    local n; n="$(pick_instance "${1:-}")"
    warn "Removing instance '${n}' (containers)."
    read -rp "Continue? (yes/no): " a; [[ "$a" == "yes" ]] || { info "Cancelled."; return; }
    dci "$n" down || true
    local db user; db="$(reg_field "$n" 3)"; user="$(reg_field "$n" 4)"
    read -rp "${RED}Also DROP database '${db}' and delete its backups? Irreversible (yes/no): ${NC}" b
    if [[ "$b" == "yes" ]]; then
        drop_db "$db" "$user"; rm -rf "${BACKUP_ROOT}/${n}"; info "Database + backups deleted."
    else
        info "Database kept (${db})."
    fi
    rm -rf "$(inst_dir "$n")"
    reg_del "$n"
    assemble_caddyfile; caddy_reload
    info "Instance '${n}' removed."
}

do_migrate_legacy() {
    need_root
    [[ -f "${LEGACY_APP_DIR}/.env" ]] || die "No legacy install found at ${LEGACY_APP_DIR}."
    ensure_platform
    local name="${1:-main}"; validate_name "$name"
    reg_has "$name" && die "An instance named '$name' already exists."
    local lenv="${LEGACY_APP_DIR}/.env" lcompose="${LEGACY_APP_DIR}/docker-compose.yml"

    info "Backing up the legacy bot first ..."
    local lurl ldb ts dump; lurl="$(env_get "$lenv" DATABASE_URL)"
    ldb="$(sed -E 's#.*/([^/?]+)(\?.*)?$#\1#' <<<"$lurl")"
    ts="$(date +%Y%m%d-%H%M%S)"; dump="/tmp/legacy-${ldb}-${ts}.sql"
    docker compose -p guardinobot -f "$lcompose" --project-directory "$LEGACY_APP_DIR" exec -T mariadb \
        sh -c "exec mariadb-dump -uroot -p\"\$MYSQL_ROOT_PASSWORD\" --single-transaction --routines --triggers '${ldb}'" \
        > "$dump" 2>/dev/null || die "Legacy DB dump failed (is the old stack running?)."
    info "Legacy dump: ${dump}"

    local BASE_DOMAIN ldomain domain sani db user pass rdb
    BASE_DOMAIN="$(env_get "$PLATFORM_ENV" BASE_DOMAIN)"
    ldomain="$(env_get "$lenv" DOMAIN)"
    echo
    if [[ -n "$ldomain" ]]; then
        echo "Legacy domain is '${ldomain}'. Keep it for this bot (recommended — gateway IPN URLs stay valid)?"
        read -rp "Keep '${ldomain}'? (yes/no) [yes]: " k || true
        if [[ "$k" == "no" ]]; then domain="${name}.${BASE_DOMAIN}"; else domain="$ldomain"; fi
    else
        domain="${name}.${BASE_DOMAIN}"
    fi
    [[ -n "$domain" ]] || die "No domain resolved; set a base domain first."

    sani="$(sanitize "$name")"; db="guardino_${sani}"; user="gb_${sani:0:24}"; pass="$(rand 24)"; rdb="$(alloc_redis_db)"
    info "Creating ${db} + importing legacy data ..."
    create_db "$db" "$user" "$pass"
    docker exec -i -e MYSQL_PWD="$ROOT_PASS" "${PLATFORM_PROJECT}-mariadb" mariadb -uroot "$db" < "$dump" || die "Import failed."

    # carry the legacy .env wholesale (keeps SECRET_KEY_STRING + SUPER_USERS), then repoint
    mkdir -p "$(inst_dir "$name")"; cp -f "$lenv" "$(inst_env "$name")"
    env_set "$(inst_env "$name")" DATABASE_URL "mysql://${user}:${pass}@mariadb:3306/${db}"
    env_set "$(inst_env "$name")" REDIS_HOST "redis"
    env_set "$(inst_env "$name")" REDIS_DB "$rdb"
    env_set "$(inst_env "$name")" DOMAIN "$domain"
    env_set "$(inst_env "$name")" WEBHOOK_BASE_URL "https://${domain}"
    env_set "$(inst_env "$name")" PUBLIC_BASE_URL "https://${domain}"
    chmod 600 "$(inst_env "$name")"
    write_instance_compose "$name"
    reg_add "$name" "$domain" "$db" "$user" "$rdb"
    assemble_caddyfile; caddy_reload
    dci "$name" up -d
    hr
    info "Migrated legacy bot -> instance '${name}'. Panel: ${CYAN}https://${domain}/${NC}"
    warn "VERIFY it works (panel login decrypts secrets; bot polls; a test IPN arrives)."
    warn "Only then stop the old stack:  docker compose -p guardinobot -f ${lcompose} down"
    warn "Keep ${LEGACY_DATA_DIR} until you've confirmed everything."
    hr
}

do_uninstall() {
    need_root
    warn "This removes ALL bots and the shared platform."
    read -rp "Continue? (yes/no): " a; [[ "$a" == "yes" ]] || { info "Cancelled."; return; }
    local n
    while IFS= read -r n; do [[ -n "$n" ]] || continue; dci "$n" down || true; done < <(reg_names)
    [[ -f "$PLATFORM_COMPOSE" ]] && dcp down || true
    read -rp "${RED}Also delete all data (${DATA_DIR}) + configs (${ROOT_DIR})? Irreversible (yes/no): ${NC}" b
    if [[ "$b" == "yes" ]]; then
        docker network rm "$NET" >/dev/null 2>&1 || true
        rm -rf "$DATA_DIR" "$ROOT_DIR" "$BIN_PATH"
        info "Everything removed."
    else
        info "Containers stopped; data kept in ${DATA_DIR}."
    fi
}

install_cli() {
    if [[ -f "${SRC_DIR}/installer/guardino.sh" ]]; then
        install -m 0755 -D "${SRC_DIR}/installer/guardino.sh" "$BIN_PATH" 2>/dev/null || true
    else
        curl -fsSL --ipv4 "$RAW_SCRIPT" -o "$BIN_PATH" 2>/dev/null && chmod 0755 "$BIN_PATH" || true
    fi
    [[ -f "$BIN_PATH" ]] && info "Management command installed: ${CYAN}guardino${NC}"
}

# ----------------------------------------------------------------------------- first-time install
do_install() {
    need_root; install_prereqs; install_docker
    clone_or_update_src
    build_images
    do_platform_up
}

# ----------------------------------------------------------------------------- menu
menu() {
    while true; do
        echo; hr
        echo "  ${CYAN}${APP_NAME}${NC} — multi-bot manager"
        hr
        echo "  1) Install / init platform (prereqs + build + platform-up)"
        echo "  2) Add a bot"
        echo "  3) Update (all or one) — rebuild shared image + restart"
        echo "  4) List bots"
        echo "  5) Backup (all or one)"
        echo "  6) Restore a bot from backup"
        echo "  7) Logs"
        echo "  8) Restart / Stop / Start a bot"
        echo "  9) Status"
        echo " 10) Edit a bot's .env"
        echo " 11) Set / change base domain"
        echo " 12) Migrate the legacy single install -> a bot"
        echo " 13) Remove a bot"
        echo " 14) Uninstall everything"
        echo "  0) Exit"
        hr
        read -rp "Choice: " c || exit 0
        case "$c" in
            1) do_install ;;
            2) do_add ;;
            3) read -rp "Instance [all]: " t || true; do_update "${t:-all}" ;;
            4) do_list ;;
            5) read -rp "Instance [all]: " t || true; do_backup "${t:-all}" ;;
            6) do_restore ;;
            7) do_logs ;;
            8) read -rp "Action (restart/stop/start): " act || true; read -rp "Instance: " t || true
               case "$act" in restart) do_restart "$t";; stop) do_stop "$t";; start) do_start "$t";; *) warn "Unknown.";; esac ;;
            9) do_status ;;
            10) do_edit_env ;;
            11) ensure_platform; prompt_base_domain ;;
            12) read -rp "New instance name [main]: " t || true; do_migrate_legacy "${t:-main}" ;;
            13) do_remove ;;
            14) do_uninstall ;;
            0) exit 0 ;;
            *) warn "Invalid option." ;;
        esac
    done
}

# ----------------------------------------------------------------------------- dispatch
case "${1:-}" in
    install)        do_install ;;
    platform-up)    do_platform_up ;;
    add)            shift; do_add "${1:-}" ;;
    update)         shift; do_update "${1:-all}" ;;
    list)           do_list ;;
    backup)         shift; do_backup "${1:-all}" ;;
    restore)        shift; do_restore "${1:-}" "${2:-}" ;;
    logs)           shift; do_logs "${1:-}" "${2:-bot}" ;;
    restart)        shift; do_restart "${1:-}" ;;
    stop)           shift; do_stop "${1:-}" ;;
    start)          shift; do_start "${1:-}" ;;
    status)         do_status ;;
    edit-env)       shift; do_edit_env "${1:-}" ;;
    domain)         ensure_platform; prompt_base_domain ;;
    migrate-legacy) shift; do_migrate_legacy "${1:-main}" ;;
    remove)         shift; do_remove "${1:-}" ;;
    uninstall)      do_uninstall ;;
    "")             menu ;;
    *)              die "Unknown subcommand: ${1}. Try: install|platform-up|add|update|list|backup|restore|logs|restart|stop|start|status|edit-env|domain|migrate-legacy|remove|uninstall" ;;
esac
