#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUTPUT_FILE="${OUTPUT_FILE:-${PROJECT_ROOT}/deploy/offline/target-profile.env}"

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

bool_text() {
  if "$@" >/dev/null 2>&1; then
    printf 'true'
  else
    printf 'false'
  fi
}

detect_package_manager() {
  if command -v apt-get >/dev/null 2>&1; then
    printf 'apt'
    return
  fi
  if command -v dnf >/dev/null 2>&1; then
    printf 'dnf'
    return
  fi
  if command -v yum >/dev/null 2>&1; then
    printf 'yum'
    return
  fi
  printf 'unknown'
}

detect_python_38_plus() {
  local py=""
  py="$(command_exists_any python3.11 python3.10 python3.9 python3.8 python3 || true)"
  [[ -n "${py}" ]] || return 1
  "${py}" - <<'PY' >/dev/null 2>&1
import sys
raise SystemExit(0 if sys.version_info >= (3, 8) else 1)
PY
}

detect_db_service() {
  if command -v systemctl >/dev/null 2>&1; then
    systemctl list-unit-files 2>/dev/null | grep -Eq '^(mysql|mysqld|mariadb)\.service'
    return $?
  fi
  return 1
}

main() {
  [[ -f /etc/os-release ]] || { echo "/etc/os-release was not found" >&2; exit 1; }
  # shellcheck disable=SC1091
  . /etc/os-release

  mkdir -p "$(dirname "${OUTPUT_FILE}")"

  cat > "${OUTPUT_FILE}" <<EOF
TARGET_OS_ID=${ID:-linux}
TARGET_OS_VERSION_ID=${VERSION_ID:-unknown}
TARGET_PACKAGE_MANAGER=$(detect_package_manager)
TARGET_ARCH=$(uname -m)
TARGET_HAS_PYTHON38_PLUS=$(bool_text detect_python_38_plus)
TARGET_HAS_NGINX=$(bool_text command -v nginx)
TARGET_HAS_MYSQL_CLIENT=$(bool_text command_exists_any mysql mariadb)
TARGET_HAS_DB_SERVICE=$(bool_text detect_db_service)
# Optional for yum family when Python 3.8+ is missing:
TARGET_PYTHON_PACKAGE_HINTS=
EOF

  printf 'Target profile written to: %s\n' "${OUTPUT_FILE}"
}

main "$@"
