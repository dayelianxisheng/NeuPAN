#!/bin/bash
# ========================================
# mowen 新小车 — 快速检查脚本
# 用途: 部署前的自动化检查
# ========================================

set -e

COLOR_RED='\033[0;31m'
COLOR_GREEN='\033[0;32m'
COLOR_YELLOW='\033[1;33m'
COLOR_NC='\033[0m' # No Color

echo "========================================"
echo " mowen 新小车 — 快速检查"
echo "========================================"

# 1. 检查 ROS 环境
echo ""
echo "【1/8】检查 ROS 环境..."
if [ -z "$ROS_MASTER_URI" ]; then
    echo -e "${COLOR_RED}✗ ROS_MASTER_URI 未设置${COLOR_NC}"
    echo "  请设置: export ROS_MASTER_URI=http://<小车IP>:11311"
    exit 1
else
    echo -e "${COLOR_GREEN}✓ ROS_MASTER_URI = $ROS_MASTER_URI${COLOR_NC}"
fi

if [ -z "$ROS_IP" ]; then
    echo -e "${COLOR_YELLOW}⚠ ROS_IP 未设置（可能影响多机通信）${COLOR_NC}"
    echo "  建议设置: export ROS_IP=<本机IP>"
else
    echo -e "${COLOR_GREEN}✓ ROS_IP = $ROS_IP${COLOR_NC}"
fi

# 2. 检查 ROS 连接
echo ""
echo "【2/8】检查 ROS 连接..."
if timeout 3 rostopic list > /dev/null 2>&1; then
    echo -e "${COLOR_GREEN}✓ 成功连接到 ROS Master${COLOR_NC}"
else
    echo -e "${COLOR_RED}✗ 无法连接到 ROS Master${COLOR_NC}"
    echo "  请检查网络连接和 ROS_MASTER_URI"
    exit 1
fi

# 3. 检查必需的 topics
echo ""
echo "【3/8】检查必需的 topics..."

TOPICS=$(rostopic list 2>/dev/null || echo "")

if echo "$TOPICS" | grep -q "/scan"; then
    echo -e "${COLOR_GREEN}✓ /scan 存在${COLOR_NC}"
else
    echo -e "${COLOR_RED}✗ /scan 不存在 (激光雷达未启动)${COLOR_NC}"
    exit 1
fi

if echo "$TOPICS" | grep -q "/odom"; then
    echo -e "${COLOR_GREEN}✓ /odom 存在${COLOR_NC}"
elif echo "$TOPICS" | grep -q "/odom_raw"; then
    echo -e "${COLOR_YELLOW}⚠ 只有 /odom_raw (需要 EKF 或手动 TF)${COLOR_NC}"
else
    echo -e "${COLOR_RED}✗ /odom 和 /odom_raw 都不存在${COLOR_NC}"
    exit 1
fi

if echo "$TOPICS" | grep -q "/cmd_vel"; then
    echo -e "${COLOR_GREEN}✓ /cmd_vel 存在${COLOR_NC}"
else
    echo -e "${COLOR_YELLOW}⚠ /cmd_vel 不存在 (底盘驱动可能未启动)${COLOR_NC}"
fi

# 4. 检查 TF 树
echo ""
echo "【4/8】检查 TF 树..."

if timeout 3 rosrun tf tf_echo odom base_link 2>&1 | grep -q "At time"; then
    echo -e "${COLOR_GREEN}✓ odom → base_link 变换正常${COLOR_NC}"
else
    echo -e "${COLOR_RED}✗ odom → base_link 变换失败${COLOR_NC}"
    echo "  请检查里程计和 TF 静态发布节点"
    exit 1
fi

if timeout 3 rosrun tf tf_echo base_link laser_link 2>&1 | grep -q "At time"; then
    echo -e "${COLOR_GREEN}✓ base_link → laser_link 变换正常${COLOR_NC}"
else
    echo -e "${COLOR_YELLOW}⚠ base_link → laser_link 变换失败${COLOR_NC}"
    echo "  请检查激光雷达 TF 配置"
fi

# 5. 检查激光雷达数据
echo ""
echo "【5/8】检查激光雷达数据..."

SCAN_HZ=$(timeout 3 rostopic hz /scan 2>&1 | grep "average rate" | awk '{print $3}' || echo "0")
if (( $(echo "$SCAN_HZ > 5" | bc -l) )); then
    echo -e "${COLOR_GREEN}✓ /scan 频率: ${SCAN_HZ} Hz${COLOR_NC}"
else
    echo -e "${COLOR_RED}✗ /scan 频率过低或无数据: ${SCAN_HZ} Hz${COLOR_NC}"
    exit 1
fi

# 6. 检查 neupan_ros 包
echo ""
echo "【6/8】检查 neupan_ros 包..."

if rospack find neupan_ros > /dev/null 2>&1; then
    NEUPAN_PATH=$(rospack find neupan_ros)
    echo -e "${COLOR_GREEN}✓ neupan_ros 已安装: $NEUPAN_PATH${COLOR_NC}"
else
    echo -e "${COLOR_RED}✗ neupan_ros 未找到${COLOR_NC}"
    echo "  请检查 ROS 工作空间是否 source"
    exit 1
fi

# 7. 检查 DUNE 模型文件
echo ""
echo "【7/8】检查 DUNE 模型文件..."

NEUPAN_ROOT=$(rospack find neupan_ros)/..
DUNE_MODEL="$NEUPAN_ROOT/example/mowen/model/mowen_real/model_5000.pth"

if [ -f "$DUNE_MODEL" ]; then
    echo -e "${COLOR_GREEN}✓ DUNE 模型存在: $DUNE_MODEL${COLOR_NC}"
else
    echo -e "${COLOR_RED}✗ DUNE 模型不存在: $DUNE_MODEL${COLOR_NC}"
    echo "  请检查模型路径"
    exit 1
fi

# 8. 检查潜在的后台进程冲突
echo ""
echo "【8/8】检查潜在的后台进程冲突..."

ROSTOPIC_COUNT=$(ps aux | grep -v grep | grep -c "rostopic pub" || echo "0")
if [ "$ROSTOPIC_COUNT" -gt 0 ]; then
    echo -e "${COLOR_YELLOW}⚠ 发现 $ROSTOPIC_COUNT 个后台 rostopic pub 进程${COLOR_NC}"
    echo "  这可能导致小车失控！"
    echo "  建议执行: pkill -f 'rostopic pub'"
else
    echo -e "${COLOR_GREEN}✓ 无后台 rostopic pub 进程${COLOR_NC}"
fi

# 检查完成
echo ""
echo "========================================"
echo -e "${COLOR_GREEN}✓ 所有检查通过！${COLOR_NC}"
echo "========================================"
echo ""
echo "下一步:"
echo "  1. 在小车端启动: roslaunch <workspace>/robot_minimal.launch"
echo "  2. 在控制端启动: roslaunch neupan_ros test_simple_straight.launch"
echo "  3. 运行测试脚本: python3 test_simple_move.py"
echo ""
echo "⚠️  安全提示:"
echo "  - 确保测试区域清空，周围无人"
echo "  - 准备好急停方案"
echo "  - 首次测试建议低速 (ref_speed: 0.1)"
echo ""
