# 新小车部署文件索引

本目录包含 mowen 新小车的简化部署配置，专注于**直线走 + 基础避障**功能验证。

## 📁 文件列表

### 🚀 快速上手（推荐从这里开始）

| 文件 | 用途 | 使用场景 |
|------|------|---------|
| **`QUICKSTART.md`** | **5分钟快速上手指南** | 第一次部署，快速验证功能 |
| **`quick_check.sh`** | **自动化环境检查脚本** | 部署前快速检查所有依赖 |
| **`test_simple_straight.launch`** | **简化测试 launch 文件** | 启动 NeuPAN 节点（保守配置） |
| **`planner_simple_test.yaml`** | **简化测试参数配置** | 低速、高安全裕度的参数 |
| **`test_simple_move.py`** | **自动化测试脚本** | 运行预定义的测试序列 |

### 📖 参考文档

| 文件 | 内容 |
|------|------|
| **`DEPLOYMENT_CHECKLIST.md`** | 详细的部署检查清单、故障排查、调试技巧 |
| `mowen_real.launch` | 原始配置（更快速度，用于复杂场景） |
| `planner.yaml` | 原始参数配置 |
| `robot_minimal.launch` | 小车端最小化启动配置（参考模板） |
| `move.py` | 巡逻任务脚本（原始版本） |
| `mowen.rviz` | RViz 可视化配置 |

---

## 🎯 快速开始

### 第 1 步: 阅读快速指南
```bash
cat QUICKSTART.md  # 5分钟快速上手指南
```

### 第 2 步: 环境检查
```bash
./quick_check.sh  # 自动检查所有依赖项
```

### 第 3 步: 启动测试
```bash
# 小车端（SSH 登录小车执行）
roslaunch <workspace>/robot_minimal.launch

# 控制端（本地执行）
roslaunch neupan_ros test_simple_straight.launch
python3 test_simple_move.py
```

---

## 📊 配置对比

| 特性 | 简化配置 | 原始配置 |
|------|---------|---------|
| **Launch 文件** | `test_simple_straight.launch` | `mowen_real.launch` |
| **参数文件** | `planner_simple_test.yaml` | `planner.yaml` |
| **参考速度** | 0.15 m/s | 0.2 m/s |
| **最大速度** | [0.2, 0.2] | [0.5, 0.5] |
| **碰撞阈值** | 0.12 m | 0.1 m |
| **安全距离** | d_max=1.2, d_min=0.15 | d_max=1.0, d_min=0.1 |
| **测试路径** | 0→3米 直线 | 0.9→2.0米 |
| **适用场景** | 首次部署、功能验证 | 日常使用、复杂场景 |

**建议:** 首次部署使用简化配置，验证成功后切换到原始配置。

---

## 🔧 常用命令速查

### 环境检查
```bash
# 检查 ROS 连接
rostopic list

# 检查 TF 树
rosrun tf tf_echo odom base_link

# 检查激光雷达
rostopic hz /scan

# 运行自动化检查
./quick_check.sh
```

### 启动节点
```bash
# 简化配置（推荐首次使用）
roslaunch neupan_ros test_simple_straight.launch

# 原始配置
roslaunch neupan_ros mowen_real.launch
```

### 发送目标
```bash
# 使用自动化脚本
python3 test_simple_move.py

# 手动发送目标点
rostopic pub /move_base_simple/goal geometry_msgs/PoseStamped \
  "header: {frame_id: 'odom'}
   pose: {position: {x: 2.0, y: 0.0, z: 0.0}, orientation: {w: 1.0}}"
```

### 紧急停止
```bash
# 方法 1: 杀掉后台进程
pkill -f "rostopic pub"

# 方法 2: 发送零速度
rostopic pub -1 /cmd_vel geometry_msgs/Twist "{}"
```

### 可视化
```bash
# 启动 RViz
rviz -d mowen.rviz

# 监控速度输出
rostopic echo /neupan_cmd_vel

# 监控规划路径
rostopic echo /neupan_plan
```

---

## ⚠️ 重要提示

### 安全第一
1. ✅ 首次测试务必使用简化配置（低速、高安全裕度）
2. ✅ 保持 2 米安全距离，准备急停方案
3. ✅ 每次测试结束后检查并清理后台 `rostopic pub` 进程
4. ✅ 不要同时运行多个串口控制程序

### 已知问题
- **近点误触发 stop**: 过滤 <0.5m 的激光点 (`scan_range: [0.5, 27.0]`)
- **后台进程失控**: 定期检查 `ps aux | grep "rostopic pub"`
- **串口冲突**: `sudo fuser -k /dev/carserial` 清理占用

详细问题列表请查看 `../../docs/BUGS.md`

---

## 📚 进一步学习

- **理解工作原理**: 阅读项目根目录 `CLAUDE.md`
- **完整部署指南**: `../../docs/real_robot_deployment.md`
- **参数调优**: `CLAUDE.md` 第 7.2 节
- **DUNE 训练**: `../../example/dune_train/`

---

## 🆘 获取帮助

**遇到问题时的排查顺序:**
1. 运行 `./quick_check.sh` 检查环境
2. 查看 `../../docs/BUGS.md` 中是否有相同问题
3. 检查 NeuPAN 和小车端终端的完整输出
4. 参考 `DEPLOYMENT_CHECKLIST.md` 中的故障排查部分

**成功标志:**
- ✅ 小车能平稳前进到目标点（误差 <0.3m）
- ✅ 遇到障碍物能主动绕行
- ✅ 速度平滑无抖动
- ✅ 到达目标后自动停止

祝部署顺利！🎉
