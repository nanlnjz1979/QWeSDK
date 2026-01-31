
FROM python:3.11

WORKDIR /app

# 复制依赖文件并安装
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制所有应用文件（包括QWeSDK包和入口点脚本）
COPY qwesdk_entrypoint.py .
COPY entrypoint.sh .

# 自动检测并安装QWeSDK包（如果在构建时提供了包文件）
RUN if [ -f qwesdk-*.tar.gz ]; then \
    echo "找到QWeSDK安装包，开始安装..." && \
    ls -la qwesdk-*.tar.gz && \
    pip install --no-cache-dir qwesdk-*.tar.gz && \
    echo "QWeSDK安装完成!" && \
    pip show qwesdk | grep Version; \
else \
    echo "未找到QWeSDK安装包，将在运行时安装"; \
fi

# 设置入口点脚本为可执行
RUN chmod +x /app/entrypoint.sh

# 设置入口点（用于运行时版本检测）
ENTRYPOINT ["/app/entrypoint.sh"]

# 默认命令（如果用户没有指定命令）
CMD ["python", "main.py"]
