# QWeSDK 使用示例

# 导入m模块
import m

# 示例1：使用selector.v1函数
print("=== 示例1：使用selector.v1函数 ===")
m1 = m.selector.v1(
    exchanges=["上交所", "深交所", "北交所"],
    list_sectors=["主板", "创业板", "科创板"],
    indexes=["中证500", "上证指数"],
    st_statuses=["正常"],
    drop_suspended=True,
    m_name="m1"
)
print(f"股票池大小: {len(m1.get_stock_pool())}")
print(f"选股结果: {[stock['code'] for stock in m1.get_selected_stocks()[:3]]}...")

# 示例2：使用input.v1函数
print("\n=== 示例2：使用input.v1函数 ===")
m2 = m.input.v1(
    data=m1.get_stock_pool(),
    table_name="stock_data_vvv",
    expr_filters=["pe > 0"],
    debug=True,
    m_name="m2"
)
print(f"获取的数据长度: {len(m2.data) if hasattr(m2, 'data') else 'N/A'}")

# 示例3：简单的策略函数
print("\n=== 示例3：简单的策略函数 ===")

def simple_initialize(context):
    """简单的初始化函数"""
    print(f"初始化完成，初始资金: {context['portfolio']['cash']}")

# 打印示例完成
print("\n=== QWeSDK 使用示例完成 ===")
