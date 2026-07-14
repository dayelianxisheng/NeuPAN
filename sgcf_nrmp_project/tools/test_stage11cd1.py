import json
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'sgcf_nrmp_project/artifacts/stages/stage_11c_d1_static_p0_closed_loop'
class Tests(unittest.TestCase):
 def load(self,n): return json.loads((OUT/n).read_text())
 def test_safe_gate(self): self.assertTrue(self.load('stage11cd1_safe_actuation_gate.json')['safety_passed'])
 def test_replay(self): self.assertTrue(self.load('stage11cd1_ros_core_equivalence.json')['passed'])
 def test_clearance(self): self.assertTrue(all(v['passed'] for v in self.load('stage11cd1_clearance_and_collision.json').values()))
 def test_stop(self): self.assertTrue(all(v['passed'] for v in self.load('stage11cd1_zero_stop_response.json').values()))
 def test_cleanup(self): self.assertTrue(self.load('stage11cd1_process_cleanup.json')['passed'])
 def test_closed_loop_capability(self): self.assertTrue(self.load('stage11cd1_closed_loop_runtime.json')['passed'])
if __name__=='__main__': unittest.main(verbosity=2)
