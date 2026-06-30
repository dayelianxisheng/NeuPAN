#!/bin/bash
# ============================================================
# Fast-LIO + NeuPAN — 小车端一键启动
# Fast-LIO 提供激光雷达里程计定位，NeuPAN 负责导航避障
#
# 用法:
#   ./start_car.sh          # 启动所有节点
#   ./start_car.sh stop     # 急停
#   ./start_car.sh check    # 健康检查
#   ./start_car.sh cleanup  # 清理
# ============================================================
set -e

export ROS_HOSTNAME=10.42.0.169
NEUPAN_DIR="$HOME/neupan_ws/src/NeuPAN"

# TODO: Fast-LIO 的工作空间路径
FAST_LIO_DIR="$HOME/fast_lio_ws"

start_roscore() {
    if ! pgrep -x roscore > /dev/null 2>&1; then
        echo "[1] 启动 roscore ..."
        roscore &
        sleep 3
    else
        echo "[1] roscore 已在运行"
    fi
}

start_lidar() {
    echo "[2] 启动激光雷达 ..."
    roslaunch lslidar_driver lslidar_serial.launch &
    sleep 4
}

start_newt() {
    echo "[3] 启动串口桥 newt.py ..."
    rosrun car_bringup newt.py &
    sleep 3
}

start_fast_lio() {
    echo "[4] TODO: 启动 Fast-LIO 定位 ..."
    echo "      期望输入: /lslidar_point_cloud (LiDAR)"
    echo "      期望输出: /odom (里程计位姿)"
    echo "      参考命令: roslaunch fast_lio mapping.launch"
    # roslaunch fast_lio mapping.launch &
    # sleep 3
}

start_tf() {
    echo "[5] 启动 TF 广播 ..."
    rosrun tf static_transform_publisher 0 0 0 0 0 0 \
        base_footprint base_link 100 &
    sleep 1
}

case "${1:-start}" in
    start)
        echo "=== Fast-LIO + NeuPAN 启动 ==="
        start_roscore
        start_lidar
        start_newt
        start_fast_lio
        start_tf
        echo ""
        echo "小车端就绪 ✅"
        echo "切换到 Docker 执行: bash deploy/scripts/deploy.sh fast_lio"
        ;;
    stop)
        rostopic pub /cmd_vel geometry_msgs/Twist "{}" -r 50 &
        sleep 3
        kill $! 2>/dev/null
        ;;
    check)
        echo "=== 健康检查 ==="
        for n in lslidar_driver_node cmd_vel_listener; do
            rosnode list 2>/dev/null | grep -q "$n" \
                && echo "  ✅ $n" || echo "  ❌ $n"
        done
        echo "--- TF ---"
        rosrun tf tf_echo odom base_link 2>/dev/null & sleep 1; kill $! 2>/dev/null || true
        ;;
    cleanup)
        echo "=== 清理 ==="
        rosnode kill -a 2>/dev/null || true
        sleep 2
        pkill -f "roslaunch|rosrun|rostopic" 2>/dev/null || true
        pkill -f "roscore" 2>/dev/null || true
        sudo fuser -k /dev/carserial 2>/dev/null || true
        echo "清理完成"
        ;;
    *)
        echo "用法: $0 [start|stop|check|cleanup]"
        ;;
esac
