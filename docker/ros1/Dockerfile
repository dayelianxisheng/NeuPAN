FROM osrf/ros:noetic-desktop-full-focal

# ============================================================
# NeuPAN ROS1 (Noetic) + Gazebo Docker 镜像
# ============================================================
# 构建:  docker build -t neupan:noetic -f docker/ros1/Dockerfile .
#        docker build --build-arg HTTP_PROXY=http://127.0.0.1:7897 \
#                     --build-arg HTTPS_PROXY=http://127.0.0.1:7897 \
#                     -t neupan:noetic -f docker/ros1/Dockerfile .
# 运行:  docker run -it --gpus all --net=host -e DISPLAY \
#         -v /tmp/.X11-unix:/tmp/.X11-unix neupan:noetic
# ============================================================

# ── 代理（构建时通过 --build-arg 传入） ──────────────
ARG HTTP_PROXY
ARG HTTPS_PROXY
ARG NO_PROXY=localhost,127.0.0.1
ENV http_proxy=${HTTP_PROXY} \
    https_proxy=${HTTPS_PROXY} \
    no_proxy=${NO_PROXY}

SHELL ["/bin/bash", "-c"]

# ── 国内加速源 ────────────────────────────────────────
RUN sed -i 's|http://archive.ubuntu.com|http://mirrors.tuna.tsinghua.edu.cn|g' /etc/apt/sources.list \
    && sed -i 's|http://security.ubuntu.com|http://mirrors.tuna.tsinghua.edu.cn|g' /etc/apt/sources.list \
    && apt-get update

# ── 系统依赖 ──────────────────────────────────────────
RUN apt-get install -y --no-install-recommends \
    software-properties-common git curl \
    ros-noetic-tf2-tools \
    ros-noetic-tf2-ros \
    ros-noetic-tf2-geometry-msgs \
    && add-apt-repository -y ppa:deadsnakes/ppa \
    && apt-get update && apt-get install -y --no-install-recommends \
    python3.9 python3.9-dev python3.9-venv python3.9-tk python3.9-distutils \
    && rm -rf /var/lib/apt/lists/*

# ── Python 3.9 pip ────────────────────────────────────
RUN curl -sS https://bootstrap.pypa.io/pip/3.9/get-pip.py | python3.9

# ── NeuPAN Python 依赖 ────────────────────────────────
RUN python3.9 -m pip install --upgrade pip setuptools wheel \
    -i https://pypi.tuna.tsinghua.edu.cn/simple
RUN python3.9 -m pip install numpy==1.26.4 scipy==1.13.0 \
    -i https://pypi.tuna.tsinghua.edu.cn/simple
RUN python3.9 -m pip install torch --index-url https://download.pytorch.org/whl/cpu

COPY . /root/neupan_ws/src/NeuPAN

RUN cd /root/neupan_ws/src/NeuPAN \
    && python3.9 -m pip install -e . -i https://pypi.tuna.tsinghua.edu.cn/simple

# ── 移除 ROS2 包（catkin_make 不兼容） ──────────────────
RUN rm -rf /root/neupan_ws/src/NeuPAN/neupan_ros2

# ── 修复 neupan_core: 空 obstacle_points 兼容 ──────────
RUN sed -i 's|self.obstacle_points = None  # (2, n)|self.obstacle_points = np.empty((2, 0))  # (2, n)|' \
    /root/neupan_ws/src/NeuPAN/neupan_ros/src/neupan_core.py \
    && sed -i '/No obstacle points, only path tracking task will be performed/a\                self.obstacle_points = np.array([[100.0], [100.0]])' \
    /root/neupan_ws/src/NeuPAN/neupan_ros/src/neupan_core.py

# ── 修复 shebangs → python3.9 ──────────────────────────
RUN sed -i '1s|#!/usr/bin/env python.*|#!/usr/bin/env python3.9|' \
    /root/neupan_ws/src/NeuPAN/neupan_ros/src/neupan_node.py \
    /root/neupan_ws/src/NeuPAN/neupan_ros/src/neupan_core.py \
    && chmod +x /root/neupan_ws/src/NeuPAN/neupan_ros/src/neupan_node.py

# ── rvo_ros + limo_ros（动态障碍物 + 机器人模型） ───
RUN cd /root/neupan_ws/src \
    && if [ -n "$HTTP_PROXY" ]; then \
         git config --global http.proxy "$HTTP_PROXY"; \
         git config --global https.proxy "$HTTPS_PROXY"; \
       fi \
    && git clone https://github.com/hanruihua/rvo_ros.git \
    && git clone https://github.com/hanruihua/limo_ros.git \
    && if [ -n "$HTTP_PROXY" ]; then \
         git config --global --unset http.proxy; \
         git config --global --unset https.proxy; \
       fi

# ── 编译 catkin workspace ──────────────────────────────
RUN source /opt/ros/noetic/setup.bash \
    && cd /root/neupan_ws \
    && catkin_make -DPYTHON_EXECUTABLE=/usr/bin/python3.9

# ── 清除代理（运行时不需要） ──────────────────────────
ENV http_proxy=""
ENV https_proxy=""
ENV HTTP_PROXY=""
ENV HTTPS_PROXY=""

# ── 入口脚本 ──────────────────────────────────────────
RUN printf '#!/bin/bash\n\
source /opt/ros/noetic/setup.bash\n\
source /root/neupan_ws/devel/setup.bash\n\
export GAZEBO_PLUGIN_PATH=${GAZEBO_PLUGIN_PATH}:/root/neupan_ws/devel/lib\n\
export __GLX_VENDOR_LIBRARY_NAME=nvidia\n\
cd /root/neupan_ws\n\
exec "$@"\n' > /entrypoint.sh && chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
CMD ["bash"]
