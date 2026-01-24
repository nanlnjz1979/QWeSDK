# 导入必要的类

from vnpy_ctastrategy.backtesting import BacktestingEngine
from vnpy.trader.constant import Interval, Exchange
import sys
import os

# 将项目根目录添加到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# 导入StrategyV1类
from m.strategy.strategy_v1 import StrategyV1

class TraderV1:
    """
    Trader V1 回测引擎类
    """
    def __init__(self, data, start_date, end_date, initialize, before_trading_start, 
                 handle_tick, handle_data, handle_trade, handle_order, after_trading, 
                 capital_base=1000000, frequency="daily", product_type="股票", 
                 before_start_days=0, volume_limit=1, order_price_field_buy="open", 
                 order_price_field_sell="close", benchmark="000300.SH", 
                 plot_charts=True, disable_cache=False, debug=False, 
                 backtest_only=False, m_cached=False, m_name="m4"):
        """
        初始化回测引擎
        
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
        """
        # 存储参数
        self.data = data
        self.start_date = start_date
        self.end_date = end_date
        self.initialize = initialize
        self.before_trading_start = before_trading_start
        self.handle_tick = handle_tick
        self.handle_data = handle_data
        self.handle_trade = handle_trade
        self.handle_order = handle_order
        self.after_trading = after_trading
        self.capital_base = capital_base
        self.frequency = frequency
        self.product_type = product_type
        self.before_start_days = before_start_days
        self.volume_limit = volume_limit
        self.order_price_field_buy = order_price_field_buy
        self.order_price_field_sell = order_price_field_sell
        self.benchmark = benchmark
        self.plot_charts = plot_charts
        self.disable_cache = disable_cache
        self.debug = debug
        self.backtest_only = backtest_only
        self.m_cached = m_cached
        self.m_name = m_name
        
        # 初始化上下文
        self.context = {}
        self.orders = []
        self.trades = []
        self.positions = {}
        
        # 初始化资金
        self.context['portfolio'] = {
            'cash': capital_base,
            'positions': {},
            'total_value': capital_base
        }
        
        # 标记是否已经初始化
        self.initialized = False
        
        # 当前日期时间
        self.current_datetime = None
        
        if self.debug:
            print(f"[DEBUG] TraderV1 初始化完成，模块名: {self.m_name}")
    
    def run(self):
        """
        运行回测
        """
        if self.debug:
            print(f"[DEBUG] 开始运行回测，开始日期: {self.start_date}，结束日期: {self.end_date}")
        
        # 1. 初始化策略
        if not self.initialized:
            self.initialize(self.context)
            self.initialized = True
        
        # 2. 运行回测主逻辑
        # 这里简化实现，实际回测需要根据频率和数据类型处理
        if self.frequency == "daily":
            self._run_daily()
        elif self.frequency == "tick":
            self._run_tick()
        
        if self.debug:
            print(f"[DEBUG] 回测结束")
        
        return self.context
    
    def _run_daily(self):
        """
        日线级别回测
        """
        # 简化实现，实际需要遍历日线数据
        if self.debug:
            print(f"[DEBUG] 运行日线回测")

        # 创建回测引擎
        engine = BacktestingEngine()

        engine.vt_symbol = "000100.SZ"
        engine.symbol = "000100"
        engine.exchange = Exchange.SZSE
        engine.interval = Interval.DAILY
        #engine.mode = BacktestingMode.BAR

        engine.gateway_name = "BACKTESTING" #日线回测网关，分钟线回测网关，tick回测网关，实盘网关都要不一样
        # 示例：调用before_trading_start 交易前处理函数
        self.before_trading_start(self.context)
        
        # 设置回测参数
        engine.capital = 1000000  # 初始资金
        engine.rate = 0.0001       # 手续费率
        engine.slippage = 0.2      # 滑点
        engine.size = 100          # 合约乘数
        engine.pricetick = 0.01    # 最小变动价位

        # 添加数据
        engine.history_data = self.data
        
        # 添加策略，并将TraderV1对象自身作为参数传递进去
        engine.add_strategy(StrategyV1, {'trader': self})
        
        # 运行回测
        engine.run_backtesting()
        
        # 示例：调用after_trading
        self.after_trading(self.context)
    
    def _run_tick(self):
        """
        Tick级别回测
        """
        # 简化实现，实际需要遍历tick数据
        if self.debug:
            print(f"[DEBUG] 运行Tick回测")
    

