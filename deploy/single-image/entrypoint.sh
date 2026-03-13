#!/usr/bin/env bash
set -Eeuo pipefail

APP_DIR="${APP_DIR:-/app/backend}"
APP_HOST="${APP_HOST:-127.0.0.1}"
APP_PORT="${APP_PORT:-8000}"
DB_HOST="${DB_HOST:-db}"
DB_PORT="${DB_PORT:-3306}"
GUNICORN_WORKERS="${GUNICORN_WORKERS:-3}"
GUNICORN_TIMEOUT="${GUNICORN_TIMEOUT:-900}"
DJANGO_COLLECTSTATIC="${DJANGO_COLLECTSTATIC:-1}"
WAIT_FOR_DB="${WAIT_FOR_DB:-1}"

term_handler() {
  if [[ -n "${gunicorn_pid:-}" ]]; then
    kill -TERM "${gunicorn_pid}" 2>/dev/null || true
  fi
  if [[ -n "${nginx_pid:-}" ]]; then
    kill -TERM "${nginx_pid}" 2>/dev/null || true
  fi
  wait || true
}

trap term_handler INT TERM

cd "${APP_DIR}"
mkdir -p "${APP_DIR}/storage" "${APP_DIR}/staticfiles" /run/nginx

if [[ "${WAIT_FOR_DB}" == "1" ]]; then
  echo "[single-image] waiting for database ${DB_HOST}:${DB_PORT} ..."
  python - <<'PY'
import os
import socket
import sys
import time

host = os.getenv("DB_HOST", "db")
port = int(os.getenv("DB_PORT", "3306"))

for attempt in range(60):
    try:
        with socket.create_connection((host, port), timeout=3):
            print(f"[single-image] database is ready: {host}:{port}")
            break
    except OSError as exc:
        print(f"[single-image] waiting for database ({attempt + 1}/60): {exc}")
        time.sleep(2)
else:
    print("[single-image] database connection timed out", file=sys.stderr)
    sys.exit(1)
PY
fi

python manage.py migrate --noinput

if [[ "${DJANGO_COLLECTSTATIC}" == "1" ]]; then
  python manage.py collectstatic --noinput
fi

gunicorn config.wsgi:application \
  --bind "${APP_HOST}:${APP_PORT}" \
  --workers "${GUNICORN_WORKERS}" \
  --timeout "${GUNICORN_TIMEOUT}" &
gunicorn_pid=$!

nginx -g 'daemon off;' &
nginx_pid=$!

while true; do
  if ! kill -0 "${gunicorn_pid}" 2>/dev/null; then
    wait "${gunicorn_pid}" || true
    kill -TERM "${nginx_pid}" 2>/dev/null || true
    wait "${nginx_pid}" || true
    exit 1
  fi

  if ! kill -0 "${nginx_pid}" 2>/dev/null; then
    wait "${nginx_pid}" || true
    kill -TERM "${gunicorn_pid}" 2>/dev/null || true
    wait "${gunicorn_pid}" || true
    exit 1
  fi

  sleep 2
done
