"""Fixed-point scan conversion and geometry sample construction."""

from __future__ import annotations

import numpy as np
from shapely.geometry import Polygon

from sgcf_nrmp.data.datasets.geometry_schema import QUERY_CATEGORIES
from sgcf_nrmp.data.procedural.scene import ProceduralScene
from sgcf_nrmp.types.geometry import Pose2D
from sgcf_nrmp.types.lidar import LidarScan


def fixed_point_observation(scan: LidarScan, point_count: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Extract valid hits, deterministically decimate, then zero-pad without duplication."""
    if point_count not in {180, 256, 360}:
        raise ValueError("fixed point count must be one of 180, 256 or 360")
    valid_ranges = np.asarray(scan.ranges[scan.valid], dtype=np.float64)
    valid_points = np.asarray(scan.points_robot, dtype=np.float64)
    if valid_points.shape[0] != valid_ranges.shape[0]:
        raise ValueError("scan points and valid ranges are not aligned")
    if valid_points.shape[0] > point_count:
        indices = np.linspace(0, valid_points.shape[0] - 1, point_count, dtype=np.int64)
        valid_points = valid_points[indices]
        valid_ranges = valid_ranges[indices]
    count = valid_points.shape[0]
    points = np.zeros((point_count, 2), dtype=np.float32)
    ranges = np.zeros((point_count,), dtype=np.float32)
    mask = np.zeros((point_count,), dtype=bool)
    points[:count] = valid_points.astype(np.float32)
    ranges[:count] = valid_ranges.astype(np.float32)
    mask[:count] = True
    return points, ranges, mask


def build_sample(
    scene: ProceduralScene,
    footprint_robot: Polygon,
    scan: LidarScan,
    query_pose: Pose2D,
    query_category: str,
    scene_id: int,
    query_id: int,
    seed: int,
    point_count: int,
    observable_truncation: float,
    spatial_step: float,
    angular_step: float,
) -> dict[str, np.ndarray]:
    points, ranges, mask = fixed_point_observation(scan, point_count)
    label = scene.label(footprint_robot, query_pose, scan, observable_truncation)
    observable_gradient = scene.gradient(
        footprint_robot, query_pose, scan, observable_truncation,
        "observable_clearance", spatial_step, angular_step,
    )
    world_gradient = scene.gradient(
        footprint_robot, query_pose, scan, observable_truncation,
        "world_clearance", spatial_step, angular_step,
    )
    observable_gradient_valid = bool(
        observable_gradient.gradient_valid
        and label.observable_available
        and label.observable_clearance < observable_truncation - spatial_step
    )
    return {
        "points_xy": points,
        "ranges": ranges,
        "point_valid_mask": mask,
        "query_pose": np.asarray(
            [query_pose.x, query_pose.y, np.sin(query_pose.yaw), np.cos(query_pose.yaw)], dtype=np.float32
        ),
        "observable_clearance": np.asarray(label.observable_clearance, dtype=np.float32),
        "world_clearance": np.asarray(label.world_clearance, dtype=np.float32),
        "observable_collision": np.asarray(label.observable_collision, dtype=bool),
        "world_collision": np.asarray(label.world_collision, dtype=bool),
        "observable_gradient": observable_gradient.as_array().astype(np.float32),
        "world_gradient": world_gradient.as_array().astype(np.float32),
        "observable_gradient_valid": np.asarray(observable_gradient_valid, dtype=bool),
        "world_gradient_valid": np.asarray(world_gradient.gradient_valid, dtype=bool),
        "observable_available": np.asarray(label.observable_available, dtype=bool),
        "query_category": np.asarray(QUERY_CATEGORIES[query_category], dtype=np.int8),
        "scene_id": np.asarray(scene_id, dtype=np.int64),
        "query_id": np.asarray(query_id, dtype=np.int64),
        "seed": np.asarray(seed, dtype=np.int64),
    }
