import os
import urllib.parse
import unittest
import importlib
import sys
from types import SimpleNamespace
from unittest.mock import Mock, patch

from m.db.sql_safety import quote_identifier, quote_string, quote_string_list
from m.config import GlobalConfig


def _query_from_url(url):
    """Decode the query parameter so assertions inspect SQL, not URL syntax."""
    return urllib.parse.parse_qs(urllib.parse.urlparse(url).query)["query"][0]


def _response():
    response = Mock()
    response.text = '{"code":"000001.SZ","date":"2024-01-02","close":10.5}\n'
    response.status_code = 200
    return response


class SqlSafetyTests(unittest.TestCase):
    def test_clickhouse_credentials_are_loaded_from_config(self):
        GlobalConfig.load_config()

        self.assertEqual(GlobalConfig.DATABASE_USER, "default")
        self.assertEqual(GlobalConfig.DATABASE_PASSWORD, "123456")

    def test_clickhouse_env_overrides_config_file(self):
        previous = {
            name: os.environ.get(name)
            for name in ("QWESDK_CLICKHOUSE_URL", "QWESDK_CLICKHOUSE_USER", "QWESDK_CLICKHOUSE_PASSWORD")
        }
        os.environ["QWESDK_CLICKHOUSE_URL"] = "http://clickhouse.internal:8123"
        os.environ["QWESDK_CLICKHOUSE_USER"] = "reader"
        os.environ["QWESDK_CLICKHOUSE_PASSWORD"] = "secret"
        try:
            GlobalConfig.load_config()
            self.assertEqual(GlobalConfig.DATABASE_IP, "clickhouse.internal:8123")
            self.assertEqual(GlobalConfig.DATABASE_USER, "reader")
            self.assertEqual(GlobalConfig.DATABASE_PASSWORD, "secret")
        finally:
            for name, value in previous.items():
                if value is None:
                    os.environ.pop(name, None)
                else:
                    os.environ[name] = value
            GlobalConfig.load_config()

    def test_quotes_simple_identifier(self):
        self.assertEqual(quote_identifier("stock_info_v"), "`stock_info_v`")

    def test_quotes_qualified_identifier_when_enabled(self):
        self.assertEqual(
            quote_identifier("default.stock_info_v", allow_qualified=True),
            "`default`.`stock_info_v`",
        )

    def test_rejects_sql_fragments_as_identifiers(self):
        with self.assertRaises(ValueError):
            quote_identifier("stock_info_v WHERE 1=1")

        with self.assertRaises(ValueError):
            quote_identifier("default.stock_info_v", allow_qualified=False)

    def test_escapes_clickhouse_string_literals(self):
        self.assertEqual(quote_string("O'Reilly\\data"), "'O\\'Reilly\\\\data'")

    def test_rejects_non_string_literals(self):
        with self.assertRaises(ValueError):
            quote_string(123)

    def test_quotes_string_list_without_changing_query_structure(self):
        values = ["000001.SZ", "x' OR 1=1 --"]

        self.assertEqual(
            quote_string_list(values),
            "'000001.SZ', 'x\\' OR 1=1 --'",
        )

    def test_empty_string_list_is_explicitly_empty(self):
        self.assertEqual(quote_string_list([]), "")

    @patch("requests.get")
    def test_input_quotes_table_and_stock_code(self, get):
        InputV1 = importlib.import_module("m.input.input_v1").InputV1
        get.return_value = _response()
        instance = InputV1.__new__(InputV1)
        instance.table_name = "prices"
        instance.debug = False

        instance._get_data_from_clickhouse(["x' OR 1=1 --"])

        query = _query_from_url(get.call_args.args[0])
        self.assertEqual(
            query,
            "SELECT * FROM `prices` WHERE code IN ('x\\' OR 1=1 --') FORMAT JSONEachRow",
        )
        self.assertEqual(get.call_args.kwargs["auth"], ("default", "123456"))

        self.assertEqual(
            instance._get_data_from_clickhouse(["000001.SZ"]),
            [{"code": "000001.SZ", "date": "2024-01-02", "close": 10.5}],
        )

    @patch("requests.get")
    def test_extract_quotes_table_dates_and_stock_code(self, get):
        # This query test does not need optional lark or TA-Lib dependencies.
        fake_core = SimpleNamespace(ExpressionAnalyzer=object, TA=object)
        with patch.dict(sys.modules, {"m.core": fake_core}):
            ExtractDataV1 = importlib.import_module(
                "m.extract_data.extract_data_v1"
            ).ExtractDataV1
        get.return_value = _response()
        instance = ExtractDataV1.__new__(ExtractDataV1)
        instance.table_name = "prices"
        instance.debug = False

        instance._get_data_from_clickhouse(
            ["x' OR 1=1 --"], "2024-01-01", "2024-01-31"
        )

        query = _query_from_url(get.call_args.args[0])
        self.assertEqual(
            query,
            "SELECT * FROM `prices` WHERE code IN ('x\\' OR 1=1 --') "
            "AND date >= '2024-01-01' AND date <= '2024-01-31' FORMAT JSONEachRow",
        )

        self.assertEqual(
            instance._get_data_from_clickhouse(
                ["000001.SZ"], "2024-01-01", "2024-01-31"
            ),
            [{"code": "000001.SZ", "date": "2024-01-02", "close": 10.5}],
        )

    @patch("requests.get")
    def test_selector_quotes_index_name(self, get):
        fake_db = SimpleNamespace(DBMgr=object)
        with patch.dict(sys.modules, {"m.db": fake_db}):
            SelectorV1 = importlib.import_module("m.selector.selector").SelectorV1
        get.return_value = _response()
        instance = SelectorV1.__new__(SelectorV1)
        instance.indexes = ["x' OR 1=1 --"]
        instance._ip = "127.0.0.1"

        self.assertEqual(
            instance._get_stock_codes_by_stock_indexes(),
            ["000001.SZ"],
        )

        query = _query_from_url(get.call_args.args[0])
        self.assertIn("WHERE index_name IN ('x\\' OR 1=1 --')", query)
        self.assertEqual(get.call_args.kwargs["auth"], ("default", "123456"))

    @patch("requests.get")
    def test_selector_parses_each_json_row_for_all_sources(self, get):
        fake_db = SimpleNamespace(DBMgr=object)
        with patch.dict(sys.modules, {"m.db": fake_db}):
            SelectorV1 = importlib.import_module("m.selector.selector").SelectorV1
        get.return_value = _response()
        instance = SelectorV1.__new__(SelectorV1)
        instance._ip = "127.0.0.1"
        instance.exchanges = ["上交所"]
        instance.st_statuses = ["正常"]
        instance.indexes = ["沪深300"]
        instance.sw2021_industries = ["电子"]

        self.assertEqual(instance._get_stock_codes_by_exchanges(), ["000001.SZ"])
        self.assertEqual(instance._get_stock_codes_by_stock_indexes(), ["000001.SZ"])
        self.assertEqual(instance._fetch_stocks_from_sw_index(), ["000001.SZ"])
        for call in get.call_args_list:
            self.assertIn("FORMAT JSONEachRow", _query_from_url(call.args[0]))

    @patch("requests.get")
    def test_clickhouse_json_parse_failure_returns_empty_result(self, get):
        InputV1 = importlib.import_module("m.input.input_v1").InputV1
        response = Mock()
        response.text = '{"code":"000001.SZ"}\nnot-json\n'
        response.status_code = 200
        get.return_value = response
        instance = InputV1.__new__(InputV1)
        instance.table_name = "prices"
        instance.debug = False

        self.assertEqual(instance._get_data_from_clickhouse(["000001.SZ"]), [])

    @patch("requests.get")
    def test_extract_uses_clickhouse_basic_auth(self, get):
        fake_core = SimpleNamespace(ExpressionAnalyzer=object, TA=object)
        with patch.dict(sys.modules, {"m.core": fake_core}):
            ExtractDataV1 = importlib.import_module(
                "m.extract_data.extract_data_v1"
            ).ExtractDataV1
        get.return_value = _response()
        instance = ExtractDataV1.__new__(ExtractDataV1)
        instance.table_name = "prices"
        instance.debug = False

        instance._get_data_from_clickhouse(
            ["000001.SZ"], "2024-01-01", "2024-01-31"
        )

        self.assertEqual(get.call_args.kwargs["auth"], ("default", "123456"))


if __name__ == "__main__":
    unittest.main()
