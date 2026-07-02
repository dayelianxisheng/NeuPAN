# NeuPAN Mowen 项目 — 运行指南

## 目录结构

```
example/mowen/
├── deploy/                     # 真机部署配置（Docker 端使用）
│   ├── pure_neupan/            # 纯 NeuPAN 路径跟踪（无地图，靠里程计）
│   │   ├── config/planner.yaml
│   │   ├── launch/mowen_real.launch
│   │   ├── rviz/
│   │   └── scripts/start_car.sh
│   ├── astar_neupan/           # A* + NeuPAN 导航（需预先建图 + AMCL）
│   │   ├── config/planner.yaml
│   │   ├── config/amcl.yaml
│   │   ├── launch/navigation.launch
│   │   ├── rviz/navigation.rviz
│   │   ├── maps/               # 已保存的地图文件
│   │   └── scripts/
│   ├── fast_lio_neupan/        # Fast-LIO 定位 + NeuPAN（TODO）
│   └── scripts/
│       └── deploy.sh           # Docker 端统一启动脚本
├── envs/                       # 仿真场景
│   ├── corridor/               # 走廊（含障碍物）
│   ├── maze_obs/               # 迷宫障碍
│   ├── dyna_maze/              # 迷宫+动态障碍
│   ├── dyna_obs/               # 动态障碍
│   ├── non_obs/                # 无障碍
│   ├── pf/                     # 纯路径跟踪
│   └── ...
├── eval.py                     # 仿真测试（支持 A* + NeuPAN）
└── scripts/                    # 小车端启动脚本（SCP 到小车）
    ├── start_car_pure.sh       # 纯 NeuPAN 小车启动
    └── start_car_astar.sh      # A* + NeuPAN 小车启动
```

---

## 仿真测试

```bash
cd example/mowen

# 跑指定场景
python eval.py corridor
python eval.py maze_obs
python eval.py dyna_maze

# 跑全部场景
python eval.py
```

每个场景包含 `env.yaml`（仿真环境）和 `planner.yaml`（规划参数）。

### 场景说明

| 场景 | 障碍物 | 特点 |
|------|--------|------|
| corridor | 静态矩形 | 走廊+障碍物，loop 测试 |
| non_obs | 无 | 纯路径跟踪 |
| maze_obs | 静态迷宫 | 复杂路径 |
| dyna_maze | 静态+动态 | 动态圆形障碍 |
| dyna_obs | 动态 | 动态障碍避障 |
| pf | 无 | 路径跟踪 |

### planner.yaml 关键参数

```yaml
# MPC
receding: 10           # 规划步数
step_time: 0.15        # 每步时间 (s)
ref_speed: 0.5         # 参考速度 (m/s)

robot:
  kinematics: 'omni'   # omni / diff / acker
  max_speed: [v_max, phi_max]    # [线速度, 方向角范围]
  max_acce: [a_v, a_phi]         # [加速度, 方向变化速度]

ipath:
  waypoints: [[x, y, theta]]     # 目标点（单个点即可，不含起始位置）
  loop: True / False             # 是否循环往复
  arrive_threshold: 0.1          # 到达判定距离 (m)

pan:
  iter_num: 2           # PAN 迭代次数

adjust:
  q_s: 0.5              # 路径跟踪权重
  p_u: 1.0              # 控制代价权重
  eta: 8.0              # 碰撞约束硬度
  d_max: 0.15           # DUNE 感知距离
  d_min: 0.05           # DUNE 最小安全距离

astar:                  # 可选，有则启用 A* 全局规划
  robot_radius: 0.25
  resolution: 0.05
```

**注意：**
- `phi_max >= 3.15` 才能后退（π ≈ 3.14）
- `waypoints` 只写目标位置即可，当前状态会自动插入为第一个点
- 不包含起始位置：`waypoints: [[4, 0, 0]]` ✅
- 不要写成：`waypoints: [[0, 0, 0], [4, 0, 0]]` ❌

---

## 真机部署 — 纯 NeuPAN 路径跟踪

### 小车端

```bash
# 硬件启动
~/neupan_ws/src/NeuPAN/scripts/start_car_pure.sh start

# 检查
~/neupan_ws/src/NeuPAN/scripts/start_car_pure.sh check

# 急停（发 3 秒零速）
~/neupan_ws/src/NeuPAN/scripts/start_car_pure.sh stop

# 里程计归零
~/neupan_ws/src/NeuPAN/scripts/start_car_pure.sh reset_odom

# 清理
~/neupan_ws/src/NeuPAN/scripts/start_car_pure.sh cleanup
```

### Docker 端

```bash
# 进入 Docker
./docker/container.sh ros1 start

# 设置 ROS 环境
export ROS_MASTER_URI=http://<小车IP>:11311
export ROS_IP=<本机IP>

# 启动 NeuPAN 规划
bash /root/neupan_ws/src/NeuPAN/example/mowen/deploy/scripts/deploy.sh pure
```

### 发送导航目标

```bash
rostopic pub /move_base_simple/goal geometry_msgs/PoseStamped \
  '{header: {frame_id: "odom"}, pose: {position: {x: 2, y: 0}, orientation: {w: 1}}}' --once
```

---

## 真机部署 — A* + NeuPAN 导航

### 第1步：建图（小车端）

```bash
roscore
rosrun car_bringup newt.py
rosrun mbot_teleop mbot_teleop.py
roslaunch car_bringup gmapping.launch

# 建完保存
roslaunch nav_demo nav02_map_save.launch

# 地图生成在 ~/.ros/ 或 ~/newznzc_ws/src/nav_demo/map/
# 将 mymap.yaml + mymap.pgm 复制到 deploy/astar_neupan/maps/
```

### 第2步：导航

**小车端：**
```bash
~/neupan_ws/src/NeuPAN/scripts/start_car_astar.sh
```

**Docker 端：**
```bash
export ROS_MASTER_URI=http://<小车IP>:11311
export ROS_IP=<本机IP>
bash /root/neupan_ws/src/NeuPAN/example/mowen/deploy/scripts/deploy.sh astar
```

**RViz 操作：**
1. 2D Pose Estimate → 点小车初始位置
2. 2D Nav Goal → 设目标点
3. 小车自动规划路径并前往

---

## 文件功能说明

### 仿真

| 文件 | 功能 |
|------|------|
| `eval.py` | 仿真运行脚本，自动检测 astar 配置节启用 A* |
| `eval_astar.py` | A* + NeuPAN 仿真（评估用） |
| `envs/<场景>/env.yaml` | 仿真环境定义（世界尺寸、障碍物、机器人起始位置） |
| `envs/<场景>/planner.yaml` | 规划参数 |

### 部署

| 文件 | 功能 |
|------|------|
| `deploy/scripts/deploy.sh` | Docker 端统一入口，`deploy.sh pure` 或 `deploy.sh astar` |
| `deploy/pure_neupan/config/planner.yaml` | 纯 NeuPAN 真机参数 |
| `deploy/pure_neupan/launch/mowen_real.launch` | 纯 NeuPAN ROS 启动文件 |
| `deploy/pure_neupan/rviz/` | RViz 可视化配置 |
| `deploy/astar_neupan/config/planner.yaml` | A* 导航真机参数 |
| `deploy/astar_neupan/config/amcl.yaml` | AMCL 定位参数 |
| `deploy/astar_neupan/launch/navigation.launch` | 导航模式 ROS 启动文件 |
| `deploy/astar_neupan/maps/` | 建图生成的地图文件 |
| `scripts/start_car_pure.sh` | 小车端纯 NeuPAN 启动（SCP 到小车） |
| `scripts/start_car_astar.sh` | 小车端 A* 导航启动（SCP 到小车） |
| `docs/` | 文档 |

### 机器人模型

| 参数 | 值 |
|------|-----|
| 运动学 | omni（全向） |
| 尺寸 | 0.42m × 0.26m |
| 激光 | 镭神 N10，80 线 |
| 串口 | `/dev/carserial`，115200 baud |

---

## 常见问题

### 启动后报 `collision_threshold` 错误
`collision_threshold` 不应小于 `d_min`。建议 `collision_threshold: 0.1`，`d_min: 0.05`。

### 机器人不按目标方向走
检查 `max_speed` 的第二个值（phi_max）。phi_max < 3.14 时无法后退或横向移动。

### 激光雷达检测不到近处障碍
检查 `scan_range` 最小值。`0.05 10.0` 表示保留 0.05m 以外的所有点，不滤近距离数据。

### Docker 找不到 launch 文件
使用完整路径：
```bash
roslaunch /root/neupan_ws/src/NeuPAN/example/mowen/deploy/pure_neupan/launch/mowen_real.launch
```

### MCU 保持最后速度（小车不停）
MCU Bug：必须持续发零速至少 3 秒才能覆盖缓存。
```bash
# 正确的急停顺序
./start_car_pure.sh stop      # 发零速 3 秒
./start_car_pure.sh cleanup    # 再杀节点
```
