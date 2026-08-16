import unittest

from m.core.order_manager import OrderManager


class OrderManagerValidationTests(unittest.TestCase):
    def setUp(self):
        self.manager = OrderManager(initial_capital=100000)

    def test_rejects_fractional_volume(self):
        result = self.manager.buy("AAA", 10.0, 100.5)

        self.assertFalse(result["success"])
        self.assertIn("整数", result["message"])

    def test_rejects_volume_that_is_not_a_lot_multiple(self):
        result = self.manager.buy("AAA", 10.0, 150)

        self.assertFalse(result["success"])
        self.assertIn("整手", result["message"])

    def test_rejects_negative_sell_volume_without_changing_position(self):
        self.assertTrue(self.manager.buy("AAA", 10.0, 100)["success"])

        result = self.manager.sell("AAA", 10.0, -100)

        self.assertFalse(result["success"])
        self.assertEqual(self.manager.get_position("AAA")["volume"], 100)


if __name__ == "__main__":
    unittest.main()
