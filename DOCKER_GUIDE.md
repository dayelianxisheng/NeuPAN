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

## 五、NeuPAN 项目 Dockerfile

项目自带构建好的 Dockerfile，位于 `docker/` 目录。已内置清华国内加速源，无需代理即可快速构建。

### 构建

```bash
# 国内直连（已内置 apt/pip/rosdep 清华源）
./docker/build.sh ros1       # ROS1 Noetic + Gazebo
./docker/build.sh ros2       # ROS2 Humble + ddr_minimal_sim

# 如需代理（git clone 等场景）
./docker/build.sh ros2 --proxy                    # 默认 http://127.0.0.1:7897
./docker/build.sh ros1 --proxy http://x.x.x.x:7890  # 自定义代理
```

### 运行

```bash
xhost +local:docker

# ROS1（Gazebo 仿真 + 动态障碍物）
docker run -it --gpus all --net=host -e DISPLAY \
  -v /tmp/.X11-unix:/tmp/.X11-unix neupan:noetic

# ROS2（ddr_minimal_sim 仿真）
docker run -it --gpus all --net=host -e DISPLAY \
  -v /tmp/.X11-unix:/tmp/.X11-unix neupan:ros2
```

### 挂载代码（开发用）

```bash
docker run -it --gpus all --net=host -e DISPLAY \
  -v /tmp/.X11-unix:/tmp/.X11-unix \
  -v /home/qcqc/resource/code/eai/NeuPAN:/root/neupan_ros2_ws/src/NeuPAN \
  neupan:ros2
```

### 已内置的加速源

| 组件 | 镜像源 |
|------|--------|
| apt (Ubuntu) | `mirrors.tuna.tsinghua.edu.cn` |
| pip | `~/.config/pip/pip.conf` 全局清华源 |
| rosdep | `ROSDISTRO_INDEX_URL` → 清华 rosdistro |
| ROS 包 | Ubuntu 22.04 官方仓库自带 ROS Humble |

---

## 六、踩坑清单

### 构建相关

| 问题 | 原因 | 解决 |
|---|---|---|
| docker build 时 apt 巨慢 | 没换国内源 | Dockerfile 内置清华源 |
| pip install 依赖包走 PyPI 慢 | 没配 pip 全局源 | 加 `~/.config/pip/pip.conf` 写入清华 index-url |
| `.dockerignore` 排除 `neupan_ros2/` | 旧注释说 "catkin_make 不兼容" | 改为在 ROS1 Dockerfile 里 `rm -rf`，保留 ROS2 需要的包 |
| `neupan_ros2/build/` 构建产物被复制进镜像 | `.dockerignore` 的 `build/` 只匹配根目录 | 改用 `**/build/` `**/install/` `**/log/` |
| colcon 报 CMakeCache.txt 路径错误 | 宿主机构建产物（含旧绝对路径）被复制 | `.dockerignore` 排除 `**/build/` 等目录 |
| `rosdep: command not found` | 没装 `python3-rosdep` | `apt-get install python3-rosdep` |
| rosdep 报 `no sources directory exists` | 没执行 `rosdep init` | `rosdep init && rosdep update` |
| `pip install -e .` 后 numpy 版本被覆盖 | `pyproject.toml` 写 `'numpy'` 无版本约束 | 改为 `'numpy==1.26.4'` 锁定版本 |
| torch 依赖包（nvidia-cublas 等）下载慢 | pip index-url 与 torch 的冲突 | torch 用 `--index-url pytorch.org` + `--extra-index-url 清华` |

### ROS / 运行时相关

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
