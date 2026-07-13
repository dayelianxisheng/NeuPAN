# SGCF-NRMP 多模态局部规划系统开发任务书（Codex 分阶段执行版）

> **文档版本**：V2.0 Codex Execution Edition  
> **执行原则**：一次只执行一个阶段；每阶段完成后输出可见成果并强制停止  
> **适用仓库**：NeuPAN 项目根目录  
> **上游保护**：`neupan/`、`neupan_ros/`、`neupan_ros2/`、`example/`、`docker/` 默认只读  
> **目标方法**：SGCF-NRMP——稀疏门控跨模态净空场与模型预测优化局部规划  
> **最终平台**：RGB 相机 + 2D LiDAR 差速小车，纯 CPU 部署
> **官方只读算法基线**：NeuPAN commit `579e7afa239cd7ff61f7f63fbd4aaaecbb136d3b`

---

# Codex 强制执行协议

本节优先级高于本文档其他章节。Codex 在执行任何开发任务前必须先阅读本节。

## A. 执行范围

1. **一次只执行用户指定的一个阶段**。  
2. 未收到用户明确的“进入下一阶段”指令前，不得提前创建下一阶段的核心实现。  
3. 可以为当前阶段创建必要的公共基础文件，但不得以“顺便”为由实现后续模型、ROS 或 Gazebo 功能。  
4. 每个阶段结束后必须停止，不得自动连续执行。  
5. 不得把未运行、未验证的代码描述为已完成。

## B. 上游源码保护

Codex 不得直接修改：

```text
neupan/
neupan_ros/
neupan_ros2/
example/
docker/
```

允许：

- 阅读；
- 搜索；
- 运行；
- 导入公共接口；
- 参考数学实现；
- 在新目录中重新实现；
- 必要时复制少量 GPL 代码，但必须保留许可证头并更新 `sgcf_nrmp_project/COPYING_NOTICE.md`。

禁止：

- 自动执行 `git restore`、`git reset --hard`、`git checkout -- <file>`；
- 自动执行 `git clean -fd`；
- 使用 `sed -i`、脚本或补丁修改上游目录；
- 删除任何 ROS1/ROS2 目录；
- 使用 `git add .`；
- 未经用户明确要求执行 commit、rebase、merge 或 push。

当前工作树中已知存在来自错误提交 `54a291c` 的 DeepSeek 语义 DUNE、color DUNE、class embedding 等修改。它们不需要保留、分析、兼容或作为实验基线，也不得自行恢复。所有算法对照统一从 Git 对象中的官方提交 `579e7af` 读取；阶段审计必须记录当前工作树与该基线的差异。

## C. 需要立即停止并向用户提问的情况

出现以下任一情况时，Codex 必须停止当前阶段，保留现场，并只提出完成当前阻塞所必需的问题：

1. 需要用户输入密码、sudo 密码、GitHub Token、SSH key 或其他凭据；
2. 需要安装系统软件并必须使用 `sudo apt`；
3. pip、conda、apt、git clone、模型下载或数据下载发生网络错误；
4. 需要从网页选择或下载 Gazebo 场景、模型、预训练权重或数据集；
5. 外部资源许可证不明确，需要用户决定是否使用；
6. 需要用户操作 GUI、RViz、Gazebo、相机、LiDAR 或真实小车；
7. 需要重启系统、重登会话、重新插拔设备或修改驱动；
8. CUDA、PyTorch、ROS、Gazebo 版本发生实质冲突，存在多种解决方案；
9. 当前 Git 状态无法确定哪些代码应保留；
10. 需要修改受保护的 NeuPAN 文件才能继续；
11. 测试结果与设计假设矛盾，继续会掩盖问题；
12. 当前阶段的验收门槛未达到，且没有明确的无风险修复办法；
13. 需要确定真实小车 CPU、相机、LiDAR、footprint、安全距离等用户硬件参数；
14. 需要用户选择算法分支、场景版本或部署后端。

网络失败处理：

- 最多重试一次；
- 保存完整错误输出；
- 不切换未知镜像源；
- 不关闭 SSL 校验；
- 不使用来历不明的安装脚本；
- 向用户说明失败命令、所需资源和建议的手动命令。

## D. 可以自行处理而不必提问的情况

Codex 可以自行完成：

- 新目录内的代码重构；
- 类型错误、lint、单元测试修复；
- 不改变算法含义的小范围配置调整；
- 生成合成数据；
- 生成图表、日志和测试报告；
- 在已有环境中运行不需要权限的命令；
- 为当前阶段增加必要的测试和文档。

## E. 阶段产物统一目录

每个阶段必须创建：

```text
sgcf_nrmp_project/artifacts/stages/stage_XX_<name>/
├── stage_report.md
├── commands.log
├── tests.log
├── environment.txt
├── files_changed.txt
├── upstream_check.txt
└── outputs/                 # 图片、CSV、JSON、视频或模型
```

`stage_report.md` 必须包含：

1. 阶段状态：`COMPLETED`、`BLOCKED` 或 `FAILED`；
2. 本阶段目标；
3. 实际完成内容；
4. 创建和修改的文件；
5. 运行命令；
6. 测试结果；
7. 可见成果路径；
8. 性能指标；
9. 尚存问题；
10. 上游目录是否保持未修改；
11. 下一阶段名称，但不得开始下一阶段。

## F. 阶段结束时的固定回复格式

成功时：

```text
阶段 XX 已完成。

完成内容：...
测试结果：...
可见成果：...
上游源码检查：...
阶段报告：...

已停止，没有开始阶段 XX+1。请确认是否进入下一阶段。
```

阻塞时：

```text
阶段 XX 已暂停，未继续执行。

阻塞原因：...
已完成部分：...
失败命令/错误：...
现场文件：...
需要你完成或确认：...

收到你的处理结果后，再从当前阶段继续。
```

## G. 完成定义（Definition of Done）

一个阶段只有同时满足以下条件才可标记为 `COMPLETED`：

- 约定代码已实现；
- 当前阶段测试全部通过；
- 至少一个用户可直接查看的成果已生成；
- 命令和环境已记录；
- 代码无明显占位 `TODO` 冒充完成；
- 受保护目录检查通过；
- 文档和代码一致；
- 没有偷偷开始下一阶段。

---


# 技术设计正文

## Stage 06 架构决策修订（2026-07-13，优先于后文旧描述）

Stage 06 在集成前接口审计中确认：Stage 04 的 `LidarClearanceField` 是 query-conditioned point encoder。点特征中的 query-local x/y 与平方距离在编码前生成，因此现有 checkpoint 无法满足“场景编码一次、多查询复用”；改变该结构需要重新训练。结合 Stage 05 批量精确 Oracle 已达到 single obstacle/corridor/narrow passage 的 17.03/23.18/21.97 ms online P95，且学习几何场仍需 exact recheck，最终决策为：

```text
REPLACE_WITH_EXACT_GEOMETRY_FOR_FINAL_SYSTEM
KEEP_LEARNED_GEOMETRY_FIELD_AS_RESEARCH_ABLATION_ONLY
```

最终主链路固定为：

```text
2D LiDAR
    -> Batched Exact Observable Geometry
    -> exact d_geo and g_geo

RGB + LiDAR
    -> Sparse RGB-LiDAR Semantic Fusion
    -> nonnegative semantic margin m_sem and reliability r

d_geo + g_geo^T(q-q_nom) + slack >= d_safe + r*m_sem
    -> Trust-Region NRMP-like QP
    -> [v, omega]
```

Exact Geometry 负责物理净空；学习模块只增加类别相关安全裕度，RGB 不得增加或伪造几何净空。`m_sem >= 0`；RGB 失效时 `r -> 0`，系统退化为 Stage 05 的 LiDAR-only exact planner。完整世界几何仍只用于离线评价。第一版不预测动态障碍未来轨迹。凡后文仍称学习净空场为最终主几何模块之处，均由本修订覆盖。

## 0. 文档目标

本文档用于指导一个完整、可验证、可部署的硕士小论文项目。项目不是在完整 NeuPAN 上增加少量功能，而是：

1. 保留 NeuPAN 作为研究基线；
2. 参考 NeuPAN 中的滚动时域、近端交替优化和模型约束设计；
3. 重新设计 RGB–LiDAR 多模态环境表示；
4. 使用批量精确可观测几何替代 DUNE 的主安全几何职责；
5. 将精确净空、精确局部梯度和学习语义安全裕度转换为 NRMP-like 优化约束；
6. 先完成核心算法，再接 ROS 2，最后在 Gazebo 和 CPU 智能小车上验证。

本文档规定：

- 研究边界；
- 模型结构；
- 训练数据来源；
- 软件环境；
- 代码结构；
- 每个文件的基础职责与接口；
- 开发阶段；
- 每阶段可见成果；
- 测试与验收条件；
- Gazebo 与 ROS 2 接入方式；
- CPU 部署路径；
- 论文实验与消融设计；
- 风险和回退方案。

---

# 1. 研究定位

## 1.1 研究问题

输入：

\[
\mathcal{O}_t=
\left(
I_t,
P_t,
s_t,
g_t
\right)
\]

其中：

- \(I_t\)：当前 RGB 图像；
- \(P_t\)：当前 LiDAR 扫描或二维点集；
- \(s_t=[x_t,y_t,\theta_t]\)：机器人状态；
- \(g_t\)：局部目标或参考路径。

输出：

\[
u_t=[v_t,\omega_t]
\]

目标是在满足机器人运动学和控制约束的情况下：

- 跟踪局部路径；
- 避免几何碰撞；
- 对人、车辆等类别保持更大的安全距离；
- 在 RGB 失效时退化为 LiDAR-only；
- 在纯 CPU 车载计算机上满足实时控制需求。

第一版能力边界：系统可对当前帧中的人、车辆等类别施加不同安全裕度，但不估计障碍速度，也不声明动态障碍轨迹预测能力。动态环境实验只评价反应式重规划；显式运动预测属于后续扩展。

## 1.2 与 NeuPAN 的关系

借鉴 NeuPAN：

- 滚动预测时域；
- 名义轨迹迭代；
- 模型动力学线性化；
- 状态、控制和近端代价；
- 学习环境表示与优化器耦合；
- 可选的可微优化训练思想。

不使用或重新设计：

- DUNE；
- `ObsPointNet`；
- 点级 \(\mu,\lambda\) 环境表示；
- 完整 NeuPAN `PAN`；
- 原始点级障碍约束生成流程。

项目形成的新链路：

```text
NeuPAN:
LiDAR points
    -> DUNE
    -> point-wise latent distance constraints
    -> NRMP

SGCF-NRMP:
RGB + LiDAR
    -> sparse gated cross-modal representation
    -> robot clearance field
    -> distance / gradient / semantic margin
    -> NRMP-like optimizer
```

## 1.3 预期论文贡献

在实现和实验成功后，可将贡献概括为：

1. 实现 CPU 实时的批量精确机器人净空与 Trust-Region NRMP-like 规划；
2. 提出面向 RGB + 2D LiDAR 的稀疏语义融合；
3. 设计非负语义安全裕度与可靠性退化机制；
4. 分离精确几何安全基础与学习语义风险；
5. 设计 RGB 失效、过期或错位时自动退化为 LiDAR-only planner 的机制；
6. 在 Gazebo 和纯 CPU 智能小车上验证部署性能。

---

# 2. 设计约束

## 2.1 原 NeuPAN 源码只读

以下目录视为上游代码：

```text
neupan/
neupan_ros/
neupan_ros2/
example/
docker/
```

研究代码不得直接修改这些目录。

可以：

- 阅读；
- 导入公共接口；
- 运行 baseline；
- 参考数学和代码结构；
- 在遵守 GPL-3.0 的情况下复制必要代码到新目录并保留许可证。

不可以：

- 直接重写 `neupan/blocks/dune.py`；
- 直接重写 `neupan/blocks/nrmp.py`；
- 将新模块塞入 `neupan_ros2`；
- 使用脚本自动 `sed` 修改上游文件；
- 删除 ROS1 或 ROS2 上游目录。

## 2.2 许可证要求

NeuPAN 使用 GPL-3.0。

如果复制 `NRMP`、`robot` 或其他实现：

1. 新文件保留原 GPL 头；
2. 文件顶部注明来源路径和修改内容；
3. 在唯一项目根目录维护 `sgcf_nrmp_project/COPYING_NOTICE.md`；
4. 新项目整体按 GPL-3.0 兼容方式发布；
5. 论文中明确算法思想来源；
6. 不把复制代码描述为完全自主实现。

建议优先根据论文和接口重新实现 `NRMPSolver`，仅在确有必要时复制少量代码。

---

# 3. 模型完整结构

## 3.1 推理链路

```text
RGB Image I_t
    |
    v
Lightweight Image Encoder
    |
    v
Low-resolution feature map F_I
    |
    | project and local soft sample
    |
2D LiDAR P_t
    |
    v
LiDAR Point Encoder -----------+
    |                          |
    v                          v
LiDAR point feature F_L    Local image feature F_Ip
    |                          |
    +-------- Gated Fusion ----+
                  |
                  v
          Fused point feature F_M
                  |
          +-------+-----------------------+
          |                               |
          v                               v
LiDAR Geometry Clearance Head     Semantic Margin Head
d_geo(q), grad_geo(q)             margin(q), reliability(q)
          |                               |
          +---------------+---------------+
                          |
                          v
d_geo + grad^T(q-q_nom) >= d_safe + reliability * margin
                          |
                          v
                  NRMP-like QP/SCP
                          |
                          v
                   trajectory and control
```

## 3.2 双分支安全定义

### 几何净空分支（最终系统：批量精确几何）

\[
d_{\text{obs}}(q,P)
\]

表示机器人 footprint 位于候选位姿 \(q\) 时，相对当前 LiDAR 可观测点集合的净空距离，本文称为 `observable_clearance`。最终系统由 Stage 05 的 `BatchedRectangleObservableOracle` 精确计算距离与梯度，不由 RGB 或学习模型修改。

完整仿真环境中的真实障碍集合用于计算 `world_clearance`。该量只用于闭环安全评估、轨迹复检和 false-safe 统计，不作为单帧 LiDAR 网络的直接监督目标，避免遮挡和视野外障碍造成不可学习的一对多标签。

Stage 04 网络曾学习该距离：

\[
d_{\text{obs}}(q,P)
\]

其梯度由距离输出通过 autograd 获得：

\[
g_{\text{obs}}(q,P)=\nabla_q d_{\text{obs}}(q,P)
\]

该模型现定位为 `Learned Geometry Ablation`，用于精度、梯度和架构选择消融，不接入最终主规划器，也不再规划独立梯度 head 作为主系统部署输出。最终主系统直接使用 exact：

\[
[d_geo,g_x,g_y,g_\theta]
\]

这些值由解析几何提供，不需要网络反向传播。

### 语义安全裕度分支

\[
m_{\text{sem}}(q,I,P)\ge0
\]

表示视觉语义带来的额外安全距离。

可靠性：

\[
r(q,I,P)\in[0,1]
\]

有效安全约束：

\[
d_{\text{geo}}
\ge
d_{\text{safe}}+
r\cdot m_{\text{sem}}
\]

RGB 失效时：

\[
r\rightarrow0
\]

系统退化为纯 LiDAR 几何规划。

### 为什么不让 RGB 直接预测几何距离

RGB 可能受到：

- 光照；
- 模糊；
- 遮挡；
- 仿真域差异；
- 标定误差；
- 时间不同步；
- 分割或特征误判。

因此 RGB 只能增加安全裕度，第一版不能删除或减弱 LiDAR 已检测到的障碍。

---

# 4. 融合方法

## 4.1 PointPainting 仅作为基线

PointPainting 基线：

```text
RGB segmentation score
    -> project to LiDAR point
    -> concatenate with point feature
```

优点：

- 简单；
- 易实现；
- 适合论文基线；
- CPU 开销低。

缺点：

- 使用单像素硬对应；
- 只使用最终类别概率；
- 标定和同步误差会直接导致错配；
- 图像中间特征利用不足。

## 4.2 主方法：Sparse Local Soft Fusion

主方法使用局部图像特征而不是单一类别编号。

对 LiDAR 点 \(p_i\) 投影得到像素：

\[
(u_i,v_i)
\]

从低分辨率图像特征图中采样投影点周围窗口：

\[
\mathcal{N}(u_i,v_i)
\]

局部权重：

\[
\alpha_{i,j}
=
\operatorname{softmax}
\left(
\phi(
f_i^L,
f_{i,j}^I,
\delta u_{i,j},
\delta v_{i,j}
)
\right)
\]

聚合图像特征：

\[
\tilde f_i^I
=
\sum_{j\in\mathcal{N}(u_i,v_i)}
\alpha_{i,j}f_{i,j}^I
\]

门控：

\[
a_i=
\sigma\left(
\operatorname{MLP}
[
f_i^L,
\tilde f_i^I,
c_i,
\Delta t_i,
e_i,
v_i^{proj}
]
\right)
\]

融合：

\[
f_i^M
=
f_i^L+
a_i\odot W\tilde f_i^I
\]

其中：

- \(c_i\)：视觉置信度；
- \(\Delta t_i\)：RGB 与 LiDAR 时间差；
- \(e_i\)：投影边界或对齐误差特征；
- \(v_i^{proj}\)：投影是否有效；
- \(a_i\)：视觉使用权重。

## 4.3 CPU 友好限制

第一版固定：

- 局部窗口：3×3；
- 图像特征分辨率：输入图像的 1/8；
- LiDAR 点数：180、256 或 360；
- 不使用全局 Cross-Attention；
- 不使用大型 Transformer；
- 不生成大型稠密 BEV；
- 不在控制周期内执行自动微分。

说明：该限制针对最终 CPU 部署。阶段 04～10 的训练与离线验证使用 autograd 计算距离对查询位姿的梯度；阶段 11 再评估并替换为独立梯度 head。

---

# 5. 净空场结构

## 5.1 查询对象

查询位姿：

\[
q=[x,y,\sin\theta,\cos\theta]
\]

不用原始 \(\theta\) 作为网络输入，避免 \(-\pi\) 与 \(\pi\) 处不连续。

## 5.2 局部点选择

对每个名义轨迹位姿 \(\bar q_k\)：

1. 将点变换到查询位姿局部坐标；
2. 选择最近的 \(K\) 个点；
3. 固定 \(K=16\sim32\)；
4. 为不足 K 的位置使用 mask，不重复障碍点；
5. 对每个预测步独立查询。

## 5.3 Geometry Clearance Head

输入：

\[
[
\Delta x_i,
\Delta y_i,
r_i,
f_i^L,
\sin\theta,
\cos\theta,
valid_i
]
\]

网络建议：

```text
Shared MLP: input -> 32 -> 64
Masked max pooling + masked mean pooling
Query MLP: pooled feature + query pose -> 64 -> 32
Output head -> [observable_clearance, collision_logit]
```

输出：

- 非负可观测净空距离 \(d_{\text{obs}}\)；
- 碰撞概率或 collision logit。

第一版的 \(g_x,g_y,g_\theta\) 由 `observable_clearance` 对查询位姿 autograd 得到，不设置独立梯度输出。独立梯度 head 是阶段 11 的可选部署优化。

## 5.4 Semantic Margin Head

输入使用融合特征：

\[
f_i^M
\]

网络：

```text
Shared MLP -> masked pooling
Query decoder
Margin head: softplus(raw_margin)
Reliability head: sigmoid(raw_reliability)
```

输出：

\[
m_{\text{sem}}\ge0
\]

\[
r\in[0,1]
\]

## 5.5 可选不确定性

第二版再加入：

\[
\sigma_{\text{geo}}
\]

安全约束变为：

\[
d_{\text{geo}}
\ge
d_{\text{safe}}+
r m_{\text{sem}}+
\beta\sigma_{\text{geo}}
\]

第一版暂不加入，避免训练与标定工作过大。

---

# 6. NRMP-like 优化器

## 6.1 状态与控制

差速小车：

\[
s_k=[x_k,y_k,\theta_k]
\]

\[
u_k=[v_k,\omega_k]
\]

离散模型：

\[
x_{k+1}=x_k+v_k\cos\theta_k\Delta t
\]

\[
y_{k+1}=y_k+v_k\sin\theta_k\Delta t
\]

\[
\theta_{k+1}=\theta_k+\omega_k\Delta t
\]

在名义轨迹附近线性化：

\[
s_{k+1}
=
A_ks_k+B_ku_k+C_k
\]

## 6.2 碰撞约束

在名义位姿 \(\bar q_k\) 查询：

\[
d_k,\quad g_k,\quad m_k,\quad r_k
\]

局部线性化：

\[
d(q_k)
\approx
d_k+
g_k^\top(q_k-\bar q_k)
\]

软安全约束：

\[
d_k+
g_k^\top(q_k-\bar q_k)+\xi_k
\ge
d_{\text{safe}}+r_km_k
\]

\[
\xi_k\ge0
\]

每轮 SCP 同时加入 trust region，限制优化状态偏离本轮名义状态：

\[
\lVert q_k-\bar q_k\rVert_\infty\le\Delta_q
\]

其中位置与角度使用分别配置的上限。若线性化误差或真实几何复检失败，应缩小 trust region 并重新求解，而不是接受该轨迹。

## 6.3 目标函数

\[
J=
J_{\text{track}}
+
J_{\text{control}}
+
J_{\text{smooth}}
+
J_{\text{prox}}
+
\rho\|\xi\|_2^2
\]

其中：

\[
J_{\text{track}}
=
\sum_k
\|Q(s_k-s_k^{ref})\|_2^2
\]

\[
J_{\text{control}}
=
\sum_k
\|Ru_k\|_2^2
\]

\[
J_{\text{smooth}}
=
\sum_k
\|u_k-u_{k-1}\|_2^2
\]

\[
J_{\text{prox}}
=
\sum_k
\|s_k-\bar s_k\|_2^2
\]

## 6.4 求解方式

开发阶段：

- CVXPY；
- OSQP；
- 可选 CvxpyLayer，用于后续联合训练研究。

部署阶段：

- 固定预测时域；
- 固定矩阵稀疏结构；
- OSQP warm start；
- C/C++ 接口；
- 可选 OSQP code generation。

不在部署端使用 CvxpyLayer 反向传播。

## 6.5 交替迭代

每个控制周期：

1. 根据上周期轨迹或参考轨迹初始化名义轨迹；
2. 查询净空场；
3. 构造线性约束；
4. 求解 QP；
5. 更新名义轨迹；
6. 重复 1～3 次；
7. 使用完整环境真实几何对优化轨迹逐 footprint 复检；
8. 复检通过后输出第一个控制量，否则缩小 trust region 重求解或触发安全停止。

真实几何复检仅在程序化环境、离线评估和 Gazebo oracle 中可用。实车无法访问完整环境几何，因此部署时以可观测几何复检、保守裕度、传感器新鲜度检查和安全停止作为回退，不能据此声明形式化安全保证。

---

# 7. 数据来源与训练标签

## 7.1 为什么加入 RGB 后不能只随机生成独立点

原 DUNE 可仅随机生成二维点，因为其学习的是：

- 单点；
- 固定机器人凸包；
- 几何对偶变量；
- 与图像、纹理和遮挡无关的关系。

加入 RGB 后，以下信息必须一致：

- 障碍物几何；
- 相机视角；
- LiDAR 扫描；
- 物体类别；
- 图像纹理；
- 遮挡；
- 光照；
- 相机内参；
- 相机—LiDAR 外参；
- 时间戳。

因此不能简单生成：

```text
[x, y, random_class]
```

这不会产生有效的多模态监督。

## 7.2 两层数据体系

### 数据层 A：程序化纯几何数据

用途：

- 训练 LiDAR Geometry Clearance Head；
- 不需要 RGB；
- 可大规模生成；
- 与原 NeuPAN 的随机几何数据思想一脉相承，但标签定义不同。

随机生成：

- 圆；
- 矩形；
- 多边形；
- 墙；
- 走廊；
- U 型障碍；
- 狭窄通道；
- 稀疏/密集障碍；
- 点云缺失；
- 距离噪声。

过程：

```text
随机二维场景
    -> 模拟 2D LiDAR
    -> 随机候选机器人位姿
    -> 计算完整 footprint 到障碍的净空
    -> 生成距离、碰撞、梯度标签
```

样本：

```python
{
    "lidar_points": float32[N, 2],
    "lidar_valid": bool[N],
    "query_pose": float32[4],
    "clearance_gt": float32[1],
    "gradient_gt": float32[3],
    "collision_gt": int64[1],
    "scene_id": str,
}
```

### 数据层 B：Gazebo 多模态数据

用途：

- 训练图像编码器；
- 训练稀疏软融合；
- 训练 Semantic Margin Head；
- 做仿真闭环验证。

每帧保存：

```text
RGB image
LaserScan / points
CameraInfo
camera_optical_frame <- laser_frame transform
robot pose
object semantic IDs
object poses
world ID
timestamp
```

样本：

```python
{
    "rgb_path": str,
    "lidar_path": str,
    "camera_info": dict,
    "T_camera_lidar": float32[4, 4],
    "query_poses": float32[M, 4],
    "clearance_gt": float32[M],
    "gradient_gt": float32[M, 3],
    "semantic_margin_gt": float32[M],
    "semantic_class_gt": int64[M],
    "projection_valid": bool[N],
    "world_id": str,
    "sequence_id": str,
    "frame_id": int,
}
```

## 7.3 几何净空标签

机器人 footprint：

\[
\mathcal{R}(q)
\]

障碍集合：

\[
\mathcal{O}
\]

网络监督目标是相对当前 LiDAR 可观测表面集合 \(\mathcal{O}_{obs}(P)\) 的净空：

\[
d^{gt}_{obs}(q,P)
=
\min_j
\operatorname{dist}(\mathcal{R}(q),\mathcal{O}_{obs,j}(P))
\]

完整环境评估另外计算：

\[
d^{gt}_{world}(q)=\min_j\operatorname{dist}(\mathcal{R}(q),\mathcal{O}_{world,j})
\]

`world_clearance` 不作为单帧网络监督标签，只用于完整环境评估、优化轨迹真实几何复检和 false-safe rate。

碰撞标签：

\[
y^{gt}_{col}
=
\mathbb{I}
\left(
\mathcal{R}(q)\cap\mathcal{O}\ne\emptyset
\right)
\]

第一版不强制学习严格负值 SDF。

建议输出：

- 非碰撞时的非负 `observable_clearance`；
- 独立 collision logit；
- 碰撞位姿的 clearance 标签设为 0。

## 7.4 梯度监督与验证

第一版不训练独立 gradient head。规划所用梯度由预测 `observable_clearance` 对查询位姿通过 autograd 计算。以下有限差分梯度作为监督一致性、数值验证和局部线性化误差评估的参考：

\[
g_x^{gt}
\approx
\frac{d(x+\epsilon_x)-d(x-\epsilon_x)}
{2\epsilon_x}
\]

\[
g_y^{gt}
\approx
\frac{d(y+\epsilon_y)-d(y-\epsilon_y)}
{2\epsilon_y}
\]

\[
g_\theta^{gt}
\approx
\frac{d(\theta+\epsilon_\theta)-d(\theta-\epsilon_\theta)}
{2\epsilon_\theta}
\]

注意：

- 角度与距离单位不同；
- 不对 \([x,y,\theta]\) 直接使用未归一化 Eikonal；
- 在碰撞边界不连续位置降低梯度损失权重；
- 可使用多尺度有限差分提高稳定性。

阶段 11 若为 CPU 部署加入独立 gradient head，必须以 autograd/有限差分梯度为教师，并单独报告梯度余弦相似度、局部线性化误差及 false-safe rate；未达到门槛时继续使用 autograd 或降低控制频率。

## 7.5 语义裕度标签

对最近或最危险障碍物类别 \(c_j\) 定义额外安全裕度：

\[
s(c_j)\ge0
\]

有效距离：

\[
d^{gt}_{eff}(q)
=
\min_j
\left[
\operatorname{dist}(\mathcal{R}(q),\mathcal{O}_j)-s(c_j)
\right]
\]

语义裕度：

\[
m^{gt}_{sem}
=
\max
\left(
0,
d^{gt}_{geo}-d^{gt}_{eff}
\right)
\]

第一版类别：

```text
unknown
static
human
vehicle
robot
```

初始裕度只是配置，不是最终论文参数：

```yaml
unknown: 0.00
static: 0.00
robot: 0.15
vehicle: 0.20
human: 0.35
```

需要通过验证集、行为实验和安全规范调整。

## 7.6 数据划分

禁止按相邻帧随机划分。

必须按：

- world；
- sequence；
- obstacle layout；
- texture set；

划分训练、验证和测试集。

建议：

```text
train worlds: 70%
validation worlds: 15%
test worlds: 15%
```

测试集至少包含：

- 未见过的纹理；
- 未见过的障碍布局；
- 不同光照；
- 不同点云噪声；
- 不同相机曝光。

---

# 8. 损失函数

## 8.1 Geometry Loss

距离：

\[
L_d=
\operatorname{SmoothL1}
(\hat d_{geo},d_{geo}^{gt})
\]

梯度：

\[
L_g=
\|
\hat g-g^{gt}
\|_1
\]

碰撞：

\[
L_c=
\operatorname{BCEWithLogits}
(\hat y_{col},y_{col}^{gt})
\]

局部线性一致性：

\[
L_{lin}
=
\left|
\hat d(q+\delta q)
-
\hat d(q)
-
\hat g(q)^\top\delta q
\right|
\]

几何总损失：

\[
L_{geo}
=
\lambda_dL_d+
\lambda_gL_g+
\lambda_cL_c+
\lambda_lL_{lin}
\]

## 8.2 Semantic Loss

裕度：

\[
L_m=
\operatorname{SmoothL1}
(\hat m,m^{gt})
\]

可靠性：

\[
L_r=
\operatorname{BCE}
(\hat r,r^{gt})
\]

其中 \(r^{gt}\) 根据以下条件生成：

- 投影有效；
- 时间差低于阈值；
- 图像未损坏；
- 类别置信度足够；
- 不在 mask 不稳定边界。

失效退化：

\[
L_{fallback}
=
\left|
\hat m(I=0)
\right|
\]

或：

\[
\left|
\hat r(I=0)
\right|
\]

## 8.3 联合损失

\[
L=
L_{geo}
+
\lambda_mL_m
+
\lambda_rL_r
+
\lambda_fL_{fallback}
\]

第一版不要求任务级轨迹损失反向传播到图像编码器。

---

# 9. 软件环境

## 9.1 总体原则

分为三个环境：

1. **训练环境**：Conda + PyTorch + GPU；
2. **核心算法环境**：Python + CPU/GPU，独立于 ROS；
3. **ROS 2 / Gazebo 环境**：系统 Python 和 Docker，不在 ROS 进程中激活 Conda。

不要将 Conda 的 Python 直接覆盖 ROS 2 系统 Python。

## 9.2 主机系统

推荐：

```text
Ubuntu 22.04 LTS
Python 3.10
ROS 2 Humble
Gazebo Fortress（默认）
```

选择理由：

- 当前 NeuPAN ROS2 项目以 Humble 为基础；
- ROS 2 Humble 官方二进制面向 Ubuntu 22.04 Jammy；
- Gazebo 官方将 Fortress 作为 ROS 2 Humble 的配套版本；
- Python 3.10 与该系统组合匹配；
- 最终 Gazebo 版本仍以用户下载场景的格式和阶段 13 检查结果为准。

版本规则：

- 本文档给出兼容性基线，不允许 Codex盲目重装现有环境；
- 阶段 01 必须先记录现有 Python、PyTorch、CUDA 和依赖版本；
- 可用环境优先复用；
- 需要联网安装、切换 CUDA wheel 或重建 Conda 环境时必须暂停并询问用户；
- 验证成功后再生成精确 lock 文件。

下载外部 Gazebo 场景后，先确认其版本。

如果场景只兼容 Gazebo Harmonic：

- 不直接污染 Humble/Fortress 环境；
- 新建独立 Docker 镜像；
- 或评估迁移到 ROS 2 Jazzy + Gazebo Harmonic；
- 不在同一环境混装不兼容版本。

## 9.3 Conda 训练环境

建议文件：

```text
envs/sgcf_train.yaml
```

基础版本：

```yaml
name: sgcf_train
channels:
  - conda-forge
dependencies:
  - python=3.10
  - pip
  - numpy=1.26.4
  - scipy=1.13
  - matplotlib
  - pandas
  - jupyter
  - pip:
      # PyTorch 和 torchvision 不在此处硬编码版本。
      # 阶段 01 先检查现有可用环境；需要联网安装时必须暂停并由用户确认。
      # 安装成功后把实际版本写入 requirements-lock.txt / environment.txt。
      - opencv-python
      - shapely==2.0.7
      - scikit-learn
      - pyyaml
      - rich
      - loguru
      - tensorboard
      - pytest
      - pytest-cov
      - hypothesis
      - ruff
      - black
      - mypy
      - pre-commit
      - onnx
      - onnxruntime
      - cvxpy==1.7.5
      - cvxpylayers==0.1.6
      - osqp==1.1.1
```

说明：

- CUDA wheel 按训练机驱动和 PyTorch 官方安装选择器安装；
- 你的 RTX 5070 Ti 当前项目可优先测试 CUDA 12.8 wheel；
- PyTorch 版本最终写入 lock 文件；
- 不应只写 `torch>=...`；
- 先通过 CUDA smoke test，再固定版本。

## 9.4 核心开发环境

核心包要求：

```text
Python 3.10
PyTorch
NumPy
SciPy
Shapely
OpenCV
CVXPY
OSQP
```

核心包不得导入：

```text
rclpy
sensor_msgs
tf2_ros
gazebo APIs
```

## 9.5 ROS 2 环境

ROS 2 工作空间使用：

```text
Ubuntu 22.04
ROS 2 Humble
Python 3.10
colcon
rosdep
rclpy
tf2_ros
message_filters
cv_bridge
image_transport
sensor_msgs
geometry_msgs
nav_msgs
visualization_msgs
diagnostic_msgs
rosbag2
```

ROS 节点原型可以用 Python。

部署版逐步迁移：

- fusion node：C++；
- inference node：C++ ONNX/OpenVINO；
- planner node：C++ OSQP。

## 9.6 Gazebo 环境

默认：

```text
ROS 2 Humble
Gazebo Fortress
ros_gz
```

必须提供：

```text
/scan
/camera/image_raw
/camera/camera_info
/odom
/cmd_vel
/tf
/tf_static
/clock
```

## 9.7 CPU 部署环境

x86 Intel：

```text
Ubuntu 22.04
ROS 2 Humble
OpenVINO 或 ONNX Runtime
OSQP C/C++
Eigen3
OpenCV
```

ARM：

```text
Ubuntu 22.04 arm64
ROS 2 Humble
ONNX Runtime CPU
OSQP C/C++
Eigen3
OpenCV
```

部署端不依赖：

- CUDA；
- CvxpyLayer；
- 训练数据生成工具；
- TensorBoard；
- Jupyter。

---

# 10. 唯一项目根目录结构

```text
NeuPAN/
├── neupan/                         # 上游，只读
├── neupan_ros/                     # 上游，只读
├── neupan_ros2/                    # 上游，只读
├── docker/                         # 上游，只读
├── example/                        # 上游，只读
│
└── sgcf_nrmp_project/              # SGCF-NRMP 唯一项目根目录
    ├── README.md
    ├── LICENSE
    ├── COPYING_NOTICE.md
    ├── CHANGELOG.md
    ├── core/                       # Python 核心算法和训练
    │   ├── pyproject.toml
    │   ├── configs/
    │   ├── envs/
    │   ├── src/sgcf_nrmp/
    │   ├── scripts/
    │   ├── tests/
    │   └── assets/
    ├── ros2_ws/                    # ROS 2 工作空间
    │   └── src/
    ├── gazebo/                     # Gazebo 世界、机器人和桥接
    │   ├── worlds/
    │   ├── models/
    │   ├── launch/
    │   └── config/
    ├── deploy/                     # CPU 部署
    │   ├── cpp/
    │   ├── model_export/
    │   └── benchmark/
    ├── docs/                       # 项目文档与阶段记录
    ├── tools/                      # 项目级工具
    └── artifacts/                  # 默认 gitignore
        ├── stages/
        ├── datasets/
        ├── checkpoints/
        ├── logs/
        ├── bags/
        ├── videos/
        ├── figures/
        └── results/
```

禁止在仓库根目录新增 `sgcf_nrmp/`、`sgcf_nrmp_docs/`、
`sgcf_nrmp_artifacts/`、`sgcf_nrmp_ros2/`、`sgcf_nrmp_gazebo/`、
`sgcf_nrmp_deploy/` 或 `sgcf_nrmp_tools/`。本章后续未带前缀的核心路径
（例如 `src/sgcf_nrmp/`、`configs/`、`scripts/`、`tests/`）均相对于
`sgcf_nrmp_project/core/`。

---

# 11. 核心包逐文件设计

## 11.1 根文件

### `sgcf_nrmp_project/core/pyproject.toml`

职责：

- 包元数据；
- Python 版本；
- 运行依赖；
- 开发依赖；
- ruff/black/mypy/pytest 配置入口。

要求：

- 不在依赖中固定 GPU CUDA wheel；
- Torch 单独安装；
- 使用 `src` layout；
- 包名 `sgcf-nrmp`；
- Python `>=3.10,<3.12` 作为第一版范围。

### `sgcf_nrmp_project/core/README.md`

包括：

- 方法简介；
- 安装；
- 数据生成；
- 训练；
- 离线测试；
- 与 ROS 2 的关系；
- 当前完成状态；
- 已知问题。

### `sgcf_nrmp_project/COPYING_NOTICE.md`

记录：

- 参考或复制的 NeuPAN 文件；
- 原许可证；
- 修改摘要；
- 论文引用。

### `CHANGELOG.md`

按版本记录：

```text
0.1.0 data generator
0.2.0 lidar clearance field
0.3.0 nrmp solver
0.4.0 multimodal fusion
...
```

---

## 11.2 配置文件

### `configs/model/lidar_field.yaml`

定义：

- 点数 N；
- 局部邻居 K；
- MLP 通道；
- query dimension；
- 距离截断范围；
- 梯度输出；
- collision head。

### `configs/model/image_encoder.yaml`

定义：

- backbone；
- 输入尺寸；
- 输出 stride；
- 输出 channels；
- 是否冻结；
- 预训练权重；
- 归一化参数。

### `configs/model/fusion.yaml`

定义：

- 3×3 或 5×5 窗口；
- soft association；
- gate hidden dim；
- 时间差阈值；
- projection invalid fallback；
- semantic class 数量。

### `configs/model/clearance_field.yaml`

定义：

- geometry head；
- semantic head；
- reliability head；
- max margin；
- output scaling。

### `configs/train/geometry.yaml`

定义：

- batch size；
- epoch；
- optimizer；
- learning rate；
- loss weights；
- data split；
- noise augmentation；
- checkpoint policy。

### `configs/train/multimodal.yaml`

定义：

- 图像增强；
- LiDAR dropout；
- 外参扰动；
- 时间差扰动；
- RGB modality dropout；
- backbone freeze schedule。

### `configs/planner/diff_robot.yaml`

定义：

- horizon；
- dt；
- Q/R；
- speed bounds；
- acceleration bounds；
- safe distance；
- slack penalty；
- max SCP iterations；
- OSQP settings。

### `configs/data/procedural.yaml`

定义：

- 空间范围；
- 障碍数量；
- 障碍类型比例；
- LiDAR 参数；
- 机器人 footprint；
- query sampler；
- label resolution。

### `configs/data/gazebo.yaml`

定义：

- topics；
- frames；
- sample rate；
- world IDs；
- image format；
- bag path；
- semantic class mapping。

---

## 11.3 公共数据结构

### `src/sgcf_nrmp/types/geometry.py`

类：

```python
@dataclass(frozen=True)
class RobotFootprint:
    vertices: np.ndarray  # (M, 2)

@dataclass(frozen=True)
class Pose2D:
    x: float
    y: float
    yaw: float
```

职责：

- footprint 验证；
- 位姿矩阵；
- polygon 转换。

### `types/lidar.py`

类：

```python
@dataclass(frozen=True)
class LidarFrame:
    points_xy: np.ndarray
    valid_mask: np.ndarray
    ranges: np.ndarray
    angles: np.ndarray
    stamp_ns: int
    frame_id: str
```

### `types/camera.py`

类：

```python
@dataclass(frozen=True)
class CameraModel:
    K: np.ndarray
    distortion: np.ndarray
    width: int
    height: int
    frame_id: str
```

### `types/multimodal.py`

类：

```python
@dataclass(frozen=True)
class MultimodalFrame:
    image: np.ndarray
    lidar: LidarFrame
    camera: CameraModel
    T_camera_lidar: np.ndarray
    image_stamp_ns: int
```

### `types/field.py`

类：

```python
@dataclass(frozen=True)
class ClearancePrediction:
    distance: torch.Tensor
    gradient: torch.Tensor
    collision_logit: torch.Tensor
    semantic_margin: torch.Tensor
    reliability: torch.Tensor
```

### `types/planner.py`

类：

```python
@dataclass(frozen=True)
class PlannerInput:
    state: np.ndarray
    reference_states: np.ndarray
    reference_controls: np.ndarray
    multimodal_frame: MultimodalFrame | None
    lidar_frame: LidarFrame

@dataclass(frozen=True)
class PlannerOutput:
    action: np.ndarray
    states: np.ndarray
    controls: np.ndarray
    slack: np.ndarray
    status: str
    timings_ms: dict[str, float]
```

---

## 11.4 几何与投影

### `geometry/transforms.py`

函数：

```python
pose2d_to_matrix()
invert_transform()
transform_points_2d()
transform_points_3d()
```

要求：

- 明确矩阵方向；
- 函数名标明 source/target；
- 禁止含糊的 `T_lc`；
- 使用 `T_target_source` 命名。

### `geometry/camera_projection.py`

类：

```python
class CameraProjector:
    def project(
        points_lidar_xyz,
        T_camera_lidar,
        camera_model,
    ) -> ProjectionResult:
        ...
```

输出：

- uv；
- depth；
- valid mask；
- border distance。

不读取神经网络特征。

### `geometry/footprint_distance.py`

接口：

```python
class ClearanceLabeler:
    def clearance(
        footprint: RobotFootprint,
        query_pose: Pose2D,
        obstacles: list[Polygon],
    ) -> float:
        ...

    def collision(...) -> bool:
        ...

    def gradient_finite_difference(...) -> np.ndarray:
        ...
```

使用 Shapely 或自主 SAT 实现。

### `geometry/raycast.py`

职责：

- 从二维障碍几何模拟 LaserScan；
- 支持最大距离；
- 支持角分辨率；
- 加噪声和丢点；
- 输出 `LidarFrame`。

---

## 11.5 程序化数据

### `data/procedural/scene_generator.py`

类：

```python
class ProceduralSceneGenerator:
    def sample_scene(self, rng) -> Scene2D:
        ...
```

生成：

- 障碍 polygon；
- 材质 ID；
- 类别 ID；
- robot origin；
- 可选动态障碍。

第一版只生成静态障碍。

### `data/procedural/query_sampler.py`

采样策略：

- 均匀采样；
- 靠近碰撞边界采样；
- 狭窄区域采样；
- 安全区域采样。

边界样本比例应较高。

### `data/procedural/dataset_writer.py`

职责：

- 批量生成；
- 写入 `.npz` 或分片 `.pt`；
- 元数据；
- 固定随机种子；
- 支持续写；
- 校验文件完整性。

### `data/datasets/geometry_dataset.py`

PyTorch Dataset：

- 加载点云；
- 固定 N；
- 数据增强；
- 返回 query 和标签。

### `data/datasets/multimodal_dataset.py`

加载：

- RGB；
- LiDAR；
- 标定；
- query；
- geometry labels；
- semantic labels。

必须保证 RGB 和 LiDAR 同步增强。

### `data/splits.py`

职责：

- 按 world/sequence 分割；
- 防止帧泄漏；
- 输出 split manifest。

---

## 11.6 图像分支

### `models/image/mobile_encoder.py`

类：

```python
class MobileImageEncoder(nn.Module):
    def forward(self, image) -> ImageFeaturePyramid:
        ...
```

第一版：

- MobileNetV3-Small；
- 输出 1/8 特征图；
- 不使用完整分割 decoder；
- 可选额外 semantic logits head 用于可视化。

### `models/image/image_preprocess.py`

职责：

- resize；
- normalize；
- letterbox 或固定 crop；
- 保存几何映射关系；
- 不在模型内部隐式 resize。

---

## 11.7 LiDAR 分支

### `models/lidar/point_encoder.py`

类：

```python
class LidarPointEncoder(nn.Module):
    def forward(
        self,
        points_xy,
        ranges,
        valid_mask,
    ) -> torch.Tensor:
        ...
```

结构：

```text
Linear -> LayerNorm -> ReLU
Linear -> ReLU
```

输出每点特征，不做全局 pooling。

### `models/lidar/neighborhood.py`

类：

```python
class QueryNeighborhood:
    def gather(
        query_poses,
        points_xy,
        features,
        valid_mask,
        k,
    ) -> NeighborhoodBatch:
        ...
```

第一版可以用：

- `torch.cdist`；
- top-k；
- 固定小点数。

部署版改为 C++ kNN 或按 LiDAR 角索引局部采样。

---

## 11.8 融合分支

### `models/fusion/local_sampler.py`

输入：

- 图像 feature map；
- 投影 uv；
- projection valid；
- 3×3 offset grid。

输出：

- local image features；
- local validity；
- offset encoding。

使用 `grid_sample`，部署导出前确认 ONNX 支持。

若 ONNX 支持不稳定：

- 改成预计算双线性索引；
- 使用 gather + weighted sum。

### `models/fusion/soft_association.py`

类：

```python
class LocalSoftAssociation(nn.Module):
    def forward(
        self,
        lidar_features,
        image_window_features,
        offsets,
        valid_mask,
    ) -> torch.Tensor:
        ...
```

只在局部窗口做权重。

### `models/fusion/reliability_gate.py`

输入：

- LiDAR feature；
- image feature；
- confidence；
- time delta；
- border distance；
- projection valid。

输出 gate：

\[
a_i\in[0,1]
\]

### `models/fusion/sparse_fusion.py`

组合：

```python
class SparseGatedFusion(nn.Module):
    def forward(...) -> FusedPointFeatures:
        ...
```

必须支持：

```python
rgb_enabled=False
```

此时输出与 LiDAR-only 兼容。

---

## 11.9 净空场

### `models/field/geometry_head.py`

类：

```python
class GeometryClearanceHead(nn.Module):
    def forward(
        self,
        query_poses,
        local_points,
        local_lidar_features,
        local_mask,
    ) -> GeometryFieldOutput:
        ...
```

输出：

- distance；
- gradient；
- collision logit。

### `models/field/semantic_head.py`

类：

```python
class SemanticMarginHead(nn.Module):
    def forward(
        self,
        query_poses,
        local_fused_features,
        local_mask,
        frame_reliability,
    ) -> SemanticFieldOutput:
        ...
```

输出：

- nonnegative margin；
- reliability。

### `models/field/sgcf_model.py`

顶层模型：

```python
class SGCFModel(nn.Module):
    def encode_scene(self, multimodal_frame) -> SceneEncoding:
        ...

    def query(
        self,
        scene_encoding,
        query_poses,
    ) -> ClearancePrediction:
        ...

    def forward(
        self,
        image,
        points,
        calibration,
        query_poses,
        metadata,
    ) -> ClearancePrediction:
        ...
```

必须分开：

- `encode_scene()`；
- `query()`。

一个控制周期内场景编码只执行一次，多个查询共享编码结果。

---

## 11.10 损失与训练

### `training/losses/geometry_loss.py`

实现：

- distance loss；
- gradient loss；
- collision BCE；
- local linear consistency。

### `training/losses/semantic_loss.py`

实现：

- margin loss；
- reliability loss；
- fallback loss；
- gate sparsity 可选。

### `training/geometry_trainer.py`

职责：

- 几何分支预训练；
- AMP；
- checkpoint；
- validation；
- TensorBoard；
- 梯度裁剪；
- NaN 检查。

### `training/multimodal_trainer.py`

训练流程：

1. 加载几何 checkpoint；
2. 冻结 geometry head；
3. 训练 image/fusion/semantic；
4. 可选小学习率解冻；
5. 保存最佳验证模型。

### `training/checkpoint.py`

checkpoint 中保存：

```text
model_state
optimizer_state
scheduler_state
epoch
config
git commit
dataset manifest hash
torch version
cuda version
random seeds
```

### `training/metrics.py`

几何指标：

- clearance MAE；
- near-boundary MAE；
- gradient cosine；
- collision accuracy；
- false-safe rate。

语义指标：

- margin MAE；
- class-wise margin MAE；
- reliability AUROC；
- RGB dropout fallback error。

---

## 11.11 规划器

### `planner/dynamics.py`

实现：

```python
class DifferentialDriveModel:
    def rollout(...)
    def linearize(...)
```

与视觉模型完全解耦。

### `planner/reference.py`

职责：

- 从局部路径生成 reference states；
- 生成 reference speed；
- 处理路径末端；
- 不处理传感器数据。

### `planner/problem.py`

构建固定参数化 QP：

- state variables；
- control variables；
- slack；
- dynamics；
- bounds；
- collision constraints；
- objective。

### `planner/solver_cvxpy.py`

开发版求解器：

```python
class CvxpyNRMPSolver:
    def solve(parameters) -> SolverResult:
        ...
```

### `planner/solver_osqp.py`

部署方向：

- 固定 sparse pattern；
- 只更新数值；
- warm start；
- timeout；
- infeasible fallback。

### `planner/constraint_builder.py`

接口：

```python
class ClearanceConstraintBuilder:
    def build(
        nominal_states,
        prediction: ClearancePrediction,
        safe_distance,
    ) -> ConstraintParameters:
        ...
```

### `planner/alternating_planner.py`

类：

```python
class SGCFNRMPPlanner:
    def plan(
        current_state,
        reference,
        scene_encoding,
    ) -> PlannerOutput:
        ...
```

流程：

- initialize；
- field query；
- constraint build；
- QP solve；
- iterate；
- action output。

### `planner/fallback.py`

回退策略：

1. RGB 失效：LiDAR-only；
2. 网络异常：基于真实最近 LiDAR 点的紧急减速；
3. QP 超时：使用上周期可行控制；
4. QP infeasible：减速或停车；
5. 过近障碍：急停。

---

## 11.12 评估与可视化

### `evaluation/field_metrics.py`

输出：

- 距离误差分布；
- 梯度误差；
- 碰撞边界误差；
- false-safe rate；
- 不同噪声下指标。

### `evaluation/planner_metrics.py`

输出：

- success；
- collision；
- path length；
- time；
- min clearance；
- semantic clearance；
- jerk；
- solve time；
- P95 latency。

### `visualization/field_plot.py`

生成：

- GT clearance heatmap；
- predicted heatmap；
- error heatmap；
- gradient arrows；
- collision boundary。

### `visualization/fusion_plot.py`

生成：

- RGB + projected LiDAR；
- local window；
- gate values；
- semantic margin points。

### `visualization/trajectory_plot.py`

显示：

- nominal trajectory；
- optimized trajectory；
- robot footprint；
- clearance values；
- safety margin；
- obstacles。

---

# 12. 脚本设计

### `scripts/generate_geometry_dataset.py`

可运行：

```bash
python scripts/generate_geometry_dataset.py \
  --config configs/data/procedural.yaml
```

可见输出：

- 随机场景图；
- LiDAR 扫描图；
- clearance heatmap；
- 数据统计。

### `scripts/train_geometry.py`

输出：

- loss 曲线；
- validation metrics；
- 最佳 checkpoint；
- 固定测试场景可视化。

### `scripts/evaluate_geometry.py`

输出 HTML/Markdown 报告：

- MAE；
- boundary MAE；
- gradient；
- false-safe；
- CPU inference latency。

### `scripts/train_multimodal.py`

训练融合和语义分支。

### `scripts/evaluate_multimodal.py`

输出：

- PointPainting baseline；
- hard feature sampling；
- local soft fusion；
- gated fusion；
- modality dropout 对比。

### `scripts/run_offline_planner.py`

输入一个场景，输出轨迹图和控制序列。

### `scripts/benchmark_cpu.py`

测试：

- PyTorch FP32；
- ONNX Runtime FP32；
- ONNX Runtime INT8；
- OpenVINO FP32/INT8；
- QP solve latency。

### `scripts/export_onnx.py`

导出：

- image encoder；
- field model；
- 可选完整 scene encoder。

需要固定：

- N；
- T；
- K；
- image size。

---

# 13. 测试结构

```text
tests/
├── unit/
├── geometry/
├── data/
├── models/
├── planner/
├── integration/
└── deployment/
```

## 13.1 必须测试

### 数据与形状

- 点数 N=0；
- N<K；
- N=K；
- N>Nmax；
- invalid projection；
- image missing；
- stale image；
- NaN/Inf input。

### 几何

- 已知圆/矩形距离；
- footprint rotation；
- finite difference gradient；
- coordinate transform direction；
- camera projection。

### 模型

- RGB disabled；
- gate 归零；
- margin 非负；
- geometry output 不因 RGB 改变；
- ONNX output 与 PyTorch 接近。

### 安全评估

- `observable_clearance` 标签、预测和坐标定义一致；
- `world_clearance` 只用于完整环境评估；
- 优化轨迹执行真实几何复检；
- false-safe rate 定义为模型或规划器判断安全、但 `world_clearance < d_safe` 的样本或轨迹点比例；
- 分别报告总体与近碰撞边界 false-safe rate。

### 优化器

- 无障碍；
- 单障碍；
- 狭窄通道；
- infeasible；
- timeout；
- warm start；
- zero semantic margin；
- positive margin。

### 集成

- field + planner；
- RGB dropout；
- LiDAR dropout；
- calibration perturbation；
- repeated 1000 frames；
- memory growth。

---

# 14. 代码规范

## 14.1 Python

工具：

```text
black
ruff
mypy
pytest
pre-commit
```

规则：

- 行宽 88；
- 所有公共函数有类型注解；
- 所有张量 docstring 写形状；
- 设备通过参数传递，不使用全局 `device`；
- 禁止函数默认参数使用可变对象；
- 禁止 `except Exception: pass`；
- 禁止生产代码 `print()`；
- 使用 `logging` 或 `loguru`；
- 配置通过 dataclass/Pydantic 风格 schema 验证；
- 文件不超过约 500 行，超过则拆分；
- 一个文件一个核心职责；
- 随机数必须使用显式 RNG；
- 模型 forward 不读取全局配置；
- 所有 I/O 与数学模块分离。

张量命名：

```text
B: batch
N: points
T: horizon queries
K: local neighbors
C: channels
H, W: image
```

例如：

```python
points_xy: Tensor  # [B, N, 2]
query_pose: Tensor # [B, T, 4]
local_feat: Tensor # [B, T, K, C]
```

## 14.2 C++

部署版：

- C++17；
- clang-format；
- clang-tidy；
- RAII；
- 控制周期禁止动态内存；
- Eigen 固定大小优先；
- 所有求解器返回 status；
- 不在回调中长时间阻塞；
- 参数启动时加载；
- 日志限频。

## 14.3 YAML

- 所有单位写在 key 或注释中；
- 距离统一米；
- 时间统一秒；
- 角度内部统一弧度；
- topic 和 frame 不硬编码；
- 配置带 `schema_version`；
- 未知字段报错；
- 配置保存到 checkpoint。

## 14.4 Git

分支：

```text
main
develop
feature/data-generator
feature/lidar-field
feature/nrmp-solver
feature/multimodal-fusion
feature/ros2
feature/gazebo
feature/cpu-deploy
```

提交建议：

```text
feat:
fix:
test:
docs:
refactor:
perf:
build:
```

禁止直接在 main 上大规模重写。

## 14.5 上游完整性

每次 CI 执行：

```bash
git diff --exit-code -- neupan example docker
git -C neupan_ros diff --exit-code
git -C neupan_ros2 diff --exit-code
```

---

# 15. ROS 2 工作空间设计

```text
sgcf_nrmp_project/ros2_ws/src/
├── sgcf_nrmp_msgs/
├── sgcf_nrmp_perception/
├── sgcf_nrmp_fusion/
├── sgcf_nrmp_planner/
├── sgcf_nrmp_bringup/
├── sgcf_nrmp_visualization/
└── sgcf_nrmp_evaluation/
```

## 15.1 `sgcf_nrmp_msgs`

第一版尽量使用标准消息。

可选自定义：

```text
SemanticPointCloud.msg
PlannerDiagnostics.msg
```

但优先使用：

- `sensor_msgs/PointCloud2`；
- `diagnostic_msgs/DiagnosticArray`；
- `nav_msgs/Path`；
- `geometry_msgs/Twist`。

## 15.2 `sgcf_nrmp_perception`

节点：

### `image_encoder_node`

订阅：

```text
/camera/image_raw
/camera/camera_info
```

发布：

```text
/sgcf/image_features
/sgcf/image_debug
/sgcf/image_diagnostics
```

原型阶段可直接在 fusion node 内推理，稳定后再拆节点。

## 15.3 `sgcf_nrmp_fusion`

节点：

### `fusion_node`

订阅：

```text
/scan
/camera/image_raw
/camera/camera_info
/tf
```

功能：

- 时间同步；
- LaserScan 转点；
- 投影；
- 特征采样；
- 融合；
- 发布 debug。

发布：

```text
/sgcf/fused_points
/sgcf/projected_image
/sgcf/fusion_diagnostics
```

## 15.4 `sgcf_nrmp_planner`

节点：

### `planner_node`

订阅：

```text
/scan 或 /sgcf/fused_points
/goal_pose
/global_plan
/tf
```

发布：

```text
/cmd_vel
/sgcf/local_plan
/sgcf/nominal_plan
/sgcf/clearance_markers
/sgcf/planner_diagnostics
```

参数：

- control rate；
- model paths；
- planner config；
- RGB enable；
- fallback mode；
- CPU thread count。

## 15.5 `sgcf_nrmp_bringup`

launch：

```text
core.launch.py
perception.launch.py
planner.launch.py
gazebo.launch.py
experiment.launch.py
```

## 15.6 QoS

传感器：

```text
best_effort
volatile
depth 5
```

控制和目标：

```text
reliable
depth 5
```

## 15.7 时间同步

使用 ApproximateTime：

- image；
- scan；
- CameraInfo。

最大时间差可配置。

超过阈值：

```text
RGB reliability = 0
```

不阻塞 LiDAR 规划。

---

# 16. Gazebo 设计

## 16.1 默认组合

默认：

```text
ROS 2 Humble
Gazebo Fortress
ros_gz
```

下载场景后执行兼容性检查：

- `.world` 还是 `.sdf`；
- SDF 版本；
- `model://` 依赖；
- 插件；
- Gazebo Classic 或新 Gazebo；
- 场景许可证；
- 纹理路径；
- 物理单位。

## 16.2 机器人

第一版：

- 差速；
- footprint 与训练标签一致；
- 2D LiDAR；
- RGB camera；
- contact sensor；
- ground-truth pose。

传感器话题：

```text
/scan
/camera/image_raw
/camera/camera_info
/contact
/odom
```

## 16.3 场景资产

下载场景放入：

```text
sgcf_nrmp_project/gazebo/worlds/vendor/<scene_name>/
```

保留：

- 原文件；
- LICENSE；
- source metadata；
- 不直接修改原场景。

适配文件单独存放：

```text
worlds/adapters/<scene_name>_overlay.sdf
```

## 16.4 语义对象

人、车、机器人等关键对象建议由本项目单独 spawn：

- 类别可控；
- 位置可控；
- 轨迹可控；
- ground truth 可获得；
- 重复实验一致。

## 16.5 Gazebo 数据采集

节点记录：

- rosbag2；
- 图像；
- LaserScan；
- TF；
- object state；
- collision；
- goal；
- cmd_vel。

同时生成 manifest。

---

# 17. Codex 分阶段开发任务

> 下列阶段为唯一执行顺序，取代旧版文档中的 Phase 0～12。  
> Codex 每次只执行一个阶段，完成后强制停止。

## 阶段 01：仓库审计、基线确认与独立工程骨架

### 目标

确认当前 NeuPAN 仓库状态，记录并隔离 DeepSeek/Color-DUNE 错误修改，将官方提交 `579e7af` 冻结为唯一可复现算法基线，并建立不修改上游源码的 SGCF-NRMP 独立项目骨架。

### 开始前检查

Codex 必须运行并记录：

```bash
pwd
git status --short
git log --oneline -10
git remote -v
git submodule status || true
git -C neupan_ros status --short || true
git -C neupan_ros2 status --short || true
python --version
which python
conda info --envs || true
```

并在受保护目录中搜索：

```text
class_embed
point_class
semantic DUNE
color DUNE
num_classes
mowen_color
neupan_ros_color
```

### 已确认基线与隔离规则

- 唯一算法基线：`579e7afa239cd7ff61f7f63fbd4aaaecbb136d3b`；
- `54a291c` 及当前工作树中的 `class_embed`、`point_class`、Semantic DUNE、修改后的 DUNE/NRMP/DUNETrain、`neupan_ros_color` 均为已确认错误修改；
- 不恢复、不分析其算法效果、不建立兼容层、不作为实验对比；
- 阶段 01 只记录它们相对 `579e7af` 的文件差异；
- 后续参考基线源码时使用 `git show 579e7af:<path>`、独立只读快照或等价方式，不得用当前受污染工作树内容替代官方基线；
- 不修改受保护目录来“清理”当前工作树。

只有当 `579e7af` Git 对象不存在、校验失败或无法读取时才构成阻塞，并停止请求用户提供可信基线对象。

### 在基线明确后的任务

创建：

```text
sgcf_nrmp_project/core/
sgcf_nrmp_project/tools/
sgcf_nrmp_project/docs/
sgcf_nrmp_project/artifacts/
```

实现：

- `pyproject.toml`；
- 最小 `src/sgcf_nrmp/__init__.py`；
- `src/sgcf_nrmp/version.py`；
- `tests/test_import.py`；
- `sgcf_nrmp_project/tools/check_upstream_clean.sh`；
- `sgcf_nrmp_project/tools/write_version_lock.py`；
- `.gitignore` 补充新项目产物，但不得覆盖用户现有规则；
- `sgcf_nrmp_project/COPYING_NOTICE.md`；
- 开发文档索引。

### 可见成果

- `repo_audit.md`；
- `environment_report.md`；
- 新项目目录树文本；
- `pytest` 导入测试结果；
- 上游版本锁文件；
- 可执行：

```bash
python -c "import sgcf_nrmp; print(sgcf_nrmp.__version__)"
```

### 验收

- 独立包可导入；
- 测试通过；
- 受保护目录没有被本阶段修改；
- 没有安装 ROS、Gazebo 或大型模型；
- 没有开始数据生成代码。

### 阶段结束

生成报告并停止，等待用户确认进入阶段 02。

---

## 阶段 02：程序化二维场景、LiDAR 仿真与净空标签可视化

### 目标

不训练网络，先证明数据和标签定义正确。

### 任务

实现：

```text
src/sgcf_nrmp/types/geometry.py
src/sgcf_nrmp/types/lidar.py
src/sgcf_nrmp/geometry/transforms.py
src/sgcf_nrmp/geometry/footprint_distance.py
src/sgcf_nrmp/geometry/raycast.py
src/sgcf_nrmp/data/procedural/scene_generator.py
src/sgcf_nrmp/data/procedural/query_sampler.py
src/sgcf_nrmp/visualization/geometry_scene.py
scripts/demo_procedural_scene.py
```

第一版只支持：

- 圆形障碍；
- 轴对齐矩形；
- 旋转矩形；
- 墙；
- 简单走廊；
- 差速小车矩形 footprint；
- 2D LiDAR ray casting；
- clearance；
- collision；
- 有限差分 gradient。

### 必须测试

- 无障碍距离；
- 单圆距离；
- 单矩形距离；
- footprint 旋转；
- 碰撞与非碰撞；
- raycast 命中距离；
- gradient 数值合理；
- 固定随机种子可重复。

### 可见成果

至少生成：

```text
outputs/scene_obstacles.png
outputs/lidar_rays.png
outputs/clearance_heatmap.png
outputs/gradient_field.png
outputs/sample_labels.csv
```

用户应能直接看出：障碍附近 clearance 小，远处 clearance 大，梯度方向大致远离最近障碍。

### 验收

- 所有几何测试通过；
- 生成 1000 个随机场景无异常；
- 无 NaN/Inf；
- 可视化符合几何直觉；
- 不训练任何模型。

完成后停止。

---

## 阶段 03：几何训练数据集生成器与数据质量报告

### 目标

将阶段 02 的几何能力变成可复现、可分片、可检查的训练数据集。

### 任务

实现：

```text
configs/data/procedural.yaml
src/sgcf_nrmp/data/procedural/dataset_writer.py
src/sgcf_nrmp/data/datasets/geometry_dataset.py
src/sgcf_nrmp/data/splits.py
scripts/generate_geometry_dataset.py
scripts/inspect_geometry_dataset.py
```

要求：

- 分片保存；
- manifest；
- 数据版本；
- 随机种子；
- train/val/test 按 scene 划分；
- 边界附近 query 过采样；
- 支持中断后继续；
- 文件校验；
- 不把大数据加入 Git。

### 可见成果

- 数据分布直方图；
- clearance 分布；
- collision 比例；
- query 到障碍距离分布；
- 随机 16 个样本拼图；
- manifest JSON；
- 数据质量 Markdown 报告。

### 验收

- Dataset 可被 DataLoader 正确读取；
- train/val/test 无 scene 泄漏；
- 随机抽样可视化正确；
- 小型数据集可在本机完整生成；
- 大规模生成前先让用户确认磁盘预算。

若需要生成超过预设容量的大数据，必须停止并询问用户保存路径和磁盘预算。

完成后停止。

---

## 阶段 04：LiDAR-only Robot Clearance Field 模型

**Stage 06 后定位：`Learned Geometry Ablation`。** 本阶段代码、checkpoint 和实验成果完整保留，用于与 exact geometry 比较精度与梯度、展示学习净空场可行性，并解释最终架构选择；不得再描述为最终主几何模块，不重新训练或强行接入主 Planner。

### 目标

训练自主设计的 LiDAR 几何净空场，输出：

```text
observable_clearance
collision_logit
```

规划梯度由 `observable_clearance` 对查询位姿 autograd 获得；本阶段不实现独立 gradient head。

### 任务

实现：

```text
configs/model/lidar_field.yaml
configs/train/geometry.yaml
src/sgcf_nrmp/models/lidar/point_encoder.py
src/sgcf_nrmp/models/lidar/neighborhood.py
src/sgcf_nrmp/models/field/geometry_head.py
src/sgcf_nrmp/training/losses/geometry_loss.py
src/sgcf_nrmp/training/geometry_trainer.py
src/sgcf_nrmp/training/checkpoint.py
src/sgcf_nrmp/training/metrics.py
scripts/train_geometry.py
scripts/evaluate_geometry.py
```

### 训练策略

先执行小规模 smoke training：

- 100～500 个 batch；
- 验证 loss 可下降；
- 验证 checkpoint 可保存和恢复。

不得直接开始长时间训练。

长训练前必须向用户展示 smoke 结果并停止，由用户确认训练轮数、GPU 和保存路径。

### 可见成果

- loss 曲线；
- validation MAE；
- near-boundary MAE；
- false-safe rate；
- GT/预测 heatmap；
- autograd gradient 与有限差分 gradient 对比；
- 模型参数量；
- CPU 单 batch 推理时间。

### 验收

- smoke loss 明显下降；
- checkpoint 恢复一致；
- 输出 shape 正确；
- distance autograd gradient 通过有限差分检查；
- margin/RGB 代码尚未加入；
- 没有独立 gradient head；最终部署替代方案留到阶段 11。

完成 smoke training 后停止。完整训练必须由用户明确授权。

---

## 阶段 05：GT 净空场驱动的 NRMP-like 优化器

### 目标

暂时不用神经网络，以真实 clearance 和 gradient 验证优化器、动力学和碰撞约束。

### 任务

实现：

```text
configs/planner/diff_robot.yaml
src/sgcf_nrmp/planner/dynamics.py
src/sgcf_nrmp/planner/reference.py
src/sgcf_nrmp/planner/problem.py
src/sgcf_nrmp/planner/constraint_builder.py
src/sgcf_nrmp/planner/solver_cvxpy.py
src/sgcf_nrmp/planner/alternating_planner.py
src/sgcf_nrmp/planner/fallback.py
scripts/demo_gt_planner.py
```

优化问题必须包含位置/角度分量独立配置的 trust region。每轮优化后使用程序化场景完整几何复检轨迹；失败时缩小 trust region 重求解，超过次数后安全停止。

### 场景

- 无障碍直线；
- 单障碍绕行；
- 两障碍间通过；
- 走廊；
- 狭窄通道；
- 不可行场景。

### 可见成果

- 每个场景轨迹图；
- nominal 与 optimized 轨迹；
- footprint 动画 GIF；
- 每次 SCP 迭代轨迹；
- OSQP 状态和耗时 CSV；
- infeasible fallback 演示。

### 验收

- 无障碍跟踪正确；
- 可行场景不碰撞；
- 不可行场景安全停止；
- 求解器超时有回退；
- 固定问题结构；
- trust region 生效；
- 优化轨迹通过真实几何复检；
- 报告轨迹级和采样点级 false-safe rate；
- 上游 NeuPAN 未修改。

完成后停止。

---

## 阶段 06：学习几何接口审计与最终几何架构决策

### 目标

在接入前审计 Stage 04 模型能否满足可缓存场景编码接口，并结合 Stage 05 精确 Oracle 的正确性、实时性和安全职责作最终架构决策。

### 已完成审计

Stage 04 encoder 的输入包含 query-local point coordinates 与 query-dependent squared distance，无法使用现有 checkpoint 实现场景编码一次、多 query 复用。改变结构需要重新训练；本阶段禁止重新训练或放宽接口强行集成。

### 可见成果

- Stage 04 接口审计；
- learned vs exact 职责分析；
- 最终架构图与决策记录；
- Stage 04 消融保留说明；
- Stage 07 重定义。

### 验收

- 状态为 `COMPLETE WITH ARCHITECTURE DECISION`；
- `REPLACE_WITH_EXACT_GEOMETRY_FOR_FINAL_SYSTEM`；
- `KEEP_LEARNED_GEOMETRY_FIELD_AS_RESEARCH_ABLATION_ONLY`；
- 不修改、不删除、不重新训练 Stage 04；
- 不开始 RGB 或 Stage 07 实现。

完成后停止。

---

## 阶段 07：RGB–LiDAR Projection, Semantic Ground Truth and PointPainting Baseline

### 目标

建立 RGB–LiDAR 相机/投影/同步基础设施、语义 ground truth 和 PointPainting 基线；定义非负 semantic margin 标签，但不接入主规划器闭环。

### 任务

实现：

```text
src/sgcf_nrmp/types/camera.py
src/sgcf_nrmp/types/multimodal.py
src/sgcf_nrmp/geometry/camera_projection.py
src/sgcf_nrmp/models/image/image_preprocess.py
src/sgcf_nrmp/data/datasets/multimodal_dataset.py
src/sgcf_nrmp/types/semantic.py
src/sgcf_nrmp/models/fusion/point_painting.py
src/sgcf_nrmp/training/losses/semantic_margin_label.py
scripts/demo_projection.py
scripts/demo_point_painting.py
```

先使用合成相机、合成点云和 Oracle semantic labels 测试。只实现相机模型、时间戳/外参接口、语义类别数据结构、PointPainting、`m_sem >= 0` 标签和投影可视化。Sparse Local Soft Fusion 延后到 Stage 08。

### 可见成果

- 3D/2D 点投影图；
- 图像上的 LiDAR 点；
- 投影有效率；
- border distance 图；
- 外参扰动前后对比；
- 时间戳过期 fallback 报告。
- Oracle semantic label 与非负 margin 分布；
- PointPainting semantic-colored LiDAR 基线。

### 强制阻塞条件

如果需要真实相机标定文件、真实传感器参数或用户手动标定，停止并询问用户提供文件或完成标定。

### 验收

- 合成已知投影误差小于 1 像素；
- 图像外点保留；
- 变换方向命名明确；
- 不接 ROS；
- 不下载分割模型。
- 不接入 NRMP-like 主规划器闭环；
- 不实现 Sparse Local Soft Fusion。

完成后停止。

---

## 阶段 08：Sparse Local Soft Fusion 主方法

### 目标

在 Stage 07 的 PointPainting 基线上实现 CPU 友好的 Sparse Local Soft Fusion、soft association 和 reliability gate，并严格保持 exact geometry 不受 RGB 修改。

### 任务

实现：

```text
configs/model/fusion.yaml
src/sgcf_nrmp/models/fusion/local_sampler.py
src/sgcf_nrmp/models/fusion/soft_association.py
src/sgcf_nrmp/models/fusion/reliability_gate.py
src/sgcf_nrmp/models/fusion/sparse_fusion.py
src/sgcf_nrmp/models/field/semantic_head.py
scripts/train_multimodal.py
scripts/evaluate_multimodal.py
```

如果需要下载预训练权重：

- 先检查本地是否已有；
- 无本地权重则停止并向用户说明下载项、大小和许可证；
- 不自行静默下载。

### 可见成果

- 3×3 局部关联权重热图；
- 每点 reliability gate 可视化；
- RGB dropout/过期退化；
- 与 Stage 07 PointPainting 的精度、鲁棒性和 CPU 延迟对比。

### 验收

- RGB 缺失时 `r -> 0`；
- exact LiDAR geometry 不因 RGB 改变；
- semantic margin 非负；
- 主方法至少在一项预先声明的鲁棒指标上优于 PointPainting，且 CPU 延迟不超预算。

完成后停止。

---

## 阶段 09：Sparse Fusion 鲁棒性消融与语义裕度准备

### 目标

在 Stage 08 主方法实现后完成系统消融、标定/同步/RGB 失效鲁棒性评价，并为 Stage 10 的 semantic margin 规划器接入冻结接口；不重复实现 Stage 08。

### 任务

实现：

```text
configs/model/fusion.yaml
src/sgcf_nrmp/models/fusion/local_sampler.py
src/sgcf_nrmp/models/fusion/soft_association.py
src/sgcf_nrmp/models/fusion/reliability_gate.py
src/sgcf_nrmp/models/fusion/sparse_fusion.py
src/sgcf_nrmp/models/field/semantic_head.py
scripts/train_multimodal.py
scripts/evaluate_multimodal.py
```

### 必须消融

- PointPainting；
- 单像素深特征；
- 3×3 平均；
- 3×3 soft association；
- soft association + gate；
- RGB dropout training。

### 可见成果

- 3×3 权重热图；
- 每点 gate 可视化；
- 标定扰动曲线；
- 时间延迟扰动曲线；
- RGB 黑屏退化；
- 与 PointPainting 的指标和延迟对比。

### 验收

主方法必须至少在一项关键鲁棒指标上稳定优于 PointPainting，且 CPU 延迟未超预算。若没有优势，停止并报告，不得直接宣称主方法有效。

完成后停止。

---

## 阶段 10：语义安全裕度与完整 SGCF-NRMP 离线实验

### 目标

形成完整的 LiDAR 几何净空 + RGB–LiDAR 语义安全裕度 + NRMP-like 优化器。

### 任务

- 训练 semantic margin；
- 训练 reliability；
- 接入约束右端；
- 不允许 RGB 修改 geometry distance；
- 完成离线闭环消融。

### 可见成果

- human/static/vehicle margin heatmap；
- 同一几何布局不同语义下轨迹差异；
- RGB 正常、过期、黑屏时的行为视频；
- 完整消融表；
- 失败案例。

### 验收

- `margin >= 0`；
- `RGB disabled => margin≈0`；
- LiDAR 障碍始终保留；
- 人附近最小距离增加；
- RGB 错误不会使系统比 LiDAR-only 更激进。

完成后停止。

---

## 阶段 11：模型导出与纯 CPU 核心性能验证

### 目标

在进入 ROS/Gazebo 前证明核心网络和优化器可在 CPU 上运行。

### 任务

实现：

```text
scripts/export_onnx.py
scripts/benchmark_cpu.py
sgcf_nrmp_project/deploy/model_export/
sgcf_nrmp_project/deploy/benchmark/
```

比较：

- PyTorch FP32；
- ONNX Runtime FP32；
- 可行时 INT8；
- Intel CPU 可选 OpenVINO；
- OSQP warm start。

同时评估独立 gradient head：以 autograd gradient 为正确性基准，只有误差、局部线性化和 false-safe 指标通过验收时才允许用于部署。

### 强制阻塞条件

需要安装 OpenVINO、系统库或额外 runtime 且当前环境没有时，停止并询问用户是否安装。不得自行 sudo。

### 可见成果

- latency histogram；
- 平均/P95/P99；
- CPU 占用；
- 模型大小；
- 输出误差；
- 独立 gradient head 与 autograd 的误差、余弦相似度和 false-safe 差异；
- QP 求解时间；
- 10 Hz 预算表。

### 验收

- 目标 CPU 信息已记录；
- 主规划链路有明确延迟；
- 明确记录部署使用 autograd 还是通过验收的独立 gradient head；
- 不满足 10 Hz 时给出精简建议并停止，不得跳到 ROS 掩盖性能问题。

完成后停止。

---

## 阶段 12：ROS 2 离线节点与 rosbag 回放

### 目标

建立 ROS 2 节点接口，但先不使用 Gazebo。

### 开始前确认

需要用户确认：

- Ubuntu/ROS 2 版本；
- 是否已安装 Humble；
- 是否使用 Docker；
- 是否已有 rosbag 或测试数据。

如未确认，停止并提问。

### 任务

创建独立工作空间：

```text
sgcf_nrmp_project/ros2_ws/src/
├── sgcf_nrmp_msgs/
├── sgcf_nrmp_fusion/
├── sgcf_nrmp_planner/
├── sgcf_nrmp_visualization/
├── sgcf_nrmp_evaluation/
└── sgcf_nrmp_bringup/
```

实现：

- 标准 topic/frame 参数；
- image/scan 同步；
- TF 查询；
- fusion diagnostics；
- planner diagnostics；
- RViz markers；
- 合成 publisher 或 rosbag 回放。

### 可见成果

- `ros2 topic list`；
- TF 树；
- RViz 截图或录屏；
- 投影图；
- local plan；
- diagnostics；
- rosbag 回放报告。

### 验收

- RGB 掉线不阻塞 LiDAR planner；
- 过期图像 reliability=0；
- 节点持续运行；
- 不修改 `neupan_ros2`。

完成后停止。

---

## 阶段 13：最小 Gazebo 传感器验证世界

### 目标

先使用项目自建的最小世界验证机器人、LiDAR、RGB、TF 和控制链路，不立即接入外部下载场景。

### 开始前确认

需要用户确认：

- Gazebo Classic、Fortress、Garden、Harmonic 中实际使用哪一版本；
- ROS–Gazebo 桥接是否已安装；
- 是否允许安装缺失包。

不明确时必须停止。

### 任务

创建：

- 简单差速机器人；
- 矩形 footprint；
- 2D LiDAR；
- RGB camera；
- 简单箱体/走廊 world；
- `/cmd_vel`；
- `/scan`；
- `/camera/image_raw`；
- `/camera/camera_info`；
- `/odom`；
- `/tf`；
- `/clock`。

### 可见成果

- Gazebo 录屏；
- 相机图像；
- LaserScan；
- RViz TF；
- 投影验证；
- 手动或脚本 cmd_vel 运动。

如需要用户实际打开 GUI 检查，Codex 应暂停并给出精确命令和检查清单。

### 验收

- 传感器时间戳正确；
- TF 正确；
- 点投影到正确物体；
- 不运行完整规划器也能验证传感器链路。

完成后停止。

---

## 阶段 14：外部 Gazebo 场景接入

### 目标

将用户从 Gazebo 网站下载的场景作为外部资产接入。

### 强制开始条件

用户必须提供：

- 场景文件或本地路径；
- 下载来源；
- 许可证信息；
- Gazebo 版本；
- 期望出生点和目标区域。

缺少任一关键项时停止并提问，不自行下载随机场景。

### 任务

- 原场景只读保存；
- 创建 manifest；
- 检查 SDF/world 版本；
- 检查 model path；
- 创建 overlay/adapter；
- spawn 机器人；
- 验证光照、碰撞、LiDAR、相机；
- 不直接修改 vendor 原文件。

### 可见成果

- 场景兼容性报告；
- 机器人出生截图；
- 相机和 LiDAR 画面；
- 缺失模型清单；
- 场景运行录屏。

完成后停止。

---

## 阶段 15：Gazebo Oracle 语义闭环验证

### 目标

先用仿真 ground truth 类别验证规划思想，不让图像模型误差干扰算法判断。

### 任务

- 可控地 spawn static/human/vehicle；
- 生成 oracle semantic margin；
- 比较 LiDAR-only 与 semantic margin；
- 运行固定场景和随机种子；
- 记录碰撞和最小语义间距。

### 可见成果

- 同场景两种轨迹视频；
- 最小 human clearance；
- success/collision 表；
- Oracle margin 可视化；
- 失败案例。

### 验收

Oracle 语义必须在不显著破坏成功率的前提下改善目标安全指标。没有改善时停止分析模型，不进入图像预测闭环。

完成后停止。

---

## 阶段 16：Gazebo RGB 预测闭环与完整论文实验

### 目标

使用 RGB 图像编码、软融合和 reliability 完成完整闭环。

### 场景

- 静态走廊；
- 人与墙几何距离相近；
- RGB 视野外障碍；
- 光照变化；
- 图像模糊；
- 标定扰动；
- 时间延迟；
- RGB 黑屏。

### 对比

- NeuPAN baseline；
- LiDAR-only SGCF-NRMP；
- PointPainting；
- soft fusion；
- full SGCF-NRMP；
- Oracle upper bound。

### 可见成果

- 完整视频；
- 论文表格；
- 消融图；
- 鲁棒曲线；
- 延迟分解；
- 失败案例集。

### 验收

- 主结果可重复；
- 随机种子和配置保存；
- baseline 公平；
- RGB 失效安全退化；
- 论文结论只基于实际数据。

完成后停止。

---

## 阶段 17：真实 CPU 智能小车部署

### 目标

在真实小车纯 CPU 平台上运行。

### 强制开始条件

用户必须提供：

- CPU 型号；
- 核数和内存；
- x86/ARM；
- 相机型号；
- LiDAR 型号；
- ROS 2 版本；
- 机器人 footprint；
- 最大速度；
- 安全距离；
- 网络和设备权限；
- 是否允许安装 OpenVINO/ONNX Runtime/OSQP 系统包。

在用户提供前必须停止，不能假设硬件。

### 任务

- 选择 ONNX Runtime 或 OpenVINO；
- 量化；
- C++ fusion/planner；
- OSQP warm start；
- 预分配内存；
- 线程绑定；
- 传感器标定；
- 低速室内测试；
- 长时间运行。

### 可见成果

- CPU 占用；
- 平均/P95/P99 延迟；
- 温度和降频；
- 30～60 分钟报告；
- 实车视频；
- 紧急停止验证。

### 验收

- 规划环路达到目标频率；
- 传感器掉线有安全行为；
- 求解超时有回退；
- 真车测试从低速、空旷环境开始；
- 用户现场确认安全后才能提高速度。

完成后停止。

---

# 17.1 阶段执行命令模板

用户向 Codex 下达任务时，推荐使用：

```text
请严格按照 docs/SGCF_NRMP_Codex_Execution_Plan_V2.md 执行阶段 01。
只执行阶段 01，不要开始后续阶段。
遇到网络、sudo、GUI、硬件、Gazebo 场景、模型下载或上游代码恢复问题时立即停止并提问。
阶段完成后生成 stage_report.md 和可见成果，然后停止。
```

下一阶段：

```text
阶段 01 已确认通过。现在只执行阶段 02，遵守相同停止规则。
```

# 17.2 Codex 不得做出的“假完成”

以下情况不能算完成：

- 只创建空文件；
- 用随机数组冒充模型有效输出，却未标注为 mock；
- 只写代码不运行测试；
- 测试被 skip；
- 生成空白图；
- 训练 loss 未下降却说训练成功；
- Gazebo 未启动却说仿真通过；
- ROS topic 未发布却说 ROS 集成完成；
- CPU 未实测却声称达到 10 Hz；
- 网络失败后静默换源；
- 修改 NeuPAN 上游代码来规避设计问题。

# 18. CPU 实时预算

设计目标，不是预先保证的结果：

| 模块 | 频率 | 目标延迟 |
|---|---:|---:|
| RGB 预处理 | 3～5 Hz | 2～5 ms |
| Image Encoder INT8 | 3～5 Hz | 40～150 ms |
| LiDAR 投影/融合 | 10 Hz | 1～8 ms |
| Scene encoding | 10 Hz | 2～10 ms |
| T 个 field query | 10 Hz | 2～10 ms |
| QP/SCP | 10 Hz | 5～30 ms |
| 发布控制 | 10 Hz | <1 ms |

主控制周期：

\[
t_{fusion}+t_{field}+t_{QP}<100\text{ ms}
\]

RGB 异步，不要求每个控制周期都更新。

建议硬件：

```text
x86-64 4～8 核
支持 AVX2
8 GB RAM
```

ARM 可行但需要更小图像和更低 RGB 频率。

---

# 19. 论文实验设计

## 19.1 基线

- NeuPAN；
- LiDAR-only SGCF-NRMP；
- PointPainting + field；
- hard deep-feature fusion；
- full SGCF-NRMP。

可选传统基线：

- DWA；
- TEB；
- MPPI。

## 19.2 环境表示指标

- Clearance MAE；
- near-boundary MAE；
- collision false-safe rate；
- gradient cosine similarity；
- local linearization error；
- inference latency。

## 19.3 规划指标

- Success Rate；
- Collision Rate；
- Navigation Time；
- Path Length；
- Minimum Clearance；
- Human Minimum Clearance；
- Jerk；
- QP solve time；
- total latency。

## 19.4 鲁棒性

- RGB blackout；
- image blur；
- low light；
- LiDAR dropout；
- extrinsic perturbation；
- time delay；
- unseen texture；
- unseen layout；
- CPU overload。

## 19.5 关键消融

| ID | Geometry | RGB Feature | Soft Association | Gate | Semantic Margin |
|---|---:|---:|---:|---:|---:|
| A0 | LiDAR |  |  |  |  |
| A1 | LiDAR | class score |  |  | ✓ |
| A2 | LiDAR | deep feature |  |  | ✓ |
| A3 | LiDAR | deep feature | ✓ |  | ✓ |
| A4 | LiDAR | deep feature | ✓ | ✓ | ✓ |
| A5 | A4 | RGB dropout training | ✓ | ✓ | ✓ |

---

# 20. 风险与回退

## 20.1 净空梯度不稳定

回退：

- 减小 query 范围；
- 加强 local linear consistency；
- 使用 GT gradient 辅助；
- 梯度裁剪；
- 在 planner 中限制 trust region。

## 20.2 RGB 造成负收益

回退：

- 固定 geometry branch；
- 加强 gate；
- RGB 只输出类别安全 margin；
- 降级为 PointPainting baseline；
- 保留 LiDAR-only 论文主结果。

## 20.3 Gazebo 域差异过大

回退：

- domain randomization；
- 预训练图像 backbone；
- 真车少量数据微调；
- RGB 只做高风险类别；
- reliability 降低。

## 20.4 CPU 不实时

精简顺序：

1. 降低 RGB 频率；
2. 降低图像尺寸；
3. 冻结并导出 image encoder；
4. INT8；
5. 减少 N；
6. 减少 T；
7. 减少 K；
8. 去掉 soft association，回退硬采样；
9. 使用 LiDAR-only。

## 20.5 QP 求解超时

回退：

- 固定结构；
- warm start；
- 减少 horizon；
- 减少 SCP iteration；
- 上周期控制；
- 急停。

---

# 21. 还需要补充并尽早确定的内容

以下内容必须进入后续项目管理，但不影响先开始 Phase 0～2。

## 21.1 真实硬件规格

需要记录：

- CPU 型号；
- 核数；
- 内存；
- 是否 Intel；
- 是否 ARM；
- 是否有 NPU；
- 功耗限制；
- 散热条件。

这决定 OpenVINO 或 ONNX Runtime 选择。

## 21.2 传感器规格

需要记录：

- LiDAR 型号；
- 扫描点数；
- 频率；
- 最大距离；
- 相机型号；
- 分辨率；
- FPS；
- FOV；
- rolling/global shutter；
- 安装外参。

## 21.3 机器人 footprint

必须确定：

- 长；
- 宽；
- 传感器相对位置；
- 最大速度；
- 最大角速度；
- 加速度；
- 制动距离。

训练标签和部署机器人必须一致。

## 21.4 场景版本

下载 Gazebo 场景后记录：

- Gazebo 版本；
- SDF 版本；
- 许可证；
- 模型依赖；
- 下载来源；
- world hash。

## 21.5 安全规则

需要明确：

- 人的最小安全距离；
- 普通障碍最小距离；
- 急停距离；
- 规划器超时处理；
- TF 丢失处理；
- 图像过期阈值；
- LiDAR 丢失阈值。

## 21.6 数据治理

需要增加：

- 数据 manifest；
- 数据版本；
- 训练/测试世界隔离；
- 数据许可证；
- checkpoint 对应数据 hash；
- 不把大型数据提交 Git。

## 21.7 论文相关工作检索

正式确定论文题名前，需要系统检索：

```text
multimodal clearance field local planning
camera lidar neural signed distance field
camera lidar differentiable motion planning
multimodal collision field robot navigation
learned clearance field MPC
```

避免与已有方法高度重复。

---

# 22. 第一轮实际实施清单

当前只做：

```text
Phase 0
Phase 1
Phase 2
```

第一批创建文件：

```text
sgcf_nrmp_project/core/
├── pyproject.toml
├── README.md
├── COPYING_NOTICE.md
├── configs/data/procedural.yaml
├── configs/model/lidar_field.yaml
├── configs/train/geometry.yaml
├── src/sgcf_nrmp/types/
├── src/sgcf_nrmp/geometry/
├── src/sgcf_nrmp/data/procedural/
├── src/sgcf_nrmp/data/datasets/
├── src/sgcf_nrmp/models/lidar/
├── src/sgcf_nrmp/models/field/geometry_head.py
├── src/sgcf_nrmp/training/
├── src/sgcf_nrmp/visualization/
├── scripts/generate_geometry_dataset.py
├── scripts/train_geometry.py
├── scripts/evaluate_geometry.py
└── tests/
```

暂时不创建：

- 完整 ROS2 节点；
- Gazebo 场景；
- RGB 模型；
- 可微联合训练；
- 真车部署代码。

只有 Geometry Clearance Field 通过后再向下推进。

---

# 23. 方法可行性总结

## 模型完整性

完整：

- 输入定义明确；
- RGB 和 LiDAR 职责明确；
- 模型输出有物理含义；
- 输出能转换成优化约束；
- 规划器输出控制；
- RGB 失效有安全回退。

## 训练可行性

可行：

- 几何分支保留程序化数据优势；
- 不需要一开始采集大量图像；
- 多模态分支在 Gazebo 中生成同步数据；
- 距离、梯度、碰撞和语义裕度都有明确标签。

## 工程可行性

可行：

- 核心与 ROS 解耦；
- 分阶段实现；
- 每阶段有可见成果；
- 失败时能定位到具体模块；
- 不依赖修改 NeuPAN 源码。

## CPU 部署可行性

有条件可行：

- 稀疏点级融合；
- 轻量图像 backbone；
- RGB 低频异步；
- 固定 N/T/K；
- ONNX/OpenVINO；
- OSQP warm start；
- 不在线 backward；
- 必须在目标 CPU 上完成 profiling。

---

# 24. 主要参考工作

1. **NeuPAN: Direct Point Robot Navigation With End-to-End Model-Based Learning**  
   借鉴学习环境表示与模型优化耦合、滚动时域和近端交替思想。

2. **PointPainting: Sequential Fusion for 3D Object Detection**  
   作为图像语义附加到 LiDAR 点的基础基线。

3. **PointAugmenting: Cross-Modal Augmentation for 3D Object Detection**  
   借鉴图像中间特征装饰点云以及跨模态一致增强。

4. **TransFusion: Robust LiDAR-Camera Fusion for 3D Object Detection with Transformers**  
   借鉴软关联和对传感器错位的鲁棒融合思想。

5. **DeepFusion: LiDAR-Camera Deep Fusion for Multi-Modal 3D Object Detection**  
   借鉴深层跨模态特征融合和可学习对齐。

6. **DeepSDF: Learning Continuous Signed Distance Functions for Shape Representation**  
   借鉴连续隐式距离场表示。

7. **iSDF: Real-Time Neural Signed Distance Fields for Robot Perception**  
   借鉴距离和梯度作为下游规划接口。

8. **MobileNetV3**  
   借鉴移动 CPU 友好的视觉编码器设计。

9. **Fast-SCNN**  
   作为嵌入式轻量视觉前端备选。

10. **OSQP**  
    用于固定结构 QP、warm start 和后续嵌入式代码生成。

---

# 25. 最终开发主线

```text
冻结原 NeuPAN baseline
    ↓
程序化几何数据
    ↓
LiDAR-only Robot Clearance Field
    ↓
GT Field + NRMP-like Solver
    ↓
Learned Field + NRMP Core Loop
    ↓
PointPainting Baseline
    ↓
Sparse Local Soft Fusion
    ↓
Semantic Margin + Reliability
    ↓
CPU Core Benchmark
    ↓
ROS 2 Replay
    ↓
Gazebo Oracle Semantics
    ↓
Gazebo Predicted RGB
    ↓
ONNX/OpenVINO + OSQP CPU Deployment
```

本项目最重要的第一个里程碑不是 Gazebo，也不是 RGB，而是：

> **在纯程序化二维场景中，证明自主设计的 LiDAR Robot Clearance Field 能准确输出完整机器人 footprint 的净空距离与局部梯度，并能稳定驱动 NRMP-like 优化器完成避障。**

这个地基成功以后，再加入 RGB 才有意义。
