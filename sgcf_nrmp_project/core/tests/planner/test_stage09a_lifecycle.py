import time,unittest
from pathlib import Path
import numpy as np,yaml
from sgcf_nrmp.data.procedural.scene import ProceduralScene
from sgcf_nrmp.data.procedural.scene_generator import circle_obstacle
from sgcf_nrmp.planner.geometry_checker import BatchedRectangleObservableOracle,ExactObservableChecker,OfflineWorldEvaluator
from sgcf_nrmp.planner.gt_nrmp_planner import GTNRMPPlanner
from sgcf_nrmp.planner.offline_simulator import run_closed_loop
from sgcf_nrmp.planner.reference import local_reference,polyline_path
from sgcf_nrmp.planner.semantic_nrmp_planner import SemanticObservableChecker
from sgcf_nrmp.semantic.semantic_margin_provider import SemanticMarginProvider
from sgcf_nrmp.types.geometry import Pose2D
from sgcf_nrmp.types.lidar import LidarConfig,LidarScan

CFG=yaml.safe_load(Path('sgcf_nrmp_project/core/configs/planner/diff_drive_gt_nrmp.yaml').read_text()); LIDAR=LidarConfig(num_beams=181,range_max=8.)
def empty_scan(): return LidarScan(np.empty(0),np.empty(0,bool),np.empty((0,2)),np.empty((0,2)),np.empty(0))
class Stage09ALifecycleTest(unittest.TestCase):
 def test_empty_and_all_padding_are_free_space(self):
  for points,mask in [(np.empty((0,2)),np.empty(0,bool)),(np.zeros((4,2)),np.zeros(4,bool)),(np.asarray([[1.,0.]]),np.asarray([False]))]:
   o=BatchedRectangleObservableOracle(points,mask,.8,.5,8.); d,g,v,n=o.distance_and_gradient(np.zeros((3,3))); np.testing.assert_array_equal(d,8.); np.testing.assert_array_equal(g,0.); self.assertFalse(v.any()); np.testing.assert_array_equal(n,-1)
 def test_p0_same_planner_and_control(self):
  state=np.zeros(3); path=polyline_path([(0,0),(4,0)]); ref=local_reference(state,path,12,.12); checker=ExactObservableChecker(empty_scan(),.8,.5,8.); a=GTNRMPPlanner(CFG).plan(state,ref,checker); b=GTNRMPPlanner(CFG).plan(state,ref,checker); np.testing.assert_allclose(a.controls,b.controls,atol=1e-10); np.testing.assert_allclose(a.states,b.states,atol=1e-10)
 def test_empty_multicycle_no_rejection_or_timeout(self):
  r=run_closed_loop(GTNRMPPlanner(CFG),ProceduralScene([],(-2,-2,5,2)),polyline_path([(0,0),(4,0)]),CFG,LIDAR,12,3); self.assertFalse(any(s in ('REJECTED_BY_GEOMETRY_CHECK','SOLVER_TIMEOUT','EMERGENCY_STOP') for s in r['statuses'])); self.assertFalse(r['metrics']['planner_induced_collision'])
 def test_initial_collision_classified_and_loop_stops(self):
  scene=ProceduralScene([circle_obstacle((.41,0),.2)],(-2,-2,5,2)); r=run_closed_loop(GTNRMPPlanner(CFG),scene,polyline_path([(0,0),(4,0)]),CFG,LIDAR,5,2); self.assertTrue(r['metrics']['initial_collision']); self.assertTrue(r['metrics']['correct_emergency_stop']); self.assertFalse(r['metrics']['planner_induced_collision']); self.assertEqual(r['metrics']['termination_step'],1)
 def test_goal_reached_does_not_plan(self):
  path=polyline_path([(0,0),(.1,0)]); r=run_closed_loop(GTNRMPPlanner(CFG),ProceduralScene([],(-1,-1,1,1)),path,CFG,LIDAR,5,1); self.assertEqual(r['metrics']['termination_reason'],'GOAL_REACHED_BEFORE_PLAN'); self.assertEqual(len(r['results']),0)
 def test_rejection_does_not_write_warm_start(self):
  class Reject:
   calls=0
   def linearization(self,s): return np.ones(len(s)),np.zeros((len(s),3)),np.ones(len(s),bool)
   def recheck_observable_trajectory(self,s,d): self.calls+=1; return {'min_observable':1. if self.calls==1 else 0.,'violated_points':0 if self.calls==1 else len(s),'observable':np.ones(len(s))}
  state=np.zeros(3); ref=local_reference(state,polyline_path([(0,0),(4,0)]),12,.12); p=GTNRMPPlanner(CFG); p.plan(state,ref,Reject()); self.assertIsNone(p.previous_controls)
 def test_point_margin_constructed_once_per_frame(self):
  calls=[]
  def factory(scan,exact):
   calls.append(1); n=len(scan.points_world); p=np.zeros((n,5)); p[:,1]=1.; return SemanticObservableChecker(exact,SemanticMarginProvider(scan.points_world,p,np.ones(n,bool),np.ones(n,bool)))
  run_closed_loop(GTNRMPPlanner(CFG),ProceduralScene([],(-2,-2,5,2)),polyline_path([(0,0),(4,0)]),CFG,LIDAR,4,1,checker_factory=factory); self.assertEqual(len(calls),4)
 def test_offline_world_delay_not_in_online_sample(self):
  original=OfflineWorldEvaluator.evaluate_trajectory
  def delayed(*a,**k): time.sleep(.01); return original(*a,**k)
  OfflineWorldEvaluator.evaluate_trajectory=delayed
  started=time.perf_counter()
  try: r=run_closed_loop(GTNRMPPlanner(CFG),ProceduralScene([],(-2,-2,5,2)),polyline_path([(0,0),(4,0)]),CFG,LIDAR,3,1)
  finally: OfflineWorldEvaluator.evaluate_trajectory=original
  self.assertGreater((time.perf_counter()-started)*1000.,40.); self.assertLess(np.median(r['timing_samples_ms']['online_equivalent_planner_ms'][1:]),100.)
