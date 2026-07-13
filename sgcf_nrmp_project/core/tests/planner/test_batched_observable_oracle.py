import unittest
import numpy as np
from shapely.geometry import MultiPoint

from sgcf_nrmp.geometry.footprint import rectangular_footprint,transform_footprint
from sgcf_nrmp.planner.geometry_checker import BatchedRectangleObservableOracle
from sgcf_nrmp.types.geometry import Pose2D


class BatchedObservableOracleTest(unittest.TestCase):
    def test_distance_matches_shapely_random_queries(self):
        rng=np.random.default_rng(12); points=rng.uniform(-4,4,(181,2)); queries=rng.uniform([-2,-2,-np.pi],[2,2,np.pi],(100,3)); oracle=BatchedRectangleObservableOracle(points,np.ones(len(points),bool),.8,.5,8.)
        actual,_=oracle.distance(queries); geometry=MultiPoint(points); footprint=rectangular_footprint(.8,.5); expected=np.asarray([min(transform_footprint(footprint,Pose2D(*q)).distance(geometry),8.) for q in queries]); np.testing.assert_allclose(actual,expected,atol=1e-12,rtol=0)

    def test_mask_empty_and_truncation(self):
        points=np.asarray([[20.,0.],[.5,0.]]); queries=np.zeros((1,3)); empty=BatchedRectangleObservableOracle(points,np.zeros(2,bool),.8,.5,8.); distance,gradient,valid,nearest=empty.distance_and_gradient(queries); np.testing.assert_array_equal(distance,[8.]); np.testing.assert_array_equal(gradient,0.); self.assertFalse(valid[0]); self.assertEqual(nearest[0],-1)
        masked=BatchedRectangleObservableOracle(points,np.asarray([True,False]),.8,.5,8.); self.assertEqual(masked.distance(queries)[0][0],8.)

    def test_autograd_matches_central_difference(self):
        rng=np.random.default_rng(14); points=rng.uniform(-4,4,(80,2)); query=np.asarray([[1.3,-1.1,.4]]); oracle=BatchedRectangleObservableOracle(points,np.ones(len(points),bool),.8,.5,8.); distance,gradient,valid,_=oracle.distance_and_gradient(query); self.assertTrue(valid[0]); eps=1e-6; numeric=[]
        for axis in range(3):
            delta=np.zeros_like(query); delta[0,axis]=eps; numeric.append((oracle.distance(query+delta)[0][0]-oracle.distance(query-delta)[0][0])/(2*eps))
        np.testing.assert_allclose(gradient[0],numeric,atol=1e-7,rtol=1e-6); self.assertTrue(np.isfinite(distance).all()); self.assertTrue(np.isfinite(gradient).all())

    def test_collision_has_deterministic_finite_subgradient(self):
        oracle=BatchedRectangleObservableOracle(np.asarray([[0.,0.]]),np.asarray([True]),.8,.5,8.); d,g,v,_=oracle.distance_and_gradient(np.zeros((1,3))); self.assertEqual(d[0],0.); self.assertFalse(v[0]); self.assertTrue(np.isfinite(g).all())
