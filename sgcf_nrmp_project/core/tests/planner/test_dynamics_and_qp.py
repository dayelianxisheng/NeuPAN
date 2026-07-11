import unittest
from pathlib import Path
import numpy as np,yaml

from sgcf_nrmp.planner.angle_utils import wrap_angle
from sgcf_nrmp.planner.dynamics import linearize,rollout,step
from sgcf_nrmp.planner.qp_problem import PersistentPlannerQP,build_qp
from sgcf_nrmp.planner.trust_region import TrustRegion


CONFIG=yaml.safe_load(Path('sgcf_nrmp_project/core/configs/planner/diff_drive_gt_nrmp.yaml').read_text())


class DynamicsQPTest(unittest.TestCase):
    def test_rollout_known_straight(self):
        states=rollout(np.zeros(3),np.tile([1.,0.],(3,1)),.2); np.testing.assert_allclose(states[:,0],[0,.2,.4,.6]); np.testing.assert_allclose(states[:,1:],0,atol=1e-12)
    def test_dynamics_jacobian_finite_difference(self):
        state=np.asarray([1.,2.,.4]); control=np.asarray([.7,-.2]); A,B,_=linearize(state,control,.2); eps=1e-6
        numeric_A=np.column_stack([(step(state+np.eye(3)[i]*eps,control,.2)-step(state-np.eye(3)[i]*eps,control,.2))/(2*eps) for i in range(3)])
        numeric_B=np.column_stack([(step(state,control+np.eye(2)[i]*eps,.2)-step(state,control-np.eye(2)[i]*eps,.2))/(2*eps) for i in range(2)])
        np.testing.assert_allclose(A,numeric_A,atol=1e-6); np.testing.assert_allclose(B,numeric_B,atol=1e-6)
    def test_angle_wrap_boundary(self):
        self.assertAlmostEqual(float(wrap_angle(-np.pi+.01-(np.pi-.01))),.02,places=8)
    def test_qp_is_valid_and_shapes(self):
        T=CONFIG['planner']['horizon']; nominal=rollout(np.zeros(3),np.tile([.5,0.],(T,1)),CONFIG['planner']['dt_s']); controls=np.tile([.5,0.],(T,1)); reference=nominal.copy(); distances=np.full(T+1,8.); gradients=np.zeros((T+1,3)); valid=np.zeros(T+1,dtype=bool)
        problem,x,u,slack=build_qp(np.zeros(3),reference,nominal,controls,np.zeros(2),distances,gradients,valid,CONFIG,TrustRegion.from_dict(CONFIG['trust_region']))
        self.assertTrue(problem.is_dcp()); self.assertTrue(problem.is_qp()); self.assertEqual(x.shape,(T+1,3)); self.assertEqual(u.shape,(T,2)); self.assertEqual(slack.shape,(T,))
    def test_persistent_qp_is_dpp_and_identity_is_stable(self):
        T=CONFIG['planner']['horizon']; controls=np.tile([.5,0.],(T,1)); nominal=rollout(np.zeros(3),controls,CONFIG['planner']['dt_s']); distances=np.full(T+1,8.); gradients=np.zeros((T+1,3)); valid=np.zeros(T+1,dtype=bool); qp=PersistentPlannerQP(CONFIG); identity=id(qp.problem)
        for offset in (0.,.1):
            qp.update(np.asarray([offset,0.,0.]),nominal+np.asarray([offset,0.,0.]),nominal+np.asarray([offset,0.,0.]),controls,np.zeros(2),distances,gradients,valid,TrustRegion.from_dict(CONFIG['trust_region']))
            self.assertEqual(id(qp.problem),identity); self.assertTrue(qp.problem.is_dpp())
    def test_trust_region_scaling(self):
        trust=TrustRegion(.1,.2,.3,.4).scaled(.5); self.assertEqual(trust,TrustRegion(.05,.1,.15,.2))
