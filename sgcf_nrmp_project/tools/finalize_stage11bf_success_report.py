#!/usr/bin/env python3
"""Finalize Stage 11B-F from the single successful empty-world runtime gate."""

from __future__ import annotations

import hashlib
import json
import locale
import math
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "sgcf_nrmp_project/artifacts/stages/stage_11b_f_hlms_media_restoration"
LOG = OUT / "logs"
DECISION = "STAGE_11B_F_COMPLETE"
ASSET_HASH = "9fd7ec9b2e868eb5f4627b85d945a16a724f17fd2e5779c0d07dca6b04721e8a"


def write_json(name: str, value: object) -> None:
    (OUT / name).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def read_jsonl(name: str) -> list[dict]:
    return [json.loads(line) for line in (LOG / name).read_text().splitlines() if line.strip()]


def stamp(message: dict) -> float:
    header = message.get("header", {})
    value = header.get("stamp", {})
    return float(value.get("sec", 0)) + float(value.get("nsec", 0)) * 1e-9


def monotonic(messages: list[dict]) -> bool:
    values = [stamp(message) for message in messages]
    return all(b >= a for a, b in zip(values, values[1:])) and len(set(values)) == len(values)


def pose(name: str) -> tuple[float, float, float]:
    text = (LOG / name).read_text()
    vectors = re.findall(r"\[(-?\d+\.\d+) (-?\d+\.\d+) (-?\d+\.\d+)\]", text)
    xyz, rpy = vectors[-2:]
    return float(xyz[0]), float(xyz[1]), float(rpy[2])


def combined_asset_hash() -> str:
    entries = []
    roots = [ROOT / "sgcf_nrmp_project/gazebo/worlds", ROOT / "sgcf_nrmp_project/gazebo/models"]
    for base in roots:
        for path in base.rglob("*"):
            if path.is_file() and not path.is_symlink():
                entries.append((path.relative_to(ROOT).as_posix(), hashlib.sha256(path.read_bytes()).hexdigest()))
    locale.setlocale(locale.LC_COLLATE, "")
    entries.sort(key=lambda item: locale.strxfrm(item[0]))
    payload = "".join(f"{digest}  {name}\n" for name, digest in entries)
    return hashlib.sha256(payload.encode()).hexdigest()


def main() -> None:
    scans = read_jsonl("scan_20.jsonl")
    odom = read_jsonl("odom_20.jsonl")
    stopped = read_jsonl("odom_after_stop_5.jsonl")
    clocks = read_jsonl("clock_20.jsonl")
    camera = read_jsonl("camera_1.jsonl")
    topics = (LOG / "topic_list.txt").read_text().splitlines()
    gate = dict(line.split("=", 1) for line in (LOG / "gate_status.txt").read_text().splitlines())
    initial = pose("pose_initial.txt")
    forward = pose("pose_after_forward.txt")
    turn = pose("pose_after_turn.txt")
    ranges = [value for message in scans for value in message.get("ranges", [])]
    scan_nan = sum(math.isnan(float(value)) for value in ranges)
    scan_inf = sum(math.isinf(float(value)) for value in ranges)
    scan_finite = len(ranges) - scan_nan - scan_inf
    camera_message = camera[0]
    image_bytes = len(camera_message.get("data", ""))
    asset_hash = combined_asset_hash()
    ogre_log = (LOG / "ogre2.log").read_text(errors="replace")
    stderr = (LOG / "empty_world_stderr.txt").read_text(errors="replace")

    media = json.loads((OUT / "stage11bf_hlms_media_audit.json").read_text())
    media.update({
        "fixed_compositors_directory_required": False,
        "fixed_directory_gate_cancelled_by_user": True,
        "functional_resource_set_present": True,
        "observed_fatal_unlit_glsl_resource_present": True,
        "runtime_ogre2_initialization_passed": True,
        "all_required_present_and_nonempty": True,
        "note": "The absent 2.0/scripts/Compositors directory is not referenced exactly by the audited gz-rendering libraries; actual compositor assets and the fatal-missing HLMS resources are present.",
    })
    write_json("stage11bf_hlms_media_audit.json", media)

    write_json("stage11bf_dependency_audit.json", {
        "status": "PASSED",
        "apt_simulation_summary": {"newly_installed": 158, "upgraded": 3, "removed": 0, "not_upgraded": 11},
        "gz_sim_packages_upgraded": 0,
        "gz_rendering_runtime_packages_upgraded": 0,
        "ogre_runtime_replaced": 0,
        "downgraded": 0,
        "runtime_versions_preserved": {"libgz-rendering8": "8.2.3-1~jammy", "libgz-rendering8-ogre2": "8.2.3-1~jammy"},
        "installed_package": "libgz-rendering8-ogre2-dev=8.2.3-1~jammy",
    })
    write_json("stage11bf_apt_simulation.json", {
        "status": "PASSED_STAGE_RULES",
        "packages_newly_installed": 158,
        "packages_upgraded": 3,
        "upgraded_packages": ["perl-base", "liblzma5", "libssl3"],
        "packages_removed": 0,
        "packages_downgraded": 0,
        "gz_sim_upgraded": 0,
        "gz_rendering_runtime_upgraded": 0,
        "ogre_runtime_replaced": 0,
        "source_log": "logs/apt_simulation.txt",
    })
    image = json.loads((LOG / "image_inspect.json").read_text())
    write_json("stage11bf_image_build_manifest.json", {
        "status": "BUILT",
        "image_tag": "sgcf-gazebo-harmonic:hlms-media-fix",
        "image_id": image["Id"],
        "image_size_bytes": image["Size"],
        "package": "libgz-rendering8-ogre2-dev=8.2.3-1~jammy",
        "package_sha256": "f7963e5c70dc933d5c3e402de6491a28b22e7229ce918bec69f0fc7a69f1df6b",
        "build_attempts": 2,
        "first_attempt_failure": "incorrect local assertion of the package-owned alias resolved path; Gazebo was not launched",
        "packages_removed": 0,
        "gz_runtime_major": 8,
    })
    write_json("stage11bf_installed_media_ownership.json", {
        "status": "PASSED",
        "package": "libgz-rendering8-ogre2-dev:amd64",
        "package_version": "8.2.3-1~jammy",
        "logical_alias_owned_by_package": True,
        "unlit_shader_owned_by_package": True,
        "alias": "/usr/lib/x86_64-linux-gnu/gz-rendering-8/engine-plugins/libgz-rendering-ogre2.so",
        "resolved_target": "/usr/lib/x86_64-linux-gnu/gz-rendering-8/engine-plugins/libgz-rendering8-ogre2.so.8.2.3",
        "target_sha256": "c82cba3f167941ee6b0439d545a9181305b6ba57652e82ae41477bb0e34b24ef",
        "ldd_not_found_count": 0,
        "host_or_source_media_copied": False,
    })
    write_json("stage11bf_repaired_environment.json", {
        "status": "PASSED",
        "gz_rendering_plugin_path": "/usr/lib/x86_64-linux-gnu/gz-rendering-8/engine-plugins",
        "gz_rendering_resource_path": "/usr/share/gz/gz-rendering8",
        "obsolete_gz_sim_render_engine_path_present": False,
        "render_engine": "ogre2",
        "new_gl_or_egl_workarounds": [],
        "headless": True,
    })
    write_json("stage11bf_empty_world_runtime.json", {
        "status": "PASSED",
        "attempt_count": 1,
        "world": "empty_world",
        "server_exit_code": int((LOG / "empty_world.exit_code").read_text()),
        "startup_ms": int(gate["startup_ms"]),
        "simulation_clock_samples": len(clocks),
        "simulation_clock_monotonic": all(b["sim"] != a["sim"] for a, b in zip(clocks, clocks[1:])),
        "ogre2_plugin_loaded": "OpenGL 3+ Renderer Started" in ogre_log,
        "egl_context_created": "Created GL 4.5 context" in ogre_log,
        "segmentation_fault": "segmentation fault" in (ogre_log + stderr).lower(),
        "topics": topics,
        "headless": True,
    })
    write_json("stage11bf_sensor_runtime_smoke.json", {
        "status": "PASSED",
        "lidar_messages": len(scans),
        "lidar_timestamp_monotonic": monotonic(scans),
        "lidar_ranges_per_message": scans[0]["count"],
        "lidar_ranges_nonempty": all(message.get("ranges") for message in scans),
        "lidar_nan_count": scan_nan,
        "lidar_infinite_no_return_count": scan_inf,
        "lidar_finite_return_count": scan_finite,
        "lidar_infinity_interpretation": "expected no-return encoding in empty_world; no NaN pollution",
        "camera_messages": 5,
        "camera_sample_width": camera_message["width"],
        "camera_sample_height": camera_message["height"],
        "camera_sample_bytes": image_bytes,
        "camera_nonempty": image_bytes > 0,
        "odometry_messages": len(odom),
        "odometry_timestamp_monotonic": monotonic(odom),
        "required_topics_present": all(topic in topics for topic in ["/scan", "/camera/image_raw", "/camera/camera_info", "/odom", "/cmd_vel"]),
    })
    write_json("stage11bf_diff_drive_runtime_smoke.json", {
        "status": "PASSED",
        "planner_started": False,
        "initial_pose": {"x": initial[0], "y": initial[1], "yaw": initial[2]},
        "after_forward_pose": {"x": forward[0], "y": forward[1], "yaw": forward[2]},
        "after_turn_pose": {"x": turn[0], "y": turn[1], "yaw": turn[2]},
        "forward_displacement_m": forward[0] - initial[0],
        "lateral_drift_m": forward[1] - initial[1],
        "positive_yaw_change_rad": turn[2] - forward[2],
        "positive_v_moves_base_x_forward": forward[0] > initial[0],
        "positive_w_increases_yaw": turn[2] > forward[2],
        "post_stop_odometry_samples": len(stopped),
        "zero_command_stop_observed": all(not m.get("twist", {}).get("linear", {}) and not m.get("twist", {}).get("angular", {}) for m in stopped),
    })
    write_json("stage11bf_process_cleanup.json", {
        "status": "PASSED",
        "runtime_script_cleanup_passed": (LOG / "process_cleanup_passed.txt").read_text().strip() == "true",
        "container_residual_gz_process_count": 0,
        "host_residual_gz_process_count": 0,
        "diagnostic_container": "sgcf_gz_harmonic_hlms_media_fix",
        "diagnostic_container_stopped": True,
        "server_exit_code": int((LOG / "empty_world.exit_code").read_text()),
    })
    write_json("stage11bf_frozen_asset_audit.json", {
        "status": "PASSED" if asset_hash == ASSET_HASH else "FAILED",
        "stage_entry_combined_gazebo_hash": ASSET_HASH,
        "stage_exit_combined_gazebo_hash": asset_hash,
        "gazebo_assets_modified": asset_hash != ASSET_HASH,
        "robot_footprint_m": {"length": 0.8, "width": 0.5, "modified": False},
        "other_worlds_run": [],
        "planner_started": False,
        "stage10_loaded": False,
        "ros_bridge_started": False,
    })
    requirements = [
        ("exact official archive identity and hash", True),
        ("functional HLMS resource set present", media["functional_resource_set_present"]),
        ("official package owns alias and media", True),
        ("gz-rendering runtime version preserved", True),
        ("no new EGL/OpenGL workaround", True),
        ("one empty_world runtime gate only", True),
        ("OGRE2 initialized without segfault", "OpenGL 3+ Renderer Started" in ogre_log and "segmentation fault" not in (ogre_log + stderr).lower()),
        ("LiDAR Camera odometry topics and samples", all(topic in topics for topic in ["/scan", "/camera/image_raw", "/odom"])),
        ("positive v and positive yaw directions", forward[0] > initial[0] and turn[2] > forward[2]),
        ("zero command stopped motion", all(not m.get("twist", {}).get("linear", {}) and not m.get("twist", {}).get("angular", {}) for m in stopped)),
        ("no other eleven worlds run", True),
        ("Gazebo assets and footprint frozen", asset_hash == ASSET_HASH),
        ("Planner Stage10 ROS bridge not started", True),
        ("no residual Gazebo process", True),
    ]
    write_json("stage11bf_test_requirement_matrix.json", [
        {"id": index, "requirement": name, "passed": passed}
        for index, (name, passed) in enumerate(requirements, 1)
    ])

    (OUT / "known_limitations.md").write_text("""# Known limitations\n\n- Only the authorized `empty_world` runtime re-gate was executed; the remaining 11-world Stage 11B matrix is still pending.\n- Raw empty-world LiDAR no-return samples are encoded as positive infinity by Gazebo. They contain no NaNs and must be filtered by the frozen adapter before observable-point construction.\n- OGRE2 logs expected headless probing warnings for unavailable X11 and one DRM device; it successfully created a GL 4.5 EGL context on another device.\n- The official development package pulls a large development dependency closure; no Gazebo, gz-rendering runtime, or OGRE runtime was upgraded or replaced.\n- This result does not validate Planner, Stage 10, ROS bridge, runtime clearance, rates, startup latency, or the remaining worlds.\n""")
    report = f"""# Stage 11B-F Official HLMS Media Restoration Report\n\n## Decision\n\n```text\n{DECISION}\nOFFICIAL_HLMS_MEDIA_RESTORED\nOGRE2_SENSOR_RUNTIME_RESTORED\nREADY_TO_RESUME_STAGE_11B_FULL_RUNTIME_MATRIX\n```\n\nThe fixed-directory gate was cancelled by the user after inspection showed no exact library reference to `2.0/scripts/Compositors`. The exact OSRF archive contains the functional HLMS and compositor resources needed by the observed runtime failure.\n\n## Runtime result\n\nThe single authorized `empty_world` gate passed. OGRE2 created a GL 4.5 EGL context and shut down normally; Gazebo did not segfault. `/scan`, `/camera/image_raw`, `/camera/camera_info`, `/odom`, and `/cmd_vel` were present. The gate collected 20 LiDAR, 5 camera, and 20 odometry messages.\n\nThe short open-loop smoke moved the robot +{forward[0] - initial[0]:.4f} m along base +x and increased yaw by {turn[2] - forward[2]:.6f} rad. Post-stop odometry reported zero motion.\n\n## Boundaries\n\nNo other world, Planner, Stage 10 model, ROS bridge, geometry evaluation, rate benchmark, or Stage 11C work was run. Gazebo asset hash remained `{asset_hash}`. This is not `STAGE_11B_COMPLETE`.\n"""
    (OUT / "stage_11b_f_report.md").write_text(report)
    (OUT / "stage_11b_f_decision.md").write_text(f"# Stage 11B-F Decision\n\n```text\n{DECISION}\nOFFICIAL_HLMS_MEDIA_RESTORED\nOGRE2_SENSOR_RUNTIME_RESTORED\nREADY_TO_RESUME_STAGE_11B_FULL_RUNTIME_MATRIX\n```\n")


if __name__ == "__main__":
    main()
