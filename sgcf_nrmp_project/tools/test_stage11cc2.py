import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "sgcf_nrmp_project/artifacts/stages/stage_11c_c2_deadline_watchdog"

class WatchdogTests(unittest.TestCase):
    def load(self, name): return json.loads((OUT / name).read_text())
    def test_watchdog(self): self.assertTrue(self.load("stage11cc2_deadline_watchdog.json")["passed"])
    def test_late_gate(self): self.assertTrue(self.load("stage11cc2_late_candidate_gate.json")["passed"])
    def test_equivalence(self): self.assertTrue(self.load("stage11cc2_ros_core_equivalence.json")["passed"])
    def test_cleanup(self): self.assertTrue(self.load("stage11cc2_process_cleanup.json")["passed"])
    def test_semantic_deadline_captured(self):
        d=self.load("stage11cc2_deadline_watchdog.json")["semantic_infeasible"]
        self.assertGreater(d["deadline_miss_count"],0); self.assertEqual(d["late_actuation_eligible_count"],0)
    def test_no_backlog(self):
        d=self.load("stage11cc2_deadline_watchdog.json")
        for scene in ("single_static_obstacle","human_path_center","semantic_infeasible"):
            self.assertFalse(d[scene]["sustained_backlog"]); self.assertLessEqual(d[scene]["pending_queue_depth_max"],1)

if __name__ == "__main__": unittest.main(verbosity=2)
