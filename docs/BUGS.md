# NeuPAN 真机部署 Bug 日志

## 1. ROS 网络：hostname 不可解析

**现象**: 机器人 `rostopic echo /cmd_vel` 无数据，容器内正常。

**原因**: NeuPAN 容器用 `--net=host` 宿主机主机名 `kunkun`，机器人网段无法解析。

**修复**: 容器内设 `ROS_IP`
```bash
export ROS_IP=10.42.0.1
```

## 2. ROS 网络：roscore 监听 127.0.0.1

**现象**: 外部连不上机器人 roscore (`Connection refused`)。

**原因**: roscore 默认只绑 `127.0.0.1`。

**修复**: 启动前设 `ROS_HOSTNAME`
```bash
export ROS_HOSTNAME=10.42.0.169
```

## 3. LiDAR 近点误触发 stop

**现象**: NeuPAN 规划器单独测试 `v=0.5`，但 ROS 节点输出 `v=0`。

**原因**: DUNE 对 <0.5m 的 LiDAR 点返回负距离 `min_d=-0.005`，触发 `stop=True`。

**修复**: 过滤近点
```yaml
scan_range: [0.5, 27.0]
```

## 4. Docker daemon 代理劫持 apt

**现象**: `docker build` 时 apt 全挂。

**原因**: daemon 配置的 `HTTP_PROXY=127.0.0.1:7897` 注入容器，容器内 127.0.0.1 不可达。

**修复**: 放弃 Dockerfile，改用容器 + setup.sh 模式。

## 5. waypoints 起点=机器人位置导致 arrive

**现象**: NeuPAN 输出 `v=0`，无任何报错。

**原因**: `waypoints: [[0,0,0],...]`，机器人正好在 [0,0,0]，`set_initial_path_from_state` 后第一段曲线零长度，立即 `arrive=True`。

**修复**: waypoints 起点设远离机器人当前位置。

## 6. 串口冲突

**现象**: `pubv.py` 报 `device disconnected or multiple access`。

**原因**: `newt.py` 和 `pubv.py` 同时打开 `/dev/carserial`。

**修复**: `sudo fuser -k /dev/carserial`，按正确顺序启动 newt 先于 pubv。

## 7. GPU 多卡卡屏

**现象**: Gazebo 启动副屏冻住。

**原因**: OpenGL 跳合成管线，副屏缓冲锁死。

**修复**: `nvidia-settings --assign CurrentMetaMode "DP-1: ... {ForceCompositionPipeline=On}"`

## 8. amcl frame 缺失

**现象**: `waiting for tf base_link to map`。

**原因**: `nav777.launch` 不含 AMCL，无 `map` 帧。

**修复**: `nav777.launch` 后加 `roslaunch nav_demo nav04_amcl.launch`，或 NeuPAN 用 `map_frame: odom`。

## 9. move_base 抢 cmd_vel

**现象**: 两个节点同时发 `/cmd_vel`。

**原因**: `nav777.launch` 含 `nav05_path_dwa.launch`（move_base）。

**修复**: `rosnode kill /move_base`。

## 10. rostopic pub 后台进程持续发指令 (高危)

**现象**: 
- 小车在无操作时持续前进/转动，不受控制
- `newt.py` 终端疯狂刷 `('\x00', 'd')` 等打印
- `rostopic hz /cmd_vel` 显示 30Hz 持续发布

**原因**: 多次执行 `rostopic pub /cmd_vel ...` 但未按 `Ctrl+C` 停止就关了终端，进程留在后台继续以 30Hz 默认频率循环发布 `/cmd_vel`。其生命周期与 bash 会话绑定，终端关闭但进程不终止。MCU 保持最后收到的速度指令，导致小车一直走。

**排查**:
```bash
# 查看谁在发 /cmd_vel
rostopic hz /cmd_vel

# 查看发布者列表 (会看到多个 /rostopic_xxxxx)
rostopic info /cmd_vel
```

**修复**:
```bash
# 方法 1: 杀掉所有 rostopic 进程
pkill -f "rostopic pub"

# 方法 2: 按 PID 逐个杀
kill <PID1> <PID2> <PID3>

# 方法 3: 发急停指令 (如果上述方法已生效)
rostopic pub -1 /cmd_vel geometry_msgs/Twist "{}"
```

**预防**:
- 用完 `rostopic pub` 务必按 `Ctrl+C` 停掉再关终端
- 用 `-r` 参数时设置有限次数: `-r 10 -1`
- 写脚本时用 `rostopic pub -1` 或 `rospy.sleep()` 后自动停

## 11. MCU 保持最后速度不归零 (无法走固定距离)

**现象**:
- `rostopic pub -1 /cmd_vel "{linear: {x: 0.1}}"` 只发一帧指令
- MCU 收到后持续以 0.1m/s 运行，永不停止
- 小车不能按指定的距离启停

**原因**: `newt.py` 将 Twist 转串口协议发给 MCU 后，MCU 以**开环**方式保持最后收到的速度值，没有超时自动归零机制。`rostopic pub -1` 只发一帧就退出，后续没有零速度指令到达。

**修复**: 使用独立脚本持续发送指定时长后自动发停止指令。

推荐使用 `docs/scripts/move_distance.py`:
```bash
# 前进 0.5 米
python3 move_distance.py forward 0.5

# 左移 0.3 米 (omni)
python3 move_distance.py left 0.3

# 旋转 90 度
python3 move_distance.py rotate_left 90

# 急停
python3 move_distance.py stop
```

**原理**: 脚本先发送速度指令 → `rospy.sleep(duration)` → 发送全零 Twist 停止。算距离公式 `t = distance / speed`。

## 12. MCU 卡顿模式: 20Hz 以下命令导致 stutter

**现象**:
- 运行 20Hz 的 /cmd_vel 发布后, 小车进入"一卡一卡"的卡顿模式
- 之后无论什么命令都卡, 必须用遥控器切换模式才能恢复

**原因**: 
- 小车有遥控器(PS2)接收器, 与串口`newt.py`共用MCU
- 20Hz 命令可能让 MCU 在遥控/串口模式间频繁切换, 进入冲突态
- 50Hz 连续稳定发布则不会触发卡顿

**修复**:
- 发布频率维持在 50Hz (实测 10Hz 和 50Hz 都正常, 20Hz 有问题)
- 如果用遥控器控制过后, 必须先切回串口模式再运行脚本
- `move_distance.py` 已更新为 50Hz

## 14. EKF 参数格式: initial_estimate_covariance 用字符串而非数值

**现象**:
- EKF 启动后不发布 odom 话题，`rostopic list` 看不到 `/odom`
- `rosrun robot_localization ekf_localization_node` 无报错，但不输出

**原因**: `example/mowen/envs/real/robot_minimal.launch` 中 `initial_estimate_covariance` 使用字符串格式 `'1e-9'` 而非数值格式 `1e-9`：

```xml
<!-- 错误: 字符串值 -->
<param name="initial_estimate_covariance" value="['1e-9', 0, 0, ...]"/>
<!-- 正确: 数值 -->
<param name="initial_estimate_covariance" value="[1e-9, 0, 0, ...]"/>
```

**修复**: 去掉 `'` 引号，但 **launch 文件在小车上不能修改**（不修改已有包原则）。

**规避**: 使用 `docs/scripts/odom_tf_broadcaster.py` 绕过 EKF，直接订阅 `/odom_raw` 广播 odom → base_footprint TF。

```python
# 在小车上用 python2 运行:
python /path/to/odom_tf_broadcaster.py

**现象**:
- 命令 0.8 m/s 跑 4s → 实际约 1.5m (期望 3.2m)
- 命令速度 × 0.47 ≈ 实际速度

**原因**: `newt.py` 用 ×1000 缩放 (0.8 → 800), MCU 可能期望 ×2000, 或有内部速度限幅

**修复**:
- `move_distance.py` 加入 `SPEED_CALIB = 0.5` 校准系数
- NeuPAN 不受影响 (靠里程计反馈闭环控制)
- 如需精确开环移动, 先校准 `SPEED_CALIB`
