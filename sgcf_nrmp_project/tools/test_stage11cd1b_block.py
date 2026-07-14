import json
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[2]; OUT=ROOT/'sgcf_nrmp_project/artifacts/stages/stage_11c_d1b_core_recheck_fix'
class Tests(unittest.TestCase):
 def load(self,n): return json.loads((OUT/n).read_text())
 def test_reproduced(self):
  d=self.load('stage11cd1b_offline_replay.json'); self.assertEqual(d['minimum_clearance_reproduced'],0.0); self.assertTrue(d['independent_overlap_proof'])
 def test_zero_is_real_overlap(self):
  d=self.load('stage11cd1b_root_cause.json'); self.assertFalse(d['observed_zero_clearance_is_erroneous']); self.assertTrue(all(any(x['inside_observable_point_count']>0 for x in i['overlap_proof']) for i in d['iterations']))
 def test_no_unsafe_patch(self): self.assertFalse(self.load('stage11cd1b_core_patch_audit.json')['patch_applied'])
 def test_no_runtime(self): self.assertFalse(self.load('stage11cd1b_single_static_closed_loop.json')['executed'])
 def test_cleanup(self): self.assertTrue(self.load('stage11cd1b_process_cleanup.json')['passed'])
if __name__=='__main__': unittest.main(verbosity=2)
