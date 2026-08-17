import urllib.parse
import unittest
import importlib
import sys
from types import SimpleNamespace
from unittest.mock import Mock, patch

from m.db.sql_safety import quote_identifier, quote_string, quote_string_list


def _query_from_url(url):
    """Decode the query parameter so assertions inspect SQL, not URL syntax."""
    return urllib.parse.parse_qs(urllib.parse.urlparse(url).query)["query"][0]


def _response():
    response = Mock()
    response.text = "code\n000001.SZ\n"
    response.status_code = 200
    return response


class SqlSafetyTests(unittest.TestCase):
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
            "SELECT * FROM `prices` WHERE code IN ('x\\' OR 1=1 --') FORMAT CSVWithNames",
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
            "AND date >= '2024-01-01' AND date <= '2024-01-31' FORMAT CSVWithNames",
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

        instance._get_stock_codes_by_stock_indexes()

        query = _query_from_url(get.call_args.args[0])
        self.assertIn("WHERE index_name IN ('x\\' OR 1=1 --')", query)


if __name__ == "__main__":
    unittest.main()
