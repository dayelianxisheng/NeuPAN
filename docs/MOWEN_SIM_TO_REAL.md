# NeuPAN Sim-to-Real 部署方案

## 1. 两套系统现状

| | newznzc_ws (真机) | NeuPAN (规划器) |
|---|---|---|
| **位置** | `clone/newznzc_ws` | `.` |
| **ROS** | Melodic (Ubuntu 18.04) | Docker 容器 (Noetic) |
| **导航** | AMCL + DWA + move_base | DUNE + NRMP (端到端 MPC) |
| **输出** | `/cmd_vel` (Twist) | `/neupan_cmd_vel` → `/cmd_vel` |
| **机器人** | mowen (0.42m × 0.26m, omni 底盘) | 同左（已训练真实尺寸模型） |

## 2. 运动模型：omni

- **AMCL**: `odom_model_type: omni`
- **DWA**: `holonomic_robot: true`
- **底盘协议**: `newt.py` 发 `cmd_twist_x/y/rotation`（全向三自由度）
- **NeuPAN 模型**: `example/mowen/model/mowen_real/model_5000.pth`（0.42×0.26 真实尺寸）

## 3. 已完成的仿真验证

```bash
conda activate neupan
cd example/mowen
python train.py    # 训练真实尺寸模型（已完成）
python eval.py corridor  # 静态走廊场景 ✅
python eval.py non_obs    # 静态随机障碍 ✅
```

## 4. 真机部署步骤

### 4.1 已创建的真机配置文件

| 文件 | 位置 |
|------|------|
| 真机 planner | `example/mowen/envs/real/planner.yaml` |
| 真机 launch | `example/mowen/envs/real/mowen_real.launch` |

### 4.2 Step 1: 启动机器人端（newznzc_ws）

**无需修改任何 newznzc_ws 代码。**

在机器人电脑上：

```bash
# 启动定位 + LiDAR + EKF（不启动 move_base）
roslaunch nav_demo nav_c.launch

# 确认话题正常
rostopic list | grep scan    # 应有 /scan
rostopic list | grep cmd_vel # 应有 /cmd_vel
rostopic echo /scan -n 1     # 有数据

# 不启动 move_base（DWA），由 NeuPAN 替代
# 原命令：roslaunch nav_demo nav05_path_dwa.launch  # 不要运行这个！
```

**newznzc_ws 提供的接口（确认可用）：**

| 话题/服务 | 类型 | 状态 |
|-----------|------|------|
| `/scan` | LaserScan | Leishen N10 发布，frame_id=laser_link |
| TF: map→base_link | 通过 AMCL + EKF | ✅ |
| `/cmd_vel` | Twist | newt.py 订阅，发串口 |

### 4.3 Step 2: 启动 NeuPAN（Docker 容器）

```bash
# NeuPAN 电脑上
./docker/container.sh ros1 enter
```

容器内：

```bash
# 如果机器人和 NeuPAN 不同机器，设 ROS_MASTER_URI
export ROS_MASTER_URI=http://<机器人IP>:11311

# 启动 NeuPAN 真机 launch
roslaunch neupan_ros mowen_real.launch
# 注：mowen_real.launch 在 example/mowen/envs/real/ 下，
#     能通过 catkin 找到因为 neupan_ros/example 是 symlink
```

或者用绝对路径：
```bash
roslaunch /root/neupan_ws/src/NeuPAN/example/mowen/envs/real/mowen_real.launch
```

### 4.4 Step 3: 发布目标点

```bash
# 方式1：Rviz 中点击 "2D Nav Goal"
# 方式2：命令行
rostopic pub /move_base_simple/goal geometry_msgs/PoseStamped "
header: {frame_id: 'map'}
pose:
  position: {x: 2.0, y: 0.0, z: 0.0}
  orientation: {x: 0.0, y: 0.0, z: 0.0, w: 1.0}
"
```

### 4.5 参数调整

```yaml
# 真机优先保证安全：
max_speed: [0.5, 0.5]        # 慢速测试，稳定后逐步提高
collision_threshold: 0.15     # 碰撞安全距离
arrive_threshold: 0.5         # 到达容差
q_s: 1.0                      # 严格路径跟踪
scan_range: [0.05, 27.0]      # Leishen N10 参数
scan_downsample: 6            # 雷达点降采样
refresh_initial_path: true    # 允许动态更新目标
```

### 4.6 网络配置

mowen 机器人（Ubuntu 18.04）和 NeuPAN 电脑同一局域网。

**推荐：机器人运行 roscore，NeuPAN 容器连接：**

```bash
# 容器内（--net=host 自动共享宿主机网络）
export ROS_MASTER_URI=http://<机器人IP>:11311
```

## 5. 修改的代码清单

### 5.1 新创建的文件（NeuPAN 项目内）

```
example/mowen/envs/real/
├── planner.yaml              # 真机规划器配置
└── mowen_real.launch         # 真机启动文件
```

### 5.2 newznzc_ws 修改

**无需修改任何代码。** 只需不启动 move_base（`nav05_path_dwa.launch`）。

### 5.3 launch 文件核心参数

`mowen_real.launch` 的关键设置：

| 参数 | 值 | 说明 |
|------|-----|------|
| `config_file` | `envs/real/planner.yaml` | 真机规划配置 |
| `map_frame` | `map` | 与 AMCL 一致 |
| `base_frame` | `base_link` | 与 AMCL 一致 |
| `lidar_frame` | `laser_link` | 与 Leishen 一致 |
| `scan_range` | `0.05 27.0` | Leishen N10 量程 |
| `dune_checkpoint` | `model/mowen_real/model_5000.pth` | 训练模型 |
| `/scan` remap | **无** | 直接用 `/scan` |
| `/neupan_cmd_vel` remap | → `/cmd_vel` | 底盘接收 |
| `/neupan_goal` remap | → `/move_base_simple/goal` | RViz 交互 |

## 6. 测试步骤

### 6.1 连接测试（无动力）

```bash
# 1. 确认容器与机器人 ROS 互通
rostopic list | grep scan    # 应有 /scan
rostopic list | grep odom    # 应有 /odom

# 2. 确认 TF 正常
rosrun tf tf_echo map base_link  # 应有输出

# 3. 启动 NeuPAN，不接底盘
# 查看 /neupan_cmd_vel 输出
rostopic echo /neupan_cmd_vel
```

### 6.2 低速空地测试

```bash
# 参数：ref_speed=0.2, max_speed=[0.3, 0.3], q_s=1.0（严格路径跟踪）
roslaunch neupan_ros ...  # 用空地配置
rostopic pub /neupan_goal geometry_msgs/PoseStamped "header: {frame_id: 'map'}; pose: {position: {x: 1.0, y: 0.0}}"
```

### 6.3 避障测试

```bash
# 参数：ref_speed=0.3, max_speed=[0.5, 0.5], q_s=0.8（允许避障减速）
# 在机器人前方 1m 放纸箱
# 逐步提高速度
```

### 6.4 长时间运行

```bash
# 目标：30 分钟无碰撞
# 监控指标：min_distance > 0.2m, v_rate < 80%
```

## 7. 风险与对策

| 风险 | 对策 |
|------|------|
| 通信延迟 > 200ms | 用有线网络，降低 scan freqs |
| TF 漂移 | 监控 map→base_link 的跳跃 |
| LiDAR 盲区 (0.1m内) | 增大 `d_min`，急停阈值设低 |
| 模型失配（训练数据 vs 真机） | 先空地测试，再逐步加障碍 |
| 底盘不响应 | 串口 `/dev/carserial` 权限，115200bps |
| 急停不及时 | 监控 `/neupan_cmd_vel` 频率，miss > 3 帧急停 |

## 8. Docker 命令速查

```bash
./docker/container.sh ros1 setup    # 首次创建容器
./docker/container.sh ros1 enter    # 进入容器
./docker/container.sh ros1 stop     # 停止
./docker/container.sh ros1 status   # 状态
```

## 9. 关键文件位置

| 文件 | 路径 |
|------|------|
| 训练配置 | `example/mowen/envs/train.yaml` |
| 走廊场景 (planner) | `example/mowen/envs/corridor/planner.yaml` |
| 走廊场景 (env) | `example/mowen/envs/corridor/env.yaml` |
| 训练模型 | `example/mowen/model/mowen_real/model_5000.pth` |
| 测试脚本 | `example/mowen/eval.py` |
| newznzc_ws | `clone/newznzc_ws/src/` |
