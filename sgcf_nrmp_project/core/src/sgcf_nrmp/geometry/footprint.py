"""Robot footprint construction and pose transforms."""

from __future__ import annotations

from shapely import affinity
from shapely.geometry import Polygon

from sgcf_nrmp.types.geometry import Pose2D


def rectangular_footprint(length: float, width: float) -> Polygon:
    """Create a centred robot-local rectangle with x-forward and y-left."""
    if length <= 0.0 or width <= 0.0:
        raise ValueError("footprint length and width must be positive")
    half_length, half_width = length / 2.0, width / 2.0
    return Polygon(
        [
            (-half_length, -half_width),
            (half_length, -half_width),
            (half_length, half_width),
            (-half_length, half_width),
        ]
    )


def transform_footprint(footprint_robot: Polygon, T_world_robot_pose: Pose2D) -> Polygon:
    """Transform a robot-local footprint into the world frame."""
    rotated = affinity.rotate(footprint_robot, T_world_robot_pose.yaw, origin=(0, 0), use_radians=True)
    return affinity.translate(rotated, T_world_robot_pose.x, T_world_robot_pose.y)
