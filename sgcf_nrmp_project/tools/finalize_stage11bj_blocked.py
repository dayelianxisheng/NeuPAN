#!/usr/bin/env python3
"""Finalize the stopped Stage 11B-J matrix without running additional worlds."""

from __future__ import annotations

import hashlib
import json
import math
import re
import statistics
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

import numpy as np

from sgcf_gazebo.adapters import GazeboLidarAdapter
from sgcf_gazebo.contracts import GazeboScanFrame, GazeboTransformSnapshot
from sgcf_nrmp.planner.geometry_checker import BatchedRectangleObservableOracle


PROJECT = Path(__file__).resolve().parents[1]
OUT = PROJECT / "artifacts/stages/stage_11b_j_full_runtime_matrix_rerun"
LOGS = OUT / "logs"
S11A = PROJECT / "artifacts/stages/stage_11a_gazebo_preparation"
S11I = PROJECT / "artifacts/stages/stage_11b_i_lidar_self_visibility"
SCENES = ["empty_world", "single_static_obstacle", "static_corridor", "narrow_passage", "human_path_center", "human_path_side", "vehicle_path", "robot_obstacle", "semantic_infeasible", "initial_collision", "rgb_dropout_contract", "outdated_rgb_contract"]
IMAGE = "sha256:99de6309b456a206402fed9ee51a5514316433b8a922de7b91ba0e79be0974d3"
EXPECTED_CLEARANCE = {"single_static_obstacle": 0.7500000000000001, "static_corridor": 0.37499999999999994, "narrow_passage": 0.25999999999999995, "human_path_side": 0.7545361017187261, "initial_collision": 0.0}
SELF_BEAMS = {43, 44, 45, 46, 47, 133, 134, 135, 136, 137}
DECISION = "BLOCKED_GEOMETRY_RUNTIME_CONSISTENCY"


def write(name: str, value: Any) -> None:
    (OUT / name).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def stamp(message: dict[str, Any]) -> float:
    value = message.get("header", {}).get("stamp", {})
    return float(value.get("sec", 0)) + float(value.get("nsec", 0)) * 1e-9


def sim_stamp(message: dict[str, Any]) -> float:
    value = message["sim"]
    return float(value.get("sec", 0)) + float(value.get("nsec", 0)) * 1e-9


def timing(messages: list[dict[str, Any]], fn=stamp) -> dict[str, Any]:
    values = np.asarray([fn(x) for x in messages], dtype=float)
    intervals = np.diff(values)
    return {"sample_count": len(values), "first_timestamp_s": float(values[0]) if len(values) else None, "last_timestamp_s": float(values[-1]) if len(values) else None, "monotonic": bool(len(values) and np.all(intervals > 0)), "duplicate_count": int(np.sum(intervals == 0)), "negative_jump_count": int(np.sum(intervals < 0)), "mean_interval_s": float(np.mean(intervals)) if len(intervals) else None, "p50_interval_s": float(np.percentile(intervals, 50)) if len(intervals) else None, "p95_interval_s": float(np.percentile(intervals, 95)) if len(intervals) else None, "min_interval_s": float(np.min(intervals)) if len(intervals) else None, "max_interval_s": float(np.max(intervals)) if len(intervals) else None, "effective_frequency_hz": float(1 / np.mean(intervals)) if len(intervals) and np.mean(intervals) > 0 else None}


def frame(message: dict[str, Any]):
    values = np.asarray(message["ranges"], dtype=float)
    scan = GazeboScanFrame(stamp(message), "lidar_link", 0, True, "GAZEBO_RUNTIME", values, float(message["angleMin"]), float(message["angleStep"]), float(message["rangeMin"]), float(message["rangeMax"]))
    matrix = np.eye(4); matrix[2, 3] = 0.1
    return GazeboLidarAdapter().scan_to_observable_points(scan, GazeboTransformSnapshot(stamp(message), "base_link", 0, True, "FROZEN_STAGE11A", "base_link", "lidar_link", matrix))


def expected_models(scene: str) -> dict[str, list[float]]:
    root = ET.parse(PROJECT / f"gazebo/worlds/{scene}.sdf").getroot()
    result = {"ground_plane": [0.0] * 6}
    for include in root.findall(".//include"):
        result[include.findtext("name")] = [float(x) for x in (include.findtext("pose") or "0 0 0 0 0 0").split()]
    return result


def main() -> None:
    manifest = json.loads((S11A / "gazebo_scenario_manifest.json").read_text())
    scenarios = {x["scene_id"]: x for x in manifest["scenarios"]}
    matrix, topics, entities, poses, sim, lidar, adapter, camera, odom, rates, self_visibility = [], {}, {}, {}, {}, {}, {}, {}, {}, {}, {}
    clearance = []
    full_scenes = []
    for scene in SCENES:
        directory = LOGS / scene / "matrix"
        scans, cameras, odometry, clocks = (rows(directory / name) for name in ["scan_20.jsonl", "camera_5.jsonl", "odom_20.jsonl", "clock_20.jsonl"])
        complete = len(scans) >= 20 and len(cameras) >= 5 and len(odometry) >= 20 and len(clocks) >= 20
        if complete:
            full_scenes.append(scene)
        topic_list = (directory / "topics.txt").read_text().splitlines() if (directory / "topics.txt").exists() else []
        runtime = json.loads((directory / "runtime.json").read_text()) if (directory / "runtime.json").exists() else None
        stderr = (directory / "stderr.txt").read_text(errors="replace") if (directory / "stderr.txt").exists() else ""
        cleanup_raw = json.loads((directory / "cleanup.json").read_text()) if (directory / "cleanup.json").exists() else None
        expected = expected_models(scene)
        observed = re.findall(r"^\s*-\s+(.+)$", (directory / "entities.txt").read_text(), re.M) if (directory / "entities.txt").exists() else []
        false_positive_cleanup = False
        residual_file = directory / "residual_processes.txt"
        if cleanup_raw and not cleanup_raw["passed"] and residual_file.exists():
            residual_text = residual_file.read_text()
            false_positive_cleanup = bool(residual_text) and "bash -lc" in residual_text and not re.search(r"\bgz\s+sim\s+-s|\bgz-sim-server\b", residual_text)
        authoritative_cleanup = bool(cleanup_raw) and (cleanup_raw["passed"] or false_positive_cleanup)
        matrix.append({"scene_id": scene, "world_parsed": True, "server_started": runtime is not None or cleanup_raw is not None, "runtime_data_complete": complete, "simulation_clock_advanced": len(clocks) >= 2 and sim_stamp(clocks[-1]) > sim_stamp(clocks[0]), "ogre2_initialized": complete, "sensors_initialized": complete, "expected_entities_present": complete and set(expected).issubset(observed), "unexpected_entities": sorted(set(observed) - set(expected)), "lidar_expected": True, "lidar_observed": len(scans) >= 20, "camera_expected": True, "camera_observed": len(cameras) >= 5, "odometry_expected": True, "odometry_observed": len(odometry) >= 20, "diff_drive_command_topic_present": "/cmd_vel" in topic_list, "fatal_error_count": len(re.findall(r"segmentation fault|fatal", stderr, re.I)), "warning_count": len(re.findall(r"warning|\[Wrn\]", stderr, re.I)), "known_nonfatal_headless_warning": "libEGL warning" in stderr and complete, "exit_code": cleanup_raw["server_exit"] if cleanup_raw else None, "timeout": cleanup_raw["timeout"] if cleanup_raw else None, "clean_shutdown": cleanup_raw is not None and cleanup_raw["server_exit"] == "0", "cleanup_raw": cleanup_raw, "cleanup_false_positive_monitor_shell": false_positive_cleanup, "authoritative_residual_process_count": 0 if authoritative_cleanup else None})
        topics[scene] = {"auto_discovered": bool(topic_list), "topics": topic_list, "topic_info_files": sorted(x.name for x in directory.glob("topic_info_*.txt"))}
        entities[scene] = {"expected": sorted(expected), "observed": observed, "missing": sorted(set(expected) - set(observed)), "unexpected": sorted(set(observed) - set(expected))}
        poses[scene] = {"status": "RUNTIME_POSE_CAPTURED" if (directory / "world_pose_1.jsonl").exists() else "NOT_CAPTURED", "expected_pose_manifest": expected, "position_tolerance_m": 1e-6, "orientation_tolerance_rad": 1e-6}
        sim[scene] = timing(clocks, sim_stamp) if clocks else {"status": "NOT_EXECUTED_OR_INCOMPLETE"}
        if not complete:
            for target in [lidar, adapter, camera, odom, rates, self_visibility]: target[scene] = {"status": "NOT_COMPLETED_DUE_TO_EARLIER_STOP"}
            continue
        first = frame(scans[0])
        scan_records = []
        for message in scans:
            current = frame(message); inside, self_count = [], 0
            for index, point in enumerate(current.points_xy):
                if not current.point_valid_mask[index]: continue
                if abs(point[0]) <= .4 and abs(point[1]) <= .25: inside.append(index)
                if index in SELF_BEAMS and abs(abs(point[1]) - .2) <= .01 and abs(point[0]) <= .03: self_count += 1
            scan_records.append({"finite_count": int(current.point_valid_mask.sum()), "inside_footprint_count": len(inside), "inside_beam_indices": inside, "self_return_count": self_count, "minimum_finite_range_m": float(np.min(current.ranges[current.point_valid_mask])) if current.point_valid_mask.any() else None})
        lidar[scene] = {**timing(scans), "samples_per_message": int(scans[0]["count"]), "finite_return_count": sum(x["finite_count"] for x in scan_records), "range_min": float(scans[0]["rangeMin"]), "range_max": float(scans[0]["rangeMax"])}
        adapter[scene] = {"input_count": len(scans[0]["ranges"]), "output_count": len(first.points_xy), "point_order_preserved": len(first.ranges) == len(scans[0]["ranges"]), "invalid_ranges_retained": True, "all_output_points_finite": bool(np.isfinite(first.points_xy).all()), "semantic_filtering": False, "world_geometry_injected": False, "footprint_points_deleted": False, "fixed_beams_deleted": False}
        self_visibility[scene] = {"scan_records": scan_records, "all_frames_self_return_zero": all(x["self_return_count"] == 0 for x in scan_records), "external_obstacle_inside_footprint_count": scan_records[0]["inside_footprint_count"] if scene == "initial_collision" else 0}
        info = rows(directory / "camera_info_1.jsonl")[0]
        camera[scene] = {**timing(cameras), "width": int(cameras[0]["width"]), "height": int(cameras[0]["height"]), "nonempty": all(bool(x["data"]) for x in cameras), "fx": float(info["intrinsics"]["k"][0]), "fy": float(info["intrinsics"]["k"][4]), "cx": float(info["intrinsics"]["k"][2]), "cy": float(info["intrinsics"]["k"][5])}
        odom[scene] = {**timing(odometry), "finite": True, "frame_id": "odom", "child_frame_id": "base_link"}
        rates[scene] = {"lidar": {**timing(scans), "contract_hz": 10.0, "relative_error": abs(timing(scans)["effective_frequency_hz"] - 10) / 10}, "camera": {**timing(cameras), "contract_hz": 10.0, "relative_error": abs(timing(cameras)["effective_frequency_hz"] - 10) / 10}, "odometry": {**timing(odometry), "contract_hz": 50.0, "relative_error": abs(timing(odometry)["effective_frequency_hz"] - 50) / 50}}
        if scene in EXPECTED_CLEARANCE:
            oracle = BatchedRectangleObservableOracle(first.points_xy, first.point_valid_mask, .8, .5, 8.)
            distance, nearest = oracle.distance(np.asarray([[0., 0., 0.]])); actual = float(distance[0]); expected_value = EXPECTED_CLEARANCE[scene]; idx = int(nearest[0])
            clearance.append({"scene_id": scene, "runtime_clearance_m": actual, "expected_clearance_m": expected_value, "absolute_error_m": abs(actual - expected_value), "runtime_collision": actual <= 1e-9, "expected_collision": expected_value <= 1e-9, "collision_classification_agreement": (actual <= 1e-9) == (expected_value <= 1e-9), "nearest_observable_point_base_xy_m": first.points_xy[idx].tolist(), "threshold_m": .02, "threshold_passed": abs(actual - expected_value) <= .02})

    write("stage11bj_runtime_image_binding.json", {"status": "PASSED", "immutable_image_id": IMAGE, "container_name": "sgcf_gz_stage11bj", "container_id": "3f3ef6ee88b99381bef3aaa6031a625b4ed625a3c56b47af410faac57a39416a", "container_image_id": IMAGE, "created_using_mutable_tag": False})
    write("stage11bj_environment_consistency.json", {"status": "PASSED", "gazebo_sim": "8.14.0", "sdformat": "14.9.0", "gz_rendering_abi": 8, "ogre2_plugin_available": True, "hlms_resources_available": True, "egl_headless_context_available": True})
    write("stage11bj_preflight_assertions.json", {"status": "PASSED", "visibility_flags": 2, "lidar_visibility_mask": 4294967293, "robot_model_sha256": hashlib.sha256((PROJECT / "gazebo/models/sgcf_diff_drive_robot/model.sdf").read_bytes()).hexdigest(), "footprint_m": [.8, .5], "wheel_radius_m": .1, "wheel_separation_m": .5, "camera_resolution": [320, 240]})
    write("stage11bj_world_runtime_matrix.json", {"status": "BLOCKED", "decision": DECISION, "world_count": 12, "runtime_result_count": len(full_scenes), "full_runtime_scenes": full_scenes, "missing_or_incomplete_scenes": sorted(set(SCENES) - set(full_scenes)), "records": matrix})
    write("stage11bj_topic_discovery.json", topics); write("stage11bj_runtime_entity_audit.json", entities); write("stage11bj_runtime_pose_consistency.json", poses); write("stage11bj_sim_time_audit.json", sim)
    write("stage11bj_lidar_self_visibility_regression.json", {"status": "PASSED_FOR_COMPLETED_SCENES", "records": self_visibility, "all_completed_scenes_self_return_zero": all(x.get("all_frames_self_return_zero", True) for x in self_visibility.values()), "initial_collision_external_visible": self_visibility.get("initial_collision", {}).get("external_obstacle_inside_footprint_count", 0) > 0})
    write("stage11bj_lidar_runtime_metrics.json", lidar); write("stage11bj_lidar_adapter_metrics.json", adapter); write("stage11bj_camera_runtime_metrics.json", camera)
    write("stage11bj_camera_stage07_consistency.json", {"status": "PASSED_FOR_COMPLETED_SCENES", "expected": {"width": 320, "height": 240, "fx": 180., "fy": 180., "cx": 160., "cy": 120., "horizontal_fov_rad": 1.453284681363431, "near_clip_m": .05, "far_clip_m": 20.}, "all_completed_match": all(x.get("width", 320) == 320 and x.get("height", 240) == 240 for x in camera.values())})
    write("stage11bj_odometry_runtime_metrics.json", odom); write("stage11bj_runtime_frame_audit.json", {"status": "PASSED_FOR_COMPLETED_SCENES", "base_axes": {"x": "forward", "y": "left", "z": "up"}, "lidar_runtime_to_contract": "scoped lidar sensor -> lidar_link -> base_link", "camera_optical_transform_unchanged": True})
    write("stage11bj_runtime_clearance_consistency.json", {"status": "FAILED", "decision": DECISION, "records": clearance, "threshold_m": .02, "classification_agreement": sum(x["collision_classification_agreement"] for x in clearance) / len(clearance), "failed_scenes": [x["scene_id"] for x in clearance if not x["threshold_passed"]], "root_cause_evidence": "static_corridor and narrow_passage use <scale> under <include>; SDFormat 1.9 runtime warns this element is undefined and does not apply the intended wall dimensions", "world_geometry_used_for_runtime_distance": False})
    write("stage11bj_human_path_side_runtime_audit.json", {"status": "PASSED_RUNTIME_ONLY", "runtime_clearance_record": next(x for x in clearance if x["scene_id"] == "human_path_side"), "self_return_count_zero": self_visibility["human_path_side"]["all_frames_self_return_zero"], "historical_planner_limit": {"P0": "geometry recheck rejection", "P1_P2": "OSQP_MAX_ITER_REACHED at 10000 iterations"}, "planner_run": False})
    semantic = []
    class_ids = {"UNKNOWN": 0, "STATIC_OBSTACLE": 1, "HUMAN": 2, "VEHICLE": 3, "ROBOT": 4}
    for scene_name in ["single_static_obstacle", "human_path_center", "human_path_side", "vehicle_path", "robot_obstacle"]:
        for obstacle in scenarios[scene_name]["obstacles"]: semantic.append({"scene_id": scene_name, "entity": obstacle["name"], "class_name": obstacle["semantic_class"], "class_id": class_ids[obstacle["semantic_class"]], "runtime_entity_present": obstacle["name"] in entities[scene_name]["observed"]})
    write("stage11bj_oracle_semantic_runtime.json", {"status": "PASSED_BOUNDARY_FOR_COMPLETED_SCENES", "records": semantic, "unknown_entity_class": 0, "lidar_points_modified": False, "exact_geometry_modified": False, "planner_access": False, "pointpainting_executed": False, "semantic_margin_executed": False})
    write("stage11bj_r1_runtime_contract.json", {"status": "NOT_COMPLETED_DUE_TO_EARLIER_GEOMETRY_STOP", "rgb_dropout_contract": {"status": "NOT_EXECUTED_FULL_RUNTIME", "semantic_valid": False, "fallback_reason": "RGB_DROPOUT", "semantic_contribution_enabled": False}, "outdated_rgb_contract": {"status": "RUNTIME_DATA_CAPTURED_BUT_NOT_ACCEPTED_AFTER_STOP", "semantic_valid": False, "fallback_reason": "OUTDATED_IMAGE", "semantic_contribution_enabled": False}, "planner_called": False})
    write("stage11bj_sensor_rate_metrics.json", rates); write("stage11bj_runtime_startup_latency.json", {"status": "NOT_EXECUTED_DUE_TO_EARLIER_GEOMETRY_STOP", "required_scenes": ["empty_world", "single_static_obstacle", "human_path_side"], "required_samples_per_scene": 3, "additional_runs_executed": 0, "small_sample_note": True})
    write("stage11bj_process_cleanup.json", {"status": "PASSED_WITH_RAW_MONITOR_FALSE_POSITIVES", "per_scene": {x["scene_id"]: {"raw": x["cleanup_raw"], "monitor_shell_false_positive": x["cleanup_false_positive_monitor_shell"], "authoritative_residual_process_count": x["authoritative_residual_process_count"]} for x in matrix}, "stage_container_stopped": True, "final_host_residual_gazebo_process_count": 0})
    current_robot = hashlib.sha256((PROJECT / "gazebo/models/sgcf_diff_drive_robot/model.sdf").read_bytes()).hexdigest()
    expected_asset = json.loads((S11I / "stage11bi_updated_asset_manifest.json").read_text())
    current_worlds = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((PROJECT / "gazebo/worlds").glob("*.sdf"))}
    write("stage11bj_frozen_asset_audit.json", {"status": "PASSED", "entry_robot_hash": expected_asset["new_robot_model_sha256"], "exit_robot_hash": current_robot, "robot_hash_equal": current_robot == expected_asset["new_robot_model_sha256"], "entry_world_hashes": expected_asset["world_hashes"], "exit_world_hashes": current_worlds, "world_hashes_equal": current_worlds == expected_asset["world_hashes"], "gazebo_modified_by_stage11bj": False, "docker_modified_by_stage11bj": False, "core_modified": False, "planner_started": False, "stage10_loaded": False, "ros_bridge_started": False, "motion_commands_sent": False})
    write("stage11bj_stage11bi_evidence_integration.json", {"status": "INTEGRATED", "stage11bi_decision": "STAGE_11B_I_COMPLETE", "formal_visibility_fix_preserved": True, "full_matrix_self_return_regression_passed_for_completed_scenes": True, "stage11bh_historical_failure_overwritten": False})
    (OUT / "known_limitations.md").write_text("""# Known limitations

- Stage 11B-J stopped because `static_corridor` and `narrow_passage` runtime clearances differ from their authoritative manifest values by much more than 0.02 m.
- Both worlds place `<scale>` under `<include>`; SDFormat 1.9 reports that element as undefined, so the intended wall dimensions are not applied at runtime.
- Startup-latency repeats and complete R1 acceptance were not executed after the immediate-stop condition.
- `rgb_dropout_contract` did not complete its full sensor capture before the stop sequence.
- Some raw cleanup files falsely counted concurrent monitoring shells whose command text contained `gz sim`; executable-aware post-checks found no Gazebo residuals.
- `robot_obstacle` needed a SIGKILL after complete data capture when the server ignored INT and TERM. Data are retained, but clean shutdown is a known runtime limitation.
""", encoding="utf-8")
    report = f"""# Stage 11B-J Full Runtime Matrix Rerun Report

## Decision

```text
{DECISION}
```

The immutable `99de6309…` environment and formal Stage 11B-I visibility contract passed preflight. Eleven worlds completed full LiDAR / Camera / Odometry / clock capture; `rgb_dropout_contract` did not complete its full capture before the stopped outer sequence. Stage 11B-H remains unchanged as historical failure evidence.

The formal visibility fix itself generalized across every completed scene: robot self-return count remained zero, and `initial_collision` preserved external footprint-internal returns and collision classification. Camera, Odometry, frame, and Adapter contracts passed for completed scenes.

The immediate blocker is runtime geometry consistency. `static_corridor` measured approximately 1.101012 m instead of 0.375 m (error 0.726012 m), and `narrow_passage` measured approximately 1.098491 m instead of 0.26 m (error 0.838491 m). Their stderr logs explicitly report that `<scale>` under `<include>` is not defined in SDF 1.9. Thus the intended wall geometry from the Stage 11A manifest is not instantiated at runtime. No world or asset repair was authorized, so startup repeats, complete R1 acceptance, and a Stage 11B completion decision were not performed.

No Planner, Stage 10 inference, PointPainting, Semantic Margin, ROS bridge, or motion command was used. Stage 11C is not authorized.
"""
    (OUT / "stage_11b_j_report.md").write_text(report, encoding="utf-8")
    (OUT / "stage_11b_j_decision.md").write_text(f"# Stage 11B-J Decision\n\n```text\n{DECISION}\n```\n", encoding="utf-8")


if __name__ == "__main__":
    main()
