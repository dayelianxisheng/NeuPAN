from __future__ import annotations
import json

TOPICS = {
    '/clock':'rosgraph_msgs/msg/Clock','/scan':'sensor_msgs/msg/LaserScan',
    '/camera/image_raw':'sensor_msgs/msg/Image','/camera/camera_info':'sensor_msgs/msg/CameraInfo',
    '/odom':'nav_msgs/msg/Odometry','/tf':'tf2_msgs/msg/TFMessage','/tf_static':'tf2_msgs/msg/TFMessage',
    '/sgcf_nrmp/fusion':'std_msgs/msg/String','/sgcf/planner_candidate_cmd_vel':'geometry_msgs/msg/Twist',
    '/sgcf/planner_status':'std_msgs/msg/String','/sgcf/planner_diagnostics':'std_msgs/msg/String',
    '/sgcf_nrmp/local_plan':'nav_msgs/msg/Path','/sgcf_nrmp/markers':'visualization_msgs/msg/MarkerArray',
    '/diagnostics':'diagnostic_msgs/msg/DiagnosticArray'}

def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)
