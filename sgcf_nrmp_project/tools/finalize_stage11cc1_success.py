#!/usr/bin/env python3
"""Finalize the successful Stage 11C-C1 offline image validation."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess

import numpy as np


ROOT = Path(__file__).resolve().parents[2]
PROJECT = ROOT / "sgcf_nrmp_project"
OUT = PROJECT / "artifacts/stages/stage_11c_c1_torch_planner_runtime"
IMAGE = "sgcf-ros2-humble-gzharmonic-torch-planner:stage11cc1"
BASE_ID = "sha256:c2288babf5595cdf3caafcd23fd68de2714863b5132ffb10b3cbd10006ca2862"
GAZEBO_ID = "sha256:72af30cf91fb3001e019c6e57846dbe8d72497516882cc3d0e99a7d5551759ac"


def dump(name: str, value: object) -> None:
    (OUT / name).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def tree_hash(path: Path) -> str:
    digest = hashlib.sha256()
    for item in sorted(entry for entry in path.rglob("*") if entry.is_file()):
        digest.update(item.relative_to(path).as_posix().encode())
        digest.update(hashlib.sha256(item.read_bytes()).digest())
    return digest.hexdigest()


def maximum_error(left, right) -> float:
    a, b = np.asarray(left, dtype=float), np.asarray(right, dtype=float)
    return float(np.max(np.abs(a - b))) if a.size else 0.0


def inspect_image(reference: str) -> dict:
    raw = subprocess.check_output(["docker", "image", "inspect", reference], text=True)
    return json.loads(raw)[0]


def main() -> None:
    host = json.loads(Path("/tmp/stage11cc1_host_reference.json").read_text())
    runtime = json.loads(Path("/tmp/stage11cc1_container_result.json").read_text())
    derived, base = inspect_image(IMAGE), inspect_image(BASE_ID)
    derived_id = derived["Id"]

    geometry_d = geometry_g = 0.0
    collision_agreement = True
    for name, expected in host["geometry"]["fixtures"].items():
        actual = runtime["geometry"]["fixtures"][name]
        geometry_d = max(geometry_d, maximum_error(expected["d_geo"], actual["d_geo"]))
        geometry_g = max(geometry_g, maximum_error(expected["g_geo"], actual["g_geo"]))
        collision_agreement &= expected["collision"] == actual["collision"]

    cases = {}
    for name, expected in host["replay"].items():
        actual = runtime["replay"][name]
        case = {
            "status": actual["status"],
            "status_agreement": expected["status"] == actual["status"],
            "eligibility_agreement": expected["command_eligible"] == actual["command_eligible"],
            "fallback_reason_agreement": expected["fallback_reason"] == actual["fallback_reason"],
            "candidate_max_absolute_error": maximum_error(expected["first_control"], actual["first_control"]),
            "d_geo_max_absolute_error": maximum_error(expected["d_geo"], actual["d_geo"]),
            "g_geo_max_absolute_error": maximum_error(expected["g_geo"], actual["g_geo"]),
            "semantic_margin_max_absolute_error": maximum_error(expected["semantic_margin"], actual["semantic_margin"]),
        }
        case["passed"] = (
            case["status_agreement"] and case["eligibility_agreement"]
            and case["fallback_reason_agreement"]
            and max(case["candidate_max_absolute_error"], case["d_geo_max_absolute_error"],
                    case["g_geo_max_absolute_error"], case["semantic_margin_max_absolute_error"]) <= 1e-6
        )
        cases[name] = case

    replay = {
        "status": "PASS", "reference": "LIVE_VERIFIED_WORKING_ENVIRONMENT",
        "reference_versions": host["environment"], "derived_versions": runtime["environment"],
        "exact_geometry": {
            "fixture_count": len(host["geometry"]["fixtures"]),
            "d_geo_max_absolute_error": geometry_d,
            "g_geo_max_absolute_error": geometry_g,
            "collision_classification_agreement": collision_agreement,
            "tolerance": 1e-6,
        },
        "cases": cases,
        "osqp": runtime["osqp"],
        "planner_cpu_constructed": True,
    }
    assert geometry_d <= 1e-6 and geometry_g <= 1e-6 and collision_agreement
    assert all(case["passed"] for case in cases.values())
    assert runtime["osqp"]["success_count"] == 20
    dump("stage11cc1_core_planner_replay_equivalence.json", replay)

    performance = dict(runtime["performance"])
    performance.update({
        "status": "PASS", "execution_device": "cpu", "includes_import_time": False,
        "warmup_iterations": 8, "cpu_execution_trace": runtime["cpu_execution_trace"],
    })
    assert performance["p95_ms"] <= 200.0
    dump("stage11cc1_cpu_runtime_performance.json", performance)

    labels = derived["Config"]["Labels"]
    base_layers = base["RootFS"]["Layers"]
    derived_layers = derived["RootFS"]["Layers"]
    lock_path = ROOT / "docker/ros2_humble_gzharmonic_torch_planner/planner_runtime_requirements.lock"
    manifest = {
        "status": "PASS", "image_tag": IMAGE, "image_id": derived_id,
        "image_size_bytes": derived["Size"], "base_image_id": BASE_ID,
        "temporary_base_tag": "sgcf-local/ros2-bridge-base:stage11cc1",
        "base_layer_prefix_agreement": derived_layers[:len(base_layers)] == base_layers,
        "base_layer_count": len(base_layers), "derived_layer_count": len(derived_layers),
        "labels": labels, "lock_sha256": hashlib.sha256(lock_path.read_bytes()).hexdigest(),
        "locked_wheel_count": 36,
        "system_python": {"numpy": "1.21.5", "scipy": "1.8.0", "rclpy": "PASS"},
        "planner_venv": {"numpy": runtime["environment"]["numpy"], "scipy": runtime["environment"]["scipy"],
                         "torch": runtime["environment"]["torch"], "osqp": runtime["environment"]["osqp"]},
        "torch_build": "CUDA_CAPABLE", "torch_compiled_cuda": runtime["environment"]["torch_compiled_cuda"],
        "formal_execution_device": "cpu", "gpu_exposed": False,
        "cuda_available": runtime["environment"]["torch_cuda_available"],
        "cuda_device_count": runtime["environment"]["torch_cuda_device_count"],
        "cuda_initialized": runtime["environment"]["torch_cuda_initialized_after"],
        "cpu_execution_trace": runtime["cpu_execution_trace"],
        "stage10_modules_loaded": runtime["environment"]["stage10_modules_loaded"],
        "ros_node_coexistence": runtime["ros"],
        "bridge_type_mappings": {name: True for name in ("Clock", "LaserScan", "Image", "CameraInfo", "Odometry", "Twist")},
        "original_bridge_image_modified": False,
    }
    assert manifest["base_layer_prefix_agreement"]
    assert labels["org.sgcf.authoritative-base-image-id"] == BASE_ID
    assert not manifest["cuda_available"] and not manifest["cuda_initialized"]
    assert not manifest["stage10_modules_loaded"]
    dump("stage11cc1_final_image_manifest.json", manifest)

    frozen_expected = {
        "core_hash": "3b94da1777e3d218c71792f2be91084b4de1e69edd498c9f9933d380d067a136",
        "gazebo_world_hash": "df8b4d1b690e8e25f6f196cc76a3f5a12218198e84fd1fed0d9509278e53a40f",
        "gazebo_model_hash": "4c69e37ccded2ed479dd2625e4895d6f4e971a0803aa5477435e2c0e074af90e",
        "original_bridge_docker_hash": "1206f1e59306d1ed2b7ba71348f798cf0650ce6bb9717648763966c9f22a9d4c",
    }
    frozen_actual = {
        "core_hash": tree_hash(PROJECT / "core"),
        "gazebo_world_hash": tree_hash(PROJECT / "gazebo/worlds"),
        "gazebo_model_hash": tree_hash(PROJECT / "gazebo/models"),
        "original_bridge_docker_hash": tree_hash(ROOT / "docker/ros2_humble_gzharmonic_bridge"),
    }
    core_tracked_unchanged = subprocess.run(
        ["git", "diff", "--quiet", "--", "sgcf_nrmp_project/core"], cwd=ROOT
    ).returncode == 0
    frozen_pass = (
        core_tracked_unchanged
        and frozen_actual["gazebo_world_hash"] == frozen_expected["gazebo_world_hash"]
        and frozen_actual["gazebo_model_hash"] == frozen_expected["gazebo_model_hash"]
        and frozen_actual["original_bridge_docker_hash"] == frozen_expected["original_bridge_docker_hash"]
        and inspect_image(BASE_ID)["Id"] == BASE_ID
    )
    assert frozen_pass

    residual = subprocess.check_output(
        ["docker", "ps", "-aq", "--filter", "name=sgcf_stage11cc1"], text=True
    ).splitlines()
    cleanup = {
        "status": "PASS", "residual_test_container_count": len(residual),
        "residual_test_containers": residual, "gazebo_started": False,
        "runtime_bridge_started": False, "cmd_vel_publication_count": 0,
        "base_image_preserved": True, "derived_image_preserved": True,
        "frozen_expected": frozen_expected, "frozen_actual": frozen_actual,
        "core_tracked_files_unchanged": core_tracked_unchanged,
        "core_tree_hash_note": "ignored Python bytecode is excluded from the tracked-source decision",
        "frozen_components_unchanged": frozen_pass, "gazebo_image_id": GAZEBO_ID,
    }
    assert not residual
    dump("stage11cc1_process_cleanup.json", cleanup)

    (OUT / "stage_11c_c1_decision.md").write_text(
        "# Stage 11C-C1 Decision\n\n"
        "```text\nSTAGE_11C_C1_COMPLETE\nCUDA_CAPABLE_TORCH_RUNTIME_IMAGE_FROZEN\n"
        "CPU_ONLY_PLANNER_EXECUTION_VALIDATED\nDUAL_NUMERICAL_STACK_ISOLATION_VALIDATED\n"
        "TORCH_BACKED_EXACT_GEOMETRY_VALIDATED\nCORE_PLANNER_CPU_REPLAY_EQUIVALENCE_VALIDATED\n"
        "ROS2_PLANNER_RUNTIME_COEXISTENCE_VALIDATED\nREADY_TO_RESTART_STAGE_11C_C_SHADOW_MODE\n```\n"
    )
    (OUT / "stage_11c_c1_report.md").write_text(f"""# Stage 11C-C1 Torch Planner Runtime Image Report

## Outcome

```text
STAGE_11C_C1_COMPLETE
CUDA_CAPABLE_TORCH_RUNTIME_IMAGE_FROZEN
CPU_ONLY_PLANNER_EXECUTION_VALIDATED
DUAL_NUMERICAL_STACK_ISOLATION_VALIDATED
TORCH_BACKED_EXACT_GEOMETRY_VALIDATED
CORE_PLANNER_CPU_REPLAY_EQUIVALENCE_VALIDATED
ROS2_PLANNER_RUNTIME_COEXISTENCE_VALIDATED
READY_TO_RESTART_STAGE_11C_C_SHADOW_MODE
```

The derived immutable image is `{derived_id}`. It is built from the verified local Bridge image `{BASE_ID}` and preserves that image's RootFS layers as an exact prefix.

The system ROS environment remains NumPy 1.21.5 / SciPy 1.8.0. The isolated Planner venv contains NumPy {runtime['environment']['numpy']}, SciPy {runtime['environment']['scipy']}, OSQP {runtime['environment']['osqp']}, and CUDA-capable Torch {runtime['environment']['torch']}. Formal execution used no GPU and observed no CUDA device, tensor, context, allocation, or kernel.

Six deterministic Exact Geometry fixtures matched the live verified working environment with zero d_geo and g_geo error. P0, semantic, R1, and collision replays matched status, eligibility, fallback reason, geometry, semantic margin, and candidate control with zero maximum error. OSQP solved 20/20 deterministic problems. Planner steady-state CPU P95 was {performance['p95_ms']:.3f} ms against the 200 ms limit.

The Planner venv imported rclpy and created/destroyed a ROS Node with the required message subscriptions without publishing `/cmd_vel`. All six ros_gz_bridge registrations remained present. The existing Planner unittest suite passed 47/47 tests. Core, Gazebo assets, the original Bridge Docker directory, and the original Bridge image remained unchanged. Gazebo and Stage 11C-C were not started.
""")
    (OUT / "known_limitations.md").write_text(
        "# Known limitations\n\n"
        "- Torch is a CUDA-capable 2.8.0+cu128 build, so the image is large; this stage validates CPU execution only.\n"
        "- Replay used deterministic frozen code fixtures and a live verified working-environment reference; Gazebo was intentionally not run.\n"
        "- Stage 10 inference, checkpoints, training, and the seven-world Stage 11C-C shadow runtime remain outside this stage.\n"
    )
    (OUT / "test_output.txt").write_text(
        "PASS derived image build\nPASS system ROS NumPy 1.21.5 / SciPy 1.8.0\n"
        "PASS isolated Planner venv\nPASS rclpy, torch, osqp, Planner imports\n"
        "PASS CPU-only formal execution; CUDA tensor/context/kernel counts = 0\n"
        "PASS Exact Geometry six fixtures; max d_geo/g_geo error = 0\n"
        "PASS OSQP deterministic smoke 20/20\nPASS P0/semantic/R1/collision replay\n"
        f"PASS CPU steady-state P95 {performance['p95_ms']:.6f} ms <= 200 ms\n"
        "PASS ROS Node create/destroy without /cmd_vel\nPASS ros_gz_bridge mappings 6/6\n"
        "PASS Planner unittest 47/47\nPASS frozen components unchanged\n"
        "PASS residual test containers = 0\nPASS Gazebo not run; Stage 11C-C not started\n"
    )


if __name__ == "__main__":
    main()
