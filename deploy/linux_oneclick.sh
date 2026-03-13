#!/usr/bin/env bash
set -Eeuo pipefail

APP_NAME="${APP_NAME:-ai_plat}"
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="${PROJECT_ROOT}/backend"
FRONTEND_DIR="${PROJECT_ROOT}/frontend"
BACKEND_ENV_FILE="${BACKEND_DIR}/.env"
FRONTEND_ENV_FILE="${FRONTEND_DIR}/.env.production.local"

RUN_USER="${RUN_USER:-${SUDO_USER:-$(id -un)}}"
RUN_GROUP="${RUN_GROUP:-$(id -gn "${RUN_USER}")}"

DOMAIN="${DOMAIN:-}"
SERVER_IP="${SERVER_IP:-}"
SERVER_NAME="${SERVER_NAME:-${DOMAIN:-_}}"

BACKEND_BIND_HOST="${BACKEND_BIND_HOST:-127.0.0.1}"
BACKEND_BIND_PORT="${BACKEND_BIND_PORT:-8000}"
BACKEND_BIND="${BACKEND_BIND_HOST}:${BACKEND_BIND_PORT}"
GUNICORN_WORKERS="${GUNICORN_WORKERS:-3}"
GUNICORN_TIMEOUT="${GUNICORN_TIMEOUT:-900}"

DB_NAME="${DB_NAME:-api_test_platform}"
DB_USER="${DB_USER:-api_user}"
DB_PASSWORD="${DB_PASSWORD:-ChangeMe_123456}"
DB_HOST="${DB_HOST:-127.0.0.1}"
DB_PORT="${DB_PORT:-3306}"
DB_MYSQL57_COMPAT="${DB_MYSQL57_COMPAT:-False}"

DJANGO_DEBUG="${DJANGO_DEBUG:-False}"
DJANGO_SECRET_KEY="${DJANGO_SECRET_KEY:-}"
DJANGO_ALLOWED_HOSTS="${DJANGO_ALLOWED_HOSTS:-}"
DJANGO_CORS_ALLOWED_ORIGINS="${DJANGO_CORS_ALLOWED_ORIGINS:-}"

DEFAULT_ADMIN_USERNAME="${DEFAULT_ADMIN_USERNAME:-admin}"
DEFAULT_ADMIN_PASSWORD="${DEFAULT_ADMIN_PASSWORD:-admin123456}"
DEFAULT_ADMIN_EMAIL="${DEFAULT_ADMIN_EMAIL:-}"
AUTH_TOKEN_TTL_SECONDS="${AUTH_TOKEN_TTL_SECONDS:-259200}"

AI_BASE_URL="${AI_BASE_URL:-https://api.openai.com/v1}"
AI_API_KEY="${AI_API_KEY:-}"
AI_MODEL="${AI_MODEL:-gpt-4o-mini}"
AI_TIMEOUT_SECONDS="${AI_TIMEOUT_SECONDS:-60}"

SYSTEMD_SERVICE="${SYSTEMD_SERVICE:-${APP_NAME}-backend}"
NGINX_SITE_NAME="${NGINX_SITE_NAME:-${APP_NAME}}"

OFFLINE_MODE="${OFFLINE_MODE:-false}"
OFFLINE_DIR="${OFFLINE_DIR:-${PROJECT_ROOT}/deploy/offline}"
OFFLINE_OS_PACKAGE_DIR="${OFFLINE_OS_PACKAGE_DIR:-${OFFLINE_DIR}/os-packages}"
OFFLINE_PYTHON_WHEEL_DIR="${OFFLINE_PYTHON_WHEEL_DIR:-${OFFLINE_DIR}/python}"
OFFLINE_FRONTEND_DIST_DIR="${OFFLINE_FRONTEND_DIST_DIR:-${OFFLINE_DIR}/frontend-dist}"
OFFLINE_FRONTEND_DIST_ARCHIVE="${OFFLINE_FRONTEND_DIST_ARCHIVE:-${OFFLINE_DIR}/frontend-dist.tar.gz}"
OFFLINE_FRONTEND_DIST_TGZ="${OFFLINE_FRONTEND_DIST_TGZ:-${OFFLINE_DIR}/frontend-dist.tgz}"

ENABLE_MIRROR_REWRITE="${ENABLE_MIRROR_REWRITE:-true}"
APT_MIRROR_BASE="${APT_MIRROR_BASE:-https://mirrors.aliyun.com}"
YUM_MIRROR_BASE="${YUM_MIRROR_BASE:-https://mirrors.aliyun.com}"
PIP_INDEX_URL="${PIP_INDEX_URL:-https://mirrors.aliyun.com/pypi/simple/}"
PIP_TRUSTED_HOST="${PIP_TRUSTED_HOST:-mirrors.aliyun.com}"
NPM_REGISTRY="${NPM_REGISTRY:-https://registry.npmmirror.com}"

PKG_MANAGER=""
PYTHON_BIN="python3"
DB_SERVICE=""
MYSQL_BIN="mysql"
OS_ID=""
OS_ID_LIKE=""
OS_VERSION_ID=""
OS_VERSION=""
OS_CODENAME=""
OS_PRETTY_NAME=""
NODE_MAJOR="0"

log() {
  printf '\n[%s] %s\n' "$(date '+%F %T')" "$*"
}

fatal() {
  printf '\n[ERROR] %s\n' "$*" >&2
  exit 1
}

is_true() {
  case "$(printf '%s' "$1" | tr '[:upper:]' '[:lower:]')" in
    1|true|yes|on) return 0 ;;
    *) return 1 ;;
  esac
}

is_offline_mode() {
  is_true "${OFFLINE_MODE}"
}

command_exists_any() {
  local cmd=""
  for cmd in "$@"; do
    if command -v "${cmd}" >/dev/null 2>&1; then
      printf '%s' "${cmd}"
      return 0
    fi
  done
  return 1
}

ensure_root() {
  if [[ "${EUID}" -eq 0 ]]; then
    return
  fi
  exec sudo -E bash "$0" "$@"
}

run_as_app() {
  if [[ "$(id -un)" == "${RUN_USER}" ]]; then
    bash -lc "$*"
  else
    sudo -H -u "${RUN_USER}" bash -lc "$*"
  fi
}

retry_cmd() {
  local max_attempts="$1"
  local sleep_seconds="$2"
  shift 2

  local attempt=1
  until "$@"; do
    if (( attempt >= max_attempts )); then
      return 1
    fi
    log "Command failed, retry ${attempt}/${max_attempts}: $*"
    sleep "$sleep_seconds"
    attempt=$((attempt + 1))
  done
}

detect_pkg_manager() {
  if command -v apt-get >/dev/null 2>&1; then
    PKG_MANAGER="apt"
    return
  fi
  if command -v dnf >/dev/null 2>&1; then
    PKG_MANAGER="dnf"
    return
  fi
  if command -v yum >/dev/null 2>&1; then
    PKG_MANAGER="yum"
    return
  fi
  fatal "Only apt, dnf and yum based Linux distributions are supported"
}

load_os_release() {
  [[ -f /etc/os-release ]] || fatal "/etc/os-release was not found"
  # shellcheck disable=SC1091
  . /etc/os-release
  OS_ID="$(printf '%s' "${ID:-}" | tr '[:upper:]' '[:lower:]')"
  OS_ID_LIKE="$(printf '%s' "${ID_LIKE:-}" | tr '[:upper:]' '[:lower:]')"
  OS_VERSION_ID="${VERSION_ID:-}"
  OS_VERSION="${VERSION:-}"
  OS_CODENAME="${VERSION_CODENAME:-${UBUNTU_CODENAME:-}}"
  OS_PRETTY_NAME="${PRETTY_NAME:-${NAME:-linux}}"
}

backup_dir() {
  local base="$1"
  local target="/var/backups/${APP_NAME}/$(basename "$base")-$(date +%Y%m%d%H%M%S)"
  mkdir -p "$(dirname "$target")"
  printf '%s' "$target"
}

has_matching_files() {
  local dir="$1"
  local pattern="$2"
  [[ -d "${dir}" ]] || return 1

  shopt -s nullglob
  local files=("${dir}"/${pattern})
  shopt -u nullglob
  (( ${#files[@]} > 0 ))
}

frontend_dist_available() {
  if [[ -f "${OFFLINE_FRONTEND_DIST_ARCHIVE}" || -f "${OFFLINE_FRONTEND_DIST_TGZ}" ]]; then
    return 0
  fi
  [[ -f "${OFFLINE_FRONTEND_DIST_DIR}/index.html" ]]
}

extract_host_from_url() {
  local url="$1"
  url="${url#*://}"
  url="${url%%/*}"
  url="${url%%\?*}"
  url="${url%%\#*}"
  url="${url%%:*}"
  printf '%s' "$url"
}

can_resolve_host() {
  local host="$1"
  [[ -n "${host}" ]] || return 0

  if command -v getent >/dev/null 2>&1; then
    getent ahostsv4 "${host}" >/dev/null 2>&1 || getent hosts "${host}" >/dev/null 2>&1
    return $?
  fi

  return 0
}

ensure_host_resolvable() {
  local host="$1"
  local purpose="${2:-network access}"
  [[ -n "${host}" ]] || return 0

  if can_resolve_host "${host}"; then
    return 0
  fi

  local nameservers=""
  if [[ -f /etc/resolv.conf ]]; then
    nameservers="$(grep -E '^[[:space:]]*nameserver[[:space:]]+' /etc/resolv.conf 2>/dev/null | awk '{print $2}' | xargs || true)"
  fi

  if [[ -n "${nameservers}" ]]; then
    fatal "DNS resolution failed for ${host} (${purpose}). Current nameservers: ${nameservers}. Fix DNS first, for example set nameserver 223.5.5.5 and 223.6.6.6 in /etc/resolv.conf, verify with 'getent hosts ${host}', then rerun the script."
  fi

  fatal "DNS resolution failed for ${host} (${purpose}). No nameserver was found in /etc/resolv.conf. Add a working DNS server such as 223.5.5.5 and 223.6.6.6, verify with 'getent hosts ${host}', then rerun the script."
}

configure_apt_mirrors() {
  log "Configuring Aliyun mirror for apt (${OS_PRETTY_NAME})"
  ensure_host_resolvable "$(extract_host_from_url "${APT_MIRROR_BASE}")" "APT mirror"

  local apt_backup
  apt_backup="$(backup_dir /etc/apt)"
  mkdir -p "${apt_backup}"
  cp -a /etc/apt/. "${apt_backup}/"

  mkdir -p /etc/apt/sources.list.d.disabled
  find /etc/apt/sources.list.d -maxdepth 1 \( -name '*.list' -o -name '*.sources' \) -type f -exec mv {} /etc/apt/sources.list.d.disabled/ \; || true

  local suite="${OS_CODENAME}"
  if [[ -z "${suite}" ]] && command -v lsb_release >/dev/null 2>&1; then
    suite="$(lsb_release -cs 2>/dev/null || true)"
  fi
  [[ -n "${suite}" ]] || fatal "Could not determine apt suite/codename for ${OS_PRETTY_NAME}"

  if [[ "${OS_ID}" == "openkylin" ]]; then
    cat > /etc/apt/sources.list <<EOF
deb ${APT_MIRROR_BASE}/openkylin/ ${suite} main restricted universe multiverse
deb-src ${APT_MIRROR_BASE}/openkylin/ ${suite} main restricted universe multiverse
EOF
  else
    cat > /etc/apt/sources.list <<EOF
deb ${APT_MIRROR_BASE}/ubuntu/ ${suite} main restricted universe multiverse
deb-src ${APT_MIRROR_BASE}/ubuntu/ ${suite} main restricted universe multiverse
deb ${APT_MIRROR_BASE}/ubuntu/ ${suite}-updates main restricted universe multiverse
deb-src ${APT_MIRROR_BASE}/ubuntu/ ${suite}-updates main restricted universe multiverse
deb ${APT_MIRROR_BASE}/ubuntu/ ${suite}-backports main restricted universe multiverse
deb-src ${APT_MIRROR_BASE}/ubuntu/ ${suite}-backports main restricted universe multiverse
deb ${APT_MIRROR_BASE}/ubuntu/ ${suite}-security main restricted universe multiverse
deb-src ${APT_MIRROR_BASE}/ubuntu/ ${suite}-security main restricted universe multiverse
EOF
  fi

  cat > /etc/apt/apt.conf.d/99-${APP_NAME}-retries <<EOF
Acquire::Retries "5";
Acquire::http::Timeout "30";
Acquire::https::Timeout "30";
Acquire::ForceIPv4 "true";
EOF

  retry_cmd 3 3 apt-get clean
  retry_cmd 3 5 apt-get update
}

derive_openeuler_release_tag() {
  local source_text="${OS_VERSION} ${OS_VERSION_ID}"
  local numeric="${OS_VERSION_ID}"
  if [[ "${source_text}" =~ ([0-9]+\.[0-9]+) ]]; then
    numeric="${BASH_REMATCH[1]}"
  fi
  if [[ "${source_text}" =~ LTS-SP([0-9]+) ]]; then
    printf '%s' "${numeric}-LTS-SP${BASH_REMATCH[1]}"
    return
  fi
  if [[ "${source_text}" =~ LTS ]]; then
    printf '%s' "${numeric}-LTS"
    return
  fi
  printf '%s' "${OS_VERSION_ID}"
}

write_centos_repo() {
  local major="$1"
  local stream_mode="$2"
  rm -f /etc/yum.repos.d/*.repo

  if [[ "${stream_mode}" == "true" ]]; then
    cat > /etc/yum.repos.d/CentOS-Stream-Aliyun.repo <<EOF
[baseos]
name=CentOS Stream - BaseOS
baseurl=${YUM_MIRROR_BASE}/repo/centos-stream/${major}/BaseOS/\$basearch/os/
enabled=1
gpgcheck=0

[appstream]
name=CentOS Stream - AppStream
baseurl=${YUM_MIRROR_BASE}/repo/centos-stream/${major}/AppStream/\$basearch/os/
enabled=1
gpgcheck=0

[extras]
name=CentOS Stream - Extras
baseurl=${YUM_MIRROR_BASE}/repo/centos-stream/${major}/extras/\$basearch/os/
enabled=1
gpgcheck=0
EOF
    return
  fi

  if [[ "${major}" == "7" || "${major}" == "8" ]]; then
    retry_cmd 3 5 curl -fL "${YUM_MIRROR_BASE}/repo/Centos-${major}.repo" -o /etc/yum.repos.d/CentOS-Base.repo
    return
  fi

  fatal "CentOS ${major} is not explicitly supported by this script yet"
}

write_openeuler_repo() {
  local release_tag="$1"
  rm -f /etc/yum.repos.d/*.repo
  cat > /etc/yum.repos.d/openEuler-Aliyun.repo <<EOF
[openEuler-OS]
name=openEuler OS
baseurl=${YUM_MIRROR_BASE}/openeuler/openEuler-${release_tag}/OS/\$basearch/
enabled=1
gpgcheck=0

[openEuler-everything]
name=openEuler everything
baseurl=${YUM_MIRROR_BASE}/openeuler/openEuler-${release_tag}/everything/\$basearch/
enabled=1
gpgcheck=0

[openEuler-update]
name=openEuler update
baseurl=${YUM_MIRROR_BASE}/openeuler/openEuler-${release_tag}/update/\$basearch/
enabled=1
gpgcheck=0

[openEuler-EPOL]
name=openEuler EPOL
baseurl=${YUM_MIRROR_BASE}/openeuler/openEuler-${release_tag}/EPOL/\$basearch/
enabled=1
gpgcheck=0
EOF
}

configure_yum_mirrors() {
  log "Configuring Aliyun mirror for ${PKG_MANAGER} (${OS_PRETTY_NAME})"
  ensure_host_resolvable "$(extract_host_from_url "${YUM_MIRROR_BASE}")" "YUM/DNF mirror"

  local yum_backup
  yum_backup="$(backup_dir /etc/yum.repos.d)"
  mkdir -p "${yum_backup}"
  cp -a /etc/yum.repos.d/. "${yum_backup}/" 2>/dev/null || true

  local os_name_lc
  os_name_lc="$(printf '%s' "${OS_PRETTY_NAME}" | tr '[:upper:]' '[:lower:]')"
  local major="${OS_VERSION_ID%%.*}"

  if [[ "${OS_ID}" == "openeuler" || "${OS_ID_LIKE}" == *openeuler* ]]; then
    write_openeuler_repo "$(derive_openeuler_release_tag)"
  elif [[ "${OS_ID}" == "centos" || "${os_name_lc}" == *centos* ]]; then
    if [[ "${os_name_lc}" == *stream* ]]; then
      write_centos_repo "${major}" "true"
    else
      write_centos_repo "${major}" "false"
    fi
  else
    find /etc/yum.repos.d -maxdepth 1 -name '*.repo' -type f -exec sed -ri \
      -e 's|^mirrorlist=|#mirrorlist=|g' \
      -e 's|^metalink=|#metalink=|g' \
      -e 's|mirror.centos.org|mirrors.aliyun.com/centos|g' \
      -e 's|mirror.stream.centos.org|mirrors.aliyun.com/repo/centos-stream|g' \
      -e 's|repo.openeuler.org|mirrors.aliyun.com/openeuler|g' \
      {} + || true
  fi

  retry_cmd 3 3 ${PKG_MANAGER} clean all
  if [[ "${PKG_MANAGER}" == "dnf" ]]; then
    retry_cmd 3 5 dnf makecache
  else
    retry_cmd 3 5 yum makecache
  fi
}

configure_system_mirrors() {
  if is_offline_mode; then
    log "Offline mode is enabled, skip mirror rewrite"
    return
  fi

  if ! is_true "${ENABLE_MIRROR_REWRITE}"; then
    log "Mirror rewrite is disabled"
    return
  fi

  case "${PKG_MANAGER}" in
    apt)
      configure_apt_mirrors
      ;;
    dnf|yum)
      configure_yum_mirrors
      ;;
  esac
}

install_base_packages_offline() {
  log "Offline mode: installing local system packages from ${OFFLINE_OS_PACKAGE_DIR} when available"

  local pattern=""
  case "${PKG_MANAGER}" in
    apt)
      pattern="*.deb"
      ;;
    dnf|yum)
      pattern="*.rpm"
      ;;
  esac

  if ! has_matching_files "${OFFLINE_OS_PACKAGE_DIR}" "${pattern}"; then
    log "Offline mode: no local system packages found, assume required base packages are already installed"
    return
  fi

  shopt -s nullglob
  local files=("${OFFLINE_OS_PACKAGE_DIR}"/${pattern})
  shopt -u nullglob

  case "${PKG_MANAGER}" in
    apt)
      export DEBIAN_FRONTEND=noninteractive
      retry_cmd 3 5 apt-get install -y "${files[@]}"
      ;;
    dnf)
      retry_cmd 3 5 dnf install -y "${files[@]}"
      ;;
    yum)
      retry_cmd 3 5 yum localinstall -y "${files[@]}"
      ;;
  esac
}

verify_offline_prerequisites() {
  local missing=()

  command_exists_any python3 python3.11 python3.10 python3.9 python3.8 >/dev/null || missing+=("python3.8+")
  command -v nginx >/dev/null 2>&1 || missing+=("nginx")
  command_exists_any mysql mariadb >/dev/null || missing+=("mysql/mariadb client")
  command -v systemctl >/dev/null 2>&1 || missing+=("systemctl")

  if (( ${#missing[@]} > 0 )); then
    fatal "Offline mode requires preinstalled base packages or local packages under ${OFFLINE_OS_PACKAGE_DIR}. Missing: ${missing[*]}"
  fi
}

install_base_packages() {
  if is_offline_mode; then
    install_base_packages_offline
    verify_offline_prerequisites
    return
  fi

  case "${PKG_MANAGER}" in
    apt)
      export DEBIAN_FRONTEND=noninteractive
      retry_cmd 3 5 apt-get install -y git curl ca-certificates nginx mysql-server python3 python3-venv python3-pip python3-dev build-essential
      ;;
    dnf)
      retry_cmd 3 5 dnf install -y git curl ca-certificates nginx mariadb-server python3 python3-pip python3-devel gcc gcc-c++ make
      ;;
    yum)
      retry_cmd 3 5 yum install -y git curl ca-certificates nginx mariadb-server python3 python3-pip python3-devel gcc gcc-c++ make
      ;;
  esac
}

ensure_python() {
  PYTHON_BIN="$(command_exists_any python3.11 python3.10 python3.9 python3.8 python3 || true)"
  [[ -n "${PYTHON_BIN}" ]] || fatal "python3.8+ is required"

  "${PYTHON_BIN}" - <<'PY'
import sys
if sys.version_info < (3, 8):
    raise SystemExit("Python 3.8+ is required")
PY

  if [[ -z "${DJANGO_SECRET_KEY}" ]]; then
    DJANGO_SECRET_KEY="$(${PYTHON_BIN} - <<'PY'
import secrets
print(secrets.token_urlsafe(50))
PY
)"
  fi
}

ensure_nodejs() {
  if is_offline_mode; then
    if frontend_dist_available; then
      log "Offline mode: using prebuilt frontend dist, skip Node.js installation"
      return
    fi
    fatal "Offline mode requires ${OFFLINE_FRONTEND_DIST_ARCHIVE} (or ${OFFLINE_FRONTEND_DIST_DIR}/index.html) because Node.js online installation is disabled"
  fi

  if command -v node >/dev/null 2>&1; then
    NODE_MAJOR="$(node -p "process.versions.node.split('.')[0]" 2>/dev/null || echo 0)"
  else
    NODE_MAJOR="0"
  fi
  if [[ "${NODE_MAJOR}" -ge 18 ]]; then
    return
  fi

  log "Installing Node.js 20"
  case "${PKG_MANAGER}" in
    apt)
      ensure_host_resolvable "deb.nodesource.com" "NodeSource APT bootstrap"
      retry_cmd 3 5 bash -lc "curl -fsSL https://deb.nodesource.com/setup_20.x | bash -"
      retry_cmd 3 5 apt-get install -y nodejs
      ;;
    dnf)
      ensure_host_resolvable "rpm.nodesource.com" "NodeSource RPM bootstrap"
      retry_cmd 3 5 bash -lc "curl -fsSL https://rpm.nodesource.com/setup_20.x | bash -"
      retry_cmd 3 5 dnf install -y nodejs
      ;;
    yum)
      ensure_host_resolvable "rpm.nodesource.com" "NodeSource RPM bootstrap"
      retry_cmd 3 5 bash -lc "curl -fsSL https://rpm.nodesource.com/setup_20.x | bash -"
      retry_cmd 3 5 yum install -y nodejs
      ;;
  esac

  command -v node >/dev/null 2>&1 || fatal "Node.js installation failed"
  NODE_MAJOR="$(node -p "process.versions.node.split('.')[0]" 2>/dev/null || echo 0)"
  [[ "${NODE_MAJOR}" -ge 18 ]] || fatal "Node.js 18+ is required, current version is too low"
}

configure_database_service() {
  if systemctl list-unit-files | grep -q '^mysql.service'; then
    DB_SERVICE="mysql"
  elif systemctl list-unit-files | grep -q '^mysqld.service'; then
    DB_SERVICE="mysqld"
  elif systemctl list-unit-files | grep -q '^mariadb.service'; then
    DB_SERVICE="mariadb"
  else
    fatal "MySQL or MariaDB service was not found"
  fi

  systemctl enable --now "${DB_SERVICE}"
}

detect_mysql_client() {
  MYSQL_BIN="$(command_exists_any mysql mariadb || true)"
  [[ -n "${MYSQL_BIN}" ]] || fatal "mysql/mariadb client was not found"
}

configure_database() {
  "${MYSQL_BIN}" <<SQL
CREATE DATABASE IF NOT EXISTS \`${DB_NAME}\` DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS '${DB_USER}'@'127.0.0.1' IDENTIFIED BY '${DB_PASSWORD}';
CREATE USER IF NOT EXISTS '${DB_USER}'@'localhost' IDENTIFIED BY '${DB_PASSWORD}';
GRANT ALL PRIVILEGES ON \`${DB_NAME}\`.* TO '${DB_USER}'@'127.0.0.1';
GRANT ALL PRIVILEGES ON \`${DB_NAME}\`.* TO '${DB_USER}'@'localhost';
FLUSH PRIVILEGES;
SQL
}

build_allowed_hosts() {
  if [[ -n "${DJANGO_ALLOWED_HOSTS}" ]]; then
    printf '%s' "${DJANGO_ALLOWED_HOSTS}"
    return
  fi

  local hosts=()
  [[ -n "${DOMAIN}" ]] && hosts+=("${DOMAIN}")
  [[ -n "${SERVER_IP}" ]] && hosts+=("${SERVER_IP}")
  hosts+=("127.0.0.1" "localhost")

  local joined=""
  local host
  for host in "${hosts[@]}"; do
    [[ -n "${joined}" ]] && joined+=","
    joined+="${host}"
  done
  printf '%s' "${joined}"
}

build_cors_origins() {
  if [[ -n "${DJANGO_CORS_ALLOWED_ORIGINS}" ]]; then
    printf '%s' "${DJANGO_CORS_ALLOWED_ORIGINS}"
    return
  fi

  local origins=()
  [[ -n "${DOMAIN}" ]] && origins+=("http://${DOMAIN}" "https://${DOMAIN}")
  [[ -n "${SERVER_IP}" ]] && origins+=("http://${SERVER_IP}")
  origins+=("http://127.0.0.1" "http://localhost")

  local joined=""
  local origin
  for origin in "${origins[@]}"; do
    [[ -n "${joined}" ]] && joined+=","
    joined+="${origin}"
  done
  printf '%s' "${joined}"
}

write_backend_env() {
  local allowed_hosts cors_origins
  allowed_hosts="$(build_allowed_hosts)"
  cors_origins="$(build_cors_origins)"

  cat > "${BACKEND_ENV_FILE}" <<EOF
DJANGO_SECRET_KEY=${DJANGO_SECRET_KEY}
DJANGO_DEBUG=${DJANGO_DEBUG}
DJANGO_ALLOWED_HOSTS=${allowed_hosts}
DJANGO_CORS_ALLOWED_ORIGINS=${cors_origins}

DB_NAME=${DB_NAME}
DB_USER=${DB_USER}
DB_PASSWORD=${DB_PASSWORD}
DB_HOST=${DB_HOST}
DB_PORT=${DB_PORT}
DB_MYSQL57_COMPAT=${DB_MYSQL57_COMPAT}

DEFAULT_ADMIN_USERNAME=${DEFAULT_ADMIN_USERNAME}
DEFAULT_ADMIN_PASSWORD=${DEFAULT_ADMIN_PASSWORD}
DEFAULT_ADMIN_EMAIL=${DEFAULT_ADMIN_EMAIL}
AUTH_TOKEN_TTL_SECONDS=${AUTH_TOKEN_TTL_SECONDS}

AI_BASE_URL=${AI_BASE_URL}
AI_API_KEY=${AI_API_KEY}
AI_MODEL=${AI_MODEL}
AI_TIMEOUT_SECONDS=${AI_TIMEOUT_SECONDS}
EOF

  chown "${RUN_USER}:${RUN_GROUP}" "${BACKEND_ENV_FILE}"
}

configure_language_mirrors() {
  if is_offline_mode; then
    log "Offline mode: skip pip/npm mirror configuration"
    return
  fi

  ensure_host_resolvable "$(extract_host_from_url "${PIP_INDEX_URL}")" "pip index"
  ensure_host_resolvable "$(extract_host_from_url "${NPM_REGISTRY}")" "npm registry"

  cat > /etc/pip.conf <<EOF
[global]
index-url = ${PIP_INDEX_URL}
trusted-host = ${PIP_TRUSTED_HOST}
timeout = 120
disable-pip-version-check = true
EOF

  run_as_app "npm config set registry '${NPM_REGISTRY}'"
  run_as_app "npm config set fetch-retries 5"
  run_as_app "npm config set fetch-retry-factor 2"
  run_as_app "npm config set fetch-retry-mintimeout 20000"
  run_as_app "npm config set fetch-retry-maxtimeout 120000"
}

setup_backend() {
  run_as_app "cd '${BACKEND_DIR}' && ${PYTHON_BIN} -m venv .venv"

  if is_offline_mode; then
    has_matching_files "${OFFLINE_PYTHON_WHEEL_DIR}" "*.whl" || fatal "Offline mode requires Python wheels under ${OFFLINE_PYTHON_WHEEL_DIR}"
    retry_cmd 3 5 run_as_app "cd '${BACKEND_DIR}' && . .venv/bin/activate && pip install --no-index --find-links='${OFFLINE_PYTHON_WHEEL_DIR}' -r requirements.txt gunicorn"
    run_as_app "cd '${BACKEND_DIR}' && . .venv/bin/activate && python manage.py migrate"
    run_as_app "cd '${BACKEND_DIR}' && . .venv/bin/activate && python manage.py check"
    return
  fi

  retry_cmd 3 5 run_as_app "cd '${BACKEND_DIR}' && . .venv/bin/activate && PIP_INDEX_URL='${PIP_INDEX_URL}' pip install -U pip setuptools wheel"
  retry_cmd 3 5 run_as_app "cd '${BACKEND_DIR}' && . .venv/bin/activate && PIP_INDEX_URL='${PIP_INDEX_URL}' pip install -r requirements.txt gunicorn"
  run_as_app "cd '${BACKEND_DIR}' && . .venv/bin/activate && python manage.py migrate"
  run_as_app "cd '${BACKEND_DIR}' && . .venv/bin/activate && python manage.py check"
}

write_frontend_env() {
  cat > "${FRONTEND_ENV_FILE}" <<EOF
VITE_API_BASE_URL=/api
EOF
  chown "${RUN_USER}:${RUN_GROUP}" "${FRONTEND_ENV_FILE}"
}

build_frontend() {
  if is_offline_mode; then
    local temp_dir=""
    local source_dir=""

    rm -rf "${FRONTEND_DIR}/dist"
    mkdir -p "${FRONTEND_DIR}/dist"

    if [[ -f "${OFFLINE_FRONTEND_DIST_ARCHIVE}" || -f "${OFFLINE_FRONTEND_DIST_TGZ}" ]]; then
      local archive_path="${OFFLINE_FRONTEND_DIST_ARCHIVE}"
      if [[ ! -f "${archive_path}" ]]; then
        archive_path="${OFFLINE_FRONTEND_DIST_TGZ}"
      fi
      temp_dir="$(mktemp -d)"
      tar -xzf "${archive_path}" -C "${temp_dir}"
      if [[ -f "${temp_dir}/index.html" ]]; then
        source_dir="${temp_dir}"
      elif [[ -f "${temp_dir}/dist/index.html" ]]; then
        source_dir="${temp_dir}/dist"
      else
        rm -rf "${temp_dir}"
        fatal "Frontend dist archive must contain index.html at root or under dist/"
      fi
      cp -a "${source_dir}/." "${FRONTEND_DIR}/dist/"
      rm -rf "${temp_dir}"
    elif [[ -f "${OFFLINE_FRONTEND_DIST_DIR}/index.html" ]]; then
      cp -a "${OFFLINE_FRONTEND_DIST_DIR}/." "${FRONTEND_DIR}/dist/"
    else
      fatal "Offline mode requires ${OFFLINE_FRONTEND_DIST_ARCHIVE} or ${OFFLINE_FRONTEND_DIST_DIR}/index.html"
    fi

    chown -R "${RUN_USER}:${RUN_GROUP}" "${FRONTEND_DIR}/dist"
    return
  fi

  retry_cmd 3 5 run_as_app "cd '${FRONTEND_DIR}' && npm install --registry '${NPM_REGISTRY}'"
  run_as_app "cd '${FRONTEND_DIR}' && npm run build"
}

write_systemd_service() {
  cat > "/etc/systemd/system/${SYSTEMD_SERVICE}.service" <<EOF
[Unit]
Description=${APP_NAME} Django Backend
After=network.target ${DB_SERVICE}.service

[Service]
User=${RUN_USER}
Group=${RUN_GROUP}
WorkingDirectory=${BACKEND_DIR}
Environment="PATH=${BACKEND_DIR}/.venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin"
ExecStart=${BACKEND_DIR}/.venv/bin/gunicorn config.wsgi:application --bind ${BACKEND_BIND} --workers ${GUNICORN_WORKERS} --timeout ${GUNICORN_TIMEOUT}
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

  systemctl daemon-reload
  systemctl enable --now "${SYSTEMD_SERVICE}"
}

write_nginx_config() {
  local nginx_conf
  nginx_conf="server {
    listen 80;
    server_name ${SERVER_NAME};
    client_max_body_size 1g;

    root ${FRONTEND_DIR}/dist;
    index index.html;

    location / {
        try_files \$uri \$uri/ /index.html;
    }

    location /api/ {
        proxy_pass http://${BACKEND_BIND};
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_connect_timeout 60s;
        proxy_read_timeout 900s;
        proxy_send_timeout 900s;
        send_timeout 900s;
    }
}"

  if [[ -d /etc/nginx/sites-available && -d /etc/nginx/sites-enabled ]]; then
    printf '%s\n' "${nginx_conf}" > "/etc/nginx/sites-available/${NGINX_SITE_NAME}"
    ln -sf "/etc/nginx/sites-available/${NGINX_SITE_NAME}" "/etc/nginx/sites-enabled/${NGINX_SITE_NAME}"
    [[ -L /etc/nginx/sites-enabled/default ]] && rm -f /etc/nginx/sites-enabled/default
  else
    printf '%s\n' "${nginx_conf}" > "/etc/nginx/conf.d/${NGINX_SITE_NAME}.conf"
  fi

  nginx -t
  systemctl enable --now nginx
  systemctl restart nginx
}

open_firewall() {
  if command -v ufw >/dev/null 2>&1 && ufw status | grep -q "Status: active"; then
    ufw allow 80/tcp || true
    ufw allow 443/tcp || true
  fi

  if command -v firewall-cmd >/dev/null 2>&1 && systemctl is-active --quiet firewalld; then
    firewall-cmd --permanent --add-service=http || true
    firewall-cmd --permanent --add-service=https || true
    firewall-cmd --reload || true
  fi
}

print_summary() {
  log "Deployment completed"
  printf '\nFrontend URL: http://%s\n' "${DOMAIN:-${SERVER_IP:-server-ip}}"
  printf 'Backend health: http://127.0.0.1:%s/api/health\n' "${BACKEND_BIND_PORT}"
  printf 'Systemd service: %s\n' "${SYSTEMD_SERVICE}"
  if [[ -d /etc/nginx/sites-available ]]; then
    printf 'Nginx config: %s\n' "/etc/nginx/sites-available/${NGINX_SITE_NAME}"
  else
    printf 'Nginx config: %s\n' "/etc/nginx/conf.d/${NGINX_SITE_NAME}.conf"
  fi
  printf 'Admin user: %s\n' "${DEFAULT_ADMIN_USERNAME}"
}

main() {
  ensure_root "$@"

  [[ -f "${BACKEND_DIR}/manage.py" ]] || fatal "backend directory was not found under ${PROJECT_ROOT}"
  [[ -f "${FRONTEND_DIR}/package.json" ]] || fatal "frontend directory was not found under ${PROJECT_ROOT}"

  load_os_release
  detect_pkg_manager
  if is_offline_mode; then
    log "Offline mode is enabled, local assets root: ${OFFLINE_DIR}"
  fi
  configure_system_mirrors

  log "Installing system packages"
  install_base_packages

  log "Ensuring Python and Node.js"
  ensure_python
  ensure_nodejs

  log "Starting database service"
  configure_database_service

  log "Configuring database"
  detect_mysql_client
  configure_database

  log "Configuring pip/npm mirrors"
  configure_language_mirrors

  log "Writing backend environment"
  write_backend_env

  log "Deploying backend"
  setup_backend

  log "Writing frontend production environment"
  write_frontend_env

  log "Building frontend"
  build_frontend

  log "Writing systemd service"
  write_systemd_service

  log "Writing Nginx config"
  write_nginx_config

  log "Opening firewall ports"
  open_firewall

  print_summary
}

main "$@"
