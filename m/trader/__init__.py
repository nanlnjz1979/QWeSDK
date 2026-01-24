# 从trader_v1.py导入TraderV1类
from .trader_v1 import TraderV1
# 从trader_v2.py导入TraderV2类
from .trader_v2 import TraderV2


def v1(data, start_date, end_date, initialize, before_trading_start, 
         handle_tick, handle_data, handle_trade, handle_order, after_trading, 
         capital_base=1000000, frequency="daily", product_type="股票", 
         before_start_days=0, volume_limit=1, order_price_field_buy="open", 
         order_price_field_sell="close", benchmark="000300.SH", 
         plot_charts=True, disable_cache=False, debug=False, 
         backtest_only=False, m_cached=False, m_name="m4"):
    """
    trader v1函数，创建并返回回测引擎实例
    
    参数:
    data: 回测数据
    start_date: 回测开始日期
    end_date: 回测结束日期
    initialize: 初始化函数
    before_trading_start: 交易前处理函数
    handle_tick: tick处理函数
    handle_data: 数据处理函数
    handle_trade: 成交处理函数
    handle_order: 订单处理函数
    after_trading: 交易后处理函数
    capital_base: 初始资金
    frequency: 回测频率
    volume_limit: 成交量限制
    order_price_field_buy: 买入订单价格字段
    order_price_field_sell: 卖出订单价格字段
    benchmark: 基准指数
    plot_charts: 是否绘制图表
    disable_cache: 是否禁用缓存
    debug: 是否调试模式
    backtest_only: 是否仅回测
    m_cached: 是否缓存
    m_name: 模块名称
    
    返回:
    TraderV1实例
    """
    if start_date == None :
        start_date = data.start_date

    if end_date == None :
        end_date = data.end_date

    # 创建回测引擎实例
    engine = TraderV1(
        data=data, 
        start_date=start_date, 
        end_date=end_date, 
        initialize=initialize, 
        before_trading_start=before_trading_start, 
        handle_tick=handle_tick, 
        handle_data=handle_data, 
        handle_trade=handle_trade, 
        handle_order=handle_order, 
        after_trading=after_trading, 
        capital_base=capital_base, 
        frequency=frequency, 
        before_start_days=before_start_days, 
        volume_limit=volume_limit, 
        order_price_field_buy=order_price_field_buy, 
        order_price_field_sell=order_price_field_sell, 
        benchmark=benchmark, 
        plot_charts=plot_charts, 
        disable_cache=disable_cache, 
        debug=debug, 
        backtest_only=backtest_only, 
        m_cached=m_cached, 
        m_name=m_name
    )
    
    # 如果不是仅回测，运行回测
    if not backtest_only:
        engine.run()
    
    return engine


def v2(data,  initialize, before_trading_start, 
         handle_data,handle_tick, handle_trade, handle_order, after_trading, 
         start_date=None, end_date=None,
         after_backtest=None, 
         capital_base=1000000, frequency="daily", 
         volume_limit=1, order_price_field_buy="open", 
         order_price_field_sell="close", benchmark="000300.SH", 
         plot_charts=True, disable_cache=False, debug=False, 
         backtest_only=False, m_cached=False, m_name="m4"):
    """
    trader v2函数，创建并返回回测引擎实例
    
    参数:
    data: 回测数据
    start_date: 回测开始日期
    end_date: 回测结束日期
    initialize: 初始化函数
    before_trading_start: 交易前处理函数
    handle_data: 数据处理函数
    handle_trade: 成交处理函数
    handle_order: 订单处理函数
    after_trading: 交易后处理函数
    after_backtest: 回测后处理函数
    capital_base: 初始资金
    frequency: 回测频率
    product_type: 产品类型
    before_start_days: 开始前天数
    volume_limit: 成交量限制
    order_price_field_buy: 买入订单价格字段
    order_price_field_sell: 卖出订单价格字段
    benchmark: 基准指数
    plot_charts: 是否绘制图表
    disable_cache: 是否禁用缓存
    debug: 是否调试模式
    backtest_only: 是否仅回测
    m_cached: 是否缓存
    m_name: 模块名称
    
    返回:
    TraderV2实例
    """
    # 创建回测引擎实例
    engine = TraderV2(
        data=data, 
        start_date=start_date, 
        end_date=end_date, 
        initialize=initialize, 
        before_trading_start=before_trading_start, 
        handle_data=handle_data, 
        handle_tick=handle_tick,
        handle_trade=handle_trade, 
        handle_order=handle_order, 
        after_trading=after_trading, 
        after_backtest=after_backtest, 
        capital_base=capital_base, 
        frequency=frequency, 
        volume_limit=volume_limit, 
        order_price_field_buy=order_price_field_buy, 
        order_price_field_sell=order_price_field_sell, 
        benchmark=benchmark, 
        plot_charts=plot_charts, 
        disable_cache=disable_cache, 
        debug=debug, 
        backtest_only=backtest_only, 
        m_cached=m_cached, 
        m_name=m_name
    )
    
    # 如果不是仅回测，运行回测
    if not backtest_only:
        engine.run()
    
    return engine
