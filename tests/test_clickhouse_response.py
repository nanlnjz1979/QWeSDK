import unittest

from m.clickhouse_response import parse_json_each_row


class ClickHouseResponseTests(unittest.TestCase):
    def test_parses_json_each_row_into_objects(self):
        self.assertEqual(
            parse_json_each_row('{"code":"000001.SZ"}\n{"code":"600000.SH"}\n'),
            [{"code": "000001.SZ"}, {"code": "600000.SH"}],
        )

    def test_ignores_blank_lines(self):
        self.assertEqual(parse_json_each_row("\n {\"code\":\"000001.SZ\"}\n"), [{"code": "000001.SZ"}])

    def test_rejects_malformed_json(self):
        with self.assertRaisesRegex(ValueError, "line 2"):
            parse_json_each_row('{"code":"000001.SZ"}\nnot-json\n')

    def test_rejects_non_object_rows(self):
        with self.assertRaisesRegex(ValueError, "object"):
            parse_json_each_row('[]\n')


if __name__ == "__main__":
    unittest.main()
