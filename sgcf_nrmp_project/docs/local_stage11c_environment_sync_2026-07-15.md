# 本机 Stage 11C 环境同步记录（2026-07-15）

本文件记录 pull 到 `ec92d61` 后，本机为复现最新权威进度
`Stage 11C-D3A` 所完成的运行环境同步。这里只同步和验证环境，不重跑
Stage 11C-A 至 D3A 的正式 Gazebo / ROS 闭环 Gate。

## 当前代码与权威进度

```text
Git HEAD = ec92d61

STAGE_11C_D3A_COMPLETE_WITH_KNOWN_PLANNER_LIMITATIONS
READY_FOR_STAGE_11C_FINAL_EVALUATION_WITH_RESTRICTIONS
```

## Gazebo 环境

本机保留 Stage 11B 的 byte-identical Gazebo image object：

```text
tag = sgcf-gazebo-harmonic:hlms-media-fix
image ID = sha256:99de6309b456a206402fed9ee51a5514316433b8a922de7b91ba0e79be0974d3
Gazebo Sim = 8.14.0
SDFormat = 14.9.0
```

本次未修改或重建 Gazebo image，未启动 Gazebo。

## ROS 2 / Harmonic Bridge 环境

基础镜像：

```text
sha256:4cbeac7831833f8d6fa4cb1f9f8e22c188853468e76b3d5b9cc58148a8c8f64b
```

本机功能等价重建结果：

```text
tag = sgcf-ros2-humble-gzharmonic-bridge:local
image ID = sha256:69ec4a1e2134de8e05532386c4220e8ea4a91107b8bf1947dab4f07948af275f
ros-humble-ros-gzharmonic = 0.244.12-3jammy
ros-humble-ros-gzharmonic-bridge = 0.244.12-3jammy
runtime ROS package = ros_gz_bridge
```

另一台电脑的权威历史 bridge ID 为 `sha256:c2288bab...`。本机 ID 不同的原因是
重新构建时 Ubuntu 安全补丁和镜像元数据发生变化；安装包版本和六类 bridge
能力已重新验证，因此本记录只声明功能等价，不声明 byte-identical。

已验证转换：

```text
rosgraph_msgs/msg/Clock        <=> gz.msgs.Clock
sensor_msgs/msg/LaserScan      <=> gz.msgs.LaserScan
sensor_msgs/msg/Image          <=> gz.msgs.Image
sensor_msgs/msg/CameraInfo     <=> gz.msgs.CameraInfo
nav_msgs/msg/Odometry          <=> gz.msgs.Odometry
geometry_msgs/msg/Twist        <=> gz.msgs.Twist
```

## Planner / Torch 环境

构建基线别名在构建前已验证绑定到本机 bridge 完整 ID：

```text
sgcf-local/ros2-bridge-base:stage11cc1
→ sha256:69ec4a1e2134de8e05532386c4220e8ea4a91107b8bf1947dab4f07948af275f
```

本机功能等价重建结果：

```text
tag = sgcf-ros2-humble-gzharmonic-torch-planner:stage11cc1
image ID = sha256:450a603029c87e18550c64d19672ccb72b66395f74c254d0b098fbf8f7deb7cc
planner lock SHA256 = 796f17e191c8a843c71ca57e1e6a093f8eb6e5bfbfc89cefd0a823a878e6175d
```

历史权威 Planner image ID 为 `sha256:03f77926...`。本机以新的功能等价 bridge
为基础重建，因此 derived ID 必然不同；锁文件 hash 和数值依赖合同保持一致。

系统 ROS Python：

```text
NumPy = 1.21.5
SciPy = 1.8.0
rclpy import = PASS
```

隔离 Planner venv：

```text
Torch = 2.8.0+cu128
Torch compiled CUDA = 12.8
torch.cuda.is_available() = false
torch.cuda.device_count() = 0
NumPy = 1.26.4
SciPy = 1.13.0
OSQP = 1.1.1
CVXPY = 1.7.5
BatchedRectangleObservableOracle import = PASS
```

Planner 正式执行合同仍是 CPU only；不得给正式容器添加 `--gpus`。

## 本次未执行的内容

```text
Gazebo world runtime
ROS topic runtime Gate
非零 cmd_vel
Planner shadow mode
Planner closed loop
Stage 10 inference
Stage 11C final evaluation
```

这些结果继续由 pull 下来的历史 artifacts 提供权威证据。本次环境同步不改变、
取代或重新声明任何正式阶段结果。

## 结论

```text
LOCAL_STAGE11C_RUNTIME_ENVIRONMENT_SYNCHRONIZED
GAZEBO_BYTE_IDENTICAL_IMAGE_AVAILABLE
BRIDGE_FUNCTIONAL_EQUIVALENCE_REBUILT
PLANNER_TORCH_FUNCTIONAL_EQUIVALENCE_REBUILT
READY_TO_REPRODUCE_CURRENT_STAGE11C_D3A_BASELINE_IF_SEPARATELY_AUTHORIZED
```

这不等于开始或完成 Stage 11C Final Evaluation。
