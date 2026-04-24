FROM python:3.11-slim

# ==========================
# 阿里云官方APT源（国内服务器专用）
# ==========================
RUN sed -i "s@deb.debian.org@mirrors.aliyun.com@g" /etc/apt/sources.list.d/debian.sources

# ==========================
# 基础编译依赖（极简、稳定）
# ==========================
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ make wget \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 环境配置
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8
ENV PYTHONIOENCODING=utf-8

# ==========================
# 清华PIP源（阿里云秒速）
# ==========================
ENV PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
ENV PIP_TRUSTED_HOST=pypi.tuna.tsinghua.edu.cn

# ==========================
# ✅ TA-Lib 终极编译：无任何外部下载！纯系统修复！
# 支持：x86_64(阿里云) + aarch64(ARM/Mac)
# ==========================
RUN set -ex; \
    ARCH=$(uname -m); \
    # 下载官方源码
    wget https://downloads.sourceforge.net/project/ta-lib/ta-lib/0.4.0/ta-lib-0.4.0-src.tar.gz -O ta.tar.gz; \
    tar zxf ta.tar.gz; \
    cd ta-lib; \
    # 核心修复：直接指定架构，不依赖自动识别
    chmod +x configure; \
    if [ "$ARCH" = "aarch64" ]; then \
        echo "arm build"; \
        ./configure --prefix=/usr --build=aarch64-unknown-linux-gnu --host=aarch64-unknown-linux-gnu; \
    else \
        echo "x86_64 build"; \
        ./configure --prefix=/usr; \
    fi; \
    # 单线程编译，避免ARM崩溃
    make -j1; \
    make install; \
    cd ..; \
    rm -rf ta-lib ta.tar.gz;

# ==========================
# 安装Python依赖（原版TA-Lib）
# ==========================
RUN pip install --no-cache-dir numpy pandas
RUN pip install --no-cache-dir celery==5.6.0 redis==5.2.0 gevent==25.9.1 vnpy==4.2.0 vnpy_ctastrategy==1.3.3
RUN pip install --no-cache-dir ta-lib lark ibis-framework duckdb matplotlib requests

# ==========================
# 业务代码
# ==========================
COPY qwesdk_entrypoint.py .

RUN if [ -f qwesdk-*.tar.gz ]; then \
    pip install --no-cache-dir qwesdk-*.tar.gz; \
fi

CMD ["sh", "-c", "python /app/qwesdk_entrypoint.py"]