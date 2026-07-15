import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "sgcf_nrmp_project/artifacts/stages/stage_11c_final_evaluation"


class FinalEvaluationTests(unittest.TestCase):
    def load(self, name):
        return json.loads((OUT / name).read_text())

    def test_scene_counts(self):
        d = self.load("stage11c_scene_outcome_matrix.json")
        self.assertEqual((d["pass_count"], d["pass_with_known_limitation_count"]), (8, 4))

    def test_no_navigation_overclaim(self):
        self.assertFalse(self.load("stage11c_scene_outcome_matrix.json")["navigation_success_claimed"])

    def test_safety_counts(self):
        d = self.load("stage11c_safety_summary.json")
        for key in ("planner_induced_collision_count", "robot_self_return_count", "stale_candidate_executed_count", "late_candidate_executed_count", "ineligible_candidate_executed_count"):
            self.assertEqual(d[key], 0)

    def test_command_chain_exact(self):
        d = self.load("stage11c_safety_summary.json")
        self.assertEqual((d["candidate_to_ros_max_abs_error"], d["ros_to_gazebo_max_abs_error"]), (0.0, 0.0))

    def test_replay_exact(self):
        self.assertEqual(self.load("stage11c_safety_summary.json")["ros_core_replay_max_abs_error"], 0.0)

    def test_initial_collision(self):
        self.assertEqual(self.load("stage11c_safety_summary.json")["initial_collision_status"], "EMERGENCY_STOP")

    def test_recheck_and_recovery(self):
        d = self.load("stage11c_safety_summary.json")
        self.assertTrue(d["full_horizon_exact_geometry_recheck_enabled"] and d["stage09c_safe_nominal_recovery_enabled"])

    def test_r1(self):
        d = self.load("stage11c_r1_failure_summary.json")
        self.assertTrue(d["passed"])
        self.assertEqual(d["maximum_p0_fallback_numeric_difference"], 0.0)

    def test_semantic_boundary(self):
        d = self.load("stage11c_semantic_summary.json")
        self.assertTrue(d["simulation_only"])
        self.assertFalse(d["stage10_started"] or d["predicted_checkpoint_loaded"])

    def test_semantic_navigation_not_claimed(self):
        self.assertFalse(self.load("stage11c_semantic_summary.json")["semantic_navigation_success_demonstrated"])

    def test_failure_latency_contained(self):
        d = self.load("stage11c_latency_summary.json")
        self.assertEqual(d["semantic_infeasible_classification"], "KNOWN_FAILURE_PATH_LATENCY_LIMITATION")
        self.assertFalse(d["semantic_infeasible_command_eligible"] or d["late_result_entered_cmd_vel_or_gazebo"])

    def test_vehicle_latency(self):
        self.assertLess(self.load("stage11c_latency_summary.json")["vehicle_path_p2_p95_ms"], 200.0)

    def test_local_images(self):
        d = self.load("stage11c_image_and_environment_manifest.json")
        self.assertTrue(d["gazebo"]["image_id"].startswith("sha256:99de6309"))
        self.assertEqual(d["planner"]["device"], "cpu")

    def test_cleanup(self):
        self.assertTrue(self.load("stage11c_process_cleanup_summary.json")["passed"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
