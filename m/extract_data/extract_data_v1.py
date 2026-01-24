from m.core import ExpressionAnalyzer, TA

class ExtractDataV1:
    """
    ExtractData V1 数据提取类
    """
    def __init__(self, start_date, data=None, table_name=None, expr_mutates=None, start_date_bound_to_trading_date=True, 
                 end_date="", end_date_bound_to_trading_date=True, before_start_days=0, 
                 debug=False, m_name="m2"):
        """
        初始化数据提取
        
        参数:
        data: 股票池数据
        table_name: 表名
        expr_mutates: 变换表达式列表
        start_date: 开始日期
        start_date_bound_to_trading_date: 是否将开始日期绑定到交易日
        end_date: 结束日期
        end_date_bound_to_trading_date: 是否将结束日期绑定到交易日
        before_start_days: 开始前的天数
        debug: 是否调试模式
        m_name: 模块名称
        """
        # 存储参数
        self.data = data
        self.table_name = table_name
        self.expr_mutates = expr_mutates or []
        self.start_date = start_date
        self.start_date_bound_to_trading_date = start_date_bound_to_trading_date
        self.end_date = end_date
        self.end_date_bound_to_trading_date = end_date_bound_to_trading_date
        self.before_start_days = before_start_days
        self.debug = debug
        self.m_name = m_name
        
        # 初始化数据，使用字典存储，键为股票代码，值为DataFrame
        self.result_data = {}
        
        # 初始化技术分析引擎
        self.TA = TA()
        
        # 提取数据
        self._extract_data()
        
        # 处理变换表达式，生成新数据
        if self.expr_mutates:
            self._process_expr_mutates()

        self.print_all_stocks()

    def _extract_data(self):
        """
        提取数据
        """
        if self.debug:
            print(f"[DEBUG] ExtractDataV1 开始提取数据，开始日期: {self.start_date}，结束日期: {self.end_date}，提前天数: {self.before_start_days}")
            print(f"[DEBUG] 输入数据长度: {len(self.data)}")
        
        try:
            # 1. 从股票代码池获取股票代码
            stock_codes = self.data
            
            if not stock_codes:
                if self.debug:
                    print(f"[DEBUG] ExtractDataV1 股票代码池为空")
                return
            
            # 转换stock_codes为纯字符串列表
            # 处理两种情况：1. 直接是字符串列表 2. 是包含code字段的字典列表
            if stock_codes and isinstance(stock_codes[0], dict):
                # 从字典列表中提取code字段值
                stock_code_strings = [str(code_dict.get('code', '')) for code_dict in stock_codes if code_dict.get('code')]
            else:
                # 已经是字符串列表
                stock_code_strings = [str(code) for code in stock_codes]
            
            if self.debug:
                print(f"[DEBUG] ExtractDataV1 股票代码数量: {len(stock_code_strings)}")
            
            # 2. 计算查询时间范围
            # 导入datetime和timedelta用于日期计算
            from datetime import datetime, timedelta
            
            # 解析开始日期和结束日期
            start_dt = datetime.strptime(self.start_date, "%Y-%m-%d")
            
            # 计算查询开始时间，考虑before_start_days
            query_start_dt = start_dt - timedelta(days=self.before_start_days)
            query_start_date = query_start_dt.strftime("%Y-%m-%d")
            
            # 结束日期，如果为空则使用当前日期
            if self.end_date:
                end_dt = datetime.strptime(self.end_date, "%Y-%m-%d")
                query_end_date = self.end_date
            else:
                end_dt = datetime.now()
                query_end_date = end_dt.strftime("%Y-%m-%d")
            
            if self.debug:
                print(f"[DEBUG] ExtractDataV1 计算查询时间范围: 查询开始日期={query_start_date}, 查询结束日期={query_end_date}")
            
            # 3. 从self.table_name表中获取这些股票的数据
            if self.table_name:
                if self.debug:
                    print(f"[DEBUG] ExtractDataV1 从表 {self.table_name} 获取数据")
                
                # 从ClickHouse获取所有股票的数据
                all_stock_data = self._get_data_from_clickhouse(stock_code_strings, query_start_date, query_end_date)
                
                if all_stock_data:
                    if self.debug:
                        print(f"[DEBUG] ExtractDataV1 从ClickHouse获取了 {len(all_stock_data)} 条数据")
                    
                    # 导入pandas用于DataFrame操作
                    import pandas as pd
                    
                    # 将所有数据转换为DataFrame
                    all_df = pd.DataFrame(all_stock_data)
                    
                    # 遍历每个股票代码，将数据拆分为单独的DataFrame
                    for stock_code in stock_code_strings:
                        # 过滤当前股票的数据
                        stock_df = all_df[all_df['code'] == stock_code]
                        
                        if not stock_df.empty:
                            # 将当前股票的数据存储到result_data字典中
                            self.result_data[stock_code] = stock_df
                            if self.debug:
                                print(f"[DEBUG] ExtractDataV1 股票 {stock_code} 数据行数: {len(stock_df)}")
                                print(self.result_data[stock_code ].head())
        
        except Exception as e:
            if self.debug:
                print(f"[ERROR] ExtractDataV1 处理数据失败: {e}")
                import traceback
                traceback.print_exc()
        
        if self.debug:
            print(f"[DEBUG] ExtractDataV1 数据提取完成，已处理股票数量: {len(self.result_data)}")
    
    def _get_data_from_clickhouse(self, stock_codes, query_start_date, query_end_date):
        """
        从ClickHouse数据库获取股票数据
        
        参数:
        stock_codes: 股票代码列表
        query_start_date: 查询开始日期
        query_end_date: 查询结束日期
        
        返回:
        股票数据列表
        """
        if self.debug:
            print(f"[DEBUG] ExtractDataV1 开始从ClickHouse获取数据")
        
        try:
            import urllib.parse
            import requests
            from io import StringIO
            import pandas as pd
            from m.config import GlobalConfig
            
            # 获取数据库配置
            db_ip_config = GlobalConfig.get_config("DATABASE_IP", "127.0.0.1:8123")
            db_ip, db_port = db_ip_config.split(":")
            
            if self.debug:
                print(f"[DEBUG] ExtractDataV1 ClickHouse配置: IP={db_ip}, Port={db_port}")
            
            # 构建SQL查询，使用FORMAT CSVWithNames直接获取带列名的数据
            if stock_codes:
                # 生成股票代码的IN子句
                codes_in_clause = "', '" .join(stock_codes)
                codes_in_clause = f"'{codes_in_clause}'"
                
                # 构建完整的SQL查询，使用FORMAT CSVWithNames
                # 添加时间范围条件：date >= query_start_date AND date <= query_end_date
                sql_query = f"SELECT * FROM {self.table_name} WHERE code IN ({codes_in_clause}) AND date >= '{query_start_date}' AND date <= '{query_end_date}' FORMAT CSVWithNames"
            else:
                # 如果没有股票代码，返回空列表
                return []
            
            # 对SQL语句进行URL编码，使用quote而不是quote_plus，避免空格被替换为+号
            quoted_sql = urllib.parse.quote(sql_query)
            
            # 发送HTTP请求到ClickHouse
            url = f"http://{db_ip}:{db_port}/?query={quoted_sql}"
            response = requests.get(url, timeout=30)
            response.raise_for_status()  # 检查请求是否成功
            
            if self.debug:
                print(f"[DEBUG] ExtractDataV1 ClickHouse响应状态: {response.status_code}")
                # 打印响应数据的前200个字符，以便调试
                print(f"[DEBUG] ExtractDataV1 ClickHouse响应前200字符: {response.text[:200]}...")
            
            # 解析CSV数据
            # 显式指定分隔符为逗号，并且第一行是列名
            # 显式指定code列为字符串类型，保留前导零
            df = pd.read_csv(StringIO(response.text), sep=',', dtype={'code': str})
            
            if self.debug:
                print(f"[DEBUG] ExtractDataV1 ClickHouse返回数据列: {df.columns.tolist()}")
                print(f"[DEBUG] ExtractDataV1 ClickHouse返回数据行数: {len(df)}")
                if len(df) > 0:
                    # 打印第一行数据，检查第一列是否完整
                    first_row = df.iloc[0].to_dict()
                    print(f"[DEBUG] ExtractDataV1 ClickHouse返回第一行数据: {first_row}")
                    # 打印第一列的名称和值，检查是否完整
                    first_column = df.columns[0]
                    first_value = first_row[first_column]
                    print(f"[DEBUG] ExtractDataV1 第一列名称: {first_column}, 第一列值: {first_value}, 长度: {len(str(first_value))}")
            
            # 将DataFrame转换为字典列表
            return df.to_dict('records')
                
        except Exception as e:
            if self.debug:
                print(f"[ERROR] ExtractDataV1 从ClickHouse获取数据失败: {e}")
                # 打印详细的错误信息和堆栈跟踪
                import traceback
                traceback.print_exc()
            return []
    
    def get_data(self):
        """
        获取提取后的数据
        
        返回:
        提取后的数据字典，键为股票代码，值为对应的DataFrame
        """
        return self.result_data
    
    def calculate_indicator(self, df, expression):
        """
        根据表达式计算指标
        参数：
            df: 包含基础数据的DataFrame
            expression: 指标计算表达式，如 "macd(close,dif,dea,macd)" 或 "dif + dea as vv"
        返回：
            df: 追加了指标的DataFrame
        """
        # 初始化表达式分析器
        analyzer = ExpressionAnalyzer()
        
        # 解析并执行表达式
        df = analyzer.parse_and_execute(expression, df, self.TA)
        
        return df
    
    def _process_expr_mutates(self):
        """
        处理变换表达式，生成新数据
        """
        if self.debug:
            print(f"[DEBUG] ExtractDataV1 开始处理变换表达式，共 {len(self.expr_mutates)} 个表达式")
        
        try:
            # 遍历每个股票代码和对应的DataFrame
            for stock_code, stock_df in self.result_data.items():
                if self.debug:
                    print(f"[DEBUG] 处理股票 {stock_code} 的数据，原始行数: {len(stock_df)}")
                
                # 依次应用每个变换表达式
                for mutate_expr in self.expr_mutates:
                    if self.debug:
                        print(f"[DEBUG] 应用表达式: {mutate_expr}")
                    
                    # 使用calculate_indicator方法应用表达式
                    stock_df = self.calculate_indicator(stock_df, mutate_expr)
                    
                    if self.debug:
                        print(f"[DEBUG] 应用表达式后的数据列: {stock_df.columns.tolist()}")
                
                # 更新result_data中的DataFrame
                self.result_data[stock_code] = stock_df
                
                if self.debug:
                    print(f"[DEBUG] 股票 {stock_code} 处理完成，最终行数: {len(stock_df)}")
        
        except Exception as e:
            if self.debug:
                print(f"[ERROR] ExtractDataV1 处理变换表达式失败: {e}")
                import traceback
                traceback.print_exc()
        
        if self.debug:
            print(f"[DEBUG] ExtractDataV1 变换表达式处理完成")
    
    def __repr__(self):
        """
        字符串表示
        """
        return f"ExtractDataV1(start_date={self.start_date}, end_date={self.end_date}, stock_count={len(self.result_data)}, m_name={self.m_name})"
    
    def print_all_stocks(self):
        """
        打印result_data中每一个股票的后10行数据
        """
        if not self.result_data:
            print("[INFO] ExtractDataV1 结果数据为空，没有股票数据可打印")
            return
        
        print(f"=== 开始打印所有股票的后10行数据，共 {len(self.result_data)} 只股票 ===")
        
        # 遍历所有股票代码和对应的DataFrame
        for stock_code, stock_df in self.result_data.items():
            print(f"\n=== 股票 {stock_code} 的后10行数据 ===")
            print(stock_df.tail(10))
        
        print(f"\n=== 所有股票数据打印完成 ===")
