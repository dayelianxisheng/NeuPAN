import unittest
from pathlib import Path
import numpy as np,yaml
from sgcf_nrmp.data.procedural.scene import ProceduralScene
from sgcf_nrmp.data.procedural.scene_generator import circle_obstacle
from sgcf_nrmp.planner.geometry_checker import ExactObservableChecker
from sgcf_nrmp.planner.gt_nrmp_planner import GTNRMPPlanner
from sgcf_nrmp.planner.reference import local_reference,polyline_path
from sgcf_nrmp.planner.semantic_nrmp_planner import SemanticObservableChecker
from sgcf_nrmp.semantic.semantic_margin_provider import SemanticMarginProvider
from sgcf_nrmp.types.geometry import Pose2D
from sgcf_nrmp.types.lidar import LidarConfig

CFG=yaml.safe_load(Path('sgcf_nrmp_project/core/configs/planner/diff_drive_gt_nrmp.yaml').read_text())
class SemanticPlannerTest(unittest.TestCase):
 def make(self,class_id=2,gate=True,available=True,age=0.):
  scene=ProceduralScene([circle_obstacle((1.5,0),.35)],(-2,-2,5,2)); state=np.zeros(3); scan=scene.scan(Pose2D(*state),LidarConfig(num_beams=181,range_max=8.),np.random.default_rng(1)); exact=ExactObservableChecker(scan,.8,.5,8.); p=np.zeros((len(scan.points_world),5)); p[:,class_id]=1; valid=np.ones(len(p),bool); provider=SemanticMarginProvider(scan.points_world,p,valid,valid,available,age,gate,.8,.5,8.); checker=SemanticObservableChecker(exact,provider); path=polyline_path([(0,0),(.7,.7),(1.5,1),(2.3,.7),(4,0)]); ref=local_reference(state,path,CFG['planner']['horizon'],CFG['planner']['reference_speed_mps']*CFG['planner']['dt_s']); return state,exact,checker,ref
 def test_human_margin_enters_qp_but_not_geometry(self):
  state,exact,checker,ref=self.make(); before=exact.distance(ref); result=GTNRMPPlanner(CFG).plan(state,ref,checker); np.testing.assert_array_equal(before,exact.distance(ref)); self.assertGreater(max(result.diagnostics['semantic_margin_samples'][0]),0); self.assertLessEqual(max(result.diagnostics['semantic_margin_samples'][0]),.350001)
 def test_static_zero_margin(self):
  state,_,checker,ref=self.make(1); result=GTNRMPPlanner(CFG).plan(state,ref,checker); self.assertEqual(max(result.diagnostics['semantic_margin_samples'][0]),0)
 def test_explicit_failures_equal_geometry_control(self):
  for kwargs in ({'available':False},{'age':.5}):
   state,exact,checker,ref=self.make(**kwargs); a=GTNRMPPlanner(CFG).plan(state,ref,exact).first_control; b=GTNRMPPlanner(CFG).plan(state,ref,checker).first_control; np.testing.assert_array_equal(a,b)
 def test_hidden_world_not_an_input(self):
  import inspect
  self.assertNotIn('world',inspect.signature(GTNRMPPlanner.plan).parameters)

