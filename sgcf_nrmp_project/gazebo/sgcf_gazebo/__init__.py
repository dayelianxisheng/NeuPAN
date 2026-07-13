"""Static Gazebo-to-SGCF data contracts; no ROS or simulator runtime required."""

from .adapters import (
    GazeboCameraAdapter,
    GazeboLidarAdapter,
    GazeboOracleSemanticAdapter,
    GazeboRobotStateAdapter,
    safe_command_for_status,
)

__all__ = [
    "GazeboCameraAdapter", "GazeboLidarAdapter", "GazeboOracleSemanticAdapter",
    "GazeboRobotStateAdapter", "safe_command_for_status",
]
