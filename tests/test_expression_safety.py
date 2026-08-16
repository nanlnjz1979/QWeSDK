import unittest

from m.db.expression_safety import safe_eval


class ExpressionSafetyTests(unittest.TestCase):
    def test_allows_arithmetic_and_whitelisted_function_calls(self):
        namespace = {
            "value": 3,
            "double": lambda number: number * 2,
        }

        result = safe_eval("double(value) + 1", namespace)

        self.assertEqual(result, 7)

    def test_rejects_attribute_access(self):
        with self.assertRaisesRegex(ValueError, "attribute"):
            safe_eval("value.__class__", {"value": 3})

    def test_rejects_unknown_names_and_builtins(self):
        with self.assertRaisesRegex(ValueError, "name"):
            safe_eval("__import__('os')", {})

    def test_rejects_comprehensions_and_lambda_expressions(self):
        with self.assertRaises(ValueError):
            safe_eval("[value for value in values]", {"values": [1, 2]})

        with self.assertRaises(ValueError):
            safe_eval("(lambda value: value)(1)", {})


if __name__ == "__main__":
    unittest.main()
