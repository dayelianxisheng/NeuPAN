#!/bin/bash
# ============================================================
# Fast-LIO + NeuPAN — 小车端启动脚本
# Fast-LIO 提供激光雷达+IMU 里程计定位
# NeuPAN 负责导航避障
#
# 用法:
#   ./start_car_pure.sh          # 启动所有节点
#   ./start_car_pure.sh stop     # 急停
#   ./start_car_pure.sh check    # 健康检查
#   ./start_car_pure.sh cleanup  # 清理
#
# 前提:
#   - FAST_LIO 已编译安装 (git clone + catkin_make)
#   - LiDAR-IMU 外参已标定 (config/fast_lio.yaml)
# ============================================================
set +e

export ROS_HOSTNAME=10.42.0.169
NEUPAN_DIR="$HOME/neupan_ws/src/NeuPAN"
FAST_LIO_DIR="$HOME/fast_lio_ws"

start_roscore() {
    if ! pgrep -x roscore > /dev/null 2>&1; then
        echo "[1] roscore ..."; roscore & sleep 3
    else
        echo "[1] roscore 已在运行"
    fi
}

start_lidar() {
    if rosnode list 2>/dev/null | grep -q lslidar_driver_node; then
        echo "[2] 激光雷达已在运行"
    else
        echo "[2] 激光雷达 ..."
        roslaunch lslidar_driver lslidar_serial.launch &
        sleep 4
    fi
}

start_imu() {
    if rosnode list 2>/dev/null | grep -q wit_imu; then
        echo "[3] IMU 已在运行"
    else
        echo "[3] IMU ..."
        roslaunch wit_ros_imu wit_imu.launch &
        sleep 2
    fi
}

start_newt() {
    if rosnode list 2>/dev/null | grep -q cmd_vel_listener; then
        echo "[4] 串口桥已在运行"
    else
        echo "[4] 串口桥 ..."
        rosrun car_bringup newt.py &
        sleep 3
    fi
}

start_fast_lio() {
    echo "[5] Fast-LIO 定位 ..."
    if [ -d "$FAST_LIO_DIR/devel" ]; then
        source "$FAST_LIO_DIR/devel/setup.bash"
        roslaunch fast_lio mapping_rov.launch \
            config_file:="$NEUPAN_DIR/example/mowen/deploy/fast_lio_neupan/config/fast_lio.yaml" &
        sleep 3
        echo "  ✅ Fast-LIO 已启动"
    else
        echo "  ⚠️ Fast-LIO 未安装: $FAST_LIO_DIR 不存在"
        echo "  请执行: cd ~ && git clone https://github.com/hku-mars/FAST_LIO.git fast_lio_ws"
    fi
}

case "${1:-start}" in
    start)
        echo "=== Fast-LIO + NeuPAN 启动 ==="
        start_roscore
        start_lidar
        start_imu
        start_newt
        start_fast_lio
        echo ""
        echo "Docker 端: bash deploy/scripts/deploy.sh fast_lio"
        echo "RViz: 2D Nav Goal → 导航"
        ;;

    stop)
        echo "=== 急停 ==="
        rosnode kill /neupan_control 2>/dev/null || true
        rostopic pub /cmd_vel geometry_msgs/Twist "{}" -r 50 &
        sleep 3; kill $! 2>/dev/null
        ;;

    check)
        echo "=== 健康检查 ==="
        PASS=0; FAIL=0
        c_node() { local n=$1 p=$2; rosnode list 2>/dev/null | grep -q "$p" && echo "  ✅ $n" && PASS=$((PASS+1)) || { echo "  ❌ $n"; FAIL=$((FAIL+1)); }; }
        c_tf() { local f=$1 t=$2; rosrun tf tf_echo "$f" "$t" 2>/dev/null & sleep 1; kill $! 2>/dev/null && echo "  ✅ TF $f→$t" && PASS=$((PASS+1)) || { echo "  ❌ TF $f→$t"; FAIL=$((FAIL+1)); }; }
        c_node roscore /rosout
        c_node 激光雷达 lslidar_driver_node
        c_node IMU wit_imu
        c_node 串口桥 cmd_vel_listener
        c_node Fast-LIO fast_lio
        echo "--- TF ---"
        c_tf odom base_link
        echo "--- 结果: ✅ $PASS | ❌ $FAIL ---"
        ;;

    cleanup)
        echo "=== 清理 ==="
        rosnode kill -a 2>/dev/null || true; sleep 2
        pkill -f "roslaunch|rosrun|rostopic|static_transform" 2>/dev/null || true
        pkill -f roscore 2>/dev/null || true; sleep 1
        echo "清理完成"
        ;;

    *)
        echo "用法: $0 [start|stop|check|cleanup]"
        ;;
esac
