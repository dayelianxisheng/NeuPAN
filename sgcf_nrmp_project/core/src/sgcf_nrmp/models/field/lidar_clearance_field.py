"""Lightweight LiDAR-only differentiable observable-clearance proxy."""

from __future__ import annotations

import torch
from torch import nn

from sgcf_nrmp.models.field.field_output import ClearanceFieldOutput
from sgcf_nrmp.models.lidar.point_encoder import MaskedPointEncoder
from sgcf_nrmp.models.lidar.query_transform import points_in_query_frame


class LidarClearanceField(nn.Module):
    def __init__(self, model_config: dict) -> None:
        super().__init__()
        self.clearance_clip_m = float(model_config["clearance_clip_m"])
        self.encoder = MaskedPointEncoder(
            5, list(model_config["point_hidden_dims"]),
            bool(model_config["use_max_pool"]), bool(model_config["use_mean_pool"]),
        )
        decoder_layers: list[nn.Module] = []
        previous = self.encoder.output_dim + 4
        for hidden in model_config["decoder_hidden_dims"]:
            decoder_layers.extend((nn.Linear(previous, hidden), nn.LayerNorm(hidden), nn.SiLU()))
            previous = hidden
        self.decoder = nn.Sequential(*decoder_layers)
        self.distance_head = nn.Linear(previous, 1)
        self.collision_head = nn.Linear(previous, 1) if model_config.get("use_collision_head", True) else None

    def forward(self, points_xy: torch.Tensor, ranges: torch.Tensor, point_valid_mask: torch.Tensor, query_pose: torch.Tensor) -> ClearanceFieldOutput:
        local = points_in_query_frame(points_xy, query_pose)
        squared_distance = torch.sum(local.square(), dim=-1, keepdim=True)
        features = torch.cat((local, ranges.unsqueeze(-1), squared_distance, point_valid_mask.unsqueeze(-1).to(local.dtype)), dim=-1)
        pooled = self.encoder(features, point_valid_mask)
        decoded = self.decoder(torch.cat((pooled, query_pose), dim=-1))
        distance = self.clearance_clip_m * torch.sigmoid(self.distance_head(decoded))
        collision = self.collision_head(decoded) if self.collision_head is not None else None
        return ClearanceFieldOutput(distance, collision)
