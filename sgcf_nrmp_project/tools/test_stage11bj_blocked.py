"""Regression checks for the stopped Stage 11B-J runtime rerun."""

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "artifacts/stages/stage_11b_j_full_runtime_matrix_rerun"


def load(name: str) -> dict:
    return json.loads((ARTIFACTS / name).read_text(encoding="utf-8"))


class Stage11BJBlockedEvidenceTest(unittest.TestCase):
    def test_immutable_image_binding(self) -> None:
        data = load("stage11bj_runtime_image_binding.json")
        self.assertEqual(data["status"], "PASSED")
        self.assertFalse(data["created_using_mutable_tag"])
        self.assertEqual(data["container_image_id"], data["immutable_image_id"])
        self.assertTrue(data["immutable_image_id"].startswith("sha256:99de6309"))

    def test_matrix_stopped_at_first_geometry_gate(self) -> None:
        data = load("stage11bj_world_runtime_matrix.json")
        self.assertEqual(data["world_count"], 12)
        self.assertEqual(data["runtime_result_count"], 11)
        self.assertEqual(data["missing_or_incomplete_scenes"], ["rgb_dropout_contract"])
        self.assertEqual(data["decision"], "BLOCKED_GEOMETRY_RUNTIME_CONSISTENCY")

    def test_clearance_failures_are_explicit(self) -> None:
        data = load("stage11bj_runtime_clearance_consistency.json")
        records = {record["scene_id"]: record for record in data["records"]}
        self.assertEqual(set(data["failed_scenes"]), {"static_corridor", "narrow_passage"})
        self.assertGreater(records["static_corridor"]["absolute_error_m"], 0.02)
        self.assertGreater(records["narrow_passage"]["absolute_error_m"], 0.02)
        self.assertTrue(records["single_static_obstacle"]["threshold_passed"])
        self.assertTrue(records["human_path_side"]["threshold_passed"])
        self.assertTrue(records["initial_collision"]["runtime_collision"])

    def test_visibility_fix_and_external_collision_remain_valid(self) -> None:
        data = load("stage11bj_lidar_self_visibility_regression.json")
        self.assertTrue(data["all_completed_scenes_self_return_zero"])
        self.assertTrue(data["initial_collision_external_visible"])

    def test_follow_on_gates_not_fabricated(self) -> None:
        startup = load("stage11bj_runtime_startup_latency.json")
        r1 = load("stage11bj_r1_runtime_contract.json")
        self.assertEqual(startup["status"], "NOT_EXECUTED_DUE_TO_EARLIER_GEOMETRY_STOP")
        self.assertEqual(startup["additional_runs_executed"], 0)
        self.assertNotEqual(r1["status"], "PASS")

    def test_assets_and_protected_runtime_boundaries(self) -> None:
        data = load("stage11bj_frozen_asset_audit.json")
        self.assertTrue(data["robot_hash_equal"])
        self.assertTrue(data["world_hashes_equal"])
        self.assertFalse(data["gazebo_modified_by_stage11bj"])
        self.assertFalse(data["docker_modified_by_stage11bj"])
        self.assertFalse(data["core_modified"])
        self.assertFalse(data["planner_started"])
        self.assertFalse(data["stage10_loaded"])
        self.assertFalse(data["ros_bridge_started"])
        self.assertFalse(data["motion_commands_sent"])

    def test_process_cleanup(self) -> None:
        data = load("stage11bj_process_cleanup.json")
        self.assertTrue(data["stage_container_stopped"])
        self.assertEqual(data["final_host_residual_gazebo_process_count"], 0)

    def test_all_json_documents_parse(self) -> None:
        for path in ARTIFACTS.glob("*.json"):
            with self.subTest(path=path.name):
                json.loads(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
