import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import date
from unittest.mock import patch

import pandas as pd

from m.worker.backtest import run_backtest_spec
from m.data_access.clickhouse import DatasetContractError, manifest_hash
from m.data_access.catalog import load_dataset
from m.worker.protocol import EventStream, validate_run_spec


def strategy_code():
    return """
def initialize(context):
    context['parameters_seen'] = context['parameters']

def handle_data(context, data):
    if context['current_datetime'].isoformat() == '2024-01-01' and 'AAA' in data:
        context['order'].buy('AAA', float(data['AAA']['close']), 100)
""".strip()


def run_spec() -> dict:
    code = strategy_code()
    manifest = {
        'datasetId': 'fixture-daily',
        'releaseVersion': 'v1',
        'sourceType': 'clickhouse',
        'schemaVersion': 'v1',
        'storageMode': 'immutable_table',
        'components': {
            'daily': {
                'database': 'default',
                'tables': {
                    'none': 'fixture_daily_none',
                    'qfq': 'fixture_daily_qfq',
                    'hfq': 'fixture_daily_hfq',
                },
            },
        },
        'coverage': {'start': '2024-01-01', 'end': '2024-12-31'},
    }
    manifest['manifestHash'] = manifest_hash(manifest)
    return {
        'schemaVersion': '1.0',
        'runId': 'bt-fixture-001',
        'strategyVersionId': 'sv-fixture-001',
        'strategyCode': code,
        'strategyCodeHash': 'sha256:' + hashlib.sha256(code.encode()).hexdigest(),
        'strategyEntryPoint': 'qwesdk_callback_v1',
        'parameters': {'shortWindow': 5},
        'symbols': ['AAA'],
        'dataset': {
            'id': 'fixture-daily',
            'version': 'v1',
            'manifestHash': manifest['manifestHash'],
            'sourceType': 'clickhouse',
            'manifest': manifest,
            'adjustmentMode': 'none',
            'frequency': 'daily',
        },
        'dateRange': {'start': '2024-01-01', 'end': '2024-01-02'},
        'initialCapital': 100000,
        'benchmark': '000300.SH',
        'limits': {'wallSeconds': 5, 'cpuSeconds': 5},
        'runtime': {'qwesdkVersion': '1.0.3', 'workerImageDigest': 'sha256:fixture'},
    }


def in_memory_dataset():
    return {'AAA': pd.DataFrame([
        {'date': '2024-01-01', 'open': 10, 'high': 11, 'low': 9, 'close': 10, 'volume': 1000},
        {'date': '2024-01-02', 'open': 11, 'high': 12, 'low': 10, 'close': 12, 'volume': 1000},
    ])}


class BacktestRunnerTests(unittest.TestCase):
    def test_validates_callback_entry_and_code_hash(self):
        with tempfile.TemporaryDirectory() as directory:
            spec = run_spec()
            validated = validate_run_spec(spec)
            self.assertEqual(validated['runId'], 'bt-fixture-001')
            self.assertEqual(validated['strategyEntryPoint'], 'qwesdk_callback_v1')
            manifest = validated['dataset']['manifest']
            self.assertEqual(set(manifest['components']['daily']['tables']), {'none', 'qfq', 'hfq'})
            self.assertEqual(manifest['manifestHash'], manifest_hash(manifest))

            invalid = dict(spec, strategyCodeHash='sha256:wrong')
            with self.assertRaisesRegex(ValueError, 'strategyCodeHash'):
                validate_run_spec(invalid)

    def test_rejects_unsupported_strategy_entry_and_dataset_path(self):
        with tempfile.TemporaryDirectory() as directory:
            spec = run_spec()
            with self.assertRaisesRegex(ValueError, 'strategyEntryPoint'):
                validate_run_spec(dict(spec, strategyEntryPoint='arbitrary_python'))

            invalid_dataset = dict(spec)
            invalid_dataset['dataset'] = dict(spec['dataset'], id='../escape')
            with self.assertRaisesRegex(ValueError, 'dataset'):
                validate_run_spec(invalid_dataset)

    def test_rejects_non_clickhouse_dataset_without_local_file_fallback(self):
        with tempfile.TemporaryDirectory() as directory:
            spec = run_spec()
            spec['dataset']['sourceType'] = 'csv'
            from m.data_access.clickhouse import DatasetContractError

            with self.assertRaisesRegex(DatasetContractError, 'source is not clickhouse') as context:
                load_dataset(spec['dataset'])
            self.assertEqual(context.exception.code, 'DATASET_SOURCE_UNSUPPORTED')

    def test_requires_and_normalizes_top_level_symbols(self):
        spec = run_spec()
        spec['symbols'] = [' AAA ', 'AAA', 'BBB']

        validated = validate_run_spec(spec)

        self.assertEqual(validated['symbols'], ['AAA', 'BBB'])
        self.assertEqual(validate_run_spec(dict(spec, symbols=[]))['symbols'], [])

    def test_loads_only_the_top_level_symbols(self):
        spec = run_spec()
        spec['symbols'] = ['AAA']
        spec['dataset']['symbols'] = ['WRONG']
        with patch('m.worker.backtest.load_dataset', return_value=in_memory_dataset()) as load:
            run_backtest_spec(spec, EventStream(spec['runId']))

        self.assertEqual(load.call_args.kwargs['symbols'], ['AAA'])

    def test_loads_stock_pool_from_strategy_when_request_symbols_are_empty(self):
        spec = run_spec()
        spec['strategyCode'] = strategy_code() + '\nSTOCK_POOL = ["AAA"]\n'
        spec['strategyCodeHash'] = 'sha256:' + hashlib.sha256(spec['strategyCode'].encode()).hexdigest()
        spec['symbols'] = []
        with patch('m.worker.backtest.load_dataset', return_value=in_memory_dataset()) as load:
            run_backtest_spec(spec, EventStream(spec['runId']))

        self.assertEqual(load.call_args.kwargs['symbols'], ['AAA'])

    def test_loads_symbols_returned_by_select_stocks(self):
        spec = run_spec()
        spec['strategyCode'] = strategy_code() + '\n\ndef select_stocks():\n    return ["AAA"]\n'
        spec['strategyCodeHash'] = 'sha256:' + hashlib.sha256(spec['strategyCode'].encode()).hexdigest()
        spec['symbols'] = []
        with patch('m.worker.backtest.load_dataset', return_value=in_memory_dataset()) as load:
            run_backtest_spec(spec, EventStream(spec['runId']))

        self.assertEqual(load.call_args.kwargs['symbols'], ['AAA'])

    def test_worker_task_returns_sanitized_strategy_failure(self):
        from m.worker import tasks

        spec = run_spec()
        spec['strategyCode'] = 'raise ValueError("secret")'
        spec['strategyCodeHash'] = 'sha256:' + hashlib.sha256(spec['strategyCode'].encode()).hexdigest()
        script = tasks._r8_sandbox_code(spec)
        environment = dict(os.environ, QWESDK_INSTALL_TARGET=os.getcwd())
        completed = subprocess.run([sys.executable, '-c', script], capture_output=True, text=True,
                                   env=environment, check=False)

        events, result = tasks._read_r8_output(completed.stdout)
        self.assertEqual(result['errorCode'], 'STRATEGY_EXECUTION_FAILED')
        self.assertNotIn('secret', json.dumps(result))

    def test_runs_trader_v2_and_returns_standard_result(self):
        with tempfile.TemporaryDirectory() as directory:
            events = EventStream('bt-fixture-001')
            with patch('m.worker.backtest.load_dataset', return_value=in_memory_dataset()):
                result = run_backtest_spec(run_spec(), events)

            self.assertEqual(result['status'], 'succeeded')
            self.assertEqual(result['summary']['tradeCount'], 2)
            self.assertIn('totalReturn', result['summary'])
            self.assertEqual(len(result['series']['equityCurve']), 2)
            candles = result['series']['returnCandles']
            self.assertEqual([candle['date'] for candle in candles], ['2024-01-01', '2024-01-02'])
            self.assertEqual(candles[0]['open'], 0)
            self.assertLess(candles[1]['open'], candles[1]['close'])
            self.assertGreater(candles[1]['high'], max(candles[1]['open'], candles[1]['close']))
            self.assertLess(candles[1]['low'], min(candles[1]['open'], candles[1]['close']))
            self.assertGreaterEqual(len(result['series']['trades']), 1)
            self.assertEqual(events.events[0]['type'], 'queued')
            self.assertEqual(events.events[-1]['type'], 'succeeded')
            messages = [event['payload'].get('message') for event in events.events if event['type'] == 'log']
            self.assertIn('正在读取数据', messages)
            self.assertIn('开始回测', messages)
            self.assertIn('回测完成', messages)

    def test_logs_data_loading_before_the_dataset_read_fails(self):
        events = EventStream('bt-fixture-001')
        with patch('m.worker.backtest.load_dataset', side_effect=DatasetContractError(
                'CLICKHOUSE_UNAVAILABLE', 'ClickHouse is unavailable')):
            with self.assertRaises(DatasetContractError):
                run_backtest_spec(run_spec(), events)

        self.assertEqual(events.events[0]['type'], 'queued')
        messages = [event['payload'].get('message') for event in events.events if event['type'] == 'log']
        self.assertEqual(messages[0], '任务已提交，等待执行')
        self.assertIn('正在读取数据', messages)

    def test_result_records_dataset_read_time_and_storage_mode(self):
        with tempfile.TemporaryDirectory() as directory:
            spec = run_spec()
            spec['dataset']['manifest']['storageMode'] = 'current_view'
            spec['dataset']['manifestHash'] = manifest_hash(spec['dataset']['manifest'])
            spec['dataset']['manifest']['manifestHash'] = spec['dataset']['manifestHash']
            with patch('m.worker.backtest.load_dataset', return_value=in_memory_dataset()):
                result = run_backtest_spec(spec, EventStream('bt-fixture-001'))

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
            spec = run_spec()
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

            with patch('m.worker.backtest.load_dataset', return_value={'AAA': frame}):
                result = run_backtest_spec(spec, EventStream(spec['runId']))

            self.assertEqual(result['status'], 'succeeded')
            self.assertGreaterEqual(result['summary']['tradeCount'], 1)

    def test_result_digest_uses_cross_language_decimal_numbers(self):
        from gateway.gateway_service import GatewayService

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

        from m.worker.backtest import _trade

        result = _trade(record)

        self.assertEqual(result['grossAmount'], 1200.0)
        self.assertEqual(result['tax'], 3.4)
        self.assertEqual(result['transferFee'], 0.5)
        self.assertEqual(result['netCashFlow'], 1194.9)

    def test_standard_trade_emits_daily_timestamp_as_utc_datetime(self):
        from m.worker.backtest import _trade

        result = _trade({
            'order_id': 1, 'timestamp': date(2024, 1, 1), 'stock_code': 'AAA',
            'direction': 'buy', 'price': 12, 'volume': 100,
        })

        self.assertEqual(result['executedAt'], '2024-01-01T00:00:00+00:00')


if __name__ == '__main__':
    unittest.main()
