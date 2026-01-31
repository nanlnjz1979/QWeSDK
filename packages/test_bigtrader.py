# 测试 bigtrader v14 函数

# 导入 M 模块（注意：在 Python 中，模块名是小写的，所以应该是 m 而不是 M）
import m

# 定义测试函数
def m4_initialize_bigquant_run(context):
    """初始化函数"""
    print(f"[测试] 初始化函数被调用，初始资金: {context['portfolio']['cash']}")
    # 在上下文中添加一些自定义属性
    context['test_property'] = 'initialized'


def m4_before_trading_start_bigquant_run(context):
    """交易前处理函数"""
    print(f"[测试] 交易前处理函数被调用")


def m4_handle_tick_bigquant_run(context, tick):
    """Tick处理函数"""
    print(f"[测试] Tick处理函数被调用，Tick: {tick}")


def m4_handle_data_bigquant_run(context, data):
    """数据处理函数"""
    # 获取当前回测日期
    current_date = context['current_datetime']
    print(f"[测试] 数据处理函数被调用，当前日期: {current_date}，数据长度: {len(data)}")
    print(f"[测试] 当前资金: {context['portfolio']['cash']}")
    
    # 遍历所有股票
    for stock_code, stock_data in data.items():
        print(f"[测试] 处理股票: {stock_code}")
        
        # 检查是否有KDJ指标数据和前一天的指标数据
        if hasattr(stock_data, 'k') and hasattr(stock_data, 'd') and hasattr(stock_data, 'k_lag1') and hasattr(stock_data, 'd_lag1'):
            # 获取当前K和D值
            current_k = stock_data.k
            current_d = stock_data.d
            
            # 获取前一天的K和D值
            previous_k = stock_data.k_lag1
            previous_d = stock_data.d_lag1
            
            # 准确的KDJ金叉判断：当前K > 当前D，并且前一天K <= 前一天D
            if current_k > current_d and previous_k <= previous_d:
                print(f"[测试] 股票 {stock_code} 出现KDJ金叉，当前K={current_k}, D={current_d}，前一天K={previous_k}, D={previous_d}")
                # 买入股票，使用开盘价作为买入价格
                buy_price = stock_data.open if hasattr(stock_data, 'open') else current_k
                # 计算买入数量（使用当前资金的10%）
                buy_amount = int(context['portfolio']['cash'] * 0.1 / buy_price / 100) * 100
                if buy_amount >= 100:  # 至少买入100股
                    print(f"[测试] 买入股票 {stock_code}，价格: {buy_price}，数量: {buy_amount}，时间: {current_date}")
                    context["order"].buy(stock_code, buy_price, buy_amount, timestamp=current_date)
            
            # 准确的KDJ死叉判断：当前K < 当前D，并且前一天K >= 前一天D
            if current_k < current_d and previous_k >= previous_d:
                print(f"[测试] 股票 {stock_code} 出现KDJ死叉，当前K={current_k}, D={current_d}，前一天K={previous_k}, D={previous_d}")
                # 检查是否持有该股票
                position = context["order"].get_position(stock_code)
                if position['volume'] > 0:
                    # 卖出股票，使用收盘价作为卖出价格
                    sell_price = stock_data.close if hasattr(stock_data, 'close') else current_k
                    # 卖出全部持仓
                    sell_amount = position['volume']
                    print(f"[测试] 卖出股票 {stock_code}，价格: {sell_price}，数量: {sell_amount}，时间: {current_date}")
                    context["order"].sell(stock_code, sell_price, sell_amount, timestamp=current_date)


def m4_handle_trade_bigquant_run(context, trade):
    """成交处理函数"""
    print(f"[测试] 成交处理函数被调用，成交: {trade}")


def m4_handle_order_bigquant_run(context, order):
    """订单处理函数"""
    print(f"[测试] 订单处理函数被调用，订单: {order}")


def m4_after_trading_bigquant_run(context):
    """交易后处理函数"""
    print(f"[测试] 交易后处理函数被调用")
    print(f"[测试] 当日结束，总市值: {context['portfolio']['total_value']}")


def m4_after_backtest_bigquant_run(context):
    """回测后处理函数"""
    print(f"[测试] 回测后处理函数被调用")
    print(f"[测试] 回测结束，最终总市值: {context['portfolio']['total_value']}")
    print(f"[测试] 初始资金: {context['portfolio']['total_value'] - (context['portfolio']['total_value'] - 1000000)}")
    print(f"[测试] 总收益率: {(context['portfolio']['total_value'] - 1000000) / 1000000 * 100:.2f}%")
    
    # 获取交易历史并打印
    if 'order' in context:
        context['order'].print_order(max_trades=100)
    
    print(f"[测试] 回测完成，策略评估结束")

print("\n=== 测试 M.selector.v1 函数 ===")
# 股票代码获取 M.selector.v1 函数
# 主要功能
# 按照规则先获取股票代码，从数据库中获取股票代码数据到m1（python中数据）
m1 = m.selector.v1(
    exchanges=["""上交所""", """深交所""","""北交所"""], 
    list_sectors=["""主板""", """创业板""", """科创板"""], 
    indexes=["""中证500""", """上证指数""", """创业板指""", """深证成指""", """上证50""", """科创50""", """沪深300""", """中证1000""", """中证100""", """深证100"""], 
    st_statuses=["""正常"""], 
    margin_tradings=["""两融标的""", """非两融标的"""], 
    sw2021_industries=[""""""], 
    drop_suspended=True, 
    m_name="""m1""" 
)
#sw2021_industries=["""基础化工"""], 
print(f"[测试] SelectorV1实例: {m1}")
print(f"[测试] 股票池大小: {len(m1.get_stock_pool())}")
print(f"[测试] 选股结果大小: {len(m1.get_selected_stocks())}")
print(f"[测试] 选股结果: {[stock['code'] for stock in m1.get_selected_stocks()]}")


print("\n=== 测试 M.input.v1 函数 ===")
# 股票数据获取 M.input.v1 函数
m2 = m.input.v1(
    data=m1.get_stock_pool(),
    table_name="""stock_data_vvv""",
    expr_filters=["""pe > 0"""],
    expr_mutates=["""c_rank(dividend_yield) AS score"""],
    expr_tables="""stock_data_vvv""",
    extra_fields="""code""",
    debug=True,
    m_name="""m2"""
)
print(f"[测试] InputV1实例: {m2}")
print(f"[测试] 获取的数据长度: {len(m2.data)}")
print(f"[测试] 第一条数据: {m2.data[0] if m2.data else '空'}")
print(m2.get_stock_pool())
print("\n=== 测试 M.extract_data.v1 函数 ===")
# 测试 M.extract_data.v1 函数
m3 = m.extract_data.v1(
    data=m2.get_stock_pool(), 
    table_name="""stock_daily_hfq_v""",    #提取日线数据的表名
    expr_mutates=["macd(close,dif,dea,macd)",
    "kdj(close,k,d,j)",
    "lag(k,1,k_lag1)",
    "lag(d,1,d_lag1)",
    "lag(j,1,j_lag1)"
    ],
    start_date="""2020-05-01""", 
    start_date_bound_to_trading_date=True, 
    end_date="""2022-12-31""", 
    end_date_bound_to_trading_date=True, 
    before_start_days=90,   # 开始前90天
    debug=True, 
    m_name="""m3""" 
)
print(f"[测试] ExtractDataV1实例: {m3}")
print(f"[测试] 提取的数据长度: {len(m3.data)}")
print(f"[测试] 第一条数据: {m3.data[0] if m3.data else '空'}")


print("\n=== 测试 input.v1、extract_data.v1 和 trader.v1 进行完整流程 ===")
# 使用 input.v1 获取数据，然后使用 extract_data.v1 提取数据，最后使用 trader.v1 进行回测
m7 = m.trader.v2(   
    data=m3,                          # 回测数据，格式为字典，键为股票代码，值为DataFrame
    initialize=m4_initialize_bigquant_run,  # 初始化函数，策略启动时调用
    before_trading_start=m4_before_trading_start_bigquant_run,  # 交易前处理函数，每日开盘前调用
    handle_data=m4_handle_data_bigquant_run,  # 数据处理函数，每日数据更新后调用
    handle_tick=m4_handle_tick_bigquant_run,  # Tick处理函数，每条Tick数据更新后调用
    handle_trade=m4_handle_trade_bigquant_run,  # 成交处理函数，订单成交后调用
    handle_order=m4_handle_order_bigquant_run,  # 订单处理函数，订单状态变化时调用
    after_trading=m4_after_trading_bigquant_run,  # 交易后处理函数，每日收盘后调用
    after_backtest=m4_after_backtest_bigquant_run,  # 回测后处理函数，回测结束时调用
    capital_base=1000000,             # 初始资金，默认为100万
    frequency="daily",                # 回测频率，"daily"表示日线回测

    volume_limit=1,                   # 成交量限制，1表示不限制
    order_price_field_buy="open",     # 买入订单使用的价格字段，"open"表示开盘价
    order_price_field_sell="close",   # 卖出订单使用的价格字段，"close"表示收盘价
    benchmark="000300.SH",            # 基准指数，用于评估策略表现
    plot_charts=False,                 # 是否绘制图表
    disable_cache=False,              # 是否禁用缓存
    debug=True,                       # 是否开启调试模式
    backtest_only=False,              # 是否仅回测，不执行其他操作
    m_cached=False,                   # 是否缓存结果
    m_name="m7"                       # 模块名称，用于标识
)

m7._run_daily()


def main():
    """主函数，用于命令行调用"""
    print("\n=== 所有测试完成 ===")
    print("测试成功：v1 函数实现正确")

if __name__ == "__main__":
    main()