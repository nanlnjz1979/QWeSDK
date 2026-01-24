# 导入必要的模块
import urllib.parse
import requests
import uuid
from m.config import GlobalConfig
import pandas as pd
from io import StringIO
# 导入共享连接管理器
from m.db import DBMgr

class SelectorV1:
    """
    Selector V1 选股器类
    """
    def __init__(self, 
                exchanges=["上交所", "深交所","北交所"], 
                list_sectors=["主板", "创业板", "科创板"], #这个指标还不知道怎么拿到
                indexes=["中证500", "上证指数", "创业板指", "深证成指", "上证50", "科创50", "沪深300", "中证1000", "中证100", "深证100"], 
                st_statuses=["正常","ST","*ST"], 
                margin_tradings=["两融标的", "非两融标的"], #这个指标还不知道怎么拿到
                sw2021_industries=["农林牧渔","基础化工","钢铁","有色金属","电子","汽车","家用电器","食品饮料","纺织服饰","轻工制造","医药生物","公用事业","交通运输","房地产"], 
                drop_suspended=True,   #过滤停牌 #ak.stock_tfp_em(date="20251226")，这个还没拿到数据
                m_name="m1"):
        """
        初始化选股器
        
        参数:
        exchanges: 交易所列表
        list_sectors: 上市板块列表
        indexes: 指数列表
        st_statuses: ST状态列表
        margin_tradings: 融资融券标的列表
        sw2021_industries: 申万2021行业列表
        drop_suspended: 是否剔除停牌股票
        m_name: 模块名称
        """
        # 存储参数
        self.exchanges = exchanges
        self.list_sectors = list_sectors
        self.indexes = indexes
        self.st_statuses = st_statuses
        self.margin_tradings = margin_tradings
        self.sw2021_industries = sw2021_industries
        self.drop_suspended = drop_suspended
        self.m_name = m_name
        
        # 初始化选股结果和股票池
        self.selected_stocks = []
        
        # 获取数据库IP地址配置
        # 只获取 IP 地址，不包含端口，因为后面的 HTTP 请求会使用不同的端口
        db_ip_config = GlobalConfig.get_config("DATABASE_IP", "127.0.0.1:9000")
        # 提取 IP 地址部分，忽略端口
        self._ip = db_ip_config.split(":")[0]
        
        # 初始化表名属性
        self.table_name = None
            
        # 执行选股
        self._select_stocks()    
    def _select_stocks(self):
        """
        执行选股
        分别调用三个函数获取股票代码，取它们的交集作为最终结果
        _get_stock_codes_by_exchanges: 根据交易所获取股票代码
        _get_stock_codes_by_stock_indexes: 根据指数获取股票代码
        _fetch_stocks_from_sw_index: 根据申万行业获取股票代码
        """
        # 清空选股结果
        self.selected_stocks = []
        
        try:
            # 1. 获取三个来源的股票代码
            # 来源1: 交易所选股
            exchange_codes = set(self._get_stock_codes_by_exchanges())
            print(f"[INFO] 交易所选股: {len(exchange_codes)} 只股票")
            
            # 来源2: 指数选股
            index_codes = set(self._get_stock_codes_by_stock_indexes())
            print(f"[INFO] 指数成份选股: {len(index_codes)} 只股票")
            
            # 来源3: 申万行业选股
            sw_codes = set(self._fetch_stocks_from_sw_index())
            print(f"[INFO] 申万行业选股: {len(sw_codes)} 只股票")
            
            # 2. 计算三个来源的交集
            if exchange_codes and index_codes and sw_codes:
                # 三个集合都有数据，取交集
                final_codes = exchange_codes.intersection(index_codes).intersection(sw_codes)
                print(f"[INFO] 三个来源交集: {len(final_codes)} 只股票")
            elif exchange_codes and index_codes:
                # 只有交易所和指数数据，取交集
                final_codes = exchange_codes.intersection(index_codes)
                print(f"[INFO] 交易所和指数交集: {len(final_codes)} 只股票")
            elif exchange_codes and sw_codes:
                # 只有交易所和申万行业数据，取交集
                final_codes = exchange_codes.intersection(sw_codes)
                print(f"[INFO] 交易所和申万行业交集: {len(final_codes)} 只股票")
            elif index_codes and sw_codes:
                # 只有指数和申万行业数据，取交集
                final_codes = index_codes.intersection(sw_codes)
                print(f"[INFO] 指数和申万行业交集: {len(final_codes)} 只股票")
            elif exchange_codes:
                # 只有交易所数据
                final_codes = exchange_codes
                print(f"[INFO] 仅使用交易所选股: {len(final_codes)} 只股票")
            elif index_codes:
                # 只有指数数据
                final_codes = index_codes
                print(f"[INFO] 仅使用指数选股: {len(final_codes)} 只股票")
            elif sw_codes:
                # 只有申万行业数据
                final_codes = sw_codes
                print(f"[INFO] 仅使用申万行业选股: {len(final_codes)} 只股票")
            else:
                # 没有任何数据
                print("[WARNING] 所有选股来源都没有返回数据")
                final_codes = set()
            
            # 3. 将最终股票代码转换为选股结果
            # 将股票代码集合转换为选股结果列表
            self.selected_stocks = [{"code": code} for code in final_codes]
            
            # 打印结果
            print(f"[INFO] 股票池大小: {len([stock['code'] for stock in self.selected_stocks])} 只股票")
            print(f"[INFO] 最终选股结果: {len(self.selected_stocks)} 只股票")
        except Exception as e:
            print(f"[ERROR] 执行选股失败: {e}")
            # 发生异常时，设置选股结果为空列表
            self.selected_stocks = []
    

    
    def get_selected_stocks(self):
        """
        获取选股结果
        
        返回:
        选股结果列表
        """
        return self.selected_stocks
    
    def print_selected_stocks(self, max_count=20, format_type='simple'):
        """
        打印选股结果中的股票代码
        
        参数:
        max_count: 最大打印数量，默认20个
        format_type: 打印格式，可选值：'simple'（简单列表）或 'table'（表格格式）
        """
        selected_stocks = self.selected_stocks
        total_count = len(selected_stocks)
        
        print(f"选股结果：共 {total_count} 只股票")
        
        if total_count == 0:
            return
        
        # 提取股票代码列表
        stock_codes = []
        for stock in selected_stocks:
            if "code" in stock:
                stock_codes.append(stock["code"])
            elif "stock_code" in stock:
                stock_codes.append(stock["stock_code"])
            elif "instrument" in stock:
                stock_codes.append(stock["instrument"])
            else:
                continue
        
        # 根据格式类型打印
        if format_type == 'table':
            # 表格格式打印
            print("\n股票代码列表：")
            print("=" * 50)
            for i, code in enumerate(stock_codes[:max_count], 1):
                print(f"{i:3d}. {code:10}")
            print("=" * 50)
        else:
            # 简单列表格式打印
            print("\n股票代码列表：")
            if len(stock_codes) <= max_count:
                # 如果数量不超过最大限制，全部打印
                print(", ".join(stock_codes))
            else:
                # 只打印前max_count个
                print(", ".join(stock_codes[:max_count]) + f", ... 等共 {total_count} 只股票")
    
    def get_stock_pool(self):
        """
        获取股票池
        
        返回:
        股票代码列表
        """
        # 从selected_stocks中提取股票代码列表
        return [stock['code'] for stock in self.selected_stocks]
    
    def _fetch_stocks_from_sw_index(self):
        """
        根据申万行业获取对应的股票代码
        
        返回:
        股票代码列表
        """
        import urllib.parse
        import requests
        from io import StringIO
        import pandas as pd
        
        # 获取数据库IP地址配置（只取IP部分）
        db_ip_config = GlobalConfig.DATABASE_IP
        db_ip = db_ip_config.split(":")[0]
        
        # 构建SQL语句，替换sw2021_industries变量
        # 生成IN子句，处理多个行业
        industries_in_clause = "', '" .join(self.sw2021_industries)
        industries_in_clause = f"'{industries_in_clause}'" if self.sw2021_industries else "''"
        
        # 构建完整的SQL语句
        sql = f"""select DISTINCT code  FROM sw_industry_stocks_v 
     where industry_code IN ( 
         SELECT DISTINCT l3.industry_code 
         FROM sw_industry_data_v l3 
         WHERE l3.parent_industry IN ( 
             SELECT industry_name 
             FROM sw_industry_data_v 
             WHERE parent_industry IN ( {industries_in_clause} ) 
         ) 
     );"""
        
        try:
            # 对SQL语句进行URL编码
            quoted_sql = urllib.parse.quote(sql)
            
            # 构建HTTP请求URL，使用8123端口和正确的API路径
            url = f"http://{db_ip}:8123/?query={quoted_sql}"
            
            # 发送HTTP请求
            response = requests.get(url)
            response.raise_for_status()  # 检查请求是否成功
            
            # 尝试多种方式解析响应数据
            try:
                # 尝试使用不同的分隔符解析，ClickHouse默认使用制表符分隔
                df = pd.read_csv(StringIO(response.text), sep='\t')
                
                # 处理结果
                stock_codes = df['code'].tolist() if 'code' in df.columns else []
                
                # 如果仍然没有获取到数据，尝试直接解析文本
                if not stock_codes and response.text:
                    # 按行分割，直接提取股票代码
                    lines = response.text.strip().split('\n')
                    # 跳过可能的表头
                    if lines and lines[0] != 'code':
                        stock_codes = lines
                    elif len(lines) > 1:
                        stock_codes = lines[1:]
            except Exception:
                # 直接解析文本作为备用方案
                lines = response.text.strip().split('\n')
                stock_codes = [line.strip() for line in lines if line.strip()]
                # 移除可能的表头
                if stock_codes and stock_codes[0] == 'code':
                    stock_codes = stock_codes[1:]
            
            print(f"[INFO] 成功获取{len(stock_codes)}个申万行业股票代码")
            return stock_codes
        except Exception as e:
            print(f"[ERROR] 获取申万行业股票数据失败: {e}")
            print(f"[ERROR] 响应内容: {response.text if 'response' in locals() else '无响应'}")
            return []
    
    def _get_stock_codes_by_exchanges(self):
        """
        根据交易所和ST状态获取对应的股票代码
        使用类初始化时的exchanges和st_statuses属性，通过HTTP 8123端口获取数据
        参考_fetch_stocks_from_api的实现方式
        ST状态说明：
        - ["正常"]: 排除ST和*ST股票（name不包含ST开头）
        - ["ST"]: 只包含ST开头但不是*ST的股票
        - ["*ST"]: 只包含*ST开头的股票
        - 组合值: 例如["正常", "ST"]表示正常和ST股票
        
        返回:
        股票代码列表
        """
        import urllib.parse
        import requests
        from io import StringIO
        import pandas as pd
        
        # 交易所映射：中文名称 -> 市场代码
        exchange_mapping = {
            "上交所": "SH",
            "深交所": "SZ",
            "北交所": "BJ"
        }
        
        # 将中文交易所名称转换为市场代码
        market_codes = [exchange_mapping[exch] for exch in self.exchanges if exch in exchange_mapping]
        
        # 处理ST状态条件
        st_condition = ""
        target_st_statuses = self.st_statuses
        
        # 根据ST状态组合生成对应的SQL条件
        has_normal = "正常" in target_st_statuses
        has_st = "ST" in target_st_statuses
        has_star_st = "*ST" in target_st_statuses
        
        # 情况1: 只有正常
        if has_normal and not has_st and not has_star_st:
            st_condition = "name NOT LIKE '%ST%'"
        # 情况2: 正常 + ST
        elif has_normal and has_st and not has_star_st:
            st_condition = "name NOT LIKE '*ST%'"
        # 情况3: 正常 + *ST
        elif has_normal and not has_st and has_star_st:
            st_condition = "name NOT LIKE 'ST%'"
        # 情况4: 只有ST
        elif not has_normal and has_st and not has_star_st:
            st_condition = "name LIKE 'ST%' AND name NOT LIKE '*ST%'"
        # 情况5: 只有*ST
        elif not has_normal and not has_st and has_star_st:
            st_condition = "name LIKE '*ST%'"
        # 情况6: ST + *ST
        elif not has_normal and has_st and has_star_st:
            st_condition = "name LIKE '%ST%'"
        # 情况7: 正常 + ST + *ST (包含所有情况)
        elif has_normal and has_st and has_star_st:
            st_condition = ""
        # 情况8: 没有指定ST状态
        else:
            st_condition = ""
        
        # 构建交易所条件
        market_condition = ""
        if market_codes:
            markets_in_clause = "', '" .join(market_codes)
            markets_in_clause = f"'{markets_in_clause}'"
            market_condition = f"market IN ({markets_in_clause})"
        
        # 组合所有条件
        all_conditions = []
        if market_condition:
            all_conditions.append(market_condition)
        if st_condition:
            all_conditions.append(st_condition)
        
        # 构建完整的WHERE子句
        if all_conditions:
            where_clause = "WHERE " + " AND ".join(all_conditions)
        else:
            # 如果没有任何条件，默认获取所有股票
            where_clause = ""
        
        # 构建SQL语句
        sql = f"""
        SELECT DISTINCT code 
        FROM stock_info_v 
        {where_clause}
        """
        
        try:
            # 获取数据库IP地址配置
            db_ip = self._ip
            
            # 对SQL语句进行URL编码
            quoted_sql = urllib.parse.quote(sql)
            
            # 构建HTTP请求URL，使用8123端口和正确的API路径
            url = f"http://{db_ip}:8123/?query={quoted_sql}"
            
            # 发送HTTP请求
            response = requests.get(url)
            response.raise_for_status()  # 检查请求是否成功
            
            # 尝试多种方式解析响应数据
            try:
                # 尝试使用不同的分隔符解析，ClickHouse默认使用制表符分隔
                df = pd.read_csv(StringIO(response.text), sep='\t')
                
                # 处理结果
                stock_codes = df['code'].tolist() if 'code' in df.columns else []
                
                # 如果仍然没有获取到数据，尝试直接解析文本
                if not stock_codes and response.text:
                    # 按行分割，直接提取股票代码
                    lines = response.text.strip().split('\n')
                    # 跳过可能的表头
                    if lines and lines[0] != 'code':
                        stock_codes = lines
                    elif len(lines) > 1:
                        stock_codes = lines[1:]
            except Exception:
                # 直接解析文本作为备用方案
                lines = response.text.strip().split('\n')
                stock_codes = [line.strip() for line in lines if line.strip()]
                # 移除可能的表头
                if stock_codes and stock_codes[0] == 'code':
                    stock_codes = stock_codes[1:]
            
            print(f"[INFO] 成功获取{len(stock_codes)}个股票代码")
            return stock_codes
        except Exception as e:
            print(f"[ERROR] 通过8123端口获取股票代码失败: {e}")
            print(f"[ERROR] 响应内容: {response.text if 'response' in locals() else '无响应'}")
            return []
    
    def _get_stock_codes_by_stock_indexes(self):
        """
        根据指数列表获取对应的股票代码
        使用类初始化时的indexes属性，通过HTTP 8123端口获取数据
        ["中证500", "上证指数", "创业板指", "深证成指", "上证50", "科创50", "沪深300", "中证1000", "中证100", "深证100"], 
        表结构：default.stock_index_v(code, name, index_code, index_name)
        
        返回:
        股票代码列表
        """
        import urllib.parse
        import requests
        from io import StringIO
        import pandas as pd
        
        # 处理指数列表
        target_indexes = self.indexes
        
        # 构建指数条件
        if target_indexes:
            # 如果有指数列表，添加WHERE条件
            indexes_in_clause = "', '" .join(target_indexes)
            indexes_in_clause = f"'{indexes_in_clause}'"
            where_clause = f"WHERE index_name IN ({indexes_in_clause})"
        else:
            # 如果没有指数列表，默认获取所有股票（不添加WHERE条件）
            print("[WARNING] 指数列表为空，默认获取所有股票")
            where_clause = ""
        
        # 构建SQL语句
        sql = f"""
        SELECT DISTINCT code 
        FROM stock_index_v 
        {where_clause}
        """
        
        try:
            # 获取数据库IP地址配置
            db_ip = self._ip
            
            # 对SQL语句进行URL编码
            quoted_sql = urllib.parse.quote(sql)
            
            # 构建HTTP请求URL，使用8123端口和正确的API路径
            url = f"http://{db_ip}:8123/?query={quoted_sql}"
            
            # 发送HTTP请求
            response = requests.get(url)
            response.raise_for_status()  # 检查请求是否成功
            
            # 尝试多种方式解析响应数据
            try:
                # 尝试使用不同的分隔符解析，ClickHouse默认使用制表符分隔
                df = pd.read_csv(StringIO(response.text), sep='\t')
                
                # 处理结果
                stock_codes = df['code'].tolist() if 'code' in df.columns else []
                
                # 如果仍然没有获取到数据，尝试直接解析文本
                if not stock_codes and response.text:
                    # 按行分割，直接提取股票代码
                    lines = response.text.strip().split('\n')
                    # 跳过可能的表头
                    if lines and lines[0] != 'code':
                        stock_codes = lines
                    elif len(lines) > 1:
                        stock_codes = lines[1:]
            except Exception:
                # 直接解析文本作为备用方案
                lines = response.text.strip().split('\n')
                stock_codes = [line.strip() for line in lines if line.strip()]
                # 移除可能的表头
                if stock_codes and stock_codes[0] == 'code':
                    stock_codes = stock_codes[1:]
            
            print(f"[INFO] 成功获取{len(stock_codes)}个股票代码")
            return stock_codes
        except Exception as e:
            print(f"[ERROR] 通过8123端口获取股票代码失败: {e}")
            print(f"[ERROR] 响应内容: {response.text if 'response' in locals() else '无响应'}")
            return []
    
    def get_stock_codes_by_exchanges(self):
        """
        公共方法：根据交易所获取股票代码
        兼容测试文件使用
        """
        return self._get_stock_codes_by_exchanges()
    
    def __repr__(self):
        """
        字符串表示
        """
        return f"SelectorV1(m_name={self.m_name}, selected_stocks_count={len(self.selected_stocks)})"
