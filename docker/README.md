# ============================================================
# NeuPAN Docker
# ============================================================

## 目录结构
```
docker/
├── ros1/
│   └── Dockerfile       # ROS Noetic + Gazebo + neupan_ros
├── ros2/
│   └── Dockerfile       # ROS Humble + ddr_minimal_sim + neupan_ros2
└── build.sh             # 构建脚本
```

## 快速开始

```bash
# 构建镜像
./docker/build.sh ros1       # ROS1 镜像
./docker/build.sh ros2       # ROS2 镜像

# 国内代理加速
./docker/build.sh ros2 --proxy

# 运行容器
xhost +local:docker

# ROS1（Gazebo 仿真）
docker run -it --gpus all --net=host -e DISPLAY \
  -v /tmp/.X11-unix:/tmp/.X11-unix neupan:noetic

# ROS2（ddr_minimal_sim 仿真）
docker run -it --gpus all --net=host -e DISPLAY \
  -v /tmp/.X11-unix:/tmp/.X11-unix neupan:humble
```

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
