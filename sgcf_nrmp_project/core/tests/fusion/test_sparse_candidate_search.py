import unittest
import numpy as np
from sgcf_nrmp.fusion.sparse_candidate_search import *


class SparseCandidateSearchTest(unittest.TestCase):
    def setUp(self): self.map=np.zeros((20,30,5)); self.map[...,0]=1; self.map[10,15]=[0,0,1,0,0]; self.uv=np.array([[15.,10.],[0.,0.]])
    def test_fixed_offsets_and_limits(self):
        self.assertEqual(len(sparse_grid_offsets(8)),25); self.assertEqual(len(sparse_grid_offsets(16)),25); self.assertEqual(len(sparse_grid_offsets(24)),49); self.assertLessEqual(max(len(pattern_offsets(x)) for x in ['C0_HARD_SINGLE_PIXEL','C1_LOCAL_3X3','C2_LOCAL_5X5','C3_SPARSE_GRID_RADIUS_8','C4_SPARSE_GRID_RADIUS_16','C5_SPARSE_GRID_RADIUS_24','C7_MULTISCALE_PYRAMID_SEARCH']),64)
    def test_border_mask_invalid_projection_and_order(self):
        border=sample_candidates(self.map,self.uv,pattern_offsets('C1_LOCAL_3X3'),[True,True]); self.assertEqual(border.probabilities.shape,(2,9,5)); self.assertTrue(np.any(~border.valid_mask[1])); invalid=sample_candidates(self.map,self.uv,pattern_offsets('C1_LOCAL_3X3'),[True,False]); self.assertFalse(invalid.valid_mask[1].any())
    def test_deterministic_order(self): np.testing.assert_array_equal(sparse_grid_offsets(16),sparse_grid_offsets(16))
    def test_center_and_shifted_correct_candidate(self):
        center=sample_candidates(self.map,self.uv[:1],pattern_offsets('C0_HARD_SINGLE_PIXEL'),[True]); self.assertEqual(np.argmax(center.probabilities[0,0]),2); shifted=sample_candidates(self.map,np.array([[7.,10.]]),sparse_grid_offsets(8),[True]); self.assertTrue(np.any(np.argmax(shifted.probabilities[0],axis=1)==2))
    def test_dropout_stale_and_all_invalid(self):
        drop=sample_candidates(self.map,self.uv,pattern_offsets('C2_LOCAL_5X5'),[True,True],rgb_available=False); stale=sample_candidates(self.map,self.uv,pattern_offsets('C2_LOCAL_5X5'),[True,True],image_age_s=.5); self.assertFalse(drop.valid_mask.any()); self.assertFalse(stale.reliable_mask.any()); self.assertTrue(np.isfinite(drop.probabilities).all())
    def test_coarse_to_fine_count_and_topk(self):
        batch=coarse_to_fine_candidates(self.map,self.uv[:1],[True],top_k=4); self.assertEqual(batch.probabilities.shape,(1,36,5)); self.assertLessEqual(batch.probabilities.shape[1],64)
    def test_multiscale_coordinates(self):
        offsets=pattern_offsets('C7_MULTISCALE_PYRAMID_SEARCH'); self.assertTrue(np.any(np.all(offsets==[24,24],axis=1))); self.assertTrue(np.any(np.all(offsets==[0,0],axis=1)))
    def test_api_has_no_gt_or_calibration_error(self):
        import inspect; names=inspect.signature(sample_candidates).parameters; self.assertNotIn('gt_class',names); self.assertNotIn('translation_error',names); self.assertNotIn('rotation_error',names); self.assertNotIn('world',names)
