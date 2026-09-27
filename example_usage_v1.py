"""Small real-data example using the legacy V1 trader entry point."""

import m


# stock_daily / stock_data_vv 里的 code 不带交易所后缀。
STOCK_POOL = ["000001", "600000", "600519"]
START_DATE = "2022-01-01"
END_DATE = "2022-03-31"
BEFORE_START_DAYS = 30


def initialize(context):
    print(f"[V1] 初始资金: {context['portfolio']['cash']}")


def before_trading_start(context):
    pass


def handle_data(context, data):
    for stock_code, stock_data in data.items():
        if not all(hasattr(stock_data, field) for field in ("k", "d", "k_lag1", "d_lag1")):
            continue

        if stock_data.k > stock_data.d and stock_data.k_lag1 <= stock_data.d_lag1:
            price = float(stock_data.open)
            volume = int(context["portfolio"]["cash"] * 0.1 / price / 100) * 100
            if volume >= 100:
                context["order"].buy(stock_code, price, volume)

        if stock_data.k < stock_data.d and stock_data.k_lag1 >= stock_data.d_lag1:
            position = context["order"].get_position(stock_code)
            if position["volume"] > 0:
                context["order"].sell(stock_code, float(stock_data.close), position["volume"])


def handle_trade(context, trade):
    pass


def handle_order(context, order):
    pass


def after_trading(context):
    pass


def build_data():
    selected = m.input.v1(
        data=STOCK_POOL,
        table_name="stock_data_vv",
        expr_filters=["pe > 0"],
        expr_mutates=["c_rank(dividend_yield) AS score"],
        expr_tables="stock_data_vv",
        extra_fields="code",
        debug=False,
        m_name="v1_input",
    )
    return m.extract_data.v1(
        data=selected.get_stock_pool(),
        table_name="stock_daily_hfq_v",
        expr_mutates=[
            "macd(close,dif,dea,macd)",
            "kdj(close,k,d,j)",
            "lag(k,1,k_lag1)",
            "lag(d,1,d_lag1)",
            "lag(j,1,j_lag1)",
        ],
        start_date=START_DATE,
        end_date=END_DATE,
        before_start_days=BEFORE_START_DAYS,
        debug=False,
        m_name="v1_extract",
    )


def main():
    data = build_data()
    engine = m.trader.v1(
        data=data,
        start_date=START_DATE,
        end_date=END_DATE,
        initialize=initialize,
        before_trading_start=before_trading_start,
        handle_tick=lambda context, tick: None,
        handle_data=handle_data,
        handle_trade=handle_trade,
        handle_order=handle_order,
        after_trading=after_trading,
        capital_base=1000000,
        frequency="daily",
        plot_charts=False,
        debug=False,
        backtest_only=True,
        m_name="example_v1",
    )
    engine.run()
    print(f"[V1] 回测完成: {START_DATE} 至 {END_DATE}")
    return engine


if __name__ == "__main__":
    main()
