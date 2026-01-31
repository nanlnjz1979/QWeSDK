from celery import Celery
import subprocess
import sys
import os

# 创建 Celery 应用
app = Celery(
    'code_runner',
    broker='redis://redis:6379/0',  # 使用 Redis 作为消息代理
    backend='redis://redis:6379/0',  # 使用 Redis 存储结果
    include=['tasks']  # 包含任务模块
)

# 备用配置：使用内存队列（无 Redis 时使用）
# app = Celery(
#     'code_runner',
#     broker='memory://',  # 内存消息代理
#     backend='cache+memory://',  # 内存结果存储
#     include=['tasks']
# )

# 配置 Celery
app.conf.update(
    result_expires=3600,  # 结果过期时间
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='Asia/Shanghai',
    enable_utc=True,
)

if __name__ == '__main__':
    app.start()
