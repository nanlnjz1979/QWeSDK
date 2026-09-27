"""Versioned JSON Lines events emitted by the QWeSDK worker."""

from __future__ import annotations

import json
import hashlib
import re
from datetime import datetime, timezone
from typing import Callable

from m.data_access.clickhouse import DatasetContractError


EVENT_SCHEMA_VERSION = "1.0"
RUN_SPEC_SCHEMA_VERSION = "1.0"
MAX_CODE_BYTES = 2 * 1024 * 1024
RUN_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")
SAFE_COMPONENT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
SAFE_SYMBOL_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,31}$")
MAX_SYMBOLS = 200


class ValidatedRunSpec(dict):
    """Mapping for R8 fields with tuple compatibility for the R1 security tests."""

    def __iter__(self):
        if "strategyCode" in self:
            yield self["runId"]
            yield self["strategyCode"]
        else:
            yield self["runId"]
            yield self["code"]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def normalize_symbols(value: object) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError("runSpec.symbols must be a list")
    if not value:
        return []
    normalized: list[str] = []
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, str):
            raise ValueError("runSpec.symbols must contain strings")
        symbol = item.strip()
        if not SAFE_SYMBOL_RE.fullmatch(symbol):
            raise ValueError("runSpec.symbols contains an invalid stock code")
        if symbol not in seen:
            normalized.append(symbol)
            seen.add(symbol)
        if len(normalized) > MAX_SYMBOLS:
            raise ValueError(f"runSpec.symbols cannot contain more than {MAX_SYMBOLS} items")
    return normalized


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


def validate_run_spec(run_spec: dict) -> ValidatedRunSpec:
    if not isinstance(run_spec, dict):
        raise ValueError("runSpec must be an object")
    if run_spec.get("schemaVersion") != RUN_SPEC_SCHEMA_VERSION:
        raise ValueError("unsupported runSpec schemaVersion")
    run_id = run_spec.get("runId")
    if not isinstance(run_id, str) or not RUN_ID_RE.fullmatch(run_id):
        raise ValueError("runSpec.runId is invalid")

    # Keep the R1 minimal script contract for existing sandbox security tests.
    legacy_code = run_spec.get("code")
    if "strategyCode" not in run_spec and legacy_code is not None:
        if not isinstance(legacy_code, str) or not legacy_code:
            raise ValueError("runSpec.code is required")
        if len(legacy_code.encode("utf-8")) > MAX_CODE_BYTES:
            raise ValueError("runSpec.code exceeds the maximum size")
        return ValidatedRunSpec(run_spec)

    code = run_spec.get("strategyCode")
    if not isinstance(code, str) or not code:
        raise ValueError("runSpec.strategyCode is required")
    if len(code.encode("utf-8")) > MAX_CODE_BYTES:
        raise ValueError("runSpec.strategyCode exceeds the maximum size")
    strategy_entry_point = run_spec.get("strategyEntryPoint")
    if strategy_entry_point not in {"qwesdk_callback_v1", "qwesdk_script_v1"}:
        raise ValueError("runSpec.strategyEntryPoint is unsupported")
    expected_hash = "sha256:" + hashlib.sha256(code.encode("utf-8")).hexdigest()
    if run_spec.get("strategyCodeHash") != expected_hash:
        raise ValueError("runSpec.strategyCodeHash does not match strategyCode")
    symbols = normalize_symbols(run_spec.get("symbols"))

    dataset = run_spec.get("dataset")
    if not isinstance(dataset, dict):
        raise ValueError("runSpec.dataset is required")
    for field in ("id", "version", "manifestHash", "adjustmentMode"):
        if not isinstance(dataset.get(field), str) or not dataset[field]:
            raise ValueError(f"runSpec.dataset.{field} is required")
    for field in ("id", "version"):
        if not SAFE_COMPONENT_RE.fullmatch(dataset[field]):
            raise ValueError(f"runSpec.dataset.{field} is invalid")
    if dataset.get("frequency", "daily") != "daily":
        raise ValueError("runSpec.dataset.frequency must be daily")
    if dataset.get("sourceType") != "clickhouse":
        raise DatasetContractError("DATASET_SOURCE_UNSUPPORTED", "runSpec dataset source is not clickhouse")
    if "manifest" not in dataset:
        raise DatasetContractError("DATASET_MANIFEST_MISSING", "runSpec dataset Manifest is required")
    if not isinstance(dataset.get("manifest"), dict):
        raise DatasetContractError("DATASET_MANIFEST_INVALID", "runSpec dataset Manifest is invalid")

    date_range = run_spec.get("dateRange")
    if not isinstance(date_range, dict) or not date_range.get("start") or not date_range.get("end"):
        raise ValueError("runSpec.dateRange is required")
    if not isinstance(run_spec.get("parameters", {}), dict):
        raise ValueError("runSpec.parameters must be an object")
    validated = ValidatedRunSpec(run_spec)
    validated["symbols"] = symbols
    return validated
