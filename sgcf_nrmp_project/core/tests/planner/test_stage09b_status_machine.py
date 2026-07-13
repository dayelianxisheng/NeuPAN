"""Stage 09B status, taxonomy, fallback, and information-boundary tests."""

import json
from pathlib import Path
import unittest

import numpy as np
import yaml
from copy import deepcopy

from sgcf_nrmp.data.procedural.scene import ProceduralScene
from sgcf_nrmp.planner.geometry_checker import ExactObservableChecker
from sgcf_nrmp.planner.gt_nrmp_planner import GTNRMPPlanner
from sgcf_nrmp.planner.reference import local_reference, polyline_path
from sgcf_nrmp.planner.semantic_nrmp_planner import SemanticObservableChecker
from sgcf_nrmp.planner.solver_result import GeometryRecheckReason, PlannerStatus, SolverFailureReason
from sgcf_nrmp.planner.status_machine import CONTROL_ACCEPTED_STATUSES, resolve_status, semantic_failure_status
from sgcf_nrmp.semantic.semantic_margin_provider import SemanticMarginProvider
from sgcf_nrmp.types.lidar import LidarScan


ROOT=Path("sgcf_nrmp_project")
CFG=yaml.safe_load((ROOT/"core/configs/planner/diff_drive_gt_nrmp.yaml").read_text())


def empty_scan():
    return LidarScan(np.empty(0),np.empty(0,bool),np.empty((0,2)),np.empty((0,2)),np.empty(0))


class Stage09BStatusMachineTest(unittest.TestCase):
    def test_statuses_serialize(self):
        for status in PlannerStatus:
            self.assertEqual(json.loads(json.dumps(status.value)),status.value)

    def test_priority_is_deterministic_and_collision_first(self):
        self.assertEqual(resolve_status(PlannerStatus.SOLVED_SAFE,PlannerStatus.SOLVER_USER_LIMIT),PlannerStatus.SOLVER_USER_LIMIT)
        self.assertEqual(resolve_status(PlannerStatus.REJECTED_BY_GEOMETRY_CHECK,PlannerStatus.EMERGENCY_STOP),PlannerStatus.EMERGENCY_STOP)

    def test_semantic_infeasible_requires_feasible_geometry(self):
        self.assertEqual(semantic_failure_status(PlannerStatus.INFEASIBLE,PlannerStatus.SOLVED_SAFE,False),PlannerStatus.SEMANTICALLY_INFEASIBLE)
        self.assertEqual(semantic_failure_status(PlannerStatus.INFEASIBLE,PlannerStatus.SOLVED_SAFE,True),PlannerStatus.SEMANTIC_DEGRADED_TO_GEOMETRY)
        self.assertEqual(semantic_failure_status(PlannerStatus.INFEASIBLE,PlannerStatus.GEOMETRICALLY_INFEASIBLE,True),PlannerStatus.GEOMETRICALLY_INFEASIBLE)
        self.assertEqual(semantic_failure_status(PlannerStatus.SOLVER_TIMEOUT,PlannerStatus.SOLVED_SAFE,True),PlannerStatus.SOLVER_TIMEOUT)

    def test_taxonomies_are_complete_and_distinct(self):
        self.assertEqual(len(set(item.value for item in GeometryRecheckReason)),7)
        self.assertEqual(len(set(item.value for item in SolverFailureReason)),7)

    def test_explicit_failure_emits_geometry_control_and_status(self):
        scan=empty_scan(); exact=ExactObservableChecker(scan,.8,.5,8.); p=np.empty((0,5)); provider=SemanticMarginProvider(scan.points_world,p,np.empty(0,bool),np.empty(0,bool),False,0.,True)
        checker=SemanticObservableChecker(exact,provider); state=np.zeros(3); ref=local_reference(state,polyline_path([(0,0),(4,0)]),12,.12)
        geometry=GTNRMPPlanner(CFG).plan(state,ref,exact); degraded=GTNRMPPlanner(CFG).plan(state,ref,checker)
        self.assertEqual(degraded.status,PlannerStatus.EXPLICIT_FAILURE_GEOMETRY_FALLBACK)
        self.assertIn(degraded.status,CONTROL_ACCEPTED_STATUSES)
        np.testing.assert_array_equal(degraded.first_control,geometry.first_control)
        self.assertEqual(degraded.diagnostics["explicit_failure_fallback"]["control_source"],"GEOMETRY_P0")

    def test_margin_bounds_and_geometry_points_unchanged(self):
        points=np.asarray([[1.,0.],[2.,.2]]); scan=LidarScan(np.ones(2),np.ones(2,bool),points,points,np.zeros(2)); exact=ExactObservableChecker(scan,.8,.5,8.); p=np.zeros((2,5)); p[:,2]=1.; provider=SemanticMarginProvider(points,p,np.ones(2,bool),np.ones(2,bool)); checker=SemanticObservableChecker(exact,provider); q=np.zeros((2,3)); before=exact.distance(q); margin=checker.semantic_margins(q); after=exact.distance(q)
        np.testing.assert_array_equal(before,after); self.assertTrue(np.all(margin>=0)); self.assertTrue(np.all(margin<=.350001)); self.assertEqual(len(exact.oracle.points),2)

    def test_integrated_semantic_infeasible_and_degraded_statuses(self):
        points=np.asarray([[2.,0.]]); scan=LidarScan(np.asarray([2.]),np.ones(1,bool),points,points,np.zeros(1)); exact=ExactObservableChecker(scan,.8,.5,8.); probabilities=np.zeros((1,5)); probabilities[:,2]=1.; checker=SemanticObservableChecker(exact,SemanticMarginProvider(points,probabilities,np.ones(1,bool),np.ones(1,bool),True,0.,True)); state=np.zeros(3); ref=local_reference(state,polyline_path([(0,0),(.5,.7),(1.,.8)]),12,.12)
        blocked=GTNRMPPlanner(CFG).plan(state,ref,checker,simulate_infeasible=True)
        self.assertEqual(blocked.status,PlannerStatus.SEMANTICALLY_INFEASIBLE)
        allowed=deepcopy(CFG); allowed["semantic"]={"allow_semantic_degradation":True}
        degraded=GTNRMPPlanner(allowed).plan(state,ref,checker,simulate_infeasible=True)
        self.assertEqual(degraded.status,PlannerStatus.SEMANTIC_DEGRADED_TO_GEOMETRY)
        self.assertEqual(degraded.diagnostics["semantic_failure_comparison"]["control_source"],"GEOMETRY_P0")

    def test_failed_solver_invalidates_primal_warm_start(self):
        exact=ExactObservableChecker(empty_scan(),.8,.5,8.); state=np.zeros(3); ref=local_reference(state,polyline_path([(0,0),(4,0)]),12,.12); planner=GTNRMPPlanner(CFG)
        self.assertIn(planner.plan(state,ref,exact).status,CONTROL_ACCEPTED_STATUSES)
        self.assertIsNotNone(planner.qp._last_primal)
        result=planner.plan(state,ref,exact,simulate_timeout=True)
        self.assertEqual(result.status,PlannerStatus.SOLVER_TIMEOUT)
        self.assertIsNone(planner.qp._last_primal); self.assertIsNone(planner.previous_controls)

    def test_stage09b_artifacts_preserve_boundaries_and_reproduction(self):
        out=ROOT/"artifacts/stages/stage_09b_planner_failure_hardening"
        summary=json.loads((out/"stage09b_run_summary.json").read_text())
        self.assertTrue(all(value==0 for value in summary["equivalence"].values()))
        self.assertEqual(summary["collision"]["planner_induced_collision_count"],0)
        self.assertLess(summary["latency"]["steady_state_online_equivalent"]["p95_ms"],100)
        self.assertEqual(summary["human_path_side"]["P0"]["status"],"REJECTED_BY_GEOMETRY_CHECK")
        self.assertEqual(summary["human_path_side"]["P1"]["failure_reasons"],["OSQP_MAX_ITER_REACHED"])
        freeze=json.loads((out/"planner_status_mapping.json").read_text())
        self.assertFalse(freeze["world_evaluator_can_override_online_status"])

    def test_latency_steady_state_is_separate_from_setup(self):
        out=ROOT/"artifacts/stages/stage_09b_planner_failure_hardening"
        latency=json.loads((out/"latency_breakdown.json").read_text())
        self.assertNotEqual(latency["first_cycle_setup_inclusive"]["sample_count"],latency["steady_state_online_equivalent"]["sample_count"])
        self.assertTrue(latency["offline_world_excluded"])
