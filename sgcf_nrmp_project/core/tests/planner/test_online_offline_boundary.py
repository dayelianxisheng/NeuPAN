import inspect
import unittest
from pathlib import Path

import numpy as np
import yaml

from sgcf_nrmp.data.procedural.scene import ProceduralScene
from sgcf_nrmp.data.procedural.scene_generator import circle_obstacle
from sgcf_nrmp.geometry.footprint import rectangular_footprint
from sgcf_nrmp.planner.geometry_checker import ExactObservableChecker,OfflineWorldEvaluator
from sgcf_nrmp.planner.gt_nrmp_planner import GTNRMPPlanner
from sgcf_nrmp.planner.reference import local_reference,polyline_path
from sgcf_nrmp.planner.solver_result import PlannerStatus
from sgcf_nrmp.types.geometry import Pose2D
from sgcf_nrmp.types.lidar import LidarConfig,LidarScan

CONFIG=yaml.safe_load(Path('sgcf_nrmp_project/core/configs/planner/diff_drive_gt_nrmp.yaml').read_text())


def empty_scan():
    return LidarScan(np.empty(0),np.empty(0,dtype=bool),np.empty((0,2)),np.empty((0,2)),np.empty(0))


class OnlineOfflineBoundaryTest(unittest.TestCase):
    def plan_from_scan(self,scan):
        state=np.zeros(3); path=polyline_path([(0,0),(4,0)]); reference=local_reference(state,path,CONFIG['planner']['horizon'],CONFIG['planner']['reference_speed_mps']*CONFIG['planner']['dt_s'])
        planner=GTNRMPPlanner(CONFIG); result=planner.plan(state,reference,ExactObservableChecker(scan,.8,.5,8.)); return planner,result

    def test_planner_signature_has_no_world_geometry(self):
        names=inspect.signature(GTNRMPPlanner.plan).parameters
        self.assertNotIn('scene',names); self.assertNotIn('world',names); self.assertNotIn('obstacles',names)

    def test_world_evaluator_failure_cannot_affect_online_planner(self):
        original=OfflineWorldEvaluator.evaluate_trajectory
        OfflineWorldEvaluator.evaluate_trajectory=lambda *args,**kwargs: (_ for _ in ()).throw(RuntimeError('offline only'))
        try: _,result=self.plan_from_scan(empty_scan())
        finally: OfflineWorldEvaluator.evaluate_trajectory=original
        self.assertTrue(np.isfinite(result.first_control).all())

    def test_same_observation_different_hidden_world_same_control(self):
        _,a=self.plan_from_scan(empty_scan()); _,b=self.plan_from_scan(empty_scan()); np.testing.assert_array_equal(a.first_control,b.first_control)

    def test_same_observation_can_have_different_offline_risk(self):
        query=np.asarray([[-.6,0.,0.]]); observable=np.asarray([5.]); footprint=rectangular_footprint(.8,.5)
        safe=OfflineWorldEvaluator(ProceduralScene([],(-3,-2,3,2)),footprint,5.).evaluate_trajectory(query,observable,.25)
        hidden=OfflineWorldEvaluator(ProceduralScene([circle_obstacle((-1.,0),.3)],(-3,-2,3,2)),footprint,5.).evaluate_trajectory(query,observable,.25)
        self.assertFalse(safe.partial_observation_world_risk); self.assertTrue(hidden.partial_observation_world_risk)

    def test_online_timing_has_no_world_key(self):
        _,result=self.plan_from_scan(empty_scan()); self.assertFalse(any('world' in key for key in result.diagnostics))

    def test_offline_evaluator_does_not_change_warm_start_or_result(self):
        planner,result=self.plan_from_scan(empty_scan()); before=planner.previous_controls.copy(); control=result.first_control.copy(); result_state=dict(result.__dict__)
        OfflineWorldEvaluator(ProceduralScene([],(-2,-2,5,2)),rectangular_footprint(.8,.5),8.).evaluate_trajectory(result.states)
        np.testing.assert_array_equal(before,planner.previous_controls); np.testing.assert_array_equal(control,result.first_control); self.assertEqual(result_state.keys(),result.__dict__.keys())

    def test_online_result_has_no_world_fields(self):
        _,result=self.plan_from_scan(empty_scan()); self.assertFalse(hasattr(result,'min_world_clearance')); self.assertFalse(hasattr(result,'partial_observation_world_risk'))

    def test_legacy_label_matches_split_observable_and_world(self):
        scene=ProceduralScene([circle_obstacle((1.2,.1),.3)],(-2,-2,3,2)); pose=Pose2D(.2,-.1,.3); lidar=LidarConfig(num_beams=61,range_max=5.); scan=scene.scan(Pose2D(0,0,0),lidar,np.random.default_rng(8)); footprint=rectangular_footprint(.8,.5)
        legacy=scene.label(footprint,pose,scan,5.); query=pose.as_array()[None,:]; online=ExactObservableChecker(scan,.8,.5,5.).distance(query)[0]; offline=OfflineWorldEvaluator(scene,footprint,5.).evaluate_trajectory(query)
        self.assertAlmostEqual(legacy.observable_clearance,online,places=10); self.assertAlmostEqual(legacy.world_clearance,offline.minimum_world_clearance,places=10); self.assertEqual(legacy.world_collision,offline.world_collision)

    def test_observable_recheck_rejects_unsafe_candidate(self):
        class RejectingObservableChecker:
            calls=0
            def linearization(self,states): return np.full(len(states),1.),np.zeros((len(states),3)),np.ones(len(states),bool)
            def recheck_observable_trajectory(self,states,d_safe):
                self.calls+=1; unsafe=self.calls>1; values=np.zeros(len(states)) if unsafe else np.ones(len(states)); return {'observable':values,'min_observable':float(values.min()),'violated_points':len(states) if unsafe else 0}
        state=np.zeros(3); path=polyline_path([(0,0),(4,0)]); reference=local_reference(state,path,CONFIG['planner']['horizon'],CONFIG['planner']['reference_speed_mps']*CONFIG['planner']['dt_s']); result=GTNRMPPlanner(CONFIG).plan(state,reference,RejectingObservableChecker()); self.assertEqual(result.status,PlannerStatus.REJECTED_BY_GEOMETRY_CHECK); np.testing.assert_array_equal(result.first_control,0.)
