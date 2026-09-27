import hashlib
import hmac
import json
from datetime import datetime, timezone

import pytest

from gateway.gateway_service import GatewayError, GatewayService
from m.data_access.clickhouse import manifest_hash


class Task:
    id = "celery-test-1"


class Control:
    def __init__(self):
        self.revoked = []

    def revoke(self, task_id, terminate=False):
        self.revoked.append((task_id, terminate))


class CeleryFake:
    def __init__(self):
        self.sent = []
        self.control = Control()

    def send_task(self, name, args, queue):
        self.sent.append((name, args, queue))
        return Task()


def spec(run_id="bt_1"):
    code = "def initialize(context):\n    pass\n\ndef handle_data(context, data):\n    pass\n"
    manifest = {
        "datasetId": "sample",
        "releaseVersion": "v1",
        "sourceType": "clickhouse",
        "schemaVersion": "v1",
        "storageMode": "immutable_table",
        "components": {"daily": {"database": "default", "tables": {
            "none": "sample_daily_none", "qfq": "sample_daily_qfq", "hfq": "sample_daily_hfq"
        }}},
        "coverage": {"start": "2024-01-01", "end": "2024-12-31"},
    }
    manifest["manifestHash"] = manifest_hash(manifest)
    return {
        "schemaVersion": "1.0", "runId": run_id, "requestId": "obx_1",
        "strategyCode": code,
        "strategyCodeHash": "sha256:" + hashlib.sha256(code.encode()).hexdigest(),
        "strategyEntryPoint": "qwesdk_callback_v1",
        "parameters": {},
        "symbols": ["AAA"],
        "dataset": {"id": "sample", "version": "v1", "manifestHash": manifest["manifestHash"],
                    "adjustmentMode": "qfq", "sourceType": "clickhouse", "manifest": manifest},
        "dateRange": {"start": "2024-01-01", "end": "2024-01-02"},
    }


def request(service, payload, key="bt_1", timestamp="2026-08-18T00:00:00Z"):
    body = json.dumps(payload, separators=(",", ":")).encode()
    return body, {
        "X-Idempotency-Key": key,
        "X-Timestamp": timestamp,
        "X-Payload-SHA256": "sha256:" + hashlib.sha256(body).hexdigest(),
        "X-Helix-Internal-Signature": "sha256=" + hmac.new(service.secret, body, hashlib.sha256).hexdigest(),
    }


def ops_request(service, path="/internal/v1/ops/summary", timestamp="2026-08-18T00:00:00Z"):
    canonical = f"{timestamp}\nGET\n{path}".encode()
    return {
        "X-Timestamp": timestamp,
        "X-Helix-Internal-Signature": "sha256=" + hmac.new(service.secret, canonical, hashlib.sha256).hexdigest(),
    }


@pytest.fixture
def service(tmp_path):
    fake = CeleryFake()
    now = datetime(2026, 8, 18, tzinfo=timezone.utc)
    result = GatewayService("secret", tmp_path / "gateway.sqlite3", fake, clock=lambda: now)
    result.fake = fake
    return result


def test_valid_submission_is_sent_to_only_allowed_celery_task(service):
    body, headers = request(service, spec())
    submission = service.submit("bt_1", body, headers)
    assert submission.celery_task_id == "celery-test-1"
    assert service.fake.sent[0][0] == "tasks.run_backtest"
    assert service.fake.sent[0][2] == "backtest"


def test_same_idempotency_request_replays_without_second_task(service):
    body, headers = request(service, spec())
    first = service.submit("bt_1", body, headers)
    second = service.submit("bt_1", body, headers)
    assert second == first
    assert len(service.fake.sent) == 1


def test_signature_digest_timestamp_and_run_spec_fail_closed(service):
    body, headers = request(service, spec())
    headers["X-Helix-Internal-Signature"] = "sha256=bad"
    with pytest.raises(GatewayError) as error:
        service.submit("bt_1", body, headers)
    assert error.value.code == "INVALID_SIGNATURE"

    body, headers = request(service, spec())
    headers["X-Payload-SHA256"] = "sha256:bad"
    with pytest.raises(GatewayError) as error:
        service.submit("bt_1", body, headers)
    assert error.value.code == "INVALID_PAYLOAD_SHA256"

    body, headers = request(service, spec(), timestamp="2020-01-01T00:00:00Z")
    with pytest.raises(GatewayError) as error:
        service.submit("bt_1", body, headers)
    assert error.value.code == "STALE_TIMESTAMP"

    invalid = spec()
    invalid["strategyCodeHash"] = "sha256:bad"
    body, headers = request(service, invalid)
    with pytest.raises(GatewayError) as error:
        service.submit("bt_1", body, headers)
    assert error.value.code == "INVALID_RUN_SPEC"

    invalid_source = spec()
    invalid_source["dataset"]["sourceType"] = "csv"
    body, headers = request(service, invalid_source)
    with pytest.raises(GatewayError) as error:
        service.submit("bt_1", body, headers)
    assert error.value.code == "DATASET_SOURCE_UNSUPPORTED"


def test_cancel_revokes_associated_task(service):
    body, headers = request(service, spec())
    service.submit("bt_1", body, headers)
    assert service.cancel("bt_1")["celeryTaskId"] == "celery-test-1"
    assert service.fake.control.revoked == [("celery-test-1", False)]


def test_result_payload_normalizes_worker_lists_to_helix_objects(service):
    payload = service._result_payload(
        spec(),
        "celery-test-1",
        {
            "status": "succeeded",
            "summary": {"totalReturn": 0.1},
            "series": {"equityCurve": []},
            "warnings": [],
            "artifacts": [],
            "runtime": {"qwesdkVersion": "1.0.3"},
        },
    )

    assert payload["warnings"] == {}
    assert payload["artifacts"] == {}
    canonical = {
        key: payload[key]
        for key in (
            "resultId", "runId", "celeryTaskId", "schemaVersion", "status", "generatedAt",
            "summary", "series", "warnings", "artifacts", "runtime",
        )
    }
    assert payload["payloadSha256"] == "sha256:f062e713c17f0efc139ad1f4d71cf44cc09d16d35e2b9e76ff89a0423a5f5e95"


def test_result_timestamp_matches_java_offsetdatetime_format(service):
    payload = service._result_payload(
        spec(),
        "celery-test-1",
        {"status": "failed", "summary": {}, "series": {}, "runtime": {}},
    )

    assert payload["generatedAt"] == "2026-08-18T00:00:00Z"

    service.clock = lambda: datetime(2026, 8, 18, 0, 0, 0, 242020, tzinfo=timezone.utc)
    payload = service._result_payload(
        spec(),
        "celery-test-1",
        {"status": "failed", "summary": {}, "series": {}, "runtime": {}},
    )
    assert payload["generatedAt"] == "2026-08-18T00:00:00.24202Z"


def test_bridge_persists_worker_result_before_unavailable_callback(service):
    body, headers = request(service, spec())
    service.submit("bt_1", body, headers)
    service.callback_base_url = "http://java-api.invalid"

    class CompletedTask:
        def get(self, timeout):
            return {
                "status": "succeeded",
                "summary": {"tradeCount": 1},
                "series": {"equityCurve": [{"date": "2024-01-01"}]},
                "warnings": [],
                "artifacts": [],
                "runtime": {},
                "events": [{"sequence": 1, "type": "succeeded", "payload": {"progress": 100}}],
            }

    service._post_callback = lambda *_args: (_ for _ in ()).throw(ConnectionError("callback unavailable"))
    service._bridge_result(spec(), "celery-test-1", CompletedTask())

    assert service.store.get_status("bt_1")["status"] == "succeeded"
    assert service.store.get_result("bt_1")["summary"]["tradeCount"] == 1


def test_bridge_persists_sanitized_worker_failure_before_callback(service):
    body, headers = request(service, spec())
    service.submit("bt_1", body, headers)

    class FailedTask:
        def get(self, timeout):
            return {
                "schemaVersion": "1.0",
                "runId": "bt_1",
                "status": "failed",
                "errorCode": "STRATEGY_EXECUTION_FAILED",
                "summary": {}, "series": {}, "runtime": {}, "events": [],
            }

    service._post_callback = lambda *_args: (_ for _ in ()).throw(ConnectionError("callback unavailable"))
    service._bridge_result(spec(), "celery-test-1", FailedTask())

    assert service.store.get_status("bt_1")["status"] == "failed"
    assert service.store.get_status("bt_1")["errorCode"] == "STRATEGY_EXECUTION_FAILED"
    assert service.store.get_result("bt_1")["errorCode"] == "STRATEGY_EXECUTION_FAILED"


def test_result_callback_retries_then_keeps_stored_error_code(service, monkeypatch):
    body, headers = request(service, spec())
    service.submit("bt_1", body, headers)
    attempts = {"count": 0}

    def flaky(path, payload):
        attempts["count"] += 1
        if attempts["count"] < 3:
            raise TimeoutError("temporary")

    class FailedTask:
        def get(self, timeout):
            return {
                "schemaVersion": "1.0",
                "runId": "bt_1",
                "status": "failed",
                "errorCode": "STRATEGY_EXECUTION_FAILED",
                "summary": {},
                "series": {},
                "runtime": {},
                "events": [],
            }

    monkeypatch.setattr(service, "_post_callback", flaky)
    monkeypatch.setattr(service, "_pause_before_callback_retry", lambda _attempt: None)
    service._bridge_result(spec(), "celery-test-1", FailedTask())

    assert attempts["count"] == 3
    assert service.store.get_result("bt_1")["errorCode"] == "STRATEGY_EXECUTION_FAILED"


def test_bridge_forwards_progress_before_the_task_finishes(service, monkeypatch):
    body, headers = request(service, spec())
    service.submit("bt_1", body, headers)
    monkeypatch.setattr(service, "_pause_before_progress_poll", lambda: None)
    posted = []
    loading = {
        "sequence": 1, "type": "running",
        "payload": {"progress": 5, "stage": "loading_data"},
        "occurredAt": "2026-09-25T00:00:00Z",
    }
    running = {
        "sequence": 2, "type": "progress",
        "payload": {"progress": 40, "stage": "running", "completedDates": 10, "totalDates": 100},
        "occurredAt": "2026-09-25T00:00:01Z",
    }
    finished = {
        "sequence": 3, "type": "succeeded",
        "payload": {"progress": 100, "stage": "completed"},
        "occurredAt": "2026-09-25T00:00:02Z",
    }

    class LiveTask:
        def __init__(self):
            self.polls = 0

        def ready(self):
            self.polls += 1
            return self.polls >= 3

        @property
        def info(self):
            if self.polls < 2:
                return {"events": [loading]}
            return {"events": [loading, running]}

        def get(self, timeout):
            assert [item.get("sequence") for item in posted] == [1, 2]
            return {
                "status": "succeeded",
                "summary": {},
                "series": {},
                "runtime": {},
                "events": [loading, running, finished],
            }

    monkeypatch.setattr(service, "_post_callback", lambda _path, payload: posted.append(payload))
    service._bridge_result(spec(), "celery-test-1", LiveTask())

    assert [item.get("sequence") for item in posted] == [1, 2, 3, None]
    assert posted[0]["payload"]["stage"] == "loading_data"
    assert posted[1]["payload"]["completedDates"] == 10
    assert posted[-1]["status"] == "succeeded"
    assert [event["sequence"] for event in service.store.get_status("bt_1")["events"]] == [1, 2]
    assert service.store.get_status("bt_1")["status"] == "succeeded"


def test_daily_progress_is_reported_about_every_five_percent():
    from m.trader.trader_v2 import TraderV2

    engine = TraderV2.__new__(TraderV2)
    engine.dates = list(range(100))
    seen = []
    engine.progress_callback = lambda completed, total: seen.append((completed, total))
    for day in range(1, 101):
        engine._report_progress(day)

    assert seen[0] == (5, 100)
    assert seen[-1] == (100, 100)
    assert len(seen) == 20


def test_operations_summary_requires_method_path_signature_and_returns_counts(service):
    service.store.create_run("bt_queued", {"runId": "bt_queued"}, status="queued")
    service.store.create_run("bt_running", {"runId": "bt_running"}, status="running")
    service.store.create_run("bt_failed", {"runId": "bt_failed"}, status="failed")
    with service.store._connect() as connection:
        connection.execute("UPDATE backtest_runs SET updated_at = ? WHERE run_id = ?",
                           ("2026-08-18T00:00:00Z", "bt_failed"))

    summary = service.operational_summary(
        ops_request(service), "/internal/v1/ops/summary"
    )

    assert summary["service"] == "execution-gateway"
    assert summary["status"] == "UP"
    assert summary["queueName"] == "backtest"
    assert summary["queuedTasks"] == 1
    assert summary["runningTasks"] == 1
    assert summary["failedTasksLast24h"] == 1


def test_operations_summary_rejects_wrong_path_signature(service):
    with pytest.raises(GatewayError) as error:
        service.operational_summary(
            ops_request(service, path="/internal/v1/other"),
            "/internal/v1/ops/summary",
        )

    assert error.value.code == "INVALID_SIGNATURE"
