"""Random-scene, query and noisy-scan reproducibility."""

import unittest

import numpy as np

from sgcf_nrmp.data.procedural.query_sampler import sample_query_poses
from sgcf_nrmp.data.procedural.scene_generator import SceneGenerator
from sgcf_nrmp.types.geometry import Pose2D
from sgcf_nrmp.types.lidar import LidarConfig


class ReproducibilityTest(unittest.TestCase):
    def test_fixed_seed_reproduces_layout_scan_and_queries(self) -> None:
        def generate(seed: int):
            rng = np.random.default_rng(seed)
            scene = SceneGenerator(rng).random_scene((-6, -6, 6, 6), 8)
            scan = scene.scan(Pose2D(0, 0, 0), LidarConfig(num_beams=91, range_noise_std=0.01, dropout_probability=0.1), rng)
            queries = sample_query_poses((-4, -4, 4, 4), 12, rng)
            bounds = np.asarray([obstacle.bounds for obstacle in scene.obstacles_world])
            return bounds, scan.ranges, scan.valid, np.asarray([pose.as_array() for pose in queries])

        first = generate(12345)
        second = generate(12345)
        for left, right in zip(first, second):
            np.testing.assert_array_equal(left, right)


if __name__ == "__main__":
    unittest.main()
