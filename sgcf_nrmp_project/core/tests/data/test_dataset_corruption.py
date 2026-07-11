import json
import shutil
import tempfile
import unittest
from pathlib import Path

from sgcf_nrmp.data.datasets.validation import DatasetIntegrityError, validate_dataset
from data.dataset_test_utils import write_tiny_dataset


class DatasetCorruptionTest(unittest.TestCase):
    def test_valid_dataset_and_manifest_counts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); write_tiny_dataset(root); report=validate_dataset(root)
            self.assertTrue(report["valid"]); self.assertEqual(report["sample_count"],80); self.assertEqual(report["scene_count"],10)

    def test_corrupt_shard_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); write_tiny_dataset(root); path=sorted(root.rglob("*.npz"))[0]; path.write_bytes(b"corrupt")
            with self.assertRaises(DatasetIntegrityError): validate_dataset(root)

    def test_temporary_shard_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); write_tiny_dataset(root); (root/"train"/"shard_bad.npz.tmp").write_bytes(b"partial")
            with self.assertRaises(DatasetIntegrityError): validate_dataset(root)

    def test_manifest_scene_ids_match_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); write_tiny_dataset(root); manifest=json.loads((root/"split_manifest.json").read_text())
            scene_sets=[set(value["scene_ids"]) for value in manifest["splits"].values()]
            self.assertFalse(scene_sets[0]&scene_sets[1]); self.assertFalse(scene_sets[0]&scene_sets[2])

    def test_unlisted_shard_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); write_tiny_dataset(root); source=sorted(root.rglob("*.npz"))[0]
            shutil.copyfile(source,root/"train"/"shard_99999.npz")
            with self.assertRaises(DatasetIntegrityError): validate_dataset(root)
