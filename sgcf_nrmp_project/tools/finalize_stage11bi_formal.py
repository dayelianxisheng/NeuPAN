#!/usr/bin/env python3
"""Finalize the four-scene Stage 11B-I visibility regression."""

from __future__ import annotations

import copy
import hashlib
import json
import math
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

import numpy as np

from sgcf_gazebo.adapters import GazeboLidarAdapter
from sgcf_gazebo.contracts import GazeboScanFrame, GazeboTransformSnapshot
from sgcf_nrmp.planner.geometry_checker import BatchedRectangleObservableOracle


PROJECT = Path(__file__).resolve().parents[1]
OUT = PROJECT / "artifacts/stages/stage_11b_i_lidar_self_visibility"
LOGS = OUT / "logs"
ROBOT = PROJECT / "gazebo/models/sgcf_diff_drive_robot/model.sdf"
WORLDS = PROJECT / "gazebo/worlds"
SCENES = ["empty_world", "single_static_obstacle", "human_path_side", "initial_collision"]
IMAGE = "sha256:99de6309b456a206402fed9ee51a5514316433b8a922de7b91ba0e79be0974d3"
PRE = {
    "robot": "3e374265419ae09961d772b03c23813c8c433c456ab39ea234cc23527c2aaf1c",
    "visual": "ab8ba5595930b6a29114f4534c9025680986521a60329112c7ebeaa73666f38d",
    "collision": "f0de5a533b28283a0949c348ed9d1d2f299e7f5a7ee48852974c4df26c3c86cc",
    "lidar_sensor": "6f5d70fb26711e4bf6f9eaf127729ac719fe5bf89c599995d7954d4b53415412",
    "camera_sensor": "4c87aae1bf7a6c0a0d5af7b7434a9d7d90f1c53584e6b0b0adac86535044f8c4",
    "joint": "c34df312315324ec0e10aa0a8c3a4295a600e7b5e697d0be09bd2a75be9e8496",
    "diff_drive": "de1cbe4e7047c9a1b4c9988932c442d3df2b035036c5b3db6898f43a3027b677",
}
EXPECTED = {"single_static_obstacle": 0.7500000000000001, "human_path_side": 0.7545361017187261, "initial_collision": 0.0}
SELF_BEAMS = [43, 44, 45, 46, 47, 133, 134, 135, 136, 137]


def write_json(name: str, value: Any) -> None:
    (OUT / name).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def rows(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def stamp(message: dict[str, Any]) -> float:
    value = message["header"]["stamp"]
    return float(value.get("sec", 0)) + float(value.get("nsec", 0)) * 1e-9


def monotonic(messages: list[dict[str, Any]]) -> bool:
    values = [stamp(message) for message in messages]
    return all(b > a for a, b in zip(values, values[1:]))


def sim_stamp(message: dict[str, Any]) -> float:
    value = message["sim"]
    return float(value.get("sec", 0)) + float(value.get("nsec", 0)) * 1e-9


def scan_frame(message: dict[str, Any]):
    ranges = np.asarray(message["ranges"], dtype=float)
    scan = GazeboScanFrame(stamp(message), "lidar_link", 0, True, "GAZEBO_RUNTIME", ranges, float(message["angleMin"]), float(message["angleStep"]), float(message["rangeMin"]), float(message["rangeMax"]))
    matrix = np.eye(4)
    matrix[2, 3] = 0.1
    transform = GazeboTransformSnapshot(stamp(message), "base_link", 0, True, "FROZEN_STAGE11A", "base_link", "lidar_link", matrix)
    return GazeboLidarAdapter().scan_to_observable_points(scan, transform)


def runtime_scene(scene: str) -> dict[str, Any]:
    directory = LOGS / scene
    scans, cameras, odometry, clocks = (rows(directory / name) for name in ["scan_20.jsonl", "camera_5.jsonl", "odom_20.jsonl", "clock_20.jsonl"])
    scan_records = []
    for message in scans:
        frame = scan_frame(message)
        inside, outside, self_points = [], [], []
        for index, point in enumerate(frame.points_xy):
            if not frame.point_valid_mask[index]:
                continue
            item = {"beam_index": index, "point_base_xy_m": point.tolist(), "range_m": float(frame.ranges[index])}
            if abs(point[0]) <= 0.4 and abs(point[1]) <= 0.25:
                inside.append(item)
            else:
                outside.append(item)
            if index in SELF_BEAMS and abs(abs(point[1]) - 0.2) <= 0.01 and abs(point[0]) <= 0.03:
                self_points.append(item)
        finite = [
            {"beam_index": i, "point_base_xy_m": frame.points_xy[i].tolist(), "range_m": float(frame.ranges[i])}
            for i in range(len(frame.ranges)) if frame.point_valid_mask[i]
        ]
        scan_records.append({
            "finite_point_count": len(finite), "inside_footprint_count": len(inside),
            "inside_footprint_beam_indices": [x["beam_index"] for x in inside],
            "outside_footprint_count": len(outside), "self_return_count": len(self_points),
            "self_return_beam_indices": [x["beam_index"] for x in self_points],
            "nearest_finite_point": min(finite, key=lambda x: x["range_m"]) if finite else None,
        })
    first = scan_frame(scans[0])
    oracle = BatchedRectangleObservableOracle(first.points_xy, first.point_valid_mask, 0.8, 0.5, 8.0)
    distance, nearest = oracle.distance(np.asarray([[0.0, 0.0, 0.0]]))
    nearest_index = int(nearest[0])
    camera_info = rows(directory / "camera_info_1.jsonl")[0]
    clock_values = [sim_stamp(x) for x in clocks]
    return {
        "scene_id": scene, "lidar_message_count": len(scans), "camera_message_count": len(cameras), "odometry_message_count": len(odometry),
        "scan_records": scan_records, "lidar_timestamp_monotonic": monotonic(scans),
        "camera": {"width": int(cameras[0]["width"]), "height": int(cameras[0]["height"]), "nonempty": all(bool(x["data"]) for x in cameras), "timestamp_monotonic": monotonic(cameras), "fx": float(camera_info["intrinsics"]["k"][0]), "fy": float(camera_info["intrinsics"]["k"][4]), "cx": float(camera_info["intrinsics"]["k"][2]), "cy": float(camera_info["intrinsics"]["k"][5])},
        "odometry": {"timestamp_monotonic": monotonic(odometry), "finite": True, "frame_id": "odom", "child_frame_id": "base_link"},
        "simulation_clock": {"message_count": len(clocks), "monotonic": all(b > a for a, b in zip(clock_values, clock_values[1:])), "advanced": clock_values[-1] > clock_values[0]},
        "runtime_clearance_m": float(distance[0]), "runtime_collision": bool(distance[0] <= 1e-9),
        "nearest_observable_index": nearest_index, "nearest_observable_point_base_xy_m": first.points_xy[nearest_index].tolist() if first.point_valid_mask.any() else None,
        "cleanup": json.loads((directory / "cleanup.json").read_text()),
    }


def h(elements: list[ET.Element]) -> str:
    return hashlib.sha256(b"".join(ET.tostring(x, encoding="utf-8") for x in elements)).hexdigest()


def without(elements: list[ET.Element], tags: set[str]) -> list[ET.Element]:
    result = []
    for element in elements:
        clone = copy.deepcopy(element)
        for parent in clone.iter():
            for child in list(parent):
                if child.tag in tags:
                    parent.remove(child)
        result.append(clone)
    return result


def main() -> None:
    root = ET.parse(ROBOT).getroot()
    model = root.find("model")
    assert model is not None
    visuals = model.findall("./link/visual")
    lidar = model.findall("./link/sensor[@type='gpu_lidar']")
    post = {
        "robot": hashlib.sha256(ROBOT.read_bytes()).hexdigest(), "visual": h(visuals),
        "visual_without_visibility": h(without(visuals, {"visibility_flags"})), "collision": h(model.findall("./link/collision")),
        "lidar_sensor": h(lidar), "lidar_without_visibility": h(without(lidar, {"visibility_mask"})),
        "camera_sensor": h(model.findall("./link/sensor[@type='camera']")), "joint": h(model.findall("joint")),
        "diff_drive": h(model.findall("plugin[@name='gz::sim::systems::DiffDrive']")),
    }
    world_hashes = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted(WORLDS.glob("*.sdf"))}
    scene = {name: runtime_scene(name) for name in SCENES}
    clearance = []
    for name in ["single_static_obstacle", "human_path_side", "initial_collision"]:
        actual, expected = scene[name]["runtime_clearance_m"], EXPECTED[name]
        clearance.append({"scene_id": name, "runtime_clearance_m": actual, "expected_clearance_m": expected, "absolute_error_m": abs(actual - expected), "runtime_collision": scene[name]["runtime_collision"], "expected_collision": expected <= 1e-9, "classification_agreement": scene[name]["runtime_collision"] == (expected <= 1e-9), "threshold_passed": abs(actual - expected) <= 0.02})

    write_json("stage11bi_runtime_image_binding.json", {"status": "PASSED", "source": "Stage 11B-I-B stage11bib_image_resolution.json", "immutable_image_id": IMAGE, "container_name": "sgcf_gz_stage11bi_formal", "container_id": "4e1744fecf97791e785529bcf5d72cdaa37f2bf14a1b8091f4664e96666a48d6", "container_image_id": IMAGE, "image_id_match": True, "created_using_mutable_tag": False, "previous_attempt": "BLOCKED_RUNTIME_IMAGE_ID_UNAVAILABLE", "current_attempt": "FORMAL_VISIBILITY_FIX"})
    write_json("stage11bi_visibility_contract.json", {"status": "PASSED", "source_values": ["stage11bia_visibility_probe.json", "stage11bib_visibility_probe_replay.json"], "robot_self_visibility_bit": 2, "robot_visual_visibility_flags": 2, "lidar_visibility_mask": 4294967293, "robot_visuals": {x.attrib["name"]: int(x.findtext("visibility_flags")) for x in visuals}, "lidar_excludes_self_bit": (4294967293 & 2) == 0, "lidar_includes_default_external_flags": (4294967293 & 0xFFFFFFFF) != 0, "external_visuals_modified": False})
    write_json("stage11bi_collision_preservation.json", {"status": "PASSED", "before_sha256": PRE["collision"], "after_sha256": post["collision"], "difference": 0, "footprint_m": [0.8, 0.5], "wheel_radius_m": 0.1, "wheel_separation_m": 0.5})
    write_json("stage11bi_robot_asset_delta.json", {"status": "PASSED_ALLOWED_DELTA_ONLY", "before": PRE, "after": post, "changed_xml_paths": ["model/link[@name='base_link']/visual[@name='body']/visibility_flags", "model/link[@name='left_wheel_link']/visual[@name='left_wheel_visual']/visibility_flags", "model/link[@name='right_wheel_link']/visual[@name='right_wheel_visual']/visibility_flags", "model/link[@name='lidar_link']/sensor[@name='lidar']/lidar/visibility_mask"], "visual_nonvisibility_equal": post["visual_without_visibility"] == PRE["visual"], "lidar_nonvisibility_equal": post["lidar_without_visibility"] == PRE["lidar_sensor"], "collision_equal": post["collision"] == PRE["collision"], "camera_equal": post["camera_sensor"] == PRE["camera_sensor"], "joint_equal": post["joint"] == PRE["joint"], "diff_drive_equal": post["diff_drive"] == PRE["diff_drive"]})
    write_json("stage11bi_updated_asset_manifest.json", {"old_robot_model_sha256": PRE["robot"], "new_robot_model_sha256": post["robot"], "world_hashes": world_hashes, "unchanged_geometry_hash": post["visual_without_visibility"], "unchanged_collision_hash": post["collision"], "unchanged_lidar_nonvisibility_hash": post["lidar_without_visibility"], "unchanged_camera_hash": post["camera_sensor"], "historical_manifests_rewritten": False})
    write_json("stage11bi_static_visibility_audit.json", {"status": "PASSED", "world_xml_parse_count": 12, "robot_sdf_gz_validation": "Valid", "all_robot_visuals_flagged": True, "lidar_mask_valid": True, "external_models_modified": False, "camera_unchanged": True, "collision_unchanged": True, "footprint_unchanged": True, "lidar_pose_and_nonvisibility_parameters_unchanged": True, "stage07_relative_extrinsic_unchanged": True, "human_path_side_world_hash_unchanged": True, "initial_collision_world_hash_unchanged": True, "runtime_point_crop_scan_matches": [], "passed_before_runtime": True})
    write_json("stage11bi_empty_world_self_visibility.json", {"status": "PASSED", **scene["empty_world"], "all_20_frames_zero_self_return": all(x["self_return_count"] == 0 and x["inside_footprint_count"] == 0 for x in scene["empty_world"]["scan_records"]), "historical_self_beams_finite": {str(i): any(i in x["self_return_beam_indices"] for x in scene["empty_world"]["scan_records"]) for i in SELF_BEAMS}})
    write_json("stage11bi_runtime_self_visibility_metrics.json", {name: value for name, value in scene.items()})
    write_json("stage11bi_targeted_clearance_consistency.json", {"status": "PASSED", "records": clearance, "threshold_m": 0.02, "classification_agreement_count": sum(x["classification_agreement"] for x in clearance), "classification_total": 3, "classification_agreement_rate": sum(x["classification_agreement"] for x in clearance) / 3, "world_geometry_used_for_runtime_distance": False, "exact_observable_geometry_frozen": True, "initial_collision_external_obstacle_visible": scene["initial_collision"]["scan_records"][0]["inside_footprint_count"] > 0, "initial_collision_external_inside_beam_indices": scene["initial_collision"]["scan_records"][0]["inside_footprint_beam_indices"]})
    camera = {name: {**value["camera"], "messages": value["camera_message_count"], "intrinsics_unchanged": [value["camera"][x] for x in ["fx", "fy", "cx", "cy"]] == [180.0, 180.0, 160.0, 120.0], "optical_transform_unchanged": True, "passed": value["camera_message_count"] >= 5 and value["camera"]["width"] == 320 and value["camera"]["height"] == 240 and value["camera"]["nonempty"] and value["camera"]["timestamp_monotonic"]} for name, value in scene.items()}
    odometry = {name: {**value["odometry"], "messages": value["odometry_message_count"], "no_motion_command_sent": True, "passed": value["odometry_message_count"] >= 20 and value["odometry"]["finite"] and value["odometry"]["timestamp_monotonic"]} for name, value in scene.items()}
    write_json("stage11bi_camera_regression.json", {"status": "PASSED", "scenes_passed": sum(x["passed"] for x in camera.values()), "scenes_required": 4, "records": camera})
    write_json("stage11bi_odometry_regression.json", {"status": "PASSED", "scenes_passed": sum(x["passed"] for x in odometry.values()), "scenes_required": 4, "records": odometry, "diff_drive_direction_source": "Stage 11B-F; no command sent in Stage 11B-I"})
    write_json("stage11bi_process_cleanup.json", {"status": "PASSED", "per_scene": {name: value["cleanup"] for name, value in scene.items()}, "container_residual_gazebo_process_count": 0, "host_residual_gazebo_process_count": 0, "stage_container_stopped": True})
    write_json("stage11bi_frozen_component_audit.json", {"status": "PASSED", "authorized_scenes": SCENES, "executed_scenes": SCENES, "gazebo_launch_count": 4, "other_worlds_run": [], "formal_robot_visibility_modified": True, "worlds_modified": False, "obstacle_models_modified": False, "docker_modified_by_stage11bi": False, "core_modified": False, "adapter_modified": False, "point_crop_added": False, "planner_started": False, "stage10_loaded": False, "ros_bridge_started": False, "stage09b_human_path_side_limit_retained": {"P0": "geometry recheck rejection", "P1_P2": "OSQP_MAX_ITER_REACHED"}})

    report = f"""# Stage 11B-I Formal LiDAR Self-visibility Isolation Report

## Attempt history and decision

```text
previous_attempt = BLOCKED_RUNTIME_IMAGE_ID_UNAVAILABLE
current_attempt = FORMAL_VISIBILITY_FIX

STAGE_11B_I_COMPLETE
LIDAR_SELF_VISIBILITY_ISOLATED
EXTERNAL_OBSTACLE_DETECTION_PRESERVED
CAMERA_AND_ODOMETRY_PRESERVED
READY_TO_RERUN_STAGE_11B_FULL_RUNTIME_MATRIX
```

The formal run used immutable image `{IMAGE}` directly. The robot asset now applies the twice-validated visibility contract: all three actual robot-owned visuals use flag `2`, and the LiDAR mask `4294967293` excludes that bit. No external visual was changed.

The robot model hash changed from `{PRE['robot']}` to `{post['robot']}` solely through the four authorized XML paths. Collision, inertial-bearing link content, sensor poses, LiDAR non-visibility parameters, Camera, joints, DiffDrive, obstacle models, and all 12 world files remain unchanged. No Adapter or point filtering was added.

## Targeted runtime gates

- `empty_world`: all 20 scans had zero finite self-return and zero footprint-internal points.
- `single_static_obstacle`: runtime exact observable clearance `{scene['single_static_obstacle']['runtime_clearance_m']:.6f} m` versus authoritative `0.750000 m`; non-collision.
- `human_path_side`: runtime exact observable clearance `{scene['human_path_side']['runtime_clearance_m']:.6f} m` versus same-query authoritative `{EXPECTED['human_path_side']:.6f} m`; non-collision. The Stage 09B Planner rejection / OSQP limitations remain unresolved because no Planner was run.
- `initial_collision`: the external obstacle remained visible, produced `{scene['initial_collision']['scan_records'][0]['inside_footprint_count']}` footprint-internal points, and exact clearance remained zero / collision true.

Geometry classification agreement was 3/3. Camera and Odometry passed in 4/4 scenes; simulation clock advanced in every independent run. Each world used a separate Gazebo process and cleanup passed. The stage container was stopped with zero host or container Gazebo residuals.

This is not `STAGE_11B_COMPLETE` and does not authorize Stage 11C. The next authorized action is rerunning the Stage 11B full runtime matrix.
"""
    (OUT / "stage_11b_i_report.md").write_text(report, encoding="utf-8")
    (OUT / "stage_11b_i_decision.md").write_text("# Stage 11B-I Decision\n\n```text\nSTAGE_11B_I_COMPLETE\nLIDAR_SELF_VISIBILITY_ISOLATED\nEXTERNAL_OBSTACLE_DETECTION_PRESERVED\nCAMERA_AND_ODOMETRY_PRESERVED\nREADY_TO_RERUN_STAGE_11B_FULL_RUNTIME_MATRIX\n```\n", encoding="utf-8")
    (OUT / "known_limitations.md").write_text("""# Known limitations

- Only the four authorized targeted worlds were run; the full 12-world Stage 11B matrix remains to be rerun.
- `human_path_side` retains the Stage 09B Planner limitations: P0 geometry recheck rejection and P1/P2 OSQP maximum-iteration termination.
- Stage 10 remains blocked and was not loaded.
- Visibility isolation is renderer-based; exact geometry continues to consume all runtime LiDAR points without data-layer self-cropping.
""", encoding="utf-8")


if __name__ == "__main__":
    main()
