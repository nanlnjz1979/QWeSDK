import hashlib
import json
from datetime import date

import pytest

from backtest_runner import build_script_runtime, load_script_module
from worker_protocol import validate_run_spec


def test_script_entry_requires_main_function():
    with pytest.raises(ValueError, match="main"):
        load_script_module("def initialize(context): pass", "qwesdk_script_v1")


def test_script_runtime_freezes_dataset_dates_and_exposes_loader():
    dataset = {
        "id": "cn-stock-daily",
        "version": "20260831",
        "manifestHash": "sha256:manifest",
        "adjustmentMode": "hfq",
    }
    runtime = build_script_runtime(
        dataset,
        {"start": "2025-08-29", "end": "2026-08-29"},
        manifest={"datasetId": "cn-stock-daily", "releaseVersion": "20260831"},
        data_loader=object(),
        before_start_days=30,
    )

    assert runtime.start_date == date(2025, 8, 29)
    assert runtime.end_date == date(2026, 8, 29)
    assert runtime.warmup_start_date == date(2025, 7, 30)
    assert runtime.dataset == dataset
    assert runtime.data_loader is not None


def test_script_module_main_receives_runtime():
    module = load_script_module("def main(runtime):\n    return runtime", "qwesdk_script_v1")
    marker = object()
    assert module.main(marker) is marker


def test_script_runtime_extracts_from_loader_using_warmup_range():
    class Loader:
        def __init__(self):
            self.calls = []

        def load_daily(self, symbols, start_date, end_date, fields=None, adjustment_mode=None):
            self.calls.append((symbols, start_date, end_date, fields, adjustment_mode))
            import pandas as pd
            return {symbols[0]: pd.DataFrame({
                "date": pd.date_range(start_date, end_date, freq="D"),
                "open":  [1.0] * ((end_date - start_date).days + 1),
                "high":  [1.0] * ((end_date - start_date).days + 1),
                "low":   [1.0] * ((end_date - start_date).days + 1),
                "close": [1.0] * ((end_date - start_date).days + 1),
                "volume": [100] * ((end_date - start_date).days + 1),
            })}

    loader = Loader()
    runtime = build_script_runtime(
        {"adjustmentMode": "none"},
        {"start": "2024-01-10", "end": "2024-01-12"},
        manifest={}, data_loader=loader, before_start_days=3,
    )

    data = runtime.extract_data(["AAA"], expressions=[])

    assert len(data["AAA"]) == 6
    assert loader.calls[0][1] == date(2024, 1, 7)
    assert loader.calls[0][2] == date(2024, 1, 12)


def test_worker_protocol_accepts_script_entry_point():
    code = "def main(runtime):\n    return runtime"
    spec = {
        "schemaVersion": "1.0",
        "runId": "bt-script-001",
        "strategyCode": code,
        "strategyCodeHash": "sha256:" + hashlib.sha256(code.encode()).hexdigest(),
        "strategyEntryPoint": "qwesdk_script_v1",
        "dataset": {
            "id": "cn-stock-daily",
            "version": "20260831",
            "manifestHash": "sha256:manifest",
            "adjustmentMode": "hfq",
            "frequency": "daily",
            "sourceType": "clickhouse",
        },
        "dateRange": {"start": "2025-08-29", "end": "2026-08-29"},
        "parameters": {},
    }

    assert validate_run_spec(spec)["strategyEntryPoint"] == "qwesdk_script_v1"
