# NeuPAN Docker

## 目录结构

```
docker/
├── ros1/
│   └── Dockerfile       # ROS Noetic + Gazebo + neupan_ros
├── ros2/
│   └── Dockerfile       # ROS Humble + ddr_minimal_sim + neupan_ros2
├── build.sh             # 构建脚本
└── README.md
```

## 快速开始

```bash
# 构建镜像（已内置清华加速源，无需代理）
./docker/build.sh ros1       # ROS1 镜像
./docker/build.sh ros2       # ROS2 镜像

# 如需通过代理加速（git clone 等清华源无法覆盖的场景）
./docker/build.sh ros2 --proxy                    # 使用默认代理 http://127.0.0.1:7897
./docker/build.sh ros1 --proxy http://192.168.1.1:7890  # 自定义代理

# 运行容器
xhost +local:docker

# ROS1（Gazebo 仿真）
docker run -it --gpus all --net=host -e DISPLAY \
  -v /tmp/.X11-unix:/tmp/.X11-unix neupan:noetic

# ROS2（ddr_minimal_sim 仿真）
docker run -it --gpus all --net=host -e DISPLAY \
  -v /tmp/.X11-unix:/tmp/.X11-unix neupan:humble
```

## 国内加速

镜像已内置以下清华镜像源，国内构建无需额外配置：

| 组件 | 镜像源 |
|------|--------|
| apt (Ubuntu) | `mirrors.tuna.tsinghua.edu.cn` |
| apt (ROS) | Ubuntu 官方仓库 (ROS Humble 自带) |
| pip | `pypi.tuna.tsinghua.edu.cn/simple` |
| rosdep | `mirrors.tuna.tsinghua.edu.cn/rosdistro` |

代理 (`--proxy`) 仅在需要 `git clone` 外部仓库（如 ROS1 的 `rvo_ros`、`limo_ros`）时有额外加速效果。

## 容器内使用

### ROS1

```bash
# Gazebo + NeuPAN 仿真
roslaunch neupan_ros gazebo_limo_env_complex_20.launch &
roslaunch neupan_ros neupan_gazebo_limo.launch
```

### ROS2

```bash
# 默认 maze 场景
ros2 launch neupan_ros2 sim_complete.launch.py

# 切换场景
ros2 launch neupan_ros2 sim_complete.launch.py sim_env_config:=scenario_u_trap.yaml
ros2 launch neupan_ros2 sim_complete.launch.py sim_env_config:=scenario_narrow_passage.yaml
ros2 launch neupan_ros2 sim_complete.launch.py sim_env_config:=scenario_polygon_random.yaml
ros2 launch neupan_ros2 sim_complete.launch.py sim_env_config:=scenario_corridor.yaml
ros2 launch neupan_ros2 sim_complete.launch.py sim_env_config:=scenario_empty.yaml
```

## ROS1 vs ROS2 对比

| | ROS1 (neupan_ros) | ROS2 (neupan_ros2) |
|---|---|---|
| **OS** | Ubuntu 20.04 | Ubuntu 22.04 |
| **ROS** | Noetic | Humble |
| **仿真器** | Gazebo Classic | ddr_minimal_sim (C++) |
| **动态障碍物** | ✅ (rvo_ros) | ❌ |
| **机器人** | LIMO | LIMO / Scout / Ranger |
| **可视化** | RViz | RViz2 |
| **多线程** | ❌ | ✅ MultiThreadedExecutor |
| **代码质量** | 基础 | 完善（类型标注、线程安全） |

## 构建流程

ROS2 镜像构建步骤：

1. **系统依赖** — apt 安装 ROS 包、编译工具链 (CMake, Eigen, yaml-cpp)
2. **Python 依赖** — pip 安装 numpy, scipy 等
3. **NeuPAN 安装** — `pip install -e .` 安装核心规划库
4. **ROS2 workspace** — `colcon build` 编译 `neupan_ros2` + `ddr_minimal_sim`

构建产物按层缓存：修改 `neupan_ros2` 源码后重新构建，只需重跑步骤 3-4。

## 常见问题

### 构建时 apt install 很慢

检查清华源是否生效：
```bash
docker run --rm ros:humble-ros-core cat /etc/apt/sources.list | grep ubuntu
```
应显示 `mirrors.tuna.tsinghua.edu.cn`。

### 构建时 pip install 很慢

检查 pip 清华源是否生效，确认 Dockerfile 中 pip 命令带有 `-i https://pypi.tuna.tsinghua.edu.cn/simple`。

### colcon build 报 CMakeCache.txt 路径错误

`.dockerignore` 已排除 `**/build/`、`**/install/`、`**/log/`，确保不会把宿主编译产物复制进镜像。如仍有问题，手动清理：
```bash
rm -rf neupan_ros2/build neupan_ros2/install neupan_ros2/log
```

### 容器内无法使用 GPU

主机需安装 NVIDIA Container Toolkit：
```bash
nvidia-container-toolkit --version
```
