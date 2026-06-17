# NeuPAN Docker

## 目录结构

```
docker/
├── container.sh         # 统一容器管理入口
├── ros1/
│   ├── setup.sh         # ROS1 一键环境配置
│   ├── rvo_ros/         # 预 clone（动态障碍物）
│   └── limo_ros/        # 预 clone（机器人模型）
├── ros2/
│   └── setup.sh         # ROS2 一键环境配置
└── README.md
```

## 快速开始

```bash
# ROS1（Gazebo 仿真）
./docker/container.sh ros1 setup    # 创建 + 安装依赖（只需一次）
./docker/container.sh ros1 enter    # 后续直接进入

# ROS2（ddr_minimal_sim 仿真）
./docker/container.sh ros2 setup
./docker/container.sh ros2 enter
```

## 命令

| 命令 | 作用 |
|------|------|
| `./docker/container.sh ros1 setup` | 删除旧容器 → 创建 → 代理 + 安装所有依赖 → 进入 |
| `./docker/container.sh ros1 enter` | 进入运行中的容器（自动设代理+ROS环境） |
| `./docker/container.sh ros1 start` | 启动已停止的容器并进入 |
| `./docker/container.sh ros1 stop` | 停止容器 |
| `./docker/container.sh ros1 status` | 查看状态 |

## 容器内测试

### ROS1

```bash
# 终端1：启动 Gazebo
roslaunch neupan_ros gazebo_limo_env_complex_20.launch

# 终端2：启动 NeuPAN
roslaunch neupan_ros neupan_gazebo_limo.launch

# 发布 goal
rostopic pub /move_base_simple/goal geometry_msgs/PoseStamped "
header:
  frame_id: odom
pose:
  position: {x: 2.0, y: 0.0, z: 0.0}
  orientation: {x: 0.0, y: 0.0, z: 0.0, w: 1.0}
"
```

### ROS2

```bash
ros2 launch neupan_ros2 sim_complete.launch.py

# 切换场景
ros2 launch neupan_ros2 sim_complete.launch.py sim_env_config:=scenario_corridor.yaml
```

## 原理

不再用 Dockerfile 构建镜像（Daemon 代理问题无法解决）。改为：

1. 从基础镜像创建容器（`--net=host` 让代理可达）
2. 容器内设代理，跑 `setup.sh` 装所有依赖
3. 容器持久保留，随时进入



## 前置条件

- Docker + NVIDIA Container Toolkit（GPU）
- 代理服务运行在 `127.0.0.1:7897`（Clash 等）
