"""Shared MLP with padding-safe max and mean pooling."""

from __future__ import annotations

import torch
from torch import nn


class MaskedPointEncoder(nn.Module):
    def __init__(self, input_dim: int, hidden_dims: list[int], use_max_pool: bool = True, use_mean_pool: bool = True) -> None:
        super().__init__()
        if not use_max_pool and not use_mean_pool:
            raise ValueError("at least one pooling method is required")
        layers: list[nn.Module] = []
        previous = input_dim
        for hidden in hidden_dims:
            layers.extend((nn.Linear(previous, hidden), nn.LayerNorm(hidden), nn.SiLU()))
            previous = hidden
        self.network = nn.Sequential(*layers)
        self.output_dim = previous * (int(use_max_pool) + int(use_mean_pool))
        self.use_max_pool, self.use_mean_pool = use_max_pool, use_mean_pool

    def forward(self, features: torch.Tensor, valid_mask: torch.Tensor) -> torch.Tensor:
        encoded = self.network(features)
        mask = valid_mask.unsqueeze(-1)
        pooled: list[torch.Tensor] = []
        if self.use_max_pool:
            maximum = encoded.masked_fill(~mask, torch.finfo(encoded.dtype).min).amax(dim=1)
            maximum = torch.where(valid_mask.any(dim=1, keepdim=True), maximum, torch.zeros_like(maximum))
            pooled.append(maximum)
        if self.use_mean_pool:
            total = (encoded * mask).sum(dim=1)
            count = mask.sum(dim=1).clamp_min(1)
            pooled.append(total / count)
        return torch.cat(pooled, dim=-1)
