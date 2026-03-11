#!/usr/bin/env sh
set -eu

echo "[backend] waiting for database ${DB_HOST:-db}:${DB_PORT:-3306} ..."
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
            print(f"[backend] database is ready: {host}:{port}")
            break
    except OSError as exc:
        print(f"[backend] waiting for database ({attempt + 1}/60): {exc}")
        time.sleep(2)
else:
    print("[backend] database connection timed out", file=sys.stderr)
    sys.exit(1)
PY

python manage.py migrate --noinput

if [ "${DJANGO_COLLECTSTATIC:-1}" = "1" ]; then
  python manage.py collectstatic --noinput
fi

exec gunicorn config.wsgi:application \
  --bind 0.0.0.0:8000 \
  --workers "${GUNICORN_WORKERS:-3}" \
  --timeout "${GUNICORN_TIMEOUT:-900}"
