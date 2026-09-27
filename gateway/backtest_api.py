"""Browser-facing daily backtest API helpers."""

from __future__ import annotations

import hashlib
import json
import os
import threading
import uuid
from datetime import date, datetime, timezone
from typing import Any

from gateway.gateway_service import GatewayService
from m.data_access.clickhouse import validate_manifest
from m.worker.protocol import normalize_symbols, validate_run_spec


def _iso_date(value: Any, field: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be an ISO date")
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError as error:
        raise ValueError(f"{field} must be an ISO date") from error


def _frequency(value: Any) -> str:
    return "daily" if value in (None, "1d", "daily") else str(value)


def list_datasets() -> list[dict[str, Any]]:
    # PostgreSQL/Helix owns the catalog; Gateway has no filesystem fallback.
    # Return the controlled empty response until Helix supplies an authorized catalog API.
    return []


class BrowserBacktestService:
    def __init__(self, gateway: GatewayService, local_execution: bool = False):
        self.gateway = gateway
        self.local_execution = local_execution

    def _build_run_spec(self, run_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        code = payload.get("strategyCode")
        if not isinstance(code, str) or not code.strip():
            raise ValueError("strategyCode is required")
        dataset = payload.get("dataset")
        if not isinstance(dataset, dict):
            raise ValueError("dataset is required")
        start = _iso_date((payload.get("dateRange") or {}).get("start"), "dateRange.start")
        end = _iso_date((payload.get("dateRange") or {}).get("end"), "dateRange.end")
        if start > end:
            raise ValueError("dateRange.start must not be after dateRange.end")
        capital = payload.get("initialCapital", 100000)
        try:
            capital = float(capital)
        except (TypeError, ValueError) as error:
            raise ValueError("initialCapital must be a positive number") from error
        if capital <= 0:
            raise ValueError("initialCapital must be a positive number")
        spec = {
            "schemaVersion": "1.0",
            "runId": run_id,
            "requestId": "browser_" + uuid.uuid4().hex,
            "strategyVersionId": payload.get("strategyVersionId") or "browser-draft",
            "strategyCode": code,
            "strategyCodeHash": "sha256:" + hashlib.sha256(code.encode("utf-8")).hexdigest(),
            "strategyEntryPoint": "qwesdk_callback_v1",
            "parameters": payload.get("parameters") if isinstance(payload.get("parameters"), dict) else {},
            "symbols": normalize_symbols(payload.get("symbols")),
            "dataset": {
                "id": dataset.get("id"),
                "version": dataset.get("version"),
                "manifestHash": dataset.get("manifestHash"),
                "adjustmentMode": dataset.get("adjustmentMode", "none"),
                "frequency": "daily",
                "sourceType": dataset.get("sourceType", "clickhouse"),
                "manifest": dataset.get("manifest"),
            },
            "dateRange": {"start": start, "end": end},
            "initialCapital": capital,
            "benchmark": payload.get("benchmark") or None,
            "limits": payload.get("limits") if isinstance(payload.get("limits"), dict) else {},
            "runtime": {"qwesdkVersion": "1.0.10", "workerImageDigest": "local"},
        }
        validate_run_spec(spec)
        return spec

    def _validate_catalog(self, spec: dict[str, Any]) -> None:
        # Gateway 只校验 Helix 已冻结的 inline Manifest，不扫描本地目录。
        requested = spec["dataset"]
        manifest = requested.get("manifest")
        if not isinstance(manifest, dict):
            raise ValueError("dataset Manifest is required")
        validate_manifest(
            manifest,
            dataset_id=requested["id"],
            version=requested["version"],
            expected_hash=requested["manifestHash"],
        )
        coverage = manifest["coverage"]
        start_date = _iso_date(coverage.get("start"), "coverage.start")
        end_date = _iso_date(coverage.get("end"), "coverage.end")
        start = spec["dateRange"]["start"]
        end = spec["dateRange"]["end"]
        if start < start_date or end > end_date:
            raise ValueError("dateRange must be within the dataset range")

    def submit(self, payload: dict[str, Any]) -> dict[str, str]:
        run_id = "bt_" + uuid.uuid4().hex
        spec = self._build_run_spec(run_id, payload)
        self._validate_catalog(spec)
        if self.local_execution:
            # 本地模式是开发环境的快捷路径；生产模式只能通过下面的
            # GatewayService -> Redis/Celery 边界提交任务。
            self.gateway.store.create_run(run_id, spec, status="queued")
            threading.Thread(target=self._run_local, args=(spec,), daemon=True).start()
            return {"runId": run_id, "status": "queued"}

        body = json.dumps(spec, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        digest = "sha256:" + hashlib.sha256(body).hexdigest()
        import hmac

        headers = {
            "X-Idempotency-Key": run_id,
            "X-Timestamp": timestamp,
            "X-Payload-SHA256": digest,
            "X-Helix-Internal-Signature": "sha256=" + hmac.new(self.gateway.secret, body, hashlib.sha256).hexdigest(),
        }
        # 浏览器工作台属于本地工具，因此由这里生成签名；生产环境中的 Helix
        # 通过 /v1 使用同一个 GatewayService 契约。
        submission = self.gateway.submit(run_id, body, headers)
        return {"runId": run_id, "status": "queued", **submission.as_dict()}

    def _run_local(self, spec: dict[str, Any]) -> None:
        try:
            from m.worker.tasks import run_backtest

            worker_result = run_backtest.run(spec)
            for event in worker_result.get("events") or []:
                self.gateway.record_event(spec["runId"], event)
            normalized = self.gateway._result_payload(spec, "local_" + spec["runId"], worker_result)
            self.gateway.save_result(spec["runId"], normalized)
        except Exception as error:
            self.gateway.store.save_error(spec["runId"], type(error).__name__)

    def status(self, run_id: str) -> dict[str, Any] | None:
        return self.gateway.status(run_id)

    def result(self, run_id: str) -> dict[str, Any] | None:
        return self.gateway.result(run_id)
