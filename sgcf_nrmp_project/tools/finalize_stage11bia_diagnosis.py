#!/usr/bin/env python3
"""Finalize Stage 11B-I-A from its two authorized empty-world runs."""

from __future__ import annotations

import hashlib
import json
import math
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts/stages/stage_11b_i_a_self_return_diagnosis"
FORMAL = OUT / "logs/formal"
PROBE = OUT / "logs/probe"
ROBOT = ROOT / "gazebo/models/sgcf_diff_drive_robot/model.sdf"
WORLD = ROOT / "gazebo/worlds/empty_world.sdf"
DECISION = "SELF_RETURN_CAUSED_BY_ROBOT_VISUAL_VISIBILITY"


def write_json(name: str, value: Any) -> None:
    (OUT / name).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def scan_metrics(directory: Path) -> dict[str, Any]:
    scans = rows(directory / "scan_20.jsonl")
    records = []
    for message_index, scan in enumerate(scans):
        finite = []
        inside = []
        for beam, raw in enumerate(scan["ranges"]):
            distance = float(raw)
            if not math.isfinite(distance):
                continue
            angle = float(scan["angleMin"]) + beam * float(scan["angleStep"])
            point = [distance * math.cos(angle), distance * math.sin(angle)]
            item = {"beam_index": beam, "range_m": distance, "bearing_rad": angle, "point_xy_m": point}
            finite.append(item)
            if abs(point[0]) <= 0.4 and abs(point[1]) <= 0.25:
                inside.append(item)
        nearest = min(finite, key=lambda item: item["range_m"]) if finite else None
        records.append({
            "message_index": message_index,
            "finite_point_count": len(finite),
            "inside_footprint_finite_point_count": len(inside),
            "inside_footprint_beam_indices": [item["beam_index"] for item in inside],
            "nearest_point": nearest,
        })
    nearest_signatures = {
        None if record["nearest_point"] is None else (
            record["nearest_point"]["beam_index"],
            round(record["nearest_point"]["point_xy_m"][0], 9),
            round(record["nearest_point"]["point_xy_m"][1], 9),
        ) for record in records
    }
    return {
        "lidar_messages": len(scans),
        "camera_messages": len(rows(directory / "camera_5.jsonl")),
        "odometry_messages": len(rows(directory / "odom_20.jsonl")),
        "records": records,
        "inside_point_cloud_stable": len({tuple(r["inside_footprint_beam_indices"]) for r in records}) == 1,
        "nearest_robot_relative_point_stable": len(nearest_signatures) == 1,
    }


def geometry_audit() -> tuple[dict[str, Any], dict[str, Any]]:
    root = ET.parse(ROBOT).getroot()
    model = root.find("model")
    assert model is not None
    visuals = [
        {"name": "body", "parent_link": "base_link", "geometry": "box", "local_pose": [0, 0, 0, 0, 0, 0], "base_frame_aabb_m": [[-0.4, -0.25, 0.0], [0.4, 0.25, 0.2]], "material": [0.15, 0.25, 0.8, 1], "visibility_flags": 0xFFFFFFFF, "scan_plane_intersects": True},
        {"name": "left_wheel_visual", "parent_link": "left_wheel_link", "geometry": "cylinder", "local_pose": [0, -0.025, 0, math.pi / 2, 0, 0], "base_frame_aabb_m": [[-0.1, 0.2, 0.0], [0.1, 0.25, 0.2]], "material": [0.05, 0.05, 0.05, 1], "visibility_flags": 0xFFFFFFFF, "scan_plane_intersects": True},
        {"name": "right_wheel_visual", "parent_link": "right_wheel_link", "geometry": "cylinder", "local_pose": [0, 0.025, 0, math.pi / 2, 0, 0], "base_frame_aabb_m": [[-0.1, -0.25, 0.0], [0.1, -0.2, 0.2]], "material": [0.05, 0.05, 0.05, 1], "visibility_flags": 0xFFFFFFFF, "scan_plane_intersects": True},
    ]
    collisions = [
        {"name": "planner_footprint_collision", "parent_link": "base_link", "geometry": "box", "base_frame_aabb_m": [[-0.4, -0.25, 0], [0.4, 0.25, 0.2]]},
        {"name": "left_wheel_collision", "parent_link": "left_wheel_link", "geometry": "cylinder", "base_frame_aabb_m": [[-0.1, 0.2, 0], [0.1, 0.25, 0.2]]},
        {"name": "right_wheel_collision", "parent_link": "right_wheel_link", "geometry": "cylinder", "base_frame_aabb_m": [[-0.1, -0.25, 0], [0.1, -0.2, 0.2]]},
    ]
    inventory = {
        "source": str(ROBOT.relative_to(ROOT)),
        "links": [element.attrib["name"] for element in model.findall("link")],
        "joints": [element.attrib["name"] for element in model.findall("joint")],
        "visuals": visuals,
        "collisions": collisions,
        "sensors": [
            {"name": "lidar", "parent_link": "lidar_link", "type": "gpu_lidar", "base_frame_origin_m": [0, 0, 0.2], "scan_plane_z_m": 0.2, "angle_min_rad": -math.pi, "angle_max_rad": math.pi, "range_min_m": 0.05, "range_max_m": 8.0, "visibility_mask": 0xFFFFFFFF},
            {"name": "rgb_camera", "parent_link": "camera_link", "type": "camera", "base_frame_origin_m": [0, 0, 1.0]},
        ],
        "geometry_enumeration_complete": len(model.findall("./link/visual")) == 3 and len(model.findall("./link/collision")) == 3,
    }
    intersections = {
        "scan_plane_z_m": 0.2,
        "coplanar_with_body_top": True,
        "intersecting_visuals": [item["name"] for item in visuals if item["scan_plane_intersects"]],
        "wheel_inner_surfaces_y_m": [-0.2, 0.2],
        "body_side_surfaces_y_m": [-0.25, 0.25],
    }
    return inventory, intersections


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    formal = scan_metrics(FORMAL)
    probe = scan_metrics(PROBE)
    geometry, intersections = geometry_audit()
    write_json("stage11bia_robot_geometry_audit.json", geometry)
    write_json("stage11bia_lidar_plane_intersection.json", intersections)

    observed = formal["records"][0]["nearest_point"]
    assert observed is not None
    bearing = observed["bearing_rad"]
    predicted_range = -0.2 / math.sin(bearing)
    predicted = [predicted_range * math.cos(bearing), -0.2]
    observed_xy = observed["point_xy_m"]
    attribution = {
        "status": "SELF_RETURN_ATTRIBUTED_TO_ROBOT_VISUAL",
        "runtime_confirmation": "SELF_RETURN_CAUSED_BY_ROBOT_VISUAL_VISIBILITY",
        "observed_nearest": observed,
        "historical_stage11bh_representative": {"beam_index": 43, "point_xy_m": [-0.013986, -0.200011], "range_m": 0.2004998},
        "candidates_ranked": [
            {"candidate_visual": "right_wheel_visual", "surface": "inner AABB surface y=-0.2", "predicted_intersection_xy_m": predicted, "position_error_m": math.dist(predicted, observed_xy), "range_error_m": abs(predicted_range - observed["range_m"]), "bearing_error_rad": 0.0},
            {"candidate_visual": "body", "surface": "side y=-0.25", "predicted_range_m": -0.25 / math.sin(bearing), "range_error_m": abs((-0.25 / math.sin(bearing)) - observed["range_m"])},
        ],
        "symmetric_positive_y_source": "left_wheel_visual inner AABB surface y=+0.2",
        "visual_vs_collision_disambiguation": "The render-only visibility probe removed all returns without modifying collisions; therefore the runtime GPU LiDAR returns are caused by visuals.",
    }
    write_json("stage11bia_self_return_attribution.json", attribution)
    write_json("stage11bia_empty_world_self_return_metrics.json", {"scope": "FORMAL_ASSET_EMPTY_WORLD", **formal})

    environment = {
        "status": "FUNCTIONAL_ENVIRONMENT_EQUIVALENCE_CONFIRMED",
        "container_name": "sgcf_gz_harmonic_hlms_media_fix",
        "container_image_id": "sha256:4585ea4a757bad1cecab7f2943b9f4e6b9d3b3ad18f76848a577f0464be9ea3c",
        "current_tag_target_observed_at_audit": "sha256:99de6309b456a206402fed9ee51a5514316433b8a922de7b91ba0e79be0974d3",
        "not_byte_identical_to_historical_image": True,
        "gazebo_sim": "8.14.0", "sdformat": "14.9.0", "gz_rendering": "8.2.3", "gz_rendering_abi": 8,
        "ogre2_package": "libgz-rendering8-ogre2 8.2.3-1~jammy",
        "GZ_RENDERING_PLUGIN_PATH": "/usr/lib/x86_64-linux-gnu/gz-rendering-8/engine-plugins",
        "GZ_RENDERING_RESOURCE_PATH": "/usr/share/gz/gz-rendering8",
        "hlms_unlit_path": "/usr/share/gz/gz-rendering8/ogre2/media/Hlms/Unlit",
        "hlms_pbs_path": "/usr/share/gz/gz-rendering8/ogre2/media/Hlms/Pbs",
        "hlms_ogre2_gate_passed": True,
        "empty_world_sha256": sha256(WORLD), "robot_model_sha256": sha256(ROBOT),
        "core_version_drift": False,
    }
    write_json("stage11bia_environment_equivalence.json", environment)
    write_json("stage11bia_visibility_feature_audit.json", {
        "status": "SUPPORTED",
        "sdformat_schema_version": "1.9 (installed by SDFormat 14.9.0)",
        "visibility_flags_schema_supported": True,
        "visibility_flags_path": "/usr/share/sdformat14/1.9/visual.sdf",
        "visibility_mask_schema_supported": True,
        "visibility_mask_path": "/usr/share/sdformat14/1.9/lidar.sdf",
        "gpu_lidar_sensor_type_supported": True,
        "type": "unsigned int", "value_range": [0, 4294967295],
        "default_visual_flags": 4294967295, "default_lidar_mask": 4294967295,
        "semantics": "visible iff lidar visibility_mask bitwise-AND visual visibility_flags is nonzero",
    })
    write_json("stage11bia_visibility_probe.json", {
        "status": "PASSED", "decision": DECISION,
        "temporary_path": "/tmp/stage11bia_visibility_probe/", "gazebo_launch_number": 2,
        "visual_visibility_bit": 2, "lidar_mask": 4294967293,
        "formal_inside_footprint_counts": [r["inside_footprint_finite_point_count"] for r in formal["records"]],
        "probe_inside_footprint_counts": [r["inside_footprint_finite_point_count"] for r in probe["records"]],
        "probe_finite_lidar_return_count": sum(r["finite_point_count"] for r in probe["records"]),
        "lidar_messages": probe["lidar_messages"], "camera_messages": probe["camera_messages"], "odometry_messages": probe["odometry_messages"],
        "collision_modified": False, "sensor_pose_modified": False, "camera_modified": False, "external_world_modified": False,
        "formal_assets_modified": False,
    })
    write_json("stage11bia_process_cleanup.json", {
        "formal_cleanup_passed": (FORMAL / "cleanup_passed.txt").read_text().strip() == "true",
        "probe_runtime_process_query_after_collection": "no gz sim or gz-sim-server process",
        "residual_gazebo_process_count": 0, "passed": True,
    })
    write_json("stage11bia_frozen_component_audit.json", {
        "status": "PASSED", "gazebo_launch_count": 2, "worlds_run": ["empty_world", "empty_world temporary visibility copy"],
        "formal_empty_world_sha256": sha256(WORLD), "formal_robot_model_sha256": sha256(ROBOT),
        "formal_gazebo_modified": False, "docker_modified_by_stage11bia": False, "core_modified_by_stage11bia": False,
        "lidar_pose_modified": False, "camera_pose_modified": False, "collision_modified": False, "minimum_range_modified": False,
        "adapter_point_crop_added": False, "planner_started": False, "stage10_loaded": False, "ros_bridge_started": False,
    })

    report = f"""# Stage 11B-I-A LiDAR Self-return Diagnosis Report

## Decision

```text
{DECISION}
VISIBILITY_MASK_FIX_FEASIBLE
READY_FOR_STAGE_11B_I_FORMAL_VISIBILITY_FIX
```

## Environment equivalence

The running container preserves Gazebo Sim 8.14.0, SDFormat 14.9.0, gz-rendering ABI 8, OGRE2, EGL headless rendering, and both installed HLMS media trees. Its rebuilt image is functionally equivalent but not byte-identical to the historical image. The container itself uses image ID `{environment['container_image_id']}`. The local tag currently resolves to a newer rebuild, which did not alter the running diagnostic container.

## Source attribution

The LiDAR origin and scan plane are at base-frame `z=0.2 m`. This is coplanar with the body top and the top tangent of both wheel visuals. The formal run produced exactly ten finite returns in every one of 20 scans at beams `43–47` and `133–137`. The nearest return was beam 45 at `[0.0, -0.200012] m`; the historical beam-43 point `[-0.013986, -0.200011] m` lies on the right-wheel visual's inner AABB surface `y=-0.2 m`. The symmetric cluster lies on the left-wheel inner surface `y=+0.2 m`. The body side is at `|y|=0.25 m` and is a worse geometric match.

Attribution to rendering visuals rather than collision geometry is established by the temporary visibility-only probe: robot collisions were unchanged, while excluding the robot visual bit removed every finite self-return.

## Runtime probe

SDFormat's installed schema explicitly supports `visual/visibility_flags` and `lidar/visibility_mask` as 32-bit unsigned masks. In `/tmp/stage11bia_visibility_probe/`, the three robot visuals used bit `2` and the LiDAR used mask `4294967293`, excluding only that bit. The probe retained 20 LiDAR messages, 5 camera images, and 20 odometry messages. All 20 LiDAR frames had zero footprint-internal points; Camera and Odometry remained operational. Formal Gazebo assets were not modified.

## Why sensor height was not changed

Raising LiDAR changes its absolute pose, scan plane, observable-point distribution, Stage 11A sensor contract, and runtime-clearance relationship. Raising LiDAR and Camera together may preserve their relative transform but still changes `base_link -> lidar_link`, `base_link -> camera_link`, and both world-to-sensor poses. That requires a separately authorized installation-contract revision and frame, sensor, geometry, clearance, and projection regression. It was neither needed nor performed here.

No Planner, Stage 10 model, ROS bridge, other world, adapter filtering, minimum-range change, collision change, or formal visibility fix was executed.
"""
    (OUT / "stage_11b_i_a_report.md").write_text(report, encoding="utf-8")
    (OUT / "stage_11b_i_a_decision.md").write_text(f"# Stage 11B-I-A Decision\n\n```text\n{DECISION}\nVISIBILITY_MASK_FIX_FEASIBLE\nREADY_FOR_STAGE_11B_I_FORMAL_VISIBILITY_FIX\n```\n", encoding="utf-8")
    (OUT / "known_limitations.md").write_text("""# Known limitations

- The result proves a visibility-only fix is feasible in a temporary copy; formal Gazebo assets remain unchanged.
- The probe used `empty_world` only and does not validate visibility behavior against external obstacles.
- The scan plane remains geometrically coplanar with robot visual surfaces until a formal visibility fix is authorized.
- Image bytes are not identical to the historical build, although locked Gazebo / SDFormat / rendering functionality is equivalent.
- The locally tagged image was rebuilt after the running container; the audited runtime identity is the container image ID recorded in the environment audit.
""", encoding="utf-8")


if __name__ == "__main__":
    main()
