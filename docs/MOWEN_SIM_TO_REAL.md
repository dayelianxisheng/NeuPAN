# NeuPAN Sim-to-Real 部署：newznzc_ws 改造详细方案

## 1. 背景

**newznzc_ws** 是 mowen 移动机器人的现有 ROS1 Melodic 工作空间，使用经典导航栈（AMCL + DWA + move_base）。本方案用 **NeuPAN** 替换 AMCL/DWA，实现端到端神经 MPC 规划。

- **目标平台**: mowen 机器人（全向底盘 + 机械臂）
- **项目位置**: `/home/zq/resource/code/emb_ai/mobile_robot/clone/newznzc_ws`
- **NeuPAN 项目**: `/home/zq/resource/code/emb_ai/mobile_robot/path_planning/NeuPAN`

## 2. 运动模型选择：为什么用 Omni

### 2.1 三种模型对比

| 模型 | 适用 | 输出 | mowen 适用？ |
|------|------|------|-------------|
| **diff** | 两轮差速 | `[v, omega]` | ❌ 无法前后平移 |
| **acker** | 阿克曼转向 | `[v, psi]` | ❌ 转向几何不匹配 |
| **omni** | 全向/麦克纳姆 | `[v, theta]` → `(vx, vy)` | ✅ 匹配 mowen 底盘协议 |

### 2.2 newznzc_ws 中的证据

```yaml
# nav04_amcl.launch
odom_model_type: omni              # AMCL 用全向模型

# dwa_local_planner_params.yaml
holonomic_robot: true             # DWA 开启全向
max_vel_y: 0.15                   # Y 方向速度

# car_bringup/param/robot_localization.yaml
# EKF 3D omnidirectional motion model
```

底盘协议 `newt.py` 同时发送 `cmd_twist_x`, `cmd_twist_y`, `cmd_twist_rotation` —— 全向三自由度。

### 2.3 NeuPAN 已有 mowen 训练好的 omni 模型

| 文件 | 内容 |
|------|------|
| `example/my_train/train.yaml` | `kinematics: 'omni'`, length=1.6, width=2.0 |
| `example/my_train/model/mowen/model_1500.pth` | 训练 5000 epoch 的 DUNE 模型 |

**结论：使用 omni 运动模型，配置参数必须与训练一致（length=1.6, width=2.0）**。

## 3. 训练细节

### 3.1 DUNE 训练

```
数据量: 100,000 随机样本
批次: 256
epoch: 5000
学习率: 5e-5 (衰减: 1500→2.5e-5, 3000→1.25e-5, 4500→6.25e-6)
数据范围: [-25, -25, 25, 25] 米（xy 边界）
```

### 3.2 模型质量

```
Mu Loss:        5.30e-7 (train) / 6.13e-6 (val)
Distance Loss:  1.35e-5 (train) / 8.24e-6 (val)
模型大小:  ~25 KB / checkpoint
```

### 3.3 训练环境

- Ubuntu 20.04 + Python 3.8 + torch 2.0.1+cpu
- 数据生成：随机点 + 机器人几何约束
- 不需要任何真实数据，纯几何训练

## 4. 当前差距

### 4.1 NeuPAN 部署配置缺 mowen

```
neupan_ros2/src/neupan_ros2/config/robots/
├── limo/        # diff, 0.322x0.22
├── scout/       # diff, 0.615x0.585
├── ranger/      # acker, 0.720x0.500
└── simulation/  # diff
```

**没有 mowen**。需新建。

### 4.2 ROS 版本不兼容

| | newznzc_ws | NeuPAN |
|---|---|---|
| ROS | Melodic (Ubuntu 18.04) | Noetic / Humble |
| Python | 2.7 / 3.6 | 3.9 / 3.10 |
| OpenCV | 3.2 (cv_bridge) | 4.x |

## 5. 改造方案

### 5.1 架构：双栈 + ros1_bridge

```
┌──────────────────────────────────┐
│  mowen 机器人                     │
│  Ubuntu 18.04 + ROS Melodic       │
│  - LeiShen LiDAR (lslidar)       │
│  - 串口底盘 (newt.py)             │
│  - EKF + AMCL (newznzc_ws)       │
└────────┬─────────────────────────┘
         │  ros1_bridge
         │  - /scan (PointCloud → LaserScan)
         │  - /tf (map → base_link)
         │  - /cmd_vel (Twist)
         ↓
┌──────────────────────────────────┐
│  NeuPAN 推理                      │
│  Docker: ros:humble-ros-core      │
│  - neupan_ros2 (已就绪)           │
│  - config/robots/mowen/ (新建)   │
│  - 订阅 /scan, /tf               │
│  - 发布 /neupan_cmd_vel          │
└──────────────────────────────────┘
```

### 5.2 实施步骤

#### Step 1: 创建 mowen 配置

在 NeuPAN 仓库（宿主机或 Docker 容器内）创建：

```bash
# neupan_ros2/src/neupan_ros2/config/robots/mowen/
mkdir -p models
```

**robot.yaml**:
```yaml
node:
  name: 'neupan_control'
  rate: 50                    # Hz
  scan_downsample: 1
  scan_range: [0.0, 25.0]
  scan_angle_range: [-3.14, 3.14]
  marker_size: 0.15
  marker_z: 0.5

frame:
  map: 'map'
  base: 'base_link'
  lidar: 'laser_link'         # 需确认 mowen 实际帧名

dune_checkpoint_file: 'models/model_1500.pth'
```

**planner.yaml** (参考 `config/robots/simulation/planner.yaml` 改 omni):
```yaml
robot:
  kinematics: 'omni'
  length: 1.6
  width: 2.0
  vel_max: 1.0
  acc_max: 1.0
  omega_max: 1.0
  alpha_max: 1.5
  wheelbase: 0.0              # omni 不需要
  ref_speed: 0.5
  safety_margin: 0.05

pan:
  nrmp_max_num: 1
  nrmp_max_iter: 100
  point_min_distance: 0.3
  receding: 8
  step_time: 0.2
  ref_path_batch: 5
  dune_max_num: 0
  dune_checkpoint: 'models/model_1500.pth'
```

**复制 DUNE 模型**:
```bash
cp example/mowen/model/mowen/model_1500.pth \
   src/neupan_ros2/config/robots/mowen/models/
```

#### Step 2: 创建 launch 文件

`neupan_ros2/src/neupan_ros2/launch/mowen.launch.py` (参考 `limo.launch.py`):

```python
from launch import LaunchDescription
from launch_ros.actions import Node
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.substitutions import FindPackageShare

def generate_launch_description():
    config_dir = PathJoinSubstitution([
        FindPackageShare('neupan_ros2'),
        'config', 'robots', 'mowen'
    ])
    
    return LaunchDescription([
        Node(
            package='neupan_ros2',
            executable='neupan_node.py',
            name='neupan_control',
            parameters=[
                PathJoinSubstitution([config_dir, 'robot.yaml']),
                PathJoinSubstitution([config_dir, 'planner.yaml']),
            ],
            remappings=[
                ('/neupan_cmd_vel', '/cmd_vel'),
                # 如果 LeiShen 是点云，加 pointcloud_to_laserscan
            ],
            output='screen',
        ),
    ])
```

#### Step 3: 配置 ros1_bridge

`ros1_bridge` 在两台机器之间双向转发：

**机器人端 (Ubuntu 18.04)** 启动 newznzc_ws:
```bash
roslaunch nav_demo nav04_amcl.launch
# 启动 LeiShen LiDAR
# 启动 EKF
# 启动 AMCL
# /scan, /tf, /map 都已发布
```

**桥接机 (Ubuntu 20.04 推荐) 或同台机器**:
```bash
# 安装 ros1_bridge
sudo apt install ros-noetic-ros1-bridge ros-humble-ros1-bridge

# 启动桥接
export ROS_MASTER_URI=http://<robot_ip>:11311  # 指向机器人
export ROS_IP=<robot_ip>
ros2 run ros1_bridge dynamic_bridge --bridge-all-topics
```

**NeuPAN 端 (Docker 容器)**:
```bash
# 容器启动时加 hosts
docker run --add-host=mowen_robot:<robot_ip> ...

# 容器内 source ROS2 + 启动 NeuPAN
./docker/container.sh ros2 setup
# 进去后
source /opt/ros/humble/setup.bash
source /root/neupan_ros2_ws/src/NeuPAN/neupan_ros2/install/setup.bash
export ROS_MASTER_URI=http://mowen_robot:11311
ros2 launch neupan_ros2 mowen.launch.py
```

### 5.3 Twist 消息适配

NeuPAN omni `forward()` 输出 `(vx, vy, 0)` 形式：

```python
# neupan/robot/robot.py linear_omni_model
# 控制 = [v_linear, theta_dir]
# forward() 后: action = [v*cos(theta), v*sin(theta), 0]  (3,1)
```

但 ROS Twist 只支持 `linear.x/y/z` 和 `angular.x/y/z`。修改 `neupan_node.py` 输出：

```python
# 在 publish_cmd_vel 之前
action = info['action']  # (2, 1) or (3, 1) for omni
twist.linear.x = float(action[0, 0])    # vx
twist.linear.y = float(action[1, 0])    # vy (omni 需要)
twist.angular.z = 0.0                   # omni 不需要 omega
self.cmd_vel_pub.publish(twist)
```

**需修改 `neupan_node.py`**：根据 `kinematics` 决定输出格式。

## 6. 环境问题

### 6.1 Docker 镜像（已完成）

- `docker/container.sh` + `ros2/setup.sh` 可一键创建 NeuPAN 容器
- 基础镜像：`ros:humble-ros-core`
- Python 3.10（自带）
- torch 2.8.0+cu128
- CUDA 12.8

### 6.2 网络通信

- mowen 机器人、桥接机、NeuPAN 推理机之间网络互通
- ROS_MASTER_URI 指向机器人端
- 防火墙：11311（ROS Master）、18888（mowen 底盘）

### 6.3 代理（仅构建时）

- 构建阶段需要代理：`export http_proxy=http://127.0.0.1:7897`
- 运行阶段不需要
- mowen 机器人一般无代理

### 6.4 依赖版本

| 依赖 | 版本 | 说明 |
|------|------|------|
| Python | 3.10 | 镜像自带 |
| torch | 2.8.0+cu128 | 需 RTX 30/40/50 系 |
| numpy | 1.26.4 | 必须，不能 ≥ 2.0 |
| scipy | ≤ 1.13.0 | 必须 |
| cvxpy | 1.7.5 | 已有训练模型配对 |
| cvxpylayers | 0.1.6 | 已有训练配对 |
| gctl | 1.2 | 必须，PIN 死 |

## 7. 测试方法

### 7.1 单元测试（已有）

```bash
cd /home/zq/resource/code/emb_ai/mobile_robot/path_planning/NeuPAN
conda activate neupan_py38  # 或 main 用 3.10
cd example
python run_exp.py -e corridor -d omni    # 仿真测试 omni 推理
python run_exp.py -e non_obs -d omni
```

### 7.2 集成测试

```bash
# 1. 启动 mowen 机器人（底盘 + LiDAR + AMCL）
# 2. 启动 ros1_bridge
# 3. 启动 NeuPAN 容器，验证：
ros2 topic list | grep scan        # 应有 /scan
ros2 topic list | grep cmd_vel     # 应有 /cmd_vel
ros2 run tf2_ros tf2_echo map base_link  # TF 正常
```

### 7.3 仿真测试（IR-Sim）

```bash
cd example
python run_exp.py -e corridor -d omni -a -n 500
# 看动画文件：neupan.gif 或 irsim_anim.mp4
```

### 7.4 实机测试步骤

1. **空地测试**：无障碍物，给 goal 看是否走直线
2. **静态障碍**：放箱子、墙，看能否绕开
3. **动态障碍**：让行人走动，看避障
4. **狭窄通道**：走廊、门口，看能否通过
5. **速度测试**：加速到 vel_max，看控制平滑
6. **长时间运行**：30 分钟，看稳定性

## 8. 风险点

| 风险 | 解决方案 |
|------|---------|
| **ros1_bridge 通信延迟** | 用 `cyclonedds` 配置 + 同网段 |
| **TF 漂移** | 保持 AMCL 持续运行，监控 /tf 频率 |
| **LiDAR 故障** | 监控 /scan 频率，异常时降速 |
| **DUNE 模型失配** | 先在 mowen 实际尺寸的场景跑仿真，验证规划稳定 |
| **Twist 消息丢失** | mowen 底盘用 last_command 缓存 |
| **omni 速度跳变** | `acc_max=1.0` 限加速度 |
| **坐标系不一致** | 全部用 `map → base_link` 单一 TF 链 |

## 9. 改造清单

| 项目 | 状态 | 优先级 |
|------|------|--------|
| 创建 `mowen/robot.yaml` | TODO | P0 |
| 创建 `mowen/planner.yaml` | TODO | P0 |
| 复制 DUNE 模型 | TODO | P0 |
| 创建 `mowen.launch.py` | TODO | P0 |
| 修改 `neupan_node.py` 支持 omni Twist | TODO | P1 |
| 配置 ros1_bridge | TODO | P1 |
| IR-Sim 仿真验证 | TODO | P1 |
| 空地实机测试 | TODO | P2 |
| 障碍物实机测试 | TODO | P2 |
| 长时间稳定性测试 | TODO | P3 |

## 10. 总结

1. **运动模型**: omni（mowen 底盘协议 + NeuPAN 已有训练模型）
2. **关键配置**: length=1.6, width=2.0（与训练一致）
3. **架构**: ros1_bridge 双栈，新代码在 NeuPAN 端
4. **环境**: Docker 容器（已就绪）+ ros1_bridge
5. **核心代码工作**: 创建 mowen 配置 + 修改 Twist 输出 + 配置桥接
6. **风险**: 通信延迟、TF 漂移、模型失配
