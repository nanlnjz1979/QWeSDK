# QWeSDK Docker 使用说明

本文档说明 QWeSDK Worker 镜像、容器、启动脚本、SDK 安装包自动升级、外部 Redis 和 R1 安全执行边界的使用方法。

## 1. 运行结构

QWeSDK Docker 环境只管理一个 Celery Worker，不创建 Redis：

~~~text
外部 Redis
    ↑ Celery Broker / Result Backend
qwesdk-worker 容器
    ↑ 启动时扫描 /packages
宿主机 QWeSDK/dist/*.whl
~~~

相关名称：

| 项目 | 默认名称 | 说明 |
|---|---|---|
| Compose 项目 | qwesdk-runtime | Docker Desktop 中显示的容器分组 |
| 业务镜像 | qwesdk:latest | 本地开发镜像；生产必须替换为固定版本或 digest |
| Worker 容器 | qwesdk-worker | 实际运行 Celery 的容器 |
| SDK 包目录 | ../dist | 相对于 docker 目录，即项目的 dist 目录 |
| 容器包目录 | /packages | 只读挂载，启动时从这里读取最新版 QWeSDK |
| SDK 安装目录 | /var/lib/qwesdk/python | 命名卷，非 root Worker 仅将升级包安装到这里 |

Docker Desktop 中 qwesdk-runtime 是 Compose 分组，不是容器，所以该行的 Container ID、Image 和 Port(s) 显示为横线。展开左侧箭头后，才能看到实际的 qwesdk-worker 容器。

qwesdk-worker 没有 Port(s) 是正常现象。Celery Worker 主动连接 Redis，不提供 HTTP 服务，因此不需要向宿主机发布端口。

## 2. 文件说明

| 文件 | 用途 |
|---|---|
| deploy_qwesdk.sh | 创建、升级、重启、查看和删除运行容器 |
| qwesdk-runtime.env | 镜像、容器、Redis 和 Celery 参数 |
| docker-compose.runtime.yml | 生产/运行时 Worker 编排 |
| app/Dockerfile | 构建 QWeSDK Worker 业务镜像 |
| app/start_qwesdk.sh | 容器入口：升级 SDK 后启动 Celery |
| app/qwesdk_entrypoint.py | 查找和安装最新 QWeSDK wheel 到可写 SDK 卷 |
| app/sandbox_runner.py | 每任务独立非 root 子进程、超时、取消和输出限制 |
| app/worker_protocol.py | RunSpec 校验和 JSON Lines 事件协议 |
| start_qwesdk.sh | 本地开发入口：构建镜像并启动 Celery |
| ../build_qwesdk_package.sh | 将 m 目录打包为 wheel 和 tar.gz |

## 3. 使用前准备

要求：

- 已安装并启动 Docker Desktop 或 Docker Engine。
- Docker Compose V2 可用，即 docker compose 命令可执行。
- Redis 已单独运行。
- 第一次启动前已经构建本地业务镜像，或者已经配置真实的远程镜像仓库。

所有以下命令默认从项目根目录执行：

~~~bash
cd /Users/nan/git/QWeSDK
~~~

首次赋予脚本执行权限：

~~~bash
chmod +x build_qwesdk_package.sh
chmod +x docker/deploy_qwesdk.sh
chmod +x docker/start_qwesdk.sh
~~~

## 4. Redis 配置

QWeSDK 脚本不会下载、创建、停止或删除 Redis。

如果还没有 Redis，可单独创建：

~~~bash
docker run -d \
  --name redis \
  --restart unless-stopped \
  -p 6379:6379 \
  redis:latest
~~~

默认连接配置位于 qwesdk-runtime.env：

~~~ini
CELERY_BROKER_URL=redis://host.docker.internal:6379/0
CELERY_RESULT_BACKEND=redis://host.docker.internal:6379/0
~~~

Redis 在其他服务器时：

~~~ini
CELERY_BROKER_URL=redis://192.168.1.100:6379/0
CELERY_RESULT_BACKEND=redis://192.168.1.100:6379/0
~~~

Redis 有密码时：

~~~ini
CELERY_BROKER_URL=redis://:password@192.168.1.100:6379/0
CELERY_RESULT_BACKEND=redis://:password@192.168.1.100:6379/0
~~~

修改配置后执行 upgrade，让新环境变量进入重建的容器。

## 5. 镜像说明

### 5.1 基础镜像和业务镜像

app/Dockerfile 使用 Python 官方镜像作为基础，在其中安装 Celery、VnPy、TA-Lib、Pandas 等环境，再生成 QWeSDK Worker 业务镜像。

两者不能混用：

| 镜像 | 用途 |
|---|---|
| python:3.11.9-slim-bookworm | 构建业务镜像的固定基础，不能直接运行 QWeSDK Worker |
| qwesdk:latest | 当前本地业务镜像，包含 Worker 运行环境和启动代码 |
| 仓库地址/qwesdk-worker:版本 | 推荐的生产业务镜像名称 |

qwesdk:latest 不是 Docker Hub 上的公开镜像。直接执行 docker pull qwesdk:latest 通常会出现 pull access denied。脚本会在拉取失败后检查本机是否存在同名镜像；本地也不存在时会退出。

### 5.2 本地构建业务镜像

首次使用或修改 Dockerfile、Celery 代码、启动代码后执行：

~~~bash
docker build \
  -t qwesdk:latest \
  docker/app
~~~

检查镜像：

~~~bash
docker image inspect qwesdk:latest
docker images qwesdk
~~~

### 5.3 使用远程镜像仓库

正式部署应将镜像推送到实际仓库，并使用明确版本号。例如：

~~~bash
docker tag qwesdk:latest registry.example.com/helix/qwesdk-worker:1.0.0
docker push registry.example.com/helix/qwesdk-worker:1.0.0
~~~

修改 qwesdk-runtime.env：

~~~ini
QWESDK_IMAGE=registry.example.com/helix/qwesdk-worker:1.0.0
~~~

私有仓库先登录：

~~~bash
docker login registry.example.com
~~~

生产环境必须使用版本号或镜像摘要，禁止使用 latest 作为不可变发布标识。

### 5.4 R1 Worker 安全约束

Worker 只接受 `tasks.run_backtest`，不接受旧的任意代码任务。策略代码写入每任务独立目录，并通过 `python -I` 在非 root 子进程中执行；Celery 主进程不会 `exec` 用户代码。容器运行时启用只读根文件系统、`no-new-privileges`、丢弃全部 capabilities、PID/内存/CPU 限制，并将 `/tmp` 放在 `noexec,nosuid,nodev` tmpfs 中。

### 5.5 vn.py 的无 GUI 依赖

Worker 只执行回测，不启动 vn.py 图形界面。`app/Dockerfile` 因此使用 `--no-deps` 安装 `vnpy` 和 `vnpy_ctastrategy`，避免拉取 PySide6/Qt 等 GUI 依赖，再显式安装回测所需的无 GUI 依赖。镜像构建末尾会导入 `Direction` 和 `BacktestingEngine` 做 headless 检查；如果这两个导入失败，镜像不会生成。

不要在运行时包升级中引入 vn.py 的新依赖。底层 vn.py 版本和依赖由镜像构建、测试并发布；`dist` 中的 QWeSDK wheel 只通过 `--no-deps` 更新 SDK 自身代码。

RunSpec、事件字段和取消/超时语义以 Helix 的 [QWe 执行协议](../../Helix/docs/current/QWe执行协议.md) 及两个 JSON Schema 为准。R1 不接入公网 Java API；真实 Gateway mTLS/HMAC、事件幂等和结果产物校验在 R3 完成。

## 6. 构建 QWeSDK 安装包

QWeSDK 源代码位于 m 目录。打包前先在 pyproject.toml 中更新版本号：

~~~toml
version = "1.0.4"
~~~

执行：

~~~bash
./build_qwesdk_package.sh
~~~

输出文件位于 dist：

~~~text
dist/qwesdk-1.0.4-py3-none-any.whl
dist/qwesdk-1.0.4.tar.gz
~~~

宿主机 Python 3.9 不能直接构建要求 Python >= 3.10 的包。打包脚本会使用本地 qwesdk:latest 镜像中的 Python 3.11，因此 Python 3.9 主机必须先完成业务镜像构建。

生产升级优先使用 wheel。容器启动时会选择版本最高的包；同版本同时存在 wheel 和 tar.gz 时优先选择 wheel。

## 7. 容器启动脚本

主要入口是：

~~~bash
./docker/deploy_qwesdk.sh <命令>
~~~

支持的命令：

| 命令 | 用途 |
|---|---|
| up | 拉取或检查镜像，首次创建并启动 Worker |
| upgrade | 拉取或检查镜像，强制重建 Worker |
| restart | 重启现有 Worker，并重新检查 SDK 包 |
| status | 查看 Compose 中的 Worker 状态 |
| logs | 持续查看 Worker 日志 |
| down | 停止并删除 Worker 和本项目网络 |

### 7.1 首次创建和启动

~~~bash
./docker/deploy_qwesdk.sh up
~~~

执行流程：

1. 读取 docker/qwesdk-runtime.env。
2. 创建配置的 SDK 包目录。
3. 尝试拉取 QWESDK_IMAGE。
4. 拉取失败时检查本地是否已有同名镜像。
5. 创建 qwesdk-worker 容器。
6. 把宿主机 dist 只读挂载为 /packages，并挂载 qwesdk-python 命名卷到 /var/lib/qwesdk/python。
7. 将最高版本 QWeSDK 包通过 `pip --target` 安装或升级到 SDK 卷；基础 venv 和镜像层保持只读。
8. 通过 `PYTHONPATH=/var/lib/qwesdk/python:/app` 优先加载升级后的 SDK。
9. 启动 Celery Worker。

本地使用 qwesdk:latest 时，下面的组合是正常的：

~~~text
pull access denied for qwesdk
[qwesdk] 远程拉取失败，继续使用本地镜像: qwesdk:latest
~~~

如果随后显示“镜像不存在且拉取失败”，说明本地镜像也不存在，应先执行第 5.2 节的 docker build。

### 7.2 查看状态

~~~bash
./docker/deploy_qwesdk.sh status
~~~

也可以直接查看实际容器：

~~~bash
docker ps -a --filter name=qwesdk
~~~

正常结果包含：

~~~text
NAME            IMAGE           STATUS
qwesdk-worker   qwesdk:latest   Up ...
~~~

### 7.3 查看日志

~~~bash
./docker/deploy_qwesdk.sh logs
~~~

按 Ctrl+C 退出日志查看，不会停止 Worker。正常启动日志应包含：

~~~text
候选包: qwesdk-1.0.4-py3-none-any.whl (wheel)
QWeSDK 更新完成: 1.0.4
Connected to redis://...
celery@... ready.
~~~

### 7.4 重启 Worker

~~~bash
./docker/deploy_qwesdk.sh restart
~~~

适合只替换 dist 中的 QWeSDK wheel 后使用。容器重新启动时会再次扫描安装包；SDK 卷会保留当前版本。

注意：restart 不重新读取 Compose 配置。修改 qwesdk-runtime.env 后应使用 upgrade。

### 7.5 强制重建 Worker

~~~bash
./docker/deploy_qwesdk.sh upgrade
~~~

适用于：

- 重新构建了同名业务镜像。
- 修改了 qwesdk-runtime.env。
- 修改了 Compose 配置。
- 需要用新镜像替换现有容器。

### 7.6 停止并删除 Worker

~~~bash
./docker/deploy_qwesdk.sh down
~~~

该命令不操作外部 Redis，也不删除 dist 中的 QWeSDK 安装包。

## 8. 本地开发启动脚本

docker/start_qwesdk.sh 是开发入口，会使用 docker/docker-compose.yml 构建镜像并启动 Celery：

~~~bash
./docker/start_qwesdk.sh
~~~

它适合修改 app/Dockerfile、tasks.py、celery_app.py 或启动代码后的本地调试。部署和日常容器管理优先使用 deploy_qwesdk.sh，避免混用两套 Compose 项目。

## 9. 配置参数

配置文件为 docker/qwesdk-runtime.env：

~~~ini
QWESDK_IMAGE=qwesdk:latest
QWESDK_PACKAGE_PATH=../dist
QWESDK_CONTAINER_NAME=qwesdk-worker
QWESDK_INSTALL_TARGET=/var/lib/qwesdk/python

CELERY_BROKER_URL=redis://host.docker.internal:6379/0
CELERY_RESULT_BACKEND=redis://host.docker.internal:6379/0
CELERY_LOGLEVEL=INFO
CELERY_POOL=prefork
CELERY_CONCURRENCY=2
QWESDK_PIDS_LIMIT=64
QWESDK_MEMORY_LIMIT=1g
QWESDK_CPUS=2.0
QWESDK_TMPFS_SIZE=1g
~~~

QWESDK_PACKAGE_PATH 相对于 docker 目录解析：

~~~text
docker/../dist
-> QWeSDK/dist
-> 容器 /packages

容器还会挂载 Compose 命名卷 `qwesdk-python` 到 `/var/lib/qwesdk/python`。该卷是唯一允许非 root Worker 写入的位置，用于保留启动时自动升级的 SDK 代码；`/packages` 和镜像根文件系统保持只读。升级安装先写入该卷内部的临时目录，成功后才替换旧 SDK 文件，安装失败会继续保留旧版本。
~~~

也可以用其他配置文件启动：

~~~bash
QWESDK_CONFIG_FILE=/absolute/path/qwesdk-runtime.env \
  ./docker/deploy_qwesdk.sh up
~~~

## 10. 常用完整流程

### 10.1 新机器首次本地运行

~~~bash
cd /Users/nan/git/QWeSDK

docker build -t qwesdk:latest docker/app
./build_qwesdk_package.sh
./docker/deploy_qwesdk.sh up
./docker/deploy_qwesdk.sh logs
~~~

### 10.2 只更新 QWeSDK 代码

1. 修改 m 目录。
2. 更新 pyproject.toml 版本号。
3. 重新打包并重启。

~~~bash
./build_qwesdk_package.sh
./docker/deploy_qwesdk.sh restart
./docker/deploy_qwesdk.sh logs
~~~

### 10.3 更新 Docker 运行环境

~~~bash
docker build -t qwesdk:latest docker/app
./docker/deploy_qwesdk.sh upgrade
./docker/deploy_qwesdk.sh logs
~~~

### 10.4 生产服务器从仓库启动

~~~bash
docker login registry.example.com
./docker/deploy_qwesdk.sh up
./docker/deploy_qwesdk.sh status
./docker/deploy_qwesdk.sh logs
~~~

前提是 qwesdk-runtime.env 中的 QWESDK_IMAGE 已改为真实仓库地址。

## 11. 常见问题

### pull access denied for qwesdk

原因：qwesdk:latest 不是 Docker Hub 公共镜像。

开发机处理：

~~~bash
docker build -t qwesdk:latest docker/app
~~~

生产机处理：将 QWESDK_IMAGE 改成实际仓库地址，并执行 docker login。

### Docker Desktop 的 qwesdk-runtime 没有 ID、镜像和端口

qwesdk-runtime 是 Compose 分组。展开它即可看到 qwesdk-worker 的 Container ID 和 Image。

### qwesdk-worker 的 Port(s) 为空

正常。Worker 只连接 Redis，不对外监听端口。以后增加 HTTP API 时才需要配置端口映射。

### 容器反复重启

查看日志：

~~~bash
./docker/deploy_qwesdk.sh logs
~~~

重点检查：

- dist 中是否有合法的 qwesdk wheel。
- Redis 地址和密码是否正确。
- Redis 端口是否能从容器访问。
- QWeSDK 安装或关键模块导入是否失败。

### 新 wheel 没有自动安装

确保 pyproject.toml 已增加版本号，文件名符合 qwesdk-x.y.z-py3-none-any.whl，然后执行 restart 并查看日志。

## 12. 后续镜像改造

依赖锁定、Python 基础镜像、TA-Lib、多架构发布和生产镜像命名方案参见 IMAGE_REBUILD_PLAN.md。
