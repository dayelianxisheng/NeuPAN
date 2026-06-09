# Docker ROS 环境构建指南

基于踩坑实录，覆盖代理、加速源、ROS 镜像构建和项目部署全流程。

---

## 一、拉取现成镜像（最快，推荐）

大部分情况不需要自己 build，Docker Hub 上都有：

```bash
# ROS1
docker pull ros:noetic-ros-core              # 最简，只有通信
docker pull ros:noetic-ros-base              # + 基础工具
docker pull osrf/ros:noetic-desktop-full     # + GUI + Gazebo

# ROS2
docker pull ros:humble-ros-core
docker pull ros:humble-desktop-full
docker pull ros:jazzy-ros-core
docker pull ros:jazzy-desktop-full

# 纯 Gazebo
docker pull gazebo:gzserver11
```

---

## 二、从 docker_images 仓库自己构建

适用于需要定制、离线环境、或 Docker Hub 不可用时。

### (1) 克隆仓库

```bash
git clone git@github.com:dayelianxisheng/docker_images.git
cd docker_images
```

> **知道为什么会有 ros/ 和 ros2/ 两个目录吗？**
> 
> - `ros/` → Docker Hub 上叫 `ros` 的 Official Image，包含 **ROS1 和 ROS2 的正式发行版**
> - `ros2/` → 仅有 nightly/testing/source 等 **开发版本**
> 
> 所以 ROS2 Humble、Jazzy 等正式版在 `ros/` 下，不在 `ros2/` 下。

### (2) 构建 ROS + Gazebo

```bash
# 以 ROS1 Noetic 为例
cd ros/noetic/ubuntu/focal

# 一键构建底层镜像（ros-core → ros-base → robot → perception）
make build

# desktop（GUI 工具）
docker build --tag=osrf/ros:noetic-desktop-focal desktop/.

# desktop-full（+ Gazebo，这个就是最完整的）
docker build --tag=osrf/ros:noetic-desktop-full-focal desktop-full/.

# 验证
docker run -it --rm osrf/ros:noetic-desktop-full-focal gzserver --version
```

### (3) 其他常用组合

| 需求 | 构建命令 |
|---|---|
| ROS2 Humble + Gazebo | `cd ros/humble/ubuntu/jammy && make build && docker build desktop-full/.` |
| ROS2 Jazzy + Gazebo | `cd ros/jazzy/ubuntu/noble && make build && docker build desktop-full/.` |
| 纯 Gazebo 11 | `cd gazebo/11/ubuntu/focal && make build` |

---

## 三、代理配置

### Docker 拉取镜像加速（registry-mirrors）

编辑 `/etc/docker/daemon.json`：

```json
{
  "registry-mirrors": [
    "https://docker.1panel.live",
    "https://hub.rat.dev"
  ]
}
```

重启 Docker：`sudo systemctl restart docker`

### 构建时容器内网络代理

Docker 容器默认走宿主机网络，但 `docker build` 时需要显式传入：

```bash
docker build \
    --build-arg HTTP_PROXY=http://127.0.0.1:7897 \
    --build-arg HTTPS_PROXY=http://127.0.0.1:7897 \
    -t my-image .
```

Clash Verge 默认端口是 **7897**（有些版本是 7890），去 Clash 面板确认。

### apt 加速（清华源）

容器内替换 apt 源：

```bash
sed -i 's/archive.ubuntu.com/mirrors.tuna.tsinghua.edu.cn/g' /etc/apt/sources.list
```

### pip 加速

```bash
pip install -i https://pypi.tuna.tsinghua.edu.cn/simple <package>
```

### git clone 加速

```bash
git config --global http.proxy http://127.0.0.1:7897
git config --global https.proxy http://127.0.0.1:7897
```

> 或者改用 ssh 协议 clone（`git clone git@github.com:...`），不走 http 代理。

---

## 四、GPU + 图形界面

如果需要 Gazebo/RVIZ 显示画面：

```bash
# 允许 Docker 访问 X11
xhost +local:docker

docker run -it --rm \
    --gpus all \                # ← GPU 访问（Gazebo 渲染需要）
    --net=host \
    -e DISPLAY=$DISPLAY \
    -v /tmp/.X11-unix:/tmp/.X11-unix \
    osrf/ros:noetic-desktop-full-focal \
    bash
```

启动 Gazebo 时设置 NVIDIA GLX：

```bash
export __GLX_VENDOR_LIBRARY_NAME=nvidia   # ← 关键！否则有窗口没画面
roslaunch xxx.launch
```

> **坑**：即便加了 `--gpus all`，默认 GLX vendor 是 Mesa，Mesa 没有 NVIDIA DRI 驱动，导致有窗口但画面黑/无渲染。`__GLX_VENDOR_LIBRARY_NAME=nvidia` 强制走 NVIDIA GLX 就好了。

---

## 五、项目 Dockerfile 模板

以 NeuPAN 为例，展示如何为一个 ROS 项目写 Dockerfile：

```dockerfile
FROM osrf/ros:noetic-desktop-full-focal

# ── 代理通过 build-arg 传入 ────────
ARG HTTP_PROXY
ARG HTTPS_PROXY
ENV http_proxy=${HTTP_PROXY} https_proxy=${HTTPS_PROXY}

# ── 项目依赖 ──────────────────────
RUN sed -i 's/archive.ubuntu.com/mirrors.tuna.tsinghua.edu.cn/g' /etc/apt/sources.list \
    && apt-get update && apt-get install -y python3.9 git python3-numpy \
    && apt-get remove -y python3-matplotlib \
    && rm -rf /var/lib/apt/lists/*

# ── Python 依赖 ───────────────────
RUN python3.9 -m pip install -e . \
    && python3.9 -m pip install numpy==1.26.4

# ── 外部 ROS 包 ────────────────────
RUN git clone https://github.com/xxx/rvo_ros.git /ws/src/rvo_ros

# ── 编译 ──────────────────────────
RUN . /opt/ros/noetic/setup.sh && cd /ws && catkin_make

# ── 清理代理 ──────────────────────
ENV http_proxy= https_proxy=

# ── 入口 ──────────────────────────
RUN echo '. /opt/ros/noetic/setup.sh && . /ws/devel/setup.sh && export __GLX_VENDOR_LIBRARY_NAME=nvidia' > /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]
CMD ["bash"]
```

构建：

```bash
# 开代理
docker build --build-arg HTTP_PROXY=http://127.0.0.1:7897 --build-arg HTTPS_PROXY=http://127.0.0.1:7897 -t my-project .

# 不开代理
docker build -t my-project .
```

---

## 六、踩坑清单

| 问题 | 原因 | 解决 |
|---|---|---|
| `ros2/humble/...` 不存在 | ROS2 正式版在 `ros/` 下 | 用 `ros/humble/ubuntu/jammy` |
| catkin 找不到 Python 包 | CMakeLists.txt 所有 install 目标被注释 | 加 `catkin_install_python(PROGRAMS ...)` |
| `from X import Y` 找不到 Y | catkin wrapper exec 后 context 没暴露到模块 | `sed` 修 wrapper 模板加 `globals().update(context)` |
| Gazebo 有窗口没画面 | Mesa 没有 NVIDIA DRI 驱动 | `export __GLX_VENDOR_LIBRARY_NAME=nvidia` |
| `spawn_model` 崩溃 No module numpy | ROS 系统 Python 3.8 缺 numpy | `apt-get install python3-numpy` |
| `ft2font` 循环 import 错误 | Python 3.9 加载了 3.8 的 matplotlib .so | `apt-get remove python3-matplotlib` |
| `torch.min()` empty tensor | NeuPAN 库不接受空障碍物 | obstacle_points 初始化为 `np.empty((2,0))` + 扔一个远点 |
| Python 3.10 in deadsnakes 没了 | Ubuntu 20.04 deadsnakes 下架了 3.10 | 用 3.9，`pyproject.toml` 写的就是 `>= 3.9` |
| pip get-pip.py 报不支持 3.9 | 新 get-pip.py 最低要 3.10 | 用 `https://bootstrap.pypa.io/pip/3.9/get-pip.py` |
| git clone 巨慢 | 没走代理 | `git config --global http.proxy http://127.0.0.1:7897` |
| docker build 时 apt 巨慢 | 容器内没代理 | `--build-arg HTTP_PROXY=...` |
