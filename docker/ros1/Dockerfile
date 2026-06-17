FROM ros:noetic-ros-core

# ============================================================
# NeuPAN ROS1 (Noetic) + Gazebo Docker 镜像（py38 分支）
# ============================================================
# 构建:  ./docker/build.sh ros1
# 运行:  docker run -it --gpus all --net=host -e DISPLAY \
#         -v /tmp/.X11-unix:/tmp/.X11-unix [-v ...] neupan:ros1
# ============================================================

SHELL ["/bin/bash", "-c"]

# ── 系统依赖 ──────────────────────────────────────────
RUN sed -i 's|http://archive.ubuntu.com|http://mirrors.tuna.tsinghua.edu.cn|g' /etc/apt/sources.list \
    && sed -i 's|http://security.ubuntu.com|http://mirrors.tuna.tsinghua.edu.cn|g' /etc/apt/sources.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
        git \
        curl \
        build-essential \
        python3-pip \
        python3-numpy \
        python3-tk \
        ros-noetic-tf2-tools \
        ros-noetic-tf2-ros \
        ros-noetic-tf2-geometry-msgs \
        ros-noetic-gazebo-ros \
        ros-noetic-gazebo-plugins \
        ros-noetic-rviz \
        ros-noetic-robot-state-publisher \
        ros-noetic-joint-state-publisher \
        ros-noetic-roslint \
        ros-noetic-xacro \
        ros-noetic-controller-manager \
    && rm -rf /var/lib/apt/lists/*

# ── pip 全局清华源 ──────────────────────────────────
RUN mkdir -p /root/.config/pip \
    && echo '[global]' > /root/.config/pip/pip.conf \
    && echo 'index-url = https://pypi.tuna.tsinghua.edu.cn/simple' >> /root/.config/pip/pip.conf

# ── Python 依赖 ───────────────────────────────────────
RUN python3 -m pip install --upgrade pip setuptools wheel
RUN python3 -m pip install numpy scipy<=1.13.0

# ── PyTorch（CPU 版，Gazebo 仿真不需要 CUDA） ────────
RUN python3 -m pip install torch==2.0.1+cpu \
    --index-url https://download.pytorch.org/whl/cpu \
    --extra-index-url https://pypi.tuna.tsinghua.edu.cn/simple

# ── 安装 NeuPAN ───────────────────────────────────────
COPY . /root/neupan_ws/src/NeuPAN

RUN cd /root/neupan_ws/src/NeuPAN \
    && python3 -m pip install -e .

# ── 删除 ROS2 包（catkin_make 不兼容） ────────────────
RUN rm -rf /root/neupan_ws/src/NeuPAN/neupan_ros2

# ── 修复 neupan_core ──────────────────────────────────
RUN sed -i 's|self.obstacle_points = None  # (2, n)|self.obstacle_points = np.empty((2, 0))  # (2, n)|' \
        /root/neupan_ws/src/NeuPAN/neupan_ros/src/neupan_core.py \
    && sed -i '/No obstacle points, only path tracking task will be performed/a\                self.obstacle_points = np.array([[100.0], [100.0]])' \
        /root/neupan_ws/src/NeuPAN/neupan_ros/src/neupan_core.py

# ── 修复 shebangs → python3 ────────────────────────────
RUN sed -i '1s|#!/usr/bin/env python.*|#!/usr/bin/env python3|' \
        /root/neupan_ws/src/NeuPAN/neupan_ros/src/neupan_node.py \
        /root/neupan_ws/src/NeuPAN/neupan_ros/src/neupan_core.py \
    && chmod +x /root/neupan_ws/src/NeuPAN/neupan_ros/src/neupan_node.py

# ── rvo_ros + limo_ros（宿主机预 clone，构建时 COPY） ──
COPY docker/ros1/rvo_ros /root/neupan_ws/src/rvo_ros
COPY docker/ros1/limo_ros /root/neupan_ws/src/limo_ros
# 清除 NeuPAN 目录下的重复副本（COPY . 带进来的）
RUN rm -rf /root/neupan_ws/src/NeuPAN/docker/ros1/rvo_ros \
           /root/neupan_ws/src/NeuPAN/docker/ros1/limo_ros

# ── 编译 catkin workspace ──────────────────────────────
RUN source /opt/ros/noetic/setup.bash \
    && cd /root/neupan_ws \
    && catkin_make -DPYTHON_EXECUTABLE=/usr/bin/python3

# ── 入口脚本 ──────────────────────────────────────────
RUN printf '#!/bin/bash\n\
source /opt/ros/noetic/setup.bash\n\
WS_SETUP="/root/neupan_ws/devel/setup.bash"\n\
[[ -f "$WS_SETUP" ]] && source "$WS_SETUP"\n\
export GAZEBO_PLUGIN_PATH=${GAZEBO_PLUGIN_PATH}:/root/neupan_ws/devel/lib\n\
export __GLX_VENDOR_LIBRARY_NAME=nvidia\n\
cd /root/neupan_ws\n\
exec "$@"\n' > /entrypoint.sh && chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
CMD ["bash"]
