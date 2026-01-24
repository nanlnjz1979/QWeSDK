from vnpy_ctastrategy import CtaTemplate, StopOrder, TickData, BarData,TradeData, OrderData, BarGenerator, ArrayManager
from vnpy.trader.constant import Direction, Offset, Exchange


class StrategyV1(CtaTemplate):
    """
    策略类 V1，不包含任何功能
    """
    # 策略作者
    author = "default"
    
    # 策略参数
    parameters = []
    variables = []
    
    def __init__(self, cta_engine, strategy_name, vt_symbol, setting):
        """初始化策略"""
        super().__init__(cta_engine, strategy_name, vt_symbol, setting)
        # 添加trader属性，用于保存TraderV1对象
        self.trader = setting.get('trader', None)
        
    def on_init(self):
        """策略初始化"""
        if self.trader and hasattr(self.trader, 'initialize'):
            # 这里需要根据initialize函数的参数要求传递合适的参数
            # 假设initialize函数需要context一个参数
            self.trader.initialize(self.trader.context)
        
        pass
    
    def on_start(self):
        """策略启动"""
        pass
    
    def on_stop(self):
        """策略停止"""
        pass
    
    def on_tick(self, tick: TickData):
        """行情推送"""
        pass
    
    def on_bar(self, bar: BarData):
        """K线推送"""
        # 如果trader对象存在，调用其handle_data函数
        if self.trader and hasattr(self.trader, 'handle_data'):
            # 这里需要根据handle_data函数的参数要求传递合适的参数
            # 假设handle_data函数需要context和data两个参数
            self.trader.handle_data(self.trader.context, [bar])
    
    def on_order(self, order: OrderData):
        """订单推送"""
        pass
    
    def on_trade(self, trade: TradeData):
        """成交推送"""
        pass
    
    def on_stop_order(self, stop_order: StopOrder):
        """停止单推送"""
        pass
