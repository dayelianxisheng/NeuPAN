#!/usr/bin/env python3
"""Evidence tests for the Stage 11C-C shadow-mode run."""

import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "sgcf_nrmp_project/artifacts/stages/stage_11c_c_planner_shadow_mode"
SCENES = ("empty_world", "single_static_obstacle", "human_path_center", "semantic_infeasible", "initial_collision", "rgb_dropout_contract", "outdated_rgb_contract")


class Stage11CCTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.results = {s: json.loads((OUT / f"runtime/{s}/planner_result.json").read_text()) for s in SCENES}

    def test_seven_authorized_worlds(self):
        self.assertEqual(set(self.results), set(SCENES))
        self.assertTrue(all(d["status"] == "PASSED" for d in self.results.values()))

    def test_snapshots_and_evaluations(self):
        for scene, result in self.results.items():
            self.assertEqual(result["snapshot_count"], 5, scene)
            self.assertEqual(result["counts"]["evaluations"], 20, scene)

    def test_ros_core_equivalence(self):
        audit = json.loads((OUT / "stage11cc_ros_core_equivalence.json").read_text())
        self.assertTrue(audit["passed"])
        self.assertLessEqual(max(audit[k] for k in ("observable_points_max_difference", "d_geo_max_difference", "g_geo_max_difference", "semantic_margin_max_difference", "candidate_max_difference")), 1e-6)

    def test_actuation_firewall(self):
        audit = json.loads((OUT / "stage11cc_actuation_firewall.json").read_text())
        self.assertTrue(audit["passed"])
        for row in audit["scenes"].values():
            self.assertEqual(row["gazebo_nonzero_command_count"], 0)
            self.assertEqual(row["cmd_vel_publisher"], "stage11cc_zero_guard")

    def test_frames_and_sensors(self):
        self.assertTrue(json.loads((OUT / "stage11cc_runtime_frame_audit.json").read_text())["passed"])
        self.assertTrue(json.loads((OUT / "stage11cc_sensor_data_plane_regression.json").read_text())["passed"])

    def test_stationary_and_self_visibility(self):
        self.assertTrue(json.loads((OUT / "stage11cc_stationary_runtime_gate.json").read_text())["passed"])
        self.assertTrue(all(result["self_return_count"] == 0 for result in self.results.values()))

    def test_single_static_clearance(self):
        values = [r["current_clearance"] for r in self.results["single_static_obstacle"]["records"]]
        self.assertLessEqual(max(abs(value - 0.750956) for value in values), 0.02)
        self.assertFalse(any(r["current_collision"] for r in self.results["single_static_obstacle"]["records"]))

    def test_oracle_semantics(self):
        rows = self.results["human_path_center"]["records"]
        semantic = [r for r in rows if r["mode"] in ("P1", "P2")]
        self.assertTrue(all(r["semantic"]["source"] == "ORACLE_GROUND_TRUTH" and r["semantic"]["class_name"] == "HUMAN" for r in semantic))
        self.assertTrue(all(0.0 <= min(r["result"]["margin"]) <= max(r["result"]["margin"]) <= 0.35 for r in semantic))
        for index in range(20):
            group = [r for r in rows if r["evaluation_index"] == index]
            self.assertEqual(len({json.dumps(r["result"]["d_geo"]) for r in group}), 1)
            self.assertEqual(len({json.dumps(r["result"]["g_geo"]) for r in group}), 1)

    def test_semantic_infeasible(self):
        rows = [r for r in self.results["semantic_infeasible"]["records"] if r["mode"] in ("P1", "P2")]
        self.assertTrue(all(r["result"]["status"] == "GEOMETRICALLY_INFEASIBLE" for r in rows))
        self.assertTrue(all(not r["result"]["eligible"] for r in rows))

    def test_initial_collision(self):
        rows = self.results["initial_collision"]["records"]
        self.assertTrue(all(r["current_collision"] for r in rows))
        self.assertTrue(all(not r["result"]["eligible"] for r in rows))

    def test_r1_contracts(self):
        for scene, reason in (("rgb_dropout_contract", "RGB_DROPOUT"), ("outdated_rgb_contract", "OUTDATED_IMAGE")):
            rows = self.results[scene]["records"]
            for index in range(20):
                p0 = next(r for r in rows if r["evaluation_index"] == index and r["mode"] == "P0")
                p2 = next(r for r in rows if r["evaluation_index"] == index and r["mode"] == "P2")
                self.assertFalse(p2["semantic"]["semantic_valid"])
                self.assertEqual(p2["semantic"]["fallback_reason"], reason)
                self.assertFalse(p2["semantic"]["enabled"])
                self.assertEqual(max(p2["result"]["margin"]), 0.0)
                self.assertEqual(p0["result"]["candidate"], p2["result"]["candidate"])
                self.assertEqual(p0["result"]["d_geo"], p2["result"]["d_geo"])
                self.assertEqual(p0["result"]["g_geo"], p2["result"]["g_geo"])

    def test_process_cleanup(self):
        self.assertTrue(json.loads((OUT / "stage11cc_process_cleanup.json").read_text())["passed"])

    def test_latency_hard_gate(self):
        audit = json.loads((OUT / "stage11cc_planner_latency.json").read_text())
        self.assertTrue(audit["passed"], f"blocked scenes: {audit['blocked_scenes']}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
