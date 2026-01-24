# SQL查询构建器实现
from types import SimpleNamespace
import re
import ibis

# ========== 核心实现：SQLQueryBuilder类 ==========
class SQLQueryBuilder:
    """合并SQLStyleQuery和ExactQuery的功能，支持：
    1. c_rank(dividend_yield_ratio) AS score 语法
    2. c_pct_rank(pe_ttm) < 0.40 语法
    3. 支持SELECT、MUTATE、FILTER等操作
    4. 支持链式操作
    """
    
    def __init__(self, table):
        self.table = table
        self.namespace = SimpleNamespace()
        # 初始化命名空间
        self._init_namespace()
    
    def _init_namespace(self):
        """初始化命名空间，添加列和自定义函数"""
        # 添加表的所有列
        for col in self.table.columns:
            setattr(self.namespace, col, getattr(self.table, col))
        
        # 添加自定义排名函数
        self._add_custom_functions()
    
    def _add_custom_functions(self):
        """添加自定义函数到命名空间"""
        
        def c_rank(col):
            """普通排名函数"""
            if isinstance(col, str):
                col = getattr(self.table, col)
            return ibis.rank().over(order_by=col)
        
        def c_pct_rank(col):
            """百分比排名函数"""
            if isinstance(col, str):
                col = getattr(self.table, col)
            return ibis.percent_rank().over(order_by=col)
        
        def c_dense_rank(col):
            """密集排名函数"""
            if isinstance(col, str):
                col = getattr(self.table, col)
            return ibis.dense_rank().over(order_by=col)
        
        def m_ta_macd_dif(col):
            """MACD DIF（差离值）计算：EMA12 - EMA26"""
            if isinstance(col, str):
                col = getattr(self.table, col)
            # 简化实现：使用固定窗口计算
            # 计算DIF = (close - 3日前close)作为简化版
            return col - col.lag(3)
        
        def m_ta_macd_dea(col):
            """MACD DEA（讯号线）计算：DIF的9日EMA"""
            if isinstance(col, str):
                col = getattr(self.table, col)
            # 简化实现：使用固定窗口计算
            # 计算DEA = (close - 5日前close)作为简化版
            return col - col.lag(5)
        
        def m_lag(col, n):
            """延迟函数：返回n期前的值"""
            return col.lag(n)
            #
            #if isinstance(col, (int, float, str,float64)):
            #    col = getattr(self.table, col)
            #return col.lag(n)
        
        def IF(condition, true_value, false_value):
            """条件函数：如果condition为真返回true_value，否则返回false_value"""
            # Ibis的ifelse函数要求condition是布尔表达式
            return ibis.ifelse(condition, true_value, false_value)
        
        def m_tag(col, n):
            """m_lag的别名函数，用于兼容用户的语法"""
            return m_lag(col, n)
        
        def AND(a, b):
            """逻辑与操作"""
            return ibis.and_(a, b)
        
        def OR(a, b):
            """逻辑或操作"""
            return ibis.or_(a, b)
        
        def NOT(a):
            """逻辑非操作"""
            return ibis.not_(a)
        
        # 添加到命名空间
        setattr(self.namespace, 'c_rank', c_rank)
        setattr(self.namespace, 'c_pct_rank', c_pct_rank)
        setattr(self.namespace, 'c_dense_rank', c_dense_rank)
        setattr(self.namespace, 'm_ta_macd_dif', m_ta_macd_dif)
        setattr(self.namespace, 'm_ta_macd_dea', m_ta_macd_dea)
        setattr(self.namespace, 'm_lag', m_lag)
        setattr(self.namespace, 'm_tag', m_tag)
        setattr(self.namespace, 'IF', IF)
        setattr(self.namespace, 'AND', AND)
        setattr(self.namespace, 'OR', OR)
        setattr(self.namespace, 'NOT', NOT)
    
    def _parse_as_expression(self, expr_str):
        """解析带有 AS 关键字的表达式，如 'c_rank(dividend_yield_ratio) AS score'"""
        # 使用正则表达式匹配 AS 语法
        as_pattern = r'\s+AS\s+'
        parts = re.split(as_pattern, expr_str, flags=re.IGNORECASE)
        
        if len(parts) == 2:
            # 有 AS 关键字，返回 (expression, alias)
            return parts[0].strip(), parts[1].strip()
        else:
            # 没有 AS 关键字，返回 (expression, None)
            return expr_str.strip(), None
    
    def _parse_expressions(self, *expressions, **kwargs):
        """解析多个表达式，处理 AS 语法和关键字参数"""
        parsed = {}
        
        # 创建命名空间，包含当前表的所有列和自定义函数
        namespace = self.namespace.__dict__.copy()
        namespace['ibis'] = ibis
        # 添加当前表的所有列到命名空间
        for col in self.table.columns:
            namespace[col] = getattr(self.table, col)
        
        # 处理位置参数（AS表达式）
        for expr in expressions:
            if isinstance(expr, str):
                # 解析 AS 表达式
                expr_part, alias = self._parse_as_expression(expr)
                
                if alias:
                    # 带有别名，执行表达式并使用别名作为列名
                    # 将逻辑运算符替换为Ibis支持的形式
                    # 替换所有逻辑运算符为Ibis支持的&/|/~形式
                    expr_part_processed = expr_part.replace(' AND ', ' & ').replace(' OR ', ' | ').replace(' NOT ', ' ~ ')
                    expr_part_processed = expr_part_processed.replace(' and ', ' & ').replace(' or ', ' | ').replace(' not ', ' ~ ')
                    # 执行表达式
                    parsed_expr = eval(expr_part_processed, {}, namespace)
                    parsed[alias] = parsed_expr
                else:
                    # 没有别名，检查是否是现有列
                    if expr_part in self.table.columns:
                        # 是现有列，直接添加
                        parsed[expr_part] = getattr(self.table, expr_part)
                    else:
                        # 是表达式，执行并使用表达式作为列名（简化处理）
                        # 将逻辑运算符替换为 Ibis 支持的形式
                        expr_part_processed = expr_part.replace(' AND ', ' & ').replace(' OR ', ' | ').replace(' NOT ', ' ~ ')
                        expr_part_processed = expr_part_processed.replace(' and ', ' & ').replace(' or ', ' | ').replace(' not ', ' ~ ')
                        parsed_expr = eval(expr_part_processed, {}, namespace)
                        parsed[expr_part] = parsed_expr
            else:
                # 不是字符串，直接使用
                parsed[str(expr)] = expr
        
        # 处理关键字参数（ExactQuery风格）
        for key, expr_str in kwargs.items():
            if isinstance(expr_str, str):
                # 执行字符串表达式，将逻辑运算符替换为 Ibis 支持的形式
                expr_str_processed = expr_str.replace(' and ', ' & ').replace(' or ', ' | ').replace(' not ', ' ~ ')
                parsed_expr = eval(expr_str_processed, {}, namespace)
                parsed[key] = parsed_expr
            else:
                # 直接使用表达式
                parsed[key] = expr_str
        
        return parsed
    
    def select(self, *expressions):
        """支持 SQL 风格的 SELECT 语句"""
        # 解析表达式
        parsed_exprs = self._parse_expressions(*expressions)
        
        # 如果没有指定表达式，选择所有列
        if not parsed_exprs:
            return SQLQueryBuilder(self.table)
        
        # 创建选择的表达式列表
        select_exprs = list(parsed_exprs.values())
        
        # 执行选择
        result_table = self.table.select(*select_exprs)
        return SQLQueryBuilder(result_table)
    
    def mutate(self, *expressions, **kwargs):
        """支持 SQL 风格的列添加，如 c_rank(dividend_yield_ratio) AS score
        同时支持 ExactQuery 风格的关键字参数
        """
        # 解析表达式（包括位置参数和关键字参数）
        parsed_exprs = self._parse_expressions(*expressions, **kwargs)
        
        # 执行添加列
        result_table = self.table.mutate(**parsed_exprs)
        return SQLQueryBuilder(result_table)
    
    def filter(self, condition):
        """过滤方法，支持字符串条件和表达式条件"""
        if isinstance(condition, str):
            # 执行字符串条件，将逻辑运算符替换为 Ibis 支持的形式
            condition_processed = condition.replace(' and ', ' & ').replace(' or ', ' | ').replace(' not ', ' ~ ')
            namespace = self.namespace.__dict__.copy()
            namespace['ibis'] = ibis
            # 更新命名空间，包含可能新添加的列
            for col in self.table.columns:
                namespace[col] = getattr(self.table, col)
            condition_expr = eval(condition_processed, {}, namespace)
        else:
            condition_expr = condition
        
        result_table = self.table.filter(condition_expr)
        return SQLQueryBuilder(result_table)
    
    def execute(self):
        """执行查询"""
        return self.table.execute()
    
    def __getattr__(self, name):
        """转发到原始表"""
        return getattr(self.table, name)