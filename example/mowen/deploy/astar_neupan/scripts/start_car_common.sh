# ============================================================
# 小车端通用函数库 — 由 start_car_pure.sh / start_car_astar.sh 引用
# ============================================================

start_roscore() {
    if ! pgrep -x roscore > /dev/null 2>&1; then echo "[1] roscore ..."; roscore & sleep 3; else echo "[1] roscore 已在"; fi
}
start_lidar() {
    if rosnode list 2>/dev/null | grep -q lslidar_driver_node; then echo "[2] 雷达已在"; else echo "[2] 雷达 ..."; roslaunch lslidar_driver lslidar_serial.launch & sleep 4; fi
}
start_newt() {
    if rosnode list 2>/dev/null | grep -q cmd_vel_listener; then echo "[3] newt.py 已在"; else echo "[3] newt.py ..."; rosrun car_bringup newt.py & sleep 3; fi
}
start_odometry() {
    rosnode kill /odometry_publisher /vel_raw_pub 2>/dev/null || true; sleep 1
    echo "[4] 里程计 ..."
    rosrun car_bringup pubv.py & sleep 2
    rosrun car_bringup base_node _odom_frame:=odom _base_footprint_frame:=base_footprint /sub_vel:=/vel_raw /pub_odom:=/odom_raw & sleep 2
}
start_tf() {
    echo "[5] TF ..."
    rosnode kill /odom_tf_broadcaster 2>/dev/null || true; sleep 1
    python "$SCRIPTS_DIR/odom_tf_broadcaster.py" & sleep 1
    rosrun tf static_transform_publisher 0 0 0 0 0 0 base_footprint base_link 100 & sleep 1
}
stop() {
    echo "=== 急停 ==="
    rosnode kill /neupan_control 2>/dev/null || true; pkill -f "rostopic pub" 2>/dev/null || true
    rostopic pub /cmd_vel geometry_msgs/Twist "{}" -r 50 & sleep 3; kill $! 2>/dev/null
    rostopic pub -1 /cmd_vel geometry_msgs/Twist "{}" 2>/dev/null || true
}
resume() { if ! rosnode list 2>/dev/null | grep -q cmd_vel_listener; then rosrun car_bringup newt.py & sleep 3; fi; echo "已恢复"; }
reset_odom() {
    rosnode kill /odometry_publisher /odom_tf_broadcaster 2>/dev/null || true; sleep 1
    rosrun car_bringup base_node _odom_frame:=odom _base_footprint_frame:=base_footprint /sub_vel:=/vel_raw /pub_odom:=/odom_raw & sleep 2
    python "$SCRIPTS_DIR/odom_tf_broadcaster.py" & sleep 1; echo "odom 已归零"
}
status() { echo "=== 节点 ==="; rosnode list 2>/dev/null | sort || echo "(无)"; echo "=== TF ==="; rosrun tf view_frames 2>/dev/null || echo "(TF 不可用)"; }
check() {
    PASS=0; FAIL=0
    c_node() { local n=$1 p=$2; rosnode list 2>/dev/null | grep -q "$p" && echo "  ✅ $n" && PASS=$((PASS+1)) || { echo "  ❌ $n"; FAIL=$((FAIL+1)); }; }
    c_tf() { local f=$1 t=$2 n=$3; rosrun tf tf_echo "$f" "$t" 2>/dev/null & sleep 1; kill $! 2>/dev/null && echo "  ✅ $n" && PASS=$((PASS+1)) || { echo "  ❌ $n"; FAIL=$((FAIL+1)); }; }
    echo "--- 节点 ---"
    c_node roscore /rosout; c_node 雷达 lslidar_driver_node; c_node 串口桥 cmd_vel_listener
    c_node 轮速 vel_raw_pub; c_node 里程计 odometry_publisher; c_node TF odom_tf_broadcaster
    echo "--- TF ---"
    c_tf odom base_footprint "TF odom→base_footprint"
    c_tf base_footprint base_link "TF base_footprint→base_link"
    c_tf base_link laser_link "TF base_link→laser_link"
    echo "--- 结果: ✅ $PASS | ❌ $FAIL ---"
}
cleanup() {
    echo "=== 清理 ==="; rosnode kill -a 2>/dev/null || true; sleep 2
    pkill -f "roslaunch|rosrun|rostopic|static_transform" 2>/dev/null || true
    pkill -f roscore 2>/dev/null || true; sleep 1; echo "清理完成"
}
