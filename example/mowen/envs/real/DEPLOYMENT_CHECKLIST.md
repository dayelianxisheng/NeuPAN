# mowen 新小车部署检查清单

## 部署前准备

### 1. 硬件检查
- [ ] 小车电量充足（建议 >50%）
- [ ] 激光雷达已连接并上电
- [ ] 轮式里程计正常工作
- [ ] 串口设备可访问（`/dev/ttyUSB*` 或 `/dev/carserial`）
- [ ] 网络连接正常（小车与控制电脑在同一网段）

### 2. 环境准备
- [ ] 小车工作空间已清理（≥3米直线空间）
- [ ] 准备测试障碍物（纸箱、椅子等，高度 >0.3m）
- [ ] 周围无人干扰，安全距离 >2m

### 3. 软件环境检查（小车端）
```bash
# SSH 登录小车
ssh <用户名>@<小车IP>

# 检查 ROS 环境
roscore &
sleep 2
rostopic list  # 应该看到基础 topics

# 检查串口设备
ls -l /dev/carserial  # 或 /dev/ttyUSB*

# 检查雷达驱动包
rospack find lslidar_driver  # 应该返回路径
```

---

## 部署步骤

### Step 1: 启动小车底层（小车端执行）

```bash
# 1. 启动 roscore（如果未启动）
roscore &

# 2. 启动最小化配置（包含 LiDAR + 轮速 + 里程计）
roslaunch <小车工作空间路径>/robot_minimal.launch

# 或参考 example/mowen/envs/real/robot_minimal.launch 创建对应文件
```

**检查点：**
```bash
# 检查必需的 topics
rostopic list | grep -E "/scan|/odom|/cmd_vel"
# 应该看到:
# /scan
# /odom (或 /odom_raw)
# /cmd_vel

# 检查 LiDAR 数据
rostopic hz /scan
# 应该显示 10-20 Hz

# 检查 TF 树
rosrun tf tf_echo odom base_link
# 应该实时输出位置变换
```

### Step 2: 设置 ROS 网络（控制电脑端）

```bash
# 设置 ROS_MASTER_URI 指向小车
export ROS_MASTER_URI=http://<小车IP>:11311
export ROS_IP=<本机IP>

# 验证连接
rostopic list
# 应该看到小车上的所有 topics

# 可选：将上述配置写入 ~/.bashrc
echo "export ROS_MASTER_URI=http://<小车IP>:11311" >> ~/.bashrc
echo "export ROS_IP=<本机IP>" >> ~/.bashrc
```

### Step 3: 启动 NeuPAN（控制电脑端）

```bash
# 进入 NeuPAN 工作空间
cd ~/neupan_ws
source devel/setup.bash

# 启动简化测试配置
roslaunch neupan_ros test_simple_straight.launch

# 或指定 neupan_root 参数
roslaunch neupan_ros test_simple_straight.launch \
    neupan_root:=$(rospack find neupan_ros)/../NeuPAN
```

**检查点：**
```bash
# 应该看到以下输出：
# - "robot state received [x, y, theta]"
# - "initial Path Received"
# - "Scan obstacle points Received"

# 检查 NeuPAN 发布的 topics
rostopic list | grep neupan
# 应该看到:
# /neupan_plan
# /neupan_initial_path
# /neupan_ref_state
# /dune_point_markers
# /nrmp_point_markers
# /robot_marker

# 检查速度输出
rostopic echo /cmd_vel
# 应该全零（还没发送目标）
```

### Step 4: 运行测试脚本

```bash
# 方法 1: 使用自动化测试脚本
cd example/mowen/envs/real
python3 test_simple_move.py

# 方法 2: 手动发送目标点
rostopic pub /move_base_simple/goal geometry_msgs/PoseStamped \
  "header: {frame_id: 'odom'}
   pose:
     position: {x: 1.0, y: 0.0, z: 0.0}
     orientation: {x: 0.0, y: 0.0, z: 0.0, w: 1.0}"
```

---

## 常见问题快速排查

### 问题 1: NeuPAN 日志显示 "waiting for tf"

**原因:** TF 树不完整

**排查:**
```bash
# 检查 TF 链路
rosrun tf view_frames
evince frames.pdf  # 查看 TF 树图

# 检查关键变换
rosrun tf tf_echo odom base_link
rosrun tf tf_echo base_link laser_link
```

**解决:**
- 确保 `robot_minimal.launch` 已启动
- 检查 TF 静态发布节点是否运行
- 参考 `docs/BUGS.md` 第 8 条

### 问题 2: 小车不动（速度始终为 0）

**排查:**
```bash
# 1. 检查 NeuPAN 是否发布速度
rostopic echo /neupan_cmd_vel

# 2. 检查是否触发 stop 标志
# 查看 NeuPAN 终端输出，如果看到:
# "neupan stop with the min distance xxx threshold xxx"
# 说明距离障碍物太近

# 3. 检查串口是否被占用
ps aux | grep -E "newt|pubv"
# 应该只看到一个 newt.py 或 pubv.py 进程
```

**解决:**
- 如果触发 stop: 调整 `scan_range` 过滤近点（参考 `docs/BUGS.md` 第 3 条）
- 如果串口冲突: `sudo fuser -k /dev/carserial`（参考 `docs/BUGS.md` 第 6 条）
- 检查是否有遗留的 `rostopic pub` 进程（参考 `docs/BUGS.md` 第 10 条）:
  ```bash
  pkill -f "rostopic pub"
  ```

### 问题 3: 小车持续运动无法停止（危险！）

**原因:** 后台 `rostopic pub` 进程持续发布速度（参考 `docs/BUGS.md` 第 10 条）

**紧急停止:**
```bash
# 方法 1: 杀掉所有 rostopic 进程
pkill -f "rostopic pub"

# 方法 2: 发送急停指令
rostopic pub -1 /cmd_vel geometry_msgs/Twist "{}"

# 方法 3: 物理急停（最后手段）
# 拔掉小车电源或按急停按钮
```

### 问题 4: LiDAR 数据异常

**排查:**
```bash
# 检查扫描频率
rostopic hz /scan

# 检查扫描数据
rostopic echo /scan | head -50

# 检查 frame_id
rostopic echo /scan | grep frame_id
# 应该是 "laser_link"
```

**解决:**
- 重启 LiDAR 驱动节点
- 检查 USB 线缆连接
- 参考 `docs/real_robot_deployment.md` 第 3 节

### 问题 5: "No obstacle points" 警告

**原因:** 激光雷达没有扫描到障碍物，或过滤太严格

**影响:** 只会走路径跟踪，避障功能失效

**排查:**
```bash
# 检查扫描范围
rosparam get /neupan_control/scan_range
# 应该是 "0.5 27.0"

# 检查下采样率
rosparam get /neupan_control/scan_downsample
# 6 是合理值，太大会过滤太多点
```

**解决:**
- 在小车周围放置障碍物（距离 0.5-5m）
- 调整 `scan_range` 和 `scan_downsample` 参数

---

## 性能监控

### 实时监控命令

```bash
# Terminal 1: 监控 NeuPAN 计算时间
# 查看 NeuPAN 终端输出，应该看到:
# "neupan forward execute time 0.023 seconds"
# 正常值: < 0.1 秒

# Terminal 2: 监控速度发布频率
rostopic hz /neupan_cmd_vel
# 应该接近 50 Hz

# Terminal 3: 监控里程计
rostopic echo /odom -n 1

# Terminal 4: 监控 CPU 使用
top -p $(pgrep -f neupan_node)
```

### 性能指标参考

| 指标 | 正常值 | 警告值 | 说明 |
|------|--------|--------|------|
| neupan forward 耗时 | <0.05s | >0.1s | 超过 0.1s 会影响实时性 |
| /cmd_vel 频率 | ~50Hz | <20Hz | 低频可能导致控制不稳定 |
| CPU 使用率 | <50% | >80% | 高 CPU 可能影响其他进程 |
| min_distance | >0.15m | <0.1m | 太小会触发 stop |

---

## 测试场景

### 场景 1: 空旷直线（基础功能）
- 目的: 验证路径跟踪
- 设置: 清空 3 米直线空间
- 预期: 平滑前进到目标点
- 参考配置: `planner_simple_test.yaml`

### 场景 2: 静态障碍物避障
- 目的: 验证避障功能
- 设置: 在路径中央 1.5m 处放置纸箱
- 预期: 绕过障碍物继续前进
- 注意: 观察 `/dune_point_markers` 和 `/nrmp_point_markers`

### 场景 3: 窄通道通过
- 目的: 验证小间隙通过能力
- 设置: 两侧放置障碍物，留出 >0.6m 通道
- 预期: 谨慎通过，不触发 stop
- 调整: 如果频繁 stop，增大 `d_min`

---

## 调试技巧

### 1. 使用 RViz 可视化

```bash
# 启动 RViz
rviz -d example/mowen/envs/real/mowen.rviz

# 添加以下 displays:
# - Path: /neupan_plan (规划路径, 绿色)
# - Path: /neupan_initial_path (初始路径, 蓝色)
# - MarkerArray: /dune_point_markers (DUNE 点, 紫色)
# - MarkerArray: /nrmp_point_markers (NRMP 点, 橙色)
# - Marker: /robot_marker (机器人轮廓, 绿色)
# - LaserScan: /scan (激光扫描)
```

### 2. 参数在线调整

```bash
# 调整参考速度
rosparam set /neupan_control/ref_speed 0.1

# 注意: planner.yaml 中的参数需要重启节点才能生效
```

### 3. 录制数据包（用于复现问题）

```bash
# 录制关键 topics
rosbag record -O test_data.bag \
    /scan /odom /cmd_vel \
    /neupan_plan /neupan_initial_path \
    /tf /tf_static

# 回放
rosbag play test_data.bag
```

---

## 安全提示

⚠️ **操作前必读：**

1. **紧急停止预案**: 保持手边有急停按钮或能快速拔掉电源
2. **测试区域**: 确保周围 2 米内无人、无贵重物品
3. **速度限制**: 首次测试建议 `ref_speed: 0.1`，逐步增加
4. **串口冲突**: 不要同时运行多个串口控制程序
5. **网络延迟**: 如果 ROS 网络延迟高（>50ms），建议在小车本地运行 NeuPAN
6. **后台进程**: 测试结束后务必检查并清理后台 `rostopic pub` 进程

---

## 成功标志

✅ 部署成功的标志：
- [ ] NeuPAN 节点正常启动，无报错
- [ ] 小车能平稳前进到目标点（误差 <0.3m）
- [ ] 遇到障碍物能主动绕行
- [ ] 速度平滑，无剧烈抖动
- [ ] min_distance 保持 >0.15m（安全距离）
- [ ] 到达目标点后自动停止

🎉 如果以上都满足，说明部署成功！可以进一步测试更复杂场景。

---

## 下一步

部署成功后可以尝试：

1. **调整避障参数**: 修改 `d_max`, `eta` 观察避障行为变化
2. **增加路径复杂度**: 测试转弯、倒车（需要 `curve_style: 'reeds'`）
3. **集成全局规划**: 接入 A* 或 RRT 作为初始路径
4. **添加上层任务**: 巡逻、跟随、自主探索

参考文档：
- 完整部署指南: `docs/real_robot_deployment.md`
- 已知问题: `docs/BUGS.md`
- 参数调优: `CLAUDE.md` 第 7.2 节
