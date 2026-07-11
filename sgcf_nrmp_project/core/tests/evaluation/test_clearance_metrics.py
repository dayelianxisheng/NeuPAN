import unittest
import numpy as np

from sgcf_nrmp.evaluation.clearance_metrics import clearance_metrics
from sgcf_nrmp.evaluation.gradient_metrics import gradient_metrics


class ClearanceMetricsTest(unittest.TestCase):
    def test_model_and_partial_observation_risks_are_separate(self):
        prediction=np.asarray([.8,.8,.2]); observable=np.asarray([.2,.9,.2]); obs_collision=np.asarray([False,False,True]); world_collision=np.asarray([True,True,True]); logits=np.asarray([-1.,-1.,1.])
        _,report=clearance_metrics(prediction,observable,obs_collision,world_collision,.6,.8,logits)
        self.assertEqual(report["model_false_safe_count"],1); self.assertEqual(report["world_risk_model_error_count"],1); self.assertEqual(report["world_risk_partial_observation_count"],1)

    def test_gradient_metrics_keep_translation_and_yaw_separate(self):
        predicted=np.asarray([[1.,0.,2.]]); target=np.asarray([[1.,0.,1.]]); result=gradient_metrics(predicted,target,np.asarray([True]),np.asarray([.01]))
        self.assertEqual(result["translation_l1"],0.); self.assertEqual(result["yaw_mae_per_radian"],1.)
