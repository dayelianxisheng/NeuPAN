"""Geometry types using metres, radians and counter-clockwise yaw.

Robot-local axes are x-forward and y-left.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class Pose2D:
    """Planar pose expressed in a named target frame."""

    x: float
    y: float
    yaw: float

    def as_array(self) -> np.ndarray:
        return np.asarray([self.x, self.y, self.yaw], dtype=np.float64)


@dataclass(frozen=True)
class ClearanceLabel:
    """Clearance and collision labels at one query pose."""

    observable_clearance: float
    world_clearance: float
    observable_collision: bool
    world_collision: bool
    observable_available: bool


@dataclass(frozen=True)
class GradientLabel:
    """Finite-difference clearance gradient and its validity metadata."""

    gx: float
    gy: float
    gyaw: float
    gradient_valid: bool
    spatial_step: float
    angular_step: float
    crosses_discontinuity: bool

    def as_array(self) -> np.ndarray:
        return np.asarray([self.gx, self.gy, self.gyaw], dtype=np.float64)
