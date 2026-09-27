import time
from unittest.mock import patch

import pandas as pd

from gateway.backtest_api import BrowserBacktestService
from m.data_access.clickhouse import manifest_hash
from gateway.gateway_service import GatewayService


class CeleryNotUsed:
    def send_task(self, *_args, **_kwargs):
        raise AssertionError("local MVP must use the real worker task implementation")


def clickhouse_manifest():
    manifest = {
        "datasetId": "fixture-daily",
        "releaseVersion": "v1",
        "sourceType": "clickhouse",
        "schemaVersion": "v1",
        "storageMode": "immutable_table",
        "components": {
            "daily": {
                "database": "default",
                "tables": {
                    "none": "fixture_daily_none",
                    "qfq": "fixture_daily_qfq",
                    "hfq": "fixture_daily_hfq",
                },
            }
        },
        "coverage": {"start": "2024-01-01", "end": "2024-12-31"},
    }
    manifest["manifestHash"] = manifest_hash(manifest)
    return manifest


def fake_clickhouse_data():
    return {"AAA": pd.DataFrame([
        {"date": "2024-01-01", "open": 10, "high": 11, "low": 9, "close": 10, "volume": 1000},
        {"date": "2024-01-02", "open": 10, "high": 12, "low": 9, "close": 12, "volume": 1000},
    ])}


def run_inline_backtest(run_spec):
    from m.worker.backtest import run_backtest_spec
    from m.worker.protocol import EventStream

    return run_backtest_spec(run_spec, EventStream(run_spec["runId"]))


def test_local_browser_run_persists_real_trader_result(tmp_path, monkeypatch):
    manifest = clickhouse_manifest()
    monkeypatch.setenv("QWESDK_INSTALL_TARGET", str(__file__).split("/gateway/")[0])
    gateway = GatewayService("secret", tmp_path / "gateway.sqlite3", CeleryNotUsed())
    browser = BrowserBacktestService(gateway, local_execution=True)

    with patch("m.worker.tasks.run_backtest.run", side_effect=run_inline_backtest), patch(
        "m.worker.backtest.load_dataset", return_value=fake_clickhouse_data()
    ) as load_dataset:
        accepted = browser.submit({
            "strategyCode": "def initialize(context):\n context['bought'] = False\ndef handle_data(context, data):\n\n if not context['bought']:\n  context['order'].buy('AAA', float(data['AAA']['close']), 100)\n  context['bought'] = True",
            "symbols": ["AAA"],
            "dataset": {
                "id": "fixture-daily",
                "version": "v1",
                "manifestHash": manifest["manifestHash"],
                "manifest": manifest,
            },
            "dateRange": {"start": "2024-01-01", "end": "2024-01-02"},
            "initialCapital": 100000,
        })
        run_id = accepted["runId"]
        deadline = time.monotonic() + 15
        status = browser.status(run_id)
        result = browser.result(run_id)
        while time.monotonic() < deadline:
            terminal = status["status"] in {"succeeded", "failed", "timed_out", "cancelled"}
            if terminal and (status["status"] != "succeeded" or result is not None):
                break
            time.sleep(0.1)
            status = browser.status(run_id)
            result = browser.result(run_id)

        load_dataset.assert_called_once()
    assert status["status"] == "succeeded"
    assert result["summary"]["tradeCount"] == 2
    assert result["series"]["equityCurve"]
    assert result["series"]["trades"][0]["grossAmount"] == 1001.0
