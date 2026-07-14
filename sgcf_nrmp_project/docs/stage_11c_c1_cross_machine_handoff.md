# Stage 11C-C1 跨机器交接说明

更新时间：2026-07-15（Asia/Shanghai）

这份说明用于在另一台电脑上重建 `Stage 11C-C1` 的 Planner Runtime 环境。
当前本机已经完成并冻结了以下权威状态：

```text
STAGE_11C_C1_COMPLETE
CUDA_CAPABLE_TORCH_RUNTIME_IMAGE_FROZEN
CPU_ONLY_PLANNER_EXECUTION_VALIDATED
DUAL_NUMERICAL_STACK_ISOLATION_VALIDATED
TORCH_BACKED_EXACT_GEOMETRY_VALIDATED
CORE_PLANNER_CPU_REPLAY_EQUIVALENCE_VALIDATED
ROS2_PLANNER_RUNTIME_COEXISTENCE_VALIDATED
READY_TO_RESTART_STAGE_11C_C_SHADOW_MODE
```

权威成果文件：

- [stage_11c_c1_report.md](../artifacts/stages/stage_11c_c1_torch_planner_runtime/stage_11c_c1_report.md)
- [stage_11c_c1_decision.md](../artifacts/stages/stage_11c_c1_torch_planner_runtime/stage_11c_c1_decision.md)
- [stage11cc1_final_image_manifest.json](../artifacts/stages/stage_11c_c1_torch_planner_runtime/stage11cc1_final_image_manifest.json)
- [stage11cc1_core_planner_replay_equivalence.json](../artifacts/stages/stage_11c_c1_torch_planner_runtime/stage11cc1_core_planner_replay_equivalence.json)
- [stage11cc1_cpu_runtime_performance.json](../artifacts/stages/stage_11c_c1_torch_planner_runtime/stage11cc1_cpu_runtime_performance.json)

## 1. 这次环境到底是什么

本阶段的目标不是装一个“通用训练环境”，而是构建一个可用于正式 Planner
离线验收的运行镜像。它的核心特点是：

- 基础层来自已验证的 Bridge 镜像；
- 系统 ROS Python 环境保持不变；
- Planner 的数值依赖放在独立 venv；
- Torch 使用 CUDA-capable wheel `2.8.0+cu128`；
- 正式执行仍然必须在 CPU 上完成；
- 不运行 Gazebo，不启动 `Stage 10`，不加载 checkpoint。

当前这台机器上的权威镜像信息如下：

```text
Base Bridge image ID:
sha256:c2288babf5595cdf3caafcd23fd68de2714863b5132ffb10b3cbd10006ca2862

Derived Planner image ID:
sha256:03f77926ea1b97cc460ca2d5893abb1b26d3b68984d53f9e98e707994841cff5

Planner lock SHA256:
796f17e191c8a843c71ca57e1e6a093f8eb6e5bfbfc89cefd0a823a878e6175d

Locked wheel count:
36
```

## 2. 目标电脑需要满足什么

目标电脑至少需要：

- Linux `amd64`
- Docker Engine
- 可用的 `buildx` / BuildKit
- 能访问官方 `PyPI` 和 `PyTorch cu128` wheel 源
- 足够的磁盘空间，Planner image 约 `6.1 GB`

不需要：

- GPU
- NVIDIA Container Runtime
- 额外的 ROS 安装
- 手工安装 Torch / NumPy / SciPy 到宿主机

## 3. 两种追平方式

### 方式 A：字节级复现

如果目标电脑能拿到本机已验证的 Bridge 基础镜像 tar，就可以尽量保持同一条镜像血缘。

源电脑导出：

```bash
docker save \
  sha256:c2288babf5595cdf3caafcd23fd68de2714863b5132ffb10b3cbd10006ca2862 \
  -o sgcf_bridge_stage11cc1_base.tar
```

目标电脑导入：

```bash
docker load -i sgcf_bridge_stage11cc1_base.tar
```

然后为本地构建创建固定别名：

```bash
docker tag \
  sha256:c2288babf5595cdf3caafcd23fd68de2714863b5132ffb10b3cbd10006ca2862 \
  sgcf-local/ros2-bridge-base:stage11cc1

docker image inspect \
  sgcf-local/ros2-bridge-base:stage11cc1 \
  --format '{{.Id}}'
```

只有当输出仍然是上面的完整 `sha256:c228...` 时，这个别名才可用于
`Stage 11C-C1` 的正式 Dockerfile。

### 方式 B：功能等价重建

如果拿不到本机的 Bridge tar，就按仓库里的 Dockerfile 重新构建。
这会得到功能等价环境，但 derived image ID 不一定和本机完全一致。

这时仍然要先让目标电脑自己的 Bridge 基础镜像通过审计，再创建本地别名。

关键约束是：

- Dockerfile 不能直接写裸 `sha256:...` 作为 `FROM`
- 必须使用本地别名 `sgcf-local/ros2-bridge-base:stage11cc1`
- 不能把它当成远程仓库名

## 4. 构建顺序

在目标电脑上，建议按下面顺序执行。

### 4.1 检查本地基础镜像

```bash
docker image inspect \
  sgcf-local/ros2-bridge-base:stage11cc1 \
  --format '{{.Id}} {{.Os}}/{{.Architecture}}'
```

期望：

```text
linux/amd64
```

### 4.2 构建 Planner Runtime 镜像

在仓库根目录执行：

```bash
docker build --progress=plain \
  -t sgcf-ros2-humble-gzharmonic-torch-planner:stage11cc1 \
  docker/ros2_humble_gzharmonic_torch_planner
```

这一步会：

- 安装最小系统包 `python3.10-venv`
- 创建 `/opt/sgcf_planner_venv`
- 按 `planner_runtime_requirements.lock` 安装 36 个锁定 wheel
- 保持系统 ROS Python 环境不变

## 5. 运行时合同

正式运行时必须满足：

```text
CUDA_VISIBLE_DEVICES=""
NVIDIA_VISIBLE_DEVICES=void
```

镜像入口已经负责设置这些变量。正式执行不使用 `--gpus`。

Torch 是 CUDA-capable 版本，但 Planner 的实际执行设备仍然必须是 CPU。

### 系统 Python 环境

目标是保留：

- `numpy == 1.21.5`
- `scipy == 1.8.0`
- `rclpy` 可导入

### Planner venv

目标是保留：

- `numpy == 1.26.4`
- `scipy == 1.13.0`
- `osqp == 1.1.1`
- `torch == 2.8.0+cu128`

## 6. 目标电脑上的验收命令

### 6.1 系统 ROS 环境

```bash
docker run --rm --network none \
  sgcf-ros2-humble-gzharmonic-torch-planner:stage11cc1 \
  /usr/bin/python3 -c 'import rclpy,numpy,scipy; print(numpy.__version__, scipy.__version__)'
```

期望：

```text
1.21.5 1.8.0
```

### 6.2 Planner venv

```bash
docker run --rm --network none \
  sgcf-ros2-humble-gzharmonic-torch-planner:stage11cc1 \
  python -c 'import torch,numpy,scipy,osqp,cvxpy; print(torch.__version__, torch.version.cuda, torch.cuda.is_available(), torch.cuda.device_count())'
```

期望：

```text
2.8.0+cu128
false
0
```

### 6.3 CPU 执行合同

```bash
docker run --rm --network none \
  -e CUDA_VISIBLE_DEVICES= \
  -e NVIDIA_VISIBLE_DEVICES=void \
  sgcf-ros2-humble-gzharmonic-torch-planner:stage11cc1 \
  python -c 'import torch; print(torch.cuda.is_available(), torch.cuda.device_count())'
```

期望：

```text
False 0
```

## 7. 你应该重点看哪些文件

如果目标电脑只是要“把环境搭起来”，优先看这些文件：

- [docker/ros2_humble_gzharmonic_torch_planner/Dockerfile](../../docker/ros2_humble_gzharmonic_torch_planner/Dockerfile)
- [docker/ros2_humble_gzharmonic_torch_planner/README.md](../../docker/ros2_humble_gzharmonic_torch_planner/README.md)
- [docker/ros2_humble_gzharmonic_torch_planner/install_validation.md](../../docker/ros2_humble_gzharmonic_torch_planner/install_validation.md)
- [docker/ros2_humble_gzharmonic_torch_planner/runtime_entrypoint.sh](../../docker/ros2_humble_gzharmonic_torch_planner/runtime_entrypoint.sh)
- [docker/ros2_humble_gzharmonic_torch_planner/planner_runtime_requirements.lock](../../docker/ros2_humble_gzharmonic_torch_planner/planner_runtime_requirements.lock)
- [docker/ros2_humble_gzharmonic_torch_planner/dependency_source_manifest.json](../../docker/ros2_humble_gzharmonic_torch_planner/dependency_source_manifest.json)

## 8. 常见坑

- 不要在 `FROM` 里直接写 `sha256:...` 裸 ID。
- 不要把 `sgcf-local/ros2-bridge-base:stage11cc1` 当成远程镜像名。
- 不要在正式验证时暴露 GPU。
- 不要改系统 ROS 的 NumPy / SciPy。
- 不要把 TorchVision、Torchaudio、Stage 10 checkpoint 混进这个镜像。
- 如果目标电脑重新构建了 Bridge 基础镜像，derived image ID 会变，这不等于环境失败。

## 9. 结论

这套环境在另一台电脑上的正确追平方式是：

1. 先拿到或重建可审计的 Bridge 基础镜像；
2. 为它创建本地别名 `sgcf-local/ros2-bridge-base:stage11cc1`；
3. 用仓库内的 `docker/ros2_humble_gzharmonic_torch_planner/Dockerfile` 构建 Planner Runtime 镜像；
4. 用上面的系统 Python、Planner venv 和 CPU 执行合同做验证。

如果你要的是“和当前机器完全一致的 image ID”，就必须先导入当前这台机器导出的基础镜像 tar。
