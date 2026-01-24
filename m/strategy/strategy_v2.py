from m.core import ArrayManager

class StrategyV2:
    """组合策略模板"""
    
    author = "TraeAI"
     
    def __init__(self, engine, strategy_name, vt_symbols, setting):
        self.engine = engine
        self.strategy_name = strategy_name
        self.vt_symbols = vt_symbols
        self.setting = setting
        
        # 初始化ArrayManager
        self.ams = {}
        for vt_symbol in vt_symbols:
            self.ams[vt_symbol] = ArrayManager()
    
    def on_init(self):
        """初始化策略"""
        print("策略初始化")
    
    def on_start(self):
        """启动策略"""
        print("策略启动")
    
    def on_stop(self):
        """停止策略"""
        print("策略停止")
    
    def on_bars(self, bars):
        """处理所有合约的Bar数据
        bars格式：{vt_symbol: BarData, ...}
        """
        # 遍历每个合约的Bar数据
        for vt_symbol, bar in bars.items():
            # 更新ArrayManager
            self.ams[vt_symbol].update_bar(bar)
            if not self.ams[vt_symbol].inited:
                continue
            