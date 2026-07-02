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
BACKUP_LOG="/var/log/guardino-bot-backup.log"

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
hr()   { echo "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"; }
title(){ echo; hr; echo "  ${CYAN}$*${NC}"; hr; }
menu_item() { printf "  ${CYAN}%2s)${NC} %s\n" "$1" "$2"; }

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

# getMe preflight — a bad token otherwise only surfaces as a silent crash-loop
# after "Bot is up". Unreachable Telegram is non-fatal (verify can't run).
check_bot_token() { # token
    local body code
    body="$(mktemp)"
    code="$(curl -sS --ipv4 --max-time 15 -o "$body" -w '%{http_code}' \
        "https://api.telegram.org/bot${1}/getMe" 2>/dev/null)" || {
        rm -f "$body"
        warn "Could not reach Telegram to verify the token — continuing."
        return 0
    }
    if [[ "$code" == 200 ]] && grep -q '"ok"[[:space:]]*:[[:space:]]*true' "$body" 2>/dev/null; then
        local un; un="$(sed -nE 's/.*"username"[[:space:]]*:[[:space:]]*"([^"]+)".*/\1/p' "$body")"
        info "Token OK${un:+ (@${un})}."
        rm -f "$body"
        return 0
    fi
    rm -f "$body"
    die "Telegram rejected this token (HTTP ${code:-?}) — double-check it with @BotFather."
}

# ----------------------------------------------------------------------------- env file helpers (KEY = "value")
env_get() { # <file> <key>
    [[ -f "$1" ]] || return 0
    grep -E "^[[:space:]]*$2[[:space:]]*=" "$1" 2>/dev/null | head -1 | sed -E 's/^[^=]*=[[:space:]]*"?([^"]*)"?[[:space:]]*$/\1/' || true
}
env_set() { # <file> <key> <value>
    local f="$1" key="$2" val="$3" esc
    esc="${val//\\/\\\\}"; esc="${esc//|/\\|}"; esc="${esc//&/\\&}"
    if grep -qE "^[[:space:]]*${key}[[:space:]]*=" "$f" 2>/dev/null; then
        sed -i -E "s|^[[:space:]]*${key}[[:space:]]*=.*|${key} = \"${esc}\"|" "$f"
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
# NB: `grep -c` prints "0" AND exits 1 on an empty registry — a bare
# `|| echo 0` would emit a second line and garble `-gt` comparisons.
instance_count() {
    local n=""
    [[ -f "$REGISTRY" ]] && n="$(grep -c . "$REGISTRY" 2>/dev/null || true)"
    echo "${n:-0}"
}

print_instance_choices() { # include_all[yes|no] stream[out|err]
    local include_all="${1:-no}" stream="${2:-out}" i=1 n domain redis
    if [[ "$include_all" == "yes" ]]; then
        if [[ "$stream" == "err" ]]; then printf >&2 "  ${CYAN}%2s)${NC} %s\n" "a" "All bots"; else printf "  ${CYAN}%2s)${NC} %s\n" "a" "All bots"; fi
    fi
    while IFS= read -r n; do
        [[ -n "$n" ]] || continue
        domain="$(reg_field "$n" 2)"
        redis="$(reg_field "$n" 5)"
        if [[ "$stream" == "err" ]]; then
            printf >&2 "  ${CYAN}%2d)${NC} %-18s %s  Redis:%s\n" "$i" "$n" "$domain" "$redis"
        else
            printf "  ${CYAN}%2d)${NC} %-18s %s  Redis:%s\n" "$i" "$n" "$domain" "$redis"
        fi
        i=$((i + 1))
    done < <(reg_names)
    if (( i == 1 )) && [[ "$include_all" != "yes" ]]; then
        if [[ "$stream" == "err" ]]; then printf >&2 "  No bot instances found.\n"; else printf "  No bot instances found.\n"; fi
    fi
}

choice_to_instance() { # choice -> stdout name or empty
    local choice="$1" n
    if [[ "$choice" =~ ^[0-9]+$ ]]; then
        (( choice > 0 )) || return 1
        n="$(reg_names | sed -n "${choice}p")"
    else
        n="$(clean_name "$choice")"
    fi
    [[ -n "$n" ]] && reg_has "$n" || return 1
    echo "$n"
}

backup_scope_label() {
    case "${1:-each}" in
        each|all) echo "All bots · separate files" ;;
        combined) echo "All bots · single archive" ;;
        *) echo "Bot: $1" ;;
    esac
}

schedule_label() {
    case "${1:-}" in
        "0 * * * *") echo "Hourly" ;;
        "0 */6 * * *") echo "Every 6 hours" ;;
        "0 */12 * * *") echo "Every 12 hours" ;;
        "0 3 * * *") echo "Daily at 03:00" ;;
        "") echo "Off" ;;
        *) echo "$1" ;;
    esac
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
    # unless-stopped: on-failure does NOT bring containers back after a reboot
    restart: unless-stopped
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
    restart: unless-stopped
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

# Always returns 0 (callers like do_add must finish their remaining steps),
# but reports the real outcome — a failed reload used to print "reloaded".
caddy_reload() {
    docker ps --format '{{.Names}}' | grep -qx "${PLATFORM_PROJECT}-caddy" || return 0
    # validate BEFORE reload: a bad Caddyfile must never replace the running
    # config (that would take every bot's panel + webhooks down at once)
    if ! docker exec "${PLATFORM_PROJECT}-caddy" caddy validate --config /etc/caddy/Caddyfile >/dev/null 2>&1; then
        err "Caddyfile is INVALID — Caddy keeps serving the previous config. Inspect: ${CADDY_DIR}/Caddyfile"
        return 0
    fi
    if docker exec "${PLATFORM_PROJECT}-caddy" caddy reload --config /etc/caddy/Caddyfile >/dev/null 2>&1; then
        info "Caddy reloaded."
    elif dcp restart caddy >/dev/null 2>&1; then
        info "Caddy restarted."
    else
        err "Caddy reload AND restart failed — panels/webhooks may be down. Check: docker logs ${PLATFORM_PROJECT}-caddy"
    fi
    return 0
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

# best-effort: warn if the bot container died right after start (bad token /
# bad .env are the common causes) instead of reporting an unconditional "up"
verify_instance() { # name
    local n="$1" st
    sleep 4
    st="$(docker inspect -f '{{.State.Status}}' "guardino-bot-${n}-bot" 2>/dev/null || true)"
    [[ "$st" == "running" ]] && return 0
    warn "Bot container is '${st:-missing}' — it may be crash-looping."
    warn "Inspect with:  ${CYAN}guardino-bot logs ${n} bot${NC}"
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
    if [[ -n "$ans" && -n "$cur" && "$BASE_DOMAIN" != "$cur" && "$(instance_count)" -gt 0 ]]; then
        warn "Existing bots keep their old <name>.${cur} domains — the new base applies only to bots added from now on."
    fi
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
    # unless-stopped: on-failure does NOT bring containers back after a reboot
    restart: unless-stopped
    env_file: [.env]
    mem_limit: 512m
    networks: [default, ${NET}]

  api:
    image: ${BOT_IMAGE}
    container_name: guardino-bot-${n}-api
    restart: unless-stopped
    command: uvicorn app.api.main:app --host 0.0.0.0 --port 8000
    env_file: [.env]
    mem_limit: 384m
    networks: [default, ${NET}]

  webpanel:
    image: ${WEB_IMAGE}
    container_name: guardino-bot-${n}-webpanel
    restart: unless-stopped
    mem_limit: 96m
    depends_on: [api]
    networks: [default, ${NET}]
    environment:
      # MUST be the instance's unique api container: on the shared network
      # every instance's api is aliased "api" and the bare name round-robins
      # across ALL bots' APIs (login codes from the wrong bot, random 401s).
      API_UPSTREAM: guardino-bot-${n}-api:8000

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
        # config.py silently drops non-numeric entries → bot would start with
        # NO admin at all; catch @usernames here (stderr: stdout is captured)
        [[ "$line" =~ ^[0-9]+$ ]] || { echo "${YELLOW}[!]${NC} Numeric Telegram ID expected (not a @username) — ignored." >&2; continue; }
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
    local other
    while IFS= read -r other; do
        if [[ -n "$other" && "$(env_get "$(inst_env "$other")" BOT_TOKEN)" == "$token" ]]; then
            die "This token is already used by instance '${other}' — two bots polling one token break both."
        fi
    done < <(reg_names)
    check_bot_token "$token"
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
    verify_instance "$name"
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
    # Ship PLATFORM-level changes too: the compose (restart policies, images)
    # and the Caddyfile — a WEBHOOK_PATHS entry added by an update would
    # otherwise never reach existing servers (silently dead IPN for the new
    # gateway, since the on-disk Caddyfile predates it).
    write_platform_compose
    dcp up -d
    assemble_caddyfile; caddy_reload
    local n
    # Regenerate each instance's compose too: updates ship compose changes
    # (e.g. the per-instance API_UPSTREAM that fixes cross-bot API routing) —
    # without this, existing instances keep the old generated file forever.
    if [[ "$target" == "all" ]]; then
        while IFS= read -r n; do
            [[ -n "$n" ]] || continue
            info "Updating '${n}' ..."
            write_instance_compose "$n"
            dci "$n" up -d
        done < <(reg_names)
    else
        reg_has "$target" || die "No instance '$target'."
        info "Updating '${target}' ..."
        write_instance_compose "$target"
        dci "$target" up -d
    fi
    docker image prune -f >/dev/null 2>&1 || true
    info "Update complete (migrations applied on start)."
}

do_update_menu() {
    ensure_platform
    local target; target="$(pick_instance_or_all "")"
    do_update "$target"
}

do_list() {
    ensure_platform
    title "🤖 Guardino-Bot instances"
    printf "%-18s %-34s %-24s %-8s\n" "NAME" "DOMAIN" "DB" "REDIS_DB"; hr
    local n
    while IFS= read -r n; do
        [[ -n "$n" ]] || continue
        printf "%-18s %-34s %-24s %-8s\n" "$n" "$(reg_field "$n" 2)" "$(reg_field "$n" 3)" "$(reg_field "$n" 5)"
    done < <(reg_names)
    hr
}

pick_instance() { # echoes a chosen instance name (arg or prompt)
    local name="${1:-}" choice
    if [[ -z "$name" ]]; then
        [[ "$(instance_count)" -gt 0 ]] || die "No bot instances found."
        echo >&2
        hr >&2
        echo "  ${CYAN}Select bot instance${NC}" >&2
        hr >&2
        print_instance_choices no err
        read -rp "Bot number/name: " choice
        name="$(choice_to_instance "$choice")" || die "Invalid bot selection."
    else
        name="$(clean_name "$name")"
    fi
    reg_has "$name" || die "No instance '$name'."
    echo "$name"
}

pick_instance_or_all() { # echoes "all" or a chosen instance name
    local name="${1:-}" choice
    case "$name" in
        all|ALL|a|A) echo "all"; return 0 ;;
    esac
    if [[ -z "$name" ]]; then
        [[ "$(instance_count)" -gt 0 ]] || die "No bot instances found."
        echo >&2
        hr >&2
        echo "  ${CYAN}Select target bot${NC}" >&2
        hr >&2
        print_instance_choices yes err
        read -rp "Bot number/name/all: " choice
        case "$choice" in
            all|ALL|a|A) echo "all"; return 0 ;;
        esac
        name="$(choice_to_instance "$choice")" || die "Invalid bot selection."
    else
        name="$(clean_name "$name")"
    fi
    reg_has "$name" || die "No instance '$name'."
    echo "$name"
}

do_logs() {
    ensure_platform; local n; n="$(pick_instance "${1:-}")"
    local svc="${2:-bot}"
    dci "$n" logs -f --tail=200 "$svc"
}

run_instance_action() { # restart|stop|start target
    local action="$1" target="$2" n
    if [[ "$target" == "all" ]]; then
        while IFS= read -r n; do
            [[ -n "$n" ]] || continue
            run_instance_action "$action" "$n"
        done < <(reg_names)
        return 0
    fi
    case "$action" in
        restart) dci "$target" restart; info "Restarted '$target'." ;;
        # stop (not down): keep the containers so `docker logs` history survives
        stop)    dci "$target" stop;    info "Stopped '$target'." ;;
        start)   dci "$target" up -d;   info "Started '$target'." ;;
        *)       die "Unknown action: $action" ;;
    esac
}

do_restart() { ensure_platform; local n; n="$(pick_instance_or_all "${1:-}")"; run_instance_action restart "$n"; }
do_stop()    { ensure_platform; local n; n="$(pick_instance_or_all "${1:-}")"; run_instance_action stop "$n"; }
do_start()   { ensure_platform; local n; n="$(pick_instance_or_all "${1:-}")"; run_instance_action start "$n"; }
do_status()  { ensure_platform; info "Platform:"; dcp ps; local n; while IFS= read -r n; do [[ -n "$n" ]] || continue; echo; info "Instance ${n}:"; dci "$n" ps; done < <(reg_names); }
do_edit_env(){ ensure_platform; local n; n="$(pick_instance "${1:-}")"; "${EDITOR:-nano}" "$(inst_env "$n")"; warn "Restart the bot to apply: guardino-bot restart $n"; }

do_control_menu() {
    ensure_platform
    while true; do
        title "⚙️ Bot controls"
        printf "  Active instances: %s\n" "$(instance_count)"
        hr
        menu_item 1 "Restart bot(s)"
        menu_item 2 "Stop bot(s)"
        menu_item 3 "Start bot(s)"
        menu_item 0 "Back"
        local act target
        read -rp "Choice: " act || return
        case "$act" in
            1) target="$(pick_instance_or_all "")"; run_instance_action restart "$target" ;;
            2) target="$(pick_instance_or_all "")"; run_instance_action stop "$target" ;;
            3) target="$(pick_instance_or_all "")"; run_instance_action start "$target" ;;
            0) return ;;
            *) warn "Invalid option." ;;
        esac
    done
}

backup_one() { # name -> path
    local n="$1" db ts out tmp
    reg_has "$n" || { warn "No instance '$n'."; return 1; }
    db="$(reg_field "$n" 3)"
    [[ -n "$db" ]] || { warn "No database registered for '${n}'."; return 1; }
    ts="$(date +%Y%m%d-%H%M%S)"
    mkdir -p "${BACKUP_ROOT}/${n}"
    # not /tmp: it's RAM-backed (tmpfs) on newer distros, and a large DB dump
    # would eat the server's memory
    tmp="$(mktemp -d "${BACKUP_ROOT}/.tmp.XXXXXX")"
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
    if ! tar -czf "$out" -C "$tmp" . 2>/dev/null; then
        warn "  Archive creation failed for '${n}'."
        rm -rf "$tmp"; rm -f "$out"
        return 1
    fi
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
        local n; n="$(pick_instance "$target")"; backup_one "$n"
    fi
}

do_backup_menu() {
    ensure_platform
    local target; target="$(pick_instance_or_all "")"
    do_backup "$target"
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
        _tg_send_doc "$token" "$chat" "$p" "${caption}
📦 Part: ${i}/${n}
🔧 Restore: cat *.part_* > $(basename "$file")" \
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

backup_caption() { # instance|ALL mode
    local target="$1" mode="${2:-Single bot}" now
    now="$(date '+%Y-%m-%d %H:%M')"
    printf '🗄 Guardino-Bot Backup\n'
    printf '📌 Scope: %s\n' "$target"
    printf '🧩 Mode: %s\n' "$mode"
    printf '🖥 Server: %s\n' "$(hostname)"
    printf '🕒 Time: %s' "$now"
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
    local name="$3"
    if ! backup_one "$name"; then
        warn "  backup failed for '${name}'; Telegram send skipped."
        return 1
    fi
    local f; f=$(ls -1t "${BACKUP_ROOT}/${name}"/*.tar.gz 2>/dev/null | head -1 || true)
    [[ -f "$f" ]] || { warn "  no backup produced for '${name}'"; return 1; }
    local snd; snd=$(_maybe_encrypt "$f")
    tg_send_file "$1" "$2" "$snd" "$(backup_caption "$name" "Separate file")" || {
        [[ "$snd" != "$f" ]] && rm -f "$snd"
        return 1
    }
    [[ "$snd" != "$f" ]] && rm -f "$snd"
    info "  Telegram sent: ${name}"
    return 0
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
    info "Backup → Telegram ($(backup_scope_label "$scope")) ..."
    local failed=0 sent=0 attempted=0
    if [[ "$scope" == "combined" ]]; then
        local n latest rels=() ts combo snd
        ts=$(date +%Y%m%d-%H%M%S)
        while IFS= read -r n; do
            [[ -n "$n" ]] || continue
            attempted=$((attempted + 1))
            if backup_one "$n"; then
                latest=$(ls -1t "${BACKUP_ROOT}/$n"/*.tar.gz 2>/dev/null | head -1 || true)
                [[ -f "$latest" ]] && rels+=( "${n}/$(basename "$latest")" )
            else
                failed=$((failed + 1))
            fi
        done < <(reg_names)
        [[ ${#rels[@]} -gt 0 ]] || { warn "No bots were backed up."; return 1; }
        combo="${BACKUP_ROOT}/.tmp-all-${ts}.tar.gz"
        if ! tar -czf "$combo" -C "$BACKUP_ROOT" "${rels[@]}" 2>/dev/null; then
            rm -f "$combo"
            err "Combined backup archive creation failed."
            return 1
        fi
        snd=$(_maybe_encrypt "$combo")
        if tg_send_file "$token" "$chat" "$snd" "$(backup_caption "All bots" "Single archive")"; then
            sent=1
        else
            failed=$((failed + 1))
        fi
        [[ "$snd" != "$combo" ]] && rm -f "$snd"
        rm -f "$combo"
    elif [[ "$scope" == "each" || "$scope" == "all" ]]; then
        local n
        while IFS= read -r n; do
            [[ -n "$n" ]] || continue
            attempted=$((attempted + 1))
            if _send_one_to_tg "$token" "$chat" "$n"; then
                sent=$((sent + 1))
            else
                failed=$((failed + 1))
            fi
        done < <(reg_names)
        (( attempted > 0 )) || { warn "No bot instances found to back up."; return 1; }
    else
        reg_has "$scope" || { err "Instance '$scope' not found."; return 1; }
        attempted=1
        if _send_one_to_tg "$token" "$chat" "$scope"; then
            sent=1
        else
            failed=1
        fi
    fi
    (( failed == 0 )) || { err "Backup → Telegram finished with errors (${sent} sent, ${failed} failed)."; return 1; }
    info "Backup → Telegram done (${sent} sent)."
}

valid_cron_expr() {
    [[ "$1" != *$'\n'* ]] || return 1
    [[ "$(awk '{print NF}' <<<"$1")" -eq 5 ]] || return 1
    # numbers/steps/ranges/lists only — one malformed line makes cron silently
    # ignore the WHOLE cron.d file, so catch typos before installing it
    [[ "$1" =~ ^[0-9*/,[:space:]-]+$ ]]
}

ensure_cron_service() {
    if ! command -v cron >/dev/null 2>&1 && ! command -v crond >/dev/null 2>&1; then
        detect_pkg_manager
        info "Installing cron service ..."
        case "$PKG" in
            apt) DEBIAN_FRONTEND=noninteractive apt-get install -y cron >/dev/null 2>&1 || true ;;
            dnf) dnf install -y cronie >/dev/null 2>&1 || true ;;
            yum) yum install -y cronie >/dev/null 2>&1 || true ;;
            *)   warn "cron is not installed; install cron/cronie manually." ;;
        esac
    fi
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
${1} root ${BIN_PATH} backup-send >> ${BACKUP_LOG} 2>&1
CRON
    chmod 0644 "$BACKUP_CRON"
    touch "$BACKUP_LOG" 2>/dev/null || true
    ensure_cron_service
    command -v crond >/dev/null 2>&1 || command -v cron >/dev/null 2>&1 || \
        warn "cron not found — install it (apt/dnf install cron|cronie) so the schedule runs."
    info "Scheduled '${1}' ($(schedule_label "$1")). Log: ${BACKUP_LOG}"
}
disable_backup_cron() { rm -f "$BACKUP_CRON"; info "Scheduled Telegram backup disabled."; }

do_backup_telegram() {
    need_root; ensure_platform
    mkdir -p "$ROOT_DIR"; umask 077
    [[ -f "$BACKUP_CONF" ]] || : > "$BACKUP_CONF"
    chmod 600 "$BACKUP_CONF"
    install_cli auto
    warn "Backups contain each bot's .env (DB creds, SECRET_KEY_STRING, BOT_TOKEN)."
    warn "Use a PRIVATE backup bot/chat; consider the encryption passphrase."
    while true; do
        local tk ch sc sched enc v nm
        tk=$(env_get "$BACKUP_CONF" BACKUP_BOT_TOKEN); ch=$(env_get "$BACKUP_CONF" BACKUP_CHAT_ID)
        sc=$(env_get "$BACKUP_CONF" BACKUP_SCOPE); sched=$(env_get "$BACKUP_CONF" BACKUP_SCHEDULE)
        enc=$(env_get "$BACKUP_CONF" BACKUP_ENC_PASS)
        title "🗄 Telegram backup"
        printf "  Destination : %s   Chat: %s\n" "$( [[ -n $tk ]] && echo 'set' || echo 'not set' )" "${ch:-not set}"
        printf "  Scope       : %s\n" "$(backup_scope_label "${sc:-each}")"
        printf "  Schedule    : %s   Cron: %s\n" "$(schedule_label "$sched")" "$( [[ -f $BACKUP_CRON ]] && echo active || echo off )"
        printf "  Encryption  : %s\n" "$( [[ -n $enc ]] && echo enabled || echo disabled )"
        hr
        menu_item 1 "Set Telegram bot token + chat id"
        menu_item 2 "Choose backup scope"
        menu_item 3 "Set schedule"
        menu_item 4 "Encryption passphrase"
        menu_item 5 "Send backup now"
        menu_item 6 "Disable schedule"
        menu_item 0 "Back"
        read -rp "Choice: " bc || return
        case "$bc" in
            1) read -rp "Backup bot token: " v; [[ -n "$v" ]] && env_set "$BACKUP_CONF" BACKUP_BOT_TOKEN "$v"
               echo "Send any message to the backup bot, then press Enter to auto-detect (or type the chat id):"
               read -rp "chat id: " v
               [[ -z "$v" ]] && { v=$(_detect_chat_id "$(env_get "$BACKUP_CONF" BACKUP_BOT_TOKEN)"); [[ -n "$v" ]] && info "Detected: $v"; }
               [[ -n "$v" ]] && env_set "$BACKUP_CONF" BACKUP_CHAT_ID "$v" || warn "No chat id set." ;;
            2) title "📦 Backup scope"
               menu_item 1 "One selected bot"
               menu_item 2 "All bots · separate files"
               menu_item 3 "All bots · single archive"
               read -rp "Choice: " v
               case "$v" in
                   1) nm="$(pick_instance "")" && env_set "$BACKUP_CONF" BACKUP_SCOPE "$nm" ;;
                   2) env_set "$BACKUP_CONF" BACKUP_SCOPE "each" ;;
                   3) env_set "$BACKUP_CONF" BACKUP_SCOPE "combined" ;;
                   *) warn "Invalid." ;;
               esac ;;
            3) title "⏱ Backup schedule"
               menu_item 1 "Hourly"
               menu_item 2 "Every 6 hours"
               menu_item 3 "Every 12 hours"
               menu_item 4 "Daily at 03:00"
               menu_item 5 "Custom cron expression"
               read -rp "Choice: " v; local cron=""
               case "$v" in
                   1) cron="0 * * * *";; 2) cron="0 */6 * * *";; 3) cron="0 */12 * * *";;
                   4) cron="0 3 * * *";; 5) read -rp "Cron (min hour dom mon dow): " cron;;
                   *) warn "Invalid.";;
               esac
               [[ -n "$cron" ]] && { env_set "$BACKUP_CONF" BACKUP_SCHEDULE "$cron"; install_backup_cron "$cron"; } ;;
            4) read -rsp "Encryption passphrase (empty = disable): " v; echo
               # env_get cuts the value at the first '"' — such a passphrase
               # would encrypt with a TRUNCATED key the user can never retype
               case "$v" in *'"'*|*'\'*)
                   warn "Double quotes and backslashes are not supported in the passphrase — not saved."; continue ;;
               esac
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

    mkdir -p "$BACKUP_ROOT"
    local tmp; tmp="$(mktemp -d "${BACKUP_ROOT}/.tmp.XXXXXX")"
    tar -xzf "$file" -C "$tmp" || die "Cannot extract $file"
    [[ -f "${tmp}/.env" ]] || die "Backup missing .env (a 'combined' archive holds one tar.gz per bot — extract it and restore each inner file)."
    local rdb; rdb="$(env_get "${tmp}/.env" REDIS_DB)"
    # never share a Redis logical DB with a different live instance
    if [[ -z "$rdb" ]] || awk -F'\t' -v n="$name" -v r="$rdb" '$1!=n && $5==r{f=1} END{exit !f}' "$REGISTRY"; then
        rdb="$(alloc_redis_db)"
    fi
    # DB/user/domain derive from the TARGET name (same as `add`), never from
    # the backup's .env: restoring under a new name while the original bot is
    # alive must not attach both to one live database or emit a duplicate
    # Caddy site block (duplicate addresses fail validation → panels down).
    local sani db du dp domain
    sani="$(sanitize "$name")"; db="guardino_bot_${sani}"; du="gbot_${sani:0:23}"; dp="$(rand 24)"
    BASE_DOMAIN="$(env_get "$PLATFORM_ENV" BASE_DOMAIN)"
    if [[ -n "$BASE_DOMAIN" ]]; then
        domain="${name}.${BASE_DOMAIN}"
    else
        domain="$(env_get "${tmp}/.env" DOMAIN)"; [[ -n "$domain" ]] || domain="$name"
        if awk -F'\t' -v n="$name" -v d="$domain" '$1!=n && $2==d{f=1} END{exit !f}' "$REGISTRY" 2>/dev/null; then
            die "Domain '${domain}' already belongs to another instance — set a base domain or restore under the original name."
        fi
    fi

    warn "Restoring '${name}' into DB '${db}' (Redis DB ${rdb}, domain ${domain})."
    read -rp "Continue? (yes/no): " a; [[ "$a" == "yes" ]] || { info "Cancelled."; rm -rf "$tmp"; return; }

    info "Creating DB + user ..."; create_db "$db" "$du" "$dp"
    if [[ -f "${tmp}/database.sql" ]]; then
        info "Importing database dump ..."
        docker exec -i -e MYSQL_PWD="$ROOT_PASS" "${PLATFORM_PROJECT}-mariadb" mariadb -uroot "$db" < "${tmp}/database.sql" || die "DB import failed."
    fi
    mkdir -p "$(inst_dir "$name")"
    cp -f "${tmp}/.env" "$(inst_env "$name")"
    chmod 600 "$(inst_env "$name")"
    env_set "$(inst_env "$name")" REDIS_DB "$rdb"
    env_set "$(inst_env "$name")" DATABASE_URL "mysql://${du}:${dp}@mariadb:3306/${db}"
    env_set "$(inst_env "$name")" DOMAIN "$domain"
    env_set "$(inst_env "$name")" WEBHOOK_BASE_URL "https://${domain}"
    env_set "$(inst_env "$name")" PUBLIC_BASE_URL "https://${domain}"
    write_instance_compose "$name"
    reg_add "$name" "$domain" "$db" "$du" "$rdb"
    assemble_caddyfile; caddy_reload
    dci "$name" up -d
    verify_instance "$name"
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
        # the .env being deleted below holds the only copy of SECRET_KEY_STRING —
        # without it the PasswordField columns in the kept DB are unrecoverable
        mkdir -p "${BACKUP_ROOT}/${n}"
        cp -f "$(inst_env "$n")" "${BACKUP_ROOT}/${n}/env-removed-$(date +%Y%m%d-%H%M%S).bak" 2>/dev/null || true
        info "Database kept (${db}) — .env preserved in ${BACKUP_ROOT}/${n}/."
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
    # either way the cron must go: it would keep invoking the removed CLI forever
    rm -f "$BACKUP_CRON"
    if [[ "$b" == "yes" ]]; then
        docker network rm "$NET" >/dev/null 2>&1 || true
        rm -rf "$DATA_DIR" "$ROOT_DIR" "$BIN_PATH"
        rm -f "$BACKUP_LOG"
        info "Everything removed."
    else
        info "Containers stopped; data kept in ${DATA_DIR}. Scheduled backup cron removed."
    fi
}

valid_cli_script() { # file
    [[ -s "${1:-}" ]] || return 1
    grep -q 'guardino-bot' "$1" || return 1
    grep -q 'backup-send)' "$1" || return 1
    bash -n "$1" >/dev/null 2>&1 || return 1
}

usable_self_source() { # file
    local p="${1:-}"
    [[ -n "$p" && -r "$p" && -f "$p" ]] || return 1
    case "$p" in
        /dev/fd/*|/proc/*/fd/*) return 1 ;;
    esac
    valid_cli_script "$p"
}

download_cli_script() { # output-file
    curl -fsSL --ipv4 "$RAW_SCRIPT" -o "$1" || return 1
    valid_cli_script "$1"
}

install_cli() { # [auto|repo|current|remote]
    local mode="${1:-auto}" src="" self="${BASH_SOURCE[0]:-$0}" repo_script="${SRC_DIR}/installer/guardino-bot.sh" force_remote=0
    case "$mode" in
        remote)
            force_remote=1
            ;;
        repo)
            valid_cli_script "$repo_script" && src="$repo_script"
            ;;
        current)
            usable_self_source "$self" && src="$self"
            ;;
        auto|"")
            if [[ "$self" == "$BIN_PATH" ]] && valid_cli_script "$BIN_PATH"; then
                info "Management command is already installed: ${CYAN}guardino-bot${NC}"
                return 0
            elif [[ "$self" != "$BIN_PATH" ]] && usable_self_source "$self"; then
                src="$self"
            elif valid_cli_script "$repo_script"; then
                src="$repo_script"
            fi
            ;;
        *)
            die "Unknown install_cli mode: $mode"
            ;;
    esac
    if [[ "$force_remote" -eq 0 && -n "$src" ]] && install -m 0755 -D "$src" "$BIN_PATH" 2>/dev/null; then
        :
    elif [[ "$force_remote" -eq 0 && "$src" != "$repo_script" ]] && valid_cli_script "$repo_script" \
        && install -m 0755 -D "$repo_script" "$BIN_PATH" 2>/dev/null; then
        :
    else
        local tmp
        tmp="$(mktemp)"
        download_cli_script "$tmp" || { rm -f "$tmp"; die "Could not download a valid management command."; }
        install -m 0755 -D "$tmp" "$BIN_PATH" || { rm -f "$tmp"; die "Could not install ${BIN_PATH}."; }
        rm -f "$tmp"
    fi
    valid_cli_script "$BIN_PATH" || die "Installed management command is invalid: ${BIN_PATH}"
    info "Management command installed: ${CYAN}guardino-bot${NC}"
}

is_stream_invocation() {
    local self="${BASH_SOURCE[0]:-$0}"
    [[ "$self" == "$BIN_PATH" ]] && return 1
    case "$self" in
        /dev/fd/*|/proc/*/fd/*) return 0 ;;
    esac
    return 1
}

sync_cli_for_remote_run() {
    is_stream_invocation || return 0
    need_root
    install_cli remote
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
    # subshell actions reset this handler to the default, so ^C kills only the
    # foreground action (e.g. leaving `logs -f`) and the menu survives;
    # ^C at the "Choice:" prompt still exits via `|| exit 0`.
    trap ':' INT
    while true; do
        title "🛡 ${APP_NAME} Manager"
        printf "  Instances: %s   Root: %s\n" "$(instance_count)" "$ROOT_DIR"
        hr
        menu_item 1 "🚀 Install / initialize platform"
        menu_item 2 "➕ Add new bot"
        menu_item 3 "⬆️  Update bots"
        menu_item 4 "📋 List bots"
        menu_item 5 "💾 Create local backup"
        menu_item 6 "♻️  Restore backup"
        menu_item 7 "📜 View logs"
        menu_item 8 "⚙️  Start / stop / restart bots"
        menu_item 9 "📊 Status"
        menu_item 10 "📝 Edit bot .env"
        menu_item 11 "🌐 Base domain"
        menu_item 12 "🗑 Remove bot"
        menu_item 13 "⚠️  Uninstall"
        menu_item 14 "🗄 Telegram backups"
        menu_item 0 "Exit"
        read -rp "Choice: " c || exit 0
        # each action runs in a subshell so a failure (die) returns to the menu
        # instead of dropping the user back to the shell.
        case "$c" in
            1)  ( do_install ) || true ;;
            2)  ( do_add ) || true ;;
            3)  ( do_update_menu ) || true ;;
            4)  ( do_list ) || true ;;
            5)  ( do_backup_menu ) || true ;;
            6)  ( do_restore ) || true ;;
            7)  ( do_logs ) || true ;;
            8)  ( do_control_menu ) || true ;;
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
sync_cli_for_remote_run
case "${1:-}" in
    install)        do_install ;;
    platform-up)    do_platform_up ;;
    add)            shift; do_add "${1:-}" ;;
    update)         shift; do_update "${1:-all}" ;;
    list)           do_list ;;
    backup)         shift; do_backup "${1:-all}" ;;
    backup-send)    backup_and_send ;;
    backup-telegram) do_backup_telegram ;;
    repair-cli)     need_root; install_cli remote ;;
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
    *)              die "Unknown subcommand: ${1}. Try: install|platform-up|add|update|list|backup|backup-send|backup-telegram|repair-cli|restore|logs|restart|stop|start|status|edit-env|domain|remove|uninstall" ;;
esac
