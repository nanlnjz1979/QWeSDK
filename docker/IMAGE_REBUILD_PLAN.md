# QWeSDK Docker 镜像依赖分析与改造方案

## 1. 当前报错的原因

qwesdk:latest 不是 Docker Hub 官方镜像，只是项目业务镜像的本地标签。
执行 docker pull qwesdk:latest 会访问 Docker Hub 的 library/qwesdk；该仓库不存在，所以出现 pull access denied。本机也没有提前构建该镜像时，部署脚本无法继续。

不能直接把 QWESDK_IMAGE 改成 python:3.11-slim。官方 Python 镜像只有 Python，没有 Celery、VnPy、TA-Lib、任务代码和启动入口，无法直接作为 Worker 运行。

正确关系：

~~~text
python:3.11-slim-bookworm 官方基础镜像
  -> 安装系统和 Python 依赖
  -> 加入 Celery、任务代码和自动升级入口
  -> 构建 QWeSDK Worker 业务镜像
  -> 推送到实际镜像仓库
  -> 服务器拉取业务镜像并创建容器
~~~

## 2. 推荐基础镜像

推荐使用：

~~~dockerfile
FROM python:3.11-slim-bookworm
~~~

正式发布时进一步锁定经过测试的镜像 digest。

选择理由：

- QWeSDK 声明 Python >= 3.10，当前主要面向 Python 3.11。
- Debian/glibc 对 VnPy、NumPy、Pandas、DuckDB、PySide6 和 TA-Lib 的 wheel 支持较成熟。
- bookworm 固定了 Debian 发行版；python:3.11-slim 是浮动标签，底层系统可能变化。
- 官方镜像同时支持 linux/amd64 和 linux/arm64，适合当前 ARM64 Mac 和常见 x86_64 Linux 服务器。
- 不建议 Alpine。Alpine 使用 musl，数值计算、TA-Lib 和 Qt 依赖更容易退化为源码编译。
- 不建议完整 python:3.11，Worker 不需要完整 Debian 工具集，镜像会明显增大。

## 3. 已确认的真实依赖

QWeSDK wheel 当前元数据的 dependencies 为空，但 m 包实际直接依赖：

| 分类 | 依赖 | 当前状态 | 建议 |
|---|---|---|---|
| 任务队列 | Celery、Redis Python Client | 部分固定 | 固定并保留 |
| 回测框架 | VnPy、vnpy_ctastrategy | 已固定 | 保留并做最小回测测试 |
| 数值表格 | NumPy、Pandas | 未固定 | 写入锁定文件 |
| 技术指标 | TA-Lib | Python 包未固定，另编译旧 C 库 | 统一版本并验证双架构 |
| 查询计算 | Ibis、DuckDB | 未固定 | 锁定；Ibis API 变化风险高 |
| 表达式 | Lark | 未固定 | 锁定 |
| 绘图 | Matplotlib | 未固定 | 锁定，继续使用 Agg 后端 |
| HTTP | Requests | 未固定 | 锁定 |
| Worker Pool | gevent | 已安装，默认却用 prefork | 不使用 gevent pool 时移除 |

VnPy 4.2.0 会带入 PySide6/Qt，因此镜像较大。当前 m 包导入时会加载 trader 模块，不能在没有回归测试时直接删掉 VnPy/Qt。后续可把 V1 后端改成延迟导入，再拆分轻量 V2 Worker。

## 4. 推荐依赖分层

基础业务镜像固定安装以下内容：

- Python 3.11 和 Debian Bookworm。
- Celery、Redis Python Client。
- VnPy、vnpy_ctastrategy。
- NumPy、Pandas、TA-Lib、Ibis、DuckDB、Lark、Matplotlib、Requests。
- docker/worker/start_qwesdk.sh、docker/worker/qwesdk_entrypoint.py；celery_app.py 和 tasks.py 已进入 QWeSDK wheel 的 m/worker。

这些依赖在构建镜像时安装并测试，不应在容器每次启动时联网安装。

可热更新部分只保留 qwesdk-x.y.z-py3-none-any.whl。宿主机目录 ../dist 挂载到容器 /packages，启动时只安装 QWeSDK wheel，并继续使用 --no-deps，防止 SDK 热更新改变已经验证的底层环境。

SDK 新版本如果需要新增或升级第三方依赖，应先发布新 Worker 镜像，再发布对应 QWeSDK wheel。

## 5. 依赖锁定

建议新增：

~~~text
docker/worker/requirements.in
docker/worker/requirements.lock
~~~

requirements.in 记录直接依赖，requirements.lock 保存完整解析结果。首份锁文件必须来自一份已通过测试的镜像，不能直接采用构建当天的全部最新版。

构建阶段至少执行：

~~~bash
python -m pip check
python -c "import m, celery, vnpy, vnpy_ctastrategy, talib, ibis, duckdb"
~~~

随后执行一个最小 V1 和 V2 回测，重点验证 Pandas、Ibis 和 VnPy API 兼容性。

## 6. TA-Lib 方案

当前 Dockerfile 编译 TA-Lib C 0.4.0，但 Python ta-lib 包没有固定版本，构建不可复现。

优先方案：

1. 在 linux/amd64 和 linux/arm64 上测试固定版本的 TA-Lib manylinux wheel。
2. 两个架构都有 wheel 时，删除手工下载和编译 C 0.4.0 的步骤。
3. 构建时要求二进制 wheel，防止静默退化为源码编译。

回退方案：目标平台没有 wheel 时使用多阶段构建。在 builder 阶段编译兼容版本的 TA-Lib C 库，只把运行库复制到最终镜像，最终镜像不保留 gcc、g++、make、wget 和源码。

## 7. 镜像命名与发布

生产环境不要使用来源不明确的 qwesdk:latest。建议：

~~~ini
QWESDK_IMAGE=registry.example.com/helix/qwesdk-worker:1.0.0
~~~

双架构发布示例：

~~~bash
docker buildx build \
  --platform linux/amd64,linux/arm64 \
  -t registry.example.com/helix/qwesdk-worker:1.0.0 \
  -t registry.example.com/helix/qwesdk-worker:stable \
  --push \
  -f docker/worker/Dockerfile .
~~~

生产部署使用版本号或 digest，不使用 latest。

没有镜像仓库时，开发机可执行：

~~~bash
docker build -t qwesdk-worker:local -f docker/worker/Dockerfile .
~~~

然后设置 QWESDK_IMAGE=qwesdk-worker:local。这只能在已经构建镜像的机器上使用，另一台服务器无法直接拉取。

## 8. 部署脚本改造

应明确区分两种镜像来源：

~~~ini
QWESDK_IMAGE_SOURCE=pull
QWESDK_IMAGE=registry.example.com/helix/qwesdk-worker:1.0.0
~~~

- pull：生产模式。只拉实际仓库镜像；失败立即退出，并提示检查地址和 docker login。
- build：开发模式。从 docker/worker/Dockerfile 本地构建，不尝试拉业务镜像。

建议命令：

~~~bash
./docker/deploy_qwesdk.sh build
./docker/deploy_qwesdk.sh up
./docker/deploy_qwesdk.sh upgrade
./docker/deploy_qwesdk.sh status
./docker/deploy_qwesdk.sh logs
./docker/deploy_qwesdk.sh down
~~~

up 不应在生产拉取失败后静默本地构建，否则仓库配置或权限错误可能被掩盖，服务器会运行一个未发布的镜像。

## 9. Redis

QWeSDK Compose 继续不创建 Redis。可使用两种方式：

1. Redis 映射宿主机端口：redis://host.docker.internal:6379/0。
2. Redis 与 QWeSDK 加入同一个外部 Docker 网络：redis://Redis容器名:6379/0。

生产更推荐外部 Docker 网络；宿主机端口方式适合本地开发。Redis 地址、密码和数据库编号只通过环境变量传入，不写进镜像。

## 10. 分步实施顺序

### 第一步：可重复构建

- 基础镜像改为 python:3.11-slim-bookworm。
- 提取并锁定 Python 依赖。
- 解决 TA-Lib wheel 或多阶段编译。
- 构建后执行 pip check、关键导入测试和最小回测。

验收：同一提交连续构建两次，依赖版本一致；ARM64 和 AMD64 均能启动。

### 第二步：镜像来源明确化

- 增加 pull/build 模式。
- 默认业务镜像改为实际仓库地址，未配置时给出明确错误。
- 不再把 qwesdk:latest 当作 Docker Hub 可下载镜像。

验收：开发机可本地构建；新服务器只凭仓库凭据即可拉取并启动。

### 第三步：QWeSDK 热更新

- 保留 /packages 只读挂载。
- 生产只接受 wheel，tar.gz 仅兼容旧流程。
- 安装前校验 SHA-256、包名和版本。
- 损坏包或安装失败时不启动错误版本。

验收：旧包不重复安装，新包启动时升级，损坏包被拒绝。

### 第四步：运行安全和回测隔离

- Worker 使用非 root 用户。
- 不在 Celery 主 Worker 进程内直接 exec 用户策略代码。
- 每个回测使用独立子进程或临时容器，限制 CPU、内存、时间和输出大小。
- 结果使用结构化 JSON 返回 Helix，大日志和结果文件写对象存储。

验收：单个策略超时、崩溃或内存超限不会拖垮 Worker。

## 11. 最终选择

- 官方基础镜像：python:3.11-slim-bookworm，正式构建锁定 digest。
- 可部署业务镜像：实际仓库/helix/qwesdk-worker:版本号。
- SDK 更新包：qwesdk-x.y.z-py3-none-any.whl，通过 ../dist 挂载。
- Redis：外部单独管理，不进入 QWeSDK Compose。
- qwesdk:latest：仅能作为本地标签，不应作为生产默认拉取地址。
