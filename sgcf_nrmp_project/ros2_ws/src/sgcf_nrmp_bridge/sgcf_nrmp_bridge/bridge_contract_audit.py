"""Print and validate the frozen Stage 11C-A bridge contract."""

from __future__ import annotations

import json


BRIDGE_MAPPINGS = [
    {
        "topic": "/clock",
        "ros_type": "rosgraph_msgs/msg/Clock",
        "gz_type": "gz.msgs.Clock",
        "direction": "GZ_TO_ROS",
    },
    {
        "topic": "/scan",
        "ros_type": "sensor_msgs/msg/LaserScan",
        "gz_type": "gz.msgs.LaserScan",
        "direction": "GZ_TO_ROS",
    },
    {
        "topic": "/camera/image_raw",
        "ros_type": "sensor_msgs/msg/Image",
        "gz_type": "gz.msgs.Image",
        "direction": "GZ_TO_ROS",
    },
    {
        "topic": "/camera/camera_info",
        "ros_type": "sensor_msgs/msg/CameraInfo",
        "gz_type": "gz.msgs.CameraInfo",
        "direction": "GZ_TO_ROS",
    },
    {
        "topic": "/odom",
        "ros_type": "nav_msgs/msg/Odometry",
        "gz_type": "gz.msgs.Odometry",
        "direction": "GZ_TO_ROS",
    },
    {
        "topic": "/cmd_vel",
        "ros_type": "geometry_msgs/msg/Twist",
        "gz_type": "gz.msgs.Twist",
        "direction": "ROS_TO_GZ",
    },
]


def main() -> None:
    topics = [item["topic"] for item in BRIDGE_MAPPINGS]
    result = {
        "status": "PASSED" if len(topics) == len(set(topics)) == 6 else "FAILED",
        "runtime_package": "ros_gz_bridge",
        "runtime_executable": "parameter_bridge",
        "mapping_count": len(BRIDGE_MAPPINGS),
        "mappings": BRIDGE_MAPPINGS,
        "planner_topic_present": False,
        "stage10_topic_present": False,
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    if result["status"] != "PASSED":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
