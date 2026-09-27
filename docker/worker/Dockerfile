FROM python:3.11.9-slim-bookworm

# ==========================
# 阿里云官方APT源（国内服务器专用）
# ==========================
RUN sed -i "s@deb.debian.org@mirrors.aliyun.com@g" /etc/apt/sources.list.d/debian.sources

# ==========================
# 基础编译依赖（极简、稳定）
# ==========================
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ make wget python3-venv \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Worker never needs root to install or execute strategy code at runtime.
RUN groupadd --system --gid 10001 qweworker \
    && useradd --system --uid 10001 --gid qweworker --home-dir /home/qweworker \
       --create-home --shell /usr/sbin/nologin qweworker \
    && mkdir -p /app/packages /tmp/qwesdk-runs /tmp/qwe-home /var/lib/qwesdk/python \
    && chown -R qweworker:qweworker /app /tmp/qwesdk-runs /tmp/qwe-home /var/lib/qwesdk

RUN python -m venv /opt/qwe-venv
ENV PATH=/opt/qwe-venv/bin:$PATH

# 环境配置
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8
ENV PYTHONIOENCODING=utf-8
ENV HOME=/tmp/qwe-home

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
RUN pip install --no-cache-dir celery==5.6.0 redis==5.2.0 gevent==25.9.1
# QWeSDK only imports vn.py's headless trader/backtesting modules. Installing
# vn.py with its default dependencies would pull PySide6/Qt, which is not
# needed by a Worker and has no matching wheel on some ARM64 mirrors.
RUN pip install --no-cache-dir --no-deps vnpy==4.2.0 vnpy_ctastrategy==1.3.3
RUN pip install --no-cache-dir \
    deap pyzmq plotly tqdm tzlocal loguru nbformat \
    ta-lib lark ibis-framework pyarrow pyarrow-hotfix duckdb matplotlib requests

RUN python - <<'PY'
from vnpy.trader.constant import Direction
from vnpy_ctastrategy.backtesting import BacktestingEngine
assert Direction.LONG
assert BacktestingEngine
print("headless vn.py backtesting imports: OK")
PY

RUN chown -R qweworker:qweworker /opt/qwe-venv

# ==========================
# 业务启动代码只保留容器入口；Worker 业务代码由启动时安装的 QWeSDK wheel 提供。
# 这样升级 wheel 就能升级 Worker 逻辑，不需要把 Python 源码重新复制进镜像。
# ==========================
COPY docker/worker/qwesdk_entrypoint.py docker/worker/start_qwesdk.sh ./
RUN chmod +x /app/start_qwesdk.sh

USER qweworker

ENTRYPOINT ["/app/start_qwesdk.sh"]
