"""Launch the frozen one-way Stage 11C-A bridge configuration."""

from launch import LaunchDescription
from launch_ros.actions import Node


BRIDGE_ARGUMENTS = [
    "/clock@rosgraph_msgs/msg/Clock[gz.msgs.Clock",
    "/scan@sensor_msgs/msg/LaserScan[gz.msgs.LaserScan",
    "/camera/image_raw@sensor_msgs/msg/Image[gz.msgs.Image",
    "/camera/camera_info@sensor_msgs/msg/CameraInfo[gz.msgs.CameraInfo",
    "/odom@nav_msgs/msg/Odometry[gz.msgs.Odometry",
    "/cmd_vel@geometry_msgs/msg/Twist]gz.msgs.Twist",
]


def generate_launch_description() -> LaunchDescription:
    return LaunchDescription([
        Node(
            package="ros_gz_bridge",
            executable="parameter_bridge",
            name="stage11ca_parameter_bridge",
            output="screen",
            arguments=BRIDGE_ARGUMENTS,
        )
    ])
