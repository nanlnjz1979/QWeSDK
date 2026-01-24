# 从input_v1.py导入InputV1类
from .input_v1 import InputV1


def v1(data=None, table_name=None, expr_filters=None, expr_mutates=None, expr_tables=None, extra_fields=None,
        debug=False, m_name="m1"):
    """
    input v1函数，用于输入数据
    
    参数:
    data: 股票池数据
    table_name: 表名
    expr_filters: 过滤表达式列表
    expr_mutates: 变换表达式列表
    expr_tables: 表达式表名
    extra_fields: 额外字段
    debug: 是否调试模式
    m_name: 模块名称
    
    返回:
    InputV1实例
    """
    # 创建InputV1实例
    input_instance = InputV1(
        data=data,
        table_name=table_name,
        expr_filters=expr_filters,
        expr_mutates=expr_mutates,
        expr_tables=expr_tables,
        extra_fields=extra_fields,
        debug=debug,
        m_name=m_name
    )
    
    # 返回实例
    return input_instance
