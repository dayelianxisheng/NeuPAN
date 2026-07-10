# SC-NeuPAN 工程设计与分阶段实施方案（V3）

> **目标**：在不修改 NeuPAN 原始源码的前提下，实现“视觉分割 + LiDAR 点云染色 + 语义感知局部规划”，先完成可独立测试的核心算法，再接入 ROS2，最后在 Gazebo 场景中完成闭环验证。  
> **审计对象**：当前上传的 NeuPAN 工程。  
> **根仓库提交**：`f254c54daff2e7fdcdeb34754859fc4f1f5aa407`  
> **ROS1 子仓库提交**：`b3ec0cb86f83ee1f8bf1c727d208a1f3c06e7b36`  
> **ROS2 子仓库提交**：`4ffb7ec2dc45ff7ee9024f64083813237906af98`  
> **状态说明**：上传版本仍包含未提交的 DeepSeek 修改。本方案假设这些修改会先被删除或恢复，之后再开始新功能开发。

---

# 1. 最终技术路线结论

## 1.1 核心结论

本项目采用以下技术路线：

- **NeuPAN 原始目录保持只读**；
- 在项目根目录新增独立的 `sc_neupan_core`；
- 核心算法与 ROS、Gazebo、OpenCV 解耦；
- 第一阶段只实现核心语义规划并进行离线单元测试；
- 核心测试通过后，再建立独立 ROS2 工作空间；
- 最终仿真使用 Gazebo；
- Gazebo 场景作为外部资产接入，不修改 NeuPAN 原始 ROS 包；
- 原 `neupan_ros2` 用作同环境下的 NeuPAN baseline；
- 新增的 `sc_neupan_planner_ros2` 用作本文方法。

## 1.2 ROS1 与 ROS2 的最终选择

最终建议：

> **SC-NeuPAN 主开发与最终 Gazebo 验证使用 ROS2。**  
> **ROS1 只保留为原项目历史示例，不作为本文创新系统的主环境。**

选择 ROS2 的原因不是“ROS2 更新”，而是当前源码约束下更可靠：

| 对比项 | ROS1 Noetic | ROS2 Humble |
|---|---|---|
| 项目自带 Gazebo | 有，LIMO + Gazebo Classic | 无，当前只有二维 `ddr_minimal_sim` |
| Python 环境 | 默认 Python 3.8，与当前 NeuPAN 要求存在冲突 | Python 3.10，与 NeuPAN 更匹配 |
| 当前 Docker setup | 会改写源码并可能删除 `neupan_ros2` | 不会主动删除 ROS1 |
| 相机、分割模型集成 | 需要绕过 Python/cv_bridge 兼容问题 | 更适合现代 PyTorch/OpenCV |
| 多节点感知融合 | 可以实现 | QoS、多线程和参数化更清晰 |
| 新增 Gazebo 工程量 | 较小 | 较大，但可完全独立设计 |
| 长期维护 | 较差 | 较好 |

虽然 ROS1 已经有 Gazebo 示例，但其当前环境脚本存在严重问题：

```bash
rm -rf "$NEUPAN_SRC/neupan_ros2"
```

由于项目目录被 Docker 绑定挂载，这条命令可能删除宿主机中的 `neupan_ros2`。

ROS1 setup 还会直接改写：

```text
neupan_ros/src/neupan_core.py
```

这与“不能修改原源码”的要求冲突。

因此，综合以下因素：

- 原源码不可改；
- 需要相机；
- 需要运行分割网络；
- 需要同步 RGB 与 LaserScan；
- 后续本来就要新增 Gazebo 场景和机器人传感器；

最终使用 ROS2 更合理。

---

# 2. 不可违反的工程约束

## 2.1 受保护目录

以下目录视为上游只读代码：

```text
neupan/
neupan_ros/
neupan_ros2/
example/
docker/
```

不在这些目录中新增或修改本文代码。

允许读取和调用它们，但不允许直接编辑。

## 2.2 可以复制，但必须保留许可证

如果需要复制 NeuPAN 的 `PAN`、`NRMP` 等实现到新目录中进行改进：

1. 保留原文件 GPL 许可证头；
2. 在文件头注明“基于 NeuPAN 对应文件修改”；
3. 在 `COPYING_NOTICE.md` 中列出来源文件；
4. 不覆盖原文件；
5. 复制后的类和模块使用新名称，避免与原包混淆。

## 2.3 原始代码完整性检查

新增工具：

```text
sc_neupan_tools/check_upstream_clean.sh
```

每次测试前执行：

```bash
git diff --exit-code -- neupan example docker
git -C neupan_ros diff --exit-code
git -C neupan_ros2 diff --exit-code
```

还应记录提交版本：

```text
sc_neupan_tools/upstream.lock
```

示例：

```yaml
root: f254c54daff2e7fdcdeb34754859fc4f1f5aa407
neupan_ros: b3ec0cb86f83ee1f8bf1c727d208a1f3c06e7b36
neupan_ros2: 4ffb7ec2dc45ff7ee9024f64083813237906af98
```

当你清除 DeepSeek 修改后，应重新生成工作区状态记录。

---

# 3. 源码审计后的关键设计修正

## 3.1 不把语义类别输入 DUNE 网络

原 DUNE 的输入是二维几何点：

\[
p_i=[x_i,y_i]^\top
\]

网络输出几何对偶变量：

\[
\mu_i=f_\theta(p_i)
\]

距离近似为：

\[
d_i^{geom}=\mu_i^\top(Gp_i-h)
\]

同一个位置的点，无论是人、墙还是车辆，其几何距离都不应发生变化。

因此禁止：

\[
\mu_i=f_\theta(x_i,y_i,class_i)
\]

否则会破坏 DUNE 的几何含义，并使原 checkpoint 无法复用。

## 3.2 语义作用于规划决策，不作用于几何编码

语义只影响：

1. 哪些障碍点优先进入 NRMP；
2. 不同类别需要多大的额外安全裕度；
3. 低置信度时如何保守退化。

不改变：

- `ObsPointNet`；
- DUNE 训练数据；
- DUNE checkpoint；
- 机器人凸包 `G,h`；
- 原始运动学模型。

## 3.3 必须解决点与语义属性的索引对齐

NeuPAN 中的障碍点会经历：

1. DUNE 输入点数限制；
2. 预测时域展开；
3. DUNE 距离排序；
4. NRMP Top-K 截断；
5. 点数不足时 padding。

因此以下属性必须同步变换：

```text
point_xy
velocity_xy
class_id
confidence
source_index
semantic_margin
priority_bias
```

禁止只下采样点而不下采样标签。

## 3.4 不能只在 NRMP 中增加权重

如果某个高风险点在 DUNE 的几何 Top-K 阶段已经被删除，后面再增加语义代价没有意义。

所以本文需要同时改进：

- **语义感知点选择**；
- **语义自适应安全裕度**。

---

# 4. 总体系统架构

```text
┌─────────────────────────────────────────────────────────────────┐
│                         原始 NeuPAN                              │
│  neupan/、neupan_ros/、neupan_ros2/ 保持不变                    │
└─────────────────────────────────────────────────────────────────┘

                         只调用，不修改
                                │
                                v

┌─────────────────────────────────────────────────────────────────┐
│                      sc_neupan_core                              │
│                                                                 │
│  SemanticPointSet                                               │
│         │                                                       │
│         ├── 索引对齐 / 下采样                                   │
│         ├── Semantic DUNE Adapter                               │
│         ├── Semantic-aware Top-K                                │
│         ├── Semantic NRMP                                       │
│         └── SCNeuPAN Planner Adapter                            │
└─────────────────────────────────────────────────────────────────┘
                                │
                                v

┌─────────────────────────────────────────────────────────────────┐
│                      sc_neupan_ros2                              │
│                                                                 │
│  RGB image ──> segmentation ──> mask + confidence               │
│  LaserScan ───────────────────> point projection / painting      │
│                                  │                              │
│                                  v                              │
│                         Semantic PointCloud2                     │
│                                  │                              │
│                                  v                              │
│                          SC-NeuPAN Planner                       │
│                                  │                              │
│                                  v                              │
│                               cmd_vel                           │
└─────────────────────────────────────────────────────────────────┘
                                │
                                v

┌─────────────────────────────────────────────────────────────────┐
│                      sc_neupan_gazebo                            │
│                                                                 │
│  可替换 world + 差速机器人 + 2D LiDAR + RGB Camera              │
│  原 NeuPAN baseline 与 SC-NeuPAN 在同一世界中运行               │
└─────────────────────────────────────────────────────────────────┘
```

---

# 5. 项目根目录代码结构

建议在当前 NeuPAN 根目录新增：

```text
NeuPAN/
├── neupan/                              # 原源码，禁止修改
├── neupan_ros/                          # 原 ROS1，禁止修改
├── neupan_ros2/                         # 原 ROS2，禁止修改
├── example/                             # 原示例，禁止修改
├── docker/                              # 原环境脚本，禁止修改
│
├── sc_neupan_core/                      # 第一阶段：核心算法
│   ├── pyproject.toml
│   ├── README.md
│   ├── COPYING_NOTICE.md
│   ├── src/
│   │   └── sc_neupan_core/
│   │       ├── __init__.py
│   │       ├── api/
│   │       │   ├── planner.py
│   │       │   └── result.py
│   │       ├── data/
│   │       │   ├── semantic_points.py
│   │       │   ├── dune_output.py
│   │       │   └── validation.py
│   │       ├── geometry/
│   │       │   ├── camera_model.py
│   │       │   ├── projector.py
│   │       │   └── transforms.py
│   │       ├── painting/
│   │       │   ├── point_painter.py
│   │       │   ├── mask_sampler.py
│   │       │   └── boundary_filter.py
│   │       ├── semantics/
│   │       │   ├── classes.py
│   │       │   ├── class_mapper.py
│   │       │   ├── profile.py
│   │       │   ├── confidence.py
│   │       │   └── selector.py
│   │       ├── solver/
│   │       │   ├── semantic_dune.py
│   │       │   ├── semantic_nrmp.py
│   │       │   ├── semantic_pan.py
│   │       │   └── planner_adapter.py
│   │       ├── diagnostics/
│   │       │   ├── timing.py
│   │       │   ├── invariants.py
│   │       │   └── debug_snapshot.py
│   │       └── config/
│   │           ├── loader.py
│   │           └── schema.py
│   ├── config/
│   │   ├── planner.yaml
│   │   ├── semantic_profile.yaml
│   │   └── projection.yaml
│   └── tests/
│       ├── unit/
│       │   ├── test_semantic_points.py
│       │   ├── test_projection.py
│       │   ├── test_point_painter.py
│       │   ├── test_alignment.py
│       │   ├── test_selector.py
│       │   └── test_confidence_fallback.py
│       ├── solver/
│       │   ├── test_dune_equivalence.py
│       │   ├── test_nrmp_dpp.py
│       │   ├── test_margin_effect.py
│       │   ├── test_padding.py
│       │   └── test_baseline_equivalence.py
│       └── integration/
│           ├── test_synthetic_scene.py
│           └── test_repeatability.py
│
├── sc_neupan_ros2/                      # 核心通过后再实现
│   ├── README.md
│   ├── build.sh
│   ├── setup.sh
│   └── src/
│       ├── sc_neupan_msgs/
│       ├── sc_neupan_perception/
│       ├── sc_neupan_fusion/
│       ├── sc_neupan_planner/
│       ├── sc_neupan_description/
│       ├── sc_neupan_gazebo/
│       ├── sc_neupan_bringup/
│       └── sc_neupan_evaluation/
│
├── sc_neupan_docker/                    # 新环境，不使用原 ROS1 setup
│   ├── README.md
│   ├── compose.yaml
│   ├── core.Dockerfile
│   ├── ros2.Dockerfile
│   ├── gazebo.Dockerfile
│   └── scripts/
│       ├── build.sh
│       ├── enter.sh
│       └── check_gpu.sh
│
├── sc_neupan_tools/
│   ├── check_upstream_clean.sh
│   ├── write_upstream_lock.sh
│   ├── upstream.lock
│   ├── validate_config.py
│   └── collect_results.py
│
├── sc_neupan_docs/
│   ├── architecture.md
│   ├── calibration.md
│   ├── experiment_protocol.md
│   ├── gazebo_scene_checklist.md
│   └── development_log.md
│
└── sc_neupan_artifacts/                 # 不提交大文件
    ├── logs/
    ├── bags/
    ├── checkpoints/
    ├── figures/
    └── results/
```

---

# 6. 核心数据接口

## 6.1 SemanticPointSet

核心包不使用 ROS 消息。

```python
@dataclass(frozen=True)
class SemanticPointSet:
    points_xy: torch.Tensor       # (2, N)，世界坐标
    class_ids: torch.Tensor       # (N,)，int64
    confidence: torch.Tensor      # (N,)，范围 [0, 1]
    velocities_xy: torch.Tensor | None = None  # (2, N)
    source_indices: torch.Tensor | None = None # (N,)
    stamp_ns: int | None = None
```

必须验证：

```python
points_xy.shape[0] == 2
points_xy.shape[1] == class_ids.shape[0]
class_ids.shape == confidence.shape
velocities_xy is None or velocities_xy.shape == points_xy.shape
```

## 6.2 统一索引操作

所有点属性只能通过统一方法筛选：

```python
semantic_points.gather(indices)
```

禁止分别写：

```python
points = points[:, indices]
classes = classes[other_indices]
```

建议提供：

```python
def gather(self, indices: torch.Tensor) -> "SemanticPointSet"
def downsample(self, max_num: int) -> "SemanticPointSet"
def select(self, mask: torch.Tensor) -> "SemanticPointSet"
```

## 6.3 DUNEOutput

```python
@dataclass(frozen=True)
class DUNEOutput:
    mu_list: list[torch.Tensor]
    lambda_list: list[torch.Tensor]
    points_list: list[torch.Tensor]
    distances_list: list[torch.Tensor]
    sort_indices_list: list[torch.Tensor]
```

原 DUNE 网络不变，但扩展类额外返回：

- 距离；
- 排序索引；
- 排序后的点。

---

# 7. 导航语义类别

不要直接让规划器使用 COCO、ADE20K 等模型的原始类别编号。

定义导航级类别：

```python
class NavigationClass(IntEnum):
    UNKNOWN = 0
    STATIC = 1
    HUMAN = 2
    VEHICLE = 3
    ROBOT = 4
```

第一版原则：

- `UNKNOWN`：保持原 NeuPAN 行为；
- `STATIC`：保持原 NeuPAN 行为；
- `HUMAN`：增加安全裕度；
- `VEHICLE`：增加安全裕度；
- `ROBOT`：可配置中等或较大安全裕度；
- 不允许负安全裕度；
- 不允许因为分割类别而删除有效 LiDAR 回波。

## 7.1 为什么 UNKNOWN 不能忽略

出现 UNKNOWN 的原因可能是：

- 点在相机视野外；
- 图像和雷达不同步；
- 分割置信度低；
- 标定误差；
- 模型没有对应类别；
- 物体被遮挡。

但 LiDAR 已经检测到物理障碍，因此 UNKNOWN 必须继续按几何障碍处理。

---

# 8. 视觉分割输出规范

分割模块输出统一格式：

```python
@dataclass(frozen=True)
class SegmentationResult:
    class_map: np.ndarray       # (H, W)，导航类别或原模型类别
    confidence_map: np.ndarray  # (H, W)，float32
    source_stamp_ns: int
```

支持两类模型：

## 8.1 实例分割模型

例如只识别：

- person；
- car；
- bicycle；
- truck。

未覆盖像素为 UNKNOWN。

优点：

- 算力要求较低；
- 重点识别高风险对象；
- 不依赖墙、地面等完整语义类别。

## 8.2 全景或语义分割模型

可输出更密集的类别图。

但第一阶段不要求所有像素都有类别。

## 8.3 重叠区域处理

当多个 mask 覆盖同一像素时：

```text
选择置信度最高的实例
```

或者：

```text
按照风险优先级覆盖：
HUMAN > VEHICLE > ROBOT > STATIC > UNKNOWN
```

默认使用“先比较风险，再比较置信度”。

---

# 9. LiDAR 点云染色模块

## 9.1 输入

- LiDAR 坐标系下的点；
- 相机内参；
- LiDAR 到相机光学坐标系的外参；
- 分割类别图；
- 分割置信度图。

## 9.2 坐标变换

LiDAR 点：

\[
P_L=[x_L,y_L,z_L,1]^\top
\]

转换到相机光学坐标系：

\[
P_C=T_C^L P_L
\]

只保留：

\[
Z_C>0
\]

像素投影：

\[
u=f_x\frac{X_C}{Z_C}+c_x
\]

\[
v=f_y\frac{Y_C}{Z_C}+c_y
\]

## 9.3 输出

每个有效 LiDAR 点得到：

```text
x
y
z
class_id
confidence
source_index
projection_valid
```

最终 NeuPAN 仍只使用二维几何点：

```text
x, y
```

其他属性只供 SC-NeuPAN 选择与优化。

## 9.4 投影失败处理

以下情况设置为 UNKNOWN：

- 点在相机后方；
- 点超出图像边界；
- TF 查询失败；
- 图像与 LaserScan 时间差超过阈值；
- confidence 小于阈值；
- 点落在分割 mask 边缘保护区；
- 相机内参未初始化。

不得删除这些 LiDAR 点。

## 9.5 Mask 边界保护

相机与 LiDAR 存在视差，mask 边界最容易出现误染色。

建议在采样前对高风险 mask 做轻微腐蚀，或计算边界距离：

```python
if distance_to_mask_boundary < boundary_guard_px:
    class_id = UNKNOWN
```

这样会牺牲少量召回率，但降低错误语义影响规划的风险。

---

# 10. 语义安全策略

## 10.1 Semantic Profile

配置文件：

```yaml
version: 1

classes:
  unknown:
    id: 0
    margin: 0.00
    priority_bias: 0.00

  static:
    id: 1
    margin: 0.00
    priority_bias: 0.00

  human:
    id: 2
    margin: 0.35
    priority_bias: 0.35

  vehicle:
    id: 3
    margin: 0.20
    priority_bias: 0.20

  robot:
    id: 4
    margin: 0.15
    priority_bias: 0.15

confidence:
  threshold: 0.55
  fallback_class: unknown
  interpolation: linear
```

以上数值只是初始占位，不是最终论文参数。

## 10.2 置信度融合

点的最终安全裕度：

\[
\Delta_i
=
c_i\Delta_{class(i)}
+
(1-c_i)\Delta_{unknown}
\]

由于第一版：

\[
\Delta_{unknown}=0
\]

可写为：

\[
\Delta_i=c_i\Delta_{class(i)}
\]

若置信度低于阈值，则直接设置为 UNKNOWN。

## 10.3 禁止负裕度

第一版必须满足：

\[
\Delta_i\ge 0
\]

这保证语义模块只能让规划更保守，不会让已有障碍变得更危险。

---

# 11. 语义感知 Top-K

原 DUNE 按几何距离排序：

\[
d_{t,i}^{geom}
\]

SC-NeuPAN 定义：

\[
score_{t,i}
=
d_{t,i}^{geom}
-
b_{t,i}
\]

其中：

\[
b_{t,i}
=
c_i b_{class(i)}
\]

按 `score` 从小到大选择前 K 个点。

含义：

- 高风险点在候选阶段被视为更近；
- DUNE 的真实几何距离不变；
- 类别只改变候选优先级。

必须同步重排：

```text
mu
lambda
point
distance
class_id
confidence
margin
source_index
```

## 11.1 每个预测时刻独立排序

障碍点在不同预测时刻的位置和几何距离不同，因此：

```text
t=1 的 Top-K
t=2 的 Top-K
...
t=T 的 Top-K
```

需要分别计算。

不能只在当前帧排序一次后复制到所有预测步。

---

# 12. Semantic NRMP

## 12.1 原始残差

NeuPAN 中每个预测时刻和障碍点的近似残差：

\[
r_{t,i}^{base}
=
\gamma_{t,i}^{\top}s_{t,xy}
-
\zeta_{t,i}
-
d_t
\]

原碰撞惩罚：

\[
J_{obs}^{base}
=
\frac{\rho}{2}
\sum_{t,i}
[-r_{t,i}^{base}]_+^2
\]

## 12.2 修改后的残差

加入语义安全裕度：

\[
r_{t,i}^{sem}
=
\gamma_{t,i}^{\top}s_{t,xy}
-
\zeta_{t,i}
-
d_t
-
\Delta_{t,i}
\]

碰撞惩罚：

\[
J_{obs}^{sem}
=
\frac{\rho}{2}
\sum_{t,i}
[-r_{t,i}^{sem}]_+^2
\]

其余目标保持不变：

\[
J=
J_{tracking}
+
J_{control}
+
J_{proximal}
+
J_{obs}^{sem}
-
\eta\sum_t d_t
\]

## 12.3 CVXPY 参数

每个预测时刻新增：

```python
para_semantic_margin[t]
```

形状：

```text
(K, 1)
```

要求：

```python
nonneg=True
```

## 12.4 DPP 检查

构造问题后必须保留：

```python
assert problem.is_dcp(dpp=True)
```

还要增加单元测试，确保：

- zero margin 可构建；
- nonzero margin 可构建；
- CvxpyLayer 可执行；
- backward 不报错；
- 求解结果不存在 NaN 或 Inf。

---

# 13. Padding 设计

原 NRMP 在点数少于 K 时，会重复第一个障碍点填满剩余行。

这可能导致同一个点被重复处罚。

为了保证基线一致：

## 13.1 Baseline 模式

```yaml
padding_mode: repeat_first
```

完全复现原行为。

## 13.2 Semantic 模式

建议：

```yaml
padding_mode: safe_dummy
```

填充安全 dummy 系数，使其残差始终为正，不产生碰撞惩罚。

例如：

```text
gamma = [0, 0]
margin = 0
zeta = -(d_max + max_margin + epsilon)
```

则：

\[
r=
0-\zeta-d_t-\Delta
\]

在参数范围内保持正值。

`test_padding.py` 必须覆盖：

- 0 个点；
- 1 个点；
- K-1 个点；
- K 个点；
- 大于 K 个点。

---

# 14. 与原 NeuPAN 的集成方式

## 14.1 不修改原 planner

新增：

```python
class SCNeuPANPlanner:
    def plan(
        self,
        state: np.ndarray,
        semantic_points: SemanticPointSet,
    ) -> PlannerResult:
        ...
```

## 14.2 Planner Adapter

推荐采用组合方式：

```text
原 neupan 实例
    │
    ├── 原 robot
    ├── 原 InitialPath
    ├── 原配置
    └── 将内部 PAN 替换为独立 SemanticPAN 实例
```

不修改原类定义。

语义数据通过显式上下文传入 `SemanticPAN`：

```python
semantic_pan.set_context(context)
try:
    action, info = base_planner(state, points, velocities)
finally:
    semantic_pan.clear_context()
```

要求：

- 单次调用后清除；
- 不允许复用上一帧语义；
- 有线程锁；
- 点数不匹配立即报错；
- 时间戳过旧时退化为 UNKNOWN。

## 14.3 为什么不直接包一层点云预处理

只在调用 NeuPAN 前修改点云顺序无法实现语义安全裕度。

因为语义裕度必须进入 NRMP 的残差。

所以核心层仍需要独立的：

```text
SemanticPAN
SemanticNRMP
SemanticDUNE adapter
```

但它们位于新包中，不修改原源码。

---

# 15. 详细模块职责

## 15.1 `data/semantic_points.py`

职责：

- 定义数据结构；
- 形状验证；
- 设备和 dtype 转换；
- 统一 gather；
- 空点云处理。

禁止：

- ROS 消息解析；
- OpenCV；
- 模型推理。

## 15.2 `geometry/camera_model.py`

职责：

- 保存相机矩阵；
- 畸变参数；
- 图像尺寸；
- 内参合法性检查。

## 15.3 `geometry/projector.py`

职责：

- 批量 3D 点投影；
- 返回有效 mask；
- 不读取语义 mask；
- 不包含 ROS TF 查询。

## 15.4 `painting/point_painter.py`

职责：

- 根据 UV 从 mask 采样；
- 生成 class/confidence；
- 投影无效点设为 UNKNOWN；
- 保留原点数量和 source index。

## 15.5 `semantics/class_mapper.py`

职责：

- 原模型类别映射到导航类别；
- 不参与几何计算；
- 支持不同分割模型配置。

## 15.6 `semantics/profile.py`

职责：

- class → margin；
- class → priority bias；
- 参数范围验证；
- 禁止负 margin。

## 15.7 `semantics/selector.py`

职责：

- 计算语义排序分数；
- 每个预测时刻独立 Top-K；
- 同步 gather 全部属性。

## 15.8 `solver/semantic_dune.py`

实现方式：

- 继承原 `DUNE`；
- 复用原模型和 checkpoint；
- 重写 `forward()`；
- 与原版相同地计算 `mu`、`lambda`、几何距离；
- 额外返回排序索引和距离；
- 不读取类别。

## 15.9 `solver/semantic_nrmp.py`

实现方式：

- 继承原 `NRMP` 或复制后改名；
- 新增 margin 参数；
- 重写障碍代价；
- 保留原导航代价、动力学和边界约束；
- 保留 DPP 检查。

为降低对上游内部实现的脆弱依赖，首版建议：

> 复制 `NRMP` 到新包并改名为 `SemanticNRMP`，保留许可证头，再做最小改动。

## 15.10 `solver/semantic_pan.py`

职责：

- 对输入点和语义进行统一下采样；
- 生成预测点流；
- 调用 SemanticDUNE；
- 进行语义 Top-K；
- 调用 SemanticNRMP；
- 保存调试信息。

## 15.11 `api/planner.py`

职责：

- 对外唯一规划入口；
- 加载 NeuPAN 原配置；
- 加载 semantic profile；
- 管理语义上下文；
- 输出统一 `PlannerResult`；
- 支持 baseline 和 semantic 两种模式。

---

# 16. 第一阶段：只实现核心，不接 ROS 和 Gazebo

## Phase 0：恢复并冻结 baseline

目标：

- 删除 DeepSeek 未提交修改；
- 确认原 NeuPAN Python 示例能运行；
- 记录三个仓库提交；
- 建立源码完整性检查。

验收条件：

```text
原 NeuPAN 示例可运行
受保护目录 git diff 为空
upstream.lock 已生成
```

注意：

不要执行当前：

```bash
docker/ros1/setup.sh
```

因为它会修改和删除受保护目录。

## Phase 1：数据结构与点云染色

实现：

```text
SemanticPointSet
CameraModel
Projector
PointPainter
ClassMapper
SemanticProfile
```

使用纯 NumPy/PyTorch 生成合成数据测试。

验收：

- 已知外参投影误差小于 1 像素；
- 无效投影不会删除 LiDAR 点；
- 类别和 source index 完全对齐；
- confidence fallback 正确；
- 所有测试不依赖 ROS。

## Phase 2：Semantic DUNE 与索引链路

实现：

```text
SemanticDUNE
DUNEOutput
SemanticSelector
```

测试：

1. `SemanticDUNE` 的 `mu/lambda/distance` 与原 DUNE 一致；
2. zero bias 时排序完全一致；
3. 点数超过 `dune_max_num` 时所有属性同步下采样；
4. 每个预测步的排序索引可追溯；
5. 不同类别不会改变 DUNE 几何距离。

验收：

```text
DUNE 等价测试通过
索引对齐测试通过
```

## Phase 3：Semantic NRMP

实现：

- semantic margin 参数；
- semantic collision residual；
- baseline padding；
- semantic safe padding；
- DPP 检查。

测试：

- margin 全零时与原 NRMP 输出一致；
- human margin 增大时，规划最小间距不减小；
- 输入语义乱序时能通过 source index 检测；
- 空点云不会崩溃；
- 参数边界不会产生 NaN。

## Phase 4：完整核心 Planner

实现：

```text
SCNeuPANPlanner
PlannerResult
DebugSnapshot
```

离线合成场景：

- 静态墙；
- 人与墙距离接近；
- 高风险点略远但应进入 Top-K；
- 图像视野外障碍；
- 低置信度误分类；
- 点数不足；
- 点数过多。

核心验收门槛：

```text
1. semantic.enabled=false 时与原 NeuPAN 等价
2. 所有单元测试通过
3. 连续运行 1000 帧无内存持续增长
4. 无 NaN/Inf
5. 单次核心增加的语义处理延迟有明确统计
6. 原源码保持未修改
```

只有以上全部通过，才进入 ROS 与 Gazebo 阶段。

---

# 17. 核心阶段测试矩阵

| 测试 | 输入 | 预期 |
|---|---|---|
| Baseline equivalence | 全部 margin=0 | 动作和轨迹与原版一致 |
| Geometry invariance | 同一点不同类别 | DUNE 距离完全相同 |
| Alignment | 下采样 + 排序 + Top-K | source index 始终一致 |
| Human priority | 人略远于静态点 | 人仍进入 Top-K |
| Confidence fallback | human 但低 confidence | 退化为 UNKNOWN |
| Camera out-of-FOV | 点不在图像中 | 保留点，类别 UNKNOWN |
| Empty points | N=0 | 不崩溃 |
| Small N | N<K | padding 不增加虚假碰撞 |
| Large N | N>dune_max | 同步下采样 |
| Repeatability | 固定输入重复运行 | 输出一致 |
| DPP | 多组 margin | `is_dcp(dpp=True)` |
| Timing | 典型点数 | 记录 DUNE、NRMP、语义处理耗时 |

---

# 18. 第二阶段：ROS2 模块设计

核心通过后，建立独立工作空间：

```text
sc_neupan_ros2/
└── src/
    ├── sc_neupan_msgs/
    ├── sc_neupan_perception/
    ├── sc_neupan_fusion/
    ├── sc_neupan_planner/
    ├── sc_neupan_description/
    ├── sc_neupan_gazebo/
    ├── sc_neupan_bringup/
    └── sc_neupan_evaluation/
```

---

# 19. ROS2 节点划分

## 19.1 `segmentation_node`

订阅：

```text
/camera/color/image_raw
```

发布：

```text
/sc_neupan/segmentation/class_map
/sc_neupan/segmentation/confidence_map
```

消息使用标准 `sensor_msgs/Image`：

- class map：`mono16`；
- confidence map：`32FC1`。

要求：

- 输出 header.stamp 保留原图像时间戳；
- 不使用推理完成时间替换；
- 模型推理失败时发布全 UNKNOWN；
- 统计推理延迟；
- 支持模型热切换但默认关闭。

## 19.2 `semantic_fusion_node`

同步输入：

```text
/scan
/sc_neupan/segmentation/class_map
/sc_neupan/segmentation/confidence_map
/camera/color/camera_info
```

使用：

```python
ApproximateTimeSynchronizer
```

处理：

1. LaserScan 转 LiDAR 坐标点；
2. 查询 `camera_optical_frame <- laser_frame`；
3. 投影；
4. mask 采样；
5. 生成语义点云。

发布：

```text
/sc_neupan/semantic_points
/sc_neupan/fusion/debug_image
/sc_neupan/fusion/diagnostics
```

## 19.3 `sc_neupan_planner_node`

订阅：

```text
/sc_neupan/semantic_points
/goal_pose 或 /plan
```

查询 TF：

```text
map -> base_link
```

发布：

```text
/sc_neupan/cmd_vel
/sc_neupan/plan
/sc_neupan/debug/dune_points
/sc_neupan/debug/nrmp_points
/sc_neupan/debug/semantic_points
/sc_neupan/diagnostics
```

## 19.4 `evaluation_node`

订阅：

```text
robot pose
cmd_vel
collision contacts
goal
semantic points
ground-truth object states
```

输出：

```text
CSV / JSON
```

不把评价逻辑写进 planner node。

---

# 20. ROS2 话题与坐标系契约

## 20.1 推荐话题

```text
/cmd_vel
/scan
/camera/color/image_raw
/camera/color/camera_info
/goal_pose
/plan

/sc_neupan/segmentation/class_map
/sc_neupan/segmentation/confidence_map
/sc_neupan/semantic_points
/sc_neupan/cmd_vel
/sc_neupan/diagnostics
```

所有名称都必须可通过参数修改。

## 20.2 坐标系

```text
map
└── odom
    └── base_link
        ├── laser_link
        └── camera_link
            └── camera_optical_frame
```

规定：

- LaserScan 原始点在 `laser_link`；
- 图像投影使用 `camera_optical_frame`；
- NeuPAN 障碍点在 `map`；
- TF 查询使用传感器消息时间戳；
- 不使用“最新 TF”代替同步时刻 TF，除非明确进入 fallback 模式。

## 20.3 QoS

传感器：

```text
best_effort
volatile
small queue
```

规划控制：

```text
reliable
small queue
```

不应使用无限队列，以免处理过期图像。

---

# 21. ROS2 Baseline 与本文方法的公平比较

最终 Gazebo 环境中运行两种模式：

## Baseline

使用原：

```text
neupan_ros2
```

输入同一 `/scan`、同一 TF、同一目标。

## Proposed

使用：

```text
sc_neupan_planner
```

输入同一 `/scan`，额外使用相机语义。

两者必须使用：

- 同一机器人几何；
- 同一 DUNE checkpoint；
- 同一路径；
- 同一控制周期；
- 同一世界；
- 同一随机种子；
- 同一初始状态。

不建议用 ROS1 场景跑 baseline、ROS2 场景跑本文方法，因为环境差异会削弱论文结论。

---

# 22. Gazebo 仿真设计

## 22.1 不立即绑定具体 Gazebo 版本

你后续会从 Gazebo 场景网站下载场景。

下载前无法确定场景属于：

- Gazebo Classic；
- 新 Gazebo；
- 使用哪一个 SDF 版本；
- 是否依赖特定系统插件。

因此核心和 ROS 节点只依赖话题契约，不依赖具体 Gazebo API。

Gazebo 适配层单独放在：

```text
sc_neupan_gazebo
```

最终根据场景格式选择对应 Docker 镜像和 launch。

## 22.2 第一版建议的仿真接口

无论 Gazebo 版本如何，必须提供：

```text
/scan                         sensor_msgs/LaserScan
/camera/color/image_raw       sensor_msgs/Image
/camera/color/camera_info     sensor_msgs/CameraInfo
/odom                         nav_msgs/Odometry
/cmd_vel                      geometry_msgs/Twist
/tf
/tf_static
/clock
```

Gazebo 之外的核心代码不感知模拟器类型。

## 22.3 机器人模型

新建：

```text
sc_neupan_description
```

第一版使用简单差速机器人，规划几何与 LIMO 保持一致：

```yaml
length: 0.322
width: 0.22
```

这样可以复用匹配该矩形几何的 DUNE checkpoint。

传感器：

- 2D LiDAR；
- RGB camera；
- 可选 contact sensor；
- 可选 ground-truth pose plugin。

需要明确传感器外参：

```yaml
laser:
  xyz: [x, y, z]
  rpy: [r, p, y]

camera:
  xyz: [x, y, z]
  rpy: [r, p, y]
```

## 22.4 为什么不用当前 `ddr_minimal_sim` 做最终实验

当前 ROS2 自带 `ddr_minimal_sim`：

- 仅二维；
- 只有 LaserScan；
- 没有 RGB camera；
- 没有真实渲染；
- 不适合验证图像分割和投影融合。

它最多可用于几何 regression，不作为论文最终仿真。

---

# 23. Gazebo 场景接入方式

用户下载场景后，不直接修改其世界文件。

建议目录：

```text
sc_neupan_ros2/src/sc_neupan_gazebo/
├── worlds/
│   └── vendor/
│       └── scene_name/
│           ├── source.world 或 source.sdf
│           ├── LICENSE
│           └── scene_manifest.yaml
├── models/
│   ├── semantic_human/
│   ├── semantic_vehicle/
│   └── semantic_static/
└── launch/
    ├── world.launch.py
    ├── spawn_robot.launch.py
    └── experiment.launch.py
```

`scene_manifest.yaml`：

```yaml
name: scene_name
source: gazebo_download_source
license: unknown
simulator_family: classic_or_gz
sdf_version: unknown
world_file: source.world
spawn_pose: [0.0, 0.0, 0.0]
goal_pose: [5.0, 0.0, 0.0]
required_model_paths: []
notes: ""
```

## 23.1 场景兼容性检查

进入算法实验前必须完成：

- 世界能独立启动；
- 无缺失 `model://`；
- 地面碰撞正常；
- 尺寸单位合理；
- 机器人不会出生在障碍内部；
- 光照足以供分割模型推理；
- 相机画面纹理正常；
- LiDAR 能检测主要实体；
- 场景许可证允许科研使用；
- 场景不依赖无法安装的专用插件。

## 23.2 外部场景与语义目标分离

下载场景主要提供：

- 走廊；
- 房间；
- 家具；
- 背景纹理。

论文需要重点测试的人、车等类别建议由本项目单独 spawn。

这样：

- 类别和位置可控；
- 可重复实验；
- 方便得到 ground truth；
- 不依赖下载场景是否自带人物。

---

# 24. Gazebo 验证分阶段设计

## Simulation Stage 1：传感器烟雾测试

不运行 NeuPAN。

验证：

- `/scan` 正常；
- 图像正常；
- CameraInfo 正常；
- TF 树正确；
- `/cmd_vel` 可驱动机器人；
- 时间戳使用仿真时间。

## Simulation Stage 2：相机-LiDAR 投影验证

不运行规划器。

显示：

- RGB 图；
- 分割 mask；
- 投影后的 LiDAR 像素；
- 染色点云。

验收：

- 静态标定场景下大部分点落在正确物体；
- 图像边界没有大量异常标签；
- 相机外点正确为 UNKNOWN；
- 时间延迟统计符合阈值。

## Simulation Stage 3：Oracle Semantic Planner

先不使用预测分割。

通过仿真对象注册表或人工场景标注，为点提供正确导航类别。

目的：

> 单独验证语义 Top-K 和安全裕度是否改善规划。

如果 Oracle 语义没有收益，不应继续接入视觉模型。

## Simulation Stage 4：Ground-truth Mask Fusion

如果使用的 Gazebo 版本支持语义或分割相机，则接入真值 mask。

若不支持，可以使用颜色编码的受控测试模型生成确定性 mask，仅用于投影与融合验证。

## Simulation Stage 5：Predicted Segmentation

接入真实分割模型：

```text
RGB → segmentation_node → mask → point painting → SC-NeuPAN
```

## Simulation Stage 6：完整闭环对比

比较：

- 原 NeuPAN；
- SC-NeuPAN Oracle；
- SC-NeuPAN ground-truth mask；
- SC-NeuPAN predicted mask。

---

# 25. 仿真实验指标

## 25.1 通用导航指标

- Success Rate；
- Collision Rate；
- Navigation Time；
- Path Length；
- 平均速度；
- 控制平滑度；
- 最小几何间距；
- 单帧规划耗时；
- 总感知到控制延迟。

## 25.2 语义专用指标

- Minimum Human Clearance；
- Human Safety Violation Rate；
- High-risk Point Recall in Top-K；
- Semantic Point Accuracy；
- Unknown Ratio；
- Projection Valid Ratio；
- Segmentation Latency；
- Fusion Latency；
- Planner Latency；
- 低置信度退化触发率。

## 25.3 鲁棒性指标

人为加入：

- 类别误判；
- mask 边界偏移；
- 外参平移误差；
- 外参旋转误差；
- 图像延迟；
- LaserScan 延迟；
- 分割节点掉线；
- 相机视野外障碍。

要求：

> 感知模块失效时，SC-NeuPAN 至少退化为原始几何 NeuPAN，而不是失去避障能力。

---

# 26. 仿真实验场景设计

下载的 Gazebo 场景中至少设计以下任务：

## Scene A：静态走廊

目的：

- 检查语义模块关闭时不影响 baseline；
- 检查路径跟踪和静态障碍。

## Scene B：人和墙距离相近

目的：

- 验证相同几何距离下，对人保持更大间距。

## Scene C：大量静态点遮蔽高风险点

目的：

- 验证 semantic-aware Top-K；
- 人体点几何距离略远，但仍应进入 NRMP。

## Scene D：相机视野外障碍

目的：

- 验证 UNKNOWN fallback；
- 机器人仍按原 NeuPAN 避障。

## Scene E：分割误判

目的：

- 验证置信度和边界保护；
- 错误类别不能导致障碍被忽略。

## Scene F：复杂下载场景

目的：

- 验证工程可迁移性；
- 统计完整链路实时性。

---

# 27. Docker 环境重新设计

禁止复用当前 ROS1 setup 的源码修改逻辑。

新增三个环境层：

## 27.1 `core.Dockerfile`

用于 Phase 1–4：

```text
Ubuntu 22.04
Python 3.10
PyTorch
NumPy
CVXPY
CVXPYLayers
pytest
OpenCV
NeuPAN editable install
sc_neupan_core editable install
```

不安装 ROS，不安装 Gazebo。

优点：

- 构建快；
- 核心测试稳定；
- 避免 ROS 干扰。

## 27.2 `ros2.Dockerfile`

继承 core 环境并增加：

```text
ROS2 Humble
rclpy
sensor_msgs
geometry_msgs
nav_msgs
tf2
message_filters
image_transport
rviz2
colcon
```

用于 ROS 节点测试，不安装 Gazebo。

## 27.3 `gazebo.Dockerfile`

继承 ROS2 环境。

根据下载场景选择对应 Gazebo 版本和桥接包。

该选择必须写入：

```text
sc_neupan_docs/gazebo_scene_checklist.md
```

## 27.4 Docker 安全要求

- 不在 setup 中执行 `sed -i` 修改上游源码；
- 不删除任何上游目录；
- 不硬编码代理地址；
- 代理通过 build args 或环境变量传入；
- 日志写入 `sc_neupan_artifacts`；
- 构建后执行 upstream clean 检查；
- 镜像中记录软件版本；
- GUI 和 GPU 参数放在独立运行脚本中。

---

# 28. ROS 与 Gazebo 实现顺序

严格顺序：

```text
恢复 baseline
    ↓
核心数据结构
    ↓
纯数学点云投影
    ↓
点云染色
    ↓
Semantic DUNE
    ↓
Semantic Top-K
    ↓
Semantic NRMP
    ↓
核心等价性和安全测试
    ↓
ROS2 segmentation node
    ↓
ROS2 fusion node
    ↓
ROS2 planner node
    ↓
ROS topic 回放测试
    ↓
Gazebo 机器人和传感器
    ↓
Gazebo 投影验证
    ↓
Oracle 语义闭环
    ↓
预测分割闭环
    ↓
论文对比实验
```

禁止在核心测试通过前同时开发：

- Gazebo world；
- 分割训练；
- 动态障碍跟踪；
- 复杂可视化；
- 自动调参。

这样可以避免问题来源无法定位。

---

# 29. 第一版不做的内容

为控制硕士小论文工作量，第一版明确不做：

- 不把语义输入 DUNE；
- 不联合训练分割网络和 NeuPAN；
- 不训练大型 Semantic Risk Network；
- 不根据语义降低障碍安全性；
- 不删除 ground 或 unknown LiDAR 点；
- 不做单目深度补点；
- 不声明能够处理透明障碍；
- 不自动预测动态障碍轨迹；
- 不同时支持 ROS1 和 ROS2；
- 不同时支持 Gazebo Classic 与新 Gazebo；
- 不在第一阶段下载和适配复杂世界。

---

# 30. 逻辑风险与防护

## 30.1 分割模型不识别墙和家具

处理：

- 未识别点为 UNKNOWN；
- UNKNOWN 继续按原 NeuPAN 避障；
- 语义仅为识别到的高风险类别增加裕度。

## 30.2 相机和 LiDAR 视场不同

处理：

- 视场外点保留；
- 标记 UNKNOWN；
- 不进行类别推测。

## 30.3 传感器基线导致遮挡不一致

处理：

- mask 边界保护；
- 低置信度退化；
- 可选时序一致性；
- 不让单帧语义取消几何障碍。

## 30.4 分割延迟使标签过期

处理：

- 使用原图时间戳；
- ApproximateTimeSynchronizer；
- 设置最大时间差；
- 超时退化为 UNKNOWN。

## 30.5 下载场景与 Gazebo 版本不兼容

处理：

- Gazebo 版本在下载后确定；
- 场景接入放在独立 adapter；
- 核心和 ROS 话题契约不改变；
- 先执行场景兼容性清单。

## 30.6 新机器人尺寸与 DUNE checkpoint 不匹配

处理：

- 第一版机器人保持 `0.322 × 0.22 m`；
- 如果修改 footprint，必须按原方法重训 DUNE；
- 语义分割数据不参与 DUNE 训练。

## 30.7 GPU 快但规划仍慢

原因：

- 分割主要使用 GPU；
- NRMP 的 CVXPY 求解主要依赖 CPU。

实验必须分别统计：

```text
segmentation time
fusion time
DUNE time
NRMP time
total latency
```

---

# 31. 配置文件分层

## Core

```text
sc_neupan_core/config/
├── planner.yaml
├── semantic_profile.yaml
└── projection.yaml
```

## ROS2

```text
sc_neupan_ros2/src/sc_neupan_bringup/config/
├── topics.yaml
├── frames.yaml
├── synchronization.yaml
├── segmentation.yaml
├── fusion.yaml
└── planner_node.yaml
```

## Gazebo

```text
sc_neupan_ros2/src/sc_neupan_gazebo/config/
├── robot.yaml
├── sensors.yaml
├── scene.yaml
└── experiment.yaml
```

## Evaluation

```text
sc_neupan_ros2/src/sc_neupan_evaluation/config/
├── metrics.yaml
├── goals.yaml
└── repetitions.yaml
```

配置不在代码中硬编码。

---

# 32. 论文贡献建议

在该工程实现成功后，论文贡献可表述为：

1. 提出一种适用于 NeuPAN 的视觉语义染色 LiDAR 表示，在保留原始几何障碍点的基础上为点附加类别与置信度。
2. 提出语义感知障碍点选择方法，使高风险对象在有限 NRMP 约束数量下获得更高保留优先级。
3. 提出语义自适应安全裕度方法，在不改变 DUNE 几何编码和预训练模型的情况下实现类别相关避让。
4. 构建基于 ROS2 和 Gazebo 的 RGB-LiDAR 局部规划验证系统，并通过 Oracle、真值融合和预测分割分阶段实验分析感知误差对规划性能的影响。

不应表述为：

- “修改 DUNE 后获得语义距离”；
- “端到端联合训练视觉和控制”；
- “语义模块能够发现 LiDAR 看不到的障碍”；
- “加入语义后自动具备动态轨迹预测”。

---

# 33. 开发验收门槛

## Gate A：开始 Solver 之前

- 数据结构测试通过；
- 投影测试通过；
- 染色测试通过。

## Gate B：开始 ROS 之前

- baseline equivalence 通过；
- DPP 测试通过；
- Top-K 对齐测试通过；
- margin 行为测试通过；
- 原源码 clean。

## Gate C：开始 Gazebo 之前

- ROS2 节点可用合成 publisher 运行；
- rosbag 回放不丢失数据；
- 时间戳和 TF 错误可退化；
- planner node 连续运行稳定。

## Gate D：开始论文正式实验之前

- Gazebo 传感器链路稳定；
- 投影可视化检查通过；
- Oracle 语义结果有效；
- baseline 与 proposed 使用同一环境；
- 重复实验脚本和指标记录完成。

---

# 34. 首次实际开发清单

第一轮只创建以下内容：

```text
sc_neupan_core/
sc_neupan_tools/
sc_neupan_docs/
sc_neupan_docker/core.Dockerfile
```

第一轮暂不创建完整 Gazebo world。

具体顺序：

1. 恢复 DeepSeek 修改；
2. 写入 `upstream.lock`；
3. 实现 `SemanticPointSet`；
4. 实现统一 gather/downsample；
5. 实现 CameraModel 和 Projector；
6. 实现 PointPainter；
7. 实现 SemanticProfile；
8. 实现 SemanticSelector；
9. 实现 SemanticDUNE；
10. 实现 SemanticNRMP；
11. 实现 SemanticPAN；
12. 实现 SCNeuPANPlanner；
13. 完成全部核心测试；
14. 再进入 ROS2 和 Gazebo。

---

# 35. 最终评审结论

经过对当前项目的 NeuPAN 核心、ROS1、ROS2 和 Docker 部分重新审查，本方案相对前两个版本修正了以下关键漏洞：

- 不再把 ROS1 现有 Gazebo 示例等同于最佳开发环境；
- 发现并规避 ROS1 setup 修改源码和删除 ROS2 目录的问题；
- 不再要求修改 `neupan/`、`neupan_ros/` 或 `neupan_ros2/`；
- 将改进算法放入独立 root-level Python 包；
- 将 ROS2 和 Gazebo 延后到核心测试通过之后；
- 保持原 DUNE 的几何含义；
- 明确语义必须同时影响 Top-K 与 NRMP margin；
- 明确点、类别和置信度的全流程索引对齐；
- 明确相机视野外、低置信度和同步失败时的保守退化；
- 使下载的 Gazebo 场景通过独立 adapter 接入；
- 保证 baseline 和本文方法最终在同一个 Gazebo 世界中公平比较。

因此，当前推荐的实施主线是：

> **独立 SC-NeuPAN 核心包 → 完整核心测试 → ROS2 多传感器节点 → 独立 Gazebo 适配层 → 下载场景闭环验证。**
