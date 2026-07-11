"""Observable-only distance and optional collision losses."""

from __future__ import annotations

import torch
from torch import nn
from torch.nn import functional as F

from sgcf_nrmp.models.field.field_output import ClearanceFieldOutput


class ClearanceLoss(nn.Module):
    """No world-oracle field is accepted by this training-loss API."""

    def __init__(self, clearance_clip_m: float, category_weights: list[float], distance_weight: float = 1.0, collision_weight: float = 0.2) -> None:
        super().__init__()
        self.clearance_clip_m = clearance_clip_m
        self.register_buffer("category_weights", torch.tensor(category_weights, dtype=torch.float32))
        self.distance_weight, self.collision_weight = distance_weight, collision_weight

    def forward(
        self,
        output: ClearanceFieldOutput,
        observable_clearance: torch.Tensor,
        observable_collision: torch.Tensor,
        query_category: torch.Tensor,
    ) -> dict[str, torch.Tensor]:
        target = observable_clearance.clamp(0.0, self.clearance_clip_m)
        per_sample = F.smooth_l1_loss(output.observable_clearance, target, reduction="none")
        weights = self.category_weights[query_category.long().reshape(-1)].reshape_as(per_sample)
        distance_loss = torch.mean(per_sample * weights)
        collision_loss = torch.zeros((), device=distance_loss.device)
        if output.observable_collision_logit is not None:
            collision_loss = F.binary_cross_entropy_with_logits(
                output.observable_collision_logit, observable_collision.float()
            )
        total = self.distance_weight * distance_loss + self.collision_weight * collision_loss
        return {"total": total, "distance": distance_loss, "collision": collision_loss}
