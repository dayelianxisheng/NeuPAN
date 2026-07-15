"""Fast Stage 15C artifact and frozen-contract tests."""

import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "sgcf_nrmp_project/artifacts/stages/stage_15c_oracle_semantic_reevaluation"


class Stage15CTests(unittest.TestCase):
    def load(self, name):
        return json.loads((OUT / name).read_text())

    def test_pair_and_baseline_counts(self):
        manifest = self.load("stage15c_experiment_manifest.json")
        self.assertEqual(manifest["pair_count"], 30)
        self.assertEqual(manifest["run_count"], 60)
        summary = self.load("stage15c_success_and_collision_summary.json")
        self.assertEqual(summary["modes"]["P0"]["successes"], 30)

    def test_safety(self):
        safety = self.load("stage15c_safety_summary.json")
        self.assertTrue(safety["passed"])
        self.assertEqual(safety["planner_induced_collision_count"], 0)
        self.assertEqual(safety["stale_late_ineligible_execution_count"], 0)
        self.assertLessEqual(safety["candidate_ros_gazebo_max_abs_error"], 1e-9)
        self.assertTrue(safety["all_zero_stop"])

    def test_geometry_invariance(self):
        geometry = self.load("stage15c_geometry_invariance.json")
        self.assertEqual(geometry["d_geo_max_difference"], 0.0)
        self.assertEqual(geometry["g_geo_max_difference"], 0.0)
        self.assertFalse(geometry["observable_points_changed_by_semantics"])
        self.assertLessEqual(geometry["ros_core_replay_max_abs_error"], 1e-6)

    def test_negative_decision(self):
        comparison = self.load("stage15c_statistical_comparison.json")
        self.assertFalse(comparison["oracle_semantic_benefit_gate"])
        decision = (OUT / "stage_15c_decision.md").read_text()
        self.assertIn("STAGE_15C_COMPLETE_WITH_NEGATIVE_RESULT", decision)
        self.assertIn("STAGE_16_SKIPPED_DUE_TO_UNESTABLISHED_ORACLE_BENEFIT", decision)

    def test_oracle_only(self):
        manifest = self.load("stage15c_experiment_manifest.json")
        self.assertEqual(manifest["semantic_source"], "ORACLE_GROUND_TRUTH")
        self.assertTrue(manifest["simulation_only"])
        self.assertTrue(manifest["not_stage10_prediction"])


if __name__ == "__main__":
    unittest.main()
