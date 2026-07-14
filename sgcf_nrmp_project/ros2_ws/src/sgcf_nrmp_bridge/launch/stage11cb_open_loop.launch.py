"""Launch the Stage 11C-B deterministic open-loop audit node."""

import os
from pathlib import Path

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description() -> LaunchDescription:
    config = (
        Path(get_package_share_directory("sgcf_nrmp_bridge"))
        / "config"
        / "stage11cb_command_profile.yaml"
    )
    return LaunchDescription(
        [
            Node(
                package="sgcf_nrmp_bridge",
                executable="stage11cb_open_loop_audit",
                name="stage11cb_open_loop_audit",
                output="screen",
                parameters=[str(config)],
                additional_env={
                    "STAGE11CB_LOG_DIR": os.environ.get("STAGE11CB_LOG_DIR", "/tmp")
                },
            )
        ]
    )

