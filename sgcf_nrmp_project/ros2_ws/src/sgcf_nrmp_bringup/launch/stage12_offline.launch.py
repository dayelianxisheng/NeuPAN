"""Documented Stage 12 component graph; the formal runner starts isolated processes."""
from launch import LaunchDescription
from launch_ros.actions import Node
def generate_launch_description():
    return LaunchDescription([Node(package='sgcf_nrmp_fusion',executable='offline_fusion'),Node(package='sgcf_nrmp_planner',executable='offline_planner'),Node(package='sgcf_nrmp_visualization',executable='offline_visualization'),Node(package='sgcf_nrmp_evaluation',executable='offline_diagnostics'),Node(package='sgcf_nrmp_bringup',executable='synthetic_publisher')])
