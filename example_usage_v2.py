"""通过 Helix DataLoader 运行 QWeSDK V2 策略的示例。"""

import m


DEFAULT_SYMBOLS = ["000001.SZ", "600000.SH", "000300.SH"]
EXTRACT_EXPRESSIONS = [
    "macd(close,dif,dea,macd)",
    "kdj(close,k,d,j)",
    "lag(k,1,k_lag1)",
    "lag(d,1,d_lag1)",
    "lag(j,1,j_lag1)",
]


def initialize(context):
    print(f"[V2] 初始资金: {context['portfolio']['cash']}")


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


def after_backtest(context):
    print(f"[V2] 最终权益: {context['portfolio']['total_value']}")


def main(runtime):
    """Worker 调用的唯一脚本入口；日期和物理表均由运行时冻结。"""
    symbols = runtime.parameters.get("symbols") or DEFAULT_SYMBOLS
    data = runtime.extract_data(symbols, expressions=EXTRACT_EXPRESSIONS)
    print(f"[V2] 数据加载: {len(data)} 只股票，{runtime.start_date} 至 {runtime.end_date}")
    return m.trader.v2(
        data=data,
        start_date=runtime.start_date,
        end_date=runtime.end_date,
        initialize=initialize,
        before_trading_start=before_trading_start,
        handle_data=handle_data,
        handle_tick=lambda context, tick: None,
        handle_trade=handle_trade,
        handle_order=handle_order,
        after_trading=after_trading,
        after_backtest=after_backtest,
        capital_base=float(runtime.parameters.get("capitalBase", 1000000)),
        frequency="daily",
        plot_charts=False,
        debug=False,
        backtest_only=True,
        m_name="example_v2",
    )


if __name__ == "__main__":
    import os

    from m.config import GlobalConfig
    from m.data_access.catalog import create_data_loader
    from m.data_access.clickhouse import manifest_hash
    from m.worker.backtest import build_script_runtime

    # VS Code 直接运行没有 Helix RunSpec。这里按本地 ClickHouse 表组装同一个 runtime。
    GlobalConfig.load_config()
    host, port = GlobalConfig.DATABASE_IP.split(":", 1)
    os.environ["QWESDK_CLICKHOUSE_URL"] = f"http://{host}:{port}"
    os.environ["QWESDK_CLICKHOUSE_USER"] = GlobalConfig.DATABASE_USER
    os.environ["QWESDK_CLICKHOUSE_PASSWORD"] = GlobalConfig.DATABASE_PASSWORD
    symbols = ["000001", "600000", "600519"]
    manifest = {
        "datasetId": "local",
        "releaseVersion": "local",
        "sourceType": "clickhouse",
        "storageMode": "current_view",
        "components": {"daily": {"database": "default", "tables": {
            "none": "stock_daily",
            "qfq": "stock_daily_qfq_v",
            "hfq": "stock_daily_hfq_v",
        }}},
        "coverage": {"start": "2010-01-01", "end": "2030-12-31"},
    }
    manifest["manifestHash"] = manifest_hash(manifest)
    dataset = {
        "id": "local",
        "version": "local",
        "sourceType": "clickhouse",
        "adjustmentMode": "hfq",
        "manifestHash": manifest["manifestHash"],
        "manifest": manifest,
    }
    runtime = build_script_runtime(
        dataset,
        {"start": "2022-01-01", "end": "2022-03-31"},
        manifest=manifest,
        data_loader=create_data_loader(dataset),
        before_start_days=30,
        symbols=symbols,
        parameters={"symbols": symbols, "capitalBase": 1000000},
    )
    main(runtime).run()
