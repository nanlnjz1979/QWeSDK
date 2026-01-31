#!/bin/bash
# Docker管理脚本
# 功能：构建、启动、停止、查看状态、查看日志等

# 脚本版本
VERSION="1.0.1"

# 颜色定义
GREEN="\033[0;32m"
YELLOW="\033[1;33m"
RED="\033[0;31m"
BLUE="\033[0;34m"
NC="\033[0m" # No Color

# 脚本目录
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
DOCKER_COMPOSE_FILE="docker-compose.yml"

# 检查必要的命令
check_commands() {
    local commands=(docker docker-compose)
    for cmd in "${commands[@]}"; do
        if ! command -v "$cmd" &> /dev/null; then
            echo -e "${RED}错误: $cmd 命令未找到${NC}"
            exit 1
        fi
    done
}

# 显示帮助信息
show_help() {
    echo -e "${BLUE}Docker管理脚本 v$VERSION${NC}"
    echo -e "======================"
    echo -e "功能：管理QWeSDK的Docker环境"
    echo -e ""
    echo -e "${GREEN}用法:${NC} $0 [选项] [服务名]"
    echo -e ""
    echo -e "${GREEN}选项:${NC}"
    echo -e "  ${YELLOW}build${NC}     - 构建Docker镜像"
    echo -e "  ${YELLOW}up${NC}        - 启动所有服务"
    echo -e "  ${YELLOW}down${NC}      - 停止并移除所有服务"
    echo -e "  ${YELLOW}restart${NC}   - 重启所有服务"
    echo -e "  ${YELLOW}status${NC}    - 查看服务状态"
    echo -e "  ${YELLOW}logs${NC}      - 查看服务日志"
    echo -e "  ${YELLOW}ps${NC}        - 查看容器状态"
    echo -e "  ${YELLOW}images${NC}    - 查看镜像状态"
    echo -e "  ${YELLOW}clean${NC}     - 清理Docker资源"
    echo -e "  ${YELLOW}exec${NC}      - 进入指定服务的容器环境"
    echo -e "  ${YELLOW}help${NC}      - 显示此帮助信息"
    echo -e ""
    echo -e "${GREEN}服务名:${NC}"
    echo -e "  qwesdk    - QWeSDK服务"
    echo -e "  redis     - Redis服务"
    echo -e "  celery    - Celery服务"
    echo -e "  runner    - Runner服务"
    echo -e ""
    echo -e "${GREEN}示例:${NC}"
    echo -e "  $0 build    # 构建镜像"
    echo -e "  $0 up       # 启动服务"
    echo -e "  $0 status   # 查看状态"
    echo -e "  $0 exec qwesdk  # 进入qwesdk容器"
    echo -e "  $0 exec redis   # 进入redis容器"
    echo -e "  $0 down     # 停止服务"
}

# 构建Docker镜像
build_images() {
    echo -e "${BLUE}开始构建Docker镜像...${NC}"
    echo -e "工作目录: $SCRIPT_DIR"
    echo -e "使用配置文件: $DOCKER_COMPOSE_FILE"
    echo -e ""
    
    # 检查docker-compose.yml文件是否存在
    if [ ! -f "$SCRIPT_DIR/$DOCKER_COMPOSE_FILE" ]; then
        echo -e "${RED}错误: $DOCKER_COMPOSE_FILE 文件不存在${NC}"
        exit 1
    fi
    
    # 构建镜像
    cd "$SCRIPT_DIR" && docker-compose -f "$DOCKER_COMPOSE_FILE" build
    
    if [ $? -eq 0 ]; then
        echo -e ""
        echo -e "${GREEN}✓ 构建成功!${NC}"
    else
        echo -e ""
        echo -e "${RED}✗ 构建失败!${NC}"
        exit 1
    fi
}

# 启动服务
start_services() {
    echo -e "${BLUE}开始启动Docker服务...${NC}"
    echo -e "工作目录: $SCRIPT_DIR"
    echo -e ""
    
    cd "$SCRIPT_DIR" && docker-compose -f "$DOCKER_COMPOSE_FILE" up -d
    
    if [ $? -eq 0 ]; then
        echo -e ""
        echo -e "${GREEN}✓ 服务启动成功!${NC}"
        echo -e ""
        echo -e "${BLUE}服务状态:${NC}"
        cd "$SCRIPT_DIR" && docker-compose -f "$DOCKER_COMPOSE_FILE" ps
    else
        echo -e ""
        echo -e "${RED}✗ 服务启动失败!${NC}"
        exit 1
    fi
}

# 停止服务
stop_services() {
    echo -e "${BLUE}开始停止Docker服务...${NC}"
    echo -e "工作目录: $SCRIPT_DIR"
    echo -e ""
    
    cd "$SCRIPT_DIR" && docker-compose -f "$DOCKER_COMPOSE_FILE" down
    
    if [ $? -eq 0 ]; then
        echo -e ""
        echo -e "${GREEN}✓ 服务停止成功!${NC}"
    else
        echo -e ""
        echo -e "${RED}✗ 服务停止失败!${NC}"
        exit 1
    fi
}

# 重启服务
restart_services() {
    echo -e "${BLUE}开始重启Docker服务...${NC}"
    stop_services
    echo -e ""
    start_services
}

# 查看服务状态
show_status() {
    echo -e "${BLUE}服务状态:${NC}"
    echo -e "工作目录: $SCRIPT_DIR"
    echo -e ""
    
    cd "$SCRIPT_DIR" && docker-compose -f "$DOCKER_COMPOSE_FILE" ps
    
    if [ $? -ne 0 ]; then
        echo -e ""
        echo -e "${YELLOW}警告: 无法获取服务状态${NC}"
    fi
}

# 查看服务日志
show_logs() {
    echo -e "${BLUE}服务日志:${NC}"
    echo -e "工作目录: $SCRIPT_DIR"
    echo -e "按 Ctrl+C 退出日志查看"
    echo -e ""
    
    cd "$SCRIPT_DIR" && docker-compose -f "$DOCKER_COMPOSE_FILE" logs -f
}

# 查看容器状态
show_containers() {
    echo -e "${BLUE}容器状态:${NC}"
    docker ps -a --filter label=com.docker.compose.project="docker"
}

# 查看镜像状态
show_images() {
    echo -e "${BLUE}镜像状态:${NC}"
    docker images --filter reference="*/qwesdk*" --filter reference="python:3.11" --filter reference="redis:7"
}

# 清理Docker资源
clean_resources() {
    echo -e "${BLUE}开始清理Docker资源...${NC}"
    echo -e "1. 停止所有服务"
    stop_services
    
    echo -e ""
    echo -e "2. 移除未使用的网络"
    docker network prune -f
    
    echo -e ""
    echo -e "3. 移除悬空镜像"
    docker image prune -f
    
    echo -e ""
    echo -e "4. 移除未使用的卷"
    docker volume prune -f
    
    echo -e ""
    echo -e "${GREEN}✓ 资源清理完成!${NC}"
}

# 进入容器环境
enter_container() {
    local service_name="$1"
    
    # 检查服务名
    if [ -z "$service_name" ]; then
        echo -e "${RED}错误: 请指定服务名${NC}"
        echo -e "可用服务: qwesdk, redis, celery, runner"
        exit 1
    fi
    
    # 检查服务是否存在
    local valid_services=(qwesdk redis celery runner)
    local service_found=false
    for valid_service in "${valid_services[@]}"; do
        if [ "$service_name" = "$valid_service" ]; then
            service_found=true
            break
        fi
    done
    
    if [ "$service_found" = false ]; then
        echo -e "${RED}错误: 未知服务 '$service_name'${NC}"
        echo -e "可用服务: qwesdk, redis, celery, runner"
        exit 1
    fi
    
    echo -e "${BLUE}准备进入 $service_name 容器环境...${NC}"
    echo -e "工作目录: $SCRIPT_DIR"
    echo -e ""
    
    # 检查服务是否在运行
    local container_status=$(cd "$SCRIPT_DIR" && docker-compose -f "$DOCKER_COMPOSE_FILE" ps -q "$service_name")
    if [ -z "$container_status" ]; then
        echo -e "${YELLOW}警告: 服务 '$service_name' 未运行，正在启动...${NC}"
        # 启动服务
        cd "$SCRIPT_DIR" && docker-compose -f "$DOCKER_COMPOSE_FILE" up -d "$service_name"
        
        if [ $? -ne 0 ]; then
            echo -e "${RED}错误: 无法启动服务 '$service_name'${NC}"
            exit 1
        fi
        
        # 等待服务启动
        echo -e "等待服务启动..."
        sleep 3
    fi
    
    # 进入容器
    echo -e "进入 $service_name 容器..."
    echo -e "输入 'exit' 退出容器"
    echo -e ""
    
    cd "$SCRIPT_DIR" && docker-compose -f "$DOCKER_COMPOSE_FILE" exec "$service_name" bash
    
    if [ $? -ne 0 ]; then
        echo -e ""
        echo -e "${YELLOW}警告: 尝试使用 sh 进入容器...${NC}"
        cd "$SCRIPT_DIR" && docker-compose -f "$DOCKER_COMPOSE_FILE" exec "$service_name" sh
        
        if [ $? -ne 0 ]; then
            echo -e ""
            echo -e "${RED}错误: 无法进入容器${NC}"
            exit 1
        fi
    fi
}

# 主函数
main() {
    check_commands
    
    if [ $# -eq 0 ]; then
        show_help
        exit 0
    fi
    
    case "$1" in
        build)
            build_images
            ;;
        up)
            start_services
            ;;
        down)
            stop_services
            ;;
        restart)
            restart_services
            ;;
        status)
            show_status
            ;;
        logs)
            show_logs
            ;;
        ps)
            show_containers
            ;;
        images)
            show_images
            ;;
        clean)
            clean_resources
            ;;
        exec)
            enter_container "$2"
            ;;
        help)
            show_help
            ;;
        *)
            echo -e "${RED}错误: 未知选项 '$1'${NC}"
            echo -e "使用 '$0 help' 查看可用选项"
            exit 1
            ;;
    esac
}

# 执行主函数
main "$@"
