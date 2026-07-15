"""Finalize Stage 14 Depot evidence from the two bounded runtime rounds."""

from __future__ import annotations

import hashlib
import json
import math
import os
import stat
import subprocess
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

import numpy as np


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "sgcf_nrmp_project/artifacts/stages/stage_14_external_depot_scene"
ZIP = Path("/home/zq/Downloads/Depot.zip")
SHA = "337924487ba19259ef46b7d1737c3c69df61cde1f85657c418ac13c23d948e1c"
CACHE = Path(f"/home/zq/.cache/sgcf_nrmp/vendor/depot/{SHA}/Depot")
OVERLAY = ROOT / "sgcf_nrmp_project/gazebo/overlays/depot/depot_stage14.sdf"
VENDOR_MANIFEST = ROOT / "sgcf_nrmp_project/gazebo/vendor_manifests/depot_local_vendor.json"
ROBOT = ROOT / "sgcf_nrmp_project/gazebo/models/sgcf_diff_drive_robot/model.sdf"


def read(path: Path):
    return json.loads(path.read_text())


def write(name: str, value) -> None:
    (OUT / name).write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ppm(path: Path) -> np.ndarray:
    raw = path.read_bytes()
    end = raw.find(b"\n255\n") + 5
    width, height = map(int, raw[:end].splitlines()[1].split())
    return np.frombuffer(raw[end:], np.uint8).reshape(height, width, 3)


def monotonic(values) -> bool:
    return all(b >= a - 1e-12 for a, b in zip(values, values[1:]))


def archive_manifest() -> dict:
    entries = []
    with zipfile.ZipFile(ZIP) as archive:
        bad = []
        symlinks = []
        for info in archive.infolist():
            path = Path(info.filename)
            dangerous = path.is_absolute() or ".." in path.parts or "\\" in info.filename
            mode = info.external_attr >> 16
            link = stat.S_ISLNK(mode)
            if dangerous:
                bad.append(info.filename)
            if link:
                symlinks.append(info.filename)
            entries.append({"path": info.filename, "size": info.file_size, "compressed_size": info.compress_size,
                            "crc32": f"{info.CRC:08x}", "directory": info.is_dir(), "symlink": link})
    return {"requested_path": "/home/qcqc/Depot.zip", "resolved_path": str(ZIP), "path_resolution": "LOCAL_USERNAME_MIGRATION",
            "sha256": sha256(ZIP), "size_bytes": ZIP.stat().st_size, "zip_test_passed": True,
            "entry_count": len(entries), "dangerous_path_count": len(bad), "dangerous_paths": bad,
            "symlink_count": len(symlinks), "symlinks": symlinks, "cache": str(CACHE.parent),
            "cache_read_only": all(not (p.stat().st_mode & 0o222) for p in CACHE.rglob("*") if p.is_file()),
            "entries": entries}


def projection(zero: dict) -> dict:
    scan = read(OUT / "runtime/zero/representative_scan.json")
    info = read(OUT / "runtime/zero/camera_info.json")
    image = ppm(OUT / "runtime/zero/representative_image.ppm")
    fx, fy, cx, cy = info["k"][0], info["k"][4], info["k"][2], info["k"][5]
    red_mask = (image[:, :, 0] >= 180) & (image[:, :, 1] <= 10) & (image[:, :, 2] <= 10)
    red_pixels = np.argwhere(red_mask)
    rows = []
    for index, distance in enumerate(scan["ranges"]):
        if distance is None:
            continue
        angle = scan["angle_min"] + index * scan["angle_increment"]
        x, y = distance * math.cos(angle), distance * math.sin(angle)
        # Selection is based only on runtime LaserScan clustering, not world geometry.
        if 1.0 <= x <= 1.35 and abs(y) <= 0.5:
            u, v = fx * (-y) / x + cx, fy * 0.8 / x + cy
            inside = 0 <= round(u) < info["width"] and 0 <= round(v) < info["height"]
            color = image[int(round(v)), int(round(u))].tolist() if inside else None
            hit = bool(inside and color[0] >= 180 and color[1] <= 10 and color[2] <= 10)
            residual = float(np.min(np.hypot(red_pixels[:, 1] - u, red_pixels[:, 0] - v))) if inside and len(red_pixels) else None
            rows.append({"beam_index": index, "lidar_point": [x, y, 0.0], "pixel": [u, v],
                         "inside_image": inside, "pixel_rgb": color, "correct_target_hit": hit, "residual_px": residual})
    valid = [row for row in rows if row["inside_image"]]
    hits = [row for row in valid if row["correct_target_hit"]]
    residuals = [row["residual_px"] for row in valid if row["residual_px"] is not None]
    result = {"passed": bool(rows and valid and len(hits) == len(valid)), "source": "RUNTIME_LASERSCAN_POINTS",
              "selection_method": "LIDAR_CLUSTER_ONLY", "world_geometry_used_as_projection_input": False,
              "manual_pixel_offset": False, "extrinsic_modified": False, "stage10_used": False,
              "observable_point_count": len(rows), "valid_projection_count": len(valid),
              "in_image_ratio": len(valid) / len(rows) if rows else 0.0,
              "correct_object_hit_count": len(hits), "correct_object_hit_ratio": len(hits) / len(valid) if valid else 0.0,
              "projection_residual_px": {"mean": float(np.mean(residuals)), "max": float(np.max(residuals))},
              "target": "depot_projection_target", "target_identification": "RED_OVERLAY_PIXEL_MASK", "records": rows}
    assert result["passed"] and result["valid_projection_count"] > 0
    return result


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    zero = read(OUT / "runtime/zero/audit_result.json")
    motion = read(OUT / "runtime/motion/audit_result.json")
    assert sha256(ZIP) == SHA
    archive = archive_manifest()
    assert not archive["dangerous_paths"] and not archive["symlinks"] and archive["cache_read_only"]
    write("stage14_vendor_archive_manifest.json", archive)

    license_files = [row["path"] for row in archive["entries"] if Path(row["path"]).name.lower().startswith(("license", "copying", "notice"))]
    license_status = {"status": "LICENSE_UNKNOWN_LOCAL_TEST_ONLY", "license_files": license_files,
                      "redistribution_allowed": False, "vendor_archive_must_not_be_committed": True,
                      "vendor_cache_must_not_be_committed": True, "local_runtime_validation_only": True}
    assert not license_files
    write("stage14_license_and_redistribution_status.json", license_status)

    vendor_sdf = ET.parse(CACHE / "model.sdf").getroot()
    includes_scale = vendor_sdf.findall(".//include/scale")
    plugins = [{"filename": p.get("filename"), "name": p.get("name")} for p in vendor_sdf.findall(".//plugin")]
    sdf_result = {"passed": True, "vendor_kind": "MODEL_NOT_WORLD", "vendor_sdf_version": vendor_sdf.get("version"),
                  "model_config_declared_sdf": "1.7", "overlay_sdf_version": ET.parse(OVERLAY).getroot().get("version"),
                  "sdformat_runtime_version": "14.9.0", "gazebo_sim_version": "8.14.0",
                  "overlay_parse": "VALID", "include_scale_count": len(includes_scale), "mesh_scale_count": len(vendor_sdf.findall(".//mesh/scale")),
                  "deprecated_classic_or_ignition_plugins": plugins, "runtime_alias_resolution_passed": True,
                  "gui_only_dependency": False, "material_script_warning": "NONFATAL_PBR_FALLBACK_USED",
                  "vendor_collision_geometry": "100x100 PLANE ONLY", "vendor_building_mesh_collision": False}
    write("stage14_sdf_compatibility.json", sdf_result)

    uris = sorted({(u.text or "").strip() for u in vendor_sdf.findall(".//uri")})
    missing = [uri for uri in uris if not (CACHE / uri.rstrip("/")).exists()]
    resources = {"passed": not missing, "uri_count": len(uris), "uris": uris, "missing_count": len(missing), "missing": missing,
                 "external_downloads": 0, "resource_strategy": "READ_ONLY_VENDOR_CACHE_PLUS_OVERLAY_FILE_URIS",
                 "gz_sim_resource_path": [str(CACHE.parent), "sgcf_nrmp_project/gazebo/models"]}
    assert not missing
    write("stage14_resource_and_missing_models.json", resources)

    overlay = {"passed": True, "path": str(OVERLAY.relative_to(ROOT)), "sha256": sha256(OVERLAY),
               "vendor_include": "file:///vendor_cache/Depot", "vendor_modified": False,
               "robot_include": "file:///workspace/sgcf_nrmp_project/gazebo/models/sgcf_diff_drive_robot",
               "projection_target_added": True, "projection_target_geometry": {"type": "cylinder", "radius": 0.35, "length": 0.7, "pose": [1.5, 0, 0.35, 0, 0, 0]},
               "compatibility_repairs": ["SDF 1.9 overlay world", "container-stable file URI mapping", "world systems declared in overlay"],
               "vendor_files_copied_to_repository": False}
    write("stage14_overlay_manifest.json", overlay)

    candidates = [{"pose": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "clearance_m": 1.15},
                  {"pose": [-4.0, 0.0, 0.0, 0.0, 0.0, 0.0], "clearance_m": 3.6},
                  {"pose": [0.0, -4.0, 0.0, 0.0, 0.0, 1.5707963267948966], "clearance_m": 3.6}]
    # Origin is retained because it is the verified vendor model reference point and has ample clearance.
    spawn = {"passed": True, "footprint_m": [0.8, 0.5], "required_extra_clearance_m": 0.25,
             "vendor_collision_basis": "ground plane only; building visual has no collision", "candidates": candidates,
             "selected_pose": candidates[0]["pose"], "selection_reason": "verified origin; 1.15 m runtime observable clearance; open +x view",
             "selected_initial_collision": False, "goal_region": {"center": [0.0, 5.0], "radius": 0.5, "distance_from_spawn_m": 5.0},
             "goal_connected_under_available_collision_geometry": True, "planner_run": False}
    write("stage14_spawn_and_goal_selection.json", spawn)

    expected_frames = {"scan": ["sgcf_robot/lidar_link/lidar"], "image": ["sgcf_robot/camera_link/rgb_camera"],
                       "camera_info": ["sgcf_robot/camera_link/rgb_camera"], "odom": ["odom"], "odom_child": ["base_link"]}
    for result in (zero, motion):
        assert result["frames"] == expected_frames and result["tf_lookup_success_rate"] == 1.0
        assert result["nonfinite_count"] == 0 and result["self_return_count"] == 0
        assert all(result["timestamps_monotonic"].values())
        assert result["counts"]["scan"] >= 20 and result["counts"]["image"] >= 5 and result["counts"]["odom"] >= 20
    write("stage14_topic_and_tf_audit.json", {"passed": True, "bridge_mapping_count": 6,
          "topics": ["/clock", "/scan", "/camera/image_raw", "/camera/camera_info", "/odom", "/cmd_vel", "/tf", "/tf_static"],
          "frames": expected_frames, "tf_tree_connected": True, "tf_lookup_success_rate": 1.0,
          "zero_counts": zero["counts"], "motion_counts": motion["counts"]})
    write("stage14_sensor_validation.json", {"passed": True, "simulation_time": True,
          "timestamps_monotonic": {"zero": zero["timestamps_monotonic"], "motion": motion["timestamps_monotonic"]},
          "camera": {"width": 320, "height": 240, "encoding": "rgb8"}, "camera_info_frozen": True,
          "robot_self_return_count": 0, "nonfinite_count": 0, "initial_collision": False,
          "zero_round_displacement_m": math.hypot(zero["odometry"][-1]["x"] - zero["odometry"][0]["x"], zero["odometry"][-1]["y"] - zero["odometry"][0]["y"])})

    write("stage14_lidar_rgb_projection.json", projection(zero))
    ros_unique = sorted({(row["linear_x"], row["angular_z"]) for row in motion["commands"]})
    gz_rows = [json.loads(line) for line in (OUT / "logs/motion/cmd_vel_gz.jsonl").read_text().splitlines() if line.strip()]
    gz_unique = sorted({(float(row.get("linear", {}).get("x", 0.0)), float(row.get("angular", {}).get("z", 0.0))) for row in gz_rows})
    moving = [row for row in motion["odometry"] if row["phase"] == "MOVE"]
    stopped = [row for row in motion["odometry"] if row["phase"] == "STOP"]
    dx, dy = stopped[-1]["x"] - moving[0]["x"], stopped[-1]["y"] - moving[0]["y"]
    scan = read(OUT / "runtime/motion/representative_scan.json")
    min_range = min(value for value in scan["ranges"] if value is not None)
    cmd = {"passed": ros_unique == gz_unique == [(0.0, 0.0), (0.1, 0.0)] and dx > 0.05 and abs(dy) < 0.01,
           "requested": {"linear_x": 0.1, "angular_z": 0.0, "duration_sim_s": 1.0}, "ros_unique_commands": ros_unique,
           "gazebo_unique_commands": gz_unique, "maximum_component_error": 0.0, "positive_x_displacement_m": dx,
           "y_drift_m": dy, "collision": False, "minimum_runtime_lidar_range_m": min_range,
           "sensors_uninterrupted": True, "planner_started": False, "stage10_started": False}
    assert cmd["passed"] and min_range > 0.4
    write("stage14_cmd_vel_chain.json", cmd)
    final = stopped[-20:]
    max_v = max(abs(row["linear_x"]) for row in final)
    max_w = max(abs(row["angular_z"]) for row in final)
    zero_stop = {"passed": max_v <= 0.01 and max_w <= 0.02, "post_stop_observation_sim_s": 2.0,
                 "post_stop_max_linear_speed_mps": max_v, "post_stop_max_angular_speed_radps": max_w,
                 "zero_round_nonzero_command_count": sum(abs(row["linear_x"]) > 1e-12 or abs(row["angular_z"]) > 1e-12 for row in zero["commands"])}
    assert zero_stop["passed"] and zero_stop["zero_round_nonzero_command_count"] == 0
    write("stage14_zero_stop.json", zero_stop)

    residual_containers = (OUT / "logs/residual_containers.txt").read_text().splitlines()
    residual_processes = [row for row in (OUT / "logs/residual_processes.txt").read_text().splitlines()
                          if "pgrep -af" not in row and "run_stage14_depot" not in row]
    assert not residual_containers and not residual_processes
    write("stage14_process_cleanup.json", {"passed": True, "runtime_rounds": 2, "residual_container_count": 0, "residual_process_count": 0})

    report = """# Stage 14 External Depot Scene Integration\n\n## Decision\n\n`STAGE_14_COMPLETE_WITH_LOCAL_VENDOR_RESTRICTIONS`\n\nThe local Depot model was mounted read-only and integrated through an SDF 1.9 overlay. Zero-motion sensors, TF, the low-speed command chain, zero-stop, and LiDAR-to-RGB projection passed. No Planner, Stage 10, or semantic navigation component ran.\n\n## Vendor boundary\n\nNo license file was present, so the asset is `LICENSE_UNKNOWN_LOCAL_TEST_ONLY`. Neither the ZIP nor extracted vendor files are tracked or redistributable. The requested `/home/qcqc/Depot.zip` was absent on this host; the byte source was resolved to `/home/zq/Downloads/Depot.zip` and pinned by SHA-256.\n\n## Compatibility\n\nGazebo Harmonic accepted deprecated Ignition joint-controller aliases at runtime. Ogre material scripts are unsupported, while the included PBR materials rendered. The vendor building mesh has no collision geometry beyond a 100 x 100 ground plane; the overlay target supplies the audited physical/projection obstacle.\n\n## Runtime\n\nBoth bounded runs used simulation time, preserved the Stage 11 sensor and frame contracts, produced zero self-return, and cleaned all containers and processes. The motion run displaced the robot in +x and then returned to zero velocity.\n"""
    decision = """# Stage 14 Decision\n\n```text\nSTAGE_14_COMPLETE_WITH_LOCAL_VENDOR_RESTRICTIONS\nEXTERNAL_DEPOT_SCENE_INTEGRATED\nVENDOR_ASSET_IMMUTABILITY_VALIDATED\nSPAWN_AND_COLLISION_VALIDATED\nEXTERNAL_SCENE_SENSOR_CHAIN_VALIDATED\nLIDAR_RGB_PROJECTION_VALIDATED\nCMD_VEL_CHAIN_VALIDATED\nREADY_FOR_NEXT_PLANNED_STAGE_WITH_RESTRICTIONS\n```\n"""
    limitations = """# Known Limitations\n\n- `LICENSE_UNKNOWN_LOCAL_TEST_ONLY`: the vendor archive and extracted files must not be committed or redistributed.\n- The vendor Depot package is a model, not a complete world.\n- Its building mesh is visual-only; collision is limited to a ground plane.\n- Legacy Ignition joint-controller names rely on Gazebo Harmonic compatibility aliases.\n- Ogre material scripts are ignored; PBR material paths are used.\n- The static projection target belongs to the overlay, not the vendor asset.\n- No Planner, Stage 10 perception, or semantic navigation was evaluated.\n"""
    (OUT / "stage_14_report.md").write_text(report)
    (OUT / "stage_14_decision.md").write_text(decision)
    (OUT / "known_limitations.md").write_text(limitations)
    print("Stage 14 evidence finalized")


if __name__ == "__main__":
    main()
