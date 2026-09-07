import hashlib
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from backtest_runner import run_backtest_spec
from data_catalog import load_dataset
from worker_protocol import EventStream, validate_run_spec


def strategy_code():
    return """
def initialize(context):
    context['parameters_seen'] = context['parameters']

def handle_data(context, data):
    if context['current_datetime'].isoformat() == '2024-01-01' and 'AAA' in data:
        context['order'].buy('AAA', float(data['AAA']['close']), 100)
""".strip()


def run_spec(data_root: Path) -> dict:
    code = strategy_code()
    return {
        'schemaVersion': '1.0',
        'runId': 'bt-fixture-001',
        'strategyVersionId': 'sv-fixture-001',
        'strategyCode': code,
        'strategyCodeHash': 'sha256:' + hashlib.sha256(code.encode()).hexdigest(),
        'strategyEntryPoint': 'qwesdk_callback_v1',
        'parameters': {'shortWindow': 5},
        'dataset': {
            'id': 'fixture-daily',
            'version': 'v1',
            'manifestHash': 'sha256:fixture',
            'sourceType': 'clickhouse',
            'manifest': {
                'datasetId': 'fixture-daily',
                'releaseVersion': 'v1',
                'sourceType': 'clickhouse',
                'storageMode': 'immutable_table',
            },
            'adjustmentMode': 'none',
            'frequency': 'daily',
        },
        'dateRange': {'start': '2024-01-01', 'end': '2024-01-02'},
        'initialCapital': 100000,
        'benchmark': '000300.SH',
        'limits': {'wallSeconds': 5, 'cpuSeconds': 5},
        'runtime': {'qwesdkVersion': '1.0.3', 'workerImageDigest': 'sha256:fixture'},
        'dataRoot': str(data_root),
    }


def in_memory_dataset():
    return {'AAA': pd.DataFrame([
        {'date': '2024-01-01', 'open': 10, 'high': 11, 'low': 9, 'close': 10, 'volume': 1000},
        {'date': '2024-01-02', 'open': 11, 'high': 12, 'low': 10, 'close': 12, 'volume': 1000},
    ])}


class BacktestRunnerTests(unittest.TestCase):
    def test_validates_callback_entry_and_code_hash(self):
        with tempfile.TemporaryDirectory() as directory:
            spec = run_spec(Path(directory))
            validated = validate_run_spec(spec)
            self.assertEqual(validated['runId'], 'bt-fixture-001')
            self.assertEqual(validated['strategyEntryPoint'], 'qwesdk_callback_v1')

            invalid = dict(spec, strategyCodeHash='sha256:wrong')
            with self.assertRaisesRegex(ValueError, 'strategyCodeHash'):
                validate_run_spec(invalid)

    def test_rejects_unsupported_strategy_entry_and_dataset_path(self):
        with tempfile.TemporaryDirectory() as directory:
            spec = run_spec(Path(directory))
            with self.assertRaisesRegex(ValueError, 'strategyEntryPoint'):
                validate_run_spec(dict(spec, strategyEntryPoint='arbitrary_python'))

            invalid_dataset = dict(spec)
            invalid_dataset['dataset'] = dict(spec['dataset'], id='../escape')
            with self.assertRaisesRegex(ValueError, 'dataset'):
                validate_run_spec(invalid_dataset)

    def test_rejects_non_clickhouse_dataset_without_local_file_fallback(self):
        with tempfile.TemporaryDirectory() as directory:
            spec = run_spec(Path(directory))
            spec['dataset']['sourceType'] = 'csv'
            with self.assertRaisesRegex(ValueError, 'data files|manifest'):
                load_dataset(spec['dataset'], Path(directory))

    def test_runs_trader_v2_and_returns_standard_result(self):
        with tempfile.TemporaryDirectory() as directory:
            events = EventStream('bt-fixture-001')
            with patch('backtest_runner.load_dataset', return_value=in_memory_dataset()):
                result = run_backtest_spec(run_spec(Path(directory)), events, Path(directory))

            self.assertEqual(result['status'], 'succeeded')
            self.assertEqual(result['summary']['tradeCount'], 2)
            self.assertIn('totalReturn', result['summary'])
            self.assertEqual(len(result['series']['equityCurve']), 2)
            self.assertGreaterEqual(len(result['series']['trades']), 1)
            self.assertEqual(events.events[0]['type'], 'queued')
            self.assertEqual(events.events[-1]['type'], 'succeeded')

    def test_result_records_dataset_read_time_and_storage_mode(self):
        with tempfile.TemporaryDirectory() as directory:
            spec = run_spec(Path(directory))
            spec['dataset']['manifest']['storageMode'] = 'current_view'
            with patch('backtest_runner.load_dataset', return_value=in_memory_dataset()):
                result = run_backtest_spec(spec, EventStream('bt-fixture-001'), Path(directory))

            self.assertEqual(result['runtime']['datasetStorageMode'], 'current_view')
            self.assertRegex(result['runtime']['datasetReadAt'], r'^20[0-9]{2}-[0-9]{2}-[0-9]{2}T')

    def test_prepares_example_usage_indicators_before_callback(self):
        with tempfile.TemporaryDirectory() as directory:
            dates = pd.date_range('2024-01-01', periods=45, freq='B')
            frame = pd.DataFrame({
                'date': dates,
                'open': [10 + index * 0.05 for index in range(len(dates))],
                'high': [10.5 + index * 0.05 for index in range(len(dates))],
                'low': [9.5 + index * 0.05 for index in range(len(dates))],
                'close': [10 + index * 0.05 for index in range(len(dates))],
                'volume': [1000] * len(dates),
            })
            spec = run_spec(Path(directory))
            spec['dateRange'] = {'start': '2024-02-01', 'end': '2024-02-29'}
            spec['strategyCode'] = """
def initialize(context):
    context['bought'] = False

def handle_data(context, data):
    row = data.get('AAA')
    if not context['bought'] and row is not None and hasattr(row, 'k') and row.k == row.k:
        context['order'].buy('AAA', float(row.open), 100, timestamp=context['current_datetime'])
        context['bought'] = True
""".strip()
            spec['strategyCodeHash'] = 'sha256:' + hashlib.sha256(spec['strategyCode'].encode()).hexdigest()

            with patch('backtest_runner.load_dataset', return_value={'AAA': frame}):
                result = run_backtest_spec(spec, EventStream(spec['runId']), Path(directory))

            self.assertEqual(result['status'], 'succeeded')
            self.assertGreaterEqual(result['summary']['tradeCount'], 1)

    def test_result_digest_uses_cross_language_decimal_numbers(self):
        from gateway_service import GatewayService

        result = {
            'resultId': 'res_1', 'runId': 'bt_1', 'celeryTaskId': None,
            'schemaVersion': '1.0', 'status': 'succeeded',
            'generatedAt': '2026-08-13T10:00:00Z',
            'summary': {'totalReturn': -0.19607495500000005},
            'series': {'equityCurve': [{
                'dailyReturn': -6.021447555992765e-05,
                'normalizedValue': 0.9996993999999999,
            }]},
            'warnings': {}, 'artifacts': {}, 'runtime': {'actualPoints': 7},
        }

        digest = GatewayService._result_digest(result)

        self.assertEqual(digest, 'sha256:2c3f96d6c08c37dc10406b3efcda121a350641a5c36eaa19020d29e527e44c36')

    def test_standard_trades_use_actual_cost_fields(self):
        record = {
            'order_id': 1, 'timestamp': '2024-01-01', 'stock_code': 'AAA',
            'direction': 'sell', 'price': 12, 'volume': 100,
            'commission': 1.2, 'stamp_duty': 3.4, 'transfer_fee': 0.5,
            'total_revenue': 1194.9,
        }

        from backtest_runner import _trade

        result = _trade(record)

        self.assertEqual(result['grossAmount'], 1200.0)
        self.assertEqual(result['tax'], 3.4)
        self.assertEqual(result['transferFee'], 0.5)
        self.assertEqual(result['netCashFlow'], 1194.9)

    def test_standard_trade_emits_daily_timestamp_as_utc_datetime(self):
        from backtest_runner import _trade

        result = _trade({
            'order_id': 1, 'timestamp': date(2024, 1, 1), 'stock_code': 'AAA',
            'direction': 'buy', 'price': 12, 'volume': 100,
        })

        self.assertEqual(result['executedAt'], '2024-01-01T00:00:00+00:00')


if __name__ == '__main__':
    unittest.main()
