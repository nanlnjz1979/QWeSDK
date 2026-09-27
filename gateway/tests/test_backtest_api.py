import hashlib
from unittest.mock import patch

import pytest

from gateway.backtest_api import BrowserBacktestService
from m.data_access.clickhouse import manifest_hash


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


def test_build_run_spec_hashes_strategy_and_keeps_user_parameters():
    service = BrowserBacktestService.__new__(BrowserBacktestService)
    code = "def initialize(context): pass\ndef handle_data(context, data): pass"
    payload = {
        "strategyCode": code,
        "parameters": {"window": 5},
        "symbols": ["000001.SZ"],
        "dataset": {
            "id": "cn-stock-daily",
            "version": "20260831",
            "manifestHash": clickhouse_manifest()["manifestHash"],
            "adjustmentMode": "none",
            "manifest": clickhouse_manifest(),
        },
        "dateRange": {"start": "2024-01-01", "end": "2024-01-02"},
        "initialCapital": 100000,
    }

    spec = service._build_run_spec("bt-browser-1", payload)

    assert spec["runId"] == "bt-browser-1"
    assert spec["strategyCodeHash"] == "sha256:" + hashlib.sha256(code.encode()).hexdigest()
    assert spec["parameters"] == {"window": 5}
    assert spec["dataset"]["frequency"] == "daily"


def test_validate_catalog_does_not_call_list_datasets():
    service = BrowserBacktestService.__new__(BrowserBacktestService)
    manifest = clickhouse_manifest()
    code = "def initialize(context): pass\ndef handle_data(context, data): pass"
    payload = {
        "strategyCode": code,
        "symbols": ["000001.SZ"],
        "dataset": {
            "id": "cn-stock-daily",
            "version": "20260831",
            "manifestHash": manifest["manifestHash"],
            "manifest": manifest,
        },
        "dateRange": {"start": "2024-01-01", "end": "2024-01-02"},
    }

    spec = service._build_run_spec("bt-browser-2", payload)
    with patch("backtest_api.list_datasets", side_effect=AssertionError("catalog scan is forbidden")):
        service._validate_catalog(spec)


def test_validate_catalog_rejects_missing_inline_manifest():
    service = BrowserBacktestService.__new__(BrowserBacktestService)
    manifest = clickhouse_manifest()
    payload = {
        "strategyCode": "def initialize(context): pass\ndef handle_data(context, data): pass",
        "symbols": ["000001.SZ"],
        "dataset": {
            "id": "cn-stock-daily",
            "version": "20260831",
            "manifestHash": manifest["manifestHash"],
        },
        "dateRange": {"start": "2024-01-01", "end": "2024-01-02"},
    }

    payload["dataset"]["manifest"] = manifest
    spec = service._build_run_spec("bt-browser-3", payload)
    del spec["dataset"]["manifest"]
    with pytest.raises(ValueError, match="Manifest is required"):
        service._validate_catalog(spec)
