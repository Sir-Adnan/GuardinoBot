#!/usr/bin/env bash
#
# Guardino-Bot multi-instance installer / manager
# Repo:   https://github.com/Sir-Adnan/GuardinoBot
# Author: UnknownZero
#
# Runs MANY independent bots on one server. One shared "platform" (MariaDB + Redis
# + Caddy + phpMyAdmin) + one isolated app stack (bot · api · webpanel) per bot,
# each with its own database, its own Redis logical DB, its own .env/token, and its
# own HTTPS subdomain. No bot can see another's data; backup/restore is per-bot.
#
# Usage:
#   bash <(curl -Ls --ipv4 https://raw.githubusercontent.com/Sir-Adnan/GuardinoBot/main/installer/guardino-bot.sh)
#   guardino-bot <add|update|backup|restore|list|remove|logs|...> [name] [args]
#
set -euo pipefail

# ----------------------------------------------------------------------------- constants
APP_NAME="Guardino-Bot"
REPO_URL="https://github.com/Sir-Adnan/GuardinoBot.git"
REPO_BRANCH="main"
RAW_SCRIPT="https://raw.githubusercontent.com/Sir-Adnan/GuardinoBot/main/installer/guardino-bot.sh"

ROOT_DIR="/opt/guardino-bot"
SRC_DIR="${ROOT_DIR}/src"                 # ONE shared git clone (build context)
PLATFORM_DIR="${ROOT_DIR}/platform"
INSTANCES_DIR="${ROOT_DIR}/instances"
REGISTRY="${ROOT_DIR}/registry.tsv"
PLATFORM_COMPOSE="${PLATFORM_DIR}/docker-compose.platform.yml"
PLATFORM_ENV="${PLATFORM_DIR}/.env.platform"
CADDY_DIR="${PLATFORM_DIR}/caddy"

DATA_DIR="/var/lib/guardino-bot"
PLATFORM_DATA="${DATA_DIR}/platform"
BACKUP_ROOT="${DATA_DIR}/backups"
BACKUP_CONF="${ROOT_DIR}/backup.conf"      # Telegram-backup config (token/chat/scope/schedule)
BACKUP_CRON="/etc/cron.d/guardino-bot-backup"  # cron entry for the scheduled backup

NET="guardino-bot-net"
PLATFORM_PROJECT="guardino-bot-platform"
BOT_IMAGE="guardino-bot:local"
WEB_IMAGE="guardino-bot-webpanel:local"
BIN_PATH="/usr/local/bin/guardino-bot"

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
public_ip() { curl -fsSL --ipv4 https://api.ipify.org 2>/dev/null | head -1 || hostname -I 2>/dev/null | awk '{print $1}'; }

# warn (non-fatal) if a domain doesn't resolve to this server — the #1 reason a
# panel "doesn't come up" is a missing wildcard DNS record (no record → no HTTPS).
dns_check() { # <domain>
    local domain="$1" ip rip base
    ip="$(public_ip)"; base="$(env_get "$PLATFORM_ENV" BASE_DOMAIN)"
    rip="$(getent hosts "$domain" 2>/dev/null | awk '{print $1}' | head -1)"
    [[ -n "$rip" ]] || rip="$(command -v dig >/dev/null 2>&1 && dig +short "$domain" A 2>/dev/null | tail -1)"
    if [[ -z "$rip" ]]; then
        warn "DNS: '${domain}' does not resolve yet."
        warn "     Add a WILDCARD record so every bot works:  ${CYAN}*.${base} A ${ip}${NC}"
        warn "     HTTPS will be issued automatically once DNS points here (no re-run needed)."
    elif [[ "$rip" != "$ip" ]]; then
        warn "DNS: '${domain}' resolves to ${rip}, not this server (${ip}). HTTPS will fail until fixed."
    else
        info "DNS OK: ${domain} -> ${ip}"
    fi
}

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
# DB name/user fragment (a-z0-9_); instance names are normalized by clean_name below
sanitize() { echo "$1" | tr '[:upper:]' '[:lower:]' | tr -c 'a-z0-9' '_' | sed -E 's/_+/_/g; s/^_+//; s/_+$//'; }
# normalize any input to a DNS/compose-safe instance name (lowercase a-z0-9-, max 31)
clean_name() {
    local out; out="$(echo "$1" | tr '[:upper:]' '[:lower:]' | tr -c 'a-z0-9-' '-' | sed -E 's/-+/-/g; s/^-+//; s/-+$//')"
    out="${out:0:31}"; sed -E 's/-+$//' <<<"$out"
}
# read+normalize an instance name into the caller's $name; warn if it changed
resolve_name() { # <current name or empty> ; sets global REPLY
    local raw="$1"
    [[ -n "$raw" ]] || read -rp "Instance name (a-z0-9-): " raw
    REPLY="$(clean_name "$raw")"
    [[ -n "$REPLY" ]] || die "Invalid instance name '${raw}' (use letters a-z, digits, '-')."
    [[ "$REPLY" == "$raw" ]] || warn "Normalized name to '${REPLY}'."
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
dci() { local n="$1"; shift; docker compose -p "guardino-bot-${n}" -f "$(inst_compose "$n")" --project-directory "$(inst_dir "$n")" "$@"; }

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
# Let root connect from the phpMyAdmin container (the image only guarantees
# root@localhost). With this, logging into phpMyAdmin as root shows ALL the
# instance databases. Runs via root@localhost (always present), so it also
# fixes an already-initialized platform. Idempotent.
ensure_root_remote() {
    mysql_root <<SQL >/dev/null 2>&1 || warn "Could not grant remote root (phpMyAdmin root login may not work)."
CREATE USER IF NOT EXISTS 'root'@'%' IDENTIFIED BY '${ROOT_PASS}';
ALTER USER 'root'@'%' IDENTIFIED BY '${ROOT_PASS}';
GRANT ALL PRIVILEGES ON *.* TO 'root'@'%' WITH GRANT OPTION;
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
# Generated by the Guardino-Bot installer. Shared platform (do not hand-edit).
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
        echo "# Generated by the Guardino-Bot installer — one site block per bot."
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
        reverse_proxy guardino-bot-${name}-bot:3333
    }
    handle {
        reverse_proxy guardino-bot-${name}-webpanel:80
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

# make sure the shared images exist (build them if a bot is added before a full install)
ensure_images() {
    docker image inspect "$BOT_IMAGE" >/dev/null 2>&1 && docker image inspect "$WEB_IMAGE" >/dev/null 2>&1 && return 0
    warn "Shared images not found — building them now ..."
    [[ -d "${SRC_DIR}/.git" ]] || clone_or_update_src
    build_images
}

# warn if the platform Caddy didn't actually start (almost always a port 80/443 clash)
verify_platform() {
    local st; st="$(docker inspect -f '{{.State.Status}}' "${PLATFORM_PROJECT}-caddy" 2>/dev/null || true)"
    [[ "$st" == "running" ]] && return 0
    warn "Caddy is not running (state: ${st:-missing}) — ports 80/443 are held by another service."
    warn "Find what owns the ports:  ss -ltnp '( sport = :80 or sport = :443 )'"
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
    ensure_root_remote     # so phpMyAdmin root login can manage ALL instance DBs
    install_cli
    verify_platform
    info "Platform is up (MariaDB · Redis · Caddy · phpMyAdmin)."
    info "phpMyAdmin: SSH-tunnel 8081, then http://localhost:8081 — login user ${CYAN}root${NC}, password = ROOT_PASS in ${PLATFORM_ENV}."
}

ensure_platform() {
    [[ -f "$PLATFORM_COMPOSE" ]] || die "Platform not initialized yet. Pick ${CYAN}'1) Install / init platform'${NC} from the menu first (or run: ${CYAN}guardino-bot install${NC})."
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
# Generated by the Guardino-Bot installer for instance '${n}' (do not hand-edit).
name: guardino-bot-${n}

services:
  bot:
    image: ${BOT_IMAGE}
    container_name: guardino-bot-${n}-bot
    restart: on-failure
    env_file: [.env]
    mem_limit: 512m
    networks: [default, ${NET}]

  api:
    image: ${BOT_IMAGE}
    container_name: guardino-bot-${n}-api
    restart: on-failure
    command: uvicorn app.api.main:app --host 0.0.0.0 --port 8000
    env_file: [.env]
    mem_limit: 384m
    networks: [default, ${NET}]

  webpanel:
    image: ${WEB_IMAGE}
    container_name: guardino-bot-${n}-webpanel
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
# ---- Guardino-Bot env for instance '${n}' (generated by installer) ----
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

DEFAULT_USERNAME_PREFIX = "Guardino_Bot"
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
    hr; info "Next: ${CYAN}guardino-bot add <name>${NC} to create a bot."; hr
}

do_add() {
    need_root; ensure_platform; ensure_images
    resolve_name "${1:-}"; local name="$REPLY"
    reg_has "$name" && die "An instance named '$name' already exists."

    BASE_DOMAIN="$(env_get "$PLATFORM_ENV" BASE_DOMAIN)"
    [[ -n "$BASE_DOMAIN" ]] || { prompt_base_domain; BASE_DOMAIN="$(env_get "$PLATFORM_ENV" BASE_DOMAIN)"; }
    [[ -n "$BASE_DOMAIN" ]] || die "A base domain is required (run platform-up and set it)."
    local domain="${name}.${BASE_DOMAIN}"
    dns_check "$domain"

    local token; read -rp "${CYAN}Telegram bot token for '${name}': ${NC}" token
    [[ -n "$token" ]] || die "BOT_TOKEN is required."
    local su; su="$(prompt_superusers)"; [[ -n "$su" ]] || warn "No super-admin entered; add one later in the .env."

    local sani db user pass rdb
    sani="$(sanitize "$name")"; db="guardino_bot_${sani}"; user="gbot_${sani:0:23}"; pass="$(rand 24)"; rdb="$(alloc_redis_db)"

    info "Creating database ${db} + Redis DB ${rdb} ..."
    create_db "$db" "$user" "$pass"
    write_instance_env "$name" "$token" "$su" "$domain" "$user" "$pass" "$db" "$rdb"
    write_instance_compose "$name"
    reg_add "$name" "$domain" "$db" "$user" "$rdb"
    assemble_caddyfile; caddy_reload

    info "Starting bot '${name}' ..."
    dci "$name" up -d
    verify_platform   # warn if Caddy isn't serving (e.g. legacy stack holds 80/443)
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
    install_cli repo
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
do_edit_env(){ ensure_platform; local n; n="$(pick_instance "${1:-}")"; "${EDITOR:-nano}" "$(inst_env "$n")"; warn "Restart the bot to apply: guardino-bot restart $n"; }

backup_one() { # name -> path
    local n="$1" db ts out tmp
    db="$(reg_field "$n" 3)"
    ts="$(date +%Y%m%d-%H%M%S)"; tmp="$(mktemp -d)"
    mkdir -p "${BACKUP_ROOT}/${n}"
    info "Backing up '${n}' (db ${db}) ..."
    if ! dump_db "$db" > "${tmp}/database.sql" 2>/dev/null; then
        warn "  DB dump failed for '${n}' (backup was not created)."
        rm -rf "$tmp"
        return 1
    fi
    cp -f "$(inst_env "$n")"     "${tmp}/.env"               2>/dev/null || true
    cp -f "$(inst_compose "$n")" "${tmp}/docker-compose.yml" 2>/dev/null || true
    reg_row "$n" > "${tmp}/meta" 2>/dev/null || true
    out="${BACKUP_ROOT}/${n}/guardino-bot-${n}-${ts}.tar.gz"
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

# ----------------------------------------------------------------------------- backup -> Telegram
TG_DOC_LIMIT=$((49 * 1024 * 1024))  # Bot API sendDocument cap is 50MB — stay under

_tg_send_doc() { # token chat file caption
    local body errf code desc
    body="$(mktemp)"; errf="$(mktemp)"
    code="$(curl -sS --max-time 600 -w '%{http_code}' -o "$body" \
        -F "chat_id=${2}" -F "caption=${4}" -F "document=@${3}" \
        "https://api.telegram.org/bot${1}/sendDocument" 2>"$errf")" || {
        desc="$(head -c 300 "$errf" 2>/dev/null || true)"
        warn "  Telegram send failed: ${desc:-curl error}"
        rm -f "$body" "$errf"
        return 1
    }
    if [[ "$code" =~ ^2 ]] && grep -q '"ok"[[:space:]]*:[[:space:]]*true' "$body" 2>/dev/null; then
        rm -f "$body" "$errf"
        return 0
    fi
    desc="$(sed -nE 's/.*"description"[[:space:]]*:[[:space:]]*"([^"]*)".*/\1/p' "$body" | head -c 300)"
    warn "  Telegram send failed (${code:-no-http-code}): ${desc:-unknown Bot API error}"
    rm -f "$body" "$errf"
    return 1
}

# send a file, splitting it into <50MB parts when it's too big for Telegram
tg_send_file() { # token chat file caption
    local token="$1" chat="$2" file="$3" caption="$4" sz
    sz=$(stat -c%s "$file" 2>/dev/null || echo 0)
    if (( sz <= TG_DOC_LIMIT )); then
        _tg_send_doc "$token" "$chat" "$file" "$caption"
        return $?
    fi
    warn "  $(basename "$file") is $((sz / 1024 / 1024))MB → splitting into parts ..."
    local prefix="${file}.part_"
    split -b 49m -- "$file" "$prefix" || { warn "  Could not split $(basename "$file")."; return 1; }
    local parts=( "${prefix}"* ) i=1 n=${#parts[@]}
    local failed=0
    for p in "${parts[@]}"; do
        _tg_send_doc "$token" "$chat" "$p" "${caption} — part ${i}/${n} (cat *.part_* → reassemble)" \
            || failed=1
        i=$((i + 1))
    done
    rm -f "${prefix}"*
    return "$failed"
}

# echo a path to send: an AES-256 copy when a passphrase is set, else the original
_maybe_encrypt() { # file
    local pass; pass=$(env_get "$BACKUP_CONF" BACKUP_ENC_PASS)
    if [[ -n "$pass" ]] && command -v openssl >/dev/null 2>&1; then
        if openssl enc -aes-256-cbc -pbkdf2 -salt -in "$1" -out "$1.enc" -pass "pass:${pass}" 2>/dev/null; then
            echo "$1.enc"; return
        fi
    fi
    echo "$1"
}

# best-effort chat id from getUpdates (user must message the bot first)
_detect_chat_id() { # token
    [[ -n "$1" ]] || return 0
    local r; r=$(curl -fsS --max-time 15 "https://api.telegram.org/bot${1}/getUpdates" 2>/dev/null) || return 0
    if command -v python3 >/dev/null 2>&1; then
        printf '%s' "$r" | python3 -c 'import json,sys
try: d=json.load(sys.stdin)
except Exception: sys.exit()
ids=[(u.get("message") or u.get("channel_post") or {}).get("chat",{}).get("id") for u in d.get("result",[])]
ids=[i for i in ids if i is not None]
print(ids[-1] if ids else "")' 2>/dev/null
    else
        printf '%s' "$r" | grep -oE '"chat":\{"id":-?[0-9]+' | grep -oE '\-?[0-9]+' | tail -1
    fi
}

_send_one_to_tg() { # token chat name
    if ! backup_one "$3" >/dev/null; then
        warn "  backup failed for '$3'; Telegram send skipped."
        return 1
    fi
    local f; f=$(ls -1t "${BACKUP_ROOT}/$3"/*.tar.gz 2>/dev/null | head -1 || true)
    [[ -f "$f" ]] || { warn "  no backup produced for '$3'"; return 1; }
    local snd; snd=$(_maybe_encrypt "$f")
    tg_send_file "$1" "$2" "$snd" "🗄 ${3} · $(hostname) · $(date '+%Y-%m-%d %H:%M')" || {
        [[ "$snd" != "$f" ]] && rm -f "$snd"
        return 1
    }
    [[ "$snd" != "$f" ]] && rm -f "$snd"
}

# create backups + send to the configured Telegram bot. Used by cron + "send now".
backup_and_send() {
    [[ -f "$BACKUP_CONF" ]] || { err "Telegram backup not configured (run: guardino-bot backup-telegram)."; return 1; }
    local token chat scope
    token=$(env_get "$BACKUP_CONF" BACKUP_BOT_TOKEN)
    chat=$(env_get "$BACKUP_CONF" BACKUP_CHAT_ID)
    scope=$(env_get "$BACKUP_CONF" BACKUP_SCOPE); scope="${scope:-each}"
    [[ -n "$token" && -n "$chat" ]] || { err "Backup bot token / chat id missing."; return 1; }
    ensure_platform
    info "Backup → Telegram (scope: ${scope}) ..."
    local failed=0
    if [[ "$scope" == "combined" ]]; then
        local n latest rels=() ts combo snd
        ts=$(date +%Y%m%d-%H%M%S)
        while IFS= read -r n; do
            [[ -n "$n" ]] || continue
            if backup_one "$n" >/dev/null; then
                latest=$(ls -1t "${BACKUP_ROOT}/$n"/*.tar.gz 2>/dev/null | head -1 || true)
                [[ -f "$latest" ]] && rels+=( "${n}/$(basename "$latest")" )
            else
                failed=1
            fi
        done < <(reg_names)
        [[ ${#rels[@]} -gt 0 ]] || { warn "No bots to back up."; return; }
        combo="/tmp/guardino-bot-all-${ts}.tar.gz"
        tar -czf "$combo" -C "$BACKUP_ROOT" "${rels[@]}" 2>/dev/null
        snd=$(_maybe_encrypt "$combo")
        tg_send_file "$token" "$chat" "$snd" "🗄 Guardino-Bot — ALL bots · $(hostname) · ${ts}" || failed=1
        [[ "$snd" != "$combo" ]] && rm -f "$snd"
        rm -f "$combo"
    elif [[ "$scope" == "each" || "$scope" == "all" ]]; then
        local n; while IFS= read -r n; do [[ -n "$n" ]] || continue; _send_one_to_tg "$token" "$chat" "$n" || failed=1; done < <(reg_names)
    else
        reg_has "$scope" || { err "Instance '$scope' not found."; return 1; }
        _send_one_to_tg "$token" "$chat" "$scope" || failed=1
    fi
    (( failed == 0 )) || { err "Backup → Telegram finished with errors."; return 1; }
    info "Backup → Telegram done."
}

valid_cron_expr() { [[ "$(awk '{print NF}' <<<"$1")" -eq 5 && "$1" != *$'\n'* ]]; }

ensure_cron_service() {
    if command -v systemctl >/dev/null 2>&1; then
        systemctl enable --now cron >/dev/null 2>&1 || systemctl enable --now crond >/dev/null 2>&1 || true
    elif command -v service >/dev/null 2>&1; then
        service cron start >/dev/null 2>&1 || service crond start >/dev/null 2>&1 || true
    fi
}

install_backup_cron() { # cron_expr
    valid_cron_expr "$1" || die "Invalid cron expression. Use exactly 5 fields: min hour dom mon dow."
    install_cli auto
    cat > "$BACKUP_CRON" <<CRON
# Guardino-Bot scheduled backup -> Telegram (managed by the installer)
SHELL=/bin/bash
PATH=/usr/local/bin:/usr/bin:/bin
${1} root ${BIN_PATH} backup-send >> /var/log/guardino-bot-backup.log 2>&1
CRON
    chmod 0644 "$BACKUP_CRON"
    ensure_cron_service
    command -v crond >/dev/null 2>&1 || command -v cron >/dev/null 2>&1 || \
        warn "cron not found — install it (apt/dnf install cron|cronie) so the schedule runs."
    info "Scheduled '${1}' (cron). Log: /var/log/guardino-bot-backup.log"
}
disable_backup_cron() { rm -f "$BACKUP_CRON"; info "Scheduled Telegram backup disabled."; }

do_backup_telegram() {
    need_root; ensure_platform
    mkdir -p "$ROOT_DIR"; umask 077
    [[ -f "$BACKUP_CONF" ]] || : > "$BACKUP_CONF"
    chmod 600 "$BACKUP_CONF"
    install_cli auto
    warn "Backups contain each bot's .env (DB creds, SECRET_KEY_STRING, BOT_TOKEN)."
    warn "Use a PRIVATE backup bot/chat; consider the encryption passphrase (option 4)."
    while true; do
        local tk ch sc sched enc
        tk=$(env_get "$BACKUP_CONF" BACKUP_BOT_TOKEN); ch=$(env_get "$BACKUP_CONF" BACKUP_CHAT_ID)
        sc=$(env_get "$BACKUP_CONF" BACKUP_SCOPE); sched=$(env_get "$BACKUP_CONF" BACKUP_SCHEDULE)
        enc=$(env_get "$BACKUP_CONF" BACKUP_ENC_PASS)
        echo; hr
        echo "  ${CYAN}Scheduled backup → Telegram${NC}"
        hr
        echo "  bot token: $( [[ -n $tk ]] && echo '✔ set' || echo '✗ unset' )    chat: ${ch:-—}"
        echo "  scope: ${sc:-each}    schedule: ${sched:-—}    encrypt: $( [[ -n $enc ]] && echo on || echo off )"
        echo "  cron: $( [[ -f $BACKUP_CRON ]] && echo active || echo off )"
        hr
        echo "  1) Set backup bot token + chat id"
        echo "  2) What to back up (one bot / all-each / all-combined)"
        echo "  3) Schedule (hourly / 6h / 12h / daily / custom)"
        echo "  4) Encryption passphrase (optional)"
        echo "  5) Send a backup now (test)"
        echo "  6) Disable the schedule"
        echo "  0) Back"
        read -rp "Choice: " bc || return
        case "$bc" in
            1) read -rp "Backup bot token: " v; [[ -n "$v" ]] && env_set "$BACKUP_CONF" BACKUP_BOT_TOKEN "$v"
               echo "Send any message to the backup bot, then press Enter to auto-detect (or type the chat id):"
               read -rp "chat id: " v
               [[ -z "$v" ]] && { v=$(_detect_chat_id "$(env_get "$BACKUP_CONF" BACKUP_BOT_TOKEN)"); [[ -n "$v" ]] && info "Detected: $v"; }
               [[ -n "$v" ]] && env_set "$BACKUP_CONF" BACKUP_CHAT_ID "$v" || warn "No chat id set." ;;
            2) echo "  1) one specific bot   2) all bots, each as its own file   3) all bots, one archive"
               read -rp "Choice: " v
               case "$v" in
                   1) echo "  Bots: $(reg_names | tr '\n' ' ')"; read -rp "Instance: " nm
                      reg_has "$nm" && env_set "$BACKUP_CONF" BACKUP_SCOPE "$nm" || warn "No such bot." ;;
                   2) env_set "$BACKUP_CONF" BACKUP_SCOPE "each" ;;
                   3) env_set "$BACKUP_CONF" BACKUP_SCOPE "combined" ;;
                   *) warn "Invalid." ;;
               esac ;;
            3) echo "  1) hourly   2) every 6h   3) every 12h   4) daily 03:00   5) custom cron"
               read -rp "Choice: " v; local cron=""
               case "$v" in
                   1) cron="0 * * * *";; 2) cron="0 */6 * * *";; 3) cron="0 */12 * * *";;
                   4) cron="0 3 * * *";; 5) read -rp "Cron (min hour dom mon dow): " cron;;
                   *) warn "Invalid.";;
               esac
               [[ -n "$cron" ]] && { env_set "$BACKUP_CONF" BACKUP_SCHEDULE "$cron"; install_backup_cron "$cron"; } ;;
            4) read -rsp "Encryption passphrase (empty = disable): " v; echo
               env_set "$BACKUP_CONF" BACKUP_ENC_PASS "$v"
               [[ -n "$v" ]] && info "AES-256 on. Restore: openssl enc -d -aes-256-cbc -pbkdf2 -in <f>.enc -out <f> -pass pass:<phrase>" || info "Encryption off." ;;
            5) backup_and_send ;;
            6) disable_backup_cron ;;
            0) return ;;
            *) warn "Invalid option." ;;
        esac
    done
}

do_restore() { # name file
    need_root; ensure_platform; ensure_images
    local file="${2:-}"
    resolve_name "${1:-}"; local name="$REPLY"
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

install_cli() { # [auto|repo|current]
    local mode="${1:-auto}" src="" self="${BASH_SOURCE[0]:-$0}"
    case "$mode" in
        repo)
            [[ -f "${SRC_DIR}/installer/guardino-bot.sh" ]] && src="${SRC_DIR}/installer/guardino-bot.sh"
            ;;
        current)
            [[ -r "$self" ]] && src="$self"
            ;;
        auto|"")
            if [[ -r "$self" && "$self" != "$BIN_PATH" ]]; then
                src="$self"
            elif [[ -f "${SRC_DIR}/installer/guardino-bot.sh" ]]; then
                src="${SRC_DIR}/installer/guardino-bot.sh"
            fi
            ;;
        *)
            die "Unknown install_cli mode: $mode"
            ;;
    esac
    if [[ -n "$src" ]] && install -m 0755 -D "$src" "$BIN_PATH" 2>/dev/null; then
        :
    elif [[ "$src" != "${SRC_DIR}/installer/guardino-bot.sh" && -f "${SRC_DIR}/installer/guardino-bot.sh" ]] \
        && install -m 0755 -D "${SRC_DIR}/installer/guardino-bot.sh" "$BIN_PATH" 2>/dev/null; then
        :
    else
        curl -fsSL --ipv4 "$RAW_SCRIPT" -o "$BIN_PATH" || die "Could not download management command."
        chmod 0755 "$BIN_PATH" || die "Could not chmod ${BIN_PATH}."
    fi
    info "Management command installed: ${CYAN}guardino-bot${NC}"
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
        echo " 12) Remove a bot"
        echo " 13) Uninstall everything"
        echo " 14) Scheduled backup → Telegram"
        echo "  0) Exit"
        hr
        read -rp "Choice: " c || exit 0
        # each action runs in a subshell so a failure (die) returns to the menu
        # instead of dropping the user back to the shell.
        case "$c" in
            1)  ( do_install ) || true ;;
            2)  ( do_add ) || true ;;
            3)  ( read -rp "Instance [all]: " t || true; do_update "${t:-all}" ) || true ;;
            4)  ( do_list ) || true ;;
            5)  ( read -rp "Instance [all]: " t || true; do_backup "${t:-all}" ) || true ;;
            6)  ( do_restore ) || true ;;
            7)  ( do_logs ) || true ;;
            8)  ( read -rp "Action (restart/stop/start): " act || true; read -rp "Instance: " t || true
                  case "$act" in restart) do_restart "$t";; stop) do_stop "$t";; start) do_start "$t";; *) warn "Unknown action.";; esac ) || true ;;
            9)  ( do_status ) || true ;;
            10) ( do_edit_env ) || true ;;
            11) ( ensure_platform; prompt_base_domain ) || true ;;
            12) ( do_remove ) || true ;;
            13) ( do_uninstall ) || true ;;
            14) ( do_backup_telegram ) || true ;;
            0)  exit 0 ;;
            *)  warn "Invalid option." ;;
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
    backup-send)    backup_and_send ;;
    backup-telegram) do_backup_telegram ;;
    restore)        shift; do_restore "${1:-}" "${2:-}" ;;
    logs)           shift; do_logs "${1:-}" "${2:-bot}" ;;
    restart)        shift; do_restart "${1:-}" ;;
    stop)           shift; do_stop "${1:-}" ;;
    start)          shift; do_start "${1:-}" ;;
    status)         do_status ;;
    edit-env)       shift; do_edit_env "${1:-}" ;;
    domain)         ensure_platform; prompt_base_domain ;;
    remove)         shift; do_remove "${1:-}" ;;
    uninstall)      do_uninstall ;;
    "")             menu ;;
    *)              die "Unknown subcommand: ${1}. Try: install|platform-up|add|update|list|backup|backup-send|backup-telegram|restore|logs|restart|stop|start|status|edit-env|domain|remove|uninstall" ;;
esac
