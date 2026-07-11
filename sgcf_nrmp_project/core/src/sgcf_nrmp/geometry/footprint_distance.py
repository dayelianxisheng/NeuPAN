"""Observable/world footprint clearance and finite-difference references."""

from __future__ import annotations

from collections.abc import Callable, Sequence

import numpy as np
from shapely.geometry import MultiPoint, Polygon
from shapely.ops import unary_union

from sgcf_nrmp.geometry.footprint import transform_footprint
from sgcf_nrmp.types.geometry import ClearanceLabel, GradientLabel, Pose2D


def clearance_labels(
    footprint_robot: Polygon,
    query_pose_world: Pose2D,
    obstacles_world: Sequence[Polygon],
    observable_points_world: np.ndarray,
    observable_truncation: float,
) -> ClearanceLabel:
    """Compute partial-observation and complete-world clearance labels."""
    footprint_world = transform_footprint(footprint_robot, query_pose_world)
    world_geometry = unary_union(list(obstacles_world)) if obstacles_world else None
    world_collision = bool(world_geometry is not None and footprint_world.intersects(world_geometry))
    world_clearance = 0.0 if world_collision else (
        float(footprint_world.distance(world_geometry)) if world_geometry is not None else float(observable_truncation)
    )

    points = np.asarray(observable_points_world, dtype=np.float64)
    observable_available = bool(points.size)
    if observable_available:
        observed_geometry = MultiPoint(points.reshape((-1, 2)))
        observable_collision = bool(footprint_world.intersects(observed_geometry))
        observable_clearance = 0.0 if observable_collision else float(footprint_world.distance(observed_geometry))
        observable_clearance = min(observable_clearance, float(observable_truncation))
    else:
        observable_collision = False
        observable_clearance = float(observable_truncation)

    return ClearanceLabel(
        observable_clearance=observable_clearance,
        world_clearance=world_clearance,
        observable_collision=observable_collision,
        world_collision=world_collision,
        observable_available=observable_available,
    )


def finite_difference_gradient(
    clearance_at_pose: Callable[[Pose2D], tuple[float, bool]],
    query_pose: Pose2D,
    spatial_step: float = 0.02,
    angular_step: float = 0.02,
    slope_discontinuity_tolerance: float = 0.5,
) -> GradientLabel:
    """Central finite difference with collision-boundary discontinuity detection.

    ``clearance_at_pose`` returns ``(clearance, collision)``. A gradient is invalid
    whenever either central-difference pair crosses a collision boundary or any
    sampled value is non-finite.
    """
    if spatial_step <= 0.0 or angular_step <= 0.0:
        raise ValueError("finite-difference steps must be positive")
    center_value, center_collision = clearance_at_pose(query_pose)
    samples = [
        clearance_at_pose(Pose2D(query_pose.x + spatial_step, query_pose.y, query_pose.yaw)),
        clearance_at_pose(Pose2D(query_pose.x - spatial_step, query_pose.y, query_pose.yaw)),
        clearance_at_pose(Pose2D(query_pose.x, query_pose.y + spatial_step, query_pose.yaw)),
        clearance_at_pose(Pose2D(query_pose.x, query_pose.y - spatial_step, query_pose.yaw)),
        clearance_at_pose(Pose2D(query_pose.x, query_pose.y, query_pose.yaw + angular_step)),
        clearance_at_pose(Pose2D(query_pose.x, query_pose.y, query_pose.yaw - angular_step)),
    ]
    values = np.asarray([item[0] for item in samples], dtype=np.float64)
    collisions = [bool(item[1]) for item in samples]
    collision_crossing = any(collisions[i] != collisions[i + 1] for i in (0, 2, 4)) or any(
        collision != bool(center_collision) for collision in collisions
    )
    steps = (spatial_step, spatial_step, angular_step)
    slope_crossing = any(
        abs((values[index] - center_value) / steps[index // 2] - (center_value - values[index + 1]) / steps[index // 2])
        > slope_discontinuity_tolerance
        for index in (0, 2, 4)
    )
    crosses = bool(collision_crossing or slope_crossing)
    valid = bool(np.all(np.isfinite(values)) and np.isfinite(center_value) and not crosses)
    gradient = np.asarray(
        [
            (values[0] - values[1]) / (2.0 * spatial_step),
            (values[2] - values[3]) / (2.0 * spatial_step),
            (values[4] - values[5]) / (2.0 * angular_step),
        ]
    )
    return GradientLabel(
        gx=float(gradient[0]),
        gy=float(gradient[1]),
        gyaw=float(gradient[2]),
        gradient_valid=valid,
        spatial_step=spatial_step,
        angular_step=angular_step,
        crosses_discontinuity=crosses,
    )
