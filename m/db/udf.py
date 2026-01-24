# 自定义函数定义
from collections import deque

# 时间序列窗口求和
def ts_sum(x, n):
    """
    时间序列窗口求和
    x: 当前数据值
    n: 窗口大小
    返回: 最近n个数据的和，如果数据不足n个则返回0.0
    """
    # 为每个n值创建一个独立的deque
    if not hasattr(ts_sum, '_deques'):
        ts_sum._deques = {}
    
    if n not in ts_sum._deques:
        ts_sum._deques[n] = deque(maxlen=n)
    
    deque_n = ts_sum._deques[n]
    deque_n.append(x)
    
    if len(deque_n) < n:
        return 0.0
    else:
        return sum(deque_n)
