"""Fast artifact and protocol regression tests for Stage 15B."""

import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "sgcf_nrmp_project/artifacts/stages/stage_15b_p0_navigation_baseline"


class Stage15BTests(unittest.TestCase):
    def test_static_scene_success_thresholds(self):
        summary = json.loads((OUT / "stage15b_success_summary.json").read_text())
        scenes = summary["scenes"]
        self.assertEqual(scenes["empty_world"]["successes"], 3)
        self.assertEqual(scenes["single_static_obstacle"]["successes"], 3)
        self.assertEqual(scenes["static_corridor"]["successes"], 3)
        self.assertGreaterEqual(scenes["narrow_passage"]["successes"], 2)

    def test_safety_contract(self):
        safety = json.loads((OUT / "stage15b_safety_summary.json").read_text())
        self.assertTrue(safety["passed"])
        self.assertEqual(safety["collision_count"], 0)
        self.assertEqual(safety["improper_execution_count"], 0)
        self.assertLessEqual(safety["maximum_command_error"], 1e-9)
        self.assertLessEqual(safety["maximum_replay_error"], 1e-6)
        self.assertTrue(safety["all_zero_stop"])

    def test_protocol_did_not_change_core_safety(self):
        protocol = json.loads((OUT / "stage15b_protocol_audit.json").read_text())
        self.assertFalse(protocol["planner_core_modified"])
        self.assertFalse(protocol["geometry_modified"])
        self.assertFalse(protocol["d_safe_modified"])
        self.assertTrue(protocol["full_horizon_recheck_enabled"])
        self.assertEqual(protocol["watchdog_ms"], 200)

    def test_expired_candidate_is_zeroed(self):
        gate = json.loads(
            (
                OUT
                / "runtime/final_single_static_obstacle_seed101_p0/safe_gate_result.json"
            ).read_text()
        )
        expired = [row for row in gate["command_log"] if row["reason"] == "CANDIDATE_EXPIRED"]
        self.assertTrue(expired)
        self.assertTrue(all(row["v"] == 0.0 and row["w"] == 0.0 for row in expired))


if __name__ == "__main__":
    unittest.main()
