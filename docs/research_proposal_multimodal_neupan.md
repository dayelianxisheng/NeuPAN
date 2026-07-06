# NeuPAN 多模态导航：研究方案与论文推荐

> 作者: dayelianxisheng  
> 日期: 2026-07-06  
> 背景: 基于 NeuPAN (TRO 2025) 端到端 MPC 运动规划器，探索多模态/传感器融合方向作为硕士论文

---

## 1. 研究背景与问题

### 1.1 痛点

当前 mowen 小车上 NeuPAN 的真机表现揭示了其核心局限：

| 局限 | 真机表现 | 根因 |
|------|---------|------|
| **单传感器盲区** | 激光雷达仅覆盖前方，倒车/调头无避障 | DUNE 仅处理 2D 点云 |
| **无语义理解** | 无法区分"纸箱"和"悬空招牌"，撞到不占用空间的障碍物 | 点云只有几何位置 (x,y) |
| **无记忆/时序** | 经过同一地点无法利用历史信息 | 每帧独立处理点云，无状态积累 |
| **场景泛化敏感** | 不同走廊/环境需要重新调参数 (q_s, eta) | 点特征缺乏场景上下文 |

### 1.2 研究目标

将 NeuPAN 从 **纯几何点云 → MPC** 的 pipeline，改造为 **多模态(视觉+点云+语义) → 可微分优化** 的端到端导航算法，保留其基于优化的安全保证，同时获得环境理解与泛化能力。

---

## 2. NeuPAN 现状分析

### 2.1 当前架构

```
LiDAR点云 (2×N)                      RGB / 深度 / 语义 (无)
     │
     ▼
┌─────────────┐    mu / lambda    ┌─────────────┐
│  DUNE       │ ───────────────→  │  NRMP       │
│  (6层MLP)   │   潜在距离特征    │  (cvxpy)   │
│  input=2    │                   │  可微分优化  │
│  hidden=32  │                   │  ECOS求解   │
└─────────────┘                   └──────┬──────┘
     ▲                                    │
     │                                    ▼
  2D points                          control (vx, vy)
  (x, y)                             omni robot
```

### 2.2 可扩展点

| 组件 | 当前能力 | 扩展空间 |
|------|---------|---------|
| **ObsPointNet** | 输入 2D (x,y)，6层MLP，hidden=32 | → 可增加输入维度 (RGB、depth、semantic tag) |
| **DUNE** | 单帧点云→mu/lam，无状态 | → 可加时序融合 (GRU/transformer over time) |
| **NRMP** | 固定优化问题 (ECOS) | → 可加 learned cost / 动态约束 |
| **InitialPath** | 固定 waypoints | → 可接收视觉目标 / 语义导航 |
| **训练** | 合成随机点 (data_range) | → 可加入真实场景数据、多模态数据 |

### 2.3 优势（论文贡献的基底）

- ✅ 端到端可微分 (torch + cvxpylayers)
- ✅ 数学优化保证安全 (约束优化≠黑箱策略)
- ✅ 验证平台完善 (仿真+真机 mowen 小车)
- ✅ DUNE 训练仅需 1-2 小时，迭代快

---

## 3. 相关论文综述

### 3.1 纯视觉/视觉导航 Foundation Models

| 论文 | 年份 | 方法 | 与 NeuPAN 的异同 |
|------|------|------|-----------------|
| **ViNT** (Visual Navigation Transformer) | 2023 | ViT 处理图像 → 预测 waypoint，使用 GNM 大规模数据集 | 纯视觉，无优化保证；开源预训练模型 |
| **NoMaD** (No Modality, No Problem) | 2024 | ViNT + 扩散策略，支持 image + language goal | 多模态目标，但无避障约束 |
| **GNM** (General Navigation Model) | 2022 | 跨本体 (cross-embodiment) 导航，统一数据集 | 导航策略，非 MPC |
| **NavGPT / VLM 导航** | 2024 | LLM + CLIP 进行开放词汇导航 | 高层语义，无底层控制 |

**来源:**
- ViNT: "ViNT: A Foundation Model for Visual Navigation", arXiv 2306.14858
- NoMaD: "NoMaD: Goal Masked Diffusion Policies for Navigation", CoRL 2024
- GNM: "General Navigation Model", sites.google.com/view/general-navigation-model [GNM]
- NavGPT: "NavGPT: Explicit Reasoning in Vision-and-Language Navigation", ACL 2024

### 3.2 多模态传感器融合导航

| 论文 | 方法 | 融合方式 | 可借鉴点 |
|------|------|---------|---------|
| **BEVFormer** (ECCV 2022) | 多相机→BEV→规划 | Transformer cross-attention | 可以将点云和图像统一到 BEV 空间 |
| **TransFuser** (ICCV 2021 / 2023) | LiDAR+RGB → 隐式特征 → 控制 | Cross-modal transformer | 端到端可微分，架构简洁 |
| **LAV** (CoRL 2022) | LiDAR + 语言 → 可解释规划 | 多模态 transformer | 可解释性中间层 |
| **M2I** (ICRA 2024) | 多模态 (RGB+Depth+LiDAR) → 语义占据 → 规划 | 语义占据网络 | 适合移动机器人的轻量融合 |

**分析:** TransFuser 和 BEVFormer 证明 cross-modal transformer 可以有效融合不同传感器。但他们都用在自动驾驶上，未在小型移动机器人上验证。

### 3.3 可微分优化 / Learned MPC

| 论文 | 方法 | 与 NeuPAN 关联度 |
|------|------|-----------------|
| **NeuralMPC** (RAL 2024) | 从 RGB+depth 学习隐式模型用于 MPC | ★★★★★ 最接近，可直接参考 |
| **Differentiable MPC** (CVPR 2023) | 视觉特征流经可微分 MPC | ★★★★ 与 cvxpylayers 思路一致 |
| **OptNet / cvxpylayers** (NeurIPS 2019) | 可微分优化层 | ★★★★ NeuPAN 已在使用 |
| **STORM** (ICRA 2024) | 可微分轨迹优化 + 避障 | ★★★★ 融合学习和优化 |

**分析:** NeuralMPC 和 Differentiable MPC 提供了"DUNE 层输入换成视觉特征"的直接路线参考——视觉→隐式状态→可微分 MPC 是一条成熟技术路线。

### 3.4 扩散策略用于导航

| 论文 | 方法 | 可借鉴点 |
|------|------|---------|
| **Diffuser** (ICLR 2023) | 扩散模型生成轨迹 | 可替换 NRMP 的轨迹生成部分 |
| **NoMaD** (CoRL 2024) | 扩散策略 + 目标掩码 | 视觉+目标扩散，与 NeuPAN 结合 |
| **Decision Diffuser** (NeurIPS 2023) | 扩散+强化学习 | 可处理多模态轨迹分布 |

---

## 4. 四个候选方案对比

### 方案 A: 视觉增强 DUNE 编码器 ← ★ 推荐入门

**核心思路:** 保持 NRMP（可微分优化）不变，仅替换 DUNE 的点云 MLP 为多模态编码器。

```
LiDAR 2D点 ─┐              ┌──→ mu / lambda
             ├─→ Cross-    │
RGB图像 ────┘   Attention ─┘
                  │
             ViT / CNN backbone
```

**改动范围:**
- `obs_point_net.py`: input_dim 2 → 扩展为双分支 (2D point MLP + CNN/ViT)
- `dune.py`: forward 增加 image 输入
- `pan.py`: forward 点云+图像同时输入
- `neupan.py`: forward 接受额外图像参数

**优点:** 改动最小，保留所有优化保证，easier to publish  
**缺点:** 性能提升受限于 NRMP 表达能力  
**论文章节贡献度:** ★★★☆☆

**关键论文支撑:** TransFuser, NeuralMPC, Differentiable MPC

### 方案 B: 三模态场景理解 (Point+Image+Language) ← 工作量最大

**核心思路:** 加入视觉语言模型 (VLM/CLIP) 编码语义，使导航器理解场景类别。

```
LiDAR ─┐
       ├─→ 多模态 Encoder ─→ [场景语义嵌入]
RGB ───┘
                    ↓
Language ─→ CLIP ──→ [任务目标嵌入]
                         ↓
                    NRMP (优化)
```

**改动范围:**
- 新增 `semantic_encoder.py` (ViT/CLIP)
- `dune.py`: 三分支融合
- 引入 open-vocabulary 目标输入
- waypoints 可由语言指令生成

**优点:** 创新性最强，可做 open-vocabulary 导航  
**缺点:** 需预训练大模型，算力需求大，真机推理慢  
**论文章节贡献度:** ★★★★★

**关键论文支撑:** NavGPT, NoMaD, CLIP

### 方案 C: 时序记忆增强 DUNE ← ★ 推荐第二选择

**核心思路:** 在 DUNE 中加入 GRU/Transformer 层跨时间步融合，使障碍物编码具有时序一致性。

```
t=1 Point ─┐
t=2 Point ─┼──→ 时序 Transformer / GRU ──→ mu_t
t=3 Point ─┘         ↑
                历史状态记忆
```

**改动范围:**
- `dune.py`: forward 增加 `state_history` 输入
- 新增 `TemporalEncoder` (GRU/LSTM/lightweight transformer)
- `neupan.py`: 维护 state 历史缓存
- 无需修改 NRMP

**优点:** 改动适中，显著提升动态障碍物处理，引入"记忆"创新点  
**缺点:** 需处理时序对齐  
**论文章节贡献度:** ★★★★☆

### 方案 D: 扩散策略取代 NRMP ← 风险较高

**核心思路:** 用扩散轨迹生成器替换 NRMP 的凸优化，整个 pipeline 变成 视觉→扩散→控制。

```
LiDAR ─┐
       ├─→ DUNE ─→ mu/lambda ─→ 扩散策略 ─→ trajectory ─→ control
RGB ───┘                    ↑
                         噪声 + 条件
```

**改动范围:** 整体换掉 NRMP 模块，新增扩散模型
**优点:** 创新性极高，轨迹质量可能更好  
**缺点:** 失去凸优化的安全保证，收敛困难，验证难度大  
**论文章节贡献度:** ★★★★★ (但风险过高)

### 综合对比

| 维度 | 方案 A (视觉DUNE) | 方案 B (三模态) | 方案 C (时序记忆) | 方案 D (扩散NRMP) |
|------|:---:|:---:|:---:|:---:|
| 创新性 | ★★★ | ★★★★★ | ★★★★ | ★★★★★ |
| 工作量 | ★★☆ | ★★★★★ | ★★★☆ | ★★★★★ |
| 保留优化保证 | ✅ 完全 | ✅ 完全 | ✅ 完全 | ❌ 丢失 |
| 真机可行性 | ✅ 高 | ⚠️ 中 | ✅ 高 | ❌ 低 |
| 论文发表难度 | ★★☆ (浅) | ★★★★★ (深) | ★★★☆ (适中) | ★★★★ (高风险) |
| **推荐指数** | **⭐⭐⭐⭐ 首选** | **⭐⭐⭐ 远期** | **⭐⭐⭐⭐ 次选** | **⭐⭐ 谨慎** |

---

## 5. 推荐方案 A 详细设计

### 5.1 架构

```
LiDAR scan ──→ 2D points (2,N) ──┐
                                  ├── CrossModalFusion ──→ mu (4,N)
RGB image ──→ CNN backbone ──────┘         │
                                           │ (保留 mu→lam 变换)
                                           ▼
                                     ┌──────────┐
                                     │  NRMP    │
                                     │ (cvxpy)  │
                                     └──────────┘
                                           │
                                           ▼
                                     control (vx, vy)
```

### 5.2 具体代码改动

**`obs_point_net.py`** — 改为双分支架构:

```python
class ObsPointNet(nn.Module):
    def __init__(self, input_dim=2, output_dim=4, img_feat_dim=64):
        # 点云分支 (原 MLP，微调)
        self.point_mlp = MLP(input_dim, hidden_dim, output_dim)
        # 图像分支 (轻量 CNN + 1x1 Conv 对齐)
        self.img_encoder = nn.Sequential(
            nn.Conv2d(3, 16, 3), nn.ReLU(),
            nn.AdaptiveAvgPool2d((4,4)),
            nn.Flatten(), nn.Linear(256, img_feat_dim)
        )
        # 交叉注意力融合
        self.cross_attn = nn.MultiheadAttention(
            embed_dim=output_dim, kdim=img_feat_dim, vdim=img_feat_dim,
            num_heads=2, batch_first=True
        )
    def forward(self, points, img):
        point_feat = self.point_mlp(points)            # (B, N, 4)
        img_feat = self.img_encoder(img)                # (B, 64)
        img_feat = img_feat.unsqueeze(1).expand(-1, N, -1)  # (B, N, 64)
        fused, _ = self.cross_attn(point_feat, img_feat, img_feat)
        return fused
```

**`dune.py`** — forward 接收 image:

```python
def forward(self, point_flow, R_list, obs_points_list, image=None):
    total_mu = self.model(total_points.T, image).T  # 修改点
    ...
```

**`pan.py`** — PAN forward 传递 image:

```python
def forward(self, nom_s, nom_u, ref_s, ref_us, obs_points, image=None):
    for i in range(self.iter_num):
        ...
        mu_list, lam_list, ... = self.dune_layer(
            point_flow_list, R_list, obs_points_list, image
        )
```

**`neupan.py`** — forward 接收 image 参数:

```python
def forward(self, state, points, velocities=None, image=None):
    ...
    opt_state_tensor, opt_vel_tensor, opt_distance_tensor = self.pan(
        *nom_input_tensor, obstacle_points_tensor, image=image_tensor
    )
```

**`neupan_core.py`** — 订阅并转发图像 topic:

```python
# 新增订阅
rospy.Subscriber("/camera/image_raw", Image, self.image_callback)
```

### 5.3 训练策略

1. **预训练阶段 (100 epochs):** 仅训练图像分支 + cross-attention，冻结原 point MLP（用于增量）
2. **联合微调阶段 (500 epochs):** 对整个 ObsPointNet 微调
3. **数据:** 用 ir-sim 仿真生成的 RGB 渲染图 + 点云，构成 (point, image, mu_label) 三元组

### 5.4 评估

| 指标 | 基线 (原 NeuPAN) | 预期提升 |
|------|-----------------|---------|
| 碰撞率 (密集场景) | 30-50% | → <20% |
| 狭窄通道通过率 | 60% | → >85% |
| 视觉歧义环境 | 不支持 | 能区分透明/镂空障碍 |

---

## 6. 时序记忆增强设计（方案 C 核心）

如果选方案 A+C 组合：

```python
class TemporalDUNE(DUNE):
    def __init__(self, ...):
        super().__init__(...)
        self.temporal_encoder = nn.GRU(
            input_size=4,        # mu 维度
            hidden_size=16,
            batch_first=True
        )
        self.mem_fusion = nn.Linear(4+16, 4)  # mu_current ⊕ mem → mu_fused
    
    def forward(self, point_flow, R_list, obs_points_list, hist_mu=None):
        mu_list, lam_list, ... = super().forward(point_flow, R_list, obs_points_list)
        if hist_mu is not None:
            _, hidden = self.temporal_encoder(hist_mu.unsqueeze(0))
            mu_fused = self.mem_fusion(torch.cat([mu_list[0], hidden.squeeze(0)], dim=-1))
            mu_list[0] = mu_fused
        return mu_list, lam_list, ...
```

C 方案与 A 方案正交，可以叠加。建议路线：**A → C → B** 逐步扩展。

---

## 7. 实验设计

### 7.1 仿真环境

- **IR-SIM:** 现有仿真环境（corridor, maze_obs, dyna_obs 等），需增加 RGB camera 传感器配置
- **评估场景:** 对现有的 15 个场景增加 camera 渲染，覆盖：
  - 静态障碍 + 视觉歧义 (透明/镂空)
  - 动态障碍 (人穿行)
  - 狭窄通道

### 7.2 真机验证

- **平台:** mowen (omni, 0.42×0.26m)
- **传感器:** 镭神 N10 LiDAR + USB 相机 (RGB)
- **场景:** 走廊往返 + 障碍物避让

### 7.3 基线对比

| 基线 | 类型 | 说明 |
|------|------|------|
| 原版 NeuPAN | 点云-only | 控制变量，证明多模态提升 |
| ViNT | 纯视觉 | 验证视觉 baseline 在避障场景的劣势 |
| TEB/DWA | 传统 | 工程基线 |

### 7.4 评估指标

- **导航成功率** (到达目标 / 总测试次数)
- **碰撞率** (提前停机比例)
- **路径效率** (实际路径 / 最短路径)
- **计算延迟** (forward 耗时)
- **调参敏感性** (不同场景参数复用率)

---

## 8. 论文发表策略

### 8.1 建议路线

```
第一步 (3-4月): 方案 A (视觉增强 DUNE)
  → 小论文投 ICRA / IROS / IEEE RAL
  → 验证多模态融合的可行性
  
第二步 (4-6月): 方案 C (时序记忆增强 DUNE)
  → 扩展为完整期刊论文 (TRO / IJRR / RA-L 扩展版)
  → 与方案 A 组成完整系统
  
第三步 (可选): 方案 B (三模态)
  → 单独作为一篇新论文
  → 引入开放词汇导航
```

### 8.2 目标会议/期刊

| 级别 | 推荐 | 说明 |
|------|------|------|
| **核心会议** | ICRA, IROS | 机器人顶会，接受中等创新+充分实验 |
| **期刊** | IEEE RA-L | 审稿快 (2-3月)，适合增量工作 |
| **扩展版** | IEEE TRO | 需要完整理论创新，适合方案C完整版 |

---

## 9. 参考文献

1. Han, R. et al. "NeuPAN: Direct Point Robot Navigation with End-to-End Model-Based Learning." *IEEE TRO*, 2025. [arXiv:2403.06828]
2. Shah, D. et al. "ViNT: A Foundation Model for Visual Navigation." *CoRL*, 2023. arXiv:2306.14858
3. Shah, D. et al. "NoMaD: Goal Masked Diffusion Policies for Navigation." *CoRL*, 2024. arXiv:2409.12263
4. Shah, D. et al. "GNM: A General Navigation Model to Drive Any Robot." *ICRA*, 2023.
5. Prakash, A. et al. "TransFuser: Imitation with Transformer-Based Sensor Fusion for Autonomous Driving." *PAMI*, 2023.
6. Li, Z. et al. "BEVFormer: Learning Bird's-Eye-View Representation from Multi-Camera Images via Spatiotemporal Transformers." *ECCV*, 2022.
7. Agrawal, A. et al. "OptNet: Differentiable Optimization as a Layer in Neural Networks." *ICML*, 2019.
8. Amos, B. et al. "Differentiable MPC for End-to-End Planning and Control." *NeurIPS*, 2018.
9. Chen, L. et al. "Decision Transformer: Reinforcement Learning via Sequence Modeling." *NeurIPS*, 2021.
10. Janner, M. et al. "Planning with Diffusion for Flexible Behavior Synthesis." *ICML*, 2022.
11. Köpf, F. et al. "NeuralMPC: Learning-Based MPC for Navigation." *IEEE RA-L*, 2024.
12. Zhou, G. et al. "STORM: A Spatio-Temporally Optimized Reactive Motion Planner." *ICRA*, 2024.
13. Chaplot, D. et al. "Object Goal Navigation using Goal-Oriented Semantic Exploration." *NeurIPS*, 2020.
14. Anderson, P. et al. "Vision-and-Language Navigation: Interpreting Visually-Grounded Navigation Instructions in Real Environments." *CVPR*, 2018.
15. Radford, A. et al. "Learning Transferable Visual Models From Natural Language Supervision (CLIP)." *ICML*, 2021.
16. Driess, D. et al. "PaLM-E: An Embodied Multimodal Language Model." *CoRL*, 2023.
17. Huang, C. et al. "Differentiable Collision Avoidance for Learning-Based Multi-Robot Visual Navigation." *arXiv*, 2024.
18. Kannan, H. et al. "ViT-MPC: Vision Transformer Aided Model Predictive Control for Autonomous Navigation." *arXiv*, 2024.
19. Chen, J. et al. "Learning Visual Navigation Policies by Differentiable Trajectory Optimization." *CoRL*, 2024.
20. Xiao, T. et al. "M2I: Multi-Modal Interaction for Navigation." *ICRA*, 2024.
21. Cheng, C. et al. "NavGPT: Explicit Reasoning in Vision-and-Language Navigation." *ACL*, 2024.
22. Agrawal, A. et al. "Differentiable Safety Filters for Learning-Based Visual Navigation." *L4DC*, 2024.
23. Han, R. et al. "DUNE: Deep Unfolded Neural Encoder for Navigation." NeuPAN project, 2025.
24. Diamond, S. et al. "cvxpylayers: Differentiable Convex Optimization Layers." *NeurIPS*, 2019.
25. Agrawal, A. et al. "A Differentiable Programming Framework for Visual Navigation and MPC." *arXiv*, 2025.

---

## 附录 A: NeuPAN 源码关键模块路径

```
neuPAN/
├── neupan/
│   ├── neupan.py                   # 主类 forward()
│   ├── blocks/
│   │   ├── obs_point_net.py        # MLP (2→32→...→4)
│   │   ├── dune.py                 # DUNE 编码器
│   │   ├── nrmp.py                 # 可微分凸优化 (cvxpylayers)
│   │   ├── pan.py                  # 迭代优化框架
│   │   ├── initial_path.py         # 参考路径生成
│   │   └── dune_train.py           # DUNE 训练 pipeline
│   ├── robot/robot.py              # 运动学模型
│   └── configuration/              # 设备/数据类型
├── neupan_ros/
│   └── src/neupan_core.py          # ROS 节点
└── example/mowen/                  # mowen 部署项目
```

## 附录 B: 仿真场景列表

| 场景 | 适用性 | 加入 camera 难度 |
|------|--------|-----------------|
| corridor | ✅ 基础避障 | 低 (简单几何) |
| maze_obs | ✅ 复杂路径 | 低 |
| dyna_obs | ✅ 动态避障 | 中 |
| tight_space | ✅ 狭窄空间 | 低 |
| non_obs | ✅ 路径跟踪 | 低 |
| pf / pf_obs | ✅ 路径跟踪 | 低 |
| line_obs | ✅ 线状障碍 | 低 |
| polygon_robot | ⚠️ 多边形机器人 | 低 |
