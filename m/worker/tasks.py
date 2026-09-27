"""Celery task allow-list for the QWeSDK worker."""

from __future__ import annotations

import json
import os
from pathlib import Path

from m.data_access.clickhouse import DatasetContractError
from m.worker.celery_app import app
from m.worker.sandbox import SandboxLimits, run_sandboxed
from m.worker.protocol import EventStream, validate_run_spec


def _limits(run_spec: dict) -> SandboxLimits:
    values = run_spec.get("limits") or {}
    def bounded(name: str, default: float, maximum: float, convert):
        return convert(min(float(values.get(name, default)), maximum))

    return SandboxLimits(
        wall_seconds=bounded("wallSeconds", 300, 3600, float),
        cpu_seconds=bounded("cpuSeconds", 300, 3600, int),
        memory_bytes=bounded("memoryBytes", 4 * 1024 * 1024 * 1024, 4 * 1024 * 1024 * 1024, int),
        max_output_bytes=bounded("maxOutputBytes", 1024 * 1024, 16 * 1024 * 1024, int),
        max_processes=bounded("maxProcesses", 128, 256, int),
    )


def _r8_sandbox_code(run_spec: dict) -> str:
    spec_json = json.dumps(run_spec, ensure_ascii=False, separators=(",", ":"))
    sdk_root = os.environ.get("QWESDK_INSTALL_TARGET", "/var/lib/qwesdk/python")
    return f"""
import json
import sys
sys.path.insert(0, {sdk_root!r})
from m.worker.backtest import StockPoolError, run_backtest_spec
from m.worker.protocol import EventStream
from m.data_access.clickhouse import DatasetContractError

spec = json.loads({spec_json!r})
events = EventStream(spec["runId"], emit_line=lambda line: print("QWE_EVENT:" + line, flush=True))
try:
    result = run_backtest_spec(spec, events)
except DatasetContractError as error:
    detail = " ".join(str(error).split())[:160]
    message = "回测失败：" + error.code + ((" " + detail) if detail else "")
    events.emit("log", level="error", stage="failed", message=message)
    events.emit("failed", progress=0, stage="failed", errorCode=error.code)
    result = {{"schemaVersion": "1.0", "runId": spec["runId"], "status": "failed",
              "errorCode": error.code, "events": events.events}}
except StockPoolError as error:
    detail = " ".join(str(error).split())[:160]
    message = "回测失败：" + detail
    events.emit("log", level="error", stage="failed", message=message)
    events.emit("failed", progress=0, stage="failed", errorCode="STRATEGY_EXECUTION_FAILED")
    result = {{"schemaVersion": "1.0", "runId": spec["runId"], "status": "failed",
              "errorCode": "STRATEGY_EXECUTION_FAILED", "events": events.events}}
except Exception:
    events.emit("log", level="error", stage="failed", message="回测失败：STRATEGY_EXECUTION_FAILED")
    events.emit("failed", progress=0, stage="failed", errorCode="STRATEGY_EXECUTION_FAILED")
    result = {{"schemaVersion": "1.0", "runId": spec["runId"], "status": "failed",
              "errorCode": "STRATEGY_EXECUTION_FAILED", "events": events.events}}
print("QWE_RESULT:" + json.dumps(result, ensure_ascii=False, separators=(",", ":")), flush=True)
""".strip()


def _publish_progress(task, events: list[dict]) -> None:
    update = getattr(task, "update_state", None)
    if update is None:
        return
    try:
        update(state="PROGRESS", meta={"events": list(events)})
    except Exception:
        return


def _consume_progress_line(task, event_stream: EventStream, line: str) -> None:
    if not line.startswith("QWE_EVENT:"):
        return
    try:
        event = json.loads(line[len("QWE_EVENT:"):])
    except json.JSONDecodeError:
        return
    if not isinstance(event, dict):
        return
    payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
    event_stream.emit(event.get("type") or "log", **payload)
    _publish_progress(task, event_stream.events)


def _read_r8_output(stdout: str) -> tuple[list[dict], dict | None]:
    events = []
    result = None
    for line in stdout.splitlines():
        if line.startswith("QWE_EVENT:"):
            try:
                events.append(json.loads(line[len("QWE_EVENT:"):]))
            except json.JSONDecodeError:
                continue
        elif line.startswith("QWE_RESULT:"):
            try:
                result = json.loads(line[len("QWE_RESULT:"):])
            except json.JSONDecodeError:
                result = None
    return events, result


@app.task(bind=True, name="tasks.run_backtest")
def run_backtest(self, run_spec: dict) -> dict:
    try:
        validated = validate_run_spec(run_spec)
    except (DatasetContractError, ValueError, TypeError) as error:
        return {
            "schemaVersion": "1.0",
            "runId": str(run_spec.get("runId") or "unknown"),
            "status": "failed",
            "errorCode": error.code if isinstance(error, DatasetContractError) else "INVALID_RUN_SPEC",
            "events": [],
        }
    run_id, code = validated

    event_stream = EventStream(run_id, emit_line=lambda line: print(line, flush=True))

    def emit_and_publish(event_type, **payload):
        event = event_stream.emit(event_type, **payload)
        _publish_progress(self, event_stream.events)
        return event

    work_root = Path(os.environ.get("QWESDK_WORK_ROOT", "/tmp/qwesdk-runs"))
    cancel_file = work_root / run_id / ".cancel"
    cancel_file.parent.mkdir(parents=True, exist_ok=True)
    if "strategyCode" in validated:
        result = run_sandboxed(
            run_id=run_id,
            code=_r8_sandbox_code(dict(validated)),
            work_root=work_root,
            limits=_limits(run_spec),
            cancel_file=cancel_file,
            emit=emit_and_publish,
            on_stdout_line=lambda line: _consume_progress_line(self, event_stream, line),
        )
        _child_events, child_result = _read_r8_output(result.stdout)
        if result.status != "succeeded" or child_result is None:
            return {
                "schemaVersion": "1.0",
                "runId": run_id,
                "status": result.status if result.status != "succeeded" else "failed",
                "stdout": result.stdout,
                "stderr": result.stderr,
                "errorCode": result.error_code or "BACKTEST_RESULT_MISSING",
                "exitCode": result.exit_code,
                "events": event_stream.events,
            }
        child_result.update({
            "schemaVersion": "1.0",
            "runId": run_id,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "errorCode": child_result.get("errorCode"),
            "exitCode": result.exit_code,
            "events": event_stream.events,
        })
        return child_result

    result = run_sandboxed(
        run_id=run_id,
        code=code,
        work_root=work_root,
        limits=_limits(run_spec),
        cancel_file=cancel_file,
        emit=emit_and_publish,
    )
    return {
        "schemaVersion": "1.0",
        "runId": run_id,
        "status": result.status,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "errorCode": result.error_code,
        "exitCode": result.exit_code,
        "events": event_stream.events,
    }
