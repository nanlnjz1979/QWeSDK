# QWeSDK 完整部署指南

本指南将帮助您完成QWeSDK的安装、本地包部署和Docker容器化部署，实现量化交易策略的开发、测试和运行。

## 1. 安装指南

### 1.1 安装包说明

QWeSDK提供了两种安装包格式：

- **源代码包**：`qwesdk-1.0.0.tar.gz`
- **二进制wheel包**：`qwesdk-1.0.0-py3-none-any.whl`

这两种包都可以在本地环境中安装和使用。

### 1.2 安装方法

#### 1.2.1 方法一：直接从dist目录安装

```bash
# 使用pip安装wheel包
pip install dist/qwesdk-1.0.0-py3-none-any.whl

# 或安装源代码包
pip install dist/qwesdk-1.0.0.tar.gz
```

#### 1.2.2 方法二：开发模式安装（适合开发人员）

```bash
# 进入QWeSDK目录
cd d:\work\QWeSDK\QWeSDK

# 开发模式安装（修改代码后立即生效）
pip install -e .
```

#### 1.2.3 方法三：将dist目录作为本地源安装

```bash
# 进入QWeSDK目录
cd d:\work\QWeSDK\QWeSDK

# 将dist目录作为本地源安装
pip install --find-links=dist qwesdk
```

### 1.3 验证安装

安装完成后，可以通过以下方式验证：

```bash
# 验证m模块是否可以正常导入
python -c "import m; print('m module imported successfully')"

# 运行测试命令
qwesdk-test

# 运行使用示例
python example_usage.py
```

### 1.4 使用示例

#### 1.4.1 基本使用

```python
# 导入m模块
import m

# 使用selector.v1函数
m1 = m.selector.v1(
    exchanges=["上交所", "深交所"],
    list_sectors=["主板", "创业板"],
    st_statuses=["正常"],
    drop_suspended=True,
    m_name="m1"
)

# 打印选股结果
print(m1.get_selected_stocks())
```

#### 1.4.2 使用trader进行回测

```python
import m

# 定义策略函数
def initialize(context):
    print(f"初始化，初始资金: {context['portfolio']['cash']}")

def handle_data(context, data):
    # 策略逻辑
    pass

# 创建trader实例
m7 = m.trader.v2(
    data=m3,  # 假设m3是已准备好的数据
    initialize=initialize,
    handle_data=handle_data,
    capital_base=1000000,
    frequency="daily"
)

# 运行回测
m7._run_daily()
```

### 1.5 命令行工具

QWeSDK提供了一个命令行工具：

```bash
# 运行测试脚本
qwesdk-test
```

### 1.6 卸载方法

```bash
# 卸载QWeSDK
pip uninstall qwesdk
```

### 1.7 升级方法

```bash
# 升级到新版本（需先构建新版本包）
pip install --upgrade dist/qwesdk-1.1.0-py3-none-any.whl
```

## 2. 本地包安装方案

### 2.1 方案说明

本方案将 QWeSDK 打包为标准 Python 安装包，并在 Docker 构建过程中从本地 `packages` 目录安装，实现以下优势：

- **安装包集中管理**：所有安装包放在同一目录，便于版本管理和更新
- **构建过程简化**：Docker 构建时直接从本地安装，无需网络下载
- **版本控制**：可随时切换不同版本的安装包
- **环境一致性**：确保在任何环境中使用相同版本的 SDK

### 2.2 目录结构

```
QWeSDK/
├── packages/                # 本地安装包目录
│   ├── qwesdk-1.0.0-py3-none-any.whl  # Wheel包（推荐）
│   └── qwesdk-1.0.0.tar.gz            # 源代码包
├── Dockerfile.localpkg      # 从本地包安装的Dockerfile
├── docker-compose.localpkg.yml  # 本地包安装的Docker Compose配置
├── config.json              # SDK配置文件
├── test_bigtrader.py        # 测试脚本
└── data/                    # 数据目录（自动创建）
```

### 2.3 准备工作

#### 2.3.1 构建安装包

```bash
# 进入QWeSDK目录
cd d:\work\QWeSDK\QWeSDK

# 构建安装包
python setup.py sdist bdist_wheel

# 复制到packages目录
mkdir -p packages
cp dist/qwesdk-1.0.0-py3-none-any.whl packages/
cp dist/qwesdk-1.0.0.tar.gz packages/
```

#### 2.3.2 配置文件准备

确保以下文件存在：
- `config.json`：SDK配置文件
- `test_bigtrader.py`：测试脚本
- `redis.conf`：Redis配置文件（如果需要）

### 2.4 部署步骤

#### 步骤一：复制文件到目标服务器

```bash
# 复制所有文件到服务器
scp -r d:\work\QWeSDK\QWeSDK\* nn@192.168.1.18:/docker/cerely/
```

#### 步骤二：使用Docker Compose启动服务

```bash
# 登录服务器
ssh nn@192.168.1.18

# 进入目录
cd /docker/cerely

# 使用本地包安装配置启动服务
docker-compose -f docker-compose.localpkg.yml up -d --build
```

#### 步骤三：验证部署

```bash
# 查看服务状态
docker-compose -f docker-compose.localpkg.yml ps

# 查看QWeSDK日志
docker-compose -f docker-compose.localpkg.yml logs -f qwesdk

# 测试QWeSDK功能
docker exec -it cerely_qwesdk_1 python test_bigtrader.py
```

### 2.5 核心配置说明

#### Dockerfile.localpkg

```dockerfile
# 从本地packages目录复制安装包
COPY packages /app/packages

# 使用本地wheel包安装QWeSDK
RUN pip install --no-cache-dir /app/packages/qwesdk-1.0.0-py3-none-any.whl
```

#### docker-compose.localpkg.yml

```yaml
qwesdk:
  build:
    context: .
    dockerfile: Dockerfile.localpkg  # 使用本地包安装的Dockerfile
  image: qwesdk:localpkg
  volumes:
    - ./packages:/app/packages       # 挂载packages目录
    - ./data:/app/data               # 数据目录
    - ./output:/app/output           # 输出目录
    - ./config.json:/app/config.json  # 配置文件
```

### 2.6 版本更新

#### 1. 构建新版本

```bash
# 更新版本号（修改setup.py中的version）
# 构建新版本
python setup.py sdist bdist_wheel

# 复制到packages目录
cp dist/qwesdk-1.1.0-py3-none-any.whl packages/
```

#### 2. 更新Dockerfile

修改 `Dockerfile.localpkg` 中的安装命令：

```dockerfile
# 更新为新版本
RUN pip install --no-cache-dir /app/packages/qwesdk-1.1.0-py3-none-any.whl
```

#### 3. 重新构建和部署

```bash
docker-compose -f docker-compose.localpkg.yml up -d --build
```

### 2.7 多版本管理

在 `packages` 目录中可以存放多个版本的安装包，通过修改 `Dockerfile.localpkg` 中的安装命令切换版本：

```dockerfile
# 使用1.0.0版本
RUN pip install --no-cache-dir /app/packages/qwesdk-1.0.0-py3-none-any.whl

# 或使用1.1.0版本
RUN pip install --no-cache-dir /app/packages/qwesdk-1.1.0-py3-none-any.whl
```

### 2.8 优势总结

1. **安装包集中管理**：所有版本的安装包放在同一目录
2. **构建速度快**：从本地安装，无需网络下载
3. **版本控制简单**：通过修改Dockerfile切换版本
4. **环境一致性**：确保所有环境使用相同版本的SDK
5. **部署便捷**：只需复制packages目录和配置文件即可

### 2.9 故障排除

#### 1. 安装包不存在

```bash
# 检查packages目录
ls -la packages/

# 重新构建安装包
python setup.py sdist bdist_wheel
cp dist/*.whl packages/
cp dist/*.tar.gz packages/
```

#### 2. 构建失败

```bash
# 查看详细构建日志
docker-compose -f docker-compose.localpkg.yml build --no-cache
```

#### 3. 版本冲突

```bash
# 清理旧版本
rm -rf packages/
mkdir -p packages
cp dist/latest-version.whl packages/
```

### 2.10 与现有环境集成

本方案可以与现有的 Redis、Celery 等服务无缝集成，通过 `docker-compose.localpkg.yml` 配置文件定义服务间的依赖关系。

## 3. Docker部署指南

### 3.1 部署前准备

#### 1. 安装Docker和Docker Compose

- [Docker安装指南](https://docs.docker.com/get-docker/)
- [Docker Compose安装指南](https://docs.docker.com/compose/install/)

#### 2. 克隆或下载SDK代码

确保您已获取完整的QWeSDK代码库。

### 3.2 部署方式

#### 方式一：使用Docker Compose（推荐）

Docker Compose可以简化容器的构建和运行过程。

##### 1. 构建和运行容器

在SDK根目录执行以下命令：

```bash
docker-compose up --build
```

- `--build` 选项表示每次运行前重新构建镜像

##### 2. 后台运行容器

```bash
docker-compose up -d
```

##### 3. 查看容器日志

```bash
docker-compose logs -f
```

##### 4. 停止容器

```bash
docker-compose down
```

#### 方式二：手动使用Docker命令

如果您更喜欢手动操作，可以使用Docker命令直接构建和运行。

##### 1. 构建Docker镜像

```bash
docker build -t qwesdk .
```

##### 2. 运行Docker容器

```bash
docker run -it --name qwesdk \
  -v ./data:/app/data \
  -v ./output:/app/output \
  -v ./config.json:/app/config.json \
  qwesdk
```

参数说明：
- `-it`：交互式运行容器
- `--name qwesdk`：指定容器名称
- `-v`：挂载本地目录到容器中

### 3.3 自定义配置

#### 1. 修改配置文件

编辑 `config.json` 文件可以自定义SDK的配置参数。

#### 2. 运行自定义脚本

修改 `docker-compose.yml` 文件中的 `command` 字段，或者在运行容器时指定自定义命令：

```bash
docker run -it --name qwesdk qwesdk python your_script.py
```

### 3.4 数据持久化

Docker Compose配置中已经挂载了以下目录：

- `./data`：用于存储数据文件
- `./output`：用于存储输出结果
- `./config.json`：SDK配置文件

确保这些目录在容器外部存在，以便数据持久化。

### 3.5 开发工作流

1. 在本地修改SDK代码或策略脚本
2. 重新构建Docker镜像：`docker-compose up --build`
3. 运行并测试：`docker-compose up`
4. 查看输出结果：`docker-compose logs -f`

### 3.6 常见问题

#### 1. 构建镜像时依赖安装失败

如果遇到依赖安装问题，可以尝试：

- 检查网络连接
- 更新Docker镜像：`docker pull python:3.11-slim`
- 手动安装失败的依赖

#### 2. 容器运行时找不到模块

确保：
- PYTHONPATH环境变量已正确设置
- 所有依赖已在requirements.txt中列出
- 代码结构正确

#### 3. 权限问题

如果遇到文件读写权限问题，可以尝试：

```bash
sudo chmod -R 777 ./data ./output
```

### 3.7 高级配置

#### 1. 多容器部署

如果需要部署多个实例或与其他服务（如数据库）配合使用，可以扩展docker-compose.yml文件。

#### 2. 使用GPU加速

如果SDK需要GPU加速，可以修改Dockerfile使用支持GPU的基础镜像，并在运行时添加GPU相关参数。

#### 3. 优化镜像大小

可以通过以下方式优化镜像大小：

- 使用更小的基础镜像
- 清理临时文件
- 使用多阶段构建

### 3.8 测试部署

部署完成后，可以运行测试脚本来验证SDK是否正常工作：

```bash
docker-compose up
```

如果看到"测试成功：v1 函数实现正确"，则表示部署成功。

### 3.9 版本更新

当SDK代码更新时，需要重新构建镜像：

```bash
docker-compose build --no-cache
```

## 4. 统一目录结构

### 4.1 完整目录结构

```
QWeSDK/
├── build/             # 构建目录
├── dist/              # 分发目录（构建输出）
├── docker/            # Docker相关文件
│   ├── app/           # 应用目录
│   │   ├── Dockerfile
│   │   ├── celery_app.py
│   │   ├── entrypoint.sh
│   │   ├── main.py
│   │   ├── qwesdk-1.0.0-py3-none-any.whl
│   │   ├── qwesdk-1.0.0.tar.gz
│   │   ├── qwesdk_entrypoint.py
│   │   ├── requirements.txt
│   │   └── tasks.py
│   ├── README.md
│   ├── docker-compose.yml
│   ├── docker_manager.bat
│   ├── docker_manager.sh
│   └── redis.conf
├── m/                 # SDK核心代码
│   ├── config/        # 配置模块
│   ├── core/          # 核心功能模块
│   ├── db/            # 数据库模块
│   ├── extract_data/  # 数据提取模块
│   ├── input/         # 数据输入模块
│   ├── selector/      # 选股模块
│   ├── strategy/      # 策略模块
│   └── trader/        # 回测模块
├── packages/          # 打包相关文件
│   ├── MANIFEST.in
│   ├── README.md
│   ├── config.json
│   ├── qwesdk-1.0.0-py3-none-any.whl
│   ├── qwesdk-1.0.0.tar.gz
│   ├── requirements.txt
│   ├── setup.py
│   └── test_bigtrader.py
├── qwesdk.egg-info/   # 包信息目录
├── data/              # 数据目录
├── output/            # 输出目录
├── DEPLOYMENT_GUIDE.md
├── INSTALLATION_GUIDE.md
├── LOCAL_PACKAGE_INSTALLATION.md
├── README_DOCKER.md
└── example_usage.py
```

### 4.2 安装后目录结构

安装后，QWeSDK的目录结构如下：

```
qwesdk/
├── m/                   # SDK核心代码
│   ├── config/          # 配置模块
│   ├── core/            # 核心功能模块
│   ├── db/              # 数据库模块
│   ├── extract_data/    # 数据提取模块
│   ├── input/           # 数据输入模块
│   ├── selector/        # 选股模块
│   ├── strategy/        # 策略模块
│   └── trader/          # 回测模块
├── config.json          # 配置文件
├── test_bigtrader.py    # 测试脚本
└── example_usage.py     # 使用示例
```

## 5. 常见问题汇总

### 5.1 安装问题

#### 安装时依赖包冲突

```bash
# 使用--no-deps选项忽略依赖，手动安装所需依赖
pip install --no-deps dist/qwesdk-1.0.0-py3-none-any.whl
```

#### 导入m模块时出错

确保：
- QWeSDK已正确安装
- Python版本≥3.10
- 所有依赖包已正确安装

#### 运行测试脚本时出错

检查：
- 网络连接是否正常（部分功能可能需要网络）
- 配置文件`config.json`是否存在且配置正确
- 依赖包版本是否符合要求

### 5.2 Docker部署问题

#### 构建镜像时依赖安装失败

如果遇到依赖安装问题，可以尝试：
- 检查网络连接
- 更新Docker镜像：`docker pull python:3.11-slim`
- 手动安装失败的依赖

#### 容器运行时找不到模块

确保：
- PYTHONPATH环境变量已正确设置
- 所有依赖已在requirements.txt中列出
- 代码结构正确

#### 权限问题

如果遇到文件读写权限问题，可以尝试：

```bash
sudo chmod -R 777 ./data ./output
```

### 5.3 本地包安装问题

#### 安装包不存在

```bash
# 检查packages目录
ls -la packages/

# 重新构建安装包
python setup.py sdist bdist_wheel
cp dist/*.whl packages/
cp dist/*.tar.gz packages/
```

#### 构建失败

```bash
# 查看详细构建日志
docker-compose -f docker-compose.localpkg.yml build --no-cache
```

#### 版本冲突

```bash
# 清理旧版本
rm -rf packages/
mkdir -p packages
cp dist/latest-version.whl packages/
```

## 6. 开发说明

### 6.1 构建新的安装包

```bash
# 清理旧的构建文件
python setup.py clean --all

# 构建新的安装包
python setup.py sdist bdist_wheel
```

新的安装包将生成在`dist`目录中。

### 6.2 修改配置文件

安装后的配置文件位置：
- 开发模式：`d:\work\QWeSDK\QWeSDK\config.json`
- 正常安装：根据Python环境不同，通常在`site-packages/m`目录下

## 7. QWeSDK 包更新指南

### 7.1 构建新版本包

当您修改了QWeSDK的代码或配置后，需要构建新版本的安装包：

```bash
# 清理旧的构建文件
python setup.py clean --all

# 构建新的安装包
python setup.py sdist bdist_wheel
```

新的安装包将生成在`dist`目录中，包括：
- `qwesdk-x.y.z.tar.gz`（源代码包）
- `qwesdk-x.y.z-py3-none-any.whl`（Wheel包）

### 7.2 本地环境更新

#### 7.2.1 直接更新

```bash
# 使用pip更新到新版本
pip install --upgrade dist/qwesdk-x.y.z-py3-none-any.whl

# 或使用源代码包更新
pip install --upgrade dist/qwesdk-x.y.z.tar.gz
```

#### 7.2.2 开发模式更新

如果您使用开发模式安装，修改代码后会立即生效，无需重新安装。

### 7.3 Docker环境更新

#### 7.3.1 更新本地包目录

```bash
# 复制新构建的包到packages目录
cp dist/qwesdk-x.y.z-py3-none-any.whl packages/
cp dist/qwesdk-x.y.z.tar.gz packages/
```

#### 7.3.2 更新Docker镜像

```bash
# 重新构建Docker镜像
docker-compose build --no-cache

# 启动更新后的服务
docker-compose up -d
```

#### 7.3.3 验证更新

```bash
# 查看服务状态
docker-compose ps

# 查看日志，确认版本更新
docker-compose logs celery
```

### 7.4 版本管理最佳实践

1. **版本号规范**：使用语义化版本号（如1.0.0, 1.0.1, 1.1.0）
2. **版本控制**：在源代码管理系统中标记重要版本
3. **包备份**：保留重要版本的安装包，以便回滚
4. **更新日志**：记录每个版本的主要更改

## 8. 总结

### 8.1 安装方式对比

| 安装方式 | 优势 | 适用场景 |
|---------|------|----------|
| 直接安装 | 简单快捷 | 快速测试和使用 |
| 开发模式 | 修改代码后立即生效 | 开发和调试 |
| 本地包安装 | 版本控制简单，构建速度快 | 多环境部署，版本管理 |
| Docker部署 | 环境一致性，简化部署 | 生产环境，多服务集成 |

### 8.2 最佳实践

1. **开发阶段**：使用开发模式安装，便于代码修改和调试
2. **测试阶段**：使用本地包安装，确保版本一致性
3. **生产阶段**：使用Docker部署，实现环境隔离和标准化

### 8.3 部署流程建议

1. 在本地开发和测试SDK代码
2. 构建安装包并复制到packages目录
3. 使用Docker Compose部署到测试环境
4. 验证功能正常后，部署到生产环境
5. 定期更新版本，保持SDK功能最新

通过本指南，您应该能够顺利完成QWeSDK的安装、部署、更新和管理，为量化交易策略的开发和运行提供稳定可靠的环境。

祝您使用QWeSDK开发出优秀的量化交易策略！