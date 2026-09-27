from celery import Celery
import os

# Runtime deployments can override these without rebuilding the image.
broker_url = os.environ.get('CELERY_BROKER_URL', 'redis://redis:6379/0')
result_backend = os.environ.get('CELERY_RESULT_BACKEND', broker_url)

# 创建 Celery 应用
app = Celery(
    'code_runner',
    broker=broker_url,
    backend=result_backend,
    include=['m.worker.tasks']  # 包含任务模块
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
