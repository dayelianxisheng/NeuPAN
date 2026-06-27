# NeuPAN 真机部署流程

> 目标机器人: 镭神 N10 激光雷达 + WitMotion IMU + **全向(omni)底盘**  
> ROS 版本: Melodic  
> 参考工作空间: `newznzc_ws` (副本路径: `/home/zq/resource/code/emb_ai/mobile_robot/clone/newznzc_ws`)  
> 真实小车代码运行在小车自带 Ubuntu 系统中

---

## 核心原则

> **任何场景测试都不得修改小车内部已有代码。**  
> 如需增加功能，只能以新增 ROS 包或独立脚本的方式，`scp` 到小车后再叠加运行。

| 类别 | 功能包 | 可否修改 |
|------|--------|---------|
| 小车已有自定义包 | `car_bringup`, `mbot_bringup`, `nav_demo`, `grab`, `wit` | ❌ 不可修改 |
| 小车已有第三方包 | `leishen`, `ydlidar_ros_driver`, `mycobot_ros`, `imu_tools`, `rf2o_laser_odometry`, `slam_karto` 等 | ❌ 不可修改 |
| NeuPAN 自身 | `neupan/`, `neupan_ros/` | ✅ 可自由修改 |
| 新增部署代码 | `neupan_deploy/` (新增 ROS 包) | ✅ 可自由添加 |

所有部署相关的启动文件、脚本、配置，建议集中放在一个新增的 `neupan_deploy/` 包中，`scp` 到小车后 `catkin_make`。

## NeuPAN 依赖 vs 小车已有能力

| 小车已有功能 | NeuPAN 是否需要 | 说明 |
|-------------|----------------|------|
| 镭神激光雷达 → `/scan` | ✅ **必需** | 障碍物感知 |
| `odom → base_link` TF | ✅ **必需** | 获取机器人位姿 |
| `newt.py` 串口底盘控制 | ✅ **必需** | 执行 `/cmd_vel` |
| 轮式里程计 (pubv.py + base_node) | ✅ 建议开启 | 提供 odom TF |
| EKF 融合 (robot_localization) | ✅ 建议开启 | 平滑里程计, 减少漂移 |
| WitMotion IMU | ⚠️ 可选 | 增强定位, 无亦可 |
| gmapping 建图 | ❌ **不用** | NeuPAN 无地图 |
| AMCL 定位 | ❌ **不用** | NeuPAN 用 odom 帧 |
| move_base/DWA 规划 | ❌ **不用** | NeuPAN 自带规划 |
| Orbbec 深度相机 | ❌ **不用** | 雷达已够 |
| 机械臂 myCobot | ❌ **不用** | |

---

- [阶段零: 前置检测 — 小车自身功能确认](#阶段零-前置检测--小车自身功能确认)
- [阶段一: Docker 直线行走测试](#阶段一-docker-直线行走测试)
- [阶段二: Docker 避障测试](#阶段二-docker-避障测试)
- [阶段三: 实车部署](#阶段三-实车部署)
- [附录 A: 新增包 neupan_deploy 结构](#附录-a-新增包-neupan_deploy-结构)
- [附录 B: 快速 scp 命令](#附录-b-快速-scp-命令)
- [附录 C: 完整检测清单](#附录-c-完整检测清单)

---

## 阶段零: 前置检测 — 小车自身功能确认

> 目标: 确认小车现有功能正常，不涉及 NeuPAN。  
> **只使用小车已有的包，不新增任何代码。**

### 0.1 激光雷达 — 镭神 N10

```bash
# 小车端执行:
roslaunch lslidar_driver lslidar_serial.launch

# 检查话题
rostopic hz /scan
# 期望: 5~15 Hz 稳定输出

rostopic echo /scan --noarr -n 1
# 期望:
#   header.frame_id: "laser_link"
#   angle_min: -3.14, angle_max: 3.14
#   range_min: 0.15, range_max: 100.0
#   ranges: [...]    ← 有有效数据, 非全 inf
```

### 0.2 轮式里程计

```bash
# 串口读取编码器 (小车已有包 car_bringup)
rosrun car_bringup pubv.py

# 检查原始轮速
rostopic echo /vel_raw --noarr -n 5
# 期望: linear.x / linear.y / angular.z 随推动小车变化

# 里程计积分节点
rosrun car_bringup base_node
# 订阅 /sub_vel → 发布 /odom_raw

rostopic echo /odom_raw -n 1
# 期望: pose + twist 有数据
```

### 0.3 底盘控制测试

> **❗ omni 全向底盘需要测试全部三个自由度**

```bash
# 启动底盘串口控制 (小车已有包)
rosrun car_bringup newt.py

# 逐项测试:
rostopic pub -1 /cmd_vel geometry_msgs/Twist \
  "{linear: {x: 0.1, y: 0.0, z: 0.0}, angular: {x: 0.0, y: 0.0, z: 0.0}}"
# 期望: 前进 0.1 m/s

rostopic pub -1 /cmd_vel geometry_msgs/Twist \
  "{linear: {x: 0.0, y: 0.1, z: 0.0}, angular: {x: 0.0, y: 0.0, z: 0.0}}"
# 期望: 横向左移 0.1 m/s

rostopic pub -1 /cmd_vel geometry_msgs/Twist \
  "{linear: {x: 0.0, y: 0.0, z: 0.0}, angular: {x: 0.0, y: 0.0, z: 0.3}}"
# 期望: 原地旋转
```

### 0.4 TF 树完整性

```bash
rosrun tf view_frames
evince frames.pdf
```

**期望 TF 树:**
```
odom
  └── base_footprint   (由小车已有节点发布)
        └── base_link   (若不存在, 需新增 static TF)
              └── laser_link  (由 lslidar 发布)
```

> **🚩 注意**: 
> - 如果 `base_footprint → base_link` 不存在，neupan_node 将无法获取机器人位置
> - 如果 EKF 参数有问题(小车 `robot_localization` launch 中 `initial_estimate_covariance` 使用字符串格式 `'1e-9'`)，EKF 不输出 odom TF
> - 绕方案: 使用 `docs/scripts/odom_tf_broadcaster.py`, 直接订阅 `/odom_raw` 广播 odom → base_footprint

### ✅ 前置检测通过标准

- [ ] `/scan` 话题 Hz ≥ 5Hz, frame_id = "laser_link"
- [ ] `/vel_raw` 编码器读数随运动变化
- [ ] `/odom_raw` 里程计积分正常
- [ ] 前进/横移/旋转 三个方向底盘控制正常
- [ ] `odom → base_footprint` TF 存在 (若无, 用 `odom_tf_broadcaster.py`)
- [ ] `base_link → laser_link` TF 存在
- [ ] `base_footprint → base_link` TF 存在 (若无, 加 static TF)
- [ ] 全零指令能停止小车

### 参考: 小车已有功能 (不与 NeuPAN 相关)

小车原生支持建图和导航，NeuPAN **不使用**这些已有功能（只使用传感器和底盘控制），但了解它们有助于排查基础问题。

#### 原生建图 (gmapping)

```bash
# 终端 1: 底盘串口
rosrun car_bringup newt.py

# 终端 2: 键盘控制
rosrun mbot_teleop mbot_teleop.py

# 终端 3: 启动建图 (雷达 + rf2o + EKF + gmapping)
roslaunch car_bringup gmapping.launch

# 终端 4: 保存地图
roslaunch nav_demo nav02_map_save.launch
# 地图保存在 ~/newznzc_ws/src/nav_demo/map/mymap.yaml
```

#### 原生导航 (AMCL + move_base + DWA)

```bash
# 终端 1: 底盘
rosrun car_bringup newt.py

# 终端 2: 导航 (地图 + AMCL + DWA)
roslaunch nav_demo nav777.launch
```

> **NeuPAN 与原生导航的区别:**
> - 原生导航依赖**预先建图** (gmapping) + **地图定位** (AMCL) + **路径规划** (move_base/DWA)
> - NeuPAN **不需要地图**, 直接处理激光雷达点云, 端到端输出控制指令
> - NeuPAN 只依赖: `/scan` + `TF (odom → base_link)` → 输出 `/cmd_vel`

#### Orbbec 深度相机

```bash
cd ~/newznzc_ws/src/OrbbecSDK_ROS/launch
roslaunch dabai_dcw2.launch
rqt_image_view
```

> 深度相机在 NeuPAN 部署中**非必需**。

---

## 阶段一: Docker 直线行走测试

> 目标: **本地 Docker** 运行 NeuPAN，通过 ROS 网络连接到小车，验证实时性。  
> **小车端已有代码不变。NeuPAN 全部在本地 Docker 中运行。**

> ⚠️ **网络架构变更说明**  
> 早期方案将 Docker 镜像传到小车运行，但小车无 GPU，且 7.9GB 镜像 scp 传输耗时。  
> 当前方案：**本地开发机跑 Docker + ROS 网络连接小车**，更轻量、便于调试。

### 1.1 架构

```
┌─ 本地开发机 (10.42.0.x) ────────────────────────────┐
│  Docker 容器 (ros:noetic-ros-core)                   │
│    neupan_ros (neupan_node)                          │
│      → ROS_MASTER_URI=http://10.42.0.169:11311       │
│      → 订阅 /scan (从小车)                           │
│      → 查询 TF (odom → base_link)                    │
│      → 发布 /neupan_cmd_vel → /cmd_vel (到小车)      │
└────────────────────────┬────────────────────────────┘
                         │ ROS network (ROS_MASTER_URI)
                         │ 小车端 roscore 在 10.42.0.169
┌─ 小车 (mowen, 10.42.0.169) ─────────────────────────┐
│  已有包 (不修改):                                    │
│    roscore                      ← ROS master         │
│    lslidar_driver  → /scan                          │
│    car_bringup (pubv.py + base_node) → /odom_raw    │
│    car_bringup (newt.py) ← /cmd_vel                 │
│                                                     │
│  新增 (运行 odom_tf_broadcaster.py 或 static TF):   │
│    odom → base_footprint TF                         │
│    static: base_footprint → base_link               │
└──────────────────────────────────────────────────────┘
```

### 1.2 前置检查清单

**开始之前，确认小车端三组件正常：**

```bash
# 登录小车
ssh mowen@10.42.0.169

# 1. 检查 roscore
echo $ROS_MASTER_URI
# 期望: http://10.42.0.169:11311

# 2. 检查网络连通 (在本地开发机)
ping 10.42.0.169
# 期望: 低延迟, 无丢包
```

### 1.3 ⚡ 卡顿前置检测 (关键!)

> **必须执行此步骤**。`newt.py` + `/cmd_vel` 发布者同时运行可能触发 MCU 卡顿模式（Bug #12）。

```bash
# 小车端终端 1: 先启动 newt.py
rosrun car_bringup newt.py
# 观察输出是否稳定, 无异常抖动

# 小车端终端 2: 50Hz 发零速测试 10 秒
# 如果卡顿, 杀掉 newt.py 就会恢复 (无需 reboot)
rostopic pub -r 50 /cmd_vel geometry_msgs/Twist "{}" &
sleep 10
kill %1

# 期间观察小车遥控器:
# ✅ 正常: 遥控器控制流畅
# ❌ 卡顿: 杀掉 newt.py 重启, 检查是否有其他进程占用 /dev/carserial

# 如果正常, 继续下一步
```

**卡顿对照表:**

| 现象 | 原因 | 处理 |
|------|------|------|
| newt.py + 任何 `/cmd_vel` → 卡顿 | Bug #12 | `pkill -f newt.py` → 遥控器自动恢复 |
| 单帧 pub (-1) 正常, 高频 → 卡顿 | 发布频率 < 20Hz 触发退化 | 保持 50Hz |
| 串口报错 "multiple access" | 多个进程占用 `/dev/carserial` | `sudo fuser -k /dev/carserial` |
| 遥控器正常, 但代码控制速度偏低 | Bug #13 (速度 ×0.47) | 不影响闭环, 跳过 |

### 1.4 小车端启动

```bash
# ——— 终端 A: 激光雷达 ———
roslaunch lslidar_driver lslidar_serial.launch

# ——— 终端 B: 轮速读取 + 里程计积分 ———
rosrun car_bringup pubv.py
rosrun car_bringup base_node

# ——— 终端 C: EKF 或 odom_tf_broadcaster (二选一) ———

# 方案 1: odom_tf_broadcaster.py (推荐, 绕过 EKF bug)
# 将此文件 scp 到小车:
#   scp docs/scripts/odom_tf_broadcaster.py mowen@10.42.0.169:~/newznzc_ws/src/car_bringup/scripts/
# 在小车上:
python /path/to/odom_tf_broadcaster.py   # 必须用 python2!

# 方案 2: 若 EKF 正常, 启动 EKF
# roslaunch robot_localization ekf_localization_node ...

# ——— 终端 D: 底盘串口 (已启动, 见 1.3) ———
rosrun car_bringup newt.py

# ——— 终端 E: 静态 TF bridge ———
# 如果 base_footprint → base_link 缺失 (参考 0.4 检查):
rosrun tf static_transform_publisher 0 0 0 0 0 0 base_footprint base_link 100
```

> 只有终端 E 和 `odom_tf_broadcaster.py` 是新增操作, 不修改小车已有包。

### 1.5 本地 Docker 启动

```bash
# ——— 本地开发机 ———

# 构建 Docker (仅首次)
./docker/container.sh ros1 setup

# 启动容器
./docker/container.sh ros1 start

# 容器内: 配置 ROS 网络环境 (关键!)
# 先查看本地 IP
ip addr show | grep 10.42

export ROS_MASTER_URI=http://10.42.0.169:11311
export ROS_IP=10.42.0.xxx    # ← 填入你本地的 10.42.x.x IP
# 验证:
rostopic list
# 期望: 看到小车端的 /scan, /odom, /tf 等话题

# 安装 neupan (容器内首次或代码变更后)
pip install -e /root/neupan_ws/src/NeuPAN

# 启动 neupan_node
roslaunch neupan_ros neupan_node.launch \
  config_file:=/root/neupan_ws/src/NeuPAN/example/mowen/deploy/planner.yaml \
  map_frame:=odom \
  base_frame:=base_link \
  lidar_frame:=laser_link \
  scan_downsample:=6 \
  scan_range:="0.5 27.0" \
  dune_checkpoint:=/root/neupan_ws/src/NeuPAN/example/mowen/model/mowen_real/model_5000.pth
```

> **如果 `rostopic list` 看不到小车话题**, 检查:
> 1. 小车端 `ROS_HOSTNAME=10.42.0.169` 是否设置 (Bug #2)
> 2. 本地 ROS_IP 是否正确 (用 `ip addr` 确认, 不要用 localhost)

### 1.6 waypoints 校准

> **启动后先查看 odom 位置, 再调整 waypoints 起点** (避免 Bug #5: 零长度路径触发立即到达)

```bash
# 容器内: 查看小车当前位置
rostopic echo /odom -n 1
# 记录 position.x 和 position.y 值

# 根据实际位置修改 waypoints
# 例如小车在 (0.05, -0.02), waypoints 应设为:
#   waypoints: [[0.05, -0.02, 0], [1.0, 0, 0]]
# 编辑文件 (在本地, 挂载后容器内可见):
#   example/mowen/deploy/planner.yaml
```

> 也可以用 ROS 参数覆盖: 部分版本支持 `initial_path` 话题刷新。
> 详见 `CLAUDE.md` 中 `update_initial_path_from_waypoints()` API。

### 1.7 发送目标

```bash
# 容器内或小车端, 发送直线目标 (odom 帧)
rostopic pub --once /move_base_simple/goal geometry_msgs/PoseStamped \
  "header: {frame_id: 'odom'}
pose:
  position: {x: 1.0, y: 0.0, z: 0.0}
  orientation: {x: 0.0, y: 0.0, z: 0.0, w: 1.0}"
```

### 1.8 实时性检测

```bash
# 容器内: 查看 forward 耗时
# planner.yaml 已设 time_print: True
# 期望: < 0.1s (仿真约 18ms)

# 查看控制指令频率
rostopic hz /neupan_cmd_vel
# 期望: ~3-5Hz (receding=5, step_time=0.3 → 1/0.3 ≈ 3.3Hz)

# 查看小车运动
# 期望: 从起点平滑走到 (1, 0) 附近, 日志打印 "arrive at the target"
# 如果未动: 检查 newt.py 是否有输出, /cmd_vel 是否有数据
rostopic echo /cmd_vel -n 3
```

### ✅ 阶段一通过标准

- [ ] 本地 Docker 与小车 ROS 网络通信正常 (`rostopic list` 能看到小车话题)
- [ ] 无 MCU 卡顿 (newt.py 稳定运行, 遥控器正常)
- [ ] `forward` 耗时 < 0.1s
- [ ] 小车沿直线到达目标点
- [ ] 无抖动、无停顿

---

## 阶段二: Docker 避障测试

> 目标: 在直线上放障碍物，验证 NeuPAN 避障。  
> **全部代码仍在 Docker 中运行，小车端不变。**

### 2.1 场地准备

```
       起点 (0, 0)      障碍物 (0.6, 0)      目标 (1.5, 0)
          ● ──────→     ┃ 纸箱/锥桶       ──────→  ●
                        ┃
      ──────────────────┻──────────────────────────
                        障碍物在直线路径上
```

### 2.2 发送目标

```bash
rostopic pub --once /move_base_simple/goal geometry_msgs/PoseStamped \
  "header: {frame_id: 'odom'}
pose:
  position: {x: 1.5, y: 0.0, z: 0.0}
  orientation: {x: 0.0, y: 0.0, z: 0.0, w: 1.0}"
```

### 2.3 观察与调参

```bash
# 在 RViz 中可视化
# /dune_point_markers (紫色) — DUNE 检测到的障碍点
# /nrmp_point_markers (橙色) — NRMP 选中的关键点

# 检查最小距离 (容器日志中)
# "neupan stop with the min distance 0.xx"
```

避障表现不佳时，修改本地的 `planner.yaml` 的 `adjust` 节，重新 scp 到容器挂载目录即可，无需重启容器。

### ✅ 阶段二通过标准

- [ ] 小车检测到障碍物 (DUNE 点显示)
- [ ] 小车平稳避开障碍物
- [ ] 绕过障碍后回到路径
- [ ] 到达目标点
- [ ] 无碰撞 (min_distance > threshold)

---

## 阶段三: 实车部署

> 目标: 去掉 Docker，直接在工控机上运行 NeuPAN，消除网络延迟。  
> **小车已有包仍不修改，新增独立的 ROS 包 `neupan_deploy`。**

### 3.1 准备新增包

在本地创建 `neupan_deploy/` 包结构（详见附录 A），包含：
- `neupan_real.launch` — 启动所有小车端已有节点 + neupan_node
- `planner_real.yaml` — NeuPAN 参数（复制自 `example/mowen/deploy/planner.yaml`）
- `check_sensors.py` — 传感器状态检测脚本

### 3.2 scp 到小车

```bash
# 将 NeuPAN 源码和新增包同步到小车
scp -r /path/to/NeuPAN 小车用户@小车IP:~/newznzc_ws/src/

# 单独同步新增包
scp -r neupan_deploy/ 小车用户@小车IP:~/newznzc_ws/src/neupan_deploy/

# 小车端编译
ssh 小车用户@小车IP
cd ~/newznzc_ws
catkin_make
source devel/setup.bash

# 安装 neupan Python 包
pip install -e ~/newznzc_ws/src/NeuPAN
```

### 3.3 启动所有节点

```bash
# 小车端: 一键启动 (所有节点)
roslaunch neupan_deploy neupan_real.launch
```

### 3.4 重复阶段一和二的测试

```bash
# 直线测试
rostopic pub --once /move_base_simple/goal geometry_msgs/PoseStamped \
  "header: {frame_id: 'odom'}
pose:
  position: {x: 1.0, y: 0.0, z: 0.0}
  orientation: {x: 0.0, y: 0.0, z: 0.0, w: 1.0}"

# 避障测试
rostopic pub --once /move_base_simple/goal geometry_msgs/PoseStamped \
  "header: {frame_id: 'odom'}
pose:
  position: {x: 1.5, y: 0.0, z: 0.0}
  orientation: {x: 0.0, y: 0.0, z: 0.0, w: 1.0}"
```

### ✅ 阶段三通过标准

- [ ] 无需 Docker，实车直接运行
- [ ] forward 耗时比 Docker 更低
- [ ] 直线到达目标点
- [ ] 成功避障

---

## 附录 A: 新增包 neupan_deploy 结构

> 这个包是唯一可以在小车上新增的 ROS 包，不修改任何已有包。

```
neupan_deploy/
├── CMakeLists.txt          # 标准 catkin 包 CMake
├── package.xml             # 依赖: rospy, std_msgs, geometry_msgs
├── launch/
│   ├── robot_minimal.launch     # 小车底层 (激光 + 里程计 + 底盘)
│   │   # 只 include 已有包的 launch, 不修改它们
│   │   # <include file="$(find lslidar_driver)/launch/lslidar_serial.launch"/>
│   │   # <node pkg="car_bringup" type="newt.py"/>
│   │   # + static TF bridge
│   │
│   └── neupan_real.launch       # 整合 launch
│       # include robot_minimal.launch
│       # + neupan_node 启动
│       # + topic remap
│
├── config/
│   └── planner_real.yaml        # NeuPAN 参数 (复制自 example/mowen/deploy/)
│
├── scripts/
│   ├── check_all.sh             # 一键检测脚本 (传感器 + TF + 底盘)
│   └── send_goal.py             # 简化目标发送
│
└── models/
    └── → model_5000.pth (符号链接或复制)
```

> `neupan_deploy/` 本身就放在 `~/newznzc_ws/src/` 下，与已有包平级，是独立的 catkin 包。

---

## 附录 B: 快速 scp 命令

```bash
# 环境变量 (一次设置)
export ROBOT_IP="192.168.1.100"       # 改为小车实际 IP
export ROBOT_USER="ubuntu"            # 改为小车用户名
export NEUPAN_LOCAL="/path/to/NeuPAN"

# 同步整个 NeuPAN 仓库到小车
scp -r $NEUPAN_LOCAL $ROBOT_USER@$ROBOT_IP:~/newznzc_ws/src/

# 只同步新增部署包
scp -r neupan_deploy/ $ROBOT_USER@$ROBOT_IP:~/newznzc_ws/src/neupan_deploy/

# 只同步配置文件
scp planner_real.yaml $ROBOT_USER@$ROBOT_IP:~/newznzc_ws/src/neupan_deploy/config/

# 从小车拉取日志
scp $ROBOT_USER@$ROBOT_IP:~/newznzc_ws/devel/*.log .
```

---

## 附录 C: 完整检测清单

### 阶段零 — 前置检测

- [ ] `/scan` Hz ≥ 5Hz, frame_id = "laser_link"
- [ ] `/vel_raw` 有编码器数据
- [ ] `/odom_raw` 里程计积分正常
- [ ] `linear.x` 控制前进/后退
- [ ] `linear.y` 控制横向移动 (omni 必测)
- [ ] `angular.z` 控制旋转
- [ ] 全零指令急停
- [ ] `odom → base_footprint` TF 存在 (若无, 用 `odom_tf_broadcaster.py`)
- [ ] `base_link → laser_link` TF 存在
- [ ] `base_footprint → base_link` TF 存在 (若无, 加 static TF)

### 阶段一 — Docker 直线 (本地 Docker → 远程小车)

- [ ] ROS 网络通: 本地 `rostopic list` 能看到小车 `/scan` `/tf` `/odom`
- [ ] 无 MCU 卡顿 (newt.py 运行 + 50Hz /cmd_vel 零速发送 10s)
- [ ] `forward` 耗时 < 0.1s
- [ ] `/neupan_cmd_vel` → `/cmd_vel` remap 正确
- [ ] waypoints 起点与 odom 实际位置对齐
- [ ] 直线到达目标点 (1, 0)
- [ ] 无抖动停顿

### 阶段二 — Docker 避障

- [ ] DUNE/NRMP 障碍点显示
- [ ] 平稳避障
- [ ] 绕过障碍回到路径
- [ ] 到达目标
- [ ] 无碰撞

### 阶段三 — 实车

- [ ] `pip install -e ~/newznzc_ws/src/NeuPAN`
- [ ] `catkin_make` 编译成功
- [ ] 不依赖 Docker，直接运行
- [ ] forward 耗时 < 0.1s (应比 Docker 更快)
- [ ] 直线到达
- [ ] 成功避障
- [ ] **自始至终没有修改 car_bringup / nav_demo / leishen 等已有包**

### 安全机制

| 动作 | 方式 |
|------|------|
| ROS 急停 | `rostopic pub -1 /cmd_vel geometry_msgs/Twist "{}"` |
| 键盘急停 | `rosrun mbot_teleop mbot_teleop.py` + 空格键 |
| 物理急停 | 底盘 MCU 急停按钮 |
| NeuPAN 急停 | 在 planner.yaml 设 `dune_max_num: 0, nrmp_max_num: 0` 关闭避障 |
