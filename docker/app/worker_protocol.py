"""Versioned JSON Lines events emitted by the QWeSDK worker."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Callable


EVENT_SCHEMA_VERSION = "1.0"
RUN_SPEC_SCHEMA_VERSION = "1.0"
MAX_CODE_BYTES = 2 * 1024 * 1024
RUN_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class EventStream:
    def __init__(self, run_id: str, emit_line: Callable[[str], None] | None = None):
        self.run_id = run_id
        self.events: list[dict] = []
        self._emit_line = emit_line

    def emit(self, event_type: str, **payload) -> dict:
        event = {
            "schemaVersion": EVENT_SCHEMA_VERSION,
            "runId": self.run_id,
            "sequence": len(self.events) + 1,
            "occurredAt": utc_now(),
            "type": event_type,
            "payload": payload,
        }
        self.events.append(event)
        if self._emit_line is not None:
            self._emit_line(json.dumps(event, ensure_ascii=False, separators=(",", ":")))
        return event


def validate_run_spec(run_spec: dict) -> tuple[str, str]:
    if not isinstance(run_spec, dict):
        raise ValueError("runSpec must be an object")
    if run_spec.get("schemaVersion") != RUN_SPEC_SCHEMA_VERSION:
        raise ValueError("unsupported runSpec schemaVersion")
    run_id = run_spec.get("runId")
    code = run_spec.get("code")
    if not isinstance(run_id, str) or not RUN_ID_RE.fullmatch(run_id):
        raise ValueError("runSpec.runId is invalid")
    if not isinstance(code, str) or not code:
        raise ValueError("runSpec.code is required")
    if len(code.encode("utf-8")) > MAX_CODE_BYTES:
        raise ValueError("runSpec.code exceeds the maximum size")
    return run_id, code
