import numpy as np
from .trading_cost_manager import TradingCostManager

class OrderManager:
    """订单管理器 - 处理下单操作并记录交易信息"""
    
    def __init__(self, initial_capital=1000000, trading_cost_manager=None):
        """初始化订单管理器
        
        参数:
        initial_capital: 初始资金（默认100万）
        trading_cost_manager: 交易成本管理器实例，如果为None则使用默认配置
        """
        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        
        # 交易成本管理器
        if trading_cost_manager is None:
            self.trading_cost_manager = TradingCostManager(initial_capital)
        else:
            self.trading_cost_manager = trading_cost_manager
        
        # 持仓管理
        self.positions = {}  # 股票代码 -> 持仓数量
        self.avg_prices = {}  # 股票代码 -> 平均持仓成本
        
        # 交易历史
        self.trade_history = []
        
        # 订单ID计数器
        self.order_id_counter = 1
    
    def buy(self, stock_code, price, volume, timestamp=None):
        """买入股票
        
        参数:
        stock_code: 股票代码
        price: 买入价格
        volume: 买入数量
        timestamp: 交易时间戳
        
        返回:
        dict: 订单执行结果
        """
        # 检查最小合约数
        if volume < self.trading_cost_manager.min_contracts:
            return {
                'success': False,
                'message': f'买入数量小于最小合约数{self.trading_cost_manager.min_contracts}'
            }
        
        # 应用滑点
        execution_price = price + self.trading_cost_manager.slippage
        
        # 计算买入成本
        total_cost, commission, transfer_fee = self.trading_cost_manager.calculate_buy_cost(
            execution_price, volume
        )
        
        # 检查资金是否足够
        if total_cost > self.current_capital:
            return {
                'success': False,
                'message': '资金不足'
            }
        
        # 执行买入
        self.current_capital -= total_cost
        
        # 更新持仓
        if stock_code in self.positions:
            total_shares = self.positions[stock_code] + volume
            total_cost_base = self.positions[stock_code] * self.avg_prices[stock_code] + volume * execution_price
            self.avg_prices[stock_code] = total_cost_base / total_shares
            self.positions[stock_code] = total_shares
        else:
            self.positions[stock_code] = volume
            self.avg_prices[stock_code] = execution_price
        
        # 记录交易
        order_id = self.order_id_counter
        self.order_id_counter += 1
        
        trade_record = {
            'order_id': order_id,
            'timestamp': timestamp,
            'stock_code': stock_code,
            'direction': 'buy',
            'price': execution_price,
            'volume': volume,
            'total_cost': total_cost,
            'commission': commission,
            'transfer_fee': transfer_fee,
            'remaining_capital': self.current_capital,
            'position_after': self.positions.get(stock_code, 0),
            'avg_price_after': self.avg_prices.get(stock_code, 0)
        }
        
        self.trade_history.append(trade_record)
        
        return {
            'success': True,
            'order_id': order_id,
            'message': f'买入成功: {stock_code} {volume}股 @ {execution_price}'
        }
    
    def sell(self, stock_code, price, volume, timestamp=None):
        """卖出股票
        
        参数:
        stock_code: 股票代码
        price: 卖出价格
        volume: 卖出数量
        timestamp: 交易时间戳
        
        返回:
        dict: 订单执行结果
        """
        # 检查是否有足够的持仓
        if stock_code not in self.positions or self.positions[stock_code] < volume:
            return {
                'success': False,
                'message': '持仓不足'
            }
        
        # 检查最小合约数
        if volume < self.trading_cost_manager.min_contracts:
            return {
                'success': False,
                'message': f'卖出数量小于最小合约数{self.trading_cost_manager.min_contracts}'
            }
        
        # 应用滑点
        execution_price = price - self.trading_cost_manager.slippage
        
        # 计算卖出收入
        total_revenue, commission, stamp_duty, transfer_fee = self.trading_cost_manager.calculate_sell_cost(
            execution_price, volume
        )
        
        # 执行卖出
        self.current_capital += total_revenue
        self.positions[stock_code] -= volume
        
        # 如果持仓为0，移除该股票
        if self.positions[stock_code] == 0:
            del self.positions[stock_code]
            del self.avg_prices[stock_code]
        
        # 记录交易
        order_id = self.order_id_counter
        self.order_id_counter += 1
        
        trade_record = {
            'order_id': order_id,
            'timestamp': timestamp,
            'stock_code': stock_code,
            'direction': 'sell',
            'price': execution_price,
            'volume': volume,
            'total_revenue': total_revenue,
            'commission': commission,
            'stamp_duty': stamp_duty,
            'transfer_fee': transfer_fee,
            'remaining_capital': self.current_capital,
            'position_after': self.positions.get(stock_code, 0),
            'avg_price_after': self.avg_prices.get(stock_code, 0) if stock_code in self.positions else 0
        }
        
        self.trade_history.append(trade_record)
        
        return {
            'success': True,
            'order_id': order_id,
            'message': f'卖出成功: {stock_code} {volume}股 @ {execution_price}'
        }
    
    def get_position(self, stock_code):
        """获取指定股票的持仓信息
        
        参数:
        stock_code: 股票代码
        
        返回:
        dict: 持仓信息
        """
        if stock_code in self.positions:
            return {
                'stock_code': stock_code,
                'volume': self.positions[stock_code],
                'avg_price': self.avg_prices[stock_code]
            }
        else:
            return {
                'stock_code': stock_code,
                'volume': 0,
                'avg_price': 0
            }
    
    def get_all_positions(self):
        """获取所有持仓信息
        
        返回:
        dict: 所有股票的持仓信息
        """
        positions_info = {}
        for stock_code in self.positions:
            positions_info[stock_code] = {
                'volume': self.positions[stock_code],
                'avg_price': self.avg_prices[stock_code]
            }
        return positions_info
    
    def calculate_total_value(self, current_prices):
        """计算账户总价值
        
        参数:
        current_prices: 股票代码 -> 当前价格的字典
        
        返回:
        float: 账户总价值
        """
        # 计算持仓市值
        position_value = 0
        for stock_code, volume in self.positions.items():
            if stock_code in current_prices:
                position_value += volume * current_prices[stock_code]
        
        # 总价值 = 持仓市值 + 可用资金
        total_value = position_value + self.current_capital
        return total_value
    
    def calculate_return(self, current_prices):
        """计算账户收益率
        
        参数:
        current_prices: 股票代码 -> 当前价格的字典
        
        返回:
        float: 账户收益率
        """
        total_value = self.calculate_total_value(current_prices)
        return (total_value - self.initial_capital) / self.initial_capital
    
    def get_trade_history(self):
        """获取交易历史
        
        返回:
        list: 交易历史记录
        """
        return self.trade_history
    
    def get_trade_history_by_stock(self, stock_code):
        """获取指定股票的交易历史
        
        参数:
        stock_code: 股票代码
        
        返回:
        list: 指定股票的交易历史记录
        """
        return [trade for trade in self.trade_history if trade['stock_code'] == stock_code]
    
    def print_order(self, max_trades=100):
        """
        打印订单交易历史
        
        参数:
        max_trades: 最大打印交易数量
        """
        # 获取交易历史
        trade_history = self.trade_history
        print(f"[测试] 总交易次数: {len(trade_history)}")
        
        # 统计买入和卖出次数
        buy_count = sum(1 for trade in trade_history if trade['direction'] == 'buy')
        sell_count = sum(1 for trade in trade_history if trade['direction'] == 'sell')
        print(f"[测试] 买入次数: {buy_count}, 卖出次数: {sell_count}")
        
        # 打印订单买卖记录
        print(f"[测试] 交易明细:")
        for i, trade in enumerate(trade_history[:max_trades]):
            direction = "买入" if trade['direction'] == 'buy' else "卖出"
            print(f"[测试] 交易{i+1}: {direction} {trade['stock_code']}，价格: {trade['price']}，数量: {trade['volume']}，时间: {trade['timestamp']}")
        if len(trade_history) > max_trades:
            print(f"[测试] ... 还有 {len(trade_history) - max_trades} 条交易记录未显示")
    
    def __str__(self):
        """返回订单管理器的字符串表示"""
        positions_str = ', '.join([f'{code}: {vol}股' for code, vol in self.positions.items()])
        return (f"OrderManager(initial_capital={self.initial_capital}, "
                f"current_capital={self.current_capital:.2f}, "
                f"positions={{ {positions_str} }}, "
                f"total_trades={len(self.trade_history)})")
