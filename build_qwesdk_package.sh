#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PYTHON_BIN=${PYTHON_BIN:-python3}
OUTPUT_DIR=${OUTPUT_DIR:-"$SCRIPT_DIR/dist"}

cd "$SCRIPT_DIR"

python_version=$($PYTHON_BIN -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
python_ok=$($PYTHON_BIN -c 'import sys; print(int(sys.version_info >= (3, 10)))')
if [ "$python_ok" != "1" ]; then
  if [ "${QWESDK_BUILD_IN_CONTAINER:-0}" = "1" ]; then
    echo "容器内仍需要 Python >= 3.10，当前为 ${python_version}" >&2
    exit 1
  fi
  if ! command -v docker >/dev/null 2>&1; then
    echo "本机 Python 为 ${python_version}，且未找到 Docker。" >&2
    echo "请安装 Python 3.10+，或安装 Docker 后重新执行本脚本。" >&2
    exit 1
  fi

  echo "本机 Python 为 ${python_version}，自动使用 qwesdk:1.0.3 中的 Python 3.11 打包..."
  exec docker run --rm \
    --entrypoint sh \
    --user "$(id -u):$(id -g)" \
    --env HOME=/tmp \
    --env QWESDK_BUILD_IN_CONTAINER=1 \
    --env PYTHON_BIN=python \
    --env OUTPUT_DIR=/src/dist \
    --volume "$SCRIPT_DIR:/src" \
    --workdir /src \
    qwesdk:1.0.3 \
    -lc './build_qwesdk_package.sh'
fi

if ! $PYTHON_BIN -m build --version >/dev/null 2>&1; then
  echo "缺少 build 模块，请先执行：$PYTHON_BIN -m pip install build" >&2
  exit 1
fi

mkdir -p "$OUTPUT_DIR"
echo "使用 Python ${python_version} 打包 QWeSDK..."
$PYTHON_BIN -m build --sdist --wheel --outdir "$OUTPUT_DIR"

$PYTHON_BIN - "$OUTPUT_DIR" <<'PY'
import sys
import zipfile
from pathlib import Path

output_dir = Path(sys.argv[1])
wheels = sorted(output_dir.glob("qwesdk-*.whl"), key=lambda p: p.stat().st_mtime)
if not wheels:
    raise SystemExit("未生成 wheel 文件")

wheel = wheels[-1]
with zipfile.ZipFile(wheel) as archive:
    names = set(archive.namelist())
required = {"m/__init__.py", "m/config/config.json"}
missing = sorted(required - names)
if missing:
    raise SystemExit(f"wheel 缺少文件: {', '.join(missing)}")

print(f"打包完成: {wheel}")
print("已验证 m/__init__.py 和 m/config/config.json 已包含在 wheel 中")
PY
