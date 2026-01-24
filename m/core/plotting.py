import matplotlib
# 使用非交互式后端，避免Qt GUI错误
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from datetime import datetime

class PlottingManager:
    """绘图管理器 - 用于绘制回测收益曲线和其他图表"""
    
    def __init__(self, debug=False):
        """
        初始化绘图管理器
        
        参数:
        debug: 是否开启调试模式
        """
        self.debug = debug
        
        # 设置中文字体
        plt.rcParams['font.sans-serif'] = ['SimHei']  # 用来正常显示中文标签
        plt.rcParams['axes.unicode_minus'] = False  # 用来正常显示负号
    
    def plot_equity_curve(self, trade_history, initial_capital=1000000, save_path=None):
        """
        绘制回测收益曲线
        
        参数:
        trade_history: 交易历史记录，从OrderManager.get_trade_history()获取
        initial_capital: 初始资金
        save_path: 图表保存路径
        
        返回:
        plt.Figure: 生成的图表对象
        """
        if not trade_history:
            if self.debug:
                print("[DEBUG] 没有交易历史记录，无法绘制收益曲线")
            return None
        
        # 按时间排序交易历史
        sorted_trades = sorted(trade_history, key=lambda x: x['timestamp'])
        
        # 提取时间戳和计算累计收益
        timestamps = []
        equity = []
        current_value = initial_capital
        
        # 初始点
        if sorted_trades:
            first_timestamp = sorted_trades[0]['timestamp']
            timestamps.append(first_timestamp)
            equity.append(current_value)
        
        # 遍历交易记录，计算累计收益
        for trade in sorted_trades:
            if trade['direction'] == 'buy':
                # 买入操作：减少资金
                current_value -= trade.get('total_cost', 0)
            else:
                # 卖出操作：增加资金
                current_value += trade.get('total_revenue', 0)
            
            # 添加时间点和对应的值
            timestamps.append(trade['timestamp'])
            equity.append(current_value)
        
        # 绘制收益曲线
        fig, ax = plt.subplots(figsize=(12, 6))
        ax.plot(timestamps, equity, label='权益曲线', linewidth=2)
        
        # 绘制初始资金线
        ax.axhline(y=initial_capital, color='r', linestyle='--', label='初始资金')
        
        # 添加标题和标签
        ax.set_title('回测收益曲线', fontsize=16)
        ax.set_xlabel('时间', fontsize=12)
        ax.set_ylabel('资金 (元)', fontsize=12)
        
        # 添加图例
        ax.legend(fontsize=10)
        
        # 添加网格
        ax.grid(True, alpha=0.3)
        
        # 自动调整日期标签
        fig.autofmt_xdate()
        
        # 计算最终收益和收益率
        if equity:
            final_value = equity[-1]
            total_return = (final_value - initial_capital) / initial_capital * 100
            
            # 在图表上添加最终收益信息
            ax.text(0.05, 0.95, 
                    f'初始资金: {initial_capital:.2f}元\n' 
                    f'最终资金: {final_value:.2f}元\n' 
                    f'总收益率: {total_return:.2f}%', 
                    transform=ax.transAxes, 
                    verticalalignment='top', 
                    bbox=dict(boxstyle='round', alpha=0.1))
        
        # 保存图表
        if save_path:
            try:
                plt.savefig(save_path, dpi=300, bbox_inches='tight')
                if self.debug:
                    print(f"[DEBUG] 收益曲线已保存到: {save_path}")
            except Exception as e:
                if self.debug:
                    print(f"[DEBUG] 保存图表失败: {e}")
        
        return fig
    
    def plot_drawdown(self, trade_history, initial_capital=1000000, save_path=None):
        """
        绘制最大回撤曲线
        
        参数:
        trade_history: 交易历史记录
        initial_capital: 初始资金
        save_path: 图表保存路径
        
        返回:
        plt.Figure: 生成的图表对象
        """
        if not trade_history:
            if self.debug:
                print("[DEBUG] 没有交易历史记录，无法绘制回撤曲线")
            return None
        
        # 按时间排序交易历史
        sorted_trades = sorted(trade_history, key=lambda x: x['timestamp'])
        
        # 计算累计收益和回撤
        timestamps = []
        equity = []
        drawdown = []
        current_value = initial_capital
        peak_value = initial_capital
        
        # 初始点
        if sorted_trades:
            first_timestamp = sorted_trades[0]['timestamp']
            timestamps.append(first_timestamp)
            equity.append(current_value)
            drawdown.append(0)
        
        # 遍历交易记录
        for trade in sorted_trades:
            if trade['direction'] == 'buy':
                current_value -= trade.get('total_cost', 0)
            else:
                current_value += trade.get('total_revenue', 0)
            
            # 更新峰值
            peak_value = max(peak_value, current_value)
            
            # 计算回撤
            if peak_value > 0:
                current_drawdown = (current_value - peak_value) / peak_value * 100
            else:
                current_drawdown = 0
            
            # 添加数据点
            timestamps.append(trade['timestamp'])
            equity.append(current_value)
            drawdown.append(current_drawdown)
        
        # 绘制回撤曲线
        fig, ax = plt.subplots(figsize=(12, 6))
        ax.plot(timestamps, drawdown, label='回撤 (%)', linewidth=2, color='red')
        
        # 添加标题和标签
        ax.set_title('回测回撤曲线', fontsize=16)
        ax.set_xlabel('时间', fontsize=12)
        ax.set_ylabel('回撤 (%)', fontsize=12)
        
        # 添加图例
        ax.legend(fontsize=10)
        
        # 添加网格
        ax.grid(True, alpha=0.3)
        
        # 自动调整日期标签
        fig.autofmt_xdate()
        
        # 计算最大回撤
        if drawdown:
            max_drawdown = min(drawdown)
            
            # 在图表上添加最大回撤信息
            ax.text(0.05, 0.95, 
                    f'最大回撤: {max_drawdown:.2f}%', 
                    transform=ax.transAxes, 
                    verticalalignment='top', 
                    bbox=dict(boxstyle='round', alpha=0.1))
        
        # 保存图表
        if save_path:
            try:
                plt.savefig(save_path, dpi=300, bbox_inches='tight')
                if self.debug:
                    print(f"[DEBUG] 回撤曲线已保存到: {save_path}")
            except Exception as e:
                if self.debug:
                    print(f"[DEBUG] 保存图表失败: {e}")
        
        return fig
    
    def plot_trade_distribution(self, trade_history, save_path=None):
        """
        绘制交易分布图表
        
        参数:
        trade_history: 交易历史记录
        save_path: 图表保存路径
        
        返回:
        plt.Figure: 生成的图表对象
        """
        if not trade_history:
            if self.debug:
                print("[DEBUG] 没有交易历史记录，无法绘制交易分布图")
            return None
        
        # 统计买入和卖出次数
        buy_count = sum(1 for trade in trade_history if trade['direction'] == 'buy')
        sell_count = sum(1 for trade in trade_history if trade['direction'] == 'sell')
        
        # 绘制饼图
        fig, ax = plt.subplots(figsize=(8, 6))
        labels = ['买入', '卖出']
        sizes = [buy_count, sell_count]
        colors = ['#4CAF50', '#F44336']
        explode = (0.1, 0)
        
        ax.pie(sizes, explode=explode, labels=labels, colors=colors,
               autopct='%1.1f%%', shadow=True, startangle=90)
        ax.axis('equal')  # 保证饼图是圆的
        
        ax.set_title('交易分布', fontsize=16)
        
        # 保存图表
        if save_path:
            try:
                plt.savefig(save_path, dpi=300, bbox_inches='tight')
                if self.debug:
                    print(f"[DEBUG] 交易分布图已保存到: {save_path}")
            except Exception as e:
                if self.debug:
                    print(f"[DEBUG] 保存图表失败: {e}")
        
        return fig
