#!/usr/bin/env python3
"""Record the Stage 11C-C1R probe-time hard stop."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "sgcf_nrmp_project/artifacts/stages/stage_11c_c1r_local_base_image_recovery"
LOGS = OUT / "logs"
BASE_ID = "sha256:c2288babf5595cdf3caafcd23fd68de2714863b5132ffb10b3cbd10006ca2862"
BASE_HEX = BASE_ID.removeprefix("sha256:")
ALIAS = f"sgcf-local/ros2-bridge-base:sha256-{BASE_HEX}"
PROBE_ID = "sha256:923f7a1c632ec1b464492c076561af69e5c63c4cd3b0153f051d7a2311cba2e0"
BASE_LAYERS = [
    "sha256:8bba68e9f91e20837c41b6906e2bba1b9118af01472c75e4259280f7575f938d",
    "sha256:1ae35a736a9d0f3baf1d623f2124efeed2a5fba7bafac148f0bf7ebd1d831ca7",
    "sha256:1947f363faf37c197fb298c9ab42af6e1f87a9159f00947cff4079b494e12884",
    "sha256:d2a03672fcded77184f142f9995af1454165757490a7a67dce9ab9773dd36978",
    "sha256:3af2284ee53f7cd62a2802ec89fe0a0b4c26fc8436f70ecdf4ce87e97d8452cc",
    "sha256:738272aca762b8e26bd9b1e3f03021d9f8fef570ddcc05a036ad37065b26f603",
    "sha256:a57bfe1d6e4794cedbd147b46be8857341923cc680cbd961c5880dd8f012268f",
    "sha256:34e97c9f6f9fe6d349ea44d41052b01e419ca5a85c84d1f3a94fe8f749d3e23e",
]


def dump(name: str, data: object) -> None:
    (OUT / name).write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


def sha(path: Path) -> str | None:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    LOGS.mkdir(parents=True, exist_ok=True)
    probe_log = (LOGS / "base_probe_build.log").read_text(errors="replace")
    remote_frontend = "docker.io/docker/dockerfile:1" in probe_log
    alias_lookup = "docker.io/sgcf-local/ros2-bridge-base" in probe_log
    no_403 = "403" not in probe_log and "Forbidden" not in probe_log

    parent = ROOT / "sgcf_nrmp_project/artifacts/stages/stage_11c_c1_torch_planner_runtime"
    docker_dir = ROOT / "docker/ros2_humble_gzharmonic_torch_planner"
    lock = docker_dir / "planner_runtime_requirements.lock"
    wheel_manifest = parent / "stage11cc1_wheel_manifest.json"
    dockerfile = docker_dir / "Dockerfile"

    dump("stage11cc1r_parent_evidence_integration.json", {
        "parent_stage": "Stage 11C-C1", "parent_decision": "BLOCKED_IMAGE_BUILD",
        "parent_preserved": True, "base_image_id": BASE_ID,
        "wheel_lock_reused": True, "wheel_count": 36,
    })
    dump("stage11cc1r_base_image_object_audit.json", {
        "status": "PASS", "inspect_success": True, "image_id": BASE_ID,
        "os": "linux", "architecture": "amd64", "size_bytes": 890542066,
        "created": "2026-07-14T19:55:30.566042179+08:00",
        "rootfs_layer_count": len(BASE_LAYERS), "rootfs_layers": BASE_LAYERS,
        "repo_digest_may_be_empty": True,
    })
    dump("stage11cc1r_local_base_alias_binding.json", {
        "status": "PASS", "alias": ALIAS, "alias_role": "NON_AUTHORITATIVE_BOOTSTRAP_ALIAS",
        "authoritative_identity": BASE_ID, "alias_image_id": BASE_ID,
        "id_match": True, "rootfs_layers_match": True,
        "future_build_precondition": "docker inspect(BASE_ALIAS).Id == BASE_ID",
    })
    dump("stage11cc1r_builder_audit.json", {
        "status": "PASS", "selected_builder": "default", "driver": "docker",
        "buildkit_version": "v0.29.0", "docker_context": "default",
        "platform_required": "linux/amd64", "local_engine_visible": True,
    })
    dump("stage11cc1r_base_probe.json", {
        "status": "FAIL_STRICT_ZERO_NETWORK_GATE", "build_exit_code": 0,
        "probe_image_id": PROBE_ID, "base_image_id": BASE_ID,
        "no_403": no_403, "remote_base_layer_pull_observed": False,
        "dockerfile_frontend_remote_access_observed": remote_frontend,
        "docker_io_alias_metadata_lookup_observed": alias_lookup,
        "hard_gate": "no Docker Hub access and no docker.io/sgcf-local lookup",
        "decision": "BLOCKED_LOCAL_BASE_IMAGE_RESOLUTION",
    })
    dump("stage11cc1r_base_layer_lineage.json", {
        "status": "PASS_BUT_NOT_SUFFICIENT", "base_layers": BASE_LAYERS,
        "probe_prefix_layers": BASE_LAYERS, "prefix_agreement_percent": 100,
        "probe_extra_layers": ["sha256:5f70bf18a086007016e948b04aed3b82103a36bea41755bc6efdc4ec11d6c6ef"],
        "architecture": "linux/amd64", "os_release": "Ubuntu 22.04.5 LTS",
    })
    dump("stage11cc1r_dependency_lock_revalidation.json", {
        "status": "PASS", "entry_count": 36, "missing_sha256_count": 0,
        "non_binary_wheel_count": 0, "duplicate_package_version_conflicts": 0,
        "torchvision_present": False, "torchaudio_present": False,
        "stage10_dependency_present": False, "lockfile_sha256": sha(lock),
        "wheel_manifest_sha256": sha(wheel_manifest), "dockerfile_sha256": sha(dockerfile),
        "lock_drift_detected": False,
    })
    not_run = {"status": "NOT_EXECUTED", "reason": "BLOCKED_LOCAL_BASE_IMAGE_RESOLUTION at zero-network base probe"}
    for name in [
        "stage11cc1r_derived_image_manifest.json", "stage11cc1r_image_lineage_audit.json",
        "stage11cc1_system_environment_regression.json", "stage11cc1_numerical_stack_isolation.json",
        "stage11cc1_torch_build_vs_execution_contract.json", "stage11cc1_cpu_execution_trace.json",
        "stage11cc1_cuda_device_access_audit.json", "stage11cc1_import_validation.json",
        "stage11cc1_torch_exact_geometry_validation.json", "stage11cc1_autograd_runtime_audit.json",
        "stage11cc1_osqp_solver_smoke.json", "stage11cc1_planner_construction.json",
        "stage11cc1_core_planner_replay_equivalence.json", "stage11cc1_cpu_runtime_performance.json",
        "stage11cc1_ros_planner_coexistence.json", "stage11cc1_bridge_capability_regression.json",
        "stage11cc1_runtime_entrypoint_contract.json", "stage11cc1_frozen_component_audit.json",
        "stage11cc1_final_image_manifest.json",
    ]:
        dump(name, not_run)
    dump("stage11cc1_process_cleanup.json", {
        "status": "PENDING_FINAL_PROBE_IMAGE_REMOVAL", "gazebo_started": False,
        "bridge_started": False, "planner_started": False,
    })

    for log in ["derived_image_build.log", "system_environment.txt", "import_validation.txt",
                "exact_geometry.txt", "autograd_runtime.txt", "osqp_smoke.txt",
                "planner_replay.txt", "cpu_performance.txt", "ros_coexistence.txt"]:
        (LOGS / log).write_text("NOT_EXECUTED: BLOCKED_LOCAL_BASE_IMAGE_RESOLUTION\n")

    report = f"""# Stage 11C-C1R Report

Stage 11C-C1R stopped at the local-base probe hard gate.

## Decision

`BLOCKED_LOCAL_BASE_IMAGE_RESOLUTION`

The authoritative local base object `{BASE_ID}` exists, is `linux/amd64`, and its eight RootFS layers matched the bootstrap alias and probe image exactly. The authorized alias is `{ALIAS}` and is only a `NON_AUTHORITATIVE_BOOTSTRAP_ALIAS`.

The probe build itself exited successfully and did not pull base layers or return HTTP 403. However, its log records both a Dockerfile frontend access to `docker.io/docker/dockerfile:1` and a canonical `docker.io/sgcf-local/...` metadata lookup. This violates the explicit zero-network / no `docker.io/sgcf-local` lookup gate. Therefore the derived Planner image was not built and no downstream Planner, Torch, OSQP, ROS coexistence, Gazebo, bridge, world, or `/cmd_vel` gate was run.

The parent Stage 11C-C1 `BLOCKED_IMAGE_BUILD` report remains unchanged.
"""
    (OUT / "stage_11c_c1r_report.md").write_text(report)
    (OUT / "stage_11c_c1r_decision.md").write_text("# Stage 11C-C1R Decision\n\n`BLOCKED_LOCAL_BASE_IMAGE_RESOLUTION`\n")
    (OUT / "known_limitations.md").write_text("# Known limitations\n\nThe default BuildKit probe canonicalized the local alias as a docker.io name and fetched the Dockerfile frontend, violating the strict zero-network probe contract.\n")
    (OUT / "stage_11c_c1_final_handoff.md").write_text("# Stage 11C-C1 Final Handoff\n\nNo final Planner image exists. Resume only with an explicitly authorized probe method that proves zero registry lookup while preserving the verified local base identity.\n")
    (OUT / "test_output.txt").write_text("PASS base object identity\nPASS alias identity\nPASS rootfs lineage\nFAIL strict zero-network probe\nNOT RUN derived image and downstream gates\n")


if __name__ == "__main__":
    main()
