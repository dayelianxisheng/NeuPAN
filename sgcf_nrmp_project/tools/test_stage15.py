import json
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'sgcf_nrmp_project/artifacts/stages/stage_15_oracle_semantic_closed_loop'
class Stage15Tests(unittest.TestCase):
 def load(self,n):return json.loads((OUT/n).read_text())
 def test_experiment_counts(self):
  d=self.load('stage15_experiment_manifest.json');self.assertEqual(d['fixed_pair_count'],15);self.assertEqual(d['random_pair_count'],20);self.assertEqual(d['total_run_count'],70);self.assertFalse(d['stage10_started'])
 def test_safety(self):
  rows=[json.loads(x) for x in (OUT/'stage15_p0_p2_paired_results.jsonl').read_text().splitlines() if x]
  self.assertEqual(len(rows),70)
  for x in rows:
   self.assertEqual(x['collision'],0);self.assertEqual(x['stale_executed']+x['late_executed']+x['ineligible_executed'],0);self.assertLessEqual(x['candidate_ros_error'],1e-9);self.assertLessEqual(x['ros_gazebo_error'],1e-9);self.assertLessEqual(x['ros_core_replay_error'],1e-6);self.assertEqual(x['robot_self_return'],0);self.assertTrue(x['zero_stop'])
 def test_geometry(self):
  d=self.load('stage15_geometry_invariance.json');self.assertLessEqual(d['d_geo_max_difference'],1e-6);self.assertLessEqual(d['g_geo_max_difference'],1e-6);self.assertFalse(d['semantic_changes_exact_geometry'])
 def test_semantics(self):
  d=self.load('stage15_semantic_margin_audit.json');self.assertEqual(d['P0_max'],0);self.assertTrue(d['nonnegative']);self.assertLessEqual(d['P2_max'],.35);self.assertEqual(d['mixed_labels'],['STATIC_OBSTACLE','HUMAN','VEHICLE'])
 def test_no_backlog_cleanup(self):
  self.assertFalse(self.load('stage15_runtime_performance.json')['continuous_backlog']);self.assertTrue(self.load('stage15_process_cleanup.json')['passed'])
if __name__=='__main__':unittest.main()
