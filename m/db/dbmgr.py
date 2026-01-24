# 共享数据库连接管理器
import duckdb

class DBMgr:
    """数据库 共享连接管理器"""
    _conn = None
    
    @classmethod
    def get(cls):
        """获取共享连接"""
        if cls._conn is None:
            cls._conn = duckdb.connect()
            # 自动注册所有自定义函数
            cls._register_default_udfs()
        return cls._conn
    
    @classmethod
    def _register_default_udfs(cls):
        """注册默认的自定义函数"""
        from .udf import ts_sum
        
        # 注册ts_sum函数，使用字符串类型名称
        cls.register_function('ts_sum', ts_sum, 
                            parameters=['DOUBLE', 'INTEGER'], return_type='DOUBLE')
    
    @classmethod
    def register(cls, name, df):
        """注册DataFrame为虚表"""
        conn = cls.get()
        conn.register(name, df)
    
    @classmethod
    def execute(cls, sql):
        """执行SQL语句，返回原生duckdb执行结果"""
        conn = cls.get()
        return conn.execute(sql)

    @classmethod
    def register_function(cls, name, func, parameters=None, return_type=None):
        """注册自定义函数"""
        conn = cls.get()
        conn.create_function(name, func, parameters=parameters, return_type=return_type)
    
    @classmethod
    def close(cls):
        """关闭共享连接"""
        if cls._conn:
            cls._conn.close()
            cls._conn = None
