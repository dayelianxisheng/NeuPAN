import tempfile
import unittest
from pathlib import Path

import numpy as np

from sgcf_nrmp.data.procedural.sample_builder import fixed_point_observation
from sgcf_nrmp.types.lidar import LidarScan
from sgcf_nrmp.types.lidar import LidarConfig
from data.dataset_test_utils import tiny_config, write_tiny_dataset


class DatasetGenerationTest(unittest.TestCase):
    def test_fixed_point_padding_and_alignment(self) -> None:
        valid = np.asarray([True, False, True])
        scan = LidarScan(np.asarray([1., 8., 2.]), valid, np.asarray([[1.,0.],[0.,2.]]), np.asarray([[1.,0.],[0.,2.]]), np.zeros(3))
        points, ranges, mask = fixed_point_observation(scan, 180)
        self.assertEqual(points.shape, (180,2)); self.assertEqual(mask.sum(), 2)
        np.testing.assert_allclose(ranges[:2], [1.,2.]); np.testing.assert_allclose(np.linalg.norm(points[:2],axis=1), ranges[:2])
        self.assertTrue(np.all(points[~mask] == 0)); self.assertTrue(np.all(ranges[~mask] == 0))

    def test_supported_fixed_sizes(self) -> None:
        scan = LidarScan(np.empty(0), np.empty(0,dtype=bool), np.empty((0,2)), np.empty((0,2)), np.empty(0))
        for size in (180,256,360): self.assertEqual(fixed_point_observation(scan,size)[0].shape,(size,2))

    def test_generated_values_are_finite_and_collision_consistent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            write_tiny_dataset(Path(directory))
            for path in Path(directory).rglob("*.npz"):
                with np.load(path) as data:
                    for key in data.files:
                        if np.issubdtype(data[key].dtype,np.floating): self.assertTrue(np.all(np.isfinite(data[key])))
                    self.assertTrue(np.all(data["world_clearance"][data["world_collision"]] == 0))

    def test_different_seed_changes_data(self) -> None:
        with tempfile.TemporaryDirectory() as left, tempfile.TemporaryDirectory() as right:
            write_tiny_dataset(Path(left), 1); write_tiny_dataset(Path(right), 2)
            a=np.load(sorted(Path(left).rglob("*.npz"))[0])["points_xy"]
            b=np.load(sorted(Path(right).rglob("*.npz"))[0])["points_xy"]
            self.assertFalse(np.array_equal(a,b))

    def test_config_hash_changes(self) -> None:
        from sgcf_nrmp.data.datasets.manifest import canonical_hash
        a=tiny_config(); b=tiny_config(); b["fixed_point_count"]=256
        self.assertNotEqual(canonical_hash(a),canonical_hash(b))

    def test_no_valid_observation_has_explicit_mask_and_invalid_gradient(self) -> None:
        from sgcf_nrmp.data.procedural.sample_builder import build_sample
        from sgcf_nrmp.data.procedural.scene import ProceduralScene
        from sgcf_nrmp.geometry.footprint import rectangular_footprint
        from sgcf_nrmp.types.geometry import Pose2D
        scene=ProceduralScene([],(-5,-5,5,5)); scan=scene.scan(Pose2D(0,0,0),LidarConfig(num_beams=180),np.random.default_rng(1))
        sample=build_sample(scene,rectangular_footprint(.8,.5),scan,Pose2D(0,0,0),"free",0,0,1,180,8.,.04,.04)
        self.assertFalse(sample["point_valid_mask"].any()); self.assertFalse(sample["observable_available"]); self.assertFalse(sample["observable_gradient_valid"])
