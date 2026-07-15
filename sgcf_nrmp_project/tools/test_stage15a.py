"""Fast regression tests for Stage 15A evidence."""
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "sgcf_nrmp_project/artifacts/stages/stage_15a_baseline_feasibility_analysis"


class Stage15ARegression(unittest.TestCase):
    def load(self, name):
        return json.loads((OUT / name).read_text())

    def test_all_runs_have_confirmed_classification(self):
        data = self.load("stage15a_failure_classification.json")
        self.assertEqual(data["run_count"], 70)
        self.assertEqual(len(data["runs"]), 70)
        self.assertNotIn("UNKNOWN", data["classification_counts"])

    def test_protocol_floor_is_documented(self):
        data = self.load("stage15a_success_protocol_audit.json")
        self.assertEqual(data["defect"], "ACTIVE_WINDOW_TOO_SHORT_FOR_REFERENCE_SPEED_GOAL_COMPLETION")
        self.assertLess(data["active_command_window_s"], data["reference_speed_shortest_completion_time_s"])
        self.assertTrue(data["goal_reference_path_endpoint_consistent"])

    def test_three_safe_p0_reruns(self):
        data = self.load("stage15a_minimal_p0_rerun.json")
        self.assertEqual(data["run_count"], 3)
        for row in data["runs"]:
            self.assertEqual(row["collision_count"], 0)
            self.assertEqual(row["stale_late_ineligible_executed"], 0)
            self.assertTrue(row["zero_stop"])

    def test_partial_progress_without_goal_success(self):
        data = self.load("stage15a_minimal_p0_rerun.json")
        self.assertTrue(any(row["goal_progress_m"] >= 0.05 for row in data["runs"]))
        self.assertFalse(any(row["goal_reached"] for row in data["runs"]))

    def test_stage16_remains_blocked(self):
        data = self.load("stage15a_stage16_readiness.json")
        self.assertFalse(data["stage16_ready"])
        self.assertEqual(data["decision"], "STAGE_15A_COMPLETE_WITH_KNOWN_PLANNER_LIMITATIONS")


if __name__ == "__main__":
    unittest.main()
