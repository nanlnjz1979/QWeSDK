class TradingCostManager:
    """交易成本管理器"""
    
    def __init__(self, initial_capital, commission_rate=0.0001, stamp_duty_rate=0.001, transfer_fee_rate=0.00002, min_contracts=100, slippage=0.01):
        """初始化交易成本管理器
        
        参数：
            initial_capital: 初始资金
            commission_rate: 佣金率（默认万分之1）
            stamp_duty_rate: 印花税率（默认千分之1，仅卖出时收取）
            transfer_fee_rate: 过户费率（默认十万分之2，仅买入时收取）
            min_contracts: 最小合约数（默认100）
            slippage: 滑点（默认0.01）
        """
        self.initial_capital = initial_capital      #初始资金
        self.commission_rate = commission_rate      #佣金率（默认万分之1）
        self.stamp_duty_rate = stamp_duty_rate      #印花税率（默认千分之1，仅卖出时收取）
        self.transfer_fee_rate = transfer_fee_rate  #过户费率（默认十万分之2，仅买入时收取）
        
        # 交易规则
        self.min_commission = 5  # 最低佣金5元
        self.min_contracts = min_contracts  # 最小合约数
        self.slippage = slippage  # 滑点
        
    def calculate_buy_cost(self, price, volume):
        """计算买入成本
        
        参数：
            price: 买入价格
            volume: 买入数量
        
        返回：
            total_cost: 总买入成本（含手续费）
            commission: 佣金
            transfer_fee: 过户费
        """
        # 计算成交金额
        turnover = price * volume
        
        # 计算佣金
        commission = turnover * self.commission_rate
        commission = max(commission, self.min_commission)  # 最低佣金
        
        # 计算过户费
        transfer_fee = turnover * self.transfer_fee_rate
        transfer_fee = round(transfer_fee, 2)  # 保留两位小数
        
        # 总买入成本
        total_cost = turnover + commission + transfer_fee
        
        return total_cost, commission, transfer_fee
    
    def calculate_sell_cost(self, price, volume):
        """计算卖出成本
        
        参数：
            price: 卖出价格
            volume: 卖出数量
        
        返回：
            total_revenue: 总卖出收入（扣税后）
            commission: 佣金
            stamp_duty: 印花税
            transfer_fee: 过户费
        """
        # 计算成交金额
        turnover = price * volume
        
        # 计算佣金
        commission = turnover * self.commission_rate
        commission = max(commission, self.min_commission)  # 最低佣金
        
        # 计算印花税（仅卖出时收取）
        stamp_duty = turnover * self.stamp_duty_rate
        stamp_duty = round(stamp_duty, 2)  # 保留两位小数
        
        # 计算过户费
        transfer_fee = turnover * self.transfer_fee_rate
        transfer_fee = round(transfer_fee, 2)  # 保留两位小数
        
        # 总卖出收入
        total_revenue = turnover - commission - stamp_duty - transfer_fee
        
        return total_revenue, commission, stamp_duty, transfer_fee
    
    def __str__(self):
        """返回交易成本管理器的字符串表示"""
        return (f"TradingCostManager(initial_capital={self.initial_capital}, "
                f"commission_rate={self.commission_rate}, "
                f"stamp_duty_rate={self.stamp_duty_rate}, "
                f"transfer_fee_rate={self.transfer_fee_rate}, "
                f"min_contracts={self.min_contracts}, "
                f"slippage={self.slippage})")
