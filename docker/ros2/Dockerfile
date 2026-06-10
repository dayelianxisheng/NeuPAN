FROM ros:humble-ros-core

# ============================================================
# NeuPAN ROS2 (Humble) Docker 镜像
# ============================================================
# 构建:  docker build -t neupan:humble -f docker/ros2/Dockerfile .
#        docker build --build-arg HTTP_PROXY=http://127.0.0.1:7897 \
#                     --build-arg HTTPS_PROXY=http://127.0.0.1:7897 \
#                     -t neupan:humble -f docker/ros2/Dockerfile .
# 运行:  docker run -it --gpus all --net=host -e DISPLAY \
#         -v /tmp/.X11-unix:/tmp/.X11-unix neupan:humble
# ============================================================

# ── 代理（构建时通过 --build-arg 传入） ──────────────
ARG HTTP_PROXY
ARG HTTPS_PROXY
ARG NO_PROXY=localhost,127.0.0.1
ENV http_proxy=${HTTP_PROXY} \
    https_proxy=${HTTPS_PROXY} \
    no_proxy=${NO_PROXY}

SHELL ["/bin/bash", "-c"]

# ── 系统依赖 ──────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
    # ROS2 包
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
    # 构建工具
    python3-colcon-common-extensions \
    python3-pip \
    python3-tk \
    # C++ 依赖 (ddr_minimal_sim)
    libeigen3-dev \
    libyaml-cpp-dev \
    build-essential \
    cmake \
    git \
    && rm -rf /var/lib/apt/lists/*

# ── Python 依赖 ───────────────────────────────────────
RUN python3 -m pip install --upgrade pip setuptools==69.5.1 wheel
RUN python3 -m pip install numpy==1.26.4 scipy==1.13.0
RUN python3 -m pip install torch --index-url https://download.pytorch.org/whl/cpu

# ── 安装 NeuPAN ───────────────────────────────────────
COPY . /root/neupan_ros2_ws/src/NeuPAN

RUN cd /root/neupan_ros2_ws/src/NeuPAN \
    && python3 -m pip install -e .

# ── 构建 ROS2 workspace ───────────────────────────────
RUN source /opt/ros/humble/setup.bash \
    && cd /root/neupan_ros2_ws/src/NeuPAN/neupan_ros2 \
    && colcon build --symlink-install --cmake-args -DCMAKE_BUILD_TYPE=Release \
    || (echo "Build failed. Trying with updated dependencies..." \
        && rosdep update && rosdep install -i --from-path . --rosdistro humble -y \
        && colcon build --symlink-install --cmake-args -DCMAKE_BUILD_TYPE=Release)

# ── 清除代理（运行时不需要） ──────────────────────────
ENV http_proxy= \
    https_proxy= \
    HTTP_PROXY= \
    HTTPS_PROXY=

# ── 入口脚本 ──────────────────────────────────────────
RUN printf '#!/bin/bash\n\
source /opt/ros/humble/setup.bash\n\
source /root/neupan_ros2_ws/src/NeuPAN/neupan_ros2/install/setup.bash\n\
export __GLX_VENDOR_LIBRARY_NAME=nvidia\n\
cd /root/neupan_ros2_ws/src/NeuPAN/neupan_ros2\n\
exec "$@"\n' > /entrypoint.sh && chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
CMD ["bash"]
