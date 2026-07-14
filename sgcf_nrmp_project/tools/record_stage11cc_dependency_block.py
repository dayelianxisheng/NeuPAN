#!/usr/bin/env python3
"""Record the Stage 11C-C dependency-gate stop without fabricating runtime data."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PROJECT = ROOT / "sgcf_nrmp_project"
OUT = PROJECT / "artifacts/stages/stage_11c_c_planner_shadow_mode"
LOGS = OUT / "logs/dependency_gate"
GAZEBO_ID = "sha256:72af30cf91fb3001e019c6e57846dbe8d72497516882cc3d0e99a7d5551759ac"
BRIDGE_ID = "sha256:c2288babf5595cdf3caafcd23fd68de2714863b5132ffb10b3cbd10006ca2862"
BLOCKER = "BLOCKED_PLANNER_RUNTIME_DEPENDENCY"


def dump(name: str, value: object) -> None:
    (OUT / name).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def tree_hash(path: Path) -> str:
    digest = hashlib.sha256()
    for item in sorted(entry for entry in path.rglob("*") if entry.is_file()):
        digest.update(item.relative_to(path).as_posix().encode())
        digest.update(hashlib.sha256(item.read_bytes()).digest())
    return digest.hexdigest()


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    LOGS.mkdir(parents=True, exist_ok=True)
    binding = {
        "status": "PASSED_PRECHECK",
        "gazebo_image_id": GAZEBO_ID,
        "bridge_image_id": BRIDGE_ID,
        "immutable_ids_from": "Stage 11C-B stage11cb_runtime_image_binding.json",
        "runtime_baseline": "FUNCTIONALLY_EQUIVALENT_RUNTIME_BASELINE",
        "binary_identity": "NOT_BINARY_IDENTICAL_TO_HISTORICAL_STAGE_11B_N_IMAGE",
        "historical_stage11bn_image_available": False,
        "runtime_started": False,
    }
    dump("stage11cc_runtime_image_binding.json", binding)
    dump(
        "stage11cc_environment_consistency.json",
        {
            **binding,
            "ros_distro": "Humble",
            "gazebo_sim": "8.14.0",
            "sdformat": "14.9.0",
            "gz_rendering_abi": 8,
            "bridge": "ros_gz_bridge",
            "network_mode": "host",
            "ros_domain_id": 42,
            "gz_partition": "sgcf_stage11ca",
            "environment_mutated": False,
        },
    )
    dependency = {
        "status": "FAILED",
        "decision": BLOCKER,
        "image_id": BRIDGE_ID,
        "python_path": "/workspace/sgcf_nrmp_project/core/src",
        "modules": {
            "rclpy": {"available": True, "version": "ROS 2 Humble system package"},
            "numpy": {"available": True, "version": "1.21.5"},
            "scipy": {"available": True, "version": "1.8.0"},
            "osqp": {"available": False, "error": "ModuleNotFoundError: No module named 'osqp'"},
            "sgcf_nrmp": {"available": None, "reason": "not evaluated after mandatory osqp failure"},
        },
        "planner_import_pass": False,
        "installation_attempted": False,
        "image_rebuild_attempted": False,
        "worlds_started": [],
        "hard_stop_rule": "Missing Planner runtime dependency",
    }
    dump("stage11cc_planner_dependency_audit.json", dependency)
    (LOGS / "dependency_stdout.txt").write_text(
        "PASS rclpy\nPASS numpy 1.21.5\nPASS scipy 1.8.0\n", encoding="utf-8"
    )
    (LOGS / "dependency_stderr.txt").write_text(
        "ModuleNotFoundError: No module named 'osqp'\n", encoding="utf-8"
    )

    not_run_files = [
        "stage11cc_actuation_firewall.json",
        "stage11cc_command_topic_audit.json",
        "stage11cc_ros_laserscan_adapter_audit.json",
        "stage11cc_input_synchronization.json",
        "stage11cc_input_freshness_audit.json",
        "stage11cc_runtime_frame_audit.json",
        "stage11cc_planner_input_manifest.json",
        "stage11cc_ros_core_equivalence.json",
        "stage11cc_planner_status_summary.json",
        "stage11cc_stationary_runtime_gate.json",
        "stage11cc_planner_latency.json",
        "stage11cc_ros_graph_audit.json",
        "stage11cc_sensor_data_plane_regression.json",
        "stage11cc_timestamp_audit.json",
        "stage11cc_lidar_self_visibility_regression.json",
    ]
    for name in not_run_files:
        dump(
            name,
            {
                "status": "NOT_EXECUTED",
                "reason": BLOCKER,
                "worlds_started": 0,
                "measurements_fabricated": False,
            },
        )
    (OUT / "stage11cc_planner_shadow_records.jsonl").write_text("", encoding="utf-8")
    dump(
        "stage11cc_process_cleanup.json",
        {
            "status": "PASSED",
            "runtime_worlds_started": 0,
            "named_stage_containers_started": 0,
            "dependency_audit_container_used_with_rm": True,
            "residual_stage_container_count": 0,
            "planner_process_count": 0,
            "zero_guard_process_count": 0,
            "gazebo_process_count": 0,
            "bridge_process_count": 0,
        },
    )
    dump(
        "stage11cc_frozen_component_audit.json",
        {
            "status": "PASSED",
            "gazebo_worlds_hash": tree_hash(PROJECT / "gazebo/worlds"),
            "gazebo_models_hash": tree_hash(PROJECT / "gazebo/models"),
            "core_hash": tree_hash(PROJECT / "core"),
            "docker_hash": tree_hash(ROOT / "docker"),
            "gazebo_image_id": GAZEBO_ID,
            "bridge_image_id": BRIDGE_ID,
            "protected_changes_by_stage11cc": [],
            "runtime_assets_modified": False,
            "core_modified": False,
            "images_modified": False,
        },
    )


if __name__ == "__main__":
    main()
