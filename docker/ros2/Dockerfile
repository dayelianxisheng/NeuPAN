FROM ros:humble-ros-core

# ============================================================
# NeuPAN ROS2 (Humble) Docker 镜像
# ============================================================
# 构建:  ./docker/build.sh ros2
# 运行:  docker run -it --gpus all --net=host -e DISPLAY \
#         -v /tmp/.X11-unix:/tmp/.X11-unix [-v ...] neupan:ros2
# ============================================================

SHELL ["/bin/bash", "-c"]

# ── 国内加速源 ────────────────────────────────────────
RUN sed -i 's|http://archive.ubuntu.com|http://mirrors.tuna.tsinghua.edu.cn|g' /etc/apt/sources.list \
    && sed -i 's|http://security.ubuntu.com|http://mirrors.tuna.tsinghua.edu.cn|g' /etc/apt/sources.list \
    && apt-get update

# ── 系统依赖 ──────────────────────────────────────────
RUN apt-get install -y --no-install-recommends \
    ros-humble-tf-transformations \
    ros-humble-tf2-tools \
    ros-humble-tf2-ros \
    ros-humble-tf2-geometry-msgs \
    ros-humble-nav-msgs \
    ros-humble-sensor-msgs \
    ros-humble-geometry-msgs \
    ros-humble-visualization-msgs \
    ros-humble-rviz2 \
    ros-humble-ament-cmake \
    ros-humble-ament-cmake-python \
    python3-colcon-common-extensions \
    python3-rosdep \
    python3-pip \
    python3-tk \
    libeigen3-dev \
    libyaml-cpp-dev \
    build-essential \
    cmake \
    git \
    && rm -rf /var/lib/apt/lists/*

# ── pip 全局清华源 ──────────────────────────────────
RUN mkdir -p /root/.config/pip \
    && echo '[global]' > /root/.config/pip/pip.conf \
    && echo 'index-url = https://pypi.tuna.tsinghua.edu.cn/simple' >> /root/.config/pip/pip.conf

# ── Python 依赖 ───────────────────────────────────────
RUN python3 -m pip install --upgrade pip setuptools==69.5.1 wheel
RUN python3 -m pip install numpy==1.26.4 scipy==1.13.0

# ── PyTorch 2.8.0 CUDA 12.8 ──────────────────────────
RUN python3 -m pip install torch==2.8.0+cu128 \
    --index-url https://download.pytorch.org/whl/cu128 \
    --extra-index-url https://pypi.tuna.tsinghua.edu.cn/simple

# ── 安装 NeuPAN ───────────────────────────────────────
COPY . /root/neupan_ros2_ws/src/NeuPAN

RUN cd /root/neupan_ros2_ws/src/NeuPAN \
    && python3 -m pip install -e .

# ── 构建 ROS2 workspace ───────────────────────────────
ENV ROSDISTRO_INDEX_URL=https://mirrors.tuna.tsinghua.edu.cn/rosdistro/index-v4.yaml
RUN source /opt/ros/humble/setup.bash \
    && cd /root/neupan_ros2_ws/src/NeuPAN/neupan_ros2 \
    && colcon build --symlink-install --cmake-args -DCMAKE_BUILD_TYPE=Release \
    || (echo "Build failed. Trying with updated dependencies..." \
        && rosdep init && rosdep update && rosdep install -i --from-path . --rosdistro humble -y \
        && colcon build --symlink-install --cmake-args -DCMAKE_BUILD_TYPE=Release)

# ── 入口脚本 ──────────────────────────────────────────
RUN printf '#!/bin/bash\n\
source /opt/ros/humble/setup.bash\n\
WS_SETUP="/root/neupan_ros2_ws/src/NeuPAN/neupan_ros2/install/setup.bash"\n\
[[ -f "$WS_SETUP" ]] && source "$WS_SETUP"\n\
export __GLX_VENDOR_LIBRARY_NAME=nvidia\n\
cd /root/neupan_ros2_ws/src/NeuPAN/neupan_ros2\n\
exec "$@"\n' > /entrypoint.sh && chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
CMD ["bash"]
