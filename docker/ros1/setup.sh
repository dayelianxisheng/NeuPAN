#!/bin/bash
# ============================================================
# NeuPAN ROS1 容器内一键环境配置脚本
# 用法: export http_proxy=http://127.0.0.1:7897 && bash setup.sh
# ============================================================
set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

WS=/root/neupan_ws
NEUPAN_SRC=$WS/src/NeuPAN

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}NeuPAN ROS1 环境配置（走代理）${NC}"
echo -e "${GREEN}========================================${NC}"

# ── apt 系统依赖 ──────────────────────────────────
echo -e "${YELLOW}[1/8] apt 系统依赖...${NC}"
apt-get update
apt-get install -y --no-install-recommends \
    git curl build-essential software-properties-common
add-apt-repository -y ppa:deadsnakes/ppa
apt-get update
apt-get install -y --no-install-recommends \
    python3.9 python3.9-dev python3.9-venv idle-python3.9 \
    python3-numpy \
    ros-noetic-tf2-tools ros-noetic-tf2-ros ros-noetic-tf2-geometry-msgs \
    ros-noetic-gazebo-ros ros-noetic-gazebo-plugins \
    ros-noetic-rviz ros-noetic-robot-state-publisher ros-noetic-joint-state-publisher \
    ros-noetic-roslint ros-noetic-xacro ros-noetic-controller-manager \
    ros-noetic-gazebo-ros-control ros-noetic-joint-state-controller
rm -rf /var/lib/apt/lists/*

# ── pip ────────────────────────────────────────────
echo -e "${YELLOW}[2/8] pip 配置...${NC}"
curl -sS https://bootstrap.pypa.io/pip/3.9/get-pip.py | python3.9

# ── Python 依赖 ─────────────────────────────────────
echo -e "${YELLOW}[3/8] numpy/scipy...${NC}"
python3.9 -m pip install --upgrade pip setuptools wheel
python3.9 -m pip install numpy==1.26.4 scipy==1.13.0

# ── torch GPU ───────────────────────────────────────
echo -e "${YELLOW}[4/8] torch 2.8.0+cu128...${NC}"
python3.9 -m pip install torch==2.8.0+cu128 \
    --index-url https://download.pytorch.org/whl/cu128

# ── neupan ───────────────────────────────────────────
echo -e "${YELLOW}[5/8] 安装 neupan...${NC}"
cd "$NEUPAN_SRC"
python3.9 -m pip install -e .

# ── 恢复系统 numpy ──────────────────────────────────
echo -e "${YELLOW}[6/8] 修复系统 numpy...${NC}"
apt-get update && apt-get install -y --reinstall python3-numpy
rm -rf /var/lib/apt/lists/*

# ── rvo_ros + limo_ros + 修复 + 编译 ────────────────
echo -e "${YELLOW}[7/8] clone rvo_ros + limo_ros + 编译...${NC}"
NEUPAN_SRC=$NEUPAN_SRC python3.9 << 'PYFIX'
import os, re
src = os.environ["NEUPAN_SRC"]
f = open(f"{src}/neupan_ros/src/neupan_core.py")
c = f.read(); f.close()
c = c.replace("self.obstacle_points = None  # (2, n)", "self.obstacle_points = np.empty((2, 0))  # (2, n)")
pat = r'(if self\.obstacle_points is None[\s\S]*?No obstacle points[\s\S]*?)\n(\s+)\)'
c = re.sub(pat, r'\1\n\2                self.obstacle_points = np.array([[100.0], [100.0]])\n\2)', c)
f = open(f"{src}/neupan_ros/src/neupan_core.py", "w")
f.write(c); f.close()
print("neupan_core fixed")
PYFIX

cd "$WS/src"
if [ -d "$NEUPAN_SRC/docker/ros1/rvo_ros" ]; then
    cp -r "$NEUPAN_SRC/docker/ros1/rvo_ros" ./rvo_ros
    cp -r "$NEUPAN_SRC/docker/ros1/limo_ros" ./limo_ros
else
    git clone https://github.com/hanruihua/rvo_ros.git
    git clone https://github.com/hanruihua/limo_ros.git
fi
rm -rf rvo_ros/.git limo_ros/.git 2>/dev/null
rm -rf "$NEUPAN_SRC/neupan_ros2" 2>/dev/null
rm -rf "$NEUPAN_SRC/docker/ros1/rvo_ros" "$NEUPAN_SRC/docker/ros1/limo_ros" 2>/dev/null

# 修复 neupan_core（空 obstacle_points 兼容 + 语法修复）
python3.9 -c "
c = open('$NEUPAN_SRC/neupan_ros/src/neupan_core.py').read()
c = c.replace('self.obstacle_points = None  # (2, n)', 'self.obstacle_points = np.empty((2, 0))  # (2, n)')
old = '''            if self.obstacle_points is None or self.obstacle_points.shape[1] == 0:
                rospy.logwarn_throttle(
                    1, \"No obstacle points, only path tracking task will be performed\"
                )
'''
new = old + '                self.obstacle_points = np.array([[100.0], [100.0]])\n'
if old in c: c = c.replace(old, new)
open('$NEUPAN_SRC/neupan_ros/src/neupan_core.py', 'w').write(c)
print('neupan_core fixed')
"

# 修复 shebangs
sed -i '1s|#!/usr/bin/env python.*|#!/usr/bin/env python3.9|' \
    "$NEUPAN_SRC/neupan_ros/src/neupan_node.py" \
    "$NEUPAN_SRC/neupan_ros/src/neupan_core.py"
chmod +x "$NEUPAN_SRC/neupan_ros/src/neupan_node.py"

# ── 编译 ─────────────────────────────────────────────
echo -e "${YELLOW}[8/8] catkin_make...${NC}"
source /opt/ros/noetic/setup.bash
cd "$WS"
catkin_make -DPYTHON_EXECUTABLE=/usr/bin/python3.9

# ── 修复 catkin wrapper（用 globals() 替代独立 context） ──
for f in neupan_node neupan_core setup; do
    WF="$WS/devel/lib/neupan_ros/${f}.py"
    SRC_FILE="$NEUPAN_SRC/neupan_ros/src/${f}.py"
    [ -f "$WF" ] && cat > "$WF" << WEND
#!/usr/bin/python3.9
python_script = "$SRC_FILE"
with open(python_script, "r") as fh:
    exec(compile(fh.read(), python_script, "exec"), globals())
WEND
    [ -f "$WF" ] && chmod +x "$WF"
done

# ── 入口脚本 ──────────────────────────────────────────
cat > /entrypoint.sh << 'ENTRY'
#!/bin/bash
source /opt/ros/noetic/setup.bash
[[ -f "/root/neupan_ws/devel/setup.bash" ]] && source /root/neupan_ws/devel/setup.bash
export GAZEBO_PLUGIN_PATH=${GAZEBO_PLUGIN_PATH}:/root/neupan_ws/devel/lib
export __GLX_VENDOR_LIBRARY_NAME=nvidia
cd /root/neupan_ws
exec "$@"
ENTRY
chmod +x /entrypoint.sh

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}配置完成！${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "启动: roslaunch neupan_ros gazebo_limo_env_complex_20.launch"
echo "固化: docker commit ros1_dev neupan:ros1"
