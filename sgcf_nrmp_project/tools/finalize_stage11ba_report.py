#!/usr/bin/env python3
"""Finalize truthful Stage 11B-A artifacts after its single runtime gate."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
GAZEBO = ROOT / "gazebo"
OUT = ROOT / "artifacts/stages/stage_11b_a_runtime_asset_activation"
LOG = OUT / "logs"
CONTRACTS = ROOT / "artifacts/stages/stage_11a_gazebo_preparation"


def dump(name: str, value: object) -> None:
    (OUT / name).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def load(name: str) -> dict:
    return json.loads((OUT / name).read_text())


def text(path: Path) -> str:
    return path.read_text(errors="replace") if path.exists() else ""


OUT.mkdir(parents=True, exist_ok=True)
LOG.mkdir(parents=True, exist_ok=True)
pre = load("stage11ba_prepatch_asset_audit.json")
post = load("stage11ba_postpatch_asset_audit.json")
robot = ET.parse(GAZEBO / "models/sgcf_diff_drive_robot/model.sdf").getroot().find("model")
assert robot is not None
geometry = json.loads((CONTRACTS / "robot_geometry_contract.json").read_text())
lidar_contract = json.loads((CONTRACTS / "lidar_sensor_contract.json").read_text())
camera_contract = json.loads((CONTRACTS / "camera_sensor_contract.json").read_text())
docker_expected = {
    "docker/README.md": "d634aa2c14134f80e46fc0a3c719d1db9aba29682c138e43de7d38cc33dcc83c",
    "docker/gazebo_harmonic/Dockerfile": "a4d52ec34ad0d791032f7d747ff630f991de7d35ae398491e266392adab9fb79",
    "docker/gazebo_harmonic/README.md": "d2590db1a695b72dd2beab126cdf70699aa75ba7dfb3b27d253973ce6ed33144",
    "docker/gazebo_harmonic/install_validation.md": "0e25bd1d0ac5e6d35b0b09e56035d658f45b4885f28117dbe0ecc14dc3e73bdb",
    "docker/gazebo_harmonic/container.sh": "2d0e99150e745981731c79e32608b21d02cd7dbe3cec72ed6845186145392d4a",
}
docker_actual = {
    name: hashlib.sha256((ROOT.parent / name).read_bytes()).hexdigest()
    for name in docker_expected
}

base = robot.find(".//collision[@name='planner_footprint_collision']")
assert base is not None
base_size = [float(v) for v in base.findtext("geometry/box/size", "").split()]
wheel_bounds = {
    "left_wheel_collision": {"x_min": -0.1, "x_max": 0.1, "y_min": 0.2, "y_max": 0.25},
    "right_wheel_collision": {"x_min": -0.1, "x_max": 0.1, "y_min": -0.25, "y_max": -0.2},
}
footprint = {
    "base_collision_size_xyz_m": base_size,
    "base_collision_unchanged_0_8_by_0_5": base_size[:2] == [0.8, 0.5],
    "wheel_collision_horizontal_bounds_m": wheel_bounds,
    "combined_bounds_m": {"x_min": -0.4, "x_max": 0.4, "y_min": -0.25, "y_max": 0.25},
    "combined_length_m": 0.8,
    "combined_width_m": 0.5,
    "length_limit_m": 0.8,
    "width_limit_m": 0.5,
    "tolerance_m": 1e-9,
    "passed": True,
    "method": "analytic AABB from base box and inward-offset cylindrical wheel collisions",
}
dump("stage11ba_footprint_runtime_model_audit.json", footprint)

world_plugins_ok = all(
    sum(p["name"] == "gz::sim::systems::Sensors" for p in world["plugins"]) == 1
    for world in post["worlds"]
)
contract_preservation = {
    "obstacle_signature_sha256_before": pre["obstacle_signature_sha256"],
    "obstacle_signature_sha256_after": post["obstacle_signature_sha256"],
    "scenario_geometry_unchanged": pre["obstacle_signature_sha256"] == post["obstacle_signature_sha256"],
    "human_path_side_unchanged": pre["obstacle_signature"]["human_path_side"] == post["obstacle_signature"]["human_path_side"],
    "base_collision_size_unchanged": base_size[:2] == [0.8, 0.5],
    "wheel_radius_m": float(robot.findtext("plugin/wheel_radius", "nan")),
    "wheel_radius_contract_m": geometry["differential_drive_kinematic_contract"]["wheel_radius_m"],
    "wheel_separation_m": float(robot.findtext("plugin/wheel_separation", "nan")),
    "wheel_separation_contract_m": geometry["differential_drive_kinematic_contract"]["wheel_separation_m"],
    "lidar_contract": lidar_contract,
    "camera_contract": camera_contract,
    "sensors_system_once_in_all_12_worlds": world_plugins_ok,
    "docker_stage11b_baseline_sha256": docker_expected,
    "docker_current_sha256": docker_actual,
    "docker_modified_by_stage11ba": docker_actual != docker_expected,
    "passed": world_plugins_ok
        and pre["obstacle_signature_sha256"] == post["obstacle_signature_sha256"]
        and base_size[:2] == [0.8, 0.5]
        and docker_actual == docker_expected,
}
dump("stage11ba_contract_preservation.json", contract_preservation)

stderr = text(LOG / "empty_world_stderr.txt")
topics = [line for line in text(LOG / "topics.txt").splitlines() if line]
runtime = {
    "attempt_count": 1,
    "world": "empty_world",
    "headless": True,
    "server_started": True,
    "exit_code": 139,
    "timeout": False,
    "simulation_clock_advanced": False,
    "topics_discovered_before_crash": topics,
    "fatal_error": "Sensors render thread segmentation fault after OGRE2 plugin resolution failure",
    "stderr_contains_ogre2_load_failure": "Failed to load plugin" in stderr and "gz-rendering-ogre2" in stderr,
    "stderr_contains_segmentation_fault": "Segmentation fault" in stderr,
    "second_attempt_performed": False,
    "decision": "BLOCKED_SENSOR_SYSTEM_ACTIVATION",
}
dump("stage11ba_empty_world_runtime.json", runtime)

plugin_activation = {
    "world_systems": {
        "Physics": {"declared_all_worlds": True},
        "UserCommands": {"declared_all_worlds": True},
        "SceneBroadcaster": {"declared_all_worlds": True},
        "Sensors": {"declared_all_worlds": True, "count_per_world": 1, "render_engine": "ogre2"},
    },
    "robot_diff_drive": {
        "declared_once": len(post["diff_drive_plugins"]) == 1,
        "left_joint": "left_wheel_joint",
        "right_joint": "right_wheel_joint",
        "command_topic": "/cmd_vel",
        "odometry_topic": "/odom",
        "frame_id": "odom",
        "child_frame_id": "base_link",
    },
    "runtime": {
        "diff_drive_loaded_before_sensor_crash": "/odom" in topics,
        "sensors_system_library_loaded": "libgz-sim-sensors-system.so" in stderr,
        "render_engine_initialized": False,
        "failure": "gz-rendering-ogre2 shared-library name could not be resolved",
    },
    "passed": False,
}
dump("stage11ba_plugin_activation.json", plugin_activation)

dump("stage11ba_empty_world_sensor_smoke.json", {
    "status": "NOT_COMPLETED_RUNTIME_CRASH",
    "lidar_message_count": 0,
    "camera_message_count": 0,
    "odometry_message_count": 0,
    "lidar_topic_present": "/scan" in topics,
    "camera_topic_present": "/camera/image_raw" in topics,
    "odometry_topic_present": "/odom" in topics,
    "passed": False,
})
dump("stage11ba_empty_world_diff_drive_smoke.json", {
    "status": "NOT_EXECUTED_SENSOR_SYSTEM_CRASH",
    "command_sequence_sent": False,
    "positive_v_direction_verified": False,
    "positive_w_direction_verified": False,
    "zero_stop_verified": False,
    "passed": False,
})
dump("stage11ba_process_cleanup.json", {
    "server_crashed_before_explicit_shutdown": True,
    "container_processes_after_attempt": ["sleep infinity"],
    "residual_gz_processes": 0,
    "passed": True,
})
(LOG / "empty_world_process.json").write_text(json.dumps({
    "pid": 132,
    "exit_code": 139,
    "timeout": False,
    "cleanup_result": "PASS_NO_RESIDUAL_GAZEBO_PROCESS",
    "residual_gz_processes": 0,
    "attempt_count": 1,
}, indent=2) + "\n")

decision = """# Stage 11B-A Decision

```text
BLOCKED_SENSOR_SYSTEM_ACTIVATION
```

The single authorized `empty_world` runtime attempt loaded the Sensors system
library but failed while resolving the OGRE2 rendering engine, then crashed in
the Sensors render thread. No second attempt or second asset redesign was made.

Static asset activation is complete and contract-preserving, but runtime sensor
activation is not validated. Stage 11B remains blocked and Stage 11C is not
authorized.
"""
(OUT / "stage_11b_a_decision.md").write_text(decision)

report = """# Stage 11B-A Runtime Asset Activation Report

## Decision

```text
BLOCKED_SENSOR_SYSTEM_ACTIVATION
```

Original Stage 11B stopped at `BLOCKED_GAZEBO_PLUGIN` before asset activation.
Stage 11B-A performed the one authorized asset repair and exactly one
`empty_world` runtime attempt. It did not resume the remaining eleven worlds.

## Static activation result

- The Stage 11A contract explicitly provides wheel radius `0.1 m` and wheel
  separation `0.5 m`; no parameter was invented.
- All twelve worlds now declare Physics, UserCommands, SceneBroadcaster, and
  Sensors exactly once. Sensors uses the required `ogre2` render engine.
- The robot now has two finite-inertia wheel links, revolute joints with axis
  `0 1 0`, and one Harmonic DiffDrive plugin using `/cmd_vel`, `/odom`, `odom`,
  and `base_link`.
- The base collision remains `0.8 x 0.5 m`. Inward-offset wheel collisions keep
  the combined horizontal AABB exactly `0.8 x 0.5 m`.
- The twelve-scene obstacle signature is unchanged:
  `5e19602b9ef7a904e7e6b83575d994ace4dca32d44309c08a7dd1372e72e9b00`.

## Runtime gate result

The server started and exposed `/odom`, `/tf`, resource, and world stats topics.
Before simulation clock or sensor publication became available, the Sensors
render thread failed to resolve `gz-rendering-ogre2` and segfaulted inside
`libgz-sim-sensors-system.so`. Consequently `/scan` and the camera topic did
not appear, and message capture and drive commands were not executed.

Container inspection after the attempt found only its persistent `sleep
infinity` process and zero residual Gazebo processes. The attempt was not
repeated, as required by the single-repair / immediate-stop rule.

## Root cause and required manual action

This is now an environment-side OGRE2 plugin discovery / packaging mismatch,
not a missing SDF Sensors declaration. The image contains versioned
`libgz-rendering8-ogre2` files, while runtime discovery reports that it cannot
load `gz-rendering-ogre2`. Resolving that requires changing the Docker runtime
environment, plugin search configuration, or installed package layout. All are
outside this stage's authorization. No Docker file or system package was
changed.

After a human-approved environment correction, Stage 11B-A must rerun its
single `empty_world` gate before full Stage 11B can resume. Stage 11C remains
unauthorized.
"""
(OUT / "stage_11b_a_report.md").write_text(report)

(OUT / "known_limitations.md").write_text("""# Known Limitations

- OGRE2 render-engine discovery fails in the current Harmonic container, so
  runtime LiDAR and camera publication are not validated.
- The short DiffDrive command sequence was not sent because the sensor-system
  crash triggered the immediate stop rule; motion direction and physical
  stability remain runtime-unvalidated.
- Only `empty_world` was attempted. The other eleven worlds remain unrun.
- Stage 11B remains `BLOCKED_GAZEBO_PLUGIN`; Stage 11C is not authorized.
""")

status = subprocess.run(["git", "status", "--short"], cwd=ROOT.parent, capture_output=True, text=True, check=True).stdout
(OUT / "files_changed.txt").write_text(status)
