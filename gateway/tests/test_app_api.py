import hashlib
import hmac
import json
import threading
import urllib.request
from http.server import ThreadingHTTPServer
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from backtest_api import BrowserBacktestService
from clickhouse_dataset_loader import manifest_hash
from gateway_service import GatewayService
from app import make_handler


class Task:
    id = "celery-api-test"


class FakeCelery:
    def send_task(self, name, args, queue):
        return Task()

    class control:
        @staticmethod
        def revoke(*_args, **_kwargs):
            return None


def clickhouse_manifest():
    manifest = {
        "datasetId": "cn-stock-daily",
        "releaseVersion": "20260831",
        "sourceType": "clickhouse",
        "schemaVersion": "v1",
        "storageMode": "immutable_table",
        "components": {
            "daily": {
                "database": "default",
                "tables": {
                    "none": "release_20260831_stock_daily_none",
                    "qfq": "release_20260831_stock_daily_qfq",
                    "hfq": "release_20260831_stock_daily_hfq",
                },
            }
        },
        "coverage": {"start": "2024-01-01", "end": "2024-12-31"},
    }
    manifest["manifestHash"] = manifest_hash(manifest)
    return manifest


def test_browser_routes_return_controlled_empty_dataset_list_and_accept_run(tmp_path):
    manifest = clickhouse_manifest()
    gateway = GatewayService("secret", tmp_path / "gateway.sqlite3", FakeCelery())
    browser = BrowserBacktestService(gateway, tmp_path, local_execution=False)
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(browser, tmp_path / "missing-data-root"))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        base = f"http://127.0.0.1:{server.server_port}"
        with patch.object(Path, "rglob", side_effect=AssertionError("dataset listing must not read files")):
            datasets = json.loads(urllib.request.urlopen(base + "/api/datasets").read())
        assert datasets == []
        body = json.dumps({
            "strategyCode": "def initialize(context): pass\ndef handle_data(context, data): pass",
            "dataset": {
                "id": "cn-stock-daily",
                "version": "20260831",
                "manifestHash": manifest["manifestHash"],
                "manifest": manifest,
            },
            "dateRange": {"start": "2024-01-01", "end": "2024-01-01"},
            "initialCapital": 100000,
        }).encode()
        request = urllib.request.Request(base + "/api/backtests", data=body, method="POST", headers={"Content-Type": "application/json"})
        submitted = json.loads(urllib.request.urlopen(request).read())
        assert submitted["runId"].startswith("bt_")
        status = json.loads(urllib.request.urlopen(base + "/api/backtests/" + submitted["runId"]).read())
        assert status["status"] == "queued"
    finally:
        server.shutdown()
        thread.join(timeout=2)


def test_internal_cancel_route_requires_signature_and_revokes_task(tmp_path):
    gateway = GatewayService("secret", tmp_path / "gateway.sqlite3", FakeCelery(),
                             clock=lambda: datetime(2026, 8, 18, tzinfo=timezone.utc))
    browser = BrowserBacktestService(gateway, tmp_path, local_execution=False)
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(browser, tmp_path))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        base = f"http://127.0.0.1:{server.server_port}"
        spec_body = json.dumps({
            "strategyCode": "def initialize(context): pass\ndef handle_data(context, data): pass",
            "dataset": {"id": "fixture", "version": "v1", "manifestHash": "sha256:fixture"},
            "dateRange": {"start": "2024-01-01", "end": "2024-01-01"},
        }).encode()
        # Seed the Gateway submission directly; this test focuses on the internal cancel route.
        with gateway._connect() as connection:
            connection.execute("INSERT INTO submissions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                               ("bt_cancel", "bt_cancel", "request", "digest", spec_body.decode(),
                                "gw_cancel", "celery-api-test", "backtest", "2026-08-18T00:00:00+00:00"))
        body = json.dumps({"runId": "bt_cancel"}, separators=(",", ":")).encode()
        digest = hashlib.sha256(body).hexdigest()
        headers = {
            "Content-Type": "application/json",
            "X-Idempotency-Key": "cancel_bt_cancel",
            "X-Timestamp": "2026-08-18T00:00:00Z",
            "X-Payload-SHA256": "sha256:" + digest,
            "X-Helix-Internal-Signature": "sha256=" + hmac.new(b"secret", body, hashlib.sha256).hexdigest(),
        }
        request = urllib.request.Request(base + "/v1/backtests/bt_cancel/cancel", data=body,
                                          method="POST", headers=headers)
        response = json.loads(urllib.request.urlopen(request).read())
        assert response["celeryTaskId"] == "celery-api-test"
    finally:
        server.shutdown()
        thread.join(timeout=2)


def test_operations_summary_route_returns_signed_gateway_metrics(tmp_path):
    gateway = GatewayService("secret", tmp_path / "gateway.sqlite3", FakeCelery(),
                             clock=lambda: datetime(2026, 8, 18, tzinfo=timezone.utc))
    gateway.store.create_run("bt_queued", {"runId": "bt_queued"}, status="queued")
    browser = BrowserBacktestService(gateway, tmp_path, local_execution=False)
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(browser, tmp_path))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        path = "/internal/v1/ops/summary"
        timestamp = "2026-08-18T00:00:00Z"
        canonical = f"{timestamp}\nGET\n{path}".encode()
        request = urllib.request.Request(
            f"http://127.0.0.1:{server.server_port}{path}",
            headers={
                "X-Timestamp": timestamp,
                "X-Helix-Internal-Signature": "sha256=" + hmac.new(b"secret", canonical, hashlib.sha256).hexdigest(),
            },
        )

        response = json.loads(urllib.request.urlopen(request).read())

        assert response["status"] == "UP"
        assert response["queuedTasks"] == 1
        assert "gateway.sqlite3" not in json.dumps(response)
    finally:
        server.shutdown()
        thread.join(timeout=2)
