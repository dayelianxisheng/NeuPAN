"""Regression tests for Stage 09C safe nominal recovery."""

from pathlib import Path
import unittest

import numpy as np
import yaml

from sgcf_nrmp.data.procedural.scene import ProceduralScene
from sgcf_nrmp.data.procedural.scene_generator import circle_obstacle
from sgcf_nrmp.planner.geometry_checker import ExactObservableChecker
from sgcf_nrmp.planner.gt_nrmp_planner import GTNRMPPlanner
from sgcf_nrmp.planner.reference import local_reference, polyline_path
from sgcf_nrmp.planner.solver_result import PlannerStatus
from sgcf_nrmp.types.geometry import Pose2D
from sgcf_nrmp.types.lidar import LidarConfig


CONFIG = yaml.safe_load(
    Path("sgcf_nrmp_project/core/configs/planner/diff_drive_gt_nrmp.yaml").read_text()
)


def fixture(obstacles, path):
    state = np.zeros(3)
    scene = ProceduralScene(obstacles, (-2, -2, 5, 2))
    scan = scene.scan(
        Pose2D(*state), LidarConfig(num_beams=181, range_max=8.0),
        np.random.default_rng(1),
    )
    checker = ExactObservableChecker(scan, 0.8, 0.5, 8.0)
    reference = local_reference(
        state, path, CONFIG["planner"]["horizon"],
        CONFIG["planner"]["reference_speed_mps"] * CONFIG["planner"]["dt_s"],
    )
    return state, checker, reference


class Stage09CCollisionRecoveryTest(unittest.TestCase):
    def test_future_collision_nominal_is_repaired_and_rechecked(self):
        path = polyline_path([(0, 0), (0.7, 0.7), (1.5, 1.0), (2.3, 0.7), (4, 0)])
        state, checker, reference = fixture([circle_obstacle((1.5, 0), 0.35)], path)
        result = GTNRMPPlanner(CONFIG).plan(state, reference, checker)

        self.assertIn(result.status, (PlannerStatus.SOLVED_SAFE, PlannerStatus.SOLVED_WITH_SLACK))
        self.assertGreaterEqual(
            result.min_observable_clearance,
            CONFIG["planner"]["d_safe_m"] - 0.02,
        )
        repairs = result.diagnostics["nominal_repair_samples"]
        self.assertTrue(any(item["applied"] for item in repairs))
        self.assertTrue(all(item["minimum_clearance_after_m"] >= CONFIG["planner"]["d_safe_m"] for item in repairs if item["applied"]))
        self.assertTrue(all(item["active"] for item in result.diagnostics["collision_recovery_constraint_samples"]))
        exact = checker.recheck_observable_trajectory(result.states, CONFIG["planner"]["d_safe_m"])
        self.assertFalse(exact["violated_points"])

    def test_empty_path_does_not_activate_recovery(self):
        path = polyline_path([(0, 0), (4, 0)])
        state, checker, reference = fixture([], path)
        result = GTNRMPPlanner(CONFIG).plan(state, reference, checker)
        self.assertIn(result.status, (PlannerStatus.SOLVED_SAFE, PlannerStatus.SOLVED_WITH_SLACK))
        self.assertFalse(any(item["applied"] for item in result.diagnostics["nominal_repair_samples"]))
        self.assertFalse(any(item["active"] for item in result.diagnostics["collision_recovery_constraint_samples"]))

    def test_current_collision_is_never_recovered(self):
        path = polyline_path([(0, 0), (4, 0)])
        state, checker, reference = fixture([circle_obstacle((0.0, 0.0), 0.2)], path)
        result = GTNRMPPlanner(CONFIG).plan(state, reference, checker)
        self.assertEqual(result.status, PlannerStatus.EMERGENCY_STOP)
        np.testing.assert_allclose(result.first_control, 0.0)
        self.assertNotIn("nominal_repair_samples", result.diagnostics)

    def test_infeasible_failure_status_is_preserved(self):
        path = polyline_path([(0, 0), (4, 0)])
        state, checker, reference = fixture([], path)
        result = GTNRMPPlanner(CONFIG).plan(
            state, reference, checker, simulate_infeasible=True,
        )
        self.assertEqual(result.status, PlannerStatus.GEOMETRICALLY_INFEASIBLE)
        np.testing.assert_allclose(result.first_control, 0.0)


if __name__ == "__main__":
    unittest.main()
