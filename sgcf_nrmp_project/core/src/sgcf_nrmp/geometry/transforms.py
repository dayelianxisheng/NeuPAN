"""Explicit SE(2) transforms named ``T_target_source``."""

from __future__ import annotations

import numpy as np

from sgcf_nrmp.types.geometry import Pose2D


def matrix_from_pose(T_target_source_pose: Pose2D) -> np.ndarray:
    """Return homogeneous ``T_target_source`` from a planar pose."""
    c, s = np.cos(T_target_source_pose.yaw), np.sin(T_target_source_pose.yaw)
    return np.asarray(
        [[c, -s, T_target_source_pose.x], [s, c, T_target_source_pose.y], [0.0, 0.0, 1.0]],
        dtype=np.float64,
    )


def inverse_transform_pose(T_target_source_pose: Pose2D) -> Pose2D:
    """Return pose parameters for ``T_source_target``."""
    T_source_target = np.linalg.inv(matrix_from_pose(T_target_source_pose))
    return Pose2D(
        float(T_source_target[0, 2]),
        float(T_source_target[1, 2]),
        float(np.arctan2(T_source_target[1, 0], T_source_target[0, 0])),
    )


def transform_points(T_target_source_pose: Pose2D, points_source: np.ndarray) -> np.ndarray:
    """Transform ``(N,2)`` points from source frame into target frame."""
    points_source = np.asarray(points_source, dtype=np.float64)
    if points_source.size == 0:
        return np.empty((0, 2), dtype=np.float64)
    if points_source.ndim != 2 or points_source.shape[1] != 2:
        raise ValueError("points_source must have shape (N, 2)")
    homogeneous = np.column_stack((points_source, np.ones(points_source.shape[0])))
    return (matrix_from_pose(T_target_source_pose) @ homogeneous.T).T[:, :2]
