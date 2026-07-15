import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "sgcf_nrmp_project/artifacts/stages/stage_11c_d3a_semantic_safety_completion"


class Stage11CD3ATests(unittest.TestCase):
    def load(self, name):
        return json.loads((OUT / name).read_text())

    def test_semantic_infeasible_zero_fallback(self):
        self.assertTrue(self.load("stage11cd3a_semantic_infeasible.json")["zero_fallback_passed"])

    def test_semantic_infeasible_not_executed(self):
        d = self.load("stage11cd3a_semantic_infeasible.json")
        self.assertEqual(d["late_or_ineligible_executed"], 0)
        self.assertEqual(d["nonzero_actuation_count"], 0)

    def test_ros_core_replay(self):
        self.assertLessEqual(self.load("stage11cd3a_ros_core_equivalence.json")["all_completed_run_max"], 1e-6)

    def test_rgb_dropout(self):
        d = self.load("stage11cd3a_rgb_dropout.json")
        self.assertEqual(d["fallback_reason"], "RGB_DROPOUT")
        self.assertTrue(d["semantic_invalid_contract_passed"])

    def test_rgb_dropout_equivalence(self):
        d = self.load("stage11cd3a_rgb_dropout.json")["pair_equivalence"]
        self.assertLessEqual(max(d["d_geo_max"], d["g_geo_max"], d["candidate_max"]), 1e-6)

    def test_outdated(self):
        d = self.load("stage11cd3a_outdated_rgb.json")
        self.assertEqual(d["fallback_reason"], "OUTDATED_IMAGE")
        self.assertTrue(d["simulation_time_contract"])

    def test_outdated_equivalence(self):
        d = self.load("stage11cd3a_outdated_rgb.json")["pair_equivalence"]
        self.assertLessEqual(max(d["d_geo_max"], d["g_geo_max"], d["candidate_max"]), 1e-6)

    def test_r1_margin_zero(self):
        for name in ("stage11cd3a_rgb_dropout.json", "stage11cd3a_outdated_rgb.json"):
            self.assertEqual(self.load(name)["semantic_margin_max"], 0.0)

    def test_probe_order(self):
        self.assertEqual(self.load("stage11cd3a_feasible_scene_probe.json")["order"], ["human_path_side", "vehicle_path"])

    def test_human_side_safe_rejection(self):
        d = self.load("stage11cd3a_feasible_scene_probe.json")["human_path_side"]
        self.assertEqual(d["p2_eligible"], 0)

    def test_vehicle_selected(self):
        d = self.load("stage11cd3a_feasible_scene_probe.json")
        self.assertEqual(d["selected"], "vehicle_path")
        self.assertGreater(d["vehicle_path"]["p2_eligible"], 0)

    def test_vehicle_latency(self):
        self.assertLessEqual(self.load("stage11cd3a_feasible_scene_probe.json")["vehicle_path"]["p95_ms"], 200.0)

    def test_vehicle_nonzero(self):
        d = self.load("stage11cd3a_feasible_scene_probe.json")["vehicle_path_closed_loop"]["p2_gate"]
        self.assertGreater(d["nonzero_actuation_count"], 0)

    def test_vehicle_safe(self):
        d = self.load("stage11cd3a_feasible_scene_probe.json")["vehicle_path_closed_loop"]["p2_gate"]
        self.assertEqual((d["collision_count"], d["stale_count"], d["backlog_count"]), (0, 0, 0))

    def test_candidate_chain(self):
        d = self.load("stage11cd3a_feasible_scene_probe.json")["vehicle_path_closed_loop"]["p2_gate"]
        self.assertTrue(d["published_candidate_match"])
        self.assertLessEqual(d["candidate_to_ros_max_abs_error"], 1e-9)
        self.assertLessEqual(d["ros_to_gazebo_max_abs_error"], 1e-9)

    def test_zero_stop(self):
        d = self.load("stage11cd3a_feasible_scene_probe.json")["vehicle_path_closed_loop"]
        self.assertTrue(d["p0_gate"]["zero_stop_passed"] and d["p2_gate"]["zero_stop_passed"])

    def test_exact_geometry_invariant(self):
        d = self.load("stage11cd3a_geometry_invariance.json")
        self.assertFalse(d["semantic_changes_exact_geometry"])
        self.assertEqual(d["vehicle_path_shadow"]["same_nominal_d_geo_max"], 0.0)

    def test_expected_known_limitation(self):
        d = self.load("stage11cd3a_feasible_scene_probe.json")["vehicle_path_closed_loop"]
        self.assertFalse(d["semantic_nonzero_closed_loop_demonstrated"])
        self.assertEqual(d["classification"], "KNOWN_PLANNER_SEMANTIC_FEASIBILITY_LIMITATION")

    def test_cleanup(self):
        self.assertTrue(self.load("stage11cd3a_process_cleanup.json")["passed"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
