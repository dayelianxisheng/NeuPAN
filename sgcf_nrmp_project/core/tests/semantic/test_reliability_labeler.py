import unittest
import numpy as np
from sgcf_nrmp.semantic.reliability_labeler import reliability_ground_truth


class ReliabilityLabelerTest(unittest.TestCase):
    def test_valid_range_boundary_and_unknown(self):
        r=reliability_ground_truth([True,True,False],[12,6,12],[2,0,3],0.); np.testing.assert_allclose(r,[1,0,0]); self.assertTrue(np.all((r>=0)&(r<=1)))
    def test_stale_dropout_and_calibration(self):
        stale=reliability_ground_truth([True],[12],[2],.5,max_image_age_s=.1); drop=reliability_ground_truth([True],[12],[2],0.,rgb_available=False); perturbed=reliability_ground_truth([True],[12],[2],0.,calibration_quality=.4); self.assertEqual(stale[0],0); self.assertEqual(drop[0],0); self.assertAlmostEqual(perturbed[0],.4)
