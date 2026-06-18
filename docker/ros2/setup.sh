#!/bin/bash
# ============================================================
# NeuPAN ROS2 容器内一键环境配置脚本
# 用法: 进入容器后 bash setup.sh（torch 需要代理则先 export http_proxy=...）
# ============================================================
set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

WS=/root/neupan_ros2_ws
NEUPAN_SRC=$WS/src/NeuPAN

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}NeuPAN ROS2 环境配置${NC}"
echo -e "${GREEN}========================================${NC}"

# ── apt 系统依赖 ──────────────────────────────────
echo -e "${YELLOW}[1/5] apt 系统依赖...${NC}"
apt-get update
apt-get install -y --no-install-recommends \
    git curl build-essential cmake \
    python3-pip python3-tk python3-colcon-common-extensions python3-rosdep \
    libeigen3-dev libyaml-cpp-dev \
    ros-humble-tf-transformations ros-humble-tf2-tools ros-humble-tf2-ros \
    ros-humble-tf2-geometry-msgs ros-humble-nav-msgs ros-humble-sensor-msgs \
    ros-humble-geometry-msgs ros-humble-visualization-msgs ros-humble-rviz2 \
    ros-humble-ament-cmake ros-humble-ament-cmake-python
rm -rf /var/lib/apt/lists/*

# ── Python 依赖 ─────────────────────────────────────
echo -e "${YELLOW}[2/5] numpy/scipy...${NC}"
python3 -m pip install --upgrade pip setuptools wheel
python3 -m pip install numpy==1.26.4 scipy==1.13.0

# ── torch GPU（需要代理） ───────────────────────────
echo -e "${YELLOW}[3/5] torch 2.8.0+cu128...${NC}"
python3 -m pip install torch==2.8.0+cu128 \
    --index-url https://download.pytorch.org/whl/cu128


# ── 安装 neupan ──────────────────────────────────────
echo -e "${YELLOW}[4/5] 安装 neupan...${NC}"
cd "$NEUPAN_SRC"
python3 -m pip install -e .

# ── 编译 ROS2 workspace ──────────────────────────────
echo -e "${YELLOW}[5/5] colcon build...${NC}"
source /opt/ros/humble/setup.bash
cd "$NEUPAN_SRC/neupan_ros2"
rm -rf build install log
colcon build --cmake-args -DCMAKE_BUILD_TYPE=Release \
    || (rosdep init && rosdep update && rosdep install -i --from-path . --rosdistro humble -y \
        && colcon build --symlink-install --cmake-args -DCMAKE_BUILD_TYPE=Release)

# ── 入口脚本 ──────────────────────────────────────────
cat > /entrypoint.sh << 'ENTRY'
#!/bin/bash
source /opt/ros/humble/setup.bash
WS_SETUP="/root/neupan_ros2_ws/src/NeuPAN/neupan_ros2/install/setup.bash"
[[ -f "$WS_SETUP" ]] && source "$WS_SETUP"
export __GLX_VENDOR_LIBRARY_NAME=nvidia
cd /root/neupan_ros2_ws/src/NeuPAN/neupan_ros2
exec "$@"
ENTRY
chmod +x /entrypoint.sh

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}配置完成！${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "启动: ros2 launch neupan_ros2 sim_complete.launch.py"
echo "固化: docker commit ros2_dev neupan:ros2"
