import unittest
import numpy as np
from sgcf_nrmp.semantic.margin_labeler import semantic_margin_ground_truth


M={0:0.,1:0.,2:.35,3:.2,4:.15}
def label(points,classes,queries=None,semantic_valid=None,trunc=8.,instances=None):
    points=np.asarray(points,float); queries=np.zeros((1,3)) if queries is None else np.asarray(queries,float); valid=np.ones(len(points),bool); semantic_valid=valid if semantic_valid is None else np.asarray(semantic_valid,bool); return semantic_margin_ground_truth(queries,points,classes,valid,semantic_valid,M,.8,.5,trunc,instances)


class MarginLabelerTest(unittest.TestCase):
    def test_single_human_bound(self):
        r=label([[1,0]],[2]); self.assertGreaterEqual(r.semantic_margin[0],0); self.assertLessEqual(r.semantic_margin[0],.35+1e-9)
    def test_single_vehicle_bound(self):
        self.assertLessEqual(label([[1,0]],[3]).semantic_margin[0],.2+1e-9)
    def test_static_wall_and_farther_human(self):
        r=label([[.8,0],[1.,0]],[1,2],instances=[10,20]); self.assertEqual(r.winning_class_id[0],2); self.assertEqual(r.winning_instance_id[0],20)
    def test_occluded_human_does_not_affect_online_margin(self):
        r=label([[.8,0],[1.,0]],[1,2],semantic_valid=[True,False]); self.assertEqual(r.semantic_margin[0],0.)
    def test_out_of_fov_human_does_not_affect_online_margin(self):
        r=label([[.8,0],[1.,0]],[1,2],semantic_valid=[True,False]); self.assertEqual(r.max_visible_class_margin,0.)
    def test_bound_for_same_obstacle_set(self):
        rng=np.random.default_rng(3); points=rng.uniform(-3,3,(50,2)); q=rng.uniform([-2,-2,-3.14],[2,2,3.14],(100,3)); r=label(points,rng.integers(0,5,50),q); self.assertTrue(np.all(r.semantic_margin<=r.max_visible_class_margin+1e-9))
    def test_truncation_bound(self):
        r=label([[9.,0]],[2],trunc=8.); self.assertGreaterEqual(r.semantic_margin[0],0); self.assertLessEqual(r.semantic_margin[0],.35+1e-9)
    def test_collision_query(self):
        r=label([[0.,0]],[2]); self.assertEqual(r.d_geo[0],0.); self.assertAlmostEqual(r.semantic_margin[0],.35)
    def test_no_visible_semantic_obstacle_margin_zero(self):
        r=label([[1.,0]],[2],semantic_valid=[False]); self.assertEqual(r.semantic_margin[0],0.)
    def test_different_world_same_observable_identical(self):
        a=label([[1.,0],[2.,.2]],[2,1]); hidden_world_a=['human']; hidden_world_b=['vehicle','wall']; b=label([[1.,0],[2.,.2]],[2,1]); np.testing.assert_array_equal(a.semantic_margin,b.semantic_margin); self.assertNotEqual(hidden_world_a,hidden_world_b)
