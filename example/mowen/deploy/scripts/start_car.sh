#!/bin/bash
# ============================================================
# NeuPAN Phase 1 — 小车端一键启动脚本
# 用法:
#   ./start_car.sh              # 启动所有节点
#   ./start_car.sh stop         # 小车急停（发零速度）
#   ./start_car.sh resume       # 恢复（重启串口桥）
#   ./start_car.sh reset_odom   # 里程计归零（重启 base_node + TF）
#   ./start_car.sh status       # 查看当前节点和话题状态
#   ./start_car.sh cleanup      # 杀掉所有节点释放串口
# ============================================================
set -e

export ROS_HOSTNAME=10.42.0.169

NEUPAN_DIR="$HOME/neupan_ws/src/NeuPAN"
SCRIPTS_DIR="$NEUPAN_DIR/docs/scripts"

# ============================================================

start_roscore() {
    if ! pgrep -x roscore > /dev/null 2>&1; then
        echo "[1/7] 启动 roscore ..."
        roscore &
        sleep 3
    else
        echo "[1/7] roscore 已在运行"
    fi
}

start_lidar() {
    if rosnode list 2>/dev/null | grep -q lslidar_driver_node; then
        echo "[2/7] 激光雷达已在运行"
    else
        echo "[2/7] 启动激光雷达 ..."
        roslaunch lslidar_driver lslidar_serial.launch &
        sleep 4
    fi
}

start_newt() {
    if rosnode list 2>/dev/null | grep -q cmd_vel_listener; then
        echo "[3/7] newt.py 已在运行"
    else
        echo "[3/7] 启动 newt.py (占串口) ..."
        rosrun car_bringup newt.py &
        sleep 3
    fi
}

start_odometry() {
    echo "[4/7] 启动 pubv.py + base_node ..."
    # 杀掉旧的以防 remap 冲突
    rosnode kill /odometry_publisher 2>/dev/null || true
    rosnode kill /vel_raw_pub 2>/dev/null || true
    sleep 1

    rosrun car_bringup pubv.py &
    sleep 2

    # base_node 带 remap：读 /vel_raw，写 /odom_raw
    rosrun car_bringup base_node \
        _odom_frame:=odom \
        _base_footprint_frame:=base_footprint \
        /sub_vel:=/vel_raw \
        /pub_odom:=/odom_raw &
    sleep 2
}

start_tf() {
    echo "[5/7] 启动 TF 广播 ..."

    # odom → base_footprint
    rosnode kill /odom_tf_broadcaster 2>/dev/null || true
    sleep 1
    python "$SCRIPTS_DIR/odom_tf_broadcaster.py" &
    sleep 1

    # base_footprint → base_link (恒等)
    rosrun tf static_transform_publisher 0 0 0 0 0 0 base_footprint base_link 100 &
    sleep 1

    # base_link → laser_link — 由 lslidar launcher 自带的 base_link_to_laser4 发布
    # 不要自己加 static TF，不要杀 base_link_to_laser4
}

verify() {
    echo ""
    echo "========== 验证 =========="
    echo "--- 节点 ---"
    rosnode list 2>/dev/null | sort
    echo ""
    echo "--- 话题 ---"
    rostopic list 2>/dev/null | sort
    echo ""
    echo "--- TF 链 odom → laser_link ---"
    rosrun tf tf_echo odom laser_link 2>/dev/null & sleep 2; kill $! 2>/dev/null || true
    echo ""
    echo "========== 完成 =========="
    echo "ROS_HOSTNAME=10.42.0.169"
    echo "ROS_MASTER_URI=http://10.42.0.169:11311"
    echo "小车端已就绪，等待 Docker 端连接。"
}

# ============================================================
# 命令处理
# ============================================================

case "${1:-start}" in
    start)
        echo "=== NeuPAN Phase 1 — 小车端一键启动 ==="
        start_roscore
        start_lidar
        start_newt
        start_odometry
        start_tf
        verify
        ;;

    stop)
        echo "=== 急停 ==="
        # 1. 杀 Docker 端 neupan_node
        rosnode kill /neupan_control 2>/dev/null || true
        # 2. 杀本地所有 rostopic 进程
        pkill -f "rostopic pub" 2>/dev/null || true
        # 3. 持续发零速 5 秒
        rostopic pub /cmd_vel geometry_msgs/Twist "{}" -r 50 &
        STOP_PID=$!
        sleep 5
        kill $STOP_PID 2>/dev/null
        rostopic pub -1 /cmd_vel geometry_msgs/Twist "{}" 2>/dev/null || true
        echo "小车停止。"
        echo "恢复请执行: $0 resume"
        ;;

    resume)
        echo "=== 恢复控制 ==="
        # 检查 newt.py 是否活着
        if ! rosnode list 2>/dev/null | grep -q cmd_vel_listener; then
            echo "newt.py 未运行，重新启动..."
            rosrun car_bringup newt.py &
            sleep 3
        fi
        echo "已恢复。请确保 Docker 端开始发 /cmd_vel。"
        ;;

    reset_odom)
        echo "=== 里程计归零 ==="
        echo "重启 base_node ..."
        rosnode kill /odometry_publisher 2>/dev/null || true
        sleep 1
        rosrun car_bringup base_node \
            _odom_frame:=odom \
            _base_footprint_frame:=base_footprint \
            /sub_vel:=/vel_raw \
            /pub_odom:=/odom_raw &
        sleep 2
        echo "重启 odom_tf_broadcaster ..."
        rosnode kill /odom_tf_broadcaster 2>/dev/null || true
        sleep 1
        python "$SCRIPTS_DIR/odom_tf_broadcaster.py" &
        sleep 1
        echo "odom 已归零。"
        rosrun tf tf_echo odom base_footprint 2>/dev/null & sleep 2; kill $! 2>/dev/null || true
        ;;

    status)
        echo "=== 节点 ==="
        rosnode list 2>/dev/null | sort || echo "(roscore 未运行)"
        echo ""
        echo "=== 话题 ==="
        rostopic list 2>/dev/null | sort || true
        echo ""
        echo "=== TF 树 ==="
        rosrun tf view_frames 2>/dev/null || echo "(TF 不可用)"
        ;;

    check|verify)
        echo "========== 节点健康检查 =========="
        FAIL=0
        PASS=0
        check_node() {
            local name="$1"
            local pattern="$2"
            if rosnode list 2>/dev/null | grep -q "$pattern"; then
                echo "  ✅ $name"
                PASS=$((PASS + 1))
            else
                echo "  ❌ $name — 未运行"
                FAIL=$((FAIL + 1))
            fi
        }
        check_topic_hz() {
            local topic="$1"
            local name="$2"
            local min_hz="$3"
            local hz
            hz=$(rostopic hz "$topic" 2>/dev/null | head -3 | awk '{print $3}' | head -1)
            if [ -n "$hz" ] && [ "$(echo "$hz > $min_hz" | bc 2>/dev/null)" = "1" ]; then
                echo "  ✅ $name — ${hz}Hz"
                PASS=$((PASS + 1))
            else
                echo "  ❌ $name — 频率不足或数据为空"
                FAIL=$((FAIL + 1))
            fi
        }
        check_tf() {
            local from="$1"
            local to="$2"
            if rosrun tf tf_echo "$from" "$to" 2>/dev/null & sleep 1; kill $! 2>/dev/null; then
                echo "  ✅ TF $from → $to"
                PASS=$((PASS + 1))
            else
                echo "  ❌ TF $from → $to — 不存在"
                FAIL=$((FAIL + 1))
            fi
        }
        echo ""
        echo "--- 节点状态 ---"
        check_node "roscore"         "/rosout"
        check_node "激光雷达"         "lslidar_driver_node"
        check_node "串口桥 newt.py"   "cmd_vel_listener"
        check_node "轮速 pubv.py"     "vel_raw_pub"
        check_node "里程计 base_node" "odometry_publisher"
        check_node "TF 广播"          "odom_tf_broadcaster"
        echo ""
        echo "--- TF 拓扑 ---"
        check_tf "odom" "base_footprint"
        check_tf "base_footprint" "base_link"
        check_tf "base_link" "laser_link"
        echo ""
        echo "--- 结果 ---"
        echo "  ✅ 通过: $PASS"
        echo "  ❌ 失败: $FAIL"
        [ "$FAIL" -eq 0 ] && echo "  所有节点正常 ✅" || echo "  有 $FAIL 个节点异常，请检查 ❌"
        ;;

    cleanup)
        echo "=== 清理 ==="
        echo "杀掉所有 ROS 节点..."
        rosnode kill -a 2>/dev/null || true
        sleep 2
        pkill -f "roslaunch|rosrun|rostopic" 2>/dev/null || true
        pkill -f "static_transform_publisher" 2>/dev/null || true
        pkill -f "roscore" 2>/dev/null || true
        sleep 2
        echo "释放串口..."
        sudo fuser -k /dev/carserial 2>/dev/null || true
        echo "清理完成。"
        ;;

    *)
        echo "用法: $0 [start|stop|resume|reset_odom|status|cleanup]"
        echo ""
        echo "  start        一键启动所有节点 (默认)"
        echo "  stop         急停 (发零速度)"
        echo "  resume       恢复控制"
        echo "  reset_odom   里程计归零"
        echo "  check|verify   检查所有节点是否启动成功"
        echo "  status       查看状态"
        echo "  cleanup      杀掉全部节点并释放串口"
        exit 1
        ;;
esac