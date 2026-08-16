"""Celery task allow-list for the QWeSDK worker."""

from __future__ import annotations

import json
import os
from pathlib import Path

from celery_app import app
from sandbox_runner import SandboxLimits, run_sandboxed
from worker_protocol import EventStream, validate_run_spec


def _limits(run_spec: dict) -> SandboxLimits:
    values = run_spec.get("limits") or {}
    def bounded(name: str, default: float, maximum: float, convert):
        return convert(min(float(values.get(name, default)), maximum))

    return SandboxLimits(
        wall_seconds=bounded("wallSeconds", 300, 3600, float),
        cpu_seconds=bounded("cpuSeconds", 300, 3600, int),
        memory_bytes=bounded("memoryBytes", 512 * 1024 * 1024, 2 * 1024 * 1024 * 1024, int),
        max_output_bytes=bounded("maxOutputBytes", 1024 * 1024, 16 * 1024 * 1024, int),
        max_processes=bounded("maxProcesses", 32, 64, int),
    )


@app.task(bind=True, name="tasks.run_backtest")
def run_backtest(self, run_spec: dict) -> dict:
    run_id, code = validate_run_spec(run_spec)

    event_stream = EventStream(run_id, emit_line=lambda line: print(line, flush=True))
    work_root = Path(os.environ.get("QWESDK_WORK_ROOT", "/tmp/qwesdk-runs"))
    cancel_file = work_root / run_id / ".cancel"
    cancel_file.parent.mkdir(parents=True, exist_ok=True)
    result = run_sandboxed(
        run_id=run_id,
        code=code,
        work_root=work_root,
        limits=_limits(run_spec),
        cancel_file=cancel_file,
        emit=event_stream.emit,
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
