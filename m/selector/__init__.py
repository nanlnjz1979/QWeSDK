# 从selector.py导入SelectorV1类
from .selector import SelectorV1


def v1(exchanges=["上交所", "深交所"], list_sectors=["主板", "创业板", "科创板"], 
       indexes=["中证500", "上证指数", "创业板指", "深证成指", "上证50", "科创50", "沪深300", "中证1000", "中证100", "深证100"], 
       st_statuses=["正常"], margin_tradings=["两融标的", "非两融标的"], 
       sw2021_industries=["农林牧渔", "采掘", "基础化工", "钢铁", "有色金属", "建筑建材", "机械设备", "电子", "汽车", "交运设备", "信息设备", "家用电器", "食品饮料", "纺织服饰", "轻工制造", "医药生物", "公用事业", "交通运输", "房地产", "金融服务", "商贸零售", "社会服务", "信息服务", "银行", "非银金融", "综合", "建筑材料", "建筑装饰", "电力设备", "国防军工", "计算机", "传媒", "通信", "煤炭", "石油石化", "环保", "美容护理"], 
       drop_suspended=True, m_name="m1"):
    """
    selector v1函数，用于选股
    
    参数:
    exchanges: 交易所列表
    list_sectors: 上市板块列表
    indexes: 指数列表
    st_statuses: ST状态列表
    margin_tradings: 融资融券标的列表
    sw2021_industries: 申万2021行业列表
    drop_suspended: 是否剔除停牌股票
    m_name: 模块名称
    
    返回:
    SelectorV1实例
    """
    # 创建SelectorV1实例
    selector_instance = SelectorV1(
        exchanges=exchanges,
        list_sectors=list_sectors,
        indexes=indexes,
        st_statuses=st_statuses,
        margin_tradings=margin_tradings,
        sw2021_industries=sw2021_industries,
        drop_suspended=drop_suspended,
        m_name=m_name
    )
    
    # 返回实例
    return selector_instance
