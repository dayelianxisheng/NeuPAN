# Stage 11C-A 跨电脑交接说明

更新时间：2026-07-14（Asia/Shanghai）

> 2026-07-14 closure update: Stage 11C-A has now completed with disclosed
> runtime limitations. Sections describing the interrupted bridge-image build
> are retained as historical audit context and are superseded by
> `stage_11c_a_ros2_bridge_data_plane/stage_11c_a_report.md`.

## 1. 权威阶段状态

本机已经完成并正式关闭 Stage 11B：

```text
STAGE_11B_COMPLETE_WITH_KNOWN_RUNTIME_LIMITATIONS
GAZEBO_HEADLESS_RUNTIME_VALIDATED
SDF_SCHEMA_NORMALIZATION_VALIDATED
LIDAR_SELF_VISIBILITY_FIX_VALIDATED
EXACT_RUNTIME_GEOMETRY_VALIDATED
READY_FOR_STAGE_11C_WITH_RESTRICTIONS
```

权威决策文件：

```text
sgcf_nrmp_project/artifacts/stages/stage_11b_n_final_runtime_matrix/stage_11b_n_decision.md
```

Stage 11C-A 当前准确状态是：

```text
STAGE_11C_A_COMPLETE_WITH_KNOWN_RUNTIME_LIMITATIONS
ROS2_GAZEBO_BRIDGE_DATA_PLANE_VALIDATED
ZERO_TWIST_RUNTIME_GATE_VALIDATED
READY_FOR_STAGE_11C_B_WITH_RESTRICTIONS
```

权威报告位于：

```text
sgcf_nrmp_project/artifacts/stages/stage_11c_a_ros2_bridge_data_plane/
  stage_11c_a_report.md
  stage_11c_a_decision.md
```

Stage 11C-B 仍需独立授权后才能开始。

## 2. 另一台电脑需要追平的 Stage 11B 变更

另一台电脑如果大约停在早期 Stage 11B，必须同步本机工作区后，按权威成果确认以下迁移已经存在：

1. Stage 11B-I：机器人自身 visual 使用 `visibility_flags = 2`，GPU LiDAR 使用
   `visibility_mask = 4294967293`，轮子自身回波被隔离，外部障碍物仍可见。
2. Stage 11B-M：活动 world 中非法 `include/scale` 已全部删除。
3. `static_corridor` 和 `narrow_passage` 墙体已经显式化为
   `[5.0, 0.15, 0.5]` box。
4. `initial_collision_obstacle` 已精确显式化为 radius `0.2 m`、length
   `0.4 m` 的 cylinder，语义仍为 `HUMAN`。
5. Stage 11B-N：最终 12-world headless runtime matrix 已完成，最终状态为
   `STAGE_11B_COMPLETE_WITH_KNOWN_RUNTIME_LIMITATIONS`。

必须同步而不能只复制报告的活动代码/资产包括：

```text
sgcf_nrmp_project/gazebo/models/sgcf_diff_drive_robot/model.sdf
sgcf_nrmp_project/gazebo/scripts/generate_static_assets.py
sgcf_nrmp_project/gazebo/worlds/*.sdf
sgcf_nrmp_project/tools/finalize_stage11b*.py
sgcf_nrmp_project/tools/run_stage11b*.sh
sgcf_nrmp_project/tools/test_stage11b*.py
sgcf_nrmp_project/artifacts/stages/stage_11b_i_a_self_return_diagnosis/
sgcf_nrmp_project/artifacts/stages/stage_11b_i_b_runtime_rebaseline/
sgcf_nrmp_project/artifacts/stages/stage_11b_i_lidar_self_visibility/
sgcf_nrmp_project/artifacts/stages/stage_11b_j_full_runtime_matrix_rerun/
sgcf_nrmp_project/artifacts/stages/stage_11b_k_explicit_wall_geometry/
sgcf_nrmp_project/artifacts/stages/stage_11b_l_global_include_scale_normalization/
sgcf_nrmp_project/artifacts/stages/stage_11b_m_exact_primitive_materialization/
sgcf_nrmp_project/artifacts/stages/stage_11b_n_final_runtime_matrix/
```

Stage 11B-H/J/K/L 的阻塞报告是审计链的一部分，不能删除或改写。

## 3. 已验证的 Gazebo 运行环境

最终 Gazebo Harmonic 不可变镜像：

```text
sha256:99de6309b456a206402fed9ee51a5514316433b8a922de7b91ba0e79be0974d3
Gazebo Sim: 8.14.0
SDFormat: 14.9.0
gz-rendering ABI: 8
OGRE2 / HLMS / EGL headless: PASS
```

该 image ID 是本机本地对象标识；另一台电脑重新构建后通常不会 byte-identical。另一台电脑必须建立自己的不可变镜像基线并执行功能等价检查，不能伪造或沿用本机 image ID。

如果要搬运完全相同的镜像，可在源电脑手工执行：

```bash
docker save \
  sha256:99de6309b456a206402fed9ee51a5514316433b8a922de7b91ba0e79be0974d3 \
  -o sgcf_gazebo_harmonic_99de6309.tar
sha256sum sgcf_gazebo_harmonic_99de6309.tar \
  > sgcf_gazebo_harmonic_99de6309.tar.sha256
```

复制后在目标电脑执行：

```bash
sha256sum -c sgcf_gazebo_harmonic_99de6309.tar.sha256
docker load -i sgcf_gazebo_harmonic_99de6309.tar
docker image inspect \
  sha256:99de6309b456a206402fed9ee51a5514316433b8a922de7b91ba0e79be0974d3
```

镜像较大；如果不要求 byte-identical，建议在目标电脑按已有 Dockerfile 重建，再执行 Stage 11B-I-B 等价性审计。

## 4. Stage 11C-A 已完成的准备工作

### 4.1 现有 ROS 2 基线只读审计

本机 `ros2_dev` 对应基础 image ID：

```text
sha256:4cbeac7831833f8d6fa4cb1f9f8e22c188853468e76b3d5b9cc58148a8c8f64b
Ubuntu: 22.04.5
ROS_DISTRO: humble
Python: 3.10.12
```

审计确认：

```text
ros2 / colcon / rosdep available
ros-humble-ros-gz* not installed
ros-humble-ros-gzharmonic* not installed
no default Fortress integration conflict found
```

`ros2_dev` 没有执行 apt 安装。目标电脑必须重新进行同样的只读审计，不能假设其 image ID 或包状态一致。

### 4.2 官方包候选与依赖模拟

仅使用 Ubuntu、ROS 和 OSRF 官方仓库，候选为：

```text
ros-humble-ros-gzharmonic = 0.244.12-3jammy
removed packages = 0
downgraded packages = 0
existing package upgrades = 2
  perl-base: Ubuntu security patch
  curl: Ubuntu security patch
```

依赖模拟约有 904 个新包。它是大型官方元包，会带入 bridge、image、interfaces、Harmonic transport/messages 及其必需依赖，因此首次构建下载量很大。

本机依赖证据位于：

```text
sgcf_nrmp_project/artifacts/stages/stage_11c_a_ros2_bridge_data_plane/logs/
  package_policy.txt
  package_show.txt
  dependency_simulation.txt
  dependency_apt_update.log
  base_packages.txt
```

### 4.3 已新增但尚未运行验证的文件

```text
docker/ros2_humble_gzharmonic_bridge/
sgcf_nrmp_project/ros2_ws/src/sgcf_nrmp_bridge/
```

这些文件只是 Stage 11C-A 的初始实现，特别是以下内容尚未经过安装后的类型注册表和 runtime Gate 验证：

```text
stage11ca_bridge.yaml
stage11ca_bridge.launch.py
```

不得把其中的 Gazebo message type 或 bridge YAML 语法视为权威结果。必须在 bridge 镜像构建后用实际安装包的 `parameter_bridge --help`、类型注册信息和最小启动结果确认。

## 5. 当前中断点

专用 bridge 镜像的构建命令是：

```bash
docker build \
  -t sgcf-ros2-humble-gzharmonic-bridge:local \
  docker/ros2_humble_gzharmonic_bridge
```

第一次构建曾因 BuildKit 不接受裸 local image ID 作为 `FROM` 而失败。随后建立了阶段专用本地别名：

```text
sgcf-ros2-humble-base:4cbeac7831833
→ sha256:4cbeac7831833f8d6fa4cb1f9f8e22c188853468e76b3d5b9cc58148a8c8f64b
```

Dockerfile 当前使用该别名，构建前必须再次校验它解析到完整基础 ID。这个别名不是跨电脑可移植的；目标电脑必须根据自身通过审计的 immutable ROS base image 创建对应别名，并记录映射。

第二次构建在下载官方依赖时被用户中断，最后日志停在约第 374 个下载包。尚未确认生成 bridge image，因此当前应视为：

```text
BRIDGE_IMAGE_BUILD_INCOMPLETE
```

日志：

```text
sgcf_nrmp_project/artifacts/stages/stage_11c_a_ros2_bridge_data_plane/logs/bridge_image_build.log
```

目标电脑可以重新构建；Docker layer/package cache 是否能复用取决于目标电脑本地状态。

## 6. 目标电脑推荐追平顺序

### 步骤 A：同步工作区

当前本机工作区的已提交基线可通过 Git 同步。若需要同步尚未提交的
Stage 11C-A 收束文件或本地 runtime 原始证据，可使用 `rsync`，并明确排除
Git 元数据和大权重：

```bash
rsync -aH --info=progress2 \
  --exclude='.git/' \
  --exclude='*.pt' \
  --exclude='*.pth' \
  --exclude='*.ckpt' \
  --exclude='*.onnx' \
  --exclude='__pycache__/' \
  /home/qcqc/resource/code/eai/NeuPAN/ \
  USER@TARGET:/path/to/NeuPAN/
```

实验报告、JSON、日志、world、生成器和测试不得排除。不要使用 `--delete`，避免误删目标电脑独有数据。

同步后在两台电脑分别保存：

```bash
git status --short > git_status_after_sync.txt
git diff --check
```

### 步骤 B：确认 Stage 11B 最终资产

```bash
grep -R '<include' -n sgcf_nrmp_project/gazebo/worlds
grep -R '<scale>' -n sgcf_nrmp_project/gazebo/worlds \
  sgcf_nrmp_project/gazebo/models
python3 -m unittest sgcf_nrmp_project.tools.test_stage11bn
```

注意：第二条可能发现合法 mesh scale；验收对象是 `include/scale = 0`，不能粗暴删除合法 mesh scale。

读取并确认：

```text
stage_11b_n_final_runtime_matrix/stage_11b_n_decision.md
stage_11b_n_final_runtime_matrix/stage11bn_frozen_asset_audit.json
```

### 步骤 C：恢复或重建 Gazebo 环境

若未搬运镜像，按 `docker/gazebo_harmonic/` 重建，然后重做不可变 ID 和功能等价审计。禁止仅因版本字符串相同就跳过 OGRE2/HLMS/EGL、empty-world smoke 和进程清理检查。

### 步骤 D：重新审计目标电脑 ROS2 基线

```bash
docker inspect ros2_dev
docker image inspect "$(docker inspect ros2_dev --format '{{.Image}}')"
docker exec ros2_dev bash -lc '
  set -e
  source /opt/ros/humble/setup.bash
  echo "ROS_DISTRO=$ROS_DISTRO"
  python3 --version
  dpkg-query -W | grep -E "ros-humble-ros-(gz|gzharmonic)|gz-|ignition" || true
'
```

只读检查；不得在 `ros2_dev` 中安装。

若 base image object 不存在或包含默认 Fortress / 冲突 ros_gz 包，按协议停止为：

```text
BLOCKED_ROS2_BASE_IMAGE_UNSUITABLE
或
BLOCKED_ROS_GZ_PACKAGE_CONFLICT
```

### 步骤 E：重新做 apt 候选与模拟

在一次性容器中添加 OSRF 官方源，执行：

```bash
apt-cache policy ros-humble-ros-gzharmonic
apt-cache show ros-humble-ros-gzharmonic
apt-get -s install --no-install-recommends ros-humble-ros-gzharmonic
```

必须确认 `removed = 0`、`downgraded = 0`，并保存完整输出。不得改用第三方镜像站或源码编译。

### 步骤 F：构建并冻结 bridge image

1. 为目标电脑审核通过的 ROS base image 创建阶段专用本地别名。
2. 校验别名解析到预期完整 ID。
3. 构建 `sgcf-ros2-humble-gzharmonic-bridge:local`。
4. 记录构建后完整 bridge image ID 和所有安装包版本。
5. 后续正式容器只使用构建后的完整 image ID，不使用可变 tag。

### 步骤 G：安装后能力审计

在 bridge image 内检查实际包名和可执行文件，不得依赖当前草稿猜测：

```bash
source /opt/ros/humble/setup.bash
ros2 pkg list | grep -E 'ros_(gz|gzharmonic)'
ros2 pkg executables | grep -E 'ros_(gz|gzharmonic)'
ros2 run <实际_bridge_package> parameter_bridge --help
```

确认 Clock、LaserScan、Image、CameraInfo、Odometry、Twist 六类转换全部注册。任一核心类型缺失时立即停止为：

```text
BLOCKED_REQUIRED_BRIDGE_TYPE_UNSUPPORTED
```

只有此步骤通过后，才能修正并冻结 bridge YAML/launch。

### 步骤 H：完成 Stage 11C-A runtime Gate

只运行 `empty_world`：

```text
Gazebo container: immutable Gazebo image ID
Bridge container: immutable new bridge image ID
network: host
GZ_PARTITION: sgcf_stage11ca
ROS_DOMAIN_ID: 42
```

严格顺序：Gazebo → 自动发现 Gazebo topic/type → bridge → ROS audit node → 采集消息 → 仅一次 zero Twist → 清理。

本机最终 Gate 已达到：

```text
/clock = 6391 (required >= 50)
/scan = 34 (required >= 20)
/camera/image_raw = 11 (required >= 5)
/camera/camera_info = 1 (required >= 1)
/odom = 52 (required >= 20)
```

只允许 zero Twist。不得发送非零命令、启动 Planner、Stage 10、Nav2、RViz、ROS bridge 以外的闭环组件。

最终采用的带限制结论是：

```text
STAGE_11C_A_COMPLETE_WITH_KNOWN_RUNTIME_LIMITATIONS
ROS2_GAZEBO_BRIDGE_DATA_PLANE_VALIDATED
ZERO_TWIST_RUNTIME_GATE_VALIDATED
READY_FOR_STAGE_11C_B_WITH_RESTRICTIONS
```

## 7. 不要同步或误用的内容

- 不要把当前未完成的 bridge build log 当作成功证据。
- 不要把本机 Docker image ID 假定为目标电脑重建后的 ID。
- 不要修改已有 `ros2_dev` 容器。
- 不要把 ROS 包安装进 Stage 11B Gazebo 镜像。
- 不要通过可变 tag 启动正式 Gate。
- 不要覆盖 Stage 11B-H/J/K/L 的阻塞报告。
- 不要过滤实验过程 artifacts；仅权重和系统/缓存文件可排除。
- 不要执行 `git reset`、`git clean` 或带 `--delete` 的同步。

## 8. 目标电脑开始工作前的最小检查清单

```text
[ ] 工作区及 Stage 11B artifacts 已同步
[ ] Stage 11B-N 决策已读取
[ ] active include/scale = 0
[ ] robot visibility_flags = 2
[ ] LiDAR visibility_mask = 4294967293
[ ] Gazebo Harmonic 功能等价环境通过
[ ] ROS2 base image object 存在且无冲突包
[ ] apt 模拟无卸载、无降级
[ ] bridge image 构建成功并冻结完整 ID
[ ] 六种 bridge 类型由安装包实证支持
[ ] 只运行 empty_world
[ ] 只发送 zero Twist
[ ] Planner / Stage 10 / Nav2 / RViz 未启动
[ ] 所有容器和 Gazebo/ROS bridge 进程清理完成
```
