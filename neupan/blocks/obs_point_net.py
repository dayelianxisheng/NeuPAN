"""
ObsPointNet — 障碍物点特征编码网络
功能：将每个 2D 障碍物点映射到潜在距离特征空间 μ（mu）
      μ 的维度 = 机器人凸包边数（edge_dim），对于 mowen 矩形是 4

架构：6 层 MLP（2/6 → 32 → 32 → 32 → 32 → 4）
      - 输入: 2D 几何位置 (x, y)  或  几何 + 语义嵌入 (x, y, embed)
      - 输出: mu (4,) 表示点到机器人各条边的距离编码
      - 可选: 语义类别嵌入层 (class_embed), 实现多模态融合

本文修改: 增加 class_embed 分支，num_classes=0 时完全等同于原版
"""

import torch.nn as nn
import torch

class ObsPointNet(nn.Module):
    def __init__(self, input_dim: int = 2, output_dim: int = 4,
                 num_classes: int = 0, class_embed_dim: int = 4) -> None:
        """
        Args:
            input_dim: 几何输入维度，默认 2 (x, y)
            output_dim: mu 输出维度 = 机器人凸包边数（矩形=4）
            num_classes: 语义类别数，0=不使用语义（纯几何原版）
            class_embed_dim: 每个类别的嵌入向量维度
        """
        super(ObsPointNet, self).__init__()

        hidden_dim = 32  # 隐藏层维度，原版保持

        # === 语义嵌入层（可选） ===
        # num_classes=0 时不创建嵌入层，eff_input_dim=2，完全等同原版
        # num_classes>0 时创建 Embedding 表，将类别id映射为稠密向量
        if num_classes > 0:
            self.class_embed = nn.Embedding(num_classes, class_embed_dim)
            eff_input_dim = input_dim + class_embed_dim  # 例: 2+4=6
        else:
            self.class_embed = None
            eff_input_dim = input_dim

        # === 6 层 MLP ===
        # 结构: Linear → LayerNorm → Tanh → Linear → ReLU → (重复)
        #       最后: Linear → ReLU（保证 mu 非负）
        # 输入输出维度:
        #   原版: 2 → 32 → 32 → 32 → 32 → 32 → 4
        #   多模态: 6 → 32 → 32 → 32 → 32 → 32 → 4
        self.MLP = nn.Sequential(
            nn.Linear(eff_input_dim, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.Tanh(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.Tanh(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.Tanh(),
            nn.Linear(hidden_dim, output_dim),
            nn.ReLU(),  # 确保 mu 非负（凸优化约束 mu >= 0）
        )

    def forward(self, x: torch.Tensor, class_ids: torch.Tensor = None) -> torch.Tensor:
        """
        Args:
            x: (B, input_dim)  — 通常是 (B, 2) 几何位置 [x, y]
            class_ids: (B,) 或 None — 每个点的类别id（从语义分割投影得到）
                      如果模型有嵌入层但未传入 class_ids，自动用 class=0 填充。
        Returns:
            mu: (B, output_dim) — 潜在距离特征编码
        """
        if self.class_embed is not None:
            if class_ids is not None:
                embed = self.class_embed(class_ids)  # (B, class_embed_dim)
            else:
                # 未提供类别时，默认用 class=0（背景/未知）
                embed = self.class_embed(
                    torch.zeros(x.shape[0], dtype=torch.long, device=x.device)
                )
            x = torch.cat([x, embed], dim=-1)  # (B, eff_input_dim)
        return self.MLP(x)
