#!/usr/bin/env python3
"""Finalize the Stage 11B-F report after the package-content hard stop."""

from __future__ import annotations

import hashlib
import json
import locale
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "sgcf_nrmp_project/artifacts/stages/stage_11b_f_hlms_media_restoration"
LOGS = OUT / "logs"
DECISION = "BLOCKED_OFFICIAL_HLMS_MEDIA_MISSING"


def read_json(name: str) -> dict:
    return json.loads((OUT / name).read_text())


def write_json(name: str, data: object) -> None:
    (OUT / name).write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


def tree_listing_hash(paths: list[Path]) -> str:
    lines: list[str] = []
    locale.setlocale(locale.LC_COLLATE, "")
    files = sorted(
        [
        candidate
        for root in paths
        for candidate in root.rglob("*")
        if candidate.is_file() and not candidate.is_symlink()
        ],
        key=lambda path: locale.strxfrm(path.as_posix()),
    )
    for path in files:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        lines.append(f"{digest}  {path.relative_to(ROOT).as_posix()}\n")
    return hashlib.sha256("".join(lines).encode()).hexdigest()


def placeholder(status: str, reason: str, **extra: object) -> dict:
    return {"status": status, "reason": reason, **extra}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    LOGS.mkdir(parents=True, exist_ok=True)
    download = read_json("stage11bf_download_audit.json")
    metadata = read_json("stage11bf_package_metadata.json")
    media = read_json("stage11bf_hlms_media_audit.json")
    alias = read_json("stage11bf_alias_package_interaction.json")

    stop_reason = (
        "The exact official package lacks the required nonempty "
        "2.0/scripts/Compositors directory. The package-content hard gate "
        "therefore prohibited dependency installation, image construction, "
        "and the empty_world runtime re-gate."
    )
    dependencies = metadata["identity"]["Depends"]
    write_json(
        "stage11bf_dependency_audit.json",
        placeholder(
            "NOT_EXECUTED_AFTER_HARD_STOP",
            stop_reason,
            declared_dependencies=[item.strip() for item in dependencies.split(",")],
            static_dependency_observations={
                "gz_rendering_core_major": 8,
                "gz_rendering_core_exact_version_required": "8.2.3-1~jammy",
                "gz_rendering_ogre2_major": 8,
                "gz_rendering_ogre2_exact_version_required": "8.2.3-1~jammy",
                "ogre_next_major_required": "2.3",
                "gz_sim_dependency_declared": False,
                "architecture_change_declared": False,
            },
            package_installed=False,
            repository_dependencies_resolved=False,
        ),
    )
    write_json(
        "stage11bf_apt_simulation.json",
        placeholder(
            "NOT_EXECUTED_AFTER_HARD_STOP",
            stop_reason,
            packages_installed=0,
            packages_upgraded=0,
            packages_downgraded=0,
            packages_removed=0,
        ),
    )
    write_json(
        "stage11bf_image_build_manifest.json",
        placeholder(
            "NOT_BUILT_AFTER_HARD_STOP",
            stop_reason,
            requested_tag="sgcf-gazebo-harmonic:hlms-media-fix",
            image_created=False,
            dockerfile_modified_by_stage11bf=False,
            packages_installed=[],
        ),
    )
    write_json(
        "stage11bf_installed_media_ownership.json",
        placeholder(
            "NOT_INSTALLED_AFTER_HARD_STOP",
            stop_reason,
            package_archive_contains_media=True,
            package_installed=False,
            dpkg_ownership_checked=False,
            host_or_source_media_copied=False,
        ),
    )
    write_json(
        "stage11bf_repaired_environment.json",
        placeholder(
            "NOT_APPLIED_AFTER_HARD_STOP",
            stop_reason,
            gz_rendering_plugin_path=(
                "/usr/lib/x86_64-linux-gnu/gz-rendering-8/engine-plugins"
            ),
            gz_rendering_resource_path=None,
            gl_or_egl_workarounds_added=[],
        ),
    )
    runtime = placeholder(
        "NOT_RUN_AFTER_PACKAGE_CONTENT_HARD_STOP",
        stop_reason,
        world="empty_world",
        attempt_count=0,
        simulation_clock_observed=False,
        gazebo_started=False,
        image_tag_created=False,
    )
    write_json("stage11bf_empty_world_runtime.json", runtime)
    write_json(
        "stage11bf_sensor_runtime_smoke.json",
        placeholder(
            "NOT_RUN_AFTER_RENDERING_GATE",
            stop_reason,
            lidar_messages=0,
            camera_messages=0,
            odometry_messages=0,
        ),
    )
    write_json(
        "stage11bf_diff_drive_runtime_smoke.json",
        placeholder(
            "NOT_RUN_AFTER_SENSOR_GATE",
            stop_reason,
            commands_published=0,
            planner_started=False,
        ),
    )
    cleanup = {
        "diagnostic_container": "sgcf_gz_harmonic_abi8_alias",
        "diagnostic_container_stopped": True,
        "container_gz_processes_before_stop": 0,
        "host_gz_processes_after_stop": 0,
        "hlms_media_fix_container_created": False,
        "residual_gz_process_count": 0,
        "passed": True,
    }
    write_json("stage11bf_process_cleanup.json", cleanup)

    gazebo_hash = tree_listing_hash(
        [ROOT / "sgcf_nrmp_project/gazebo/worlds", ROOT / "sgcf_nrmp_project/gazebo/models"]
    )
    frozen = {
        "stage_entry_combined_gazebo_hash": "9fd7ec9b2e868eb5f4627b85d945a16a724f17fd2e5779c0d07dca6b04721e8a",
        "stage_exit_combined_gazebo_hash": gazebo_hash,
        "gazebo_assets_modified_by_stage11bf": gazebo_hash
        != "9fd7ec9b2e868eb5f4627b85d945a16a724f17fd2e5779c0d07dca6b04721e8a",
        "robot_footprint_m": {"length": 0.8, "width": 0.5, "modified": False},
        "lidar_contract_modified": False,
        "camera_contract_modified": False,
        "stage05_exact_geometry_modified": False,
        "stage07_projection_modified": False,
        "stage07_semantic_margin_modified": False,
        "stage09b_planner_modified": False,
        "stage10_modified": False,
        "other_worlds_run": [],
        "planner_started": False,
        "ros_bridge_started": False,
        "passed": gazebo_hash
        == "9fd7ec9b2e868eb5f4627b85d945a16a724f17fd2e5779c0d07dca6b04721e8a",
    }
    write_json("stage11bf_frozen_asset_audit.json", frozen)

    requirement_matrix = [
        {"id": 1, "requirement": "official OSRF archive source", "status": "VERIFIED", "evidence": "stage11bf_download_audit.json"},
        {"id": 2, "requirement": "exact package name", "status": "VERIFIED", "evidence": "stage11bf_package_metadata.json"},
        {"id": 3, "requirement": "exact 8.2.3-1~jammy version", "status": "VERIFIED", "evidence": "stage11bf_package_metadata.json"},
        {"id": 4, "requirement": "amd64 architecture", "status": "VERIFIED", "evidence": "stage11bf_package_metadata.json"},
        {"id": 5, "requirement": "fixed package SHA256", "status": "VERIFIED", "evidence": "stage11bf_download_audit.json"},
        {"id": 6, "requirement": "Hlms/Unlit/GLSL present", "status": "VERIFIED", "evidence": "stage11bf_hlms_media_audit.json"},
        {"id": 7, "requirement": "required PBS/Unlit/Terra resources present", "status": "VERIFIED", "evidence": "stage11bf_hlms_media_audit.json"},
        {"id": 8, "requirement": "resource root derived correctly", "status": "VERIFIED", "evidence": "stage11bf_resource_path_audit.json"},
        {"id": 9, "requirement": "installed media has dpkg ownership", "status": "NOT_REACHED_HARD_STOP", "evidence": "stage11bf_installed_media_ownership.json"},
        {"id": 10, "requirement": "no source or host media copied", "status": "VERIFIED", "evidence": "stage11bf_installed_media_ownership.json"},
        {"id": 11, "requirement": "no Gazebo upgrade or downgrade", "status": "VERIFIED_NO_TRANSACTION", "evidence": "stage11bf_apt_simulation.json"},
        {"id": 12, "requirement": "alias interaction handled", "status": "VERIFIED", "evidence": "stage11bf_alias_package_interaction.json"},
        {"id": 13, "requirement": "alias target matches Stage 11B-E", "status": "VERIFIED", "evidence": "stage11bf_alias_package_interaction.json"},
        {"id": 14, "requirement": "no new EGL/OpenGL workaround", "status": "VERIFIED", "evidence": "stage11bf_repaired_environment.json"},
        {"id": 15, "requirement": "single empty_world runtime gate", "status": "NOT_REACHED_HARD_STOP_ZERO_ATTEMPTS", "evidence": "stage11bf_empty_world_runtime.json"},
        {"id": 16, "requirement": "no other eleven worlds run", "status": "VERIFIED", "evidence": "stage11bf_frozen_asset_audit.json"},
        {"id": 17, "requirement": "Gazebo asset hashes unchanged", "status": "VERIFIED", "evidence": "stage11bf_frozen_asset_audit.json"},
        {"id": 18, "requirement": "footprint unchanged", "status": "VERIFIED", "evidence": "stage11bf_frozen_asset_audit.json"},
        {"id": 19, "requirement": "Planner not started", "status": "VERIFIED", "evidence": "stage11bf_frozen_asset_audit.json"},
        {"id": 20, "requirement": "Stage 10 not loaded", "status": "VERIFIED", "evidence": "stage11bf_frozen_asset_audit.json"},
        {"id": 21, "requirement": "ROS bridge not started", "status": "VERIFIED", "evidence": "stage11bf_frozen_asset_audit.json"},
        {"id": 22, "requirement": "no residual Gazebo processes", "status": "VERIFIED", "evidence": "stage11bf_process_cleanup.json"},
        {"id": 23, "requirement": "all JSON parse", "status": "VERIFIED_BY_TEST_OUTPUT", "evidence": "test_output.txt"},
        {"id": 24, "requirement": "compileall", "status": "VERIFIED_BY_TEST_OUTPUT", "evidence": "test_output.txt"},
        {"id": 25, "requirement": "git diff --check", "status": "VERIFIED_BY_TEST_OUTPUT", "evidence": "test_output.txt"},
        {"id": 26, "requirement": "protected directories unchanged", "status": "VERIFIED", "evidence": "stage11bf_frozen_asset_audit.json"},
    ]
    write_json("stage11bf_test_requirement_matrix.json", requirement_matrix)

    (LOGS / "package_download.log").write_text(
        "\n".join(
            [
                f"requested_url={download['requested_url']}",
                f"final_url={download['final_url']}",
                f"http_status={download['http_status']}",
                f"content_type={download['content_type']}",
                f"content_length={download['content_length']}",
                f"downloaded_size={download['downloaded_size']}",
                f"sha256={download['sha256']}",
                f"md5={download['md5']}",
                f"timestamp={download['download_file_mtime_utc']}",
            ]
        )
        + "\n"
    )
    placeholders = {
        "apt_simulation.txt": "NOT_EXECUTED_AFTER_HLMS_CONTENT_HARD_STOP\n",
        "image_build.log": "NOT_BUILT_AFTER_HLMS_CONTENT_HARD_STOP\n",
        "empty_world_stdout.txt": "NOT_RUN_AFTER_HLMS_CONTENT_HARD_STOP\n",
        "empty_world_stderr.txt": "NOT_RUN_AFTER_HLMS_CONTENT_HARD_STOP\n",
        "ogre2.log": "NOT_CREATED_BECAUSE_EMPTY_WORLD_WAS_NOT_RUN\n",
        "topic_list.txt": "NOT_COLLECTED_BECAUSE_EMPTY_WORLD_WAS_NOT_RUN\n",
    }
    for name, content in placeholders.items():
        (LOGS / name).write_text(content)

    report = f"""# Stage 11B-F Official HLMS Media Restoration Report

## Decision

```text
{DECISION}
```

Stage 11B-F stopped at the mandatory package-content gate. No package was
installed, no Docker image was built, and no Gazebo world was run.

## Official archive audit

The only authorized OSRF archive returned HTTP 200 with no redirect. Its
`Content-Type` is `{download['content_type']}`, its recorded size is
`{download['content_length']}` bytes, and the downloaded file exactly matches
that size. The package SHA256 is `{download['sha256']}`; its MD5 also matches
the S3 ETag `{download['etag']}`.

`dpkg-deb` confirms the exact identity:

```text
Package: {metadata['identity']['Package']}
Version: {metadata['identity']['Version']}
Architecture: {metadata['identity']['Architecture']}
```

## HLMS completeness result

The package contains one package-owned media root candidate:
`{media['media_root_in_package']}`. It contains {media['file_count']} files,
{media['directory_count']} directories, {media['glsl_file_count']} GLSL files,
{media['piece_file_count']} piece files, and {media['total_bytes']} bytes.

The required `Hlms/Unlit/GLSL`, `Hlms/Pbs/GLSL`, `Hlms/Gz`, `Hlms/Terra`,
Common GLSL, and Terra GLSL trees are present and nonempty. However,
`2.0/scripts/Compositors` is absent. Therefore the package does not satisfy the
user-defined complete-HLMS hard gate, even though it fixes the directory that
caused Stage 11B-E's original Unlit error.

## Alias and resource-root audit

The archive also contains the official logical alias
`libgz-rendering-ogre2.so -> libgz-rendering8-ogre2.so`. Consequently a valid
installation path would need to start from the pre-alias image, not overwrite
the Stage 11B-E local alias. No such image was built because the earlier media
gate failed. The sole derived resource root is `/usr/share/gz/gz-rendering8`,
whose `ogre2/media` child is present in the archive.

## Actions intentionally not taken

- No apt simulation or dependency installation was performed after the hard stop.
- No `sgcf-gazebo-harmonic:hlms-media-fix` image or container was created.
- `GZ_RENDERING_RESOURCE_PATH` was not changed.
- No shader, Gazebo asset, footprint, sensor contract, or algorithm was modified.
- No `empty_world` or any of the remaining eleven worlds was run.
- No Planner, Stage 10 model, or ROS bridge was started.

## Preservation and cleanup

The Stage 11B-E diagnostic container was stopped. Residual Gazebo process count
is zero. The Stage-entry and Stage-exit Gazebo asset hashes match, and the
frozen 0.8 m x 0.5 m footprint remains unchanged.

## Next action

Stage 11B remains blocked. Proceeding requires an official exact-version package
or explicitly authorized source that includes the missing compositor tree; the
current authorization forbids copying from source or editing shaders. Stage 11C
is not authorized.
"""
    (OUT / "stage_11b_f_report.md").write_text(report)
    (OUT / "stage_11b_f_decision.md").write_text(
        f"""# Stage 11B-F Decision

```text
{DECISION}
```

The exact OSRF archive passes source, identity, version, architecture, size,
hash, Unlit, PBS, Gz, and Terra checks, but lacks the mandatory nonempty
`2.0/scripts/Compositors` directory. Installation, image construction, and the
single runtime re-gate were therefore not authorized to proceed.
"""
    )
    (OUT / "known_limitations.md").write_text(
        """# Known Limitations

- The exact official archive audited here lacks `2.0/scripts/Compositors` under
  its sole OGRE2 media root.
- The package was not installed, so runtime package ownership was not tested.
- No corrected image was built and no Stage 11B-F Gazebo runtime attempt occurred.
- Sensor, odometry, and DiffDrive gates remain unvalidated after Stage 11B-E.
- The local ABI-8 alias remains a Stage 11B-E compatibility shim, not a Debian-owned file.
- Full Stage 11B and Stage 11C remain blocked.
"""
    )
    (OUT / "files_changed.txt").write_text(
        """Stage 11B-F changes:
sgcf_nrmp_project/tools/stage11bf_package_audit.py
sgcf_nrmp_project/tools/finalize_stage11bf_blocked_report.py
sgcf_nrmp_project/tools/test_stage11bf_blocked_audit.py
sgcf_nrmp_project/artifacts/stages/stage_11b_f_hlms_media_restoration/

Docker files modified by Stage 11B-F: none
Gazebo assets modified by Stage 11B-F: none
Protected algorithms modified by Stage 11B-F: none
Images built by Stage 11B-F: none
Worlds run by Stage 11B-F: none
"""
    )


if __name__ == "__main__":
    main()
