#!/bin/bash
# Docker 端启动脚本
# 用法: bash deploy.sh <模式> <机器人IP>
# 模式: pure    → 纯 NeuPAN 路径跟踪
#       astar   → A* + NeuPAN 导航

MODE="${1:-pure}"
ROBOT_IP="${2:-10.42.0.169}"

export ROS_MASTER_URI=http://$ROBOT_IP:11311
export ROS_IP=10.42.0.1

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
NEUPAN_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

case "$MODE" in
    pure)
        echo "=== Pure NeuPAN 路径跟踪 ==="
        roslaunch "$NEUPAN_DIR/deploy/pure_neupan/launch/mowen_real.launch"
        ;;
    astar)
        echo "=== A* + NeuPAN 导航 ==="
        roslaunch "$NEUPAN_DIR/deploy/astar_neupan/launch/navigation.launch"
        ;;
    *)
        echo "用法: bash deploy.sh [pure|astar] [IP]"
        ;;
esac
