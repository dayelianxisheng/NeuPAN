# NeuPAN 真机部署进展报告

> 更新日期: 2026-06-26  
> 小车: mowen (10.42.0.40/169)  
> 系统: Ubuntu 18.04 / ROS Melodic

---

## 一、已完成的工作

### 1. 基础环境 ✅
- [x] Claude Code 在小车安装完成，可正常使用
- [x] Node.js 18 (glibc-217兼容版) 已安装到 `~/.local/node18/`
- [x] API 配置: `mimo-v2.5-pro` 模型，`inferaichat.com` 代理

### 2. 传感器状态 ✅
- [x] 激光雷达 (镭神 N10): 10.05Hz, frame_id=`laser_link`, 扫描范围±π
- [x] 轮式里程计: `/vel_raw` + `/odom_raw` 正常

### 3. 串口协议分析 ✅
在 `newznzc_ws/src/car_bringup/scripts/` 中发现 3 个不同的串口协议实现：

| 脚本 | 帧头 | 缩放 | 波特率 | 字节序 | 有 y? |
|------|------|------|--------|--------|-------|
| `newt.py` | `\xAA\xBB\x0A\x12\x02` | ×1000 | 115200 | 小端 | ✅ |
| `teleop_send_vel_mowen.py` | `\x11\x00\x00\x00` | ×100 | 115200 | 大端 | ❌ |
| `teleop_test.py` | `\x11\x00\x00\x3c` | ×100 | 9600 | 直接 | ❌ |

### 4. 卡顿问题排查 ✅（Bug #12）
**结论：** `newt.py` + `/cmd_vel` 发布者 → MCU 退化状态

规避方案：
- newt.py 保持 50Hz 发布可缓解
- 卡顿时杀掉 newt.py 立即恢复（无需 reboot）
- 详见 `deployment_flow.md` §1.3

### 5. 配置文件 ✅
- `example/mowen/envs/real/planner.yaml`: omni, collision_threshold=0.05, max_speed=[0.2,0.5], ref_speed=0.15
- `example/mowen/envs/real/mowen_real.launch`: map_frame=odom, base_frame=base_link, lidar_frame=laser_link, scan_range=0.5-27.0, scan_downsample=6
- `example/mowen/model/mowen_real/model_5000.pth`: omni 模型 checkpoint

---

## 二、测试阶段

### Phase 0: 前置检测 ✅ (2026-06-25)
- [x] 6 方向底盘测试（前/后/左/右/左转/右转）
- [x] TF 树完整: `odom → base_footprint → base_link → laser_link`
- [x] LiDAR 10Hz 稳定
- [x] 串口 55Hz 稳定
- [x] Bug #11 (MCU 保持速度不归零) — 已用 `move_distance.py` 规避
- [x] Bug #13 (速度偏差 ×0.47) — 不影响闭环，跳过校准

### Phase 1: 本地 Docker → 实车直线行走测试 ✅ (2026-06-26)
**架构：** 本地开发机 Docker (ros:noetic-ros-core) + ROS 网络连接小车
- [x] ROS 网络配通 (ROS_MASTER_URI, ROS_IP) ✅
- [x] MCU 卡顿前置检测 ✅
- [x] forward 耗时 < 0.1s ✅
- [x] 直线到达 2.91m（目标 3m）✅

### Phase 2: 本地 Docker → 实车避障测试 ✅ (2026-06-26)
**成功参数（来自 dyna_non_obs）：**
```yaml
receding: 8; step_time: 0.15; ref_speed: 1
collision_threshold: 0.1
q_s: 0.5; p_u: 1.0; eta: 8.0; d_max: 0.3; d_min: 0.05
```
- [x] 放障碍物 → DUNE 检测 ✅
- [x] NRMP 规划绕行 ✅
- [x] 到达目标点 (3, 0) ✅

---

## 三、已知问题

### Bug #12: MCU 卡顿模式
- **现象**: newt.py + `/cmd_vel` 发布 → MCU 卡顿
- **规避**: 杀掉 newt.py 后遥控器自动恢复；保持 50Hz 可缓解
- **影响**: Phase 1 启动前必须先做卡顿前置检测

### Bug #13: 速度偏差
- **现象**: 命令速度 × 0.47 ≈ 实际速度
- **规避**: NeuPAN 靠里程计闭环，不受影响
- **影响**: 仅影响开环距离测试

### Bug #14: EKF 参数格式错误
- **现象**: `initial_estimate_covariance` 用 `'1e-9'` 字符串，EKF 解析失败
- **规避**: 用 `odom_tf_broadcaster.py` 绕过

---

## 四、关键文件位置

```
NeuPAN/
├── docs/
│   ├── deployment_flow.md              # 部署流程 (已更新 Phase 1 架构)
│   ├── BUGS.md                         # Bug 日志
│   ├── test_record_template.md         # 测试记录模板
│   ├── scripts/
│   │   ├── move_distance.py            # 开环距离测试
│   │   ├── neupan_serial_bridge.py     # 串口桥 (替代 newt.py)
│   │   └── odom_tf_broadcaster.py      # odom TF 广播 (绕过 EKF)
│   └── neupan_car_deploy_status.md     # 本文件
├── example/mowen/
│   ├── envs/real/
│   │   ├── planner.yaml                # NeuPAN 参数
│   │   ├── mowen_real.launch           # ROS launch
│   │   └── move.py                     # 点移动控制脚本
│   └── model/mowen_real/
│       └── model_5000.pth              # omni 模型
├── docker/
│   └── container.sh                    # Docker 容器管理
└── neupan_ros/
    └── src/neupan_core.py              # 已修复 omni generate_twist_msg
```

---

## 五、Phase 1 快速启动

```bash
# 1. 检查网络
ping 10.42.0.169

# 2. 小车端 5 个终端
#    A: roslaunch lslidar_driver lslidar_serial.launch
#    B: rosrun car_bringup pubv.py && rosrun car_bringup base_node
#    C: python odom_tf_broadcaster.py         # 绕过 EKF
#    D: rosrun car_bringup newt.py             # 先做卡顿检测!
#    E: rosrun tf static_transform_publisher 0 0 0 0 0 0 base_footprint base_link 100

# 3. 本地 Docker
./docker/container.sh ros1 start
# 容器内:
export ROS_MASTER_URI=http://10.42.0.169:11311
export ROS_IP=10.42.0.xxx   # 本地 10.42.x.x IP

# 4. 启动 neupan_node
roslaunch neupan_ros neupan_node.launch \
  config_file:=/root/neupan_ws/src/NeuPAN/example/mowen/envs/real/planner.yaml \
  map_frame:=odom base_frame:=base_link lidar_frame:=laser_link \
  scan_downsample:=6 scan_range:="0.5 27.0" \
  dune_checkpoint:=/root/neupan_ws/src/NeuPAN/example/mowen/model/mowen_real/model_5000.pth

# 5. 校准 waypoints + 发送目标
rostopic echo /odom -n 1   # 查看实际位置，调 waypoints
rostopic pub --once /move_base_simple/goal geometry_msgs/PoseStamped \
  "header: {frame_id: 'odom'}
pose: {position: {x: 1.0, y: 0.0, z: 0.0}, orientation: {w: 1.0}}"
```

---

## 六、工作日志

### 2026-06-24 ~ 2026-06-25: Phase 0 完成
- 环境搭建、TF 修复、底盘测试、串口协议分析
- 详情见会话历史

### 2026-06-26: 文档更新 + Phase 1 & 2 测试成功 🎉
- `deployment_flow.md` Phase 1 架构改为 **本地 Docker → 远程小车**
- 新增 MCU 卡顿前置检测步骤、waypoints 校准说明、ROS 网络配置
- 修复 `move_distance.py` / `start_car.sh` 停止命令（持续零速 3 秒）
- 修复 `laser_link` TF 错误（yaw=π 导致 LiDAR 数据反转）
- **Phase 1 直线测试成功** — 车从 (0,0) 走到 2.91m ✅
- **Phase 2 避障测试成功** — 检测障碍物并绕行 ✅
- 最终参数来源: `example/mowen/envs/dyna_non_obs/planner.yaml`
