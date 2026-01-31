# Docker管理脚本使用指南

本文档介绍如何使用Docker管理脚本管理QWeSDK的Docker环境。

## 脚本说明

我们提供了两个版本的管理脚本：

| 脚本名称 | 适用系统 | 功能 |
|---------|---------|------|
| `docker_manager.sh` | Linux/Mac | Shell脚本 |
| `docker_manager.bat` | Windows | 批处理脚本 |

两个脚本功能完全相同，只是针对不同操作系统做了适配。

## 功能列表

| 命令 | 描述 |
|------|------|
| `build` | 构建Docker镜像，自动检测并安装QWeSDK包 |
| `up` | 启动所有服务（Redis、Celery、Runner、QWeSDK） |
| `down` | 停止并移除所有服务 |
| `restart` | 重启所有服务 |
| `status` | 查看服务状态 |
| `logs` | 查看服务日志（实时更新） |
| `ps` | 查看容器状态 |
| `images` | 查看镜像状态 |
| `clean` | 清理Docker资源（网络、镜像、卷） |
| `help` | 显示帮助信息 |

## 使用方法

### Linux/Mac系统

1. **进入脚本目录**
   ```bash
   cd docker
   ```

2. **赋予脚本执行权限**
   ```bash
   chmod +x docker_manager.sh
   ```

3. **执行脚本**
   ```bash
   ./docker_manager.sh [命令]
   ```

### Windows系统

1. **进入脚本目录**
   在文件资源管理器中进入 `docker` 目录

2. **执行脚本**
   在命令提示符或PowerShell中执行：
   ```cmd
   docker_manager.bat [命令]
   ```

## 常用操作示例

### 1. 构建Docker镜像

```bash
# Linux/Mac
./docker_manager.sh build

# Windows
docker_manager.bat build
```

**功能**：构建所有Docker镜像，包括自动检测和安装QWeSDK包。

### 2. 启动服务

```bash
# Linux/Mac
./docker_manager.sh up

# Windows
docker_manager.bat up
```

**功能**：启动所有服务并在后台运行。

### 3. 查看服务状态

```bash
# Linux/Mac
./docker_manager.sh status

# Windows
docker_manager.bat status
```

**功能**：查看所有服务的运行状态。

### 4. 查看服务日志

```bash
# Linux/Mac
./docker_manager.sh logs

# Windows
docker_manager.bat logs
```

**功能**：查看所有服务的日志，按 `Ctrl+C` 退出。

### 5. 停止服务

```bash
# Linux/Mac
./docker_manager.sh down

# Windows
docker_manager.bat down
```

**功能**：停止并移除所有服务。

### 6. 重启服务

```bash
# Linux/Mac
./docker_manager.sh restart

# Windows
docker_manager.bat restart
```

**功能**：停止然后重新启动所有服务。

### 7. 清理Docker资源

```bash
# Linux/Mac
./docker_manager.sh clean

# Windows
docker_manager.bat clean
```

**功能**：清理未使用的Docker资源，包括网络、镜像和卷。

## 版本管理

### 更新QWeSDK版本

1. **将新版本的包文件放入 `docker/app/` 目录**
   ```
docker/app/
└── qwesdk-1.1.0.tar.gz    # 新版本
```

2. **重新构建Docker镜像**
   ```bash
   ./docker_manager.sh build
   ```

3. **重启服务**
   ```bash
   ./docker_manager.sh restart
   ```

### 查看当前版本

```bash
# 查看QWeSDK服务的日志，其中包含版本信息
./docker_manager.sh logs
```

## 故障排除

### 1. 脚本执行权限问题

**Linux/Mac**：
```bash
chmod +x docker_manager.sh
```

### 2. Docker命令未找到

确保Docker和Docker Compose已正确安装并添加到系统路径中。

### 3. 端口冲突

如果启动失败，可能是端口6379（Redis）被占用，检查并释放该端口。

### 4. 构建失败

检查：
- QWeSDK包文件是否存在于 `docker/app/` 目录
- 网络连接是否正常
- 系统资源是否足够

### 5. 版本检测失败

检查：
- QWeSDK包文件名是否符合格式 `qwesdk-x.y.z.tar.gz`
- 包文件是否完整

## 高级配置

### 自定义Docker Compose文件

如果需要使用自定义的Docker Compose文件，可以修改脚本中的 `DOCKER_COMPOSE_FILE` 变量。

### 环境变量

脚本会继承系统的环境变量，包括Docker相关的配置。

## 总结

Docker管理脚本提供了一站式的Docker环境管理解决方案，包括：

- **自动版本检测**：构建和运行时自动检测QWeSDK版本
- **一键操作**：简化Docker命令的执行
- **状态监控**：实时查看服务状态和日志
- **资源管理**：清理未使用的Docker资源

通过这些脚本，您可以更方便地管理QWeSDK的Docker环境，无需记住复杂的Docker命令。
