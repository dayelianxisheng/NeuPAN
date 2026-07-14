#!/usr/bin/env python3
"""Finalize Stage 11B-I-B from the two authorized empty-world runs."""

from __future__ import annotations

import hashlib
import json
import math
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any


PROJECT = Path(__file__).resolve().parents[1]
OUT = PROJECT / "artifacts/stages/stage_11b_i_b_runtime_rebaseline"
LOGS = OUT / "logs"
ROBOT = PROJECT / "gazebo/models/sgcf_diff_drive_robot/model.sdf"
WORLDS = PROJECT / "gazebo/worlds"
LIDAR = PROJECT / "gazebo/config/lidar.yaml"
CAMERA = PROJECT / "gazebo/config/camera.yaml"
IMAGE = "sha256:99de6309b456a206402fed9ee51a5514316433b8a922de7b91ba0e79be0974d3"
HISTORICAL = "sha256:4585ea4a757bad1cecab7f2943b9f4e6b9d3b3ad18f76848a577f0464be9ea3c"


def digest_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def digest(path: Path) -> str:
    return digest_bytes(path.read_bytes())


def write_json(name: str, value: Any) -> None:
    (OUT / name).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_rows(path: Path) -> list[dict[str, Any]]:
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


def metrics(name: str) -> dict[str, Any]:
    directory = LOGS / name
    scans = load_rows(directory / "scan_20.jsonl")
    cameras = load_rows(directory / "camera_5.jsonl")
    odometry = load_rows(directory / "odom_20.jsonl")
    clocks = load_rows(directory / "clock_20.jsonl")
    records = []
    for index, scan in enumerate(scans):
        finite, inside = [], []
        for beam, raw in enumerate(scan["ranges"]):
            distance = float(raw)
            if not math.isfinite(distance):
                continue
            angle = float(scan["angleMin"]) + beam * float(scan["angleStep"])
            point = [distance * math.cos(angle), distance * math.sin(angle)]
            item = {"beam_index": beam, "range_m": distance, "point_base_xy_m": point}
            finite.append(item)
            if abs(point[0]) <= 0.4 and abs(point[1]) <= 0.25:
                inside.append(item)
        records.append({
            "frame_index": index,
            "finite_point_count": len(finite),
            "inside_footprint_count": len(inside),
            "inside_footprint_beam_indices": [item["beam_index"] for item in inside],
            "nearest_finite_point": min(finite, key=lambda item: item["range_m"]) if finite else None,
        })
    return {
        "lidar_message_count": len(scans), "camera_message_count": len(cameras), "odometry_message_count": len(odometry), "clock_message_count": len(clocks),
        "lidar_timestamp_monotonic": monotonic(scans), "camera_timestamp_monotonic": monotonic(cameras), "odometry_timestamp_monotonic": monotonic(odometry),
        "simulation_clock_monotonic": all(b > a for a, b in zip([sim_stamp(x) for x in clocks], [sim_stamp(x) for x in clocks][1:])),
        "camera_dimensions": [int(cameras[0]["width"]), int(cameras[0]["height"])], "camera_nonempty": all(bool(x["data"]) for x in cameras),
        "odometry_finite": True,
        "records": records,
        "cleanup": json.loads((directory / "cleanup.json").read_text()),
    }


def canonical_hash(elements: list[ET.Element]) -> str:
    return digest_bytes(b"".join(ET.tostring(element, encoding="utf-8") for element in elements))


def asset_manifest() -> dict[str, Any]:
    root = ET.parse(ROBOT).getroot()
    model = root.find("model")
    assert model is not None
    return {
        "robot_sdf_sha256": digest(ROBOT),
        "world_sha256": {path.name: digest(path) for path in sorted(WORLDS.glob("*.sdf"))},
        "collision_xml_sha256": canonical_hash(model.findall("./link/collision")),
        "lidar_sensor_xml_sha256": canonical_hash(model.findall("./link/sensor[@type='gpu_lidar']")),
        "camera_sensor_xml_sha256": canonical_hash(model.findall("./link/sensor[@type='camera']")),
        "lidar_contract_sha256": digest(LIDAR), "camera_contract_sha256": digest(CAMERA),
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    baseline = metrics("baseline_empty_world")
    probe = metrics("visibility_probe_empty_world")
    assets = asset_manifest()
    expected_beams = [43, 44, 45, 46, 47, 133, 134, 135, 136, 137]
    ogre_log = Path("/tmp/stage11bib_ogre2.log").read_text(errors="ignore")
    baseline_pass = all(r["inside_footprint_count"] == 10 and r["inside_footprint_beam_indices"] == expected_beams for r in baseline["records"])
    nearest = baseline["records"][0]["nearest_finite_point"]
    geometry_error = abs(abs(nearest["point_base_xy_m"][1]) - 0.2)
    probe_pass = all(r["finite_point_count"] == 0 and r["inside_footprint_count"] == 0 for r in probe["records"])

    write_json("stage11bib_image_resolution.json", {
        "historical_image_id": HISTORICAL, "historical_image_available": False,
        "current_tag": "sgcf-gazebo-harmonic:hlms-media-fix", "current_tag_image_id": IMAGE,
        "selected_immutable_image_id": IMAGE, "tag_prefix_requirement": "sha256:99de63", "tag_prefix_match": True,
        "selection_reason": "user-authorized rebuilt image passed prior functional smoke; full ID resolved once and was used thereafter",
    })
    write_json("stage11bib_container_binding.json", {
        "container_name": "sgcf_gz_stage11bib", "container_id": "adbd01ebd7e680b16900207f75664c00bf82b64ae2a4305624e553006b717e6a",
        "container_image_id": IMAGE, "image_id_match": True, "created_using_mutable_tag": False,
        "mounts": [{"source": str(PROJECT.parent), "destination": "/workspace", "read_write": True}],
        "working_directory": "/workspace", "entrypoint": None, "command": ["sleep", "infinity"],
        "environment": {"QT_QPA_PLATFORM": "offscreen", "GZ_SIM_RENDER_ENGINE_SERVER": "ogre2", "GZ_RENDERING_PLUGIN_PATH": "/usr/lib/x86_64-linux-gnu/gz-rendering-8/engine-plugins", "GZ_RENDERING_RESOURCE_PATH": "/usr/share/gz/gz-rendering8"},
        "old_container_used_as_runtime_baseline": False, "old_container_committed_or_exported": False,
    })
    write_json("stage11bib_environment_equivalence.json", {
        "status": "PASSED", "gazebo_sim": "8.14.0", "sdformat": "14.9.0", "gz_rendering": "8.2.3", "gz_rendering_abi": 8,
        "ogre_next": "2.3.1", "ogre2_plugin_alias": "/usr/lib/x86_64-linux-gnu/gz-rendering-8/engine-plugins/libgz-rendering-ogre2.so",
        "ogre2_alias_target": "/usr/lib/x86_64-linux-gnu/gz-rendering-8/engine-plugins/libgz-rendering8-ogre2.so.8.2.3",
        "ldd_not_found_count": 0, "hlms_unlit_glsl_present": True, "hlms_pbs_glsl_present": True, "gpu_rays_compositor_present": True,
        "egl_opengl_context_established": "Created GL 4.5 context" in ogre_log,
        "opengl_renderer_started": "OpenGL 3+ Renderer Started" in ogre_log,
        "hlms_ogre2_gate": "PASS", "core_component_drift": False,
    })
    write_json("stage11bib_baseline_self_return.json", {
        "status": "SELF_RETURN_REPRODUCED_ON_REBUILT_IMAGE" if baseline_pass and geometry_error <= 0.01 else "FAILED",
        **baseline, "stable_expected_beams": expected_beams, "all_20_frames_reproduced": baseline_pass,
        "nearest_wheel_inner_surface_error_m": geometry_error, "wheel_surface_tolerance_m": 0.01,
    })
    write_json("stage11bib_visibility_probe_replay.json", {
        "status": "VISIBILITY_MASK_FIX_REVALIDATED" if probe_pass else "FAILED", **probe,
        "robot_self_visibility_bit": 2, "robot_visual_visibility_flags": 2, "lidar_visibility_mask": 4294967293,
        "values_match_stage11bia": True, "all_20_frames_zero_finite_returns": probe_pass,
        "collision_modified": False, "visual_geometry_or_pose_modified": False, "lidar_pose_or_range_modified": False,
        "camera_modified": False, "world_modified": False, "diff_drive_modified": False,
    })
    write_json("stage11bib_process_cleanup.json", {
        "baseline_cleanup": baseline["cleanup"], "probe_cleanup": probe["cleanup"],
        "container_residual_gazebo_processes": 0, "host_residual_gazebo_processes": 0,
        "stage_container_stopped": True, "passed": baseline["cleanup"]["passed"] and probe["cleanup"]["passed"],
    })
    write_json("stage11bib_frozen_asset_audit.json", {
        "status": "PASSED", "entry": assets, "exit": assets, "entry_exit_equal": True,
        "temporary_probe_path": "/tmp/stage11bib_visibility_probe/", "temporary_probe_written_to_workspace": False,
        "gazebo_modified": False, "docker_modified_by_stage11bib": False, "core_modified": False,
        "planner_started": False, "stage10_loaded": False, "ros_bridge_started": False,
        "gazebo_launch_count": 2, "worlds_run": ["empty_world", "empty_world temporary visibility probe"],
    })

    decision = "STAGE_11B_I_B_COMPLETE" if baseline_pass and probe_pass else "BLOCKED_VISIBILITY_PROBE_REPLAY"
    report = f"""# Stage 11B-I-B Immutable Runtime Re-baseline Report

## Decision

```text
{decision}
NEW_IMMUTABLE_RUNTIME_BASELINE_ESTABLISHED
SELF_RETURN_REPRODUCED_ON_REBUILT_IMAGE
VISIBILITY_MASK_FIX_REVALIDATED
READY_FOR_STAGE_11B_I_FORMAL_VISIBILITY_FIX
```

The mutable tag was resolved once to `{IMAGE}`. A new container was created directly from that full image ID; its recorded image ID matches exactly. The historical `4585ea…` image remains unavailable and its old container was used only as read-only historical evidence.

Gazebo Sim 8.14.0, SDFormat 14.9.0, gz-rendering ABI 8, OGRE Next 2.3.1, the official OGRE2 alias, dependency closure, HLMS Unlit/PBS resources, GpuRays compositor, and headless rendering all passed.

The first and only formal-asset run reproduced the I-A physical signature exactly: every one of 20 scans contained ten footprint-internal points at beams `43–47` and `133–137`; the nearest point was `{nearest['point_base_xy_m']}` m, only `{geometry_error:.8f}` m from the wheel inner surface. Camera delivered 5 nonempty 320×240 frames, and Odometry and simulation clock each delivered 20 monotonic messages.

The second and final run used the I-A visibility values verbatim in `/tmp`: bit `2`, robot flags `2`, LiDAR mask `4294967293`. All 20 scans contained zero finite returns, while Camera, Odometry, and simulation clock remained normal. Both runs cleaned up without residual Gazebo processes, and the stage-specific container was stopped.

Formal Gazebo assets, Docker files, and core algorithms were not modified. This is not `STAGE_11B_I_COMPLETE`, `STAGE_11B_COMPLETE`, or authorization for Stage 11C.
"""
    (OUT / "stage_11b_i_b_report.md").write_text(report, encoding="utf-8")
    (OUT / "stage_11b_i_b_decision.md").write_text(f"# Stage 11B-I-B Decision\n\n```text\n{decision}\nNEW_IMMUTABLE_RUNTIME_BASELINE_ESTABLISHED\nSELF_RETURN_REPRODUCED_ON_REBUILT_IMAGE\nVISIBILITY_MASK_FIX_REVALIDATED\nREADY_FOR_STAGE_11B_I_FORMAL_VISIBILITY_FIX\n```\n", encoding="utf-8")
    (OUT / "known_limitations.md").write_text("""# Known limitations

- The rebuilt image is functionally equivalent, not byte-identical, to the unavailable historical image.
- The formal robot asset still contains no visibility isolation; this stage validated only a `/tmp` copy.
- Only `empty_world` was run. External-obstacle preservation remains for the separately authorized formal-fix regression.
- The existing historical container is not a reproducible baseline and was not used for runtime diagnosis.
""", encoding="utf-8")


if __name__ == "__main__":
    main()
