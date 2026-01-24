# 从extract_data_v1.py导入ExtractDataV1类
from .extract_data_v1 import ExtractDataV1


def v1(start_date, data=None, table_name=None, expr_mutates=None, start_date_bound_to_trading_date=True, 
        end_date="", end_date_bound_to_trading_date=True, before_start_days=0, 
        debug=False, m_name="m2"):
    """
    extract_data v1函数，用于提取数据
    
    参数:
    data: 股票池数据
    table_name: 表名
    expr_mutates: 变换表达式列表
    start_date: 开始日期
    start_date_bound_to_trading_date: 开始日期是否绑定到交易日
    end_date: 结束日期
    end_date_bound_to_trading_date: 结束日期是否绑定到交易日
    before_start_days: 开始前天数
    debug: 是否调试模式
    m_name: 模块名称
    
    返回:
    ExtractDataV1实例
    """
    # 创建ExtractDataV1实例
    extract_instance = ExtractDataV1(
        data=data,
        table_name=table_name,
        expr_mutates=expr_mutates,
        start_date=start_date,
        start_date_bound_to_trading_date=start_date_bound_to_trading_date,
        end_date=end_date,
        end_date_bound_to_trading_date=end_date_bound_to_trading_date,
        before_start_days=before_start_days,
        debug=debug,
        m_name=m_name
    )
    
    # 返回实例
    return extract_instance
