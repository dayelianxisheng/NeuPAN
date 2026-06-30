# Fast-LIO + NeuPAN 部署框架

## 架构

```
小车端（Ubuntu 18.04 / ROS Melodic）
┌─────────────────────────────────────────────┐
│  LiDAR (镭神 N10)    IMU (WIT)              │
│       │                  │                   │
│       └────────┬─────────┘                   │
│                │                              │
│         Fast-LIO (定位)                       │
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
├── config/
│   ├── planner.yaml        # NeuPAN 规划参数（已配置）
│   └── fast_lio.yaml       # TODO: Fast-LIO 参数
├── launch/
│   └── fast_lio_neupan.launch  # 主 launch 文件（NeuPAN 已配置）
├── scripts/
│   └── start_car.sh        # 小车端启动脚本（Fast-LIO 部分待填充）
└── rviz/
    └── fast_lio_neupan.rviz    # RViz 配置模板
```

## TODO

### 1. Fast-LIO 安装编译
- [ ] 小车端 clone: `git clone https://github.com/hku-mars/FAST_LIO.git`
- [ ] 配置 LiDAR 型号（镭神 N10 → Livox 格式适配）
- [ ] 编译: `catkin_make` 或 `catkin build`

### 2. Fast-LIO 参数配置
- [ ] 填写 `config/fast_lio.yaml`（LiDAR 参数 + IMU 外参）
- [ ] 标定 LiDAR→IMU 外参
- [ ] 调试点云配准效果

### 3. Launch 集成
- [ ] 在 `fast_lio_neupan.launch` 中取消 Fast-LIO 注释并接入
- [ ] 验证 TF 树: `odom (Fast-LIO) → base_link → laser_link`
- [ ] 测试话题连通性: `/odom` → NeuPAN 正确接收

### 4. 路径规划接口
- [ ] 决定全局路径提供方式:
  - 手动 waypoints（写入 planner.yaml）
  - 外部路径规划（订阅 `/neupan_goal` 并调用 `set_initial_path()`）
  - RViz 2D Nav Goal 交互

### 5. 实车测试
- [ ] 空载直线行走测试
- [ ] 带 Fast-LIO 定位的闭环路径跟踪
- [ ] 避障测试

## 快速启动

```bash
# 1. 小车端
cd ~/neupan_ws/src/NeuPAN/example/mowen/deploy/fast_lio_neupan/scripts
./start_car.sh

# 2. Docker 端
export ROS_MASTER_URI=http://10.42.0.169:11311
export ROS_IP=10.42.0.1
bash deploy/scripts/deploy.sh fast_lio
```
