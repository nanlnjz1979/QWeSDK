#!/bin/sh
set -eu

echo "[qwesdk] 检查本地 SDK 包..."
mkdir -p "${HOME:-/tmp/qwe-home}"
python /app/qwesdk_entrypoint.py

if [ "$(id -u)" = "0" ]; then
  echo "[qwesdk] 禁止以 root 用户启动 Worker" >&2
  exit 1
fi

echo "[qwesdk] Worker 以非 root 用户 $(id -u) 启动"

echo "[qwesdk] 启动 Celery Worker..."
exec celery -A celery_app worker \
  --loglevel="${CELERY_LOGLEVEL:-INFO}" \
  --pool="${CELERY_POOL:-prefork}" \
  --concurrency="${CELERY_CONCURRENCY:-2}"
