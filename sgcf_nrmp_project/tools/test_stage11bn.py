"""Acceptance tests for the final Stage 11B-N runtime matrix."""

import json
import unittest
from pathlib import Path


PROJECT=Path(__file__).resolve().parents[1]
OUT=PROJECT/"artifacts/stages/stage_11b_n_final_runtime_matrix"
def load(name):return json.loads((OUT/name).read_text())


class Stage11BNAcceptanceTest(unittest.TestCase):
 def test_immutable_runtime(self):
  d=load('stage11bn_runtime_image_binding.json');self.assertFalse(d['created_using_mutable_tag']);self.assertEqual(d['container_image_id'],d['immutable_image_id']);self.assertTrue(d['immutable_image_id'].startswith('sha256:99de6309'))
 def test_asset_preflight(self):
  d=load('stage11bn_final_asset_preflight.json');self.assertEqual(d['active_include_scale_count'],0);self.assertEqual(d['sdformat_parse_pass_count'],12);self.assertEqual(d['robot_visual_visibility_flags'],[2,2,2]);self.assertEqual(d['lidar_visibility_mask'],4294967293)
 def test_full_matrix_fresh(self):
  d=load('stage11bn_world_runtime_matrix.json');e=load('stage11bn_stage11bm_evidence_integration.json');self.assertEqual(d['runtime_result_count'],12);self.assertEqual(d['missing_world_count'],0);self.assertEqual(d['segmentation_fault_count'],0);self.assertTrue(e['stage11bn_matrix_is_fresh']);self.assertFalse(e['stage11bm_runtime_reused_as_stage11bn_evidence'])
 def test_entities_and_time(self):
  e=load('stage11bn_runtime_entity_audit.json');t=load('stage11bn_sim_time_audit.json');self.assertEqual(e['expected_entities_present_fraction'],1.);self.assertTrue(all(not x['missing'] and not x['unexpected'] for x in e['records'].values()));self.assertTrue(all(x['monotonic'] and x['negative_jump_count']==0 for x in t['records'].values()))
 def test_self_visibility_and_initial_collision(self):
  s=load('stage11bn_lidar_self_visibility_regression.json');c=load('stage11bn_runtime_clearance_consistency.json');self.assertTrue(s['all_scenes_self_return_zero']);self.assertTrue(s['initial_collision_external_visible']);self.assertGreater(s['records']['initial_collision']['external_obstacle_inside_footprint_count'],0);initial=next(x for x in c['records'] if x['scene_id']=='initial_collision');self.assertTrue(initial['runtime_collision'])
 def test_adapter_contract(self):
  d=load('stage11bn_lidar_adapter_metrics.json');self.assertTrue(all(x['point_order_preserved'] and x['invalid_ranges_handled'] and not x['footprint_points_deleted'] and not x['fixed_beams_deleted'] for x in d['records'].values()))
 def test_sensor_frame_clearance(self):
  c=load('stage11bn_camera_stage07_consistency.json');o=load('stage11bn_odometry_runtime_metrics.json');g=load('stage11bn_runtime_clearance_consistency.json');self.assertTrue(c['all_scenes_match']);self.assertTrue(all(x['monotonic'] and x['finite'] for x in o.values()));self.assertEqual(g['classification_agreement_count'],5);self.assertTrue(all(x['threshold_passed'] for x in g['records']))
 def test_semantic_and_r1(self):
  s=load('stage11bn_oracle_semantic_runtime.json');r=load('stage11bn_r1_runtime_contract.json');self.assertTrue(s['initial_collision_human']);self.assertFalse(s['exact_geometry_modified']);self.assertEqual(r['rgb_dropout_contract']['fallback_reason'],'RGB_DROPOUT');self.assertEqual(r['outdated_rgb_contract']['fallback_reason'],'OUTDATED_IMAGE')
 def test_startup_samples(self):
  d=load('stage11bn_runtime_startup_latency.json');self.assertTrue(d['all_sample_counts_three']);self.assertTrue(all(x['sample_count']==3 for x in d['records'].values()))
 def test_cleanup_and_frozen_assets(self):
  c=load('stage11bn_process_cleanup.json');f=load('stage11bn_frozen_asset_audit.json');self.assertTrue(c['all_runs_cleanup_passed']);self.assertEqual(c['final_host_residual_gazebo_process_count'],0);self.assertTrue(c['stage_container_stopped']);self.assertTrue(f['world_hashes_unchanged'] and f['model_hashes_unchanged'] and f['gazebo_tree_unchanged'] and f['docker_tree_unchanged'] and f['core_tree_unchanged']);self.assertFalse(f['planner_started'] or f['stage10_loaded'] or f['ros_bridge_started'] or f['motion_commands_sent'])
 def test_all_json_parse(self):
  for p in OUT.rglob('*.json'):
   with self.subTest(path=p):json.loads(p.read_text())


if __name__=='__main__':unittest.main()
