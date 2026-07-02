# Fast-LIO + NeuPAN 部署框架

## 架构

```
小车端（Ubuntu 18.04 / ROS Melodic）
┌─────────────────────────────────────────────┐
│  LiDAR (镭神 N10)    IMU (WitMotion)        │
│       │                  │                   │
│       └────────┬─────────┘                   │
│                │                              │
│         Fast-LIO2 (定位)                      │
│                │                              │
│            /odom (位姿)                       │
│                │                              │
│  NeuPAN (导航避障) ──→ /cmd_vel ──→ 串口桥    │
│         ↑                                    │
│    /move_base_simple/goal (目标点)             │
└─────────────────────────────────────────────┘
         ↑ ROS network (10.42.0.x)
┌─────────────────────────────────────────────┐
│  Docker 端（开发机）                          │
│  - RViz 可视化                                │
│  - 发送导航目标点                              │
└─────────────────────────────────────────────┘
```

## 与其它模式对比

| 模式 | 定位方式 | 全局路径 | 适用场景 |
|------|---------|---------|---------|
| `pure_neupan` | 轮式里程计 | 手动 waypoints | 已知简单路径 |
| `astar_neupan` | AMCL + 地图 | A* 规划 | 已建图固定环境 |
| `fast_lio_neupan` | Fast-LIO (LiDAR+IMU) | 无 (需外部提供) | 未知环境、快速部署 |

## 文件结构

```
deploy/fast_lio_neupan/
├── FAST_LIO_DEPLOY.md          # 本文件
├── config/
│   ├── planner.yaml            # NeuPAN 规划参数
│   └── fast_lio.yaml           # Fast-LIO2 参数（需根据设备标定）
├── launch/
│   └── fast_lio_neupan.launch  # 主 launch 文件
├── scripts/
│   └── start_car.sh            # 小车端启动脚本
└── rviz/
    └── fast_lio_neupan.rviz    # RViz 配置
```

## 安装 Fast-LIO2（小车端）

```bash
# 1. 克隆并编译（小车端）
cd ~
git clone https://github.com/hku-mars/FAST_LIO.git fast_lio_ws
cd fast_lio_ws
catkin_make
source devel/setup.bash

# 2. 检查 LiDAR 话题
rostopic echo /lslidar_point_cloud -n1 --noarr | head -5

# 3. 检查 IMU 话题
rostopic echo /wit/imu -n1 | head -5
```

## LiDAR-IMU 外参标定

Fast-LIO 需要 LiDAR 到 IMU 的外参（旋转+平移）。
修改 `config/fast_lio.yaml` 中的 `extrinsic_T` 参数。

参考标定方法：
1. 使用 [LiDAR_IMU_Calib](https://github.com/APRIL-ZJU/lidar_IMU_calib)
2. 或者根据机械安装尺寸手动测量

## 日常使用

### 小车端
```bash
~/neupan_ws/src/NeuPAN/example/mowen/deploy/fast_lio_neupan/scripts/start_car_pure.sh
```

### Docker 端
```bash
export ROS_MASTER_URI=http://10.42.0.169:11311
export ROS_IP=10.42.0.1
bash /root/neupan_ws/src/NeuPAN/example/mowen/deploy/scripts/deploy.sh fast_lio
```

### RViz 操作
1. 确认 Fast-LIO 点云和 TF 正常
2. **2D Nav Goal** → 设置目标点
3. NeuPAN 自动规划路径并导航

## 调试

```bash
# 查看 Fast-LIO 定位
rostopic echo /odom -n1 | head -10

# 查看 TF 树
rosrun tf view_frames

# 检查 Fast-LIO 点云
rostopic hz /lslidar_point_cloud
```
