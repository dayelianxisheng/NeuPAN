FROM osrf/ros:noetic-desktop-full-focal

# ── 代理（构建时通过 --build-arg 传入） ──────────────
ARG HTTP_PROXY
ARG HTTPS_PROXY
ARG NO_PROXY=localhost,127.0.0.1
ENV http_proxy=${HTTP_PROXY} \
    https_proxy=${HTTPS_PROXY} \
    no_proxy=${NO_PROXY}

# ── 系统依赖 ──────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
    software-properties-common git \
    && add-apt-repository -y ppa:deadsnakes/ppa \
    && apt-get update && apt-get install -y --no-install-recommends \
    python3.9 python3.9-dev python3.9-venv python3.9-tk \
    && rm -rf /var/lib/apt/lists/*

# ── Python 3.9 pip ────────────────────────────────────
RUN curl -sS https://bootstrap.pypa.io/pip/3.9/get-pip.py | python3.9

# ── ROS 系统 Python 的 numpy（spawn_model 需要） ─────
RUN apt-get update && apt-get install -y --no-install-recommends python3-numpy \
    && apt-get remove -y python3-matplotlib \
    && rm -rf /var/lib/apt/lists/*

# ── 修复 catkin wrapper：让 exec 后的名字暴露给 import ──
RUN sed -i 's/exec(compile(fh.read(), python_script, "exec"), context)/exec(compile(fh.read(), python_script, "exec"), context)\n    globals().update(context)/' \
    /opt/ros/noetic/share/catkin/cmake/template/script.py.in

# ── NeuPAN Planner ─────────────────────────────────────
COPY . /root/neupan_ws/src/NeuPAN
RUN cd /root/neupan_ws/src/NeuPAN \
    && python3.9 -m pip install -e . \
    && python3.9 -m pip install numpy==1.26.4

# ── 修复 neupan_core: obstacle_points 空数组问题 ──────
RUN sed -i 's/self.obstacle_points = None  # (2, n)/self.obstacle_points = np.empty((2, 0))  # (2, n)/' \
    /root/neupan_ws/src/NeuPAN/neupan_ros/src/neupan_core.py \
    && sed -i 's/            self.obstacle_points = None$/            self.obstacle_points = np.empty((2, 0))/' \
    /root/neupan_ws/src/NeuPAN/neupan_ros/src/neupan_core.py \
    && sed -i 's/            return None$/            return self.obstacle_points/' \
    /root/neupan_ws/src/NeuPAN/neupan_ros/src/neupan_core.py \
    && sed -i 's/if self.obstacle_points is None:/if self.obstacle_points is None or self.obstacle_points.shape[1] == 0:/' \
    /root/neupan_ws/src/NeuPAN/neupan_ros/src/neupan_core.py
RUN sed -i '/No obstacle points, only path tracking task will be performed/a\                self.obstacle_points = np.array([[100.0], [100.0]])' \
    /root/neupan_ws/src/NeuPAN/neupan_ros/src/neupan_core.py

# ── 修复 shebangs → python3.9 ──────────────────────────
RUN sed -i '1s|#!/usr/bin/env python.*|#!/usr/bin/env python3.9|' \
    /root/neupan_ws/src/NeuPAN/neupan_ros/src/neupan_node.py \
    /root/neupan_ws/src/NeuPAN/neupan_ros/src/neupan_core.py

# ── rvo_ros + limo_ros ─────────────────────────────────
RUN git config --global http.proxy ${HTTP_PROXY} 2>/dev/null; \
    git config --global https.proxy ${HTTPS_PROXY} 2>/dev/null; \
    cd /root/neupan_ws/src \
    && git clone https://github.com/hanruihua/rvo_ros.git \
    && git clone https://github.com/hanruihua/limo_ros.git \
    && git config --global --unset http.proxy 2>/dev/null; \
    git config --global --unset https.proxy 2>/dev/null

# ── 编译工作空间 ──────────────────────────────────────
RUN bash -c "source /opt/ros/noetic/setup.bash \
    && cd /root/neupan_ws \
    && catkin_make -DPYTHON_EXECUTABLE=/usr/bin/python3.9"

# ── 清除代理环境变量（运行时不需要） ──────────────────
ENV http_proxy= \
    https_proxy= \
    HTTP_PROXY= \
    HTTPS_PROXY=

# ── 环境入口 ──────────────────────────────────────────
RUN echo '#!/bin/bash\n\
source /opt/ros/noetic/setup.bash\n\
source /root/neupan_ws/devel/setup.bash\n\
export GAZEBO_PLUGIN_PATH=${GAZEBO_PLUGIN_PATH}:/root/neupan_ws/devel/lib\n\
export __GLX_VENDOR_LIBRARY_NAME=nvidia\n\
cd /root/neupan_ws\n\
exec "$@"' > /entrypoint.sh && chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
CMD ["bash"]
