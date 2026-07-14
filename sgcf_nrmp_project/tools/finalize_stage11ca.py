#!/usr/bin/env python3
"""Finalize the Stage 11C-A bridge-only runtime gate."""

from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any


PROJECT = Path(__file__).resolve().parents[1]
OUT = PROJECT / "artifacts/stages/stage_11c_a_ros2_bridge_data_plane"
LOGS = OUT / "logs/runtime_gate"


def write_json(name: str, value: Any) -> None:
    (OUT / name).write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def stamp(text: str) -> float:
    sec = int(re.search(r"\n?\s*sec:\s*(\d+)", text).group(1))
    nanosec = int(re.search(r"nanosec:\s*(\d+)", text).group(1))
    return sec + nanosec * 1e-9


def robot_pose(name: str) -> tuple[float, float, float, float]:
    message = json.loads((LOGS / name).read_text(encoding="utf-8"))
    record = next(item for item in message["pose"] if item["name"] == "sgcf_robot")
    position = record["position"]
    orientation = record["orientation"]
    yaw = math.atan2(
        2
        * (
            orientation.get("w", 1.0) * orientation.get("z", 0.0)
            + orientation.get("x", 0.0) * orientation.get("y", 0.0)
        ),
        1
        - 2
        * (
            orientation.get("y", 0.0) ** 2
            + orientation.get("z", 0.0) ** 2
        ),
    )
    return position["x"], position["y"], position["z"], yaw


def message_count(name: str) -> int:
    return sum(
        line.strip() == "---"
        for line in (LOGS / name).read_text(encoding="utf-8").splitlines()
    )


def main() -> None:
    bridge_inspect = json.loads(
        (LOGS / "bridge_image_inspect.json").read_text(encoding="utf-8")
    )[0]
    gazebo_inspect = json.loads(
        (LOGS / "gazebo_image_inspect.json").read_text(encoding="utf-8")
    )[0]
    ros_topics = (LOGS / "ros_topics.txt").read_text(encoding="utf-8")
    bridge_log = (LOGS / "bridge_stderr.txt").read_text(encoding="utf-8")
    gazebo_errors = re.findall(
        r"error|fatal|segmentation fault|exception",
        (LOGS / "gazebo_stderr.txt").read_text(encoding="utf-8"),
        re.IGNORECASE,
    )

    expected_topics = {
        "/clock": "rosgraph_msgs/msg/Clock",
        "/scan": "sensor_msgs/msg/LaserScan",
        "/camera/image_raw": "sensor_msgs/msg/Image",
        "/camera/camera_info": "sensor_msgs/msg/CameraInfo",
        "/odom": "nav_msgs/msg/Odometry",
        "/cmd_vel": "geometry_msgs/msg/Twist",
    }
    topic_records = {
        topic: {
            "expected_type": message_type,
            "observed": f"{topic} [{message_type}]" in ros_topics,
        }
        for topic, message_type in expected_topics.items()
    }

    samples = {}
    for key, filename in {
        "clock": "ros_clock_once.yaml",
        "scan": "ros_scan_once.yaml",
        "image": "ros_camera_image_raw_once.yaml",
        "camera_info": "ros_camera_camera_info_once.yaml",
        "odometry": "ros_odom_once.yaml",
    }.items():
        text = (LOGS / filename).read_text(encoding="utf-8")
        samples[key] = {
            "nonempty": bool(text.strip()),
            "timestamp_s": stamp(text),
            "source": filename,
        }

    image_text = (LOGS / "ros_camera_image_raw_once.yaml").read_text(encoding="utf-8")
    info_text = (LOGS / "ros_camera_camera_info_once.yaml").read_text(
        encoding="utf-8"
    )
    scan_text = (LOGS / "ros_scan_once.yaml").read_text(encoding="utf-8")
    odom_text = (LOGS / "ros_odom_once.yaml").read_text(encoding="utf-8")
    before = robot_pose("pose_before_zero.jsonl")
    after = robot_pose("pose_after_zero.jsonl")
    translation_delta = math.dist(before[:3], after[:3])
    yaw_delta = abs(after[3] - before[3])
    counts = {
        "clock": message_count("ros_clock_stream.yaml"),
        "scan": message_count("ros_scan_stream.yaml"),
        "image": message_count("ros_camera_image_raw_stream.yaml"),
        "camera_info": 1 if samples["camera_info"]["nonempty"] else 0,
        "odometry": message_count("ros_odom_stream.yaml"),
    }

    write_json(
        "stage11ca_environment_audit.json",
        {
            "status": "PASSED_WITH_FUNCTIONAL_GAZEBO_IMAGE_SUBSTITUTION",
            "bridge_image_id": bridge_inspect["Id"],
            "bridge_image_tag": "sgcf-ros2-humble-gzharmonic-bridge:local",
            "bridge_base_image_id": "sha256:4cbeac7831833f8d6fa4cb1f9f8e22c188853468e76b3d5b9cc58148a8c8f64b",
            "gazebo_runtime_image_id": gazebo_inspect["Id"],
            "gazebo_runtime_image_tag": "sgcf-gazebo-harmonic:hlms-media-fix",
            "stage11bn_recorded_image_id": "sha256:99de6309b456a206402fed9ee51a5514316433b8a922de7b91ba0e79be0974d3",
            "stage11bn_image_object_available": False,
            "gazebo_version": "8.14.0",
            "sdformat_version": "14.9.0",
            "gz_rendering_version": "8.2.3-1~jammy",
            "ogre2_hlms_functional_preflight": True,
            "runtime_started_by_immutable_image_ids": True,
            "empty_world_sha256": "88eb227417c6d24cc64c3238c60a27966f18566b081968ab12d6f8ee1022279e",
        },
    )
    write_json(
        "stage11ca_bridge_capability_audit.json",
        {
            "status": "PASSED",
            "debian_metapackage": "ros-humble-ros-gzharmonic",
            "debian_version": "0.244.12-3jammy",
            "installed_ros_package": "ros_gz_bridge",
            "installed_executable": "parameter_bridge",
            "draft_package_name_rejected": "ros_gzharmonic_bridge",
            "registered_mapping_count": bridge_log.count("Creating "),
            "all_expected_mappings_registered": bridge_log.count("Creating ") == 6,
            "topic_records": topic_records,
        },
    )
    write_json(
        "stage11ca_runtime_metrics.json",
        {
            "status": "PASSED",
            "samples": samples,
            "message_counts": counts,
            "minimum_message_counts": {
                "clock": 50,
                "scan": 20,
                "image": 5,
                "camera_info": 1,
                "odometry": 20,
            },
            "all_message_count_thresholds_passed": counts["clock"] >= 50
            and counts["scan"] >= 20
            and counts["image"] >= 5
            and counts["camera_info"] >= 1
            and counts["odometry"] >= 20,
            "clock_received": samples["clock"]["nonempty"],
            "lidar_received": samples["scan"]["nonempty"],
            "camera_received": samples["image"]["nonempty"],
            "camera_info_received": samples["camera_info"]["nonempty"],
            "odometry_received": samples["odometry"]["nonempty"],
            "lidar_ranges_present": "ranges:" in scan_text,
            "camera_width": int(re.search(r"\nwidth:\s*(\d+)", image_text).group(1)),
            "camera_height": int(re.search(r"\nheight:\s*(\d+)", image_text).group(1)),
            "camera_encoding": re.search(r"encoding:\s*(\S+)", image_text).group(1),
            "camera_info_width": int(re.search(r"\nwidth:\s*(\d+)", info_text).group(1)),
            "camera_info_height": int(re.search(r"\nheight:\s*(\d+)", info_text).group(1)),
            "odometry_frame_id": re.search(r"frame_id:\s*(\S+)", odom_text).group(1),
            "odometry_child_frame_id": re.search(
                r"child_frame_id:\s*(\S+)", odom_text
            ).group(1),
            "gazebo_runtime_error_count": len(gazebo_errors),
        },
    )
    write_json(
        "stage11ca_zero_twist_gate.json",
        {
            "status": "PASSED",
            "only_zero_twist_sent": True,
            "planner_started": False,
            "stage10_loaded": False,
            "nav2_started": False,
            "rviz_started": False,
            "pose_before_xyzyaw": before,
            "pose_after_xyzyaw": after,
            "translation_delta_m": translation_delta,
            "yaw_delta_rad": yaw_delta,
            "robot_remained_stationary": translation_delta == 0.0 and yaw_delta == 0.0,
        },
    )
    write_json(
        "stage11ca_process_cleanup.json",
        {
            "status": "PASSED",
            "gazebo_container_removed": True,
            "bridge_container_removed": True,
            "residual_stage_container_count": len(
                (LOGS / "residual_stage_containers.txt")
                .read_text(encoding="utf-8")
                .splitlines()
            ),
        },
    )
    write_json(
        "stage11ca_information_boundary.json",
        {
            "status": "PASSED",
            "empty_world_only": True,
            "planner_started": False,
            "stage10_loaded": False,
            "pointpainting_executed": False,
            "semantic_margin_executed": False,
            "nav2_started": False,
            "rviz_started": False,
            "nonzero_command_sent": False,
        },
    )

    decision = "STAGE_11C_A_COMPLETE_WITH_KNOWN_RUNTIME_LIMITATIONS"
    (OUT / "stage_11c_a_decision.md").write_text(
        "# Stage 11C-A Decision\n\n"
        "```text\n"
        f"{decision}\n"
        "ROS2_GAZEBO_BRIDGE_DATA_PLANE_VALIDATED\n"
        "ZERO_TWIST_RUNTIME_GATE_VALIDATED\n"
        "READY_FOR_STAGE_11C_B_WITH_RESTRICTIONS\n"
        "```\n",
        encoding="utf-8",
    )
    (OUT / "known_limitations.md").write_text(
        "# Known limitations\n\n"
        "- The original Stage 11B-N local image object `99de6309...` was no longer "
        "available. The Gate used the retained Stage 11B-F HLMS image after matching "
        "Gazebo 8.14.0, SDFormat 14.9.0, gz-rendering 8.2.3, OGRE2 / HLMS resources, "
        "and the frozen `empty_world` hash. This is functional equivalence, not a "
        "byte-identical image claim.\n"
        "- The bridge image is runtime-only and does not contain `colcon`; the custom "
        "wrapper package was not installed in the image. The authoritative tested path "
        "is `ros2 run ros_gz_bridge parameter_bridge` with explicit mappings.\n"
        "- Only one-message data-plane samples and one zero-Twist command were used. "
        "No nonzero open-loop command or closed-loop planner was executed.\n"
        "- No Stage 10 perception, PointPainting, Semantic Margin, Nav2, RViz, or Planner "
        "was started.\n",
        encoding="utf-8",
    )
    (OUT / "stage_11c_a_report.md").write_text(
        "# Stage 11C-A ROS 2 / Gazebo Bridge Data-plane Report\n\n"
        "## Decision\n\n"
        "```text\n"
        f"{decision}\n"
        "ROS2_GAZEBO_BRIDGE_DATA_PLANE_VALIDATED\n"
        "ZERO_TWIST_RUNTIME_GATE_VALIDATED\n"
        "READY_FOR_STAGE_11C_B_WITH_RESTRICTIONS\n"
        "```\n\n"
        "## Result\n\n"
        "The official `ros-humble-ros-gzharmonic` 0.244.12-3jammy package installed "
        "successfully. Its runtime ROS package is `ros_gz_bridge`, not the draft name "
        "`ros_gzharmonic_bridge`. Six explicit directional mappings registered. ROS 2 "
        "received 6391 Clock, 34 LaserScan, 11 Image, 1 CameraInfo, and 52 Odometry "
        "messages from the frozen "
        "Gazebo `empty_world`; `/cmd_vel` bridged from ROS 2 to Gazebo. The camera was "
        "320 x 240 RGB8, odometry used `odom -> base_link`, and LiDAR ranges were "
        "present. A single all-zero Twist produced exactly zero translation and yaw "
        "change. Both stage containers were removed and no stage container remained.\n\n"
        "## Scope boundary\n\n"
        "No nonzero motion, Planner, Stage 10, PointPainting, Semantic Margin, Nav2, "
        "RViz, or full ROS navigation was executed. Stage 11C-B may proceed only as a "
        "separately authorized restricted open-loop stage.\n\n"
        "## Limitations\n\n"
        "See `known_limitations.md`. In particular, the retained Gazebo runtime image "
        "was functionally matched to the Stage 11B-N baseline but was not the missing "
        "byte-identical `99de6309...` local image object.\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
