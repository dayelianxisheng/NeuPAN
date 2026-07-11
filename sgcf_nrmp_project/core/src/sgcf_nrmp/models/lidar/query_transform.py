"""Differentiable query-frame transforms for x/y/sin(yaw)/cos(yaw)."""

from __future__ import annotations

import torch


def points_in_query_frame(points_xy: torch.Tensor, query_pose: torch.Tensor) -> torch.Tensor:
    if points_xy.ndim != 3 or points_xy.shape[-1] != 2:
        raise ValueError("points_xy must have shape [B,N,2]")
    if query_pose.ndim != 2 or query_pose.shape[-1] != 4:
        raise ValueError("query_pose must have shape [B,4]")
    delta = points_xy - query_pose[:, None, :2]
    sin_yaw, cos_yaw = query_pose[:, 2:3], query_pose[:, 3:4]
    local_x = cos_yaw * delta[..., 0] + sin_yaw * delta[..., 1]
    local_y = -sin_yaw * delta[..., 0] + cos_yaw * delta[..., 1]
    return torch.stack((local_x, local_y), dim=-1)


def query_gradient_to_xyyaw(query_gradient: torch.Tensor, query_pose: torch.Tensor) -> torch.Tensor:
    """Convert d/d[x,y,sin,cos] to d/d[x,y,yaw] by the chain rule."""
    yaw_gradient = query_gradient[:, 2] * query_pose[:, 3] - query_gradient[:, 3] * query_pose[:, 2]
    return torch.stack((query_gradient[:, 0], query_gradient[:, 1], yaw_gradient), dim=-1)
