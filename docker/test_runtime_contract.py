import re
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
START_SCRIPT = ROOT / "docker" / "worker" / "start_qwesdk.sh"
COMPOSE_FILE = ROOT / "docker" / "docker-compose.runtime.yml"
APP_DOCKERFILE = ROOT / "docker" / "worker" / "Dockerfile"
GATEWAY_REQUIREMENTS = ROOT / "gateway" / "requirements.txt"


def test_worker_startup_consumes_backtest_queue():
    script = START_SCRIPT.read_text(encoding="utf-8")
    runtime_env = (ROOT / "docker" / "qwesdk-runtime.env").read_text(encoding="utf-8")

    assert '--queues="${CELERY_QUEUES:-celery}"' in script
    assert "CELERY_QUEUES=backtest" in runtime_env
    assert "QWESDK_IMAGE=qwesdk:1.0.5" in runtime_env


def test_runtime_does_not_mount_a_local_dataset_root():
    compose = COMPOSE_FILE.read_text(encoding="utf-8")

    assert "QWESDK_DATA_ROOT" not in compose
    assert "QWESDK_DATA_PATH" not in compose
    assert "/data/qwesdk" not in compose


def test_worker_receives_clickhouse_connection_settings_without_baking_credentials():
    compose = COMPOSE_FILE.read_text(encoding="utf-8")
    worker = compose[compose.index("  qwesdk:"):]

    assert "QWESDK_CLICKHOUSE_URL: ${QWESDK_CLICKHOUSE_URL:-}" in worker
    assert "QWESDK_CLICKHOUSE_USER: ${QWESDK_CLICKHOUSE_USER:-default}" in worker
    assert "QWESDK_CLICKHOUSE_PASSWORD: ${QWESDK_CLICKHOUSE_PASSWORD:-}" in worker


def test_gateway_data_volume_is_initialized_for_non_root_gateway():
    compose = COMPOSE_FILE.read_text(encoding="utf-8")

    assert "gateway-data-init:" in compose
    assert "chown -R 10001:10001 /var/lib/helix-gateway" in compose
    assert "condition: service_completed_successfully" in compose


def test_worker_image_loads_runtime_modules_from_the_sdk_wheel():
    dockerfile = APP_DOCKERFILE.read_text(encoding="utf-8")

    assert "COPY docker/worker/qwesdk_entrypoint.py docker/worker/start_qwesdk.sh" in dockerfile
    assert "COPY docker/app" not in dockerfile


def test_gateway_declares_dataset_catalog_runtime_dependency():
    requirements = GATEWAY_REQUIREMENTS.read_text(encoding="utf-8")

    assert "pandas" in requirements


def test_latest_sdk_wheel_contains_current_trader_equity_metrics():
    project = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    version = re.search(r'^version = "([^"]+)"$', project, re.MULTILINE).group(1)
    wheels = sorted((ROOT / "dist").glob(f"qwesdk-{version}-*.whl"))

    assert wheels, f"dist 中缺少与源码版本 {version} 匹配的 QWeSDK wheel"
    with zipfile.ZipFile(wheels[-1]) as archive:
        trader = archive.read("m/trader/trader_v2.py").decode("utf-8")

    assert "self.equity_curve = []" in trader
    assert "def _record_daily_equity" in trader


def test_r8_default_memory_limit_allows_native_runtime_libraries():
    tasks = (ROOT / "m" / "worker" / "tasks.py").read_text(encoding="utf-8")
    sandbox = (ROOT / "m" / "worker" / "sandbox.py").read_text(encoding="utf-8")

    assert "memory_bytes=bounded(\"memoryBytes\", 1024 * 1024 * 1024" in tasks
    assert "memory_bytes: int = 1024 * 1024 * 1024" in sandbox
