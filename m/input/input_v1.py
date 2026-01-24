class InputV1:
    """
    Input V1 数据输入类
    """
    
    def __init__(self, data=None, table_name=None, expr_filters=None, expr_mutates=None, expr_tables=None, extra_fields=None,
                 debug=False, m_name="m1"):
        """
        初始化数据输入
        
        参数:
        data: 股票池数据
        table_name: 表名
        expr_filters: 过滤表达式列表
        expr_mutates: 变换表达式列表
        expr_tables: 表达式表名
        extra_fields: 额外字段
        debug: 是否调试模式
        m_name: 模块名称
        """
        # 存储参数
        self.data = data
        self.table_name = table_name
        self.expr_filters = expr_filters or []
        self.expr_mutates = expr_mutates or []
        self.expr_tables = expr_tables
        self.extra_fields = extra_fields
        self.debug = debug
        self.m_name = m_name
        
        # 如果没有传入data，则初始化为空列表
        if self.data is None:
            self.data = []
        
        # 执行SQL查询
        self._execute_sql()
    
    def _execute_sql(self):
        """
        执行SQL查询
        """
        if self.debug:
            print(f"[DEBUG] InputV1 开始处理数据")
        
        # 处理股票数据：从股票池获取数据，生成新列，过滤股票
        self._process_stock_data()
        
        if self.debug:
            print(f"[DEBUG] InputV1 查询完成，返回 {len(self.data)} 条数据")
    
    def _process_stock_data(self):
        """
        处理股票数据：
        1. 从股票代码池获取股票代码
        2. 从self.table_name表中获取这些股票的数据
        3. 使用SQLQueryBuilder处理数据（生成新列、过滤股票、提取列）
        """
        if self.debug:
            print(f"[DEBUG] InputV1 开始处理股票数据")
        
        try:
            # 1. 从股票代码池获取股票代码
            stock_codes = self.data

            if not stock_codes:
                if self.debug:
                    print(f"[DEBUG] InputV1 股票代码池为空")
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
                print(f"[DEBUG] InputV1 股票代码数量: {len(stock_code_strings)}")
            
            # 2. 从self.table_name表中获取这些股票的数据
            if self.table_name:
                if self.debug:
                    print(f"[DEBUG] InputV1 从表 {self.table_name} 获取数据")
                
                # 从ClickHouse获取数据
                stock_data = self._get_data_from_clickhouse(stock_code_strings)
                
                if stock_data:
                    if self.debug:
                        print(f"[DEBUG] InputV1 从ClickHouse获取了 {len(stock_data)} 条数据")
                    
                    # 3. 使用SQLQueryBuilder处理数据
                    self._process_data_with_query_builder(stock_data)
            
            if self.debug:
                print(f"[DEBUG] InputV1 股票数据处理完成")
                print(f"[DEBUG] 股票代码示例: {stock_codes[:5]}...")
        except Exception as e:
            if self.debug:
                print(f"[ERROR] InputV1 处理股票数据失败: {e}")
            # 发生异常时，保持原有数据不变
    
    def _process_data_with_query_builder(self, data):
        """
        使用SQLQueryBuilder处理数据：
        1. 生成新列
        2. 过滤股票
        3. 提取指定列
        
        参数:
        data: 原始股票数据列表
        """
        if self.debug:
            print(f"[DEBUG] InputV1 开始使用SQLQueryBuilder处理数据")
        
        try:
            import ibis
            import pandas as pd
            from m.db.sql_builder import SQLQueryBuilder
            
            # 将数据转换为pandas DataFrame
            df = pd.DataFrame(data)
            
            if df.empty:
                if self.debug:
                    print(f"[DEBUG] InputV1 数据为空，跳过处理")
                return
            
            # 使用ibis创建内存表
            # 首先创建一个ibis连接
            con = ibis.memtable(df)
            
            # 创建SQLQueryBuilder实例
            query_builder = SQLQueryBuilder(con)
            
            if self.debug:
                print(f"[DEBUG] InputV1 创建了SQLQueryBuilder实例")
            
            # 4. 处理expr_mutates生成新列
            if self.expr_mutates:
                if self.debug:
                    print(f"[DEBUG] InputV1 使用SQLQueryBuilder处理变换表达式: {self.expr_mutates}")
                # 应用所有变换表达式
                for mutate_expr in self.expr_mutates:
                    query_builder = query_builder.mutate(mutate_expr)
                
            # 打印生成新列后的所有数据
            if self.debug:
                print(f"[DEBUG] InputV1 生成新列后的所有数据:")
                # 执行临时查询获取当前结果
                temp_result = query_builder.execute()
                print(temp_result)
            
            # 5. 处理expr_filters过滤股票
            if self.expr_filters:
                if self.debug:
                    print(f"[DEBUG] InputV1 使用SQLQueryBuilder处理过滤表达式: {self.expr_filters}")
                # 应用所有过滤表达式
                for filter_expr in self.expr_filters:
                    query_builder = query_builder.filter(filter_expr)
            
            # 6. 处理extra_fields提取列

            #if self.extra_fields:
            #    if self.debug:
            #        print(f"[DEBUG] InputV1 使用SQLQueryBuilder提取额外字段: {self.extra_fields}")
            #    # 选择指定的列
            #    query_builder = query_builder.select(self.extra_fields)
            
            # 执行查询
            if self.debug:
                print(f"[DEBUG] InputV1 执行SQLQueryBuilder查询")
            
            # 执行查询并获取结果
            result = query_builder.execute()
            
            if self.debug:
                print(f"[DEBUG] InputV1 SQLQueryBuilder查询结果: {result}")
                print(f"[DEBUG] InputV1 SQLQueryBuilder查询结果行数: {len(result)}")
            
            # 将结果转换为字典列表
            if isinstance(result, pd.DataFrame):
                self.data = result.to_dict('records')
            else:
                self.data = result
            
            if self.debug:
                print(f"[DEBUG] InputV1 使用SQLQueryBuilder处理数据完成")
        except Exception as e:
            if self.debug:
                print(f"[ERROR] InputV1 使用SQLQueryBuilder处理数据失败: {e}")
            # 发生异常时，保持原有数据不变
    
    def _get_data_from_clickhouse(self, stock_codes):
        """
        从ClickHouse数据库获取股票数据
        
        参数:
        stock_codes: 股票代码列表
        
        返回:
        股票数据列表
        """
        if self.debug:
            print(f"[DEBUG] InputV1 开始从ClickHouse获取数据")
        
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
                print(f"[DEBUG] InputV1 ClickHouse配置: IP={db_ip}, Port={db_port}")
            
            # 构建SQL查询，使用FORMAT CSVWithNames直接获取带列名的数据
            if stock_codes:
                # 生成股票代码的IN子句
                codes_in_clause = "', '" .join(stock_codes)
                codes_in_clause = f"'{codes_in_clause}'"
                
                # 构建完整的SQL查询，使用FORMAT CSVWithNames
                sql_query = f"SELECT * FROM {self.table_name} WHERE code IN ({codes_in_clause}) FORMAT CSVWithNames"
            else:
                # 如果没有股票代码，查询所有数据
                sql_query = f"SELECT * FROM {self.table_name} FORMAT CSVWithNames"
            
            # 对SQL语句进行URL编码
            quoted_sql = urllib.parse.quote(sql_query)
            
            # 构建HTTP请求URL
            url = f"http://{db_ip}:{db_port}/?query={quoted_sql}"
            
            if self.debug:
                print(f"[DEBUG] InputV1 ClickHouse请求URL: {url}")
                print(f"[DEBUG] InputV1 ClickHouse执行SQL: {sql_query}")
            
            # 发送HTTP请求
            response = requests.get(url, timeout=30)
            response.raise_for_status()  # 检查请求是否成功
            
            if self.debug:
                print(f"[DEBUG] InputV1 ClickHouse响应状态: {response.status_code}")
            
            # 解析响应数据
            # 现在使用FORMAT CSVWithNames，所以应该有列头
            # 使用逗号分隔符，并且第一行是列名
            # 显式指定code列为字符串类型，保留前导零
            df = pd.read_csv(StringIO(response.text), sep=',', dtype={'code': str})
            
            if self.debug:
                print(f"[DEBUG] InputV1 ClickHouse返回数据列: {df.columns.tolist()}")
                print(f"[DEBUG] InputV1 ClickHouse返回数据行数: {len(df)}")
                if len(df) > 0:
                    print(f"[DEBUG] InputV1 ClickHouse返回数据前5行: {df.head().to_dict('records')[:5]}")
            
            # 将DataFrame转换为字典列表
            return df.to_dict('records')
        except Exception as e:
            if self.debug:
                print(f"[ERROR] InputV1 从ClickHouse获取数据失败: {e}")
            return []
    
    def get_data(self):
        """
        获取查询结果数据
        
        返回:
        数据列表
        """
        return self.data
    
    def get_stock_pool(self):
        """
        获取满足条件的股票代码列表
        
        返回:
        股票代码列表
        """
        # 从self.data中提取股票代码
        return self.data 
         
    
    def __repr__(self):
        """
        字符串表示
        """
        return f"InputV1(debug={self.debug}, m_name={self.m_name}, data_length={len(self.data)})"