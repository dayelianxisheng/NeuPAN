import unittest
import numpy as np
from sgcf_nrmp.geometry.camera_projection import invert_transform,project_lidar_points,transform_points
from sgcf_nrmp.types.camera import CameraIntrinsics


K=CameraIntrinsics(100,100,50,40,100,80,.05)


class CameraProjectionTest(unittest.TestCase):
    def test_center_projection(self):
        r=project_lidar_points(np.array([[0.,0.,2.]]),np.array([True]),np.eye(4),K); np.testing.assert_allclose(r.uv,[[50,40]],atol=1e-12); self.assertTrue(r.valid_mask[0])
    def test_boundary_and_behind(self):
        points=np.array([[-1.,0.,2.],[-1.01,0.,2.],[0,0,-1.]])
        r=project_lidar_points(points,np.ones(3,bool),np.eye(4),K); self.assertTrue(r.valid_mask[0]); self.assertFalse(r.valid_mask[1]); self.assertFalse(r.valid_mask[2])
    def test_inverse_roundtrip(self):
        T=np.eye(4); T[:3,3]=[1,2,3]; T[:3,:3]=np.array([[0,-1,0],[1,0,0],[0,0,1]]); points=np.array([[.2,.3,.4]]); np.testing.assert_allclose(transform_points(transform_points(points,T),invert_transform(T)),points,atol=1e-12)
    def test_batch_shape_invalid_and_padding(self):
        points=np.array([[0,0,1],[0,0,2],[0,0,3.]]); r=project_lidar_points(points,np.array([True,False,False]),np.eye(4),K); self.assertEqual(r.uv.shape,(3,2)); np.testing.assert_array_equal(r.valid_mask,[True,False,False]); self.assertTrue(np.isfinite(r.uv).all())
    def test_hidden_world_metadata_cannot_change_projection(self):
        points=np.array([[.1,.2,2.]]); a=project_lidar_points(points,[True],np.eye(4),K); hidden_world={'obstacles':['unobserved']}; b=project_lidar_points(points,[True],np.eye(4),K); np.testing.assert_array_equal(a.uv,b.uv); np.testing.assert_array_equal(a.valid_mask,b.valid_mask); self.assertTrue(hidden_world)
