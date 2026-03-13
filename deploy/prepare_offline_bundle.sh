#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OFFLINE_DIR="${OFFLINE_DIR:-${PROJECT_ROOT}/deploy/offline}"
OFFLINE_OS_PACKAGE_DIR="${OFFLINE_OS_PACKAGE_DIR:-${OFFLINE_DIR}/os-packages}"
OFFLINE_PYTHON_WHEEL_DIR="${OFFLINE_PYTHON_WHEEL_DIR:-${OFFLINE_DIR}/python}"
OFFLINE_FRONTEND_DIST_ARCHIVE="${OFFLINE_FRONTEND_DIST_ARCHIVE:-${OFFLINE_DIR}/frontend-dist.tar.gz}"
TARGET_PROFILE_FILE="${TARGET_PROFILE_FILE:-${OFFLINE_DIR}/target-profile.env}"
SKIP_OS_PACKAGES="${SKIP_OS_PACKAGES:-false}"

PYTHON_BIN="${PYTHON_BIN:-}"
PACKAGE_MANAGER=""
OS_ID=""
OS_VERSION_ID=""
TARGET_OS_ID=""
TARGET_OS_VERSION_ID=""
TARGET_PACKAGE_MANAGER=""
TARGET_ARCH=""
TARGET_HAS_PYTHON38_PLUS=""
TARGET_HAS_NGINX=""
TARGET_HAS_MYSQL_CLIENT=""
TARGET_HAS_DB_SERVICE=""
TARGET_PYTHON_PACKAGE_HINTS=""

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

ensure_dirs() {
  mkdir -p "${OFFLINE_OS_PACKAGE_DIR}" "${OFFLINE_PYTHON_WHEEL_DIR}" "${OFFLINE_DIR}"
}

detect_os() {
  [[ -f /etc/os-release ]] || fatal "/etc/os-release was not found"
  # shellcheck disable=SC1091
  . /etc/os-release
  OS_ID="${ID:-linux}"
  OS_VERSION_ID="${VERSION_ID:-unknown}"

  if command -v apt-get >/dev/null 2>&1; then
    PACKAGE_MANAGER="apt"
  elif command -v dnf >/dev/null 2>&1; then
    PACKAGE_MANAGER="dnf"
  elif command -v yum >/dev/null 2>&1; then
    PACKAGE_MANAGER="yum"
  else
    fatal "Unsupported package manager"
  fi
}

load_target_profile() {
  if [[ ! -f "${TARGET_PROFILE_FILE}" ]]; then
    TARGET_OS_ID="${OS_ID}"
    TARGET_OS_VERSION_ID="${OS_VERSION_ID}"
    TARGET_PACKAGE_MANAGER="${PACKAGE_MANAGER}"
    TARGET_ARCH="$(uname -m)"
    return
  fi

  # shellcheck disable=SC1090
  . "${TARGET_PROFILE_FILE}"

  TARGET_OS_ID="${TARGET_OS_ID:-${OS_ID}}"
  TARGET_OS_VERSION_ID="${TARGET_OS_VERSION_ID:-${OS_VERSION_ID}}"
  TARGET_PACKAGE_MANAGER="${TARGET_PACKAGE_MANAGER:-${PACKAGE_MANAGER}}"
  TARGET_ARCH="${TARGET_ARCH:-$(uname -m)}"
  TARGET_HAS_PYTHON38_PLUS="${TARGET_HAS_PYTHON38_PLUS:-}"
  TARGET_HAS_NGINX="${TARGET_HAS_NGINX:-}"
  TARGET_HAS_MYSQL_CLIENT="${TARGET_HAS_MYSQL_CLIENT:-}"
  TARGET_HAS_DB_SERVICE="${TARGET_HAS_DB_SERVICE:-}"
  TARGET_PYTHON_PACKAGE_HINTS="${TARGET_PYTHON_PACKAGE_HINTS:-}"
}

validate_target_context() {
  if [[ "${TARGET_PACKAGE_MANAGER}" != "${PACKAGE_MANAGER}" ]]; then
    if is_true "${SKIP_OS_PACKAGES}"; then
      log "Target package manager is ${TARGET_PACKAGE_MANAGER}, current machine is ${PACKAGE_MANAGER}; skip OS package download"
      return
    fi
    fatal "Target package manager is ${TARGET_PACKAGE_MANAGER}, but current preparation machine is ${PACKAGE_MANAGER}. Prepare OS packages on the same package-manager family machine, or rerun with SKIP_OS_PACKAGES=true to only build wheels and frontend dist."
  fi
}

select_python() {
  if [[ -n "${PYTHON_BIN}" ]]; then
    command -v "${PYTHON_BIN}" >/dev/null 2>&1 || fatal "PYTHON_BIN not found: ${PYTHON_BIN}"
    return
  fi
  PYTHON_BIN="$(command_exists_any python3.11 python3.10 python3.9 python3.8 python3 || true)"
  [[ -n "${PYTHON_BIN}" ]] || fatal "Python 3.8+ is required on the online preparation machine"
}

download_python_wheels() {
  log "Downloading Python wheels with ${PYTHON_BIN}"
  "${PYTHON_BIN}" -m pip download -r "${PROJECT_ROOT}/backend/requirements.txt" -d "${OFFLINE_PYTHON_WHEEL_DIR}"
  "${PYTHON_BIN}" -m pip download gunicorn -d "${OFFLINE_PYTHON_WHEEL_DIR}"
}

build_frontend_dist() {
  command -v npm >/dev/null 2>&1 || fatal "npm is required to build frontend dist"

  log "Building frontend dist"
  (
    cd "${PROJECT_ROOT}/frontend"
    npm install
    npm run build
    tar -czf "${OFFLINE_FRONTEND_DIST_ARCHIVE}" -C dist .
  )
}

print_package_if_missing() {
  local package_name="$1"
  local exists_flag="$2"
  if [[ "${exists_flag}" != "true" ]]; then
    printf '%s\n' "${package_name}"
  fi
}

build_default_system_packages() {
  local packages=()

  case "${TARGET_PACKAGE_MANAGER}" in
    apt)
      while IFS= read -r item; do [[ -n "${item}" ]] && packages+=("${item}"); done < <(print_package_if_missing "nginx" "${TARGET_HAS_NGINX}")
      if [[ "${TARGET_HAS_DB_SERVICE}" != "true" || "${TARGET_HAS_MYSQL_CLIENT}" != "true" ]]; then
        packages+=("mysql-server")
      fi
      if [[ "${TARGET_HAS_PYTHON38_PLUS}" != "true" ]]; then
        packages+=("python3" "python3-venv" "python3-pip")
      fi
      ;;
    dnf)
      while IFS= read -r item; do [[ -n "${item}" ]] && packages+=("${item}"); done < <(print_package_if_missing "nginx" "${TARGET_HAS_NGINX}")
      if [[ "${TARGET_HAS_DB_SERVICE}" != "true" || "${TARGET_HAS_MYSQL_CLIENT}" != "true" ]]; then
        packages+=("mariadb-server" "mariadb")
      fi
      if [[ "${TARGET_HAS_PYTHON38_PLUS}" != "true" ]]; then
        packages+=("python3" "python3-pip")
      fi
      ;;
    yum)
      while IFS= read -r item; do [[ -n "${item}" ]] && packages+=("${item}"); done < <(print_package_if_missing "nginx" "${TARGET_HAS_NGINX}")
      if [[ "${TARGET_HAS_DB_SERVICE}" != "true" || "${TARGET_HAS_MYSQL_CLIENT}" != "true" ]]; then
        packages+=("mariadb-server" "mariadb")
      fi
      if [[ "${TARGET_HAS_PYTHON38_PLUS}" != "true" ]]; then
        if [[ -n "${TARGET_PYTHON_PACKAGE_HINTS}" ]]; then
          read -r -a hinted <<<"${TARGET_PYTHON_PACKAGE_HINTS}"
          packages+=("${hinted[@]}")
        else
          fatal "Target lacks Python 3.8+, but yum family package names are repo-dependent. Set TARGET_PYTHON_PACKAGE_HINTS in ${TARGET_PROFILE_FILE} or pass SYSTEM_PACKAGES manually."
        fi
      fi
      ;;
  esac

  printf '%s\n' "${packages[@]}" | awk 'NF' | sort -u
}

download_os_packages_apt() {
  local packages=("$@")
  ((${#packages[@]} > 0)) || return 0

  log "Installing apt download helpers"
  apt-get update
  apt-get install -y apt-rdepends

  local pkg=""
  local all_packages=()
  for pkg in "${packages[@]}"; do
    all_packages+=("${pkg}")
    while IFS= read -r dep; do
      [[ -n "${dep}" ]] || continue
      all_packages+=("${dep}")
    done < <(apt-rdepends "${pkg}" 2>/dev/null | grep -v '^ ' | grep -Ev '^(PreDepends|Depends):' || true)
  done

  mapfile -t all_packages < <(printf '%s\n' "${all_packages[@]}" | awk 'NF' | sort -u)
  ((${#all_packages[@]} > 0)) || return 0

  log "Downloading apt packages"
  (
    cd "${OFFLINE_OS_PACKAGE_DIR}"
    apt-get download "${all_packages[@]}"
  )
}

download_os_packages_dnf() {
  local packages=("$@")
  ((${#packages[@]} > 0)) || return 0

  log "Installing dnf download plugin"
  dnf install -y 'dnf-command(download)'
  dnf download --resolve --alldeps --destdir "${OFFLINE_OS_PACKAGE_DIR}" "${packages[@]}"
}

download_os_packages_yum() {
  local packages=("$@")
  ((${#packages[@]} > 0)) || return 0

  log "Installing yumdownloader helper"
  yum install -y yum-utils
  yumdownloader --resolve --destdir "${OFFLINE_OS_PACKAGE_DIR}" "${packages[@]}"
}

download_os_packages() {
  if is_true "${SKIP_OS_PACKAGES}"; then
    log "SKIP_OS_PACKAGES=true, skip OS package download"
    return
  fi

  local package_list="${SYSTEM_PACKAGES:-}"
  if [[ -z "${package_list}" ]]; then
    package_list="$(build_default_system_packages | xargs || true)"
  fi

  if [[ -z "${package_list}" ]]; then
    log "No OS packages need to be downloaded based on the target profile"
    return
  fi

  read -r -a packages <<<"${package_list}"
  if ((${#packages[@]} == 0)); then
    log "SYSTEM_PACKAGES is empty, skip OS package download"
    return
  fi

  log "Downloading OS packages for target ${TARGET_OS_ID} ${TARGET_OS_VERSION_ID} (${TARGET_PACKAGE_MANAGER}): ${package_list}"
  case "${PACKAGE_MANAGER}" in
    apt)
      download_os_packages_apt "${packages[@]}"
      ;;
    dnf)
      download_os_packages_dnf "${packages[@]}"
      ;;
    yum)
      download_os_packages_yum "${packages[@]}"
      ;;
  esac
}

print_summary() {
  printf '\nTarget profile: %s\n' "${TARGET_PROFILE_FILE}"
  printf 'Target OS: %s %s (%s, %s)\n' "${TARGET_OS_ID}" "${TARGET_OS_VERSION_ID}" "${TARGET_PACKAGE_MANAGER}" "${TARGET_ARCH}"
  printf 'Offline assets prepared under: %s\n' "${OFFLINE_DIR}"
  printf 'OS packages: %s\n' "${OFFLINE_OS_PACKAGE_DIR}"
  printf 'Python wheels: %s\n' "${OFFLINE_PYTHON_WHEEL_DIR}"
  printf 'Frontend archive: %s\n' "${OFFLINE_FRONTEND_DIST_ARCHIVE}"
}

main() {
  ensure_dirs
  detect_os
  load_target_profile
  validate_target_context
  select_python
  download_os_packages
  download_python_wheels
  build_frontend_dist
  print_summary
}

main "$@"
