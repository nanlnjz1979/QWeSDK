from lark import Lark, Transformer, v_args

class ExpressionAnalyzer:
    """表达式分析器，使用Lark解析指标表达式"""
    
    def __init__(self):
        # 定义语法规则
        self.grammar = r"""
            ?start: expr ["as" column_name]
            
            ?expr: function_call
                | expr "+" expr   -> add
                | expr "-" expr   -> sub
                | expr "*" expr   -> mul
                | expr "/" expr   -> div
                | column_name
                | NUMBER
            
            function_call: NAME "(" [expr ("," expr)*] ")"
            column_name: NAME
            
            NAME: /[a-zA-Z_][a-zA-Z0-9_]*/
            NUMBER: /-?\d+(\.\d+)?/
            
            %import common.WS
            %ignore WS
        """
        
        # 创建解析器
        self.parser = Lark(self.grammar, start='start', parser='lalr')
        
        # 定义Transformer用于执行解析树
        @v_args(inline=True)
        class EvalTransformer(Transformer):
            def __init__(self, df, ta_engine):
                self.df = df
                self.ta_engine = ta_engine
                
            def start(self, expr_result, as_name=None):
                """处理表达式结果和别名"""
                return expr_result, as_name
            
            def add(self, left, right):
                """处理加法表达式"""
                return self.df[left] + self.df[right]
            
            def sub(self, left, right):
                """处理减法表达式"""
                return self.df[left] - self.df[right]
            
            def mul(self, left, right):
                """处理乘法表达式"""
                return self.df[left] * self.df[right]
            
            def div(self, left, right):
                """处理除法表达式"""
                return self.df[left] / self.df[right]
            
            def column_name(self, name):
                """处理列名"""
                return str(name)
            
            def NUMBER(self, num):
                """处理数字"""
                return float(num)
            
            def function_call(self, name, *args):
                """处理函数调用"""
                func_name = str(name)
                
                if func_name == 'macd':
                    # MACD函数参数：close_col, dif_col, dea_col, macd_col
                    if len(args) < 4:
                        raise ValueError(f"MACD函数需要4个参数: close_col, dif_col, dea_col, macd_col")
                    close_col, dif_col, dea_col, macd_col = args
                    self.df = self.ta_engine.calculate_macd(self.df, close_col, dif_col, dea_col, macd_col)
                    return None
                elif func_name == 'kdj':
                    # KDJ函数参数：close_col, k_col, d_col, j_col
                    if len(args) < 4:
                        raise ValueError(f"KDJ函数需要4个参数: close_col, k_col, d_col, j_col")
                    close_col, k_col, d_col, j_col = args
                    self.df = self.ta_engine.calculate_kdj(self.df, close_col, k_col, d_col, j_col)
                    return None
                elif func_name == 'lag':
                    # lag函数参数：src_col, lag_period, dest_col
                    if len(args) < 3:
                        raise ValueError(f"lag函数需要3个参数: src_col, lag_period, dest_col")
                    src_col, lag_period, dest_col = args
                    # 将lag_period转换为整数
                    lag_period = int(lag_period)
                    self.df = self.ta_engine.calculate_lag(self.df, src_col, lag_period, dest_col)
                    return None
                else:
                    raise ValueError(f"不支持的函数: {func_name}")
        
        self.Transformer = EvalTransformer
    
    def parse_and_execute(self, expression, df, ta_engine):
        """解析并执行表达式
        参数：
            expression: 指标表达式
            df: 包含数据的DataFrame
            ta_engine: 技术分析引擎实例
        返回：
            df: 更新后的DataFrame
        """
        parse_tree = self.parser.parse(expression)
        transformer = self.Transformer(df, ta_engine)
        result, as_name = transformer.transform(parse_tree)
        
        # 如果有结果且指定了别名，将结果添加到DataFrame
        if result is not None and as_name is not None:
            df[as_name] = result
        
        return df
