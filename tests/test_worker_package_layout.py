from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def test_worker_runtime_is_importable_from_the_qwesdk_package():
    from m.data_access import catalog, clickhouse
    from m.worker import backtest, celery_app, protocol, sandbox, tasks

    assert catalog
    assert clickhouse
    assert backtest
    assert celery_app
    assert protocol
    assert sandbox
    assert tasks


def test_worker_docker_entrypoint_starts_the_packaged_worker():
    script = (ROOT / "docker" / "worker" / "start_qwesdk.sh").read_text(encoding="utf-8")
    dockerfile = (ROOT / "docker" / "worker" / "Dockerfile").read_text(encoding="utf-8")

    assert "celery -A m.worker.celery_app worker" in script
    assert "COPY docker/worker/qwesdk_entrypoint.py docker/worker/start_qwesdk.sh" in dockerfile
    assert "COPY docker/app" not in dockerfile
