from datetime import date
import unittest

import pandas as pd

from m.trader.trader_v2 import TraderV2


def make_data(*dates):
    return {
        "AAA": pd.DataFrame(
            {
                "date": list(dates),
                "open": [10.0 + index for index, _ in enumerate(dates)],
                "high": [11.0 + index for index, _ in enumerate(dates)],
                "low": [9.0 + index for index, _ in enumerate(dates)],
                "close": [10.5 + index for index, _ in enumerate(dates)],
                "volume": [1000 for _ in dates],
            }
        )
    }


def build_engine(data, **callbacks):
    no_op = lambda *args: None
    return TraderV2(
        data=data,
        start_date="2024-01-01",
        end_date="2024-01-03",
        initialize=callbacks.get("initialize", no_op),
        before_trading_start=callbacks.get("before_trading_start", no_op),
        handle_data=callbacks.get("handle_data", no_op),
        handle_tick=no_op,
        handle_trade=callbacks.get("handle_trade", no_op),
        handle_order=callbacks.get("handle_order", no_op),
        after_trading=callbacks.get("after_trading", no_op),
        plot_charts=False,
    )


class TraderV2Tests(unittest.TestCase):
    def test_current_price_uses_first_bar_before_array_manager_warmup(self):
        engine = build_engine(make_data("2024-01-01"))
        engine.array_managers["AAA"].update_bar(
            engine.data["AAA"].iloc[0]
        )

        self.assertEqual(engine._get_current_price("AAA", "close"), 10.5)

    def test_engine_order_is_callable(self):
        engine = build_engine(make_data("2024-01-01"))
        engine.array_managers["AAA"].update_bar(
            engine.data["AAA"].iloc[0]
        )

        order = engine.order("AAA", 100)

        self.assertEqual(order["status"], "filled")
        self.assertEqual(engine.order_manager.get_position("AAA")["volume"], 100)

    def test_context_order_updates_portfolio_and_callbacks(self):
        events = []

        def handle_order(context, order):
            events.append(("order", order["status"]))

        def handle_trade(context, trade):
            events.append(("trade", trade["direction"]))

        engine = build_engine(
            make_data("2024-01-01"),
            handle_order=handle_order,
            handle_trade=handle_trade,
        )
        engine.array_managers["AAA"].update_bar(
            engine.data["AAA"].iloc[0]
        )
        result = engine.context["order"].buy(
            "AAA", 10.0, 100, timestamp=date(2024, 1, 1)
        )

        self.assertTrue(result["success"])
        self.assertEqual(engine.context["portfolio"]["positions"]["AAA"], 100)
        self.assertLess(engine.context["portfolio"]["cash"], engine.capital_base)
        self.assertEqual(events, [("order", "filled"), ("trade", "buy")])

    def test_context_order_uses_current_datetime_when_timestamp_is_omitted(self):
        engine = build_engine(make_data("2024-01-01"))
        engine.current_datetime = date(2024, 1, 1)
        engine.context["current_datetime"] = engine.current_datetime
        engine.array_managers["AAA"].update_bar(engine.data["AAA"].iloc[0])

        engine.context["order"].buy("AAA", 10.0, 100)

        self.assertEqual(
            engine.order_manager.get_trade_history()[-1]["timestamp"],
            date(2024, 1, 1),
        )

    def test_empty_data_can_run_without_unbound_daily_data(self):
        engine = build_engine({})

        context = engine.run()

        self.assertEqual(context["portfolio"]["total_value"], engine.capital_base)

    def test_dates_use_union_when_stocks_have_different_histories(self):
        data = make_data("2024-01-01", "2024-01-02")
        data["BBB"] = data["AAA"].iloc[[1]].copy()
        engine = build_engine(data)

        self.assertEqual(
            engine.dates,
            [date(2024, 1, 1), date(2024, 1, 2)],
        )

    def test_after_trading_marks_existing_positions_to_latest_close(self):
        data = make_data("2024-01-01", "2024-01-02")
        values = []

        def handle_data(context, daily_data):
            if context["current_datetime"] == date(2024, 1, 1):
                context["order"].buy("AAA", 10.0, 100)

        def after_trading(context):
            values.append(context["portfolio"]["total_value"])

        engine = build_engine(
            data,
            handle_data=handle_data,
            after_trading=after_trading,
        )
        engine.run()

        self.assertEqual(len(values), 2)
        self.assertGreater(values[1], values[0])


if __name__ == "__main__":
    unittest.main()
