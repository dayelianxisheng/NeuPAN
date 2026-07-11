"""Two-dimensional LiDAR configuration and scan types."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class LidarConfig:
    angle_min: float = -3.141592653589793
    angle_max: float = 3.141592653589793
    num_beams: int = 181
    range_min: float = 0.05
    range_max: float = 12.0
    range_noise_std: float = 0.0
    dropout_probability: float = 0.0

    def __post_init__(self) -> None:
        if self.num_beams < 1:
            raise ValueError("num_beams must be positive")
        if self.angle_max < self.angle_min:
            raise ValueError("angle_max must be >= angle_min")
        if not 0.0 <= self.dropout_probability <= 1.0:
            raise ValueError("dropout_probability must be in [0, 1]")
        if not 0.0 <= self.range_min < self.range_max:
            raise ValueError("ranges must satisfy 0 <= range_min < range_max")

    @property
    def angles(self) -> np.ndarray:
        return np.linspace(self.angle_min, self.angle_max, self.num_beams, dtype=np.float64)


@dataclass(frozen=True)
class LidarScan:
    """Ranges and hit points; points are in robot-local x-forward/y-left coordinates."""

    ranges: np.ndarray
    valid: np.ndarray
    points_robot: np.ndarray
    points_world: np.ndarray
    angles: np.ndarray

    @property
    def valid_count(self) -> int:
        return int(np.count_nonzero(self.valid))
