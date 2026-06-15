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

    BUILD_ARGS="-t neupan:${TARGET} -f docker/${TARGET}/Dockerfile ."
    if [[ -n "$PROXY" ]]; then
        BUILD_ARGS="--build-arg HTTP_PROXY=${PROXY} --build-arg HTTPS_PROXY=${PROXY} ${BUILD_ARGS}"
        echo " 代理: ${PROXY}"
    fi

    docker build ${BUILD_ARGS}
    echo ""
done

echo "============================================="
echo " 构建完成"
echo "============================================="
echo ""
echo "运行容器:"
echo "  ROS1: xhost +local:docker && docker run -it --gpus all --net=host -e DISPLAY -v /tmp/.X11-unix:/tmp/.X11-unix neupan:noetic"
echo "  ROS2: xhost +local:docker && docker run -it --gpus all --net=host -e DISPLAY -v /tmp/.X11-unix:/tmp/.X11-unix neupan:ros2"
