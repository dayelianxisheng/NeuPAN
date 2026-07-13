#!/usr/bin/env python3
"""Tests for the stopped Stage 11B-H runtime matrix audit."""

from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "sgcf_nrmp_project/artifacts/stages/stage_11b_h_full_runtime_matrix"


def load(name: str):
    return json.loads((OUT / name).read_text())


class Stage11BHBlockedRuntimeTest(unittest.TestCase):
    def test_environment_matches_stage11bf(self) -> None:
        value = load("stage11bh_environment_consistency.json")
        self.assertEqual(value["status"], "PASSED")
        self.assertTrue(value["stage11bf_match"])
        self.assertEqual(value["ldd_not_found_count"], 0)

    def test_complete_runtime_matrix_evidence(self) -> None:
        value = load("stage11bh_world_runtime_matrix.json")
        self.assertEqual(value["matrix_size"], 12)
        self.assertEqual(value["new_runtime_world_count"], 11)
        self.assertTrue(value["all_worlds_loaded"])
        self.assertEqual(value["records"][0]["evidence_source"], "STAGE_11B_F_AUTHORITY")
        for row in value["records"]:
            self.assertTrue(row["simulation_clock_advanced"])
            self.assertEqual(row["residual_process_count"], 0)

    def test_runtime_sensors(self) -> None:
        lidar = load("stage11bh_lidar_runtime_metrics.json")
        camera = load("stage11bh_camera_runtime_metrics.json")
        odometry = load("stage11bh_odometry_runtime_metrics.json")
        for scene in lidar:
            self.assertEqual(lidar[scene]["messages"], 20)
            self.assertTrue(lidar[scene]["monotonic"])
            self.assertEqual(lidar[scene]["nan_count"], 0)
            self.assertEqual(camera[scene]["messages"], 5)
            self.assertEqual((camera[scene]["width"], camera[scene]["height"]), (320, 240))
            self.assertTrue(camera[scene]["nonempty"])
            self.assertEqual(odometry[scene]["messages"], 20)
            self.assertTrue(odometry[scene]["monotonic"])

    def test_lidar_adapter_boundary(self) -> None:
        value = load("stage11bh_lidar_adapter_metrics.json")
        for metrics in value.values():
            self.assertEqual(metrics["input_count"], metrics["output_count"])
            self.assertTrue(metrics["point_order_preserved"])
            self.assertTrue(metrics["invalid_ranges_retained"])
            self.assertTrue(metrics["output_points_finite"])
            self.assertFalse(metrics["semantic_filtering"])
            self.assertFalse(metrics["world_geometry_injected"])

    def test_geometry_blocker_is_explicit(self) -> None:
        value = load("stage11bh_runtime_clearance_consistency.json")
        self.assertEqual(value["decision"], "BLOCKED_GEOMETRY_RUNTIME_CONSISTENCY")
        self.assertEqual(value["collision_classification_agreement"], 0.2)
        records = {item["scene_id"]: item for item in value["records"]}
        self.assertTrue(records["initial_collision"]["collision_classification_agreement"])
        for scene in ["single_static_obstacle", "static_corridor", "narrow_passage", "human_path_side"]:
            self.assertFalse(records[scene]["collision_classification_agreement"])
            self.assertEqual(records[scene]["runtime_clearance_m"], 0.0)

    def test_r1_contract_without_planner(self) -> None:
        value = load("stage11bh_r1_runtime_contract.json")
        self.assertEqual(value["status"], "PASSED")
        self.assertFalse(value["rgb_dropout_contract"]["semantic_contribution_enabled"])
        self.assertFalse(value["outdated_rgb_contract"]["semantic_contribution_enabled"])
        self.assertFalse(value["planner_called"])

    def test_stage11bf_evidence_integrated(self) -> None:
        value = load("stage11bh_stage11bf_evidence_integration.json")
        self.assertEqual(value["matrix_size"], 12)
        self.assertFalse(value["empty_world_rerun_as_function_gate"])
        self.assertTrue(value["empty_world_diff_drive"]["positive_v_moves_base_x_forward"])
        self.assertTrue(value["empty_world_diff_drive"]["positive_w_increases_yaw"])

    def test_frozen_assets_and_cleanup(self) -> None:
        frozen = load("stage11bh_frozen_asset_audit.json")
        cleanup = load("stage11bh_process_cleanup.json")
        self.assertEqual(frozen["entry_hash"], frozen["exit_hash"])
        self.assertFalse(frozen["gazebo_modified"])
        self.assertFalse(frozen["docker_modified_by_stage11bh"])
        self.assertFalse(frozen["planner_started"])
        self.assertFalse(frozen["stage10_loaded"])
        self.assertFalse(frozen["ros_bridge_started"])
        self.assertTrue(all(cleanup["per_scene"].values()))
        self.assertEqual(cleanup["host_residual_gz_process_count"], 0)

    def test_startup_repeats_stopped(self) -> None:
        value = load("stage11bh_runtime_startup_latency.json")
        self.assertEqual(value["status"], "NOT_COMPLETED_AFTER_IMMEDIATE_STOP")
        self.assertEqual(value["repeat_runs_executed"], 0)

    def test_all_json_parse(self) -> None:
        for path in OUT.glob("*.json"):
            with self.subTest(path=path.name):
                json.loads(path.read_text())

    def test_git_diff_check(self) -> None:
        result = subprocess.run(["git", "diff", "--check"], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
