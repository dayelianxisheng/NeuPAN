import tempfile
import unittest
from pathlib import Path

import torch
from torch.utils.data import DataLoader

from sgcf_nrmp.data.datasets.geometry_dataset import GeometryClearanceDataset
from data.dataset_test_utils import write_tiny_dataset


class DatasetLoadingTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(); self.root=Path(self.temp.name); write_tiny_dataset(self.root)
    def tearDown(self) -> None: self.temp.cleanup()

    def test_length_dtype_and_shape(self) -> None:
        dataset=GeometryClearanceDataset(self.root,"train"); sample=dataset[0]
        self.assertEqual(len(dataset),56); self.assertEqual(sample["points_xy"].shape,(180,2)); self.assertEqual(sample["query_pose"].shape,(4,))
        self.assertEqual(sample["points_xy"].dtype,torch.float32); self.assertEqual(sample["point_valid_mask"].dtype,torch.bool)
        self.assertEqual(sample["observable_clearance"].shape,(1,)); self.assertEqual(sample["observable_gradient"].shape,(3,))

    def test_dataloader_batch_shape(self) -> None:
        batch=next(iter(DataLoader(GeometryClearanceDataset(self.root,"validation"),batch_size=4)))
        self.assertEqual(batch["points_xy"].shape,(4,180,2)); self.assertEqual(batch["world_collision"].shape,(4,1))

    def test_padding_is_masked(self) -> None:
        sample=GeometryClearanceDataset(self.root,"test")[0]; mask=sample["point_valid_mask"]
        self.assertTrue(torch.all(sample["points_xy"][~mask] == 0)); self.assertTrue(torch.all(sample["ranges"][~mask] == 0))

    def test_augmentation_is_explicit_and_deterministic(self) -> None:
        a=GeometryClearanceDataset(self.root,"train",True,99)[0]; b=GeometryClearanceDataset(self.root,"train",True,99)[0]
        self.assertTrue(torch.equal(a["points_xy"],b["points_xy"])); self.assertEqual(a["observable_clearance"],b["observable_clearance"])
