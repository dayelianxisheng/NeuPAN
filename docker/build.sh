#!/bin/bash
# ============================================================
# NeuPAN Docker 构建脚本
# ============================================================
# 用法:
#   ./docker/build.sh ros1      构建 ROS1 Noetic 镜像
#   ./docker/build.sh ros2      构建 ROS2 Humble 镜像
#   ./docker/build.sh ros1 ros2 构建全部
#
# 代理:
#   ./docker/build.sh ros2 --proxy       使用 clash verge 默认代理
#   ./docker/build.sh ros2 -p http://...  自定义代理地址
# ============================================================

set -e

PROXY=""
TARGETS=()

# 解析参数
while [[ $# -gt 0 ]]; do
    case $1 in
        ros1|ros2) TARGETS+=("$1"); shift ;;
        --proxy|-p)
            if [[ "$2" == http* ]]; then
                PROXY="$2"; shift 2
            else
                PROXY="http://127.0.0.1:7897"; shift
            fi ;;
        *) echo "未知参数: $1"; exit 1 ;;
    esac
done

[[ ${#TARGETS[@]} -eq 0 ]] && echo "用法: $0 ros1|ros2 [--proxy]" && exit 1

for TARGET in "${TARGETS[@]}"; do
    echo "============================================="
    echo " 构建 neupan:${TARGET}"
    echo "============================================="

    # 基础构建参数
    BUILD_ARGS="-t neupan:${TARGET} -f docker/${TARGET}/Dockerfile ."

    if [[ -n "$PROXY" ]]; then
        # 清除 Docker daemon 注入的 127.0.0.1 代理（容器内不可达）
        # 通过 PIP_PROXY 传递给 pip（仅 torch 下载使用）
        BUILD_ARGS="--build-arg HTTP_PROXY= --build-arg HTTPS_PROXY= --build-arg http_proxy= --build-arg https_proxy= --build-arg PIP_PROXY=${PROXY} ${BUILD_ARGS}"
        echo " 代理: ${PROXY} (仅用于 pip torch)"
    else
        # 无代理时也清除 daemon 注入的代理
        BUILD_ARGS="--build-arg HTTP_PROXY= --build-arg HTTPS_PROXY= --build-arg http_proxy= --build-arg https_proxy= ${BUILD_ARGS}"
    fi

    docker build ${BUILD_ARGS}
    echo ""
done

echo "============================================="
echo " 构建完成"
echo "============================================="
echo ""
echo "运行容器:"
echo "  ROS1: xhost +local:docker && docker run -it --gpus all --net=host -e DISPLAY -v /tmp/.X11-unix:/tmp/.X11-unix neupan:ros1"
echo "  ROS2: xhost +local:docker && docker run -it --gpus all --net=host -e DISPLAY -v /tmp/.X11-unix:/tmp/.X11-unix neupan:ros2"
