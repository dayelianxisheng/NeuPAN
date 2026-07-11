"""Reproducible query-pose sampling."""

from __future__ import annotations

import numpy as np

from sgcf_nrmp.types.geometry import Pose2D


def sample_query_poses(
    bounds: tuple[float, float, float, float], count: int, rng: np.random.Generator
) -> list[Pose2D]:
    if count < 0:
        raise ValueError("count must be non-negative")
    x_min, y_min, x_max, y_max = bounds
    xy = rng.uniform([x_min, y_min], [x_max, y_max], size=(count, 2))
    yaw = rng.uniform(-np.pi, np.pi, size=count)
    return [Pose2D(float(point[0]), float(point[1]), float(angle)) for point, angle in zip(xy, yaw)]
