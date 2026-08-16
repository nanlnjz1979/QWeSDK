#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
COMPOSE_FILE="$SCRIPT_DIR/docker-compose.yml"

cd "$SCRIPT_DIR"

echo "[qwesdk] 构建镜像..."
docker compose -f "$COMPOSE_FILE" build celery

echo "[qwesdk] 启动 Celery（Redis 由外部单独管理）..."
docker compose -f "$COMPOSE_FILE" up -d celery

echo "[qwesdk] 当前状态："
docker compose -f "$COMPOSE_FILE" ps

echo "[qwesdk] 查看实时日志："
echo "docker compose -f \"$COMPOSE_FILE\" logs -f celery"
