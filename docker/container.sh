#!/bin/bash
# ============================================================
# NeuPAN Docker 统一容器管理
# 用法:
#   ./docker/container.sh ros1 setup    创建 + 下载依赖
#   ./docker/container.sh ros1 start    启动并进入
#   ./docker/container.sh ros1 enter    进入运行中的容器
#   ./docker/container.sh ros1 stop     停止容器
#   ./docker/container.sh ros1 status   查看状态
# ============================================================
set -e

TARGET="$1"
CMD="${2:-enter}"

if [ "$TARGET" != "ros1" ] && [ "$TARGET" != "ros2" ]; then
    echo "用法: $0 [ros1|ros2] [setup|start|enter|stop|status]"
    exit 1
fi

xhost +local:docker > /dev/null 2>&1 || true
SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

# GPU
GPU_FLAG=""
docker run --rm --gpus all ubuntu:22.04 nvidia-smi > /dev/null 2>&1 && GPU_FLAG="--gpus all"

# 配置
if [ "$TARGET" = "ros1" ]; then
    NAME="ros1_dev"
    IMAGE="ros:noetic-ros-core"
    SETUP_SCRIPT="/root/neupan_ws/src/NeuPAN/docker/ros1/setup.sh"
    WS_MOUNT="-v $SCRIPT_DIR:/root/neupan_ws/src/NeuPAN"
    INIT_CMD="export http_proxy=http://127.0.0.1:7897 https_proxy=http://127.0.0.1:7897 __GLX_VENDOR_LIBRARY_NAME=nvidia; source /opt/ros/noetic/setup.bash; [ -f /root/neupan_ws/devel/setup.bash ] && source /root/neupan_ws/devel/setup.bash; cd /root/neupan_ws"
else
    NAME="ros2_dev"
    IMAGE="ros:humble-ros-core"
    SETUP_SCRIPT="/root/neupan_ros2_ws/src/NeuPAN/docker/ros2/setup.sh"
    WS_MOUNT="-v $SCRIPT_DIR:/root/neupan_ros2_ws/src/NeuPAN"
    INIT_CMD="export http_proxy=http://127.0.0.1:7897 https_proxy=http://127.0.0.1:7897 __GLX_VENDOR_LIBRARY_NAME=nvidia; source /opt/ros/humble/setup.bash; [ -f /root/neupan_ros2_ws/src/NeuPAN/neupan_ros2/install/setup.bash ] && source /root/neupan_ros2_ws/src/NeuPAN/neupan_ros2/install/setup.bash; cd /root/neupan_ros2_ws/src/NeuPAN/neupan_ros2"
fi

# 代理设置
PROXY_VARS="export http_proxy=http://127.0.0.1:7897 https_proxy=http://127.0.0.1:7897;"

case "$CMD" in
    setup)
        echo "=== 创建 $TARGET 容器 + 安装依赖 ==="
        docker rm -f "$NAME" 2>/dev/null || true
        docker run -d --name "$NAME" $GPU_FLAG --net=host -e DISPLAY \
            -v /tmp/.X11-unix:/tmp/.X11-unix $WS_MOUNT \
            "$IMAGE" sleep infinity
        echo "[1/2] 容器已创建，开始安装依赖..."
        docker exec "$NAME" bash -c "$PROXY_VARS bash $SETUP_SCRIPT"
        echo "[2/2] 安装完成"
        docker exec -it "$NAME" bash -c "$INIT_CMD; exec bash"
        ;;
    start)
        if docker ps --format '{{.Names}}' | grep -q "^${NAME}$"; then
            echo "容器已在运行"
        elif docker ps -a --format '{{.Names}}' | grep -q "^${NAME}$"; then
            echo "启动已有容器..."
            docker start "$NAME"
        else
            echo "容器不存在，请先: $0 $TARGET setup"; exit 1
        fi
        docker exec -it "$NAME" bash -c "$INIT_CMD; exec bash"
        ;;
    enter)
        docker exec -it "$NAME" bash -c "$INIT_CMD; exec bash"
        ;;
    stop)
        docker stop "$NAME" 2>/dev/null && echo "已停止 $NAME" || echo "$NAME 未运行"
        ;;
    status)
        docker ps -a --filter "name=$NAME" --format "{{.Names}}  {{.Status}}"
        docker exec "$NAME" bash -c 'echo "  GPU: $(nvidia-smi 2>/dev/null | grep GeForce || echo cpu)"' 2>/dev/null || true
        ;;
    *)
        echo "用法: $0 [ros1|ros2] [setup|start|enter|stop|status]"
        exit 1
        ;;
esac
