"""Numerical tests for transforms, distances, gradients and LiDAR visibility."""

from __future__ import annotations

import unittest

import numpy as np

from sgcf_nrmp.data.procedural.scene import ProceduralScene
from sgcf_nrmp.data.procedural.scene_generator import (
    circle_obstacle,
    rectangle_obstacle,
    wall_obstacle,
)
from sgcf_nrmp.geometry.footprint import rectangular_footprint
from sgcf_nrmp.geometry.transforms import inverse_transform_pose, transform_points
from sgcf_nrmp.types.geometry import Pose2D
from sgcf_nrmp.types.lidar import LidarConfig


class GeometryTest(unittest.TestCase):
    def setUp(self) -> None:
        self.footprint = rectangular_footprint(2.0, 1.0)
        self.full_scan = LidarConfig(-np.pi, np.pi, 361, 0.05, 10.0)

    def scan(self, scene: ProceduralScene, config: LidarConfig | None = None):
        return scene.scan(Pose2D(0.0, 0.0, 0.0), config or self.full_scan, np.random.default_rng(7))

    def test_empty_scene_lidar_and_clearance_are_explicitly_truncated(self) -> None:
        scene = ProceduralScene([], (-5, -5, 5, 5))
        scan = self.scan(scene)
        label = scene.label(self.footprint, Pose2D(0, 0, 0), scan, 10.0)
        self.assertEqual(scan.valid_count, 0)
        self.assertFalse(label.observable_available)
        self.assertEqual(label.observable_clearance, 10.0)
        self.assertEqual(label.world_clearance, 10.0)

    def test_single_circle_known_distance(self) -> None:
        scene = ProceduralScene([circle_obstacle((4.0, 0.0), 1.0, 64)], (-6, -6, 6, 6))
        scan = self.scan(scene)
        label = scene.label(self.footprint, Pose2D(0, 0, 0), scan, 10.0)
        self.assertAlmostEqual(label.world_clearance, 2.0, delta=2e-3)
        self.assertAlmostEqual(label.observable_clearance, 2.0, delta=2e-3)

    def test_single_rectangle_known_distance(self) -> None:
        obstacle = rectangle_obstacle((4.0, 0.0), 2.0, 2.0)
        scene = ProceduralScene([obstacle], (-6, -6, 6, 6))
        label = scene.label(self.footprint, Pose2D(0, 0, 0), self.scan(scene), 10.0)
        self.assertAlmostEqual(label.world_clearance, 2.0, places=6)

    def test_rotated_footprint_changes_clearance(self) -> None:
        obstacle = rectangle_obstacle((2.0, 0.0), 0.2, 3.0)
        scene = ProceduralScene([obstacle], (-5, -5, 5, 5))
        scan = self.scan(scene)
        aligned = scene.label(self.footprint, Pose2D(0, 0, 0), scan, 10.0)
        rotated = scene.label(self.footprint, Pose2D(0, 0, np.pi / 2), scan, 10.0)
        self.assertAlmostEqual(aligned.world_clearance, 0.9, places=6)
        self.assertAlmostEqual(rotated.world_clearance, 1.4, places=6)

    def test_footprint_intersection_sets_world_collision(self) -> None:
        scene = ProceduralScene([rectangle_obstacle((0.8, 0.0), 1.0, 1.0)], (-5, -5, 5, 5))
        label = scene.label(self.footprint, Pose2D(0, 0, 0), self.scan(scene), 10.0)
        self.assertTrue(label.world_collision)
        self.assertEqual(label.world_clearance, 0.0)

    def test_wall_raycast_known_range(self) -> None:
        scene = ProceduralScene([wall_obstacle((3, -2), (3, 2), 0.2)], (-5, -5, 5, 5))
        config = LidarConfig(0.0, 0.0, 1, 0.05, 10.0)
        scan = self.scan(scene, config)
        self.assertTrue(scan.valid[0])
        self.assertAlmostEqual(scan.ranges[0], 2.9, places=6)

    def test_lidar_max_range_excludes_far_obstacle(self) -> None:
        scene = ProceduralScene([wall_obstacle((6, -2), (6, 2), 0.2)], (-8, -8, 8, 8))
        scan = self.scan(scene, LidarConfig(0, 0, 1, 0.05, 5.0))
        self.assertFalse(scan.valid[0])
        self.assertEqual(scan.ranges[0], 5.0)

    def test_lidar_field_of_view(self) -> None:
        scene = ProceduralScene([circle_obstacle((-3, 0), 0.5)], (-5, -5, 5, 5))
        scan = self.scan(scene, LidarConfig(-np.pi / 3, np.pi / 3, 61, 0.05, 8.0))
        self.assertEqual(scan.valid_count, 0)

    def test_near_obstacle_occludes_far_obstacle(self) -> None:
        near = wall_obstacle((2, -1), (2, 1), 0.2)
        far = wall_obstacle((4, -1), (4, 1), 0.2)
        scene = ProceduralScene([near, far], (-5, -5, 6, 5))
        scan = self.scan(scene, LidarConfig(0, 0, 1, 0.05, 8.0))
        self.assertAlmostEqual(scan.ranges[0], 1.9, places=6)

    def test_observable_and_world_clearance_differ_outside_fov(self) -> None:
        front = circle_obstacle((4, 0), 0.5)
        hidden_rear = circle_obstacle((-1.5, 0), 0.3)
        scene = ProceduralScene([front, hidden_rear], (-6, -6, 6, 6))
        scan = self.scan(scene, LidarConfig(-np.pi / 4, np.pi / 4, 91, 0.05, 8.0))
        label = scene.label(self.footprint, Pose2D(-0.4, 0, 0), scan, 8.0)
        self.assertGreater(label.observable_clearance, label.world_clearance + 1.0)

    def test_xy_finite_difference_gradient(self) -> None:
        scene = ProceduralScene([wall_obstacle((4, -5), (4, 5), 0.2)], (-6, -6, 6, 6))
        scan = self.scan(scene)
        # Non-zero yaw avoids the genuine support-function cusp at yaw=0.
        gradient = scene.gradient(self.footprint, Pose2D(0, 0, 0.35), scan, 10.0, "world_clearance", 0.01, 0.01)
        self.assertTrue(gradient.gradient_valid)
        self.assertAlmostEqual(gradient.gx, -1.0, places=5)
        self.assertAlmostEqual(gradient.gy, 0.0, places=5)

    def test_yaw_finite_difference_gradient(self) -> None:
        obstacle = wall_obstacle((3, -5), (3, 5), 0.2)
        scene = ProceduralScene([obstacle], (-6, -6, 6, 6))
        scan = self.scan(scene)
        pose = Pose2D(0, 0, 0.35)
        gradient = scene.gradient(self.footprint, pose, scan, 10.0, "world_clearance", 0.005, 0.005)
        expected = np.sin(pose.yaw) - 0.5 * np.cos(pose.yaw)
        self.assertTrue(gradient.gradient_valid)
        self.assertAlmostEqual(gradient.gyaw, expected, delta=2e-3)

    def test_no_valid_lidar_points_with_full_dropout(self) -> None:
        scene = ProceduralScene([circle_obstacle((3, 0), 0.5)], (-5, -5, 5, 5))
        scan = self.scan(scene, LidarConfig(-np.pi, np.pi, 61, 0.05, 8.0, 0.0, 1.0))
        label = scene.label(self.footprint, Pose2D(0, 0, 0), scan, 8.0)
        self.assertFalse(label.observable_available)
        self.assertEqual(label.observable_clearance, 8.0)

    def test_transform_inverse_roundtrip(self) -> None:
        T_world_robot = Pose2D(2.0, -1.0, 0.7)
        points_robot = np.asarray([[1.0, 0.0], [-0.2, 3.0]])
        points_world = transform_points(T_world_robot, points_robot)
        recovered = transform_points(inverse_transform_pose(T_world_robot), points_world)
        np.testing.assert_allclose(recovered, points_robot, atol=1e-12)


if __name__ == "__main__":
    unittest.main()
