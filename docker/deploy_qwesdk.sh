#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
CONFIG_FILE=${QWESDK_CONFIG_FILE:-"$SCRIPT_DIR/qwesdk-runtime.env"}
COMPOSE_FILE="$SCRIPT_DIR/docker-compose.runtime.yml"
ACTION=${1:-up}

if [ ! -f "$CONFIG_FILE" ]; then
  echo "配置文件不存在: $CONFIG_FILE" >&2
  exit 1
fi

set -a
. "$CONFIG_FILE"
set +a

QWESDK_IMAGE=${QWESDK_IMAGE:-qwesdk:1.0.5}
QWESDK_PACKAGE_PATH=${QWESDK_PACKAGE_PATH:-../dist}

cd "$SCRIPT_DIR"

compose() {
  docker compose --env-file "$CONFIG_FILE" -f "$COMPOSE_FILE" "$@"
}

pull_or_use_local() {
  image=$1
  echo "[qwesdk] 拉取镜像: $image"
  if docker pull "$image"; then
    return 0
  fi
  if docker image inspect "$image" >/dev/null 2>&1; then
    echo "[qwesdk] 远程拉取失败，继续使用本地镜像: $image"
    return 0
  fi
  echo "[qwesdk] 镜像不存在且拉取失败: $image" >&2
  return 1
}

case "$ACTION" in
  up)
    mkdir -p "$QWESDK_PACKAGE_PATH"
    pull_or_use_local "$QWESDK_IMAGE"
    echo "[qwesdk] SDK 包目录: $SCRIPT_DIR/$QWESDK_PACKAGE_PATH"
    echo "[qwesdk] Redis Broker: ${CELERY_BROKER_URL:-redis://host.docker.internal:6379/0}"
    compose up -d --pull never qwesdk
    compose ps
    ;;
  upgrade)
    mkdir -p "$QWESDK_PACKAGE_PATH"
    pull_or_use_local "$QWESDK_IMAGE"
    compose up -d --pull never --force-recreate qwesdk
    compose ps
    ;;
  restart)
    compose restart qwesdk
    compose ps
    ;;
  status)
    compose ps
    ;;
  logs)
    compose logs -f qwesdk
    ;;
  down)
    compose down
    ;;
  *)
    echo "用法: $0 {up|upgrade|restart|status|logs|down}" >&2
    exit 2
    ;;
esac
