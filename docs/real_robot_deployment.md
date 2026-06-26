# NeuPAN 真机部署完整指南

## 目录

- [1. 架构概览](#1-架构概览)
- [2. 系统依赖与环境准备](#2-系统依赖与环境准备)
- [3. 传感器对接](#3-传感器对接)
- [4. 定位系统对接](#4-定位系统对接)
- [5. 底盘驱动对接](#5-底盘驱动对接)
- [6. TF 树配置](#6-tf-树配置)
- [7. 机器人参数配置](#7-机器人参数配置)
- [8. DUNE 模型训练](#8-dune-模型训练)
- [9. Launch 文件编写](#9-launch-文件编写)
- [10. 调试与测试](#10-调试与测试)
- [11. 常见问题排查](#11-常见问题排查)

---

## 1. 架构概览

### 1.1 仿真 vs 真机数据流对比

```
仿真环境 (Gazebo):
┌─────────────┐     /scan (LaserScan)     ┌──────────────┐
│  Gazebo     │ ─────────────────────────→ │              │
│  虚拟激光雷达 │                           │  neupan_node │
└─────────────┘                           │              │
┌─────────────┐     tf (ground truth)     │              │
│  Gazebo     │ ─────────────────────────→ │              │
│  模型状态    │                           └──────┬───────┘
└─────────────┘                                  │
                                                 │ /neupan_cmd_vel
                                                 ▼
                                          ┌─────────────┐
                                          │  Gazebo     │
                                          │  模型控制器   │
                                          └─────────────┘

真机环境:
┌─────────────┐     /scan (LaserScan)     ┌──────────────┐
│  激光雷达驱动 │ ─────────────────────────→ │              │
│  rplidar等   │                           │  neupan_node │
└─────────────┘                           │              │
┌─────────────┐     tf (定位系统)          │              │
│  定位系统    │ ─────────────────────────→ │              │
│  AMCL/SLAM  │                           └──────┬───────┘
└─────────────┘                                  │
                                                 │ /neupan_cmd_vel
                                                 ▼
                                          ┌─────────────┐
                                          │  底盘驱动    │
                                          │  串口/CAN    │
                                          └─────────────┘
```

### 1.2 neupan_core.py 关键接口分析

```python
# 输入接口 (订阅)
/scan              → LaserScan    # 模拟: Gazebo, 真机: 实际雷达
tf (map→base_link) → Transform    # 模拟: Gazebo ground truth, 真机: 定位系统
/initial_path      → Path         # 可选: 外部路径规划器
/neupan_goal       → PoseStamped  # 目标点
/neupan_waypoints  → Path         # 路点

# 输出接口 (发布)
/neupan_cmd_vel    → Twist        # 速度命令 → 底盘驱动
/neupan_plan       → Path         # 规划路径 (可视化)
/neupan_ref_state  → Path         # 参考状态 (可视化)
```

---

## 2. 系统依赖与环境准备

### 2.1 软件依赖

```bash
# 基础依赖
- Ubuntu 20.04 / 22.04
- ROS Noetic / ROS2 Humble
- Python >= 3.10 (推荐 3.10)
- CUDA (可选, 仅 DUNE 训练需要)

# Python 包 (pyproject.toml 已锁定版本)
numpy==1.26.4
scipy==1.13.0
torch>=2.1.0
cvxpy==1.7.5
cvxpylayers==0.1.6
gctl==1.2
```

### 2.2 安装步骤

```bash
# 1. 安装 NeuPAN 核心库 (neupan_ros 依赖此 Python 包, 必须先安装)
cd /path/to/NeuPAN
pip install -e .

# 2. 安装 ROS wrapper (ROS1)
#    创建工作空间
mkdir -p ~/neupan_ws/src
cd ~/neupan_ws/src
ln -s /path/to/NeuPAN/neupan_ros .

#    安装 ROS 依赖
cd ~/neupan_ws
rosdep install --from-paths src --ignore-src -y

#    编译
catkin_make

#    将 workspace 环境加入 .bashrc
cd ~/neupan_ws/src/neupan_ros
sh source_setup.sh
source ~/neupan_ws/devel/setup.bash

# 或安装 ROS2 wrapper (需要在独立的 ROS2 工作空间中编译)
cd /path/to/NeuPAN/neupan_ros2
# 按照 neupan_ros2 内的说明编译
```

---

## 3. 传感器对接

### 3.1 激光雷达驱动

**需要做的**: 启动实际激光雷达驱动节点, 发布 `/scan` topic

常见激光雷达驱动包:

| 激光雷达型号 | ROS 包名 | 安装命令 |
|-------------|---------|---------|
| RPLidar A1/A2/A3 | `rplidar_ros` | `sudo apt install ros-noetic-rplidar-ros` |
| SICK TiM series | `sick_scan` | `sudo apt install ros-noetic-sick-scan` |
| Hokuyo URG | `hokuyo_node` | `sudo apt install ros-noetic-hokuyo-node` |
| Velodyne (3D) | `velodyne_pointcloud` | `sudo apt install ros-noetic-velodyne-pointcloud` |
| Livox (3D) | `livox_ros_driver2` | 从 GitHub 编译 |

### 3.2 关键参数确认

启动雷达驱动后, 用 `rostopic echo /scan` 确认:

```bash
# 检查 frame_id (必须与 lidar_frame 参数一致)
header:
  frame_id: "laser_link"    # ← 取决于实际雷达驱动, 有些雷达用 "laser" 或 "laser_frame",
                            #   需要与 neupan 参数 lidar_frame 匹配

# 检查数据范围
angle_min: -3.14            # 起始角度
angle_max: 3.14             # 结束角度
range_min: 0.05             # 最小测距范围
range_max: 10.0             # 最大测距范围
```

### 3.3 3D 雷达转 2D

如果使用 3D 雷达 (Velodyne, Livox), 需要投影到 2D:

```bash
# 方法1: 使用 pointcloud_to_laserscan 包
sudo apt install ros-noetic-pointcloud-to-laserscan

# launch 文件中添加:
<node pkg="pointcloud_to_laserscan" type="pointcloud_to_laserscan_node"
      name="pcd_to_scan">
    <remap from="cloud_in" to="/livox/pointcloud"/>
    <remap from="scan" to="/scan"/>
    <param name="target_frame" value="laser_link"/>
    <param name="min_height" value="-0.5"/>
    <param name="max_height" value="0.5"/>
</node>
```

### 3.4 neupan_node.py 中的激光雷达相关代码

```python
# neupan_core.py 第 103 行 - 订阅激光雷达
rospy.Subscriber("/scan", LaserScan, self.scan_callback)

# scan_callback 关键处理逻辑 (第 203-263 行):
def scan_callback(self, scan_msg):
    ranges = np.array(scan_msg.ranges)
    angles = np.linspace(scan_msg.angle_min, scan_msg.angle_max, len(ranges))

    # 下采样 + 距离过滤 + 角度过滤
    for i in range(len(ranges)):
        if (i % self.scan_downsample == 0
            and distance >= self.scan_range[0]
            and distance <= self.scan_range[1]
            and angle > self.scan_angle_range[0]
            and angle < self.scan_angle_range[1]):
            point = np.array([[distance * cos(angle)], [distance * sin(angle)]])
            points.append(point)

    # 转换到 map 坐标系
    (trans, rot) = self.listener.lookupTransform(self.map_frame, self.lidar_frame, ...)
    self.obstacle_points = rot_matrix @ point_array + trans_matrix
```

---

## 4. 定位系统对接

### 4.1 定位方案选择

| 方案 | 适用场景 | 优点 | 缺点 |
|------|---------|------|------|
| **AMCL** | 已有地图 | 成熟稳定 | 需要预先建图 |
| **Cartographer** | 未知环境, 需建图 | 实时建图+定位 | 计算资源消耗大 |
| **Hector SLAM** | 无里程计 | 不依赖里程计 | 平面运动假设 |
| **LOAM/LIO-SAM** | 3D 雷达 | 精度高 | 配置复杂 |
| **VINS-Fusion** | 视觉+IMU | 不依赖激光 | 光照敏感 |

### 4.2 AMCL 方案 (推荐新手)

```bash
# 1. 先建图 (使用 gmapping 或 cartographer)
roslaunch my_robot mapping.launch

# 2. 保存地图
rosrun map_server map_saver -f /path/to/map

# 3. 运行 AMCL 定位
roslaunch amcl amcl.launch map_file:=/path/to/map.yaml
```

### 4.3 neupan_node.py 中的定位相关代码

```python
# neupan_core.py 第 119-139 行 - 获取机器人状态
def run(self):
    while not rospy.is_shutdown():
        try:
            # 通过 tf 获取 map → base_link 变换
            (trans, rot) = self.listener.lookupTransform(
                self.map_frame, self.base_frame, rospy.Time(0)
            )
            yaw = self.quat_to_yaw_list(rot)
            x, y = trans[0], trans[1]
            self.robot_state = np.array([x, y, yaw]).reshape(3, 1)

        except (tf.LookupException, tf.ConnectivityException, tf.ExtrapolationException):
            rospy.loginfo_throttle(1, "waiting for tf ...")
            continue
```

**关键点**: 定位系统必须发布 `map → base_link` 的 tf 变换（或通过 `map → odom` + `odom → base_link` 链路拼接，tf 会自动解析完整变换链）。推荐标准结构：AMCL 发布 `map → odom`，底盘里程计发布 `odom → base_link`。

### 4.4 无地图部署（odom 帧模式）

对于不依赖全局地图的场景（如 mowen 小车），可直接用 `odom` 帧代替 `map`:

```xml
<param name="map_frame" value="odom"/>
```

此时 neupan 工作在 odom 坐标系下，无需 AMCL/map 定位。优点是部署简单，缺点是里程计漂移会导致长时间运动后定位不准。适用于巡逻、跟随等短距离任务。

> [!IMPORTANT]
> 使用 odom 帧模式时需要确保 TF 链路完整:
> ```
> odom → base_footprint → base_link → laser_link
> ```
> 其中 `base_footprint → base_link` 通常为 identity 变换，
> 通过 `static_transform_publisher 0 0 0 0 0 0 base_footprint base_link 100` 补充。

---

## 5. 底盘驱动对接

### 5.1 速度命令格式

neupan_node 发布 `geometry_msgs/Twist` 格式:

```python
# neupan_core.py 第 380-398 行
def generate_twist_msg(self, vel):
    speed = vel[0, 0]   # 线速度 / vx
    steer = vel[1, 0]   # 角速度 / vy (omni)

    action = Twist()

    if self.neupan_planner.robot.kinematics == 'omni':
        # omni: (vx, vy) → linear.x / linear.y
        action.linear.x = speed    # vx
        action.linear.y = steer   # vy
    else:
        # diff / acker: (linear, angular) → linear.x / angular.z
        action.linear.x = speed    # 线速度 (m/s)
        action.angular.z = steer   # 转向角速度 (rad/s)

    return action
```

### 5.2 底盘驱动对接方式

**方式 A: topic remap (推荐)**

如果底盘驱动订阅 `/cmd_vel`:

```xml
<!-- launch 文件中添加 remap -->
<remap from="/neupan_cmd_vel" to="/cmd_vel"/>
```

**方式 B: 编写 bridge 节点**

如果底盘使用自定义协议 (串口/CAN):

```python
#!/usr/bin/env python3
import rospy
from geometry_msgs.msg import Twist
import serial  # 或 python-can

class CmdVelBridge:
    def __init__(self):
        self.ser = serial.Serial('/dev/ttyUSB0', 115200)
        rospy.Subscriber('/neupan_cmd_vel', Twist, self.callback)

    def callback(self, msg):
        linear = msg.linear.x
        angular = msg.angular.z
        # 转换为底盘协议格式并发送
        cmd = f"VEL,{linear:.3f},{angular:.3f}\n"
        self.ser.write(cmd.encode())

if __name__ == '__main__':
    rospy.init_node('cmd_vel_bridge')
    bridge = CmdVelBridge()
    rospy.spin()
```

**方式 C: 直接修改 neupan_core.py**

```python
# 修改第 82 行的 topic 名称
self.vel_pub = rospy.Publisher("/cmd_vel", Twist, queue_size=10)
```

### 5.3 不同运动学的输出格式

| 运动学类型 | `vel[0,0]` | `vel[1,0]` | Twist 赋值 | 说明 |
|-----------|-----------|-----------|------------|------|
| `diff` | 线速度 (m/s) | 角速度 (rad/s) | `linear.x = vel[0]`, `angular.z = vel[1]` | 差速驱动 |
| `acker` | 线速度 (m/s) | 转向角 (rad) | `linear.x = vel[0]`, `angular.z = vel[1]` | 阿克曼 |
| `omni` | vx (m/s) | vy (m/s) | `linear.x = vx`, `linear.y = vy` | 全向 (内部先优化 (v_linear, theta) 再转为 (vx, vy)) |

> [!WARNING]
> **omni 的 Twist 输出与 diff/acker 不同！** `neupan_core.py` 的 `generate_twist_msg()` 需要根据 kinematics 做分支处理——omni 时 `vel[1,0]` 是 vy，应赋给 `linear.y` 而非 `angular.z`。

> [!NOTE]
> 真机部署时 `max_speed: [0.2, 0.5]` 中的角速度 `0.5 rad/s ≈ 29°/s` 对大部分地面机器人偏大。建议从 `[0.2, 0.3]` 开始调试，逐步增大。

---

## 6. TF 树配置

### 6.1 必需的 TF 树结构

```
map
 └── odom (由定位系统发布)
      └── base_link (由底盘里程计发布)
           └── laser_link (由 URDF 或 static_tf 发布)
```

### 6.2 检查 TF 树

```bash
# 查看完整 tf 树
rosrun tf view_frames
evince frames.pdf

# 检查特定变换
rosrun tf tf_echo map base_link
rosrun tf tf_echo base_link laser_link
```

### 6.3 neupan_node.py 中的 TF 使用

```python
# 机器人状态获取 (第 120 行)
self.listener.lookupTransform(self.map_frame, self.base_frame, ...)
# ↑ 需要 map → base_link 变换

# 激光点云转换 (第 239 行)
self.listener.lookupTransform(self.map_frame, self.lidar_frame, ...)
# ↑ 需要 map → laser_link 变换
```

### 6.4 常见 TF 配置

**方案 A: 标准 odom 结构**

```xml
<!-- 定位系统发布 map → odom -->
<!-- 底盘驱动发布 odom → base_link -->
<!-- 静态 tf 发布 base_link → laser_link -->

<node pkg="tf" type="static_transform_publisher"
      name="base_to_laser"
      args="0.1 0 0.2 0 0 0 base_link laser_link 100"/>
```

**方案 B: 直接 map → base_link**

如果定位系统直接发布 `map → base_link` (如 AMCL 配置):

```xml
<!-- neupan 参数设置 -->
<param name="map_frame" value="map"/>
<param name="base_frame" value="base_link"/>
```

**方案 C: base_footprint → base_link 桥接（mowen 小车）**

部分机器人使用 `base_footprint` 作为里程计坐标系。需要在 launch 中添加静态 TF:

```xml
<!-- 桥接 TF: base_footprint → base_link -->
<node pkg="tf" type="static_transform_publisher"
      name="footprint_to_base"
      args="0 0 0 0 0 0 base_footprint base_link 100"/>
```

然后在 neupan 参数中保持 `base_frame: base_link` 不变，TF 链 `odom → base_footprint → base_link` 会被自动解析。

### 6.5 Frame 参数配置

```yaml
# robot.yaml (ROS2) 或 launch 参数 (ROS1)
map_frame: "map"           # 地图坐标系
base_frame: "base_link"    # 机器人基座坐标系
lidar_frame: "laser_link"  # 激光雷达坐标系
```

---

## 7. 机器人参数配置

### 7.1 planner.yaml 关键参数

```yaml
# MPC 参数 (mowen omni 全向机器人真机参数)
receding: 5              # 预测步长, 越小反应越快
step_time: 0.3           # 控制周期 (s), 对应 ≈3Hz 求解频率
ref_speed: 0.15          # 参考速度 (m/s)
collision_threshold: 0.05    # 碰撞检测阈值 (m), 真机建议 0.05~0.1

# 机器人参数
robot:
  kinematics: 'omni'       # 运动学类型: diff/acker/omni
  max_speed: [0.2, 0.5]   # 最大速度 [线速度 (m/s), 角速度 (rad/s)]
  max_acce: [0.2, 0.5]    # 最大加速度
  length: 0.42             # 机器人长度 (m)
  width: 0.26              # 机器人宽度 (m)

# 避障参数
adjust:
  q_s: 0.3        # 状态跟踪权重, 越小路径跟踪越松
  p_u: 2.5        # 速度跟踪权重
  eta: 10.0       # 松弛变量权重
  d_max: 0.15     # 最大安全距离 (m)
  d_min: 0.01     # 最小安全距离 (m)
```
  eta: 15.0       # 松弛变量权重
  d_max: 0.1      # 最大安全距离 (m)
  d_min: 0.01     # 最小安全距离 (m)
  ro_obs: 400     # 避障惩罚系数
```

### 7.2 参数调优指南

| 参数 | 调大效果 | 调小效果 | 调试建议 |
|------|---------|---------|---------|
| `q_s` | 路径跟踪更紧, 但可能抖动 | 路径跟踪更松, 更平滑 | 从 0.5 开始 |
| `p_u` | 速度更稳定 | 速度变化更灵活 | 从 1.0 开始 |
| `d_max` | 离障碍物更远 | 可以靠近障碍物 | 根据安全需求 |
| `ro_obs` | 避障更激进 | 避障更保守 | 从 200 开始 |
| `receding` | 规划更远, 更平滑 | 反应更快, 计算量小 | 5-10 之间 |
| `step_time` | 更平滑, 但反应慢 | 反应快, 但可能抖动 | 匹配控制频率 |

> [!TIP]
> **`step_time` 与控制频率的关系:**
> `step_time` 是 MPC 优化内部的离散化步长（每个 receding step 代表的时间），而 NeuPAN 的求解发布频率由主循环决定（默认 50Hz）。两者是独立的概念。例如 `step_time=0.25` 表示一次 8-step 的 MPC 规划了未来 2 秒的运动，而控制频率 50Hz 意味着每 20ms 重新求解一次。一般保持 `step_time` 与实际机器人控制周期一致（通常 0.05~0.2s）。

### 7.3 ROS2 配置文件结构

```
config/robots/my_robot/
├── robot.yaml           # ROS 节点参数
├── planner.yaml         # NeuPAN 规划参数
└── models/
    └── dune_model_5000.pth  # DUNE 预训练模型
```

**robot.yaml 示例** (参数名可能与 ROS1 版不同, 以实际 `neupan_ros2` 代码为准):

```yaml
neupan_node:
  ros__parameters:
    robot_type: 'my_robot'
    robot_description: 'My differential drive robot'

    planner_config_file: 'planner.yaml'
    dune_checkpoint_file: 'models/dune_model_5000.pth'

    map_frame: 'map'
    base_frame: 'base_link'
    lidar_frame: 'laser_link'

    scan_angle_max: 3.14
    scan_angle_min: -3.14
    scan_downsample: 2
    scan_range_max: 5.0
    scan_range_min: 0.1

    control_frequency: 20.0
    refresh_initial_path: true
```

---

## 8. DUNE 模型训练

### 8.1 何时需要重新训练

- ✅ 机器人尺寸与预训练模型不同
- ✅ 机器人形状不同 (如从圆形改为矩形)
- ❌ 更换激光雷达 (不需要)
- ❌ 更换场景 (不需要)

### 8.2 训练步骤

```bash
cd /path/to/NeuPAN/example/dune_train

# 1. 修改 dune_train.yaml 中的机器人参数
robot:
  kinematics: 'diff'
  length: 0.4      # ← 改为实际尺寸
  width: 0.3       # ← 改为实际尺寸

train:
  data_range: [-10, -10, 10, 10]  # 根据雷达范围调整

# 2. 运行训练
python train_dune.py

# 3. 训练完成后, 将模型复制到配置目录
cp model/my_robot/model_5000.pth /path/to/config/models/
```

### 8.3 训练参数说明

```yaml
train:
  data_size: 100000          # 训练数据量
  data_range: [-25,-25,25,25] # 障碍物生成范围 [x_min, y_min, x_max, y_max]
  batch_size: 256
  epoch: 5000
  lr: 5e-5                   # 学习率
  save_freq: 500             # 每 N epoch 保存一次
```

---

## 9. Launch 文件编写

### 9.1 ROS1 完整 Launch 文件示例

```xml
<!-- neupan_real_robot.launch -->
<launch>
    <!-- ========== 参数配置 ========== -->
    <arg name="config_file"
         default="$(find neupan_ros)/config/my_robot/planner.yaml"/>
    <arg name="dune_checkpoint"
         default="$(find neupan_ros)/config/my_robot/models/dune_model_5000.pth"/>

    <!-- TF Frame 配置 -->
    <arg name="map_frame" default="map"/>
    <arg name="base_frame" default="base_link"/>
    <arg name="lidar_frame" default="laser_link"/>

    <!-- 激光雷达参数 -->
    <arg name="scan_topic" default="/scan"/>
    <arg name="scan_range" default="0.1 5.0"/>
    <arg name="scan_angle_range" default="-3.14 3.14"/>
    <arg name="scan_downsample" default="2"/>

    <!-- 控制参数 -->
    <arg name="refresh_initial_path" default="true"/>

    <!-- ========== 激光雷达驱动 ========== -->
    <!-- 根据实际雷达型号修改 -->
    <include file="$(find rplidar_ros)/launch/rplidar_a2.launch"/>

    <!-- ========== 定位系统 ========== -->
    <!-- 方案1: AMCL (需要预先建图) -->
    <include file="$(find amcl)/launch/amcl.launch">
        <arg name="map_file" value="$(find my_robot)/maps/map.yaml"/>
    </include>

    <!-- 方案2: Cartographer (实时建图) -->
    <!-- <include file="$(find my_robot)/launch/cartographer.launch"/> -->

    <!-- ========== 底盘驱动 ========== -->
    <include file="$(find my_robot)/launch/base_driver.launch"/>

    <!-- ========== static TF ========== -->
    <!-- base_link → laser_link -->
    <node pkg="tf" type="static_transform_publisher"
          name="base_to_laser"
          args="0.1 0 0.2 0 0 0 base_link laser_link 100"/>

    <!-- ========== NeuPAN 节点 ========== -->
    <node name='neupan_control' pkg="neupan_ros" type="neupan_node.py" output="screen">
        <!-- 配置文件 -->
        <param name="config_file" value="$(arg config_file)"/>
        <param name="dune_checkpoint" value="$(arg dune_checkpoint)"/>

        <!-- Frame 配置 -->
        <param name="map_frame" value="$(arg map_frame)"/>
        <param name="base_frame" value="$(arg base_frame)"/>
        <param name="lidar_frame" value="$(arg lidar_frame)"/>

        <!-- 激光雷达参数 -->
        <param name="scan_range" value="$(arg scan_range)"/>
        <param name="scan_angle_range" value="$(arg scan_angle_range)"/>
        <param name="scan_downsample" value="$(arg scan_downsample)"/>
        <param name="refresh_initial_path" value="$(arg refresh_initial_path)"/>

        <!-- Topic remap -->
        <remap from="/scan" to="$(arg scan_topic)"/>
        <remap from="/neupan_cmd_vel" to="/cmd_vel"/>
        <remap from="/neupan_goal" to="/move_base_simple/goal"/>
    </node>

    <!-- ========== RViz (可选) ========== -->
    <node name="rviz" pkg="rviz" type="rviz"
          args="-d $(find neupan_ros)/rviz/neupan_real.rviz"/>
</launch>
```

### 9.2 ROS2 Launch 文件示例

```python
# neupan_real_robot.launch.py
import os
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription, DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory

def generate_launch_description():
    # 配置路径
    robot_config_dir = os.path.join(
        get_package_share_directory('neupan_ros2'),
        'config', 'robots', 'my_robot'
    )
    robot_config = os.path.join(robot_config_dir, 'robot.yaml')

    # 激光雷达驱动
    rplidar_launch = IncludeLaunchDescription(
        os.path.join(
            get_package_share_directory('rplidar_ros'),
            'launch', 'rplidar_a2.launch.py'
        )
    )

    # 定位系统
    # amcl_launch = IncludeLaunchDescription(...)

    # static TF
    static_tf = Node(
        package='tf2_ros',
        executable='static_transform_publisher',
        name='base_to_laser',
        arguments=['0.1', '0', '0.2', '0', '0', '0', 'base_link', 'laser_link']
    )

    # NeuPAN 节点
    neupan_node = Node(
        package='neupan_ros2',
        executable='neupan_node',
        name='neupan_node',
        output='screen',
        parameters=[
            robot_config,
            {'robot_config_dir': robot_config_dir}
        ],
        remappings=[
            ('/neupan_cmd_vel', '/cmd_vel'),
        ]
    )

    return LaunchDescription([
        rplidar_launch,
        static_tf,
        neupan_node,
    ])
```

---

## 10. 调试与测试

### 10.1 分步调试流程

```bash
# Step 1: 检查激光雷达
rostopic echo /scan | head -20
# 应该看到 range 数据

# Step 2: 检查 TF 树
rosrun tf tf_echo map base_link
# 应该看到位置和姿态

# Step 3: 检查 TF 树完整性
rosrun tf view_frames
# 确保 map → odom → base_link → laser_link 链路完整

# Step 4: 启动 NeuPAN (仅路径跟踪, 无避障)
# 临时设置 planner.yaml 中 dune_max_num: 0 和 nrmp_max_num: 0
# 注意: 即使关闭避障, 仍需要激光雷达扫描到障碍点(或让算法走 fallback)
#       代码中当 obstacle_points 为空时会填充 (100,100) 虚拟点
roslaunch neupan_ros neupan_real_robot.launch

# Step 5: 发送目标点 (--once 表示发送一次后退出)
rostopic pub --once /move_base_simple/goal geometry_msgs/PoseStamped \
  "header: {frame_id: 'map'}
pose:
  position: {x: 1.0, y: 0.0, z: 0.0}
  orientation: {x: 0.0, y: 0.0, z: 0.0, w: 1.0}"

# Step 6: 检查速度输出
rostopic echo /neupan_cmd_vel
```

### 10.2 RViz 可视化

```bash
# 添加以下 topic 进行可视化:
# - /neupan_plan (规划路径, 绿色)
# - /neupan_initial_path (初始路径, 蓝色)
# - /neupan_ref_state (参考状态, 红色)
# - /dune_point_markers (DUNE 障碍点, 紫色)
# - /nrmp_point_markers (NRMP 障碍点, 橙色)
# - /robot_marker (机器人轮廓, 绿色)
```

### 10.3 性能监控

```bash
# 查看 NeuPAN 计算时间 (需在 planner.yaml 中设置 time_print: True)
# 打开后会在运行 NeuPAN 的终端打印类似:
# "neupan forward execute time 0.023 seconds"
# 推荐控制频率 >= 10Hz (即 forward 耗时 < 0.1s)

# 查看 CPU 使用
top -p $(pgrep -f neupan_node)
```

---

## 11. 常见问题排查

### 11.1 "waiting for tf"

**原因**: 定位系统没有发布正确的 tf 变换

**排查**:
```bash
# 检查 tf 是否存在
rosrun tf tf_echo map base_link

# 检查 frame 名称是否匹配
rosparam get /neupan_control/map_frame
rosparam get /neupan_control/base_frame
```

**解决**:
1. 确保定位系统已启动
2. 确保 frame 名称一致
3. 检查 tf 树是否连通

### 11.2 "No obstacle points"

**原因**: 激光雷达数据未到达或过滤太严格

**排查**:
```bash
# 检查激光雷达 topic
rostopic hz /scan

# 检查数据范围
rostopic echo /scan | grep "range_min\|range_max"
```

**解决**:
1. 检查激光雷达驱动是否启动
2. 调整 `scan_range` 参数 (增大 range_max)
3. 调整 `scan_downsample` 参数 (减小下采样)

### 11.3 机器人不动

**原因**: 速度命令未到底盘驱动

**排查**:
```bash
# 检查速度命令是否发布
rostopic echo /neupan_cmd_vel

# 检查 topic remap
rosnode info /neupan_control
```

**解决**:
1. 检查 topic remap 是否正确
2. 检查底盘驱动是否订阅正确的 topic
3. 检查底盘驱动是否正常工作

### 11.4 机器人抖动

**原因**: 参数不合适或控制频率不匹配

**解决**:
1. 增大 `step_time` (如 0.1 → 0.2)
2. 减小 `q_s` (如 1.0 → 0.5)
3. 增大 `receding` (如 5 → 8)
4. 确保 `step_time` 与实际控制频率匹配

### 11.5 避障效果差

**原因**: DUNE 模型不匹配或参数不合适

**解决**:
1. 检查 DUNE 模型是否与机器人尺寸匹配
2. 增大 `ro_obs` (如 200 → 400)
3. 增大 `d_max` (如 0.1 → 0.2)
4. 减小 `nrmp_max_num` (减少计算量, 提高实时性)

---

## 附录 A: 快速检查清单

- [ ] 激光雷达驱动已启动, `/scan` topic 有数据
- [ ] 定位系统已启动, `map → base_link` tf 变换存在
- [ ] `base_link → laser_link` static tf 已配置
- [ ] `planner.yaml` 中机器人参数与实际一致
- [ ] DUNE 模型与机器人尺寸匹配
- [ ] `map_frame`, `base_frame`, `lidar_frame` 参数与实际 frame 一致
- [ ] `/neupan_cmd_vel` 已 remap 到底盘驱动订阅的 topic
- [ ] 底盘驱动已启动并正常工作

## 附录 B: 推荐测试流程

1. **空旷场地测试**: 先在无障碍物环境测试路径跟踪
2. **简单避障测试**: 放置单个障碍物测试避障
3. **复杂场景测试**: 在有多个障碍物的环境测试
4. **动态避障测试**: 有移动障碍物的环境测试
5. **长时间运行测试**: 连续运行 30 分钟以上测试稳定性

## 附录 C: 性能优化建议

1. **降低计算量**:
   - 减小 `receding` (如 10 → 5)
   - 减小 `nrmp_max_num` (如 10 → 5)
   - 增大 `scan_downsample` (如 1 → 3)

2. **提高避障性能**:
   - 增大 `dune_max_num` (如 100 → 200, 取决于雷达点云密度, 超过实际点数则无提升)
   - 增大 `iter_num` (如 2 → 3)

3. **CPU 优化**:
   - 确保使用 CPU 运行 (cvxpy 不支持 GPU)
   - 使用多核 CPU (推荐 Intel i7 或更高)
