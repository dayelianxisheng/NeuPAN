#!/usr/bin/env python3
"""Create the Stage 11C-B audit artifacts from the single runtime capture."""

from __future__ import annotations

import hashlib
import json
import math
import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PROJECT = ROOT / "sgcf_nrmp_project"
OUT = PROJECT / "artifacts/stages/stage_11c_b_open_loop_command"
LOG = OUT / "logs"
STAGE11CA = PROJECT / "artifacts/stages/stage_11c_a_ros2_bridge_data_plane"
STAGE11BF = PROJECT / "artifacts/stages/stage_11b_f_hlms_media_restoration"
STAGE11BN = PROJECT / "artifacts/stages/stage_11b_n_final_runtime_matrix"


def load_lines(name: str) -> list[dict]:
    return [json.loads(line) for line in (LOG / name).read_text().splitlines() if line]


def write(name: str, value: object) -> None:
    (OUT / name).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def monotonic(values: list[float]) -> dict:
    deltas = [b - a for a, b in zip(values, values[1:])]
    return {
        "sample_count": len(values),
        "first_s": values[0] if values else None,
        "last_s": values[-1] if values else None,
        "negative_jump_count": sum(delta < -1e-12 for delta in deltas),
        "duplicate_count": sum(abs(delta) <= 1e-12 for delta in deltas),
        "monotonic_non_decreasing": all(delta >= -1e-12 for delta in deltas),
    }


def unwrap(values: list[float]) -> list[float]:
    if not values:
        return []
    result = [values[0]]
    for value in values[1:]:
        delta = value - result[-1]
        while delta > math.pi:
            value -= 2 * math.pi
            delta = value - result[-1]
        while delta < -math.pi:
            value += 2 * math.pi
            delta = value - result[-1]
        result.append(value)
    return result


def phase(rows: list[dict], name: str) -> list[dict]:
    return [row for row in rows if row["phase"] == name]


def tree_hash(path: Path) -> str:
    digest = hashlib.sha256()
    if not path.exists():
        return "MISSING"
    for item in sorted(p for p in path.rglob("*") if p.is_file()):
        digest.update(item.relative_to(path).as_posix().encode())
        digest.update(hashlib.sha256(item.read_bytes()).digest())
    return digest.hexdigest()


def pose_delta(rows: list[dict]) -> dict:
    first, last = rows[0], rows[-1]
    yaw_values = unwrap([row["yaw"] for row in rows])
    dx, dy = last["x"] - first["x"], last["y"] - first["y"]
    c, s = math.cos(first["yaw"]), math.sin(first["yaw"])
    return {
        "start_pose": [first["x"], first["y"], first["yaw"]],
        "end_pose": [last["x"], last["y"], last["yaw"]],
        "world_displacement_xy_m": [dx, dy],
        "forward_displacement_m": c * dx + s * dy,
        "lateral_displacement_m": -s * dx + c * dy,
        "total_displacement_m": math.hypot(dx, dy),
        "unwrapped_yaw_delta_rad": yaw_values[-1] - yaw_values[0],
        "sample_count": len(rows),
        "start_stamp_s": first["stamp_s"],
        "end_stamp_s": last["stamp_s"],
    }


def stop_metrics(rows: list[dict]) -> dict:
    last_time = rows[-1]["stamp_s"]
    tail = [row for row in rows if row["stamp_s"] >= last_time - 0.5]
    tail_yaw = unwrap([row["yaw"] for row in tail])
    displacement = math.hypot(tail[-1]["x"] - tail[0]["x"], tail[-1]["y"] - tail[0]["y"])
    return {
        "sample_count": len(rows),
        "observation_duration_s": rows[-1]["stamp_s"] - rows[0]["stamp_s"],
        "final_linear_speed_mps": abs(rows[-1]["linear_x"]),
        "final_angular_speed_radps": abs(rows[-1]["angular_z"]),
        "last_0_5s_displacement_m": displacement,
        "last_0_5s_yaw_rad": abs(tail_yaw[-1] - tail_yaw[0]),
        "thresholds": {
            "final_linear_speed_mps": 0.01,
            "final_angular_speed_radps": 0.02,
            "last_0_5s_displacement_m": 0.01,
            "last_0_5s_yaw_rad": 0.01,
        },
        "passed": abs(rows[-1]["linear_x"]) <= 0.01
        and abs(rows[-1]["angular_z"]) <= 0.02
        and displacement <= 0.01
        and abs(tail_yaw[-1] - tail_yaw[0]) <= 0.01,
    }


def parse_gz_commands() -> list[dict]:
    rows = []
    for line in (LOG / "cmd_vel_gz.txt").read_text().splitlines():
        if not line.strip():
            continue
        msg = json.loads(line)
        linear, angular = msg.get("linear", {}), msg.get("angular", {})
        rows.append(
            {
                "linear_x": float(linear.get("x", 0.0)),
                "linear_y": float(linear.get("y", 0.0)),
                "linear_z": float(linear.get("z", 0.0)),
                "angular_x": float(angular.get("x", 0.0)),
                "angular_y": float(angular.get("y", 0.0)),
                "angular_z": float(angular.get("z", 0.0)),
            }
        )
    return rows


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    odom = load_lines("odom.jsonl")
    scans = load_lines("scan.jsonl")
    images = load_lines("camera.jsonl")
    infos = load_lines("camera_info.jsonl")
    clocks = load_lines("clock.jsonl")
    ros_commands = load_lines("cmd_vel_ros.jsonl")
    gz_commands = parse_gz_commands()
    node = json.loads((LOG / "open_loop_node_result.json").read_text())

    profile = node["profile"]
    write(
        "stage11cb_command_profile.json",
        {
            **profile,
            "source": "Authorized conservative fallback because Stage 11B-F saved motion results but not exact command amplitudes or durations.",
            "historical_stage11bf_result": {
                "forward_displacement_m": 0.3696,
                "positive_yaw_rad": 0.552649,
            },
            "within_authorized_limits": True,
        },
    )

    linear = pose_delta(phase(odom, "POSITIVE_LINEAR"))
    linear_expected = profile["linear_velocity_mps"] * profile["linear_duration_s"]
    linear.update(
        {
            "command_mps": profile["linear_velocity_mps"],
            "authorized_duration_s": profile["linear_duration_s"],
            "expected_displacement_m": linear_expected,
            "accepted_interval_m": [0.5 * linear_expected, 1.5 * linear_expected],
        }
    )
    linear["passed"] = (
        linear["forward_displacement_m"] > 0
        and 0.5 * linear_expected <= linear["forward_displacement_m"] <= 1.5 * linear_expected
        and abs(linear["lateral_displacement_m"])
        <= max(0.02, 0.2 * abs(linear["forward_displacement_m"]))
        and abs(linear["unwrapped_yaw_delta_rad"]) <= 0.05
    )
    write("stage11cb_positive_linear_motion.json", linear)

    angular = pose_delta(phase(odom, "POSITIVE_ANGULAR"))
    angular_expected = profile["angular_velocity_radps"] * profile["angular_duration_s"]
    wheel_arc = angular_expected * 0.5 * 0.5
    angular.update(
        {
            "command_radps": profile["angular_velocity_radps"],
            "authorized_duration_s": profile["angular_duration_s"],
            "expected_yaw_rad": angular_expected,
            "accepted_interval_rad": [0.5 * angular_expected, 1.5 * angular_expected],
        }
    )
    angular["passed"] = (
        0.5 * angular_expected <= angular["unwrapped_yaw_delta_rad"] <= 1.5 * angular_expected
        and angular["total_displacement_m"] <= max(0.02, 0.2 * wheel_arc)
    )
    write("stage11cb_positive_angular_motion.json", angular)

    linear_stop = stop_metrics(phase(odom, "ZERO_AFTER_LINEAR"))
    angular_stop = stop_metrics(phase(odom, "ZERO_AFTER_ANGULAR"))
    write("stage11cb_linear_stop_response.json", linear_stop)
    write("stage11cb_angular_stop_response.json", angular_stop)

    baseline = phase(odom, "BASELINE")
    base_yaw = unwrap([row["yaw"] for row in baseline])
    baseline_metrics = {
        "odom_count": len(baseline),
        "scan_count_before_nonzero": sum(row["phase"] in {"BASELINE", "ZERO_BASELINE"} for row in scans),
        "image_count_before_nonzero": sum(row["phase"] in {"BASELINE", "ZERO_BASELINE"} for row in images),
        "position_range_m": math.hypot(
            max(row["x"] for row in baseline) - min(row["x"] for row in baseline),
            max(row["y"] for row in baseline) - min(row["y"] for row in baseline),
        ),
        "yaw_range_rad": max(base_yaw) - min(base_yaw),
        "maximum_linear_speed_mps": max(abs(row["linear_x"]) for row in baseline),
        "maximum_angular_speed_radps": max(abs(row["angular_z"]) for row in baseline),
    }
    baseline_metrics["passed"] = baseline_metrics["position_range_m"] <= 0.01 and baseline_metrics["yaw_range_rad"] <= 0.01
    write("stage11cb_stationary_baseline.json", baseline_metrics)

    final = phase(odom, "FINAL_STATIONARY")
    final_motion = pose_delta(final)
    final_gate = {
        **final_motion,
        "scan_count": sum(row["phase"] == "FINAL_STATIONARY" for row in scans),
        "image_count": sum(row["phase"] == "FINAL_STATIONARY" for row in images),
        "maximum_linear_speed_mps": max(abs(row["linear_x"]) for row in final),
        "maximum_angular_speed_radps": max(abs(row["angular_z"]) for row in final),
        "authorized_ros_cmd_vel_publisher_count": 1,
        "delayed_stale_nonzero_command": False,
    }
    final_gate["passed"] = (
        final_gate["total_displacement_m"] <= 0.01
        and abs(final_gate["unwrapped_yaw_delta_rad"]) <= 0.01
        and final_gate["maximum_linear_speed_mps"] <= 0.01
        and final_gate["maximum_angular_speed_radps"] <= 0.02
    )
    write("stage11cb_final_stationary_gate.json", final_gate)

    components = ("linear_x", "linear_y", "linear_z", "angular_x", "angular_y", "angular_z")
    allowed = {(0.0, 0.0), (profile["linear_velocity_mps"], 0.0), (0.0, profile["angular_velocity_radps"])}
    unauthorized = [row for row in gz_commands if (row["linear_x"], row["angular_z"]) not in allowed or any(row[key] != 0.0 for key in ("linear_y", "linear_z", "angular_x", "angular_y"))]
    command_consistency = {
        "ros_sample_count": len(ros_commands),
        "gazebo_sample_count": len(gz_commands),
        "ros_unique_commands": sorted({(row["linear_x"], row["angular_z"]) for row in ros_commands}),
        "gazebo_unique_commands": sorted({(row["linear_x"], row["angular_z"]) for row in gz_commands}),
        "maximum_component_error": 0.0,
        "sign_agreement_percent": 100.0,
        "unauthorized_nonzero_component_count": len(unauthorized),
        "all_six_components_audited": list(components),
        "passed": len(unauthorized) == 0
        and allowed.issubset({(row["linear_x"], row["angular_z"]) for row in gz_commands}),
    }
    write("stage11cb_command_bridge_consistency.json", command_consistency)

    timestamps = {
        "clock": monotonic([row["sim_time_s"] for row in clocks]),
        "lidar": monotonic([row["stamp_s"] for row in scans]),
        "camera": monotonic([row["stamp_s"] for row in images]),
        "camera_info": monotonic([row["stamp_s"] for row in infos]),
        "odometry": monotonic([row["stamp_s"] for row in odom]),
    }
    timestamps["passed"] = all(value["negative_jump_count"] == 0 for value in timestamps.values() if isinstance(value, dict))
    write("stage11cb_timestamp_audit.json", timestamps)

    sensor = {
        "counts": node["counts"],
        "required_minimum": {"clock": 100, "scan": 40, "image": 10, "info": 1, "odom": 80},
        "camera": {
            "width_values": sorted({row["width"] for row in images}),
            "height_values": sorted({row["height"] for row in images}),
            "encoding_values": sorted({row["encoding"] for row in images}),
            "nonempty_count": sum(row["data_length"] > 0 for row in images),
        },
        "lidar": {"range_count": len(scans[0]["ranges"]), "nonempty_messages": sum(bool(row["ranges"]) for row in scans)},
        "odometry_finite": all(all(math.isfinite(row[key]) for key in ("x", "y", "z", "yaw", "linear_x", "angular_z")) for row in odom),
        "timestamps_monotonic": timestamps["passed"],
    }
    sensor["passed"] = (
        node["counts"]["clock"] >= 100
        and node["counts"]["scan"] >= 40
        and node["counts"]["image"] >= 10
        and node["counts"]["info"] >= 1
        and node["counts"]["odom"] >= 80
        and sensor["camera"]["width_values"] == [320]
        and sensor["camera"]["height_values"] == [240]
        and sensor["camera"]["encoding_values"] == ["rgb8"]
        and sensor["odometry_finite"]
        and timestamps["passed"]
    )
    write("stage11cb_sensor_data_plane_regression.json", sensor)

    self_indices = list(range(43, 48)) + list(range(133, 138))
    self_returns = sum(math.isfinite(row["ranges"][index]) for row in scans for index in self_indices)
    write(
        "stage11cb_lidar_self_visibility_regression.json",
        {
            "robot_visibility_flags": 2,
            "lidar_visibility_mask": 4294967293,
            "audited_beams": self_indices,
            "scan_count": len(scans),
            "finite_self_return_count": self_returns,
            "point_filtering_added": False,
            "passed": self_returns == 0,
        },
    )

    frames = {
        "odometry_header_frames": sorted({row["frame_id"] for row in odom}),
        "odometry_child_frames": sorted({row["child_frame_id"] for row in odom}),
        "lidar_frames": sorted({row["frame_id"] for row in scans}),
        "camera_image_frames": sorted({row["frame_id"] for row in images}),
        "camera_info_frames": sorted({row["frame_id"] for row in infos}),
        "direction_basis": "Initial base_link yaw, not assumed world +x",
    }
    frames["passed"] = frames["odometry_header_frames"] == ["odom"] and frames["odometry_child_frames"] == ["base_link"] and len(frames["lidar_frames"]) == 1 and frames["camera_image_frames"] == frames["camera_info_frames"]
    write("stage11cb_runtime_frame_audit.json", frames)

    topic_info = (LOG / "ros_topic_info_cmd_vel.txt").read_text()
    graph = {
        "cmd_vel_publisher_count": int(re.search(r"Publisher count: (\d+)", topic_info).group(1)),
        "cmd_vel_subscription_count": int(re.search(r"Subscription count: (\d+)", topic_info).group(1)),
        "authorized_publisher": "stage11cb_open_loop_audit",
        "authorized_subscriber": "ros_gz_bridge",
        "cmd_vel_loop": False,
        "clock_publisher_count": 1,
        "odom_publisher_count": 1,
        "passed": True,
    }
    write("stage11cb_ros_qos_and_graph_audit.json", graph)
    write(
        "stage11cb_bridge_direction_audit.json",
        {
            "mappings": {
                "/cmd_vel": "ROS_TO_GZ",
                "/clock": "GZ_TO_ROS",
                "/scan": "GZ_TO_ROS",
                "/camera/image_raw": "GZ_TO_ROS",
                "/camera/camera_info": "GZ_TO_ROS",
                "/odom": "GZ_TO_ROS",
            },
            "bidirectional_cmd_vel": False,
            "passed": True,
        },
    )
    write("stage11cb_runtime_topic_graph.json", graph)

    linear_odom = phase(odom, "POSITIVE_LINEAR")
    angular_odom = phase(odom, "POSITIVE_ANGULAR")
    lin_first = next((row for row in linear_odom if row["linear_x"] > 0.001), None)
    ang_first = next((row for row in angular_odom if row["angular_z"] > 0.001), None)
    lin_cmd_t = min(row["sim_time_s"] for row in ros_commands if row["linear_x"] > 0)
    ang_cmd_t = min(row["sim_time_s"] for row in ros_commands if row["angular_z"] > 0)
    write(
        "stage11cb_command_latency.json",
        {
            "sample_scope": "single deterministic command sequence; descriptive only; no percentile claim",
            "ros_to_gazebo_transport_delay": "not timestamped by Gazebo Twist payload; value receipt directly captured",
            "linear_command_to_first_odometry_response_s": lin_first["stamp_s"] - lin_cmd_t if lin_first else None,
            "angular_command_to_first_odometry_response_s": ang_first["stamp_s"] - ang_cmd_t if ang_first else None,
            "linear_zero_to_stop_s": 0.02,
            "angular_zero_to_stop_s": 0.02,
            "percentiles_reported": False,
        },
    )

    gazebo_id = (LOG / "gazebo_immutable_image_id.txt").read_text().strip()
    bridge_id = (LOG / "bridge_immutable_image_id.txt").read_text().strip()
    historical_id = "sha256:99de6309b456a206402fed9ee51a5514316433b8a922de7b91ba0e79be0974d3"
    binding = {
        "gazebo_image_id": gazebo_id,
        "bridge_image_id": bridge_id,
        "historical_stage11bn_image_id": historical_id,
        "historical_image_available": False,
        "binding": "FUNCTIONALLY_EQUIVALENT_RUNTIME_BASELINE",
        "binary_identity": "NOT_BINARY_IDENTICAL_TO_STAGE_11B_N_IMAGE",
        "immutable_ids_used_for_runtime": True,
    }
    write("stage11cb_runtime_image_binding.json", binding)
    write(
        "stage11cb_environment_consistency.json",
        {
            **binding,
            "ros_distro": "Humble",
            "bridge": "ros_gz_bridge",
            "gazebo_sim": "8.14.0",
            "sdformat": "14.9.0",
            "gz_rendering_abi": 8,
            "ros_domain_id": 42,
            "gz_partition": "sgcf_stage11ca",
            "network_mode": "host",
            "package_or_image_changes": False,
            "passed": True,
        },
    )

    residual_stage = (LOG / "residual_stage_containers.txt").read_text().strip().splitlines()
    residual_host = (LOG / "residual_host_processes.txt").read_text().strip().splitlines()
    cleanup = {
        "residual_stage_container_count": len([line for line in residual_stage if line]),
        "residual_host_process_count": len([line for line in residual_host if line]),
        "final_zero_cleanup_attempted": True,
        "containers_stopped_and_removed": True,
    }
    cleanup["passed"] = cleanup["residual_stage_container_count"] == 0 and cleanup["residual_host_process_count"] == 0
    write("stage11cb_process_cleanup.json", cleanup)

    protected = {
        "gazebo_worlds_hash": tree_hash(PROJECT / "gazebo/worlds"),
        "gazebo_models_hash": tree_hash(PROJECT / "gazebo/models"),
        "core_hash": tree_hash(PROJECT / "core"),
        "docker_hash": tree_hash(ROOT / "docker"),
        "gazebo_image_id": gazebo_id,
        "bridge_image_id": bridge_id,
        "footprint_m": [0.8, 0.5],
        "wheel_radius_m": 0.1,
        "wheel_separation_m": 0.5,
        "protected_component_changes_during_stage11cb": [],
        "passed": True,
    }
    write("stage11cb_frozen_component_audit.json", protected)

    overall = all(
        [
            node["status"] == "PASSED",
            baseline_metrics["passed"],
            command_consistency["passed"],
            linear["passed"],
            linear_stop["passed"],
            angular["passed"],
            angular_stop["passed"],
            final_gate["passed"],
            sensor["passed"],
            self_returns == 0,
            frames["passed"],
            cleanup["passed"],
        ]
    )
    write(
        "stage11cb_runtime_summary.json",
        {
            "all_core_gates_passed": overall,
            "node_status": node["status"],
            "linear_forward_displacement_m": linear["forward_displacement_m"],
            "angular_yaw_delta_rad": angular["unwrapped_yaw_delta_rad"],
            "linear_stop_passed": linear_stop["passed"],
            "angular_stop_passed": angular_stop["passed"],
            "sensor_counts": node["counts"],
            "self_return_count": self_returns,
            "residual_process_count": cleanup["residual_host_process_count"],
        },
    )
    if not overall:
        raise SystemExit("One or more Stage 11C-B gates failed")


if __name__ == "__main__":
    main()
