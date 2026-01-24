import numpy as np

class ArrayManager:
    """管理K线数据的数组管理器 - 纯动态字段实现"""
    
    def __init__(self, size=100):
        self.size = size
        self.count = 0
        # 所有字段都存储在fields字典中，包括传统的OHLCV字段
        self.fields = {}
    
    def update_bar(self, bar):
        """更新K线数据
        
        支持任意字段的动态更新，包括价格、成交量和各种指标
        
        参数:
        bar: K线数据，可以是字典、对象或具有属性的实例
        """
        # 检查bar是否为字典或具有__dict__属性
        if hasattr(bar, '__dict__'):
            bar_dict = bar.__dict__
        elif isinstance(bar, dict):
            bar_dict = bar
        else:
            # 尝试将bar转换为字典
            try:
                bar_dict = {k: getattr(bar, k) for k in dir(bar) if not k.startswith('_') and not callable(getattr(bar, k, None))}
            except Exception:
                bar_dict = {}
        
        # 遍历bar中的所有字段
        for key, value in bar_dict.items():
            # 尝试转换为数值
            try:
                numeric_value = float(value)
            except (ValueError, TypeError):
                continue
            
            # 如果字段不存在，创建新数组
            if key not in self.fields:
                self.fields[key] = np.zeros(self.size, dtype=np.float64)
            
            # 更新字段数据
            field_array = self.fields[key]
            field_array[:-1] = field_array[1:]
            field_array[-1] = numeric_value
        
        if self.count < self.size:
            self.count += 1
    
    @property
    def inited(self):
        """是否已经初始化完成"""
        return self.count >= self.size
    
    def get_field(self, field_name):
        """
        获取指定字段的数据
        
        参数:
        field_name: 字段名称
        
        返回:
        字段对应的数组，如果字段不存在返回None
        """
        return self.fields.get(field_name, None)
    
    def has_field(self, field_name):
        """
        检查是否存在指定字段
        
        参数:
        field_name: 字段名称
        
        返回:
        布尔值，表示字段是否存在
        """
        return field_name in self.fields
    
    def get_all_fields(self):
        """
        获取所有可用字段名称
        
        返回:
        字段名称列表
        """
        return list(self.fields.keys())
    
    # 保持与原有接口的兼容性
    @property
    def close(self):
        return self.fields.get('close', self.fields.get('close_price', np.zeros(self.size)))
    
    @property
    def high(self):
        return self.fields.get('high', self.fields.get('high_price', np.zeros(self.size)))
    
    @property
    def low(self):
        return self.fields.get('low', self.fields.get('low_price', np.zeros(self.size)))
    
    @property
    def open(self):
        return self.fields.get('open', self.fields.get('open_price', np.zeros(self.size)))
    
    @property
    def volume(self):
        return self.fields.get('volume', np.zeros(self.size))
