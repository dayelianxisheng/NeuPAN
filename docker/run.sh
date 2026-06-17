#!/bin/bash
# ============================================================
# NeuPAN Docker 快速启动脚本
# 用法: ./docker/run.sh [ros1|ros2]    (默认 ros2)
# ============================================================

set -e

TARGET="${1:-ros2}"

# ── X11 图形权限 ──────────────────────────────────
xhost +local:docker > /dev/null 2>&1

# ── 检查 GPU ─────────────────────────────────────
GPU_FLAG=""
if docker run --rm --gpus all ubuntu:22.04 nvidia-smi > /dev/null 2>&1; then
    GPU_FLAG="--gpus all"
    echo "[INFO] NVIDIA GPU 已启用"
else
    echo "[WARN] 未检测到 GPU，使用 CPU 模式"
fi

# ── 项目根目录 ──────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

# ── torch wheel 目录（可选） ─────────────────────
TORCH_MOUNT=""
TORCH_DIR="$HOME/resource/env/torch"
if [ -d "$TORCH_DIR" ]; then
    TORCH_MOUNT="-v $TORCH_DIR:/root/torch_pkgs"
    echo "[INFO] 挂载 torch wheel: $TORCH_DIR"
fi

# ── 启动容器 ────────────────────────────────────
case $TARGET in
    ros1)
        IMAGE="neupan:ros1"
        echo "[INFO] 启动 NeuPAN ROS1 容器..."
        docker run -it --rm \
            $GPU_FLAG \
            --net=host \
            -e DISPLAY \
            -v /tmp/.X11-unix:/tmp/.X11-unix \
            -v "$SCRIPT_DIR/neupan_ros:/root/neupan_ws/src/NeuPAN/neupan_ros" \
            $TORCH_MOUNT \
            "$IMAGE" \
            bash -c '
                if [ -d /root/torch_pkgs ] && ! python3 -c "import torch" 2>/dev/null; then
                    WHEEL=$(ls /root/torch_pkgs/torch-*.whl 2>/dev/null | head -1)
                    [ -n "$WHEEL" ] && python3 -m pip install "$WHEEL" -q
                fi
                echo ""
                echo "============================================="
                echo " NeuPAN ROS1 容器就绪"
                echo " 改代码后执行: cd ~/neupan_ws && catkin_make"
                echo "============================================="
                exec bash
            '
        ;;
    ros2)
        IMAGE="neupan:ros2"
        echo "[INFO] 启动 NeuPAN ROS2 容器..."
        docker run -it --rm \
            $GPU_FLAG \
            --net=host \
            -e DISPLAY \
            -v /tmp/.X11-unix:/tmp/.X11-unix \
            -v "$SCRIPT_DIR/neupan_ros2:/root/neupan_ros2_ws/src/NeuPAN/neupan_ros2" \
            $TORCH_MOUNT \
            "$IMAGE" \
            bash -c '
                if [ -d /root/torch_pkgs ] && ! python3 -c "import torch" 2>/dev/null; then
                    WHEEL=$(ls /root/torch_pkgs/torch-*.whl 2>/dev/null | head -1)
                    [ -n "$WHEEL" ] && pip install "$WHEEL" -q
                fi
                if [ ! -f /root/neupan_ros2_ws/src/NeuPAN/neupan_ros2/install/setup.bash ]; then
                    source /opt/ros/humble/setup.bash
                    cd /root/neupan_ros2_ws/src/NeuPAN/neupan_ros2
                    colcon build --symlink-install
                fi
                echo ""
                echo "============================================="
                echo " NeuPAN ROS2 容器就绪"
                echo " 启动: ros2 launch neupan_ros2 sim_complete.launch.py"
                echo "============================================="
                exec bash
            '
        ;;
    *)
        echo "用法: $0 [ros1|ros2]"
        exit 1
        ;;
esac
