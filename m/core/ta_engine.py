import talib
import numpy as np

class TA:
    """技术分析指标库"""
    
    @staticmethod
    def calculate_macd(df, close_col, dif_col, dea_col, macd_col):
        """计算MACD指标并追加到DataFrame中
        参数：
            df: 包含收盘价列的DataFrame
            close_col: 收盘价列名
            dif_col: DIF线列名
            dea_col: DEA线列名
            macd_col: MACD柱体列名
        返回：
            df: 追加了MACD指标的DataFrame
        """
        # 验证必要的列存在
        if close_col not in df.columns:
            raise ValueError(f"收盘价列 '{close_col}' 不存在于DataFrame中")
        
        # 计算MACD指标
        df[close_col] = df[close_col].astype(float)
        
        # 使用talib计算MACD指标
        dif, dea, macd_hist = talib.MACD(
            df[close_col],
            fastperiod=12,
            slowperiod=26,
            signalperiod=9
        )
        
        # 添加MACD指标到DataFrame
        df[dif_col] = dif      # DIF线
        df[dea_col] = dea      # DEA线
        df[macd_col] = macd_hist  # MACD柱体
        
        return df
    
    @staticmethod
    def calculate_kdj(df, close_col, k_col, d_col, j_col):
        """计算KDJ指标并追加到DataFrame中
        参数：
            df: 包含OHLC数据的DataFrame
            close_col: 收盘价列名
            k_col: K值列名
            d_col: D值列名
            j_col: J值列名
        返回：
            df: 追加了KDJ指标的DataFrame
        """
        # 验证必要的列存在
        required_cols = ['high', 'low', close_col]
        for col in required_cols:
            if col not in df.columns:
                raise ValueError(f"列 '{col}' 不存在于DataFrame中")
        
        # 转换为浮点数
        df['high'] = df['high'].astype(float)
        df['low'] = df['low'].astype(float)
        df[close_col] = df[close_col].astype(float)
        
        # 使用talib计算KD指标
        k, d = talib.STOCH(
            df['high'],
            df['low'],
            df[close_col],
            fastk_period=9,
            slowk_period=3,
            slowk_matype=0,
            slowd_period=3,
            slowd_matype=0
        )
        
        # 计算J值: J = 3*K - 2*D
        j = 3 * k - 2 * d
        
        # 添加KDJ指标到DataFrame
        df[k_col] = k      # K值
        df[d_col] = d      # D值
        df[j_col] = j      # J值
        
        return df
    
    @staticmethod
    def calculate_lag(df, src_col, lag_period, dest_col):
        """计算滞后指标并追加到DataFrame中
        参数：
            df: 包含数据的DataFrame
            src_col: 源列名
            lag_period: 滞后期数
            dest_col: 目标列名
        返回：
            df: 追加了滞后指标的DataFrame
        """
        # 验证必要的列存在
        if src_col not in df.columns:
            raise ValueError(f"列 '{src_col}' 不存在于DataFrame中")
        
        # 计算滞后值
        df[dest_col] = df[src_col].shift(lag_period)
        
        return df
