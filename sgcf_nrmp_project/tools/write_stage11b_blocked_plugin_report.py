#!/usr/bin/env python3
"""Write the evidence-preserving Stage 11B plugin-block report."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "sgcf_nrmp_project/artifacts/stages/stage_11b_gazebo_headless_smoke"
LOGS = OUT / "logs"
SCENES = [
    "empty_world",
    "single_static_obstacle",
    "static_corridor",
    "narrow_passage",
    "human_path_center",
    "human_path_side",
    "vehicle_path",
    "robot_obstacle",
    "semantic_infeasible",
    "initial_collision",
    "rgb_dropout_contract",
    "outdated_rgb_contract",
]
STOP = "BLOCKED_GAZEBO_PLUGIN"


def write_json(name: str, value: object) -> None:
    (OUT / name).write_text(json.dumps(value, indent=2) + "\n")


def unavailable(scope: str) -> dict[str, object]:
    return {
        "status": "NOT_EXECUTED_AFTER_IMMEDIATE_STOP",
        "scope": scope,
        "stop_reason": STOP,
        "fabricated_runtime_data": False,
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    LOGS.mkdir(parents=True, exist_ok=True)

    environment = {
        "decision": STOP,
        "audit_location": "Docker container sgcf_gz_harmonic",
        "gz_executable": "/usr/bin/gz",
        "gz_sim_available": True,
        "gazebo_distribution": "Harmonic",
        "gazebo_sim_version": "8.14.0",
        "sdformat_version": "14.9.0",
        "headless_server_available": True,
        "sdf_1_9_empty_world_parse_and_start": True,
        "available_commands": ["gui", "model", "msg", "sdf", "sim", "topic", "service", "log", "param"],
        "physics_engine": "DART via gz-physics7-dartsim",
        "environment_gate_passed": True,
        "runtime_gate_failure": "Sensors and diff-drive runtime systems are not declared/active in the Stage 11A assets.",
    }
    write_json("stage11b_environment_audit.json", environment)
    write_json("stage11b_container_environment.json", {
        "container_name": "sgcf_gz_harmonic",
        "container_status_during_audit": "running",
        "image_tag": "sgcf-gazebo-harmonic:local",
        "image_id": "sha256:add3df817107a929749e1ed78b3a6bd674e47850527c7f790694915d078f81db",
        "project_mount": "/home/qcqc/resource/code/eai/NeuPAN:/workspace",
        "working_directory": "/workspace",
        "GZ_SIM_RESOURCE_PATH": "/workspace/sgcf_nrmp_project/gazebo/models:/workspace/sgcf_nrmp_project/gazebo",
        "GZ_SIM_SYSTEM_PLUGIN_PATH": None,
        "GZ_SIM_PHYSICS_ENGINE_PATH": "/usr/lib/x86_64-linux-gnu/gz-physics-7/engine-plugins",
        "gui_started": False,
        "planner_started": False,
        "ros_bridge_started": False,
        "stage10_model_loaded": False,
    })

    plugins = [
        {"function": "physics system", "runtime_evidence": "world advanced and /world/empty_world/control exists", "load_success": True},
        {"function": "scene broadcaster", "runtime_evidence": "/world/empty_world/scene/info and pose/info topics exist", "load_success": True},
        {"function": "user commands", "runtime_evidence": "create/remove/set_pose services exist", "load_success": True},
        {"function": "sensors system", "runtime_evidence": "no /scan or camera topic; no Sensors system declaration in world", "load_success": False, "critical": True},
        {"function": "diff drive", "runtime_evidence": "no command/odometry topic; no DiffDrive plugin or wheel joints in robot SDF", "load_success": False, "critical": True},
        {"function": "odometry", "runtime_evidence": "no odometry topic", "load_success": False, "critical": True},
        {"function": "LiDAR", "runtime_evidence": "gpu_lidar SDF element present but no runtime publisher", "load_success": False, "critical": True},
        {"function": "RGB camera", "runtime_evidence": "camera SDF element present but no runtime publisher", "load_success": False, "critical": True},
    ]
    write_json("stage11b_plugin_inventory.json", {"decision": STOP, "plugins": plugins})
    write_json("stage11b_resource_resolution.json", {
        "world": "empty_world",
        "world_file": "/workspace/sgcf_nrmp_project/gazebo/worlds/empty_world.sdf",
        "sdf_parse_success": True,
        "model_uri_resolution_success": True,
        "physics_engine_resolution_success": True,
        "fatal_resource_errors": [],
        "sensor_runtime_system_resolution_success": False,
        "diff_drive_runtime_resolution_success": False,
        "decision": STOP,
    })

    matrix = []
    for scene in SCENES:
        ran = scene == "empty_world"
        matrix.append({
            "scene_id": scene,
            "world_file": f"sgcf_nrmp_project/gazebo/worlds/{scene}.sdf",
            "runtime_started": ran,
            "sdf_parse_result": "PASS" if ran else "NOT_RUN_STOP_CONDITION",
            "server_startup_result": "PASS" if ran else "NOT_RUN_STOP_CONDITION",
            "simulation_clock_topic_present": True if ran else None,
            "expected_entities_present": "NOT_SAMPLED" if ran else "NOT_RUN_STOP_CONDITION",
            "lidar_sensor_topic_present": False if ran else None,
            "camera_sensor_topic_present": False if ran else None,
            "diff_drive_plugin_active": False if ran else None,
            "fatal_errors": [] if ran else None,
            "warnings": ["Critical sensor and diff-drive runtime systems inactive"] if ran else None,
            "exit_code": 0 if ran else None,
            "timeout": False if ran else None,
            "clean_shutdown": True if ran else None,
            "residual_gz_process": False if ran else None,
            "status": STOP if ran else "NOT_RUN_IMMEDIATE_STOP",
        })
    write_json("stage11b_world_runtime_matrix.json", {
        "required_world_count": 12,
        "started_world_count": 1,
        "not_started_world_count": 11,
        "decision": STOP,
        "worlds": matrix,
    })

    write_json("stage11b_runtime_entity_audit.json", {
        "status": "PARTIAL_EMPTY_WORLD_ONLY",
        "pose_and_scene_topics_present": True,
        "entity_payload_sampled": False,
        "reason": "Immediate stop followed missing sensor runtime topics.",
        "decision": STOP,
    })
    write_json("stage11b_runtime_pose_consistency.json", unavailable("runtime entity pose comparison"))
    write_json("stage11b_sim_time_audit.json", {
        "status": "PARTIAL_TOPIC_DISCOVERY_ONLY",
        "clock_topics": ["/clock", "/world/empty_world/clock"],
        "stats_topics": ["/stats", "/world/empty_world/stats"],
        "timestamps_sampled": 0,
        "monotonicity_evaluated": False,
        "reason": "Immediate stop followed missing sensor runtime topics.",
        "decision": STOP,
    })
    write_json("stage11b_lidar_runtime_metrics.json", {
        "status": "BLOCKED_NO_RUNTIME_TOPIC",
        "expected_sdf_topic": "/scan",
        "auto_discovered": False,
        "messages_collected": 0,
        "decision": STOP,
    })
    write_json("stage11b_lidar_adapter_metrics.json", unavailable("runtime scan adapter validation"))
    write_json("stage11b_runtime_clearance_consistency.json", unavailable("runtime LiDAR exact-clearance comparison"))
    write_json("stage11b_camera_runtime_metrics.json", {
        "status": "BLOCKED_NO_RUNTIME_TOPIC",
        "expected_sdf_topic": "/camera/image_raw",
        "auto_discovered": False,
        "messages_collected": 0,
        "decision": STOP,
    })
    write_json("stage11b_camera_stage07_consistency.json", unavailable("runtime camera and Stage 07 comparison"))
    write_json("stage11b_sensor_rate_metrics.json", unavailable("LiDAR, camera and odometry rate measurement"))
    write_json("stage11b_runtime_frame_audit.json", {
        **unavailable("runtime frame audit"),
        "static_contract_unchanged": True,
        "runtime_sensor_parent_evidence_available": False,
    })
    write_json("stage11b_diff_drive_smoke.json", {
        "status": "BLOCKED_DIFF_DRIVE_NOT_ACTIVE",
        "commands_sent": 0,
        "unsafe_motion_attempted": False,
        "decision": STOP,
    })
    write_json("stage11b_odometry_consistency.json", unavailable("runtime odometry comparison"))
    write_json("stage11b_command_safety_runtime.json", unavailable("runtime command publisher safety mapping"))
    write_json("stage11b_oracle_semantic_runtime.json", unavailable("Oracle semantic runtime sidecar"))
    write_json("stage11b_r1_runtime_contract.json", unavailable("RGB dropout and outdated RGB runtime adapter contracts"))
    write_json("stage11b_human_path_side_runtime_audit.json", {
        **unavailable("human_path_side runtime audit"),
        "frozen_stage09b_result": {
            "P0": "exact clearance 0.24652 m < 0.25 m; geometry recheck rejection",
            "P1_P2": "OSQP_MAX_ITER_REACHED; iterations 10000",
        },
        "planner_run_in_stage11b": False,
        "claim_resolved": False,
    })
    write_json("stage11b_runtime_startup_latency.json", {
        "status": "INSUFFICIENT_SAMPLES_AFTER_IMMEDIATE_STOP",
        "empty_world_single_probe": {"server_ready_wall_s_approx": 4.0, "statistical_p95_claimed": False},
        "required_repeated_scenes_completed": 0,
        "decision": STOP,
    })

    for scene in SCENES:
        directory = LOGS / scene
        directory.mkdir(parents=True, exist_ok=True)
        if scene == "empty_world":
            (directory / "stdout.log").write_text("")
            (directory / "stderr.log").write_text("")
            (directory / "exit_code.txt").write_text("0\n")
            (directory / "timeout_status.txt").write_text("false\n")
            (directory / "process_cleanup.txt").write_text("clean shutdown; no residual gz sim server\n")
            (directory / "runtime_probe.txt").write_text(
                "PID=75\n"
                "topics=/clock,/gazebo/resource_paths,/stats,/world/empty_world/clock,"
                "/world/empty_world/dynamic_pose/info,/world/empty_world/pose/info,"
                "/world/empty_world/scene/deletion,/world/empty_world/scene/info,"
                "/world/empty_world/state,/world/empty_world/stats\n"
                "sensor_topics=/scan absent; camera absent; odometry absent\n"
                "service_families=server_control,world control,create,remove,set_pose,scene info\n"
            )
        else:
            message = f"NOT RUN: immediate stop after {STOP} in empty_world\n"
            (directory / "stdout.log").write_text(message)
            (directory / "stderr.log").write_text(message)
            (directory / "exit_code.txt").write_text("NOT_RUN\n")
            (directory / "timeout_status.txt").write_text("NOT_RUN\n")
            (directory / "process_cleanup.txt").write_text("NOT_APPLICABLE_PROCESS_NOT_STARTED\n")

    (OUT / "stage11b_gazebo_version.md").write_text(
        "# Stage 11B Gazebo Version\n\n"
        "Docker runtime audit: Gazebo Harmonic / Gazebo Sim 8.14.0 and "
        "SDFormat 14.9.0. `gz sim`, `topic`, `service`, and `model` are available. "
        "The environment/version gate passed; Stage 11B is blocked later by inactive "
        "sensor and diff-drive runtime systems.\n"
    )
    (OUT / "stage_11b_decision.md").write_text(
        "# Stage 11B Decision\n\n```text\nBLOCKED_GAZEBO_PLUGIN\n```\n\n"
        "The Harmonic Docker runtime and SDF 1.9 empty-world load pass, but the "
        "Stage 11A assets do not activate the Sensors system or DiffDrive system. "
        "No LiDAR, camera, odometry, or command transport topic exists. The immediate "
        "stop rule was applied before the remaining eleven worlds. Stage 11C is not authorized.\n"
    )
    (OUT / "stage_11b_report.md").write_text(
        "# Stage 11B Harmonic Headless Runtime Report\n\n"
        "## Decision\n\n```text\nBLOCKED_GAZEBO_PLUGIN\n```\n\n"
        "## Environment\n\nThe authorized Docker environment passed its hard gate: Gazebo Harmonic "
        "8.14.0, SDFormat 14.9.0, headless `gz sim`, DART physics, and the required "
        "CLI commands are available. `empty_world.sdf` parsed and started without a "
        "fatal resource or physics error.\n\n"
        "## Blocking runtime evidence\n\nAfter four wall-clock seconds of running `empty_world`, automatic topic "
        "discovery found clock, stats, pose, scene, and state topics, but no `/scan`, "
        "camera, odometry, or command topic. User-command and scene services were present. "
        "The robot SDF contains sensor elements but no active Sensors system; it also has "
        "no DiffDrive plugin or wheel joints. This is a critical plugin-chain block.\n\n"
        "## Stop scope\n\nOnly `empty_world` was started. The other eleven worlds, sensor message capture, "
        "runtime adapter/clearance/frame audits, diff-drive motion, safety publisher, "
        "Oracle sidecar, R1 contracts, startup repetitions, tests, and visualizations were "
        "not executed. Their JSON records explicitly say `NOT_EXECUTED`; no values were "
        "fabricated. The server exited with code 0 and no residual Gazebo process.\n\n"
        "## Boundaries preserved\n\nNo Docker file, Planner, Exact Geometry, Semantic Margin, Stage 10 module, robot "
        "footprint, sensor contract, frame contract, or scenario geometry was modified. "
        "No GUI, Planner, ROS bridge, PointPainting, or Stage 10 inference was started.\n\n"
        "## Required next action\n\nA separately authorized asset repair must define the existing Harmonic Sensors "
        "system and a physically consistent differential-drive model/plugin while preserving "
        "the 0.8 x 0.5 m collision footprint and all frozen contracts. Stage 11B must then restart "
        "from the twelve-world matrix; Stage 11C cannot begin.\n"
    )
    (OUT / "known_limitations.md").write_text(
        "# Known Limitations\n\n"
        "- Stage 11A sensor elements have no active Harmonic Sensors system at runtime.\n"
        "- The robot asset has no DiffDrive system or wheel joints; odometry and command topics are absent.\n"
        "- Only `empty_world` was started before the mandatory stop.\n"
        "- Runtime LiDAR, camera, frames, clearance, rates, motion, and sidecar contracts remain unvalidated.\n"
        "- `human_path_side` retains the frozen Stage 09B limitation and was not run.\n"
    )
    (OUT / "test_output.txt").write_text(
        "Environment CLI checks: PASS\n"
        "Gazebo Sim version: 8.14.0\nSDFormat version: 14.9.0\n"
        "empty_world SDF/server/physics start: PASS\n"
        "runtime LiDAR topic: FAIL (absent)\nruntime camera topic: FAIL (absent)\n"
        "runtime diff-drive/odometry topics: FAIL (absent)\n"
        "process cleanup: PASS\nDECISION: BLOCKED_GAZEBO_PLUGIN\n"
        "unittest/compileall/full matrix: NOT RUN after immediate stop\n"
    )

    baseline = {
        "stage11b_start_git_status": [
            " M docker/README.md",
            "?? docker/gazebo_harmonic/",
            "?? sgcf_nrmp_project/artifacts/stages/stage_11b_gazebo_headless_smoke/",
        ],
        "docker_diff_sha256": "f0853935e7e97daf9ae95f1bae043245fa9c4ab1fda00950fe7da215176ebe4c",
        "docker_file_sha256": {
            "docker/README.md": "d634aa2c14134f80e46fc0a3c719d1db9aba29682c138e43de7d38cc33dcc83c",
            "docker/gazebo_harmonic/Dockerfile": "a4d52ec34ad0d791032f7d747ff630f991de7d35ae398491e266392adab9fb79",
            "docker/gazebo_harmonic/README.md": "d2590db1a695b72dd2beab126cdf70699aa75ba7dfb3b27d253973ce6ed33144",
            "docker/gazebo_harmonic/install_validation.md": "0e25bd1d0ac5e6d35b0b09e56035d658f45b4885f28117dbe0ecc14dc3e73bdb",
            "docker/gazebo_harmonic/container.sh": "2d0e99150e745981731c79e32608b21d02cd7dbe3cec72ed6845186145392d4a",
        },
        "docker_modified_during_stage11b": False,
    }
    write_json("stage11b_preflight_baseline.json", baseline)

    changed = [str(path.relative_to(ROOT)) for path in sorted(OUT.rglob("*")) if path.is_file()]
    changed.append("sgcf_nrmp_project/tools/write_stage11b_blocked_plugin_report.py")
    (OUT / "files_changed.txt").write_text("\n".join(sorted(set(changed))) + "\n")


if __name__ == "__main__":
    main()
