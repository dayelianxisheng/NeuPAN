"""Launch the frozen one-way Stage 11C-A bridge configuration."""

from pathlib import Path

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description() -> LaunchDescription:
    config = Path(get_package_share_directory("sgcf_nrmp_bridge")) / "config" / "stage11ca_bridge.yaml"
    return LaunchDescription([
        Node(
            package="ros_gzharmonic_bridge",
            executable="parameter_bridge",
            name="stage11ca_parameter_bridge",
            output="screen",
            parameters=[{"config_file": str(config)}],
        )
    ])
