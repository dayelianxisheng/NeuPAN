#!/bin/bash
# Docker 端启动脚本
# 用法: bash deploy.sh <模式> <机器人IP>
# 模式: pure    → 纯 NeuPAN 路径跟踪
#       astar   → A* + NeuPAN 导航

MODE="${1:-pure}"

# 从环境变量读取 ROS_MASTER_URI，兼容 docker 内外
if [ -z "${ROS_MASTER_URI:-}" ]; then
    ROBOT_IP="${2:-10.42.0.169}"
    export ROS_MASTER_URI=http://$ROBOT_IP:11311
fi
if [ -z "${ROS_IP:-}" ]; then
    export ROS_IP=10.42.0.1
fi

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
    fast_lio)
        echo "=== Fast-LIO + NeuPAN 导航 ==="
        roslaunch "$NEUPAN_DIR/deploy/fast_lio_neupan/launch/fast_lio_neupan.launch"
        ;;
    *)
        echo "用法: bash deploy.sh [pure|astar|fast_lio] [IP]"
        echo ""
        echo "  pure      纯 NeuPAN 路径跟踪（初始 odom 定位）"
        echo "  astar     A* + AMCL + NeuPAN（需先建图）"
        echo "  fast_lio  Fast-LIO 定位 + NeuPAN（未知环境）"
        ;;
esac
