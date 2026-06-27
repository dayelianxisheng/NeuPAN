# 任务：NeuPAN Phase 1 Docker 直线行走测试（本地电脑端）

## 背景
NeuPAN 是一个端到端 MPC 路径规划器，运行在本机的 Docker 容器中。
实体小车（mowen, 10.42.0.169）已启动所有节点：
- ✅ 激光雷达 `/scan` ~10Hz
- ✅ 轮速里程计 `/odom_raw`
- ✅ TF `odom → base_footprint → base_link → laser_link`
- ✅ `newt.py` 串口桥监听 `/cmd_vel`
- ❌ Docker daemon HTTP_PROXY 会劫持容器 apt（注意规避）

## 架构
```
本机 Docker (10.42.0.1) ─── ROS ───→ 小车 mowen (10.42.0.169)
  ROS_MASTER_URI=http://10.42.0.169:11311
  ROS_IP=10.42.0.1
```

## 测试目标
启动 neupan_node，发送直线目标点 (1, 0)，验证：
1. forward 计算耗时 < 0.1s
2. 控制频率 ~50Hz（/neupan_cmd_vel）
3. 小车平滑前进到目标点并打印 "arrive"

## 已知踩坑（必须注意）
1. **ROS 网络设 IP**：容器内必须 `export ROS_IP=10.42.0.1`
2. **waypoints 起点不能等于机器人位置**：`waypoints: [[0,0,0], [1,0,0]]` 会立即 arrive
   → 起点设在 [0.1, 0, 0] 或类似非零位置
3. **速度偏差 ~2x**：NeuPAN 闭环控制不受影响，不用管
4. **Docker daemon 代理问题**：不要用 Dockerfile build，用容器 + setup.sh 模式

## 需要执行的步骤

### 1. 确认小车端在线
```bash
# 检查能否看到小车话题
rostopic list
# 应看到：/scan, /odom_raw, /vel_raw, /cmd_vel, /tf

# 检查传感器频率
rostopic hz /scan      # 应 ~10Hz
rostopic hz /odom_raw  # 应 ~20Hz
```

### 2. 启动 Docker 容器
```bash
# 查看已有镜像
docker images | grep neupan

# 如果没有镜像，从小车scp或者本地build
# 启动容器（假设 neupan:ros1）
docker run -it --rm --net=host --name neupan_test neupan:ros1 bash
```

### 3. 容器内配置 ROS 网络
```bash
export ROS_MASTER_URI=http://10.42.0.169:11311
export ROS_IP=10.42.0.1
# 验证连接
rostopic list
```

### 4. 启动 neupan_node
根据 NeuPAN 的启动方式（可能是 roslaunch 或 python 脚本）启动规划器。
使用 `mowen_real.launch` 配置：
- map_frame=odom
- base_frame=base_link
- 确保 waypoints 不从 (0,0,0) 开始

### 5. 观察测试结果
- neupan_node 是否正常初始化
- forward 计算耗时
- /neupan_cmd_vel 发布频率
- 小车是否前进
- 是否打印 "arrive"
- 观察运动是否平滑

### 6. 记录数据
记录以下指标：
- forward 耗时: ______ s
- /neupan_cmd_vel 频率: ______ Hz
- 小车运动: □ 平滑 □ 抖动 □ 异常
- 到达目标: □ 到达 □ 未到

## 如果出问题
1. rostopic 看不到小车话题 → 检查 ROS_IP / ROS_MASTER_URI
2. neupan_node 启动报错 → 检查 GPU/CUDA、模型路径、参数配置
3. 小车不动 → 检查 /cmd_vel 是否有数据发布
4. 小车卡顿 → Bug #12，杀掉 newt.py 恢复
