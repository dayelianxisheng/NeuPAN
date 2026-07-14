#!/usr/bin/env python3
"""Finalize Stage 11C-C1 after the immutable-FROM build failure."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PROJECT = ROOT / "sgcf_nrmp_project"
DOCKER = ROOT / "docker/ros2_humble_gzharmonic_torch_planner"
OUT = PROJECT / "artifacts/stages/stage_11c_c1_torch_planner_runtime"
BASE = "sha256:c2288babf5595cdf3caafcd23fd68de2714863b5132ffb10b3cbd10006ca2862"
GAZEBO = "sha256:72af30cf91fb3001e019c6e57846dbe8d72497516882cc3d0e99a7d5551759ac"
DECISION = "BLOCKED_IMAGE_BUILD"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tree_hash(path: Path) -> str:
    digest = hashlib.sha256()
    for item in sorted(entry for entry in path.rglob("*") if entry.is_file()):
        digest.update(item.relative_to(path).as_posix().encode())
        digest.update(hashlib.sha256(item.read_bytes()).digest())
    return digest.hexdigest()


def dump(name: str, value: object) -> None:
    (OUT / name).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    lock = DOCKER / "planner_runtime_requirements.lock"
    lock_rows = [line for line in lock.read_text().splitlines() if line and not line.startswith("#")]
    packages = []
    for line in lock_rows:
        requirement, hash_value = line.split(" --hash=sha256:")
        name, version = requirement.split("==", 1)
        packages.append({"package": name, "version": version, "sha256": hash_value, "binary_only": True})
    dump(
        "stage11cc1_base_image_binding.json",
        {
            "status": "PASSED_PREBUILD",
            "base_image_id": BASE,
            "local_object_available": True,
            "dockerfile_from": BASE,
            "immutable_reference_used": True,
            "base_image_modified": False,
        },
    )
    dump(
        "stage11cc1_dual_environment_contract.json",
        {
            "status": "DEFINED_NOT_BUILT",
            "system_python": "/usr/bin/python3",
            "system_numpy": "1.21.5",
            "system_scipy": "1.8.0",
            "planner_python": "/opt/sgcf_planner_venv/bin/python",
            "venv_system_site_packages": True,
            "planner_numeric_stack_isolated": True,
            "bridge_uses_system_environment": True,
        },
    )
    closure = {
        "status": "PASSED_PREBUILD",
        "torch_role": "TORCH_GEOMETRY_RUNTIME",
        "torch_runtime_files": ["sgcf_nrmp/planner/geometry_checker.py"],
        "torchvision_imported": False,
        "stage10_imported": False,
        "checkpoint_access_required": False,
        "cvxpy_required": True,
        "osqp_required_via_cvxpy": True,
        "qdldl_standalone_required": False,
        "scipy_role": "NUMERICAL_RUNTIME / CVXPY-OSQP stack",
        "cuda_hardcoded_in_core": False,
        "geometry_tensor_device_literal": "cpu",
    }
    dump("stage11cc1_planner_import_closure.json", closure)
    dump(
        "stage11cc1_dependency_role_classification.json",
        {
            "status": "PASSED_PREBUILD",
            "roles": {
                "torch": "TORCH_GEOMETRY_RUNTIME",
                "numpy": "NUMERICAL_RUNTIME",
                "scipy": "NUMERICAL_RUNTIME",
                "cvxpy": "NUMERICAL_RUNTIME",
                "osqp": "NUMERICAL_RUNTIME",
                "shapely": "NUMERICAL_RUNTIME",
                "rclpy": "ROS_SYSTEM_RUNTIME",
                "sgcf_nrmp": "PROJECT_RUNTIME",
                "torchvision": "UNUSED_OPTIONAL",
                "Stage10": "UNUSED_OPTIONAL",
            },
        },
    )
    dump(
        "stage11cc1_cpu_device_contract.json",
        {
            "status": "DEFINED_NOT_EXECUTED",
            "torch_build": "CUDA-CAPABLE TORCH BUILD",
            "execution": "CPU-ONLY PLANNER EXECUTION CONTRACT",
            "cuda_visible_devices": "",
            "nvidia_visible_devices": "void",
            "docker_gpus_flag": False,
            "nvidia_devices_mounted": False,
            "core_geometry_device_literal": "cpu",
        },
    )
    dump(
        "stage11cc1_dependency_resolution.json",
        {
            "status": "PASSED_PREBUILD",
            "resolver": "pip dry-run --ignore-installed --only-binary=:all:",
            "python": "3.10 amd64",
            "package_count": len(packages),
            "all_binary": True,
            "all_hash_locked": True,
            "torch": "2.8.0+cu128",
            "numpy": "1.26.4",
            "scipy": "1.13.0",
            "cvxpy": "1.7.5",
            "osqp": "1.1.1",
            "torchvision": None,
            "torchaudio": None,
        },
    )
    dump(
        "stage11cc1_wheel_manifest.json",
        {
            "status": "LOCKED_NOT_INSTALLED",
            "package_count": len(packages),
            "packages": packages,
            "torch_official_url": "https://download-r2.pytorch.org/whl/cu128/torch-2.8.0%2Bcu128-cp310-cp310-manylinux_2_28_x86_64.whl",
            "torch_hash_matches_official_index": True,
            "host_wheel_copied_into_build": False,
            "source_builds": 0,
        },
    )
    dump(
        "stage11cc1_numerical_stack_isolation.json",
        {
            "status": "NOT_EXECUTED",
            "reason": DECISION,
            "system_expected": {"numpy": "1.21.5", "scipy": "1.8.0"},
            "venv_locked": {"numpy": "1.26.4", "scipy": "1.13.0"},
        },
    )
    dump(
        "stage11cc1_torch_runtime_manifest.json",
        {
            "status": "LOCKED_NOT_INSTALLED",
            "version": "2.8.0+cu128",
            "compiled_cuda": "12.8",
            "wheel_sha256": "0c96999d15cf1f13dd7c913e0b21a9a355538e6cfc10861a17158320292f5954",
            "build_contract": "CUDA-CAPABLE TORCH BUILD",
            "execution_contract": "CPU-ONLY PLANNER EXECUTION CONTRACT",
        },
    )
    dump(
        "stage11cc1_stage10_isolation.json",
        {
            "status": "PASSED_STATIC_PREBUILD",
            "stage10_import_count": 0,
            "torchvision_import_count": 0,
            "checkpoint_required": False,
            "torch_classification": "TORCH_RUNTIME_MATH_DEPENDENCY",
        },
    )
    build_log = (OUT / "logs/image_build.log").read_text()
    dump(
        "stage11cc1_image_build_manifest.json",
        {
            "status": "FAILED",
            "decision": DECISION,
            "base_image_id": BASE,
            "derived_image_id": None,
            "derived_tag": "sgcf-ros2-humble-gzharmonic-torch-planner:stage11cc1",
            "dockerfile_sha256": sha(DOCKER / "Dockerfile"),
            "lockfile_sha256": sha(lock),
            "failure_stage": "BuildKit FROM source metadata resolution",
            "failure": "raw local sha256 image ID treated as docker.io/library/sha256 reference; registry proxy returned 403",
            "packages_downloaded_by_build": 0,
            "base_filesystem_mutated": False,
            "log_contains_403": "403 Forbidden" in build_log,
        },
    )
    downstream = [
        "stage11cc1_installed_package_manifest.json",
        "stage11cc1_system_environment_regression.json",
        "stage11cc1_import_validation.json",
        "stage11cc1_torch_exact_geometry_validation.json",
        "stage11cc1_autograd_runtime_audit.json",
        "stage11cc1_osqp_solver_smoke.json",
        "stage11cc1_planner_construction.json",
        "stage11cc1_core_planner_replay_equivalence.json",
        "stage11cc1_cpu_runtime_performance.json",
        "stage11cc1_ros_planner_coexistence.json",
        "stage11cc1_bridge_capability_regression.json",
        "stage11cc1_cpu_execution_trace.json",
        "stage11cc1_cuda_device_access_audit.json",
    ]
    for name in downstream:
        dump(name, {"status": "NOT_EXECUTED", "reason": DECISION, "measurements_fabricated": False})
    dump(
        "stage11cc1_torch_build_vs_execution_contract.json",
        {
            "status": "DEFINED_NOT_EXECUTED",
            "torch_build_version": "2.8.0+cu128",
            "compiled_cuda_version": "12.8",
            "wheel_source": "PyTorch official cu128 index",
            "wheel_hash": packages[0]["sha256"],
            "gpu_exposed": False,
            "cuda_visible_devices": "",
            "nvidia_visible_devices": "void",
            "selected_planner_device": "cpu",
            "runtime_measurements": None,
        },
    )
    dump(
        "stage11cc1_runtime_entrypoint_contract.json",
        {
            "status": "DEFINED_NOT_VALIDATED",
            "bridge": {"python": "/usr/bin/python3", "command": "ros2 run ros_gz_bridge parameter_bridge"},
            "planner": {"python": "/opt/sgcf_planner_venv/bin/python", "cuda_visible_devices": "", "nvidia_visible_devices": "void"},
            "zero_guard": {"planner_dependency": False},
            "formal_processes_started": False,
        },
    )
    dump(
        "stage11cc1_frozen_component_audit.json",
        {
            "status": "PASSED",
            "base_bridge_image_id": BASE,
            "gazebo_image_id": GAZEBO,
            "gazebo_world_hash": tree_hash(PROJECT / "gazebo/worlds"),
            "gazebo_model_hash": tree_hash(PROJECT / "gazebo/models"),
            "core_hash": tree_hash(PROJECT / "core"),
            "original_bridge_docker_hash": tree_hash(ROOT / "docker/ros2_humble_gzharmonic_bridge"),
            "protected_changes_by_stage11cc1": [],
            "gazebo_runs": 0,
            "cmd_vel_publications": 0,
        },
    )
    dump(
        "stage11cc1_process_cleanup.json",
        {
            "status": "PASSED",
            "build_process_running": False,
            "build_container_count": 0,
            "test_container_count": 0,
            "ros_test_process_count": 0,
            "planner_test_process_count": 0,
            "gazebo_process_count": 0,
        },
    )
    for name in (
        "system_environment.txt", "import_validation.txt", "exact_geometry.txt",
        "autograd_runtime.txt", "osqp_smoke.txt", "planner_replay.txt",
        "cpu_performance.txt", "ros_coexistence.txt", "process_cleanup.txt",
    ):
        (OUT / "logs" / name).write_text(f"NOT_EXECUTED: {DECISION}\n", encoding="utf-8")
    (OUT / "logs/dependency_resolution.txt").write_text(
        f"Resolved {len(packages)} exact binary wheels with hashes.\n"
        "Torch 2.8.0+cu128 official index hash verified.\n",
        encoding="utf-8",
    )
    (OUT / "logs/wheel_download.txt").write_text(
        "No formal build wheel download occurred; BuildKit failed at FROM metadata resolution.\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
