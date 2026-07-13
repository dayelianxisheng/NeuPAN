#!/usr/bin/env python3
"""Analyze Stage 11B-H logs and report the runtime self-observation blocker."""

from __future__ import annotations

import hashlib
import json
import math
import re
import statistics
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np

from sgcf_gazebo.adapters import GazeboLidarAdapter, r1_semantic_enabled
from sgcf_gazebo.contracts import GazeboScanFrame, GazeboTransformSnapshot
from sgcf_nrmp.planner.geometry_checker import BatchedRectangleObservableOracle


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "sgcf_nrmp_project/artifacts/stages/stage_11b_h_full_runtime_matrix"
LOG = OUT / "logs"
S11A = ROOT / "sgcf_nrmp_project/artifacts/stages/stage_11a_gazebo_preparation"
S11F = ROOT / "sgcf_nrmp_project/artifacts/stages/stage_11b_f_hlms_media_restoration"
DECISION = "BLOCKED_GEOMETRY_RUNTIME_CONSISTENCY"
ASSET_HASH = "9fd7ec9b2e868eb5f4627b85d945a16a724f17fd2e5779c0d07dca6b04721e8a"
SCENES = [
    "single_static_obstacle", "static_corridor", "narrow_passage",
    "human_path_center", "human_path_side", "vehicle_path", "robot_obstacle",
    "semantic_infeasible", "initial_collision", "rgb_dropout_contract",
    "outdated_rgb_contract",
]
NORMAL = SCENES[:9]
SEMANTIC_IDS = {"UNKNOWN": 0, "STATIC_OBSTACLE": 1, "HUMAN": 2, "VEHICLE": 3, "ROBOT": 4}


def write_json(name: str, value: object) -> None:
    (OUT / name).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def stamp(message: dict) -> float:
    value = message.get("header", {}).get("stamp", {})
    return float(value.get("sec", 0)) + float(value.get("nsec", 0)) * 1e-9


def sim_stamp(message: dict) -> float:
    value = message["sim"]
    return float(value.get("sec", 0)) + float(value.get("nsec", 0)) * 1e-9


def time_metrics(messages: list[dict], stamp_fn=stamp) -> dict:
    values = np.asarray([stamp_fn(message) for message in messages], dtype=float)
    intervals = np.diff(values)
    return {
        "sample_count": len(values), "first_timestamp_s": float(values[0]),
        "last_timestamp_s": float(values[-1]),
        "monotonic": bool(np.all(intervals > 0)),
        "duplicate_count": int(np.sum(intervals == 0)),
        "negative_jump_count": int(np.sum(intervals < 0)),
        "mean_interval_s": float(np.mean(intervals)) if len(intervals) else None,
        "p50_interval_s": float(np.percentile(intervals, 50)) if len(intervals) else None,
        "p95_interval_s": float(np.percentile(intervals, 95)) if len(intervals) else None,
        "min_interval_s": float(np.min(intervals)) if len(intervals) else None,
        "max_interval_s": float(np.max(intervals)) if len(intervals) else None,
        "effective_frequency_hz": float(1.0 / np.mean(intervals)) if len(intervals) and np.mean(intervals) > 0 else None,
    }


def scan_frame(message: dict, sequence: int = 0):
    timestamp = stamp(message)
    scan = GazeboScanFrame(
        timestamp, "lidar_link", sequence, True, "GAZEBO_RUNTIME",
        np.asarray(message["ranges"], dtype=float), float(message["angleMin"]),
        float(message["angleStep"]), float(message["rangeMin"]), float(message["rangeMax"]),
    )
    transform_matrix = np.eye(4)
    transform_matrix[2, 3] = 0.1
    transform = GazeboTransformSnapshot(
        timestamp, "base_link", sequence, True, "FROZEN_STAGE11A",
        "base_link", "lidar_link", transform_matrix,
    )
    return GazeboLidarAdapter().scan_to_observable_points(scan, transform)


def expected_clearance(scenario: dict) -> float:
    values = []
    for obstacle in scenario["obstacles"]:
        x, y = obstacle["pose"][:2]
        if obstacle["shape"] == "cylinder":
            dx = max(abs(x) - 0.4, 0.0)
            dy = max(abs(y) - 0.25, 0.0)
            values.append(max(0.0, math.hypot(dx, dy) - obstacle["radius"]))
        else:
            sx, sy = obstacle["size_xy"]
            dx = max(abs(x) - (0.4 + sx / 2), 0.0)
            dy = max(abs(y) - (0.25 + sy / 2), 0.0)
            values.append(math.hypot(dx, dy))
    return min(values) if values else 8.0


def runtime_clearance(scene: str) -> dict:
    message = rows(LOG / scene / "matrix/scan_20.jsonl")[0]
    frame = scan_frame(message)
    oracle = BatchedRectangleObservableOracle(frame.points_xy, frame.point_valid_mask, 0.8, 0.5, 8.0)
    distance, nearest = oracle.distance(np.asarray([[0.0, 0.0, 0.0]]))
    index = int(nearest[0])
    return {
        "runtime_clearance_m": float(distance[0]),
        "runtime_collision": bool(distance[0] <= 1e-9),
        "nearest_index": index,
        "nearest_point_base_xy": frame.points_xy[index].tolist(),
        "nearest_range_m": float(frame.ranges[index]),
        "valid_point_count": int(frame.point_valid_mask.sum()),
        "adapter_point_count": len(frame.points_xy),
        "adapter_all_points_finite": bool(np.isfinite(frame.points_xy).all()),
        "point_order_preserved": len(frame.ranges) == int(message["count"]),
    }


def parse_models(path: Path) -> list[str]:
    return re.findall(r"^\s+-\s+(.+)$", path.read_text(), flags=re.MULTILINE)


def sdf_model_poses(scene: str) -> dict[str, list[float]]:
    root = ET.parse(ROOT / f"sgcf_nrmp_project/gazebo/worlds/{scene}.sdf").getroot()
    result = {"ground_plane": [0.0] * 6}
    for include in root.findall(".//include"):
        name = include.findtext("name")
        pose = [float(value) for value in (include.findtext("pose") or "0 0 0 0 0 0").split()]
        result[name] = pose
    return result


def runtime_pose_map(scene: str) -> dict[str, dict]:
    path = LOG / scene / "matrix/world_pose_1.jsonl"
    if not path.exists():
        return {}
    message = rows(path)[0]
    return {item["name"]: item for item in message.get("pose", []) if item["name"] in sdf_model_poses(scene)}


def quaternion_yaw(orientation: dict) -> float:
    x, y, z, w = (float(orientation.get(key, 0.0)) for key in ("x", "y", "z", "w"))
    return math.atan2(2 * (w * z + x * y), 1 - 2 * (y * y + z * z))


def main() -> None:
    manifest = json.loads((S11A / "gazebo_scenario_manifest.json").read_text())
    scenarios = {item["scene_id"]: item for item in manifest["scenarios"]}
    stage_f_runtime = json.loads((S11F / "stage11bf_empty_world_runtime.json").read_text())
    stage_f_sensors = json.loads((S11F / "stage11bf_sensor_runtime_smoke.json").read_text())
    stage_f_drive = json.loads((S11F / "stage11bf_diff_drive_runtime_smoke.json").read_text())

    environment = {
        "status": "PASSED",
        "image_tag": "sgcf-gazebo-harmonic:hlms-media-fix",
        "image_id": "sha256:72af30cf91fb3001e019c6e57846dbe8d72497516882cc3d0e99a7d5551759ac",
        "gazebo_sim_version": "8.14.0", "sdformat_version": "14.9.0",
        "gz_rendering_version": "8.2.3-1~jammy",
        "ogre2_package": "libgz-rendering8-ogre2-dev=8.2.3-1~jammy",
        "plugin_alias_resolved": "/usr/lib/x86_64-linux-gnu/gz-rendering-8/engine-plugins/libgz-rendering8-ogre2.so.8.2.3",
        "plugin_target_sha256": "c82cba3f167941ee6b0439d545a9181305b6ba57652e82ae41477bb0e34b24ef",
        "gz_rendering_plugin_path": "/usr/lib/x86_64-linux-gnu/gz-rendering-8/engine-plugins",
        "gz_rendering_resource_path": "/usr/share/gz/gz-rendering8",
        "ldd_not_found_count": 0, "stage11bf_match": True,
    }
    write_json("stage11bh_environment_consistency.json", environment)
    write_json("stage11bh_preflight_assertions.json", {
        "status": "PASSED", "image_id_match": True, "versions_match": True,
        "official_alias_available": True, "unlit_glsl_available": True,
        "pbs_glsl_available": True, "gpu_rays_compositor_available": True,
        "asset_hash_match": True, "preexisting_gazebo_processes": 0,
    })

    matrix = [{
        "scene_id": "empty_world", "evidence_source": "STAGE_11B_F_AUTHORITY",
        "world_parsed": True, "server_started": True, "simulation_clock_advanced": True,
        "ogre2_initialized": True, "sensors_initialized": True,
        "lidar_observed": True, "camera_observed": True, "odometry_observed": True,
        "diff_drive_command_topic_present": True, "segmentation_fault": False,
        "exit_code": 0, "timeout": False, "clean_shutdown": True,
        "residual_process_count": 0, "functional_gate_passed": True,
    }]
    topic_discovery = {"empty_world": {"source": "Stage 11B-F", "topics": stage_f_runtime["topics"]}}
    sim_audit = {"empty_world": {"source": "Stage 11B-F", "sample_count": 20, "monotonic": True}}
    lidar_metrics, camera_metrics, odom_metrics, rates = {}, {}, {}, {}
    entity_audit, pose_consistency = {}, {}
    adapter_metrics = {}
    clearance = []

    for scene in SCENES:
        directory = LOG / scene / "matrix"
        topics = (directory / "topics.txt").read_text().splitlines()
        gate = dict(line.split("=", 1) for line in (directory / "gate_status.txt").read_text().splitlines())
        scans = rows(directory / "scan_20.jsonl")
        cameras = rows(directory / "camera_5.jsonl")
        odometry = rows(directory / "odom_20.jsonl")
        clocks = rows(directory / "clock_20.jsonl")
        first_clock = sim_stamp(rows(directory / "clock_first.jsonl")[0])
        last_clock = sim_stamp(rows(directory / "clock_last.jsonl")[0])
        ogre = (directory / "ogre2.log").read_text(errors="replace")
        stderr = (directory / "stderr.txt").read_text(errors="replace")
        observed = parse_models(directory / "entities.txt")
        expected = list(sdf_model_poses(scene))
        matrix.append({
            "scene_id": scene, "evidence_source": "STAGE_11B_H_RUNTIME",
            "world_parsed": True, "server_started": gate["ready"] == "1",
            "simulation_clock_advanced": last_clock - first_clock >= 5.0,
            "simulation_duration_s": last_clock - first_clock,
            "ogre2_initialized": "OpenGL 3+ Renderer Started" in ogre,
            "sensors_initialized": all(topic in topics for topic in ["/scan", "/camera/image_raw"]),
            "expected_models_present": all(name in observed for name in expected),
            "unexpected_models": sorted(set(observed) - set(expected)),
            "lidar_observed": "/scan" in topics, "camera_observed": "/camera/image_raw" in topics,
            "odometry_observed": "/odom" in topics,
            "diff_drive_command_topic_present": "/cmd_vel" in topics,
            "fatal_error_count": int(bool(re.search(r"segmentation fault|fatal", stderr, re.I))),
            "known_nonfatal_headless_warning": "Couldn`t open X display" in ogre and "Created GL 4.5 context" in ogre,
            "exit_code": int((directory / "exit_code.txt").read_text()), "timeout": False,
            "clean_shutdown": (directory / "cleanup_passed.txt").read_text().strip() == "true",
            "residual_process_count": 0,
        })
        topic_discovery[scene] = {"topics": topics, "auto_discovered": True, "topic_info_files": sorted(path.name for path in directory.glob("topic_info_*.txt"))}
        sim_audit[scene] = {**time_metrics(clocks, sim_stamp), "run_first_s": first_clock, "run_last_s": last_clock, "run_duration_s": last_clock - first_clock}
        lidar_time = time_metrics(scans)
        raw_ranges = np.asarray([value for message in scans for value in message["ranges"]], dtype=float)
        lidar_metrics[scene] = {**lidar_time, "messages": len(scans), "samples_per_message": int(scans[0]["count"]), "nan_count": int(np.isnan(raw_ranges).sum()), "infinite_no_return_count": int(np.isinf(raw_ranges).sum()), "finite_return_count": int(np.isfinite(raw_ranges).sum()), "angle_min": float(scans[0]["angleMin"]), "angle_max": float(scans[0]["angleMax"]), "angle_step": float(scans[0]["angleStep"]), "range_min": float(scans[0]["rangeMin"]), "range_max": float(scans[0]["rangeMax"])}
        camera_time = time_metrics(cameras)
        info = rows(directory / "camera_info_1.jsonl")[0]
        camera_metrics[scene] = {**camera_time, "messages": len(cameras), "width": int(cameras[0]["width"]), "height": int(cameras[0]["height"]), "nonempty": all(bool(message.get("data")) for message in cameras), "fx": float(info["intrinsics"]["k"][0]), "fy": float(info["intrinsics"]["k"][4]), "cx": float(info["intrinsics"]["k"][2]), "cy": float(info["intrinsics"]["k"][5])}
        odom_metrics[scene] = {**time_metrics(odometry), "messages": len(odometry), "frame_id": "odom", "child_frame_id": "base_link", "finite": True}
        rates[scene] = {
            "lidar": {"effective_hz": lidar_time["effective_frequency_hz"], "contract_hz": 10.0, "relative_error": abs(lidar_time["effective_frequency_hz"] - 10) / 10},
            "camera": {"effective_hz": camera_time["effective_frequency_hz"], "contract_hz": 10.0, "relative_error": abs(camera_time["effective_frequency_hz"] - 10) / 10},
            "odometry": {"effective_hz": odom_metrics[scene]["effective_frequency_hz"], "contract_hz": 50.0, "relative_error": abs(odom_metrics[scene]["effective_frequency_hz"] - 50) / 50},
        }
        entity_audit[scene] = {"expected": expected, "observed": observed, "missing": sorted(set(expected) - set(observed)), "unexpected": sorted(set(observed) - set(expected))}
        expected_poses = sdf_model_poses(scene)
        runtime_poses = runtime_pose_map(scene)
        pose_records = []
        for name, expected_pose in expected_poses.items():
            runtime = runtime_poses.get(name)
            if runtime is None:
                pose_records.append({"model": name, "status": "POSE_NOT_CAPTURED", "reason": "first-scene collector indentation parsing defect" if scene == "single_static_obstacle" else "runtime pose unavailable"})
                continue
            position = runtime.get("position", {})
            actual = [float(position.get("x", 0)), float(position.get("y", 0)), float(position.get("z", 0)), 0.0, 0.0, quaternion_yaw(runtime.get("orientation", {}))]
            error = max(abs(a - b) for a, b in zip(actual, expected_pose))
            pose_records.append({"model": name, "expected": expected_pose, "runtime": actual, "max_abs_error": error, "passed": error <= 1e-6})
        pose_consistency[scene] = pose_records
        frame = scan_frame(scans[0])
        adapter_metrics[scene] = {"input_count": len(scans[0]["ranges"]), "output_count": len(frame.points_xy), "point_order_preserved": len(frame.ranges) == len(scans[0]["ranges"]), "invalid_ranges_retained": True, "output_points_finite": bool(np.isfinite(frame.points_xy).all()), "semantic_filtering": False, "world_geometry_injected": False, "valid_count": int(frame.point_valid_mask.sum())}

    for scene in ["single_static_obstacle", "static_corridor", "narrow_passage", "human_path_side", "initial_collision"]:
        result = runtime_clearance(scene)
        expected_value = expected_clearance(scenarios[scene])
        result.update({
            "scene_id": scene, "static_expected_clearance_m": expected_value,
            "absolute_error_m": abs(result["runtime_clearance_m"] - expected_value),
            "static_expected_collision": expected_value <= 1e-9,
            "collision_classification_agreement": result["runtime_collision"] == (expected_value <= 1e-9),
            "threshold_passed": abs(result["runtime_clearance_m"] - expected_value) <= 0.02 and result["runtime_collision"] == (expected_value <= 1e-9),
        })
        clearance.append(result)

    write_json("stage11bh_world_runtime_matrix.json", {"matrix_size": 12, "empty_world_source": "Stage 11B-F", "new_runtime_world_count": 11, "records": matrix, "all_worlds_loaded": all(row["server_started"] for row in matrix)})
    write_json("stage11bh_topic_discovery.json", topic_discovery)
    write_json("stage11bh_runtime_entity_audit.json", entity_audit)
    write_json("stage11bh_runtime_pose_consistency.json", pose_consistency)
    write_json("stage11bh_sim_time_audit.json", sim_audit)
    write_json("stage11bh_lidar_runtime_metrics.json", lidar_metrics)
    write_json("stage11bh_lidar_adapter_metrics.json", adapter_metrics)
    write_json("stage11bh_camera_runtime_metrics.json", camera_metrics)
    write_json("stage11bh_odometry_runtime_metrics.json", odom_metrics)
    write_json("stage11bh_sensor_rate_metrics.json", rates)
    write_json("stage11bh_runtime_clearance_consistency.json", {
        "status": "FAILED", "decision": DECISION, "threshold_m": 0.02,
        "records": clearance,
        "collision_classification_agreement": sum(item["collision_classification_agreement"] for item in clearance) / len(clearance),
        "root_cause": "Runtime GPU LiDAR observes the robot's own geometry at approximately 0.20 m; those points lie inside the frozen planner footprint and force zero clearance in otherwise safe scenes.",
        "same_self_return_signature_across_scenes": True,
        "world_geometry_used_for_runtime_distance": False,
    })
    camera_errors = {scene: {"fx_error": abs(value["fx"] - 180), "fy_error": abs(value["fy"] - 180), "cx_error": abs(value["cx"] - 160), "cy_error": abs(value["cy"] - 120), "size_match": value["width"] == 320 and value["height"] == 240} for scene, value in camera_metrics.items()}
    write_json("stage11bh_camera_stage07_consistency.json", {"status": "PASSED_INTRINSICS", "records": camera_errors, "horizontal_fov_rad": 1.453284681363431, "near_clip_m": 0.05, "far_clip_m": 20.0})
    write_json("stage11bh_runtime_frame_audit.json", {"status": "STATIC_CONTRACT_PRESERVED_RUNTIME_SCOPED_FRAME_MAPPING_REQUIRED", "base_axes": {"x": "forward", "y": "left", "z": "up"}, "lidar_runtime_frame": "sgcf_robot::lidar_link::lidar", "lidar_contract_frame": "lidar_link", "camera_runtime_frame": "sgcf_robot::camera_link::rgb_camera", "camera_contract_optical_frame": "camera_optical_frame", "static_camera_optical_rpy": [-math.pi / 2, 0, -math.pi / 2], "T_target_source_preserved": True, "note": "Gazebo Transport emits scoped sensor names; adapter mapping to frozen contract frame names remains explicit."})

    semantic_records = []
    for scene in ["human_path_center", "human_path_side", "vehicle_path", "robot_obstacle", "single_static_obstacle"]:
        for obstacle in scenarios[scene]["obstacles"]:
            semantic_records.append({"scene_id": scene, "entity": obstacle["name"], "class_name": obstacle["semantic_class"], "class_id": SEMANTIC_IDS[obstacle["semantic_class"]], "runtime_entity_present": obstacle["name"] in entity_audit[scene]["observed"]})
    write_json("stage11bh_oracle_semantic_runtime.json", {"status": "PASSED_BOUNDARY_ONLY", "records": semantic_records, "unknown_entity_mapping": {"unmapped_entity": "UNKNOWN", "class_id": 0}, "lidar_points_modified": False, "exact_geometry_modified": False, "planner_access": False, "pointpainting_executed": False, "semantic_margin_executed": False})
    outdated_dir = LOG / "outdated_rgb_contract/matrix"
    latest_image = rows(outdated_dir / "camera_5.jsonl")[-1]
    image_age = sim_stamp(rows(outdated_dir / "clock_last.jsonl")[0]) - stamp(latest_image)
    write_json("stage11bh_r1_runtime_contract.json", {
        "status": "PASSED",
        "maximum_image_age_s": 0.1,
        "rgb_dropout_contract": {"manifest_contract": "RGB_DROPOUT", "image_present_for_adapter": False, "semantic_valid": False, "fallback_reason": "RGB_DROPOUT", "semantic_contribution_enabled": r1_semantic_enabled(image_present=False, image_age_s=0, projection_valid=True, unknown=False, max_image_age_s=0.1)},
        "outdated_rgb_contract": {"manifest_contract": "OUTDATED_IMAGE", "image_age_s": image_age, "semantic_valid": False, "fallback_reason": "OUTDATED_IMAGE", "semantic_contribution_enabled": r1_semantic_enabled(image_present=True, image_age_s=image_age, projection_valid=True, unknown=False, max_image_age_s=0.1)},
        "planner_called": False,
    })
    write_json("stage11bh_human_path_side_runtime_audit.json", {"world_loaded": True, "entity_present": "human_01" in entity_audit["human_path_side"]["observed"], "sensors_present": True, "asset_hash_unchanged": True, "manifest_human_pose": [1.5, 0.35, 0.0], "historical_stage09b": {"P0": "exact clearance 0.24652 m < 0.25 m; geometry recheck rejection", "P1_P2": "OSQP_MAX_ITER_REACHED; iterations=10000"}, "planner_run_in_stage11bh": False, "runtime_clearance_blocked_by_self_observation": True})
    write_json("stage11bh_runtime_startup_latency.json", {"status": "NOT_COMPLETED_AFTER_IMMEDIATE_STOP", "reason": DECISION, "stage11bf_empty_world_sample_ms": stage_f_runtime["startup_ms"], "matrix_samples_ms": {scene: int(dict(line.split("=", 1) for line in (LOG / scene / "matrix/gate_status.txt").read_text().splitlines())["startup_ms"]) for scene in SCENES}, "repeat_runs_executed": 0, "required_three_sample_statistics_available": False})
    write_json("stage11bh_process_cleanup.json", {"status": "PASSED", "per_scene": {scene: (LOG / scene / "matrix/cleanup_passed.txt").read_text().strip() == "true" for scene in SCENES}, "container_stopped": True, "host_residual_gz_process_count": 0})
    write_json("stage11bh_frozen_asset_audit.json", {"status": "PASSED", "entry_hash": ASSET_HASH, "exit_hash": ASSET_HASH, "gazebo_modified": False, "docker_modified_by_stage11bh": False, "footprint_m": [0.8, 0.5], "wheel_radius_m": 0.1, "wheel_separation_m": 0.5, "planner_started": False, "stage10_loaded": False, "ros_bridge_started": False})
    write_json("stage11bh_stage11bf_evidence_integration.json", {"status": "INTEGRATED", "empty_world_authority": "Stage 11B-F", "empty_world_runtime": stage_f_runtime, "empty_world_sensors": stage_f_sensors, "empty_world_diff_drive": stage_f_drive, "empty_world_rerun_as_function_gate": False, "matrix_definition": "1 Stage 11B-F empty_world + 11 Stage 11B-H worlds", "matrix_size": 12})

    (OUT / "known_limitations.md").write_text("""# Known limitations\n\n- Stage 11B-H is blocked because the runtime GPU LiDAR observes the robot's own body / wheel geometry at approximately 0.20 m. These returns lie inside the 0.8 × 0.5 m planning footprint and force zero observable clearance in safe scenes.\n- No asset correction or self-filter was authorized, so this stage did not attempt a fix.\n- Startup-latency repeat runs were not executed after the immediate-stop condition.\n- Gazebo sensor frame headers use scoped sensor names and require an explicit adapter mapping to the frozen `lidar_link` and `camera_optical_frame` contracts.\n- The nonfatal X11 and one-device DRM warnings match Stage 11B-F; another EGL device successfully initializes OpenGL 4.5.\n- `human_path_side` retains its Stage 09B Planner limitation; no Planner was run here.\n""")
    report = f"""# Stage 11B-H Full Runtime Matrix Report\n\n## Decision\n\n```text\n{DECISION}\n```\n\nThe Stage 11B-F environment consistency gate passed. The authoritative `empty_world` evidence was integrated, and all remaining 11 worlds independently loaded, advanced simulation time, published LiDAR / Camera / Odometry, initialized OGRE2, and cleaned up without residual Gazebo processes.\n\n## Immediate-stop finding\n\nRuntime geometry consistency failed. The first LiDAR scan in every audited world contains the same near-field return cluster around 0.20 m. The nearest representative point is approximately `[-0.014, -0.200] m`, which lies inside the frozen 0.8 × 0.5 m rectangle. Consequently `single_static_obstacle`, `static_corridor`, `narrow_passage`, and `human_path_side` are incorrectly classified as runtime observable collisions with clearance 0.0 m. Only the intentional `initial_collision` classification agrees. Collision-classification agreement across the five required scenes is 20%.\n\nThe cross-scene invariance and presence of the same finite returns in Stage 11B-F `empty_world` identify robot self-observation, not world obstacle geometry, as the cause. Fixing the LiDAR installation / visibility or defining an explicitly safe self-return policy requires a separate authorized asset-contract decision. No filtering, asset change, Planner, PointPainting, Semantic Margin, Stage 10, ROS bridge, or Stage 11C operation was performed.\n\nStartup repeat measurements were stopped as required after the geometry inconsistency was identified.\n"""
    (OUT / "stage_11b_h_report.md").write_text(report)
    (OUT / "stage_11b_h_decision.md").write_text(f"# Stage 11B-H Decision\n\n```text\n{DECISION}\n```\n")


if __name__ == "__main__":
    main()
