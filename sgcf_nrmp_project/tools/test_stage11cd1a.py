import json
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[2]; OUT=ROOT/'sgcf_nrmp_project/artifacts/stages/stage_11c_d1a_speed_contract_and_geometry_diagnosis'
class Tests(unittest.TestCase):
 def load(self,n): return json.loads((OUT/n).read_text())
 def test_speed(self):
  d=self.load('stage11cd1a_speed_contract.json'); self.assertEqual(d['effective_linear_limit_mps'],1.0); self.assertTrue(d['candidate_0_240_mps_within_formal_contract']); self.assertFalse(d['candidate_clamping'])
 def test_empty(self): self.assertTrue(self.load('stage11cd1a_empty_world_closed_loop.json')['passed'])
 def test_commands(self): self.assertTrue(self.load('stage11cd1a_command_consistency.json')['passed'])
 def test_replay(self): self.assertTrue(self.load('stage11cd1a_ros_core_equivalence.json')['passed'])
 def test_stop(self): self.assertTrue(self.load('stage11cd1a_zero_stop_response.json')['passed'])
 def test_diagnosis(self):
  d=self.load('stage11cd1a_single_static_geometry_diagnosis.json'); self.assertEqual(d['classification'],'CORE_GEOMETRY_RECHECK_LIMITATION'); self.assertFalse(d['ros_wrapper_input_error']); self.assertLessEqual(d['clearance_error_m'],.02)
 def test_cleanup(self): self.assertTrue(self.load('stage11cd1a_process_cleanup.json')['passed'])
if __name__=='__main__': unittest.main(verbosity=2)
