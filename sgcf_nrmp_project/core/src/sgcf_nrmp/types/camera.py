"""Pinhole-camera types using T_target_source transform names."""

from dataclasses import dataclass
import numpy as np


@dataclass(frozen=True)
class CameraIntrinsics:
    fx: float; fy: float; cx: float; cy: float; width: int; height: int; minimum_depth: float = 0.05

    def __post_init__(self):
        if min(self.fx,self.fy)<=0 or min(self.width,self.height)<=0 or self.minimum_depth<0: raise ValueError("invalid camera intrinsics")


@dataclass(frozen=True)
class ProjectionResult:
    uv: np.ndarray
    depth: np.ndarray
    valid_mask: np.ndarray
    border_distance_px: np.ndarray
