import unittest
import numpy as np
from sgcf_nrmp.fusion.pointpainting import paint_points
from sgcf_nrmp.types.camera import ProjectionResult
from sgcf_nrmp.types.semantic import SemanticClass


class PointPaintingTest(unittest.TestCase):
    def setup(self):
        p=np.array([[1.,0.],[2.,0.],[3.,0.]]); proj=ProjectionResult(np.array([[2,2],[1,1],[8,8.]],float),np.ones(3),np.array([True,False,True]),np.array([5,0,1.])); image=np.zeros((10,10),int); image[2,2]=int(SemanticClass.HUMAN); image[8,8]=int(SemanticClass.VEHICLE); return p,proj,image
    def test_class_read_and_order_preserved(self):
        p,proj,image=self.setup(); painted=paint_points(p,np.linalg.norm(p,axis=1),proj,image,0.); np.testing.assert_array_equal(painted.features[:,:2],p); np.testing.assert_array_equal(painted.class_ids,[2,0,3]); self.assertEqual(len(painted.features),len(p))
    def test_invalid_projection_unknown_without_deletion(self):
        p,proj,image=self.setup(); painted=paint_points(p,np.ones(3),proj,image,0.); self.assertEqual(painted.class_ids[1],0); self.assertEqual(painted.projection_confidence[1],0); self.assertEqual(len(painted.features),3)
    def test_rgb_missing_or_stale_confidence_zero(self):
        p,proj,image=self.setup(); missing=paint_points(p,np.ones(3),proj,image,0.,rgb_available=False); stale=paint_points(p,np.ones(3),proj,image,.5,max_image_age_s=.1); self.assertTrue(np.all(missing.projection_confidence==0)); self.assertTrue(np.all(stale.reliability==0)); np.testing.assert_array_equal(missing.features[:,:2],p)
    def test_no_nan_inf(self):
        p,proj,image=self.setup(); painted=paint_points(p,np.ones(3),proj,image,0.); self.assertTrue(np.isfinite(painted.features).all())
