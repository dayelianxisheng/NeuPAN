"""Static-world 2D LiDAR ray casting."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
from shapely.geometry import GeometryCollection, LineString, MultiLineString, MultiPoint, Point, Polygon
from shapely.ops import unary_union

from sgcf_nrmp.geometry.transforms import inverse_transform_pose, transform_points
from sgcf_nrmp.types.geometry import Pose2D
from sgcf_nrmp.types.lidar import LidarConfig, LidarScan


def _coordinates(geometry: object) -> list[tuple[float, float]]:
    if isinstance(geometry, Point):
        return [(geometry.x, geometry.y)]
    if isinstance(geometry, (LineString, MultiPoint)):
        return [tuple(value) for value in geometry.coords] if isinstance(geometry, LineString) else [
            (point.x, point.y) for point in geometry.geoms
        ]
    if isinstance(geometry, (GeometryCollection, MultiLineString)):
        result: list[tuple[float, float]] = []
        for child in geometry.geoms:
            result.extend(_coordinates(child))
        return result
    return []


def simulate_lidar(
    obstacles_world: Sequence[Polygon],
    T_world_robot_pose: Pose2D,
    config: LidarConfig,
    rng: np.random.Generator,
) -> LidarScan:
    """Cast rays and return nearest visible surface hits.

    A valid hit is a boundary intersection in ``[range_min, range_max]`` that was
    not randomly dropped. Invalid beams retain ``range_max`` and do not create an
    observable point.
    """
    angles = config.angles
    ranges = np.full(config.num_beams, config.range_max, dtype=np.float64)
    valid = np.zeros(config.num_beams, dtype=bool)
    points_world: list[np.ndarray] = []
    world_boundary = unary_union([polygon.boundary for polygon in obstacles_world]) if obstacles_world else None
    origin = np.asarray([T_world_robot_pose.x, T_world_robot_pose.y], dtype=np.float64)

    for index, angle_robot in enumerate(angles):
        angle_world = T_world_robot_pose.yaw + angle_robot
        endpoint = origin + config.range_max * np.asarray([np.cos(angle_world), np.sin(angle_world)])
        if world_boundary is None:
            continue
        intersection = LineString([origin, endpoint]).intersection(world_boundary)
        candidates = _coordinates(intersection)
        if not candidates:
            continue
        candidate_array = np.asarray(candidates, dtype=np.float64)
        candidate_ranges = np.linalg.norm(candidate_array - origin, axis=1)
        eligible = candidate_ranges >= config.range_min
        if not np.any(eligible):
            continue
        hit_range = float(np.min(candidate_ranges[eligible]))
        if hit_range > config.range_max:
            continue
        if rng.random() < config.dropout_probability:
            continue
        noisy_range = float(np.clip(hit_range + rng.normal(0.0, config.range_noise_std), config.range_min, config.range_max))
        if noisy_range >= config.range_max:
            continue
        ranges[index] = noisy_range
        valid[index] = True
        points_world.append(origin + noisy_range * np.asarray([np.cos(angle_world), np.sin(angle_world)]))

    point_array_world = np.asarray(points_world, dtype=np.float64).reshape((-1, 2)) if points_world else np.empty((0, 2))
    T_robot_world_pose = inverse_transform_pose(T_world_robot_pose)
    point_array_robot = transform_points(T_robot_world_pose, point_array_world)
    return LidarScan(ranges, valid, point_array_robot, point_array_world, angles)
