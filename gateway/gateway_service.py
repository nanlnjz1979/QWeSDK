"""Internal Execution Gateway for the Helix R8 backtest contract."""

from __future__ import annotations

import hashlib
import hmac
import json
import math
import sqlite3
import time
import uuid
import threading
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Callable

from gateway.backtest_store import BacktestStore
from m.data_access.clickhouse import DatasetContractError
from m.worker.protocol import validate_run_spec


class GatewayError(Exception):
    def __init__(self, code: str, status: int, message: str | None = None):
        super().__init__(message or code)
        self.code = code
        self.status = status


@dataclass(frozen=True)
class Submission:
    accepted: bool
    gateway_request_id: str
    celery_task_id: str
    queue_name: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "accepted": self.accepted,
            "gatewayRequestId": self.gateway_request_id,
            "celeryTaskId": self.celery_task_id,
            "queueName": self.queue_name,
        }


class GatewayService:
    def __init__(
        self,
        secret: str,
        database_path: str | Path,
        celery_app: Any,
        clock: Callable[[], datetime] | None = None,
        max_timestamp_age_seconds: int = 300,
        callback_base_url: str | None = None,
        callback_secret: str | None = None,
        work_root: str | Path = "/tmp/qwesdk-runs",
        store: BacktestStore | None = None,
    ):
        if not secret:
            raise ValueError("Gateway secret must be non-empty")
        self.secret = secret.encode("utf-8")
        self.celery_app = celery_app
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.max_timestamp_age_seconds = max_timestamp_age_seconds
        self.database_path = str(database_path)
        self.callback_base_url = callback_base_url.rstrip("/") if callback_base_url else None
        self.callback_secret = (callback_secret or secret).encode("utf-8")
        self.work_root = Path(work_root)
        self._initialize_database()
        self.store = store or BacktestStore(database_path)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize_database(self) -> None:
        if self.database_path != ":memory:":
            Path(self.database_path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute(
                """CREATE TABLE IF NOT EXISTS submissions (
                    idempotency_key TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    request_id TEXT NOT NULL,
                    payload_sha256 TEXT NOT NULL,
                    body TEXT NOT NULL,
                    gateway_request_id TEXT NOT NULL,
                    celery_task_id TEXT NOT NULL,
                    queue_name TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )"""
            )

    def submit(self, run_id: str, body: bytes, headers: dict[str, str]) -> Submission:
        # 先完成身份和完整性校验，再解析业务契约，避免不可信输入被投递到
        # Celery 或写入提交记录。
        payload = self._authenticate(run_id, body, headers)
        try:
            validate_run_spec(payload)
        except DatasetContractError as error:
            raise GatewayError(error.code, 400, str(error)) from error
        except (TypeError, ValueError) as error:
            raise GatewayError("INVALID_RUN_SPEC", 400, str(error)) from error

        idempotency_key = self._header(headers, "x-idempotency-key")
        request_id = payload.get("requestId")
        if not isinstance(request_id, str) or not request_id:
            raise GatewayError("MISSING_REQUEST_ID", 400)
        digest = "sha256:" + hashlib.sha256(body).hexdigest()

        with self._connect() as connection:
            previous = connection.execute(
                "SELECT * FROM submissions WHERE idempotency_key = ?", (idempotency_key,)
            ).fetchone()
            if previous:
                # 使用相同幂等 Key 的重试请求直接返回原来的 ID；如果请求体不同，
                # 则拒绝请求，避免创建第二个任务。
                if previous["run_id"] != run_id or previous["body"] != body.decode("utf-8"):
                    raise GatewayError("IDEMPOTENCY_CONFLICT", 409)
                return Submission(True, previous["gateway_request_id"], previous["celery_task_id"], previous["queue_name"])

            gateway_request_id = "gw_" + uuid.uuid4().hex
            self.store.create_run(run_id, payload, status="queued")
            # Gateway 是这个架构中唯一的 Celery 生产者；Worker 稍后从 backtest
            # 队列消费这个固定名称的任务。
            task = self.celery_app.send_task("tasks.run_backtest", args=[payload], queue="backtest")
            celery_task_id = str(getattr(task, "id", "") or "")
            if not celery_task_id:
                raise GatewayError("CELERY_SUBMISSION_FAILED", 503)
            submission = Submission(True, gateway_request_id, celery_task_id, "backtest")
            connection.execute(
                """INSERT INTO submissions
                (idempotency_key, run_id, request_id, payload_sha256, body,
                 gateway_request_id, celery_task_id, queue_name, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (idempotency_key, run_id, request_id, digest, body.decode("utf-8"),
                 gateway_request_id, celery_task_id, "backtest", self.clock().isoformat()),
            )
            if self.callback_base_url and hasattr(task, "get"):
                # 本地 Celery 客户端可能提供 AsyncResult.get()；这个桥接线程用于
                # 在 Worker 结果后端位于本地时接收并处理结果。
                threading.Thread(target=self._bridge_result, args=(payload, celery_task_id, task), daemon=True).start()
            return submission

    def cancel(self, run_id: str) -> dict[str, Any]:
        with self._connect() as connection:
            record = connection.execute(
                "SELECT celery_task_id FROM submissions WHERE run_id = ? ORDER BY created_at DESC LIMIT 1",
                (run_id,),
            ).fetchone()
        if not record:
            raise GatewayError("TASK_NOT_FOUND", 404)
        task_id = record["celery_task_id"]
        cancel_marker = self.work_root / run_id / ".cancel"
        cancel_marker.parent.mkdir(parents=True, exist_ok=True)
        cancel_marker.touch(exist_ok=True)
        self.celery_app.control.revoke(task_id, terminate=False)
        return {"accepted": True, "runId": run_id, "celeryTaskId": task_id}

    def operational_summary(self, headers: dict[str, str], path: str) -> dict[str, Any]:
        """校验 Helix 运维请求，并返回不含内部明细的 Gateway 摘要。"""
        self._authenticate_operational_request(headers, path)
        summary = self.store.get_operational_summary(self.clock())
        return {
            "service": "execution-gateway",
            "status": "UP",
            "checkedAt": self._java_isoformat(self.clock()),
            "queueName": "backtest",
            **summary,
        }

    def authenticate_cancel(self, run_id: str, body: bytes, headers: dict[str, str]) -> None:
        payload = self._authenticate(run_id, body, headers)
        if set(payload) != {"runId"}:
            raise GatewayError("INVALID_CANCEL_REQUEST", 400)

    def _pause_before_progress_poll(self) -> None:
        time.sleep(0.5)

    def _task_is_pending(self, task: Any) -> bool:
        ready = getattr(task, "ready", None)
        if not callable(ready):
            return False
        try:
            return not bool(ready())
        except Exception:
            return False

    def _progress_events(self, task: Any) -> list[dict[str, Any]]:
        info = getattr(task, "info", None)
        if not isinstance(info, dict):
            return []
        events = info.get("events")
        return events if isinstance(events, list) else []

    def _forward_events(
        self,
        run_spec: dict[str, Any],
        celery_task_id: str,
        events: list[dict[str, Any]],
        sent: set[int],
        *,
        record: bool,
    ) -> None:
        for event in events:
            if not isinstance(event, dict):
                continue
            sequence = int(event.get("sequence", 0))
            if sequence in sent:
                continue
            if record:
                self.store.record_event(run_spec["runId"], event)
            payload = dict(event.get("payload") or {})
            payload["celeryTaskId"] = celery_task_id
            callback = {
                "eventId": f"{celery_task_id}_{sequence}",
                "runId": run_spec["runId"],
                "celeryTaskId": celery_task_id,
                "sequence": sequence,
                "occurredAt": event.get("occurredAt") or self.clock().isoformat(),
                "type": event.get("type", "log"),
                "payload": payload,
                "payloadSha256": self._payload_digest(payload),
            }
            try:
                self._post_callback(f"/internal/v1/backtests/{run_spec['runId']}/events", callback)
            except Exception:
                continue
            sent.add(sequence)

    def _bridge_result(self, run_spec: dict[str, Any], celery_task_id: str, task: Any) -> None:
        try:
            # 任务还在跑时，从 Celery 进度里取出新事件并转发给 Helix。
            sent: set[int] = set()
            timeout = float((run_spec.get("limits") or {}).get("wallSeconds", 300)) + 30
            deadline = time.monotonic() + timeout
            while self._task_is_pending(task) and time.monotonic() < deadline:
                self._forward_events(
                    run_spec, celery_task_id, self._progress_events(task), sent, record=True,
                )
                self._pause_before_progress_poll()
            # 先持久化结果，再通知 Helix；即使回调暂时不可用，也不能丢失 Worker
            # 已经生成的结果。
            try:
                worker_result = task.get(timeout=max(1.0, deadline - time.monotonic()))
            except Exception:
                worker_result = {
                    "schemaVersion": "1.0",
                    "runId": run_spec["runId"],
                    "status": "failed",
                    "errorCode": "WORKER_EXECUTION_FAILED",
                    "summary": {},
                    "series": {},
                    "runtime": {},
                    "events": [],
                }
            events = worker_result.get("events") or []
            result = self._result_payload(run_spec, celery_task_id, worker_result)
            # Keep the Gateway's durable result available even when Java is temporarily down.
            self.store.save_result(run_spec["runId"], result)
            self._forward_events(run_spec, celery_task_id, events, sent, record=False)
            self._post_result_callback(f"/internal/v1/backtests/{run_spec['runId']}/result", result)
        except Exception:
            return

    def record_event(self, run_id: str, event: dict[str, Any]) -> None:
        self.store.record_event(run_id, event)

    def save_result(self, run_id: str, result: dict[str, Any]) -> None:
        self.store.save_result(run_id, result)

    def status(self, run_id: str) -> dict[str, Any] | None:
        return self.store.get_status(run_id)

    def result(self, run_id: str) -> dict[str, Any] | None:
        return self.store.get_result(run_id)

    def _result_payload(self, run_spec: dict[str, Any], celery_task_id: str, worker_result: dict[str, Any]) -> dict[str, Any]:
        generated_at = self._java_isoformat(self.clock())
        result = {
            "resultId": f"res_{celery_task_id}",
            "runId": run_spec["runId"],
            "celeryTaskId": celery_task_id,
            "schemaVersion": "1.0",
            "status": worker_result.get("status", "failed"),
            "errorCode": worker_result.get("errorCode"),
            "generatedAt": generated_at,
            "summary": worker_result.get("summary") or {},
            "series": worker_result.get("series") or {},
            "warnings": {},
            "artifacts": {},
            "runtime": worker_result.get("runtime") or {},
        }
        result["payloadSha256"] = self._result_digest(result)
        return result

    @staticmethod
    def _java_isoformat(value: datetime) -> str:
        """Match Java OffsetDateTime serialization used by result verification."""
        rendered = value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        if "." in rendered:
            head, suffix = rendered.split("Z", 1)
            head = head.rstrip("0")
            rendered = head.rstrip(".") + "Z" + suffix
        return rendered

    def _pause_before_callback_retry(self, attempt: int) -> None:
        time.sleep(min(2 ** (attempt - 1), 4))

    def _post_result_callback(self, path: str, payload: dict[str, Any]) -> None:
        last_error = None
        for attempt in range(1, 4):
            try:
                self._post_callback(path, payload)
                return
            except Exception as error:
                last_error = error
                if attempt < 3:
                    self._pause_before_callback_retry(attempt)
        raise last_error

    def _post_callback(self, path: str, payload: dict[str, Any]) -> None:
        # 回调使用独立的签名方向：Gateway -> Helix。
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        request = urllib.request.Request(self.callback_base_url + path, data=body, method="POST", headers={
            "Content-Type": "application/json",
            "X-Helix-Internal-Signature": "sha256=" + hmac.new(self.callback_secret, body, hashlib.sha256).hexdigest(),
        })
        with urllib.request.urlopen(request, timeout=10) as response:
            if response.status < 200 or response.status >= 300:
                raise GatewayError("CALLBACK_REJECTED", 502)

    def _payload_digest(self, payload: dict[str, Any]) -> str:
        canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return "sha256:" + hashlib.sha256(canonical).hexdigest()

    @classmethod
    def _result_digest(cls, result: dict[str, Any]) -> str:
        canonical_payload = {key: result[key] for key in (
            "resultId", "runId", "celeryTaskId", "schemaVersion", "status", "generatedAt",
            "summary", "series", "warnings", "artifacts", "runtime")}
        canonical = json.dumps(cls._normalize_checksum_value(canonical_payload),
            ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return "sha256:" + hashlib.sha256(canonical).hexdigest()

    @classmethod
    def _normalize_checksum_value(cls, value: Any) -> Any:
        if isinstance(value, bool) or value is None or isinstance(value, str):
            return value
        if isinstance(value, int):
            return str(value)
        if isinstance(value, float):
            if not math.isfinite(value):
                raise ValueError("checksum payload contains a non-finite number")
            try:
                return format(Decimal(str(value)), "f")
            except InvalidOperation as error:
                raise ValueError("checksum payload contains an invalid number") from error
        if isinstance(value, dict):
            return {key: cls._normalize_checksum_value(item) for key, item in value.items()}
        if isinstance(value, list):
            return [cls._normalize_checksum_value(item) for item in value]
        return value

    def _authenticate(self, run_id: str, body: bytes, headers: dict[str, str]) -> dict[str, Any]:
        # 这些校验会把 URL 中的 run ID、请求体、时间有效性和共享密钥绑定在一起，
        # 防止重放、篡改以及跨回测任务提交。
        if not isinstance(run_id, str) or not run_id or "/" in run_id or "\\" in run_id:
            raise GatewayError("INVALID_RUN_ID", 400)
        try:
            payload = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise GatewayError("INVALID_BODY", 400) from error
        if not isinstance(payload, dict):
            raise GatewayError("INVALID_RUN_SPEC", 400)
        if payload.get("runId") != run_id:
            raise GatewayError("RUN_ID_MISMATCH", 400)
        idempotency_key = self._header(headers, "x-idempotency-key")
        if not idempotency_key:
            raise GatewayError("MISSING_IDEMPOTENCY_KEY", 400)
        timestamp = self._header(headers, "x-timestamp")
        if not timestamp:
            raise GatewayError("INVALID_TIMESTAMP", 400)
        try:
            parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            age = abs((self.clock() - parsed.astimezone(timezone.utc)).total_seconds())
        except ValueError as error:
            raise GatewayError("INVALID_TIMESTAMP", 400) from error
        if age > self.max_timestamp_age_seconds:
            raise GatewayError("STALE_TIMESTAMP", 401)
        declared_digest = self._header(headers, "x-payload-sha256")
        actual_digest = "sha256:" + hashlib.sha256(body).hexdigest()
        if not hmac.compare_digest(declared_digest or "", actual_digest):
            raise GatewayError("INVALID_PAYLOAD_SHA256", 400)
        expected = "sha256=" + hmac.new(self.secret, body, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(self._header(headers, "x-helix-internal-signature") or "", expected):
            raise GatewayError("INVALID_SIGNATURE", 401)
        return payload

    def _authenticate_operational_request(self, headers: dict[str, str], path: str) -> None:
        if path != "/internal/v1/ops/summary":
            raise GatewayError("INVALID_SIGNATURE", 401)
        timestamp = self._header(headers, "x-timestamp")
        signature = self._header(headers, "x-helix-internal-signature")
        if not timestamp or not signature:
            raise GatewayError("INVALID_SIGNATURE", 401)
        try:
            parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            age = abs((self.clock() - parsed.astimezone(timezone.utc)).total_seconds())
        except ValueError as error:
            raise GatewayError("INVALID_TIMESTAMP", 401) from error
        if age > self.max_timestamp_age_seconds:
            raise GatewayError("STALE_TIMESTAMP", 401)
        canonical = f"{timestamp}\nGET\n{path}".encode("utf-8")
        expected = "sha256=" + hmac.new(self.secret, canonical, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            raise GatewayError("INVALID_SIGNATURE", 401)

    @staticmethod
    def _header(headers: dict[str, str], name: str) -> str | None:
        lowered = {str(key).lower(): value for key, value in headers.items()}
        value = lowered.get(name.lower())
        return str(value) if value is not None else None
