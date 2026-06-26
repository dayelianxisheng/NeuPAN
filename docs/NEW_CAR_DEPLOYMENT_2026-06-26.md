# NeuPAN 新小车部署配置更新

**日期**: 2026-06-26  
**目标**: 为 mowen 新小车准备简化的部署配置，专注于**直线走 + 基础避障**功能验证

---

## 🎯 更新概要

为新小车部署准备了完整的简化配置和文档，包括：
- ✅ 保守参数的测试配置（低速、高安全裕度）
- ✅ 自动化测试脚本和环境检查工具
- ✅ 详细的快速上手指南和故障排查文档
- ✅ 基于已知问题的预防措施

---

## 📦 新增文件

位置: `example/mowen/envs/real/`

### 核心部署文件（⭐ 必读）

1. **`QUICKSTART.md`** ⭐
   - 5分钟快速上手指南
   - 推荐首次部署时阅读

2. **`test_simple_straight.launch`** ⭐
   - 简化测试 launch 文件
   - 低速保守配置

3. **`planner_simple_test.yaml`** ⭐
   - 简化参数配置
   - 速度降低25-60%，安全距离增大

4. **`test_simple_move.py`** ⭐
   - Python 自动化测试脚本
   - 测试序列: 前进→避障→返回

5. **`quick_check.sh`** ⭐
   - Bash 自动化环境检查
   - 8项关键检查

### 参考文档

6. **`README.md`**
   - 文件索引和导航

7. **`DEPLOYMENT_CHECKLIST.md`**
   - 详细的部署检查清单
   - 11个常见问题排查

8. **`DEPLOYMENT_SUMMARY.md`**
   - 本次更新的完整总结

---

## 🔧 关键改进

### 参数对比

| 参数 | 简化配置 | 原始配置 | 改进原因 |
|------|---------|---------|---------|
| `ref_speed` | 0.15 m/s | 0.2 m/s | 降低25%，提高安全性 |
| `max_speed` | [0.2, 0.2] | [0.5, 0.5] | 降低60%，避免失控 |
| `collision_threshold` | 0.12 m | 0.1 m | 增加20%安全裕度 |
| `d_max` | 1.2 m | 1.0 m | 更早开始避障 |
| `d_min` | 0.15 m | 0.1 m | 保持更大安全间距 |
| `scan_range` | [0.5, 27.0] | 相同 | 明确过滤近点防误停 |

### 安全改进

1. **预防近点误停** (BUGS.md #3)
   - `scan_range: [0.5, 27.0]` 过滤 <0.5m 点
   - 避免 LiDAR 近点触发 stop

2. **检测后台进程冲突** (BUGS.md #10)
   - `quick_check.sh` 自动检测遗留的 `rostopic pub` 进程
   - 防止小车失控

3. **保守参数设置**
   - 低速启动，避免首次测试失控
   - 安全距离增大，留出更多反应时间

---

## 📋 快速开始

```bash
# Step 1: 阅读快速指南
cd example/mowen/envs/real
cat QUICKSTART.md

# Step 2: 环境检查
./quick_check.sh

# Step 3: 部署（3步流程见 QUICKSTART.md）
# 小车端: roslaunch <workspace>/robot_minimal.launch
# 控制端: roslaunch neupan_ros test_simple_straight.launch
# 测试: python3 test_simple_move.py
```

---

## 📚 文档导航

- **快速上手**: `example/mowen/envs/real/QUICKSTART.md`
- **详细检查清单**: `example/mowen/envs/real/DEPLOYMENT_CHECKLIST.md`
- **文件索引**: `example/mowen/envs/real/README.md`
- **完整总结**: `example/mowen/envs/real/DEPLOYMENT_SUMMARY.md`

现有文档（参考）：
- **完整部署指南**: `docs/real_robot_deployment.md`
- **已知问题**: `docs/BUGS.md`（14个问题）
- **项目文档**: `CLAUDE.md`

---

## ✅ 验证标准

部署成功的标志：
- ✅ NeuPAN 正常启动，无 "waiting for tf" 报错
- ✅ 小车能平稳前进到目标点（误差 <0.3m）
- ✅ 遇到障碍物能主动绕行
- ✅ 速度平滑无抖动
- ✅ 到达目标后自动停止
- ✅ min_distance 保持 >0.15m

---

## ⚠️ 重要提示

1. **首次测试必用简化配置**
   - 使用 `test_simple_straight.launch`
   - 不要直接用 `mowen_real.launch`（速度快）

2. **安全预案**
   - 保持2米安全距离
   - 准备急停方案（拔电源或按钮）
   - 每次测试结束检查后台进程

3. **渐进式测试**
   - 先验证直线走
   - 再测试避障
   - 最后切换到原始配置

---

## 🎓 学习路径

1. **今天**: 阅读 `QUICKSTART.md` + 运行 `quick_check.sh` + 3步部署
2. **明天**: 阅读 `CLAUDE.md` + `docs/real_robot_deployment.md`
3. **后续**: 参数调优 + 复杂场景测试

---

## 📊 工作量

- **新增文件**: 8个（~1500行代码+文档）
- **测试覆盖**: 基础功能（直线走+避障）
- **文档完整度**: 快速上手 + 详细排查 + API参考

---

## 🔄 与原配置的关系

- **不影响原配置**: 原有 `mowen_real.launch` 和 `planner.yaml` 保持不变
- **渐进式过渡**: 先用简化配置验证，再切换到原始配置
- **兼容性**: 使用相同的 DUNE 模型和 ROS 接口

---

## 🆘 获取帮助

遇到问题时：
1. 运行 `./quick_check.sh`
2. 查看 `docs/BUGS.md`
3. 参考 `DEPLOYMENT_CHECKLIST.md`

---

**准备就绪！现在可以开始部署新小车了。** 🚀

首次部署建议从 `example/mowen/envs/real/QUICKSTART.md` 开始阅读。
