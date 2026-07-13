import unittest
import numpy as np
from shapely.geometry import box
from sgcf_nrmp.geometry.semantic_rasterizer import rasterize_semantic_prisms
from sgcf_nrmp.types.camera import CameraIntrinsics
from sgcf_nrmp.types.semantic import SemanticClass,SemanticObstacle


class SemanticSceneTest(unittest.TestCase):
    def setUp(self): self.K=CameraIntrinsics(100,100,80,60,160,120,.05); self.T=np.array([[0,-1,0,0],[0,0,-1,1],[1,0,0,0],[0,0,0,1]],float)
    def obstacle(self,x,klass,instance,color): return SemanticObstacle(box(x,-.4,x+.4,.4),klass,instance,1.5,color)
    def test_render_is_reproducible_and_finite(self):
        obstacles=[self.obstacle(2,SemanticClass.HUMAN,1,(1,0,0))]; a=rasterize_semantic_prisms(obstacles,self.T,self.K); b=rasterize_semantic_prisms(obstacles,self.T,self.K); np.testing.assert_array_equal(a.semantic_id_image,b.semantic_id_image); np.testing.assert_array_equal(a.depth_image,b.depth_image); self.assertTrue(np.isfinite(a.depth_image).all())
    def test_near_prism_occludes_far_prism(self):
        far=self.obstacle(4,SemanticClass.VEHICLE,2,(0,0,1)); near=self.obstacle(2,SemanticClass.HUMAN,1,(1,0,0)); image=rasterize_semantic_prisms([far,near],self.T,self.K); visible=image.semantic_id_image[image.semantic_id_image>0]; self.assertGreater(len(visible),0); self.assertIn(int(SemanticClass.HUMAN),visible)
    def test_background_unknown_and_ids_not_derived_from_rgb(self):
        a=self.obstacle(2,SemanticClass.HUMAN,7,(0.2,.2,.2)); image=rasterize_semantic_prisms([a],self.T,self.K); self.assertEqual(image.semantic_id_image[0,0],0); self.assertEqual(image.instance_id_image.max(),7); self.assertEqual(image.semantic_id_image.max(),int(SemanticClass.HUMAN))
    def test_moving_foreground_changes_occlusion_deterministically(self):
        far=self.obstacle(4,SemanticClass.VEHICLE,2,(0,0,1)); center=self.obstacle(2,SemanticClass.HUMAN,1,(1,0,0)); side=SemanticObstacle(box(2,1.2,2.4,1.6),SemanticClass.HUMAN,1,1.5,(1,0,0)); a=rasterize_semantic_prisms([far,center],self.T,self.K); b=rasterize_semantic_prisms([far,side],self.T,self.K); self.assertFalse(np.array_equal(a.semantic_id_image,b.semantic_id_image)); np.testing.assert_array_equal(b.semantic_id_image,rasterize_semantic_prisms([far,side],self.T,self.K).semantic_id_image)
