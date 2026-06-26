# mowen 新小车 — 5 分钟快速上手指南

本指南帮助你在新小车上快速部署 NeuPAN，实现**直线走 + 避障**的基础功能。

---

## 前置条件

✅ **硬件准备**
- mowen 小车（omni 全向底盘）
- 激光雷达（Leishen N10）已连接
- 小车与控制电脑在同一网络

✅ **软件准备**
- 小车端：ROS Noetic + 底层驱动已安装
- 控制电脑：NeuPAN 已安装（`pip install -e .`）
- neupan_ros 已编译（`catkin_make`）

---

## 快速启动（3 步）

### 📍 Step 1: 启动小车底层（在小车上执行）

```bash
# SSH 登录小车
ssh <用户名>@<小车IP>

# 启动最小化配置（LiDAR + 里程计 + EKF）
roslaunch <小车工作空间>/launch/robot_minimal.launch
# 或参考 example/mowen/envs/real/robot_minimal.launch 创建

# 保持此终端运行
```

**检查:** 应该看到激光雷达、里程计节点启动成功

---

### 📍 Step 2: 启动 NeuPAN（在控制电脑上执行）

```bash
# 终端 1: 设置 ROS 网络环境
export ROS_MASTER_URI=http://<小车IP>:11311
export ROS_IP=<本机IP>

# 验证连接
rostopic list  # 应该看到 /scan, /odom 等

# 快速检查（可选）
cd ~/neupan_ws/src/NeuPAN/example/mowen/envs/real
./quick_check.sh  # 自动检查所有依赖

# 启动 NeuPAN 节点
cd ~/neupan_ws
source devel/setup.bash
roslaunch neupan_ros test_simple_straight.launch

# 保持此终端运行
```

**检查:** 应该看到以下输出
```
[INFO] robot state received [x, y, theta]
[INFO] initial Path Received
[INFO] Scan obstacle points Received
```

---

### 📍 Step 3: 运行测试（在控制电脑新终端执行）

```bash
# 终端 2: 运行自动化测试
cd ~/neupan_ws/src/NeuPAN/example/mowen/envs/real
python3 test_simple_move.py

# 测试内容:
# 1. 前进 1 米
# 2. 继续前进 1 米（可放置障碍物测试避障）
# 3. 返回起点
```

**或手动发送目标点:**

```bash
# 前进到前方 2 米
rostopic pub /move_base_simple/goal geometry_msgs/PoseStamped \
  "header: {frame_id: 'odom'}
   pose:
     position: {x: 2.0, y: 0.0, z: 0.0}
     orientation: {w: 1.0}"
```

---

## 可视化（可选）

```bash
# 终端 3: 启动 RViz 查看规划效果
rviz -d ~/neupan_ws/src/NeuPAN/example/mowen/envs/real/mowen.rviz
```

**在 RViz 中添加:**
- `Path` → `/neupan_plan` (规划路径，绿色)
- `Path` → `/neupan_initial_path` (初始路径，蓝色)
- `LaserScan` → `/scan` (激光扫描)
- `MarkerArray` → `/dune_point_markers` (障碍点，紫色)
- `Marker` → `/robot_marker` (机器人轮廓)

---

## 常见问题 30 秒解决

### ❌ 问题: "waiting for tf"

```bash
# 检查 TF 树
rosrun tf tf_echo odom base_link

# 如果报错，检查小车端 robot_minimal.launch 是否启动
```

**解决:** 确保小车端的里程计和 TF 静态发布节点正常运行

---

### ❌ 问题: 小车不动

```bash
# 1. 检查速度输出
rostopic echo /neupan_cmd_vel

# 2. 如果速度为 0，查看 NeuPAN 终端
# 如果看到 "neupan stop with min distance xxx"
# → 说明触发了碰撞检测
```

**解决方案 A: 过滤近点**

编辑 `test_simple_straight.launch`:
```xml
<arg name="scan_range" default="0.5 27.0"/>  <!-- 增大最小值到 0.5m -->
```

**解决方案 B: 调整安全阈值**

编辑 `planner_simple_test.yaml`:
```yaml
collision_threshold: 0.15  # 从 0.12 增加到 0.15
```

---

### ❌ 问题: 小车失控持续运动

```bash
# 🚨 紧急停止
pkill -f "rostopic pub"
rostopic pub -1 /cmd_vel geometry_msgs/Twist "{}"
```

**原因:** 后台有 `rostopic pub` 进程在持续发送速度指令

**预防:** 使用 `rostopic pub` 后务必按 `Ctrl+C` 停止

---

### ❌ 问题: "No obstacle points" 警告

```bash
# 检查激光雷达
rostopic hz /scan
rostopic echo /scan | head -20
```

**影响:** 只能走路径跟踪，避障失效

**解决:**
- 在小车周围放置障碍物（距离 0.5-5m）
- 调整 `scan_downsample` 参数（减小值增加点数）

---

## 参数快速调优

### 🔧 调整速度（更快/更慢）

编辑 `planner_simple_test.yaml`:
```yaml
ref_speed: 0.15  # 改为 0.1（更慢更安全）或 0.2（更快）
max_speed: [0.2, 0.2]  # 最大速度限制
```

### 🔧 调整避障距离（更近/更远）

```yaml
adjust:
  d_max: 1.2   # 最大安全距离（增大→更早避障）
  d_min: 0.15  # 最小安全距离（增大→离障碍物更远）
```

### 🔧 调整避障强度

```yaml
adjust:
  eta: 15.0    # 避障权重（增大→避障更激进）
```

---

## 文件说明

新增文件位于 `example/mowen/envs/real/`:

| 文件 | 用途 |
|------|------|
| `test_simple_straight.launch` | 简化测试 launch 文件 |
| `planner_simple_test.yaml` | 简化测试配置（保守参数） |
| `test_simple_move.py` | 自动化测试脚本 |
| `quick_check.sh` | 部署前快速检查脚本 |
| `DEPLOYMENT_CHECKLIST.md` | 详细部署检查清单 |
| `QUICKSTART.md` | 本文件 |

原有文件（复杂场景）:
- `mowen_real.launch` — 原始配置
- `planner.yaml` — 原始参数（速度更快，参数更激进）

---

## 进阶使用

✅ **基础功能测试通过后**，可以尝试：

### 1. 使用原始配置（更快速度）

```bash
roslaunch neupan_ros mowen_real.launch  # 使用原始配置
```

### 2. 自定义路径

编辑 `planner_simple_test.yaml`:
```yaml
ipath:
  waypoints: [[0.5, 0, 0], [2.0, 0, 0], [2.0, 1.0, 0]]  # 添加转弯点
```

### 3. 接入全局规划器

发布 `/initial_path` topic，NeuPAN 会自动跟随：
```bash
# 从 A* 或其他规划器获取路径后发布
rostopic pub /initial_path nav_msgs/Path "..."
```

### 4. 巡逻任务

使用 `move.py` 脚本（在原配置中）:
```bash
python3 move.py 1.0 0.0  2.0 0.0  2.0 1.0  0.0 0.0  # 四个点循环巡逻
```

---

## 安全提示 ⚠️

1. **首次测试必读:**
   - 使用低速配置（`ref_speed: 0.1`）
   - 保持 2 米安全距离
   - 准备急停方案（拔电源或急停按钮）

2. **清理后台进程:**
   ```bash
   # 每次测试结束后检查
   ps aux | grep "rostopic pub"
   pkill -f "rostopic pub"  # 如果有，立即清理
   ```

3. **串口冲突:**
   - 不要同时运行多个控制程序
   - 如果小车无响应，检查串口占用：`sudo fuser -k /dev/carserial`

---

## 成功标志 ✅

部署成功的表现：
- ✅ 小车能平稳前进到目标点（误差 <0.3m）
- ✅ 遇到障碍物能主动绕行
- ✅ 速度平滑无抖动
- ✅ 到达目标后自动停止
- ✅ NeuPAN 终端无报错

---

## 获取帮助

- 📖 详细部署指南: `docs/real_robot_deployment.md`
- 🐛 已知问题汇总: `docs/BUGS.md`
- ✅ 完整检查清单: `DEPLOYMENT_CHECKLIST.md`
- 📝 项目文档: `CLAUDE.md`

**如果遇到问题:**
1. 先查看 `docs/BUGS.md` 中是否有相同问题
2. 运行 `./quick_check.sh` 自动检查环境
3. 查看 NeuPAN 和小车端终端的完整输出

---

## 下一步学习

✅ 基础功能验证后，推荐学习顺序：

1. **理解 NeuPAN 架构** → 阅读 `CLAUDE.md` 了解工作原理
2. **调参优化** → 实验不同 `q_s`, `eta`, `d_max` 组合
3. **DUNE 训练** → 如果更换机器人几何形状，重新训练模型
4. **ROS 集成** → 接入 Nav2 或其他导航框架
5. **复杂场景** → 测试动态障碍物、窄通道、倒车等

祝部署顺利！🎉
