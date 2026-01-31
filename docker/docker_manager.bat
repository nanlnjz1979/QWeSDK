@echo off
chcp 65001 >nul

:: Docker管理脚本（Windows版本）
:: 功能：管理QWeSDK的Docker环境

set "SCRIPT_VERSION=1.0.1"
set "DOCKER_COMPOSE_FILE=docker-compose.yml"

:: 检查必要的命令
echo 检查必要的命令...
echo ===================
docker --version >nul 2>&1
if %errorlevel% neq 0 (
    echo 错误: docker 命令未找到
    exit /b 1
)

docker-compose --version >nul 2>&1
if %errorlevel% neq 0 (
    echo 错误: docker-compose 命令未找到
    exit /b 1
)
echo 命令检查完成

:: 显示帮助信息
:show_help
echo Docker管理脚本 v%SCRIPT_VERSION%
echo ===================
echo 功能：管理QWeSDK的Docker环境
echo 
echo 用法: %~nx0 [选项] [服务名]
echo 
echo 选项:
echo   build     - 构建Docker镜像
echo   up        - 启动所有服务
echo   down      - 停止并移除所有服务
echo   restart   - 重启所有服务
echo   status    - 查看服务状态
echo   logs      - 查看服务日志
echo   ps        - 查看容器状态
echo   images    - 查看镜像状态
echo   clean     - 清理Docker资源
echo   exec      - 进入指定服务的容器环境
echo   help      - 显示此帮助信息
echo 
echo 服务名:
echo   qwesdk    - QWeSDK服务
echo   redis     - Redis服务
echo   celery    - Celery服务
echo   runner    - Runner服务
echo 
echo 示例:
echo   %~nx0 build    ^| 构建镜像
echo   %~nx0 up       ^| 启动服务
echo   %~nx0 status   ^| 查看状态
echo   %~nx0 exec qwesdk  ^| 进入qwesdk容器
echo   %~nx0 exec redis   ^| 进入redis容器
echo   %~nx0 down     ^| 停止服务
goto :eof

:: 构建Docker镜像
:build_images
echo 开始构建Docker镜像...
echo 工作目录: %~dp0
echo 使用配置文件: %DOCKER_COMPOSE_FILE%
echo 

:: 检查docker-compose.yml文件是否存在
if not exist "%~dp0%DOCKER_COMPOSE_FILE" (
    echo 错误: %DOCKER_COMPOSE_FILE% 文件不存在
    exit /b 1
)

:: 构建镜像
docker-compose -f "%~dp0%DOCKER_COMPOSE_FILE" build
if %errorlevel% equ 0 (
    echo 
    echo 构建成功!
) else (
    echo 
    echo 构建失败!
    exit /b 1
)
goto :eof

:: 启动服务
:start_services
echo 开始启动Docker服务...
echo 工作目录: %~dp0
echo 

docker-compose -f "%~dp0%DOCKER_COMPOSE_FILE" up -d
if %errorlevel% equ 0 (
    echo 
    echo 服务启动成功!
    echo 
    echo 服务状态:
    docker-compose -f "%~dp0%DOCKER_COMPOSE_FILE" ps
) else (
    echo 
    echo 服务启动失败!
    exit /b 1
)
goto :eof

:: 停止服务
:stop_services
echo 开始停止Docker服务...
echo 工作目录: %~dp0
echo 

docker-compose -f "%~dp0%DOCKER_COMPOSE_FILE" down
if %errorlevel% equ 0 (
    echo 
    echo 服务停止成功!
) else (
    echo 
    echo 服务停止失败!
    exit /b 1
)
goto :eof

:: 重启服务
:restart_services
echo 开始重启Docker服务...
call :stop_services
echo 
call :start_services
goto :eof

:: 查看服务状态
:show_status
echo 服务状态:
echo 工作目录: %~dp0
echo 

docker-compose -f "%~dp0%DOCKER_COMPOSE_FILE" ps
if %errorlevel% neq 0 (
    echo 
    echo 警告: 无法获取服务状态
)
goto :eof

:: 查看服务日志
:show_logs
echo 服务日志:
echo 工作目录: %~dp0
echo 按 Ctrl+C 退出日志查看
echo 

docker-compose -f "%~dp0%DOCKER_COMPOSE_FILE" logs -f
goto :eof

:: 查看容器状态
:show_containers
echo 容器状态:
docker ps -a --filter label=com.docker.compose.project="docker"
goto :eof

:: 查看镜像状态
:show_images
echo 镜像状态:
docker images --filter reference="*/qwesdk*" --filter reference="python:3.11" --filter reference="redis:7"
goto :eof

:: 清理Docker资源
:clean_resources
echo 开始清理Docker资源...
echo 1. 停止所有服务
call :stop_services

echo 
echo 2. 移除未使用的网络
docker network prune -f

echo 
echo 3. 移除悬空镜像
docker image prune -f

echo 
echo 4. 移除未使用的卷
docker volume prune -f

echo 
echo 资源清理完成!
goto :eof

:: 进入容器环境
:enter_container
set "SERVICE_NAME=%~1"

:: 检查服务名
if "%SERVICE_NAME%" equ "" (
    echo 错误: 请指定服务名
    echo 可用服务: qwesdk, redis, celery, runner
    exit /b 1
)

:: 检查服务是否存在
set "VALID_SERVICES=qwesdk redis celery runner"
set "SERVICE_FOUND=false"
for %%s in (%VALID_SERVICES%) do (
    if "%SERVICE_NAME%" equ "%%s" (
        set "SERVICE_FOUND=true"
        goto :service_found
    )
)
:service_found
if "%SERVICE_FOUND%" equ "false" (
    echo 错误: 未知服务 '%SERVICE_NAME%'
    echo 可用服务: qwesdk, redis, celery, runner
    exit /b 1
)

echo 准备进入 %SERVICE_NAME% 容器环境...
echo 工作目录: %~dp0
echo 

:: 检查服务是否在运行
docker-compose -f "%~dp0%DOCKER_COMPOSE_FILE" ps -q "%SERVICE_NAME%" >nul 2>&1
if %errorlevel% neq 0 (
    echo 警告: 服务 '%SERVICE_NAME%' 未运行，正在启动...
    :: 启动服务
    docker-compose -f "%~dp0%DOCKER_COMPOSE_FILE" up -d "%SERVICE_NAME%"
    if %errorlevel% neq 0 (
        echo 错误: 无法启动服务 '%SERVICE_NAME%'
        exit /b 1
    )
    :: 等待服务启动
    echo 等待服务启动...
    timeout /t 3 >nul
)

:: 进入容器
echo 进入 %SERVICE_NAME% 容器...
echo 输入 'exit' 退出容器
echo 

docker-compose -f "%~dp0%DOCKER_COMPOSE_FILE" exec "%SERVICE_NAME%" bash
if %errorlevel% neq 0 (
    echo 
    echo 警告: 尝试使用 sh 进入容器...
    docker-compose -f "%~dp0%DOCKER_COMPOSE_FILE" exec "%SERVICE_NAME%" sh
    if %errorlevel% neq 0 (
        echo 
        echo 错误: 无法进入容器
        exit /b 1
    )
)
goto :eof

:: 主函数
if "%~1" equ "" goto :show_help

if "%~1" equ "build" (
    call :build_images
) else if "%~1" equ "up" (
    call :start_services
) else if "%~1" equ "down" (
    call :stop_services
) else if "%~1" equ "restart" (
    call :restart_services
) else if "%~1" equ "status" (
    call :show_status
) else if "%~1" equ "logs" (
    call :show_logs
) else if "%~1" equ "ps" (
    call :show_containers
) else if "%~1" equ "images" (
    call :show_images
) else if "%~1" equ "clean" (
    call :clean_resources
) else if "%~1" equ "exec" (
    call :enter_container "%~2"
) else if "%~1" equ "help" (
    call :show_help
) else (
    echo 错误: 未知选项 '%~1'
    echo 使用 '%~nx0 help' 查看可用选项
    exit /b 1
)
