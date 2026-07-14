#!/usr/bin/env python3
"""Record Stage 11C-C0's build-preflight dependency-coupling stop."""

from __future__ import annotations

import hashlib
import json
import platform
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PROJECT = ROOT / "sgcf_nrmp_project"
OUT = PROJECT / "artifacts/stages/stage_11c_c0_planner_runtime_image"
LOGS = OUT / "logs"
BASE_ID = "sha256:c2288babf5595cdf3caafcd23fd68de2714863b5132ffb10b3cbd10006ca2862"
GAZEBO_ID = "sha256:72af30cf91fb3001e019c6e57846dbe8d72497516882cc3d0e99a7d5551759ac"
DECISION = "BLOCKED_RUNTIME_TRAINING_DEPENDENCY_COUPLING"


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
    dump(
        "stage11cc0_base_image_binding.json",
        {
            "status": "PASSED",
            "base_bridge_image_id": BASE_ID,
            "immutable_id": True,
            "image_object_previously_verified_by_stage11cc_dependency_gate": True,
            "ros_distro": "Humble",
            "python_version": "3.10",
            "rclpy": "AVAILABLE",
            "numpy": "1.21.5",
            "scipy": "1.8.0",
            "original_image_modified": False,
            "derived_image_built": False,
        },
    )
    closure = {
        "status": "BLOCKED",
        "decision": DECISION,
        "formal_entry": "sgcf_nrmp.planner.GTNRMPPlanner",
        "runtime_chain": [
            "sgcf_nrmp.planner.__init__",
            "sgcf_nrmp.planner.gt_nrmp_planner.GTNRMPPlanner",
            "sgcf_nrmp.planner.geometry_checker.ExactObservableChecker",
            "sgcf_nrmp.planner.geometry_checker.BatchedRectangleObservableOracle",
        ],
        "third_party_runtime": {
            "numpy": "required",
            "scipy": "required transitively by solver stack",
            "cvxpy": "direct runtime import in planner/qp_problem.py",
            "osqp": "CVXPY runtime solver backend",
            "qdldl": "OSQP binary wheel dependency / backend component",
            "shapely": "direct runtime import in geometry_checker.py",
            "torch": "direct unconditional runtime import and used by Exact Observable Geometry",
        },
        "torch_evidence": {
            "file": "sgcf_nrmp_project/core/src/sgcf_nrmp/planner/geometry_checker.py",
            "import": "import torch",
            "runtime_uses": ["torch.as_tensor", "torch.linalg.vector_norm", "torch.autograd.grad"],
            "training_only": False,
        },
        "cvxpy_required": True,
        "osqp_directly_imported": False,
        "osqp_required_as_cvxpy_solver": True,
        "torch_required_by_formal_planner_import": True,
        "stage10_module_required": False,
        "stage10_dependency_can_be_excluded": False,
        "reason_stage10_dependency_cannot_be_excluded": "Torch is required by shared Planner geometry runtime even without importing Stage 10 modules.",
        "training_dependencies_can_be_excluded": False,
        "standard_library": ["dataclasses", "enum", "time", "collections.abc"],
        "project_modules": ["planner", "geometry", "semantic", "fusion", "types", "data.procedural"],
        "ros_modules": ["rclpy and ROS messages required only by future wrapper"],
    }
    dump("stage11cc0_planner_import_closure.json", closure)
    dump(
        "stage11cc0_working_environment_evidence.json",
        {
            "evidence_only": True,
            "copied_into_image": False,
            "python": "3.10.0",
            "python_abi": "cpython-310",
            "architecture": platform.machine(),
            "numpy": "1.26.4",
            "scipy": "1.13.0",
            "osqp": "1.1.1",
            "cvxpy": "1.7.5",
            "qdldl": "not importable as top-level module",
            "torch": "2.8.0+cu128",
            "abi_difference_from_base": False,
            "numerical_stack_difference_from_base": True,
            "planner_dependency_source": "current host neupan environment, read-only version evidence",
        },
    )
    dump(
        "stage11cc0_dependency_lock.json",
        {
            "status": "NOT_CREATED",
            "reason": DECISION,
            "repository_constraints": {
                "numpy": ">=1.26,<2",
                "torch": "==2.8.0",
                "source": "sgcf_nrmp_project/core/pyproject.toml",
            },
            "stage_constraints": {"numpy": "==1.21.5", "scipy": "==1.8.0", "torch": "PROHIBITED"},
            "numerical_stack_conflict": True,
            "unlocked_install_attempted": False,
        },
    )
    dump(
        "stage11cc0_wheel_manifest.json",
        {
            "status": "NOT_DOWNLOADED",
            "reason": DECISION,
            "wheel_count": 0,
            "network_access_used": False,
            "hashes_fabricated": False,
        },
    )
    dump(
        "stage11cc0_stage10_dependency_isolation.json",
        {
            "status": "FAILED",
            "decision": DECISION,
            "stage10_modules_imported": False,
            "torch_imported_by_formal_planner": True,
            "torch_import_location": "sgcf_nrmp.planner.geometry_checker",
            "torch_use": "Exact Observable Geometry tensor/autograd implementation",
            "cuda_required": False,
            "stage10_checkpoint_loaded": False,
            "isolation_requirement_satisfied": False,
        },
    )
    not_executed = [
        "stage11cc0_image_build_manifest.json",
        "stage11cc0_installed_package_manifest.json",
        "stage11cc0_import_validation.json",
        "stage11cc0_osqp_solver_smoke.json",
        "stage11cc0_planner_construction.json",
        "stage11cc0_core_replay_equivalence.json",
        "stage11cc0_ros_planner_runtime_coexistence.json",
        "stage11cc0_bridge_capability_regression.json",
    ]
    for name in not_executed:
        dump(
            name,
            {
                "status": "NOT_EXECUTED",
                "reason": DECISION,
                "image_built": False,
                "measurements_fabricated": False,
            },
        )
    dump(
        "stage11cc0_frozen_component_audit.json",
        {
            "status": "PASSED",
            "base_bridge_image_id": BASE_ID,
            "gazebo_image_id": GAZEBO_ID,
            "gazebo_worlds_hash": tree_hash(PROJECT / "gazebo/worlds"),
            "gazebo_models_hash": tree_hash(PROJECT / "gazebo/models"),
            "core_hash": tree_hash(PROJECT / "core"),
            "original_bridge_docker_hash": tree_hash(ROOT / "docker/ros2_humble_gzharmonic_bridge"),
            "protected_changes_by_stage11cc0": [],
            "derived_image_built": False,
            "gazebo_run_count": 0,
            "cmd_vel_publish_count": 0,
        },
    )
    (LOGS / "dependency_audit.txt").write_text(
        "Formal planner import chain reaches geometry_checker.py.\n"
        "geometry_checker.py unconditionally imports torch and uses it for exact observable geometry.\n"
        "pyproject.toml requires torch==2.8.0 and numpy>=1.26,<2.\n"
        "Stage 11C-C0 prohibits Torch and freezes numpy==1.21.5.\n"
        f"Decision: {DECISION}\n",
        encoding="utf-8",
    )
    for name in (
        "wheel_download.txt",
        "image_build.log",
        "import_validation.txt",
        "osqp_smoke.txt",
        "core_replay.txt",
        "ros_coexistence.txt",
    ):
        (LOGS / name).write_text(f"NOT_EXECUTED: {DECISION}\n", encoding="utf-8")


if __name__ == "__main__":
    main()
