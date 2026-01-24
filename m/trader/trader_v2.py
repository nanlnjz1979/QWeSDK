# 导入必要的类
import sys
import os
import pandas as pd
from datetime import datetime

# 将项目根目录添加到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# 导入core目录下的类
from m.core.array_manager import ArrayManager
from m.core.ta_engine import TA
from m.core.trading_cost_manager import TradingCostManager
from m.core.expression_analyzer import ExpressionAnalyzer
from m.core.order_manager import OrderManager

# 导入StrategyV2类
from m.strategy.strategy_v2 import StrategyV2

class TraderV2:
    """
    Trader V2 多股票回测引擎类
    不使用vn.py框架，使用自定义的回测逻辑
    """
    def __init__(self, data, start_date, end_date, initialize, before_trading_start, 
                 handle_data, handle_tick,handle_trade, handle_order, after_trading, 
                 after_backtest=None, 
                 capital_base=1000000, frequency="daily", 
                 volume_limit=1, order_price_field_buy="open", 
                 order_price_field_sell="close", benchmark="000300.SH", 
                 plot_charts=True, disable_cache=False, debug=False, 
                 backtest_only=False, m_cached=False, m_name="m4"):
        """
        初始化回测引擎
        
        参数:
        data: 回测数据，格式为字典，键为股票代码，值为DataFrame
        start_date: 回测开始日期
        end_date: 回测结束日期
        initialize: 初始化函数
        before_trading_start: 交易前处理函数
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
        """
        # 存储参数
        self.start_date = start_date
        self.end_date = end_date
        self.initialize = initialize
        self.before_trading_start = before_trading_start
        self.handle_data = handle_data
        self.handle_trade = handle_trade
        self.handle_order = handle_order
        self.after_trading = after_trading
        self.after_backtest = after_backtest
        self.capital_base = capital_base
        self.frequency = frequency
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
        
        # 处理数据参数
        # 检查data是否有get_data方法（如ExtractDataV1实例）
        if hasattr(data, 'get_data'):
            # 使用get_data方法获取数据
            self.data = data.get_data()
            if self.debug:
                print(f"[DEBUG] TraderV2 从 ExtractDataV1 实例获取数据，股票数量: {len(self.data)}")
            
            # 从ExtractDataV1实例获取日期信息
            if self.start_date is None and hasattr(data, 'start_date'):
                self.start_date = data.start_date
                if self.debug:
                    print(f"[DEBUG] 从 ExtractDataV1 实例获取开始日期: {self.start_date}")
            if self.end_date is None and hasattr(data, 'end_date'):
                self.end_date = data.end_date
                if self.debug:
                    print(f"[DEBUG] 从 ExtractDataV1 实例获取结束日期: {self.end_date}")
        else:
            # 直接使用传入的数据
            self.data = data

        # 如果仍然没有日期信息，尝试从data对象获取
        if self.start_date is None and hasattr(self.data, 'start_date'):
            self.start_date = self.data.start_date
        if self.end_date is None and hasattr(self.data, 'end_date'):
            self.end_date = self.data.end_date 
       
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
        
        # 股票代码列表
        self.stock_codes = list(self.data.keys()) if isinstance(self.data, dict) else []
        
        # 时间序列（所有股票的公共日期）
        self.dates = self._get_common_dates()
        
        # 数据管理器，每个股票对应一个ArrayManager
        self.array_managers = {}
        for code in self.stock_codes:
            self.array_managers[code] = ArrayManager()
        
        # 技术分析引擎
        self.ta = TA()
        
        # 交易成本管理器
        self.cost_manager = TradingCostManager(initial_capital=capital_base)
        
        # 订单管理器
        self.order = OrderManager(initial_capital=capital_base, trading_cost_manager=self.cost_manager)
        
        # 将订单管理器添加到context中
        self.context['order'] = self.order
        
        # 绘图管理器
        from m.core.plotting import PlottingManager
        self.plotting_manager = PlottingManager(debug=debug)
        
        if self.debug:
            print(f"[DEBUG] TraderV2 初始化完成，模块名: {self.m_name}")
            print(f"[DEBUG] 股票数量: {len(self.stock_codes)}, 回测天数: {len(self.dates)}")
    
    def _get_common_dates(self):
        """
        获取所有股票的公共日期
        """
        if not self.stock_codes:
            return []
        
        # 获取第一个股票的日期
        common_dates = set(pd.to_datetime(self.data[self.stock_codes[0]]['date']).dt.date)
        
        # 求所有股票日期的交集
        for code in self.stock_codes[1:]:
            dates = set(pd.to_datetime(self.data[code]['date']).dt.date)
            common_dates = common_dates.intersection(dates)
        
        # 转换为排序后的列表
        common_dates = sorted(list(common_dates))
        
        # 过滤日期范围
        start_date = pd.to_datetime(self.start_date).date()
        end_date = pd.to_datetime(self.end_date).date()
        
        filtered_dates = [date for date in common_dates if start_date <= date <= end_date]
        
        return filtered_dates
    
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
        
        # 调用回测后处理函数
        if self.after_backtest:
            if self.debug:
                print(f"[DEBUG] 调用回测后处理函数")
            self.after_backtest(self.context)
        
        # 绘制收益曲线
        self._plot_results()
        
        return self.context
    
    def _plot_results(self):
        """
        绘制回测结果图表
        """
        # 检查是否需要绘制图表
        if not self.plot_charts:
            if self.debug:
                print(f"[DEBUG] plot_charts=False，跳过绘图")
            return
        
        if self.debug:
            print(f"[DEBUG] 开始绘制回测结果图表")
        
        # 获取交易历史
        trade_history = self.order.get_trade_history()
        
        if not trade_history:
            if self.debug:
                print(f"[DEBUG] 没有交易历史记录，跳过绘图")
            return
        
        # 绘制收益曲线
        equity_fig = self.plotting_manager.plot_equity_curve(
            trade_history, 
            initial_capital=self.capital_base,
            save_path=f"backtest_equity_curve_{self.m_name}.png"
        )
        
        # 绘制回撤曲线
        drawdown_fig = self.plotting_manager.plot_drawdown(
            trade_history, 
            initial_capital=self.capital_base,
            save_path=f"backtest_drawdown_{self.m_name}.png"
        )
        
        # 绘制交易分布图
        trade_dist_fig = self.plotting_manager.plot_trade_distribution(
            trade_history,
            save_path=f"backtest_trade_distribution_{self.m_name}.png"
        )
        
        if self.debug:
            print(f"[DEBUG] 回测结果图表绘制完成")
    
    def _close_all_positions(self, context, daily_data):
        """
        回测结束后关闭所有持仓
        
        参数:
        context: 上下文对象
        daily_data: 当日数据
        """
        if self.debug:
            print(f"[DEBUG] 开始关闭所有持仓")
        
        # 获取所有持仓
        positions = self.order.get_all_positions()
        
        if not positions:
            if self.debug:
                print(f"[DEBUG] 没有持仓需要关闭")
            return
        
        # 从context中获取当前时间
        current_datetime = context.get('current_datetime', None)
        
        # 遍历所有持仓并卖出
        for stock_code, position_info in positions.items():
            volume = position_info['volume']
            if volume <= 0:
                continue
            
            # 从daily_data中获取卖出价格
            sell_price = None
            if stock_code in daily_data:
                stock_data = daily_data[stock_code]
                if hasattr(stock_data, 'close'):
                    sell_price = stock_data.close
            
            # 如果daily_data中没有价格，使用get_current_price获取
            if sell_price is None:
                sell_price = self._get_current_price(stock_code, 'close')
            
            if self.debug:
                print(f"[DEBUG] 卖出股票: {stock_code}，数量: {volume}，价格: {sell_price}，时间: {current_datetime}")
            
            # 执行卖出操作
            result = self.order.sell(stock_code, sell_price, volume, timestamp=current_datetime)
            
            if result['success']:
                if self.debug:
                    print(f"[DEBUG] 卖出成功: {result['message']}")
            else:
                if self.debug:
                    print(f"[DEBUG] 卖出失败: {result['message']}")
        
        # 同步持仓到context
        self._sync_positions_to_context()
        
        if self.debug:
            print(f"[DEBUG] 所有持仓已关闭")
    
    def _run_daily(self):
        """
        日线级别回测
        """
        if self.debug:
            print(f"[DEBUG] 运行日线回测")
        
        # 遍历每个交易日
        for date in self.dates:
            # 设置当前日期
            self.current_datetime = date
            self.context['current_datetime'] = date
            
            # 交易前处理
            self.before_trading_start(self.context)
            
            # 准备当日数据
            daily_data = {}
            for code in self.stock_codes:
                # 获取当日数据
                df = self.data[code]
                df['date'] = pd.to_datetime(df['date'])
                today_data = df[df['date'].dt.date == date]
                
                if not today_data.empty:
                    # 获取当日第一行数据（日线数据）
                    daily_data[code] = today_data.iloc[0]
                    
                    # 更新ArrayManager
                    bar = daily_data[code]
                    self.array_managers[code].update_bar(bar)
            
            # 处理数据
            self.handle_data(self.context, daily_data)
            
            # 交易后处理
            self.after_trading(self.context)
        
        # 回测结束后关闭所有持仓
        self._close_all_positions(self.context, daily_data)
    
    def _run_tick(self):
        """
        Tick级别回测
        """
        # 简化实现，实际需要遍历tick数据
        if self.debug:
            print(f"[DEBUG] 运行Tick回测")
    
    def get_results(self):
        """
        获取回测结果
        """
        if self.debug:
            print(f"[DEBUG] 获取回测结果")
        
        # 计算最终收益
        final_value = self.context['portfolio']['total_value']
        total_return = (final_value - self.capital_base) / self.capital_base * 100
        
        # 计算每日收益等指标
        # 这里简化实现，实际需要更复杂的计算
        
        return {
            'context': self.context,
            'orders': self.orders,
            'trades': self.trades,
            'positions': self.positions,
            'final_value': final_value,
            'total_return': total_return,
            'start_date': self.start_date,
            'end_date': self.end_date,
            'stock_count': len(self.stock_codes)
        }
    
    def order(self, stock_code, amount, style='market'):
        """
        下单函数
        
        参数:
        stock_code: 股票代码
        amount: 下单数量，正数为买入，负数为卖出
        style: 下单类型，market为市价单
        """
        if self.debug:
            print(f"[DEBUG] 下单: 股票 {stock_code}，数量 {amount}")
        
        # 获取当前价格
        if amount > 0:  # 买入
            price = self._get_current_price(stock_code, self.order_price_field_buy)
        else:  # 卖出
            price = self._get_current_price(stock_code, self.order_price_field_sell)
        
        # 使用OrderManager执行交易
        if amount > 0:
            # 买入
            result = self.order.buy(stock_code, price, amount, timestamp=self.current_datetime)
        else:
            # 卖出
            result = self.order.sell(stock_code, price, abs(amount), timestamp=self.current_datetime)
        
        # 创建订单记录
        order = {
            'stock_code': stock_code,
            'amount': amount,
            'style': style,
            'datetime': self.current_datetime,
            'status': 'filled' if result['success'] else 'rejected',
            'order_id': result.get('order_id', None),
            'message': result.get('message', '')
        }
        
        if result['success']:
            # 从交易历史中获取最新的交易记录
            trade_history = self.order.get_trade_history()
            if trade_history:
                latest_trade = trade_history[-1]
                order['filled_price'] = latest_trade['price']
                order['filled_amount'] = amount
            
            # 同步持仓到context
            self._sync_positions_to_context()
        else:
            order['filled_price'] = 0
            order['filled_amount'] = 0
        
        # 添加到订单列表
        self.orders.append(order)
        
        # 调用订单处理函数
        self.handle_order(self.context, order)
        
        return order
    
    def _sync_positions_to_context(self):
        """
        同步OrderManager的持仓到context中
        """
        # 获取当前价格
        current_prices = {}
        for code in self.stock_codes:
            current_prices[code] = self._get_current_price(code, 'close')
        
        # 同步资金
        self.context['portfolio']['cash'] = self.order.current_capital
        
        # 同步持仓
        positions = {}
        for code, info in self.order.get_all_positions().items():
            positions[code] = info['volume']
        self.context['portfolio']['positions'] = positions
        
        # 同步总价值
        total_value = self.order.calculate_total_value(current_prices)
        self.context['portfolio']['total_value'] = total_value
    
    def _get_current_price(self, stock_code, price_field):
        """
        获取当前价格
        """
        # 从当前数据中获取价格
        for code in self.stock_codes:
            if code == stock_code:
                # 获取最新的ArrayManager数据
                am = self.array_managers[code]
                if am.inited:
                    if price_field == 'open':
                        return am.open[-1]
                    elif price_field == 'close':
                        return am.close[-1]
                    elif price_field == 'high':
                        return am.high[-1]
                    elif price_field == 'low':
                        return am.low[-1]
        
        # 如果没有数据，返回默认价格
        return 10.0
    
    def _update_total_value(self):
        """
        更新总市值
        """
        # 计算持仓市值
        positions_value = 0
        for stock_code, amount in self.context['portfolio']['positions'].items():
            if amount != 0:
                price = self._get_current_price(stock_code, 'close')
                positions_value += price * abs(amount)
        
        # 更新总市值
        self.context['portfolio']['total_value'] = self.context['portfolio']['cash'] + positions_value
        
        if self.debug:
            print(f"[DEBUG] 更新总市值: 现金 {self.context['portfolio']['cash']:.2f}, 持仓市值 {positions_value:.2f}, 总市值 {self.context['portfolio']['total_value']:.2f}")
