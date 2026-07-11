import unittest
from pathlib import Path
import numpy as np,yaml

from sgcf_nrmp.data.procedural.scene import ProceduralScene
from sgcf_nrmp.data.procedural.scene_generator import circle_obstacle
from sgcf_nrmp.geometry.footprint import rectangular_footprint
from sgcf_nrmp.planner.geometry_checker import ExactGeometryChecker
from sgcf_nrmp.planner.gt_nrmp_planner import GTNRMPPlanner
from sgcf_nrmp.planner.reference import local_reference,polyline_path
from sgcf_nrmp.planner.solver_result import PlannerStatus
from sgcf_nrmp.types.geometry import Pose2D
from sgcf_nrmp.types.lidar import LidarConfig


CONFIG=yaml.safe_load(Path('sgcf_nrmp_project/core/configs/planner/diff_drive_gt_nrmp.yaml').read_text())


def setup(scene,path,state=None):
    state=path[0] if state is None else np.asarray(state,float); scan=scene.scan(Pose2D(*map(float,state)),LidarConfig(num_beams=181,range_max=8.),np.random.default_rng(1)); footprint=rectangular_footprint(.8,.5); checker=ExactGeometryChecker(scene,scan,footprint,8.); reference=local_reference(state,path,CONFIG['planner']['horizon'],CONFIG['planner']['reference_speed_mps']*CONFIG['planner']['dt_s']); return state,checker,reference


class PlannerBehaviorTest(unittest.TestCase):
    def test_no_obstacle_solution_bounds_initial_and_acceleration(self):
        scene=ProceduralScene([],(-2,-2,5,2)); path=polyline_path([(0,0),(4,0)]); state,checker,reference=setup(scene,path); result=GTNRMPPlanner(CONFIG).plan(state,reference,checker)
        self.assertIn(result.status,(PlannerStatus.SOLVED_SAFE,PlannerStatus.SOLVED_WITH_SLACK)); np.testing.assert_allclose(result.states[0],state,atol=1e-6); self.assertTrue(np.all(result.controls[:,0]>=CONFIG['bounds']['v_min_mps']-1e-4)); self.assertTrue(np.all(result.controls[:,0]<=CONFIG['bounds']['v_max_mps']+1e-4)); self.assertTrue(np.all(result.slack>=-1e-8)); self.assertLessEqual(np.max(np.abs(np.diff(np.r_[0,result.controls[:,0]])))/CONFIG['planner']['dt_s'],CONFIG['bounds']['acceleration_max_mps2']+1e-3)
    def test_affine_obstacle_constraint_and_geometry_recheck(self):
        scene=ProceduralScene([circle_obstacle((1.5,0),.35)],(-2,-2,5,2)); path=polyline_path([(0,0),(.7,.7),(1.5,1.),(2.3,.7),(4,0)]); state,checker,reference=setup(scene,path); result=GTNRMPPlanner(CONFIG).plan(state,reference,checker)
        self.assertIn(result.status,(PlannerStatus.SOLVED_SAFE,PlannerStatus.SOLVED_WITH_SLACK)); self.assertGreaterEqual(result.min_observable_clearance,CONFIG['planner']['d_safe_m']-1e-3)
    def test_warm_start_runs(self):
        scene=ProceduralScene([],(-2,-2,5,2)); path=polyline_path([(0,0),(4,0)]); state,checker,reference=setup(scene,path); planner=GTNRMPPlanner(CONFIG); first=planner.plan(state,reference,checker); second=planner.plan(state,reference,checker,first.first_control); self.assertIn(second.status,(PlannerStatus.SOLVED_SAFE,PlannerStatus.SOLVED_WITH_SLACK))
    def test_timeout_and_infeasible_fallback(self):
        scene=ProceduralScene([],(-2,-2,5,2)); path=polyline_path([(0,0),(4,0)]); state,checker,reference=setup(scene,path); planner=GTNRMPPlanner(CONFIG); timeout=planner.plan(state,reference,checker,simulate_timeout=True); infeasible=planner.plan(state,reference,checker,simulate_infeasible=True); self.assertEqual(timeout.status,PlannerStatus.SOLVER_TIMEOUT); self.assertEqual(infeasible.status,PlannerStatus.INFEASIBLE); np.testing.assert_allclose(infeasible.first_control,0)
    def test_emergency_stop(self):
        scene=ProceduralScene([circle_obstacle((.41,0),.2)],(-2,-2,5,2)); path=polyline_path([(0,0),(4,0)]); state,checker,reference=setup(scene,path); result=GTNRMPPlanner(CONFIG).plan(state,reference,checker); self.assertEqual(result.status,PlannerStatus.EMERGENCY_STOP); np.testing.assert_allclose(result.first_control,0)
    def test_hidden_world_collision_classification(self):
        # Rear obstacle is outside forward FOV and intersects a future query.
        scene=ProceduralScene([circle_obstacle((-1.,0),.3)],(-3,-2,3,2)); state=np.asarray([0.,0.,0.]); scan=scene.scan(Pose2D(*state),LidarConfig(-np.pi/3,np.pi/3,61,.05,5.),np.random.default_rng(1)); checker=ExactGeometryChecker(scene,scan,rectangular_footprint(.8,.5),5.); check=checker.recheck(np.asarray([[-.6,0.,0.]]),.25); self.assertTrue(check['partial_observation_world_risk'])
