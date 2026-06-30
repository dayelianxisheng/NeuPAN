#!/bin/bash
# ============================================================
# A* + NeuPAN 导航 — 小车端一键启动（硬件+地图+AMCL）
# 用法:
#   ./start_car_astar.sh          # 启动（默认）
#   ./start_car_astar.sh stop     # 急停
#   ./start_car_astar.sh check    # 检查
#   ./start_car_astar.sh cleanup  # 清理
# ============================================================
set +e

export ROS_HOSTNAME=10.42.0.169

NEUPAN_DIR="$HOME/neupan_ws/src/NeuPAN"
SCRIPTS_DIR="$NEUPAN_DIR/scripts"
MAP_PATH="$NEUPAN_DIR/deploy/maps/mymap.yaml"

source "$SCRIPTS_DIR/start_car_common.sh"

start_urdf() {
    echo "[6] 机器人模型 (URDF) ..."
    if roslaunch mowen display.launch 2>/dev/null; then
        echo "  ✅ URDF"
    else
        echo "  ⚠️ 无 URDF（跳过）"
    fi &
    sleep 2
}

start_ekf() {
    echo "[7] EKF 数据融合 ..."
    if [ -f "$HOME/newznzc_ws/src/car_bringup/param/robot_localization.yaml" ]; then
        rosparam load "$HOME/newznzc_ws/src/car_bringup/param/robot_localization.yaml" 2>/dev/null
    fi
    rosrun robot_localization ekf_localization_node \
        _odom_frame:=odom _world_frame:=odom _base_link_frame:=base_footprint \
        _two_d_mode:=true _frequency:=20 \
        _odom0:=/odom_raw _imu0:=/wit/imu \
        odometry/filtered:=odom &
    sleep 2
}

start_map() {
    echo "[8] 地图服务 ..."
    if [ -f "$MAP_PATH" ]; then
        rosrun map_server map_server "$MAP_PATH" &
        sleep 2
    else
        echo "  ⚠️ 地图不存在: $MAP_PATH"
    fi
}

start_amcl() {
    echo "[9] AMCL 定位 ..."
    rosrun amcl amcl scan:=/scan \
        odom_frame_id:=odom base_frame_id:=base_link global_frame_id:=map \
        _odom_model_type:=omni _min_particles:=500 _max_particles:=2000 &
    sleep 2
}

nav_check() {
    echo "--- 导航组件检查 ---"
    for topic in /map /amcl_pose /scan; do
        if rostopic info "$topic" 2>/dev/null | grep -q "Publishers"; then
            echo "  ✅ $topic"
        else
            echo "  ❌ $topic"
        fi
    done
    if rosrun tf tf_echo map base_link 2>/dev/null & sleep 1; kill $! 2>/dev/null; then
        echo "  ✅ TF map→base_link (定位正常)"
    else
        echo "  ❌ TF map→base_link (AMCL 未定位)"
    fi
}

case "${1:-start}" in
    start)
        echo "=== A* + NeuPAN 导航启动 ==="
        start_roscore
        start_lidar
        start_newt
        start_odometry
        start_tf
        start_urdf
        start_ekf
        start_map
        start_amcl
        echo ""
        echo "小车端就绪 ✅ 切换到 Docker 执行:"
        echo "  bash deploy/scripts/deploy.sh astar"
        ;;

    stop)     stop ;;
    resume)   resume ;;
    reset_odom) reset_odom ;;
    status)   status ;;
    check)
        echo "=== A* + NeuPAN 健康检查 ==="
        check
        nav_check
        ;;
    cleanup)  cleanup ;;
    *)
        echo "用法: $0 [start|stop|resume|reset_odom|status|check|cleanup]"
        ;;
esac
