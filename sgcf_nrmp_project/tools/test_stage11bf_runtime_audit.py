#!/usr/bin/env python3
"""Tests for the completed Stage 11B-F single-world runtime gate."""

from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "sgcf_nrmp_project/artifacts/stages/stage_11b_f_hlms_media_restoration"


def load(name: str) -> dict:
    return json.loads((OUT / name).read_text())


class Stage11BFRuntimeAuditTest(unittest.TestCase):
    def test_exact_official_package(self) -> None:
        audit = load("stage11bf_download_audit.json")
        metadata = load("stage11bf_package_metadata.json")
        self.assertTrue(audit["passed"])
        self.assertEqual(audit["sha256"], "f7963e5c70dc933d5c3e402de6491a28b22e7229ce918bec69f0fc7a69f1df6b")
        self.assertTrue(metadata["identity_exact_match"])

    def test_functional_hlms_media(self) -> None:
        audit = load("stage11bf_hlms_media_audit.json")
        self.assertTrue(audit["fixed_directory_gate_cancelled_by_user"])
        self.assertTrue(audit["functional_resource_set_present"])
        self.assertTrue(audit["runtime_ogre2_initialization_passed"])

    def test_package_owned_install(self) -> None:
        audit = load("stage11bf_installed_media_ownership.json")
        self.assertEqual(audit["package_version"], "8.2.3-1~jammy")
        self.assertTrue(audit["logical_alias_owned_by_package"])
        self.assertTrue(audit["unlit_shader_owned_by_package"])
        self.assertEqual(audit["ldd_not_found_count"], 0)
        self.assertFalse(audit["host_or_source_media_copied"])

    def test_runtime_and_topics(self) -> None:
        runtime = load("stage11bf_empty_world_runtime.json")
        sensors = load("stage11bf_sensor_runtime_smoke.json")
        self.assertEqual(runtime["attempt_count"], 1)
        self.assertTrue(runtime["ogre2_plugin_loaded"])
        self.assertTrue(runtime["egl_context_created"])
        self.assertFalse(runtime["segmentation_fault"])
        self.assertTrue(sensors["required_topics_present"])
        self.assertGreaterEqual(sensors["lidar_messages"], 20)
        self.assertGreaterEqual(sensors["camera_messages"], 5)
        self.assertGreaterEqual(sensors["odometry_messages"], 20)
        self.assertEqual(sensors["lidar_nan_count"], 0)

    def test_diff_drive(self) -> None:
        audit = load("stage11bf_diff_drive_runtime_smoke.json")
        self.assertTrue(audit["positive_v_moves_base_x_forward"])
        self.assertTrue(audit["positive_w_increases_yaw"])
        self.assertTrue(audit["zero_command_stop_observed"])
        self.assertFalse(audit["planner_started"])

    def test_frozen_boundary_and_cleanup(self) -> None:
        frozen = load("stage11bf_frozen_asset_audit.json")
        cleanup = load("stage11bf_process_cleanup.json")
        self.assertEqual(frozen["status"], "PASSED")
        self.assertEqual(frozen["other_worlds_run"], [])
        self.assertFalse(frozen["planner_started"])
        self.assertFalse(frozen["stage10_loaded"])
        self.assertFalse(frozen["ros_bridge_started"])
        self.assertEqual(cleanup["container_residual_gz_process_count"], 0)

    def test_all_json_parse(self) -> None:
        for path in OUT.glob("*.json"):
            with self.subTest(path=path.name):
                json.loads(path.read_text())

    def test_git_diff_check(self) -> None:
        result = subprocess.run(["git", "diff", "--check"], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
