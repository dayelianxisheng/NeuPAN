import tempfile
import unittest
from pathlib import Path

from sgcf_nrmp.data.datasets.manifest import file_sha256
from data.dataset_test_utils import write_tiny_dataset


class DatasetReproducibilityTest(unittest.TestCase):
    def test_same_seed_produces_identical_shards(self) -> None:
        with tempfile.TemporaryDirectory() as left, tempfile.TemporaryDirectory() as right:
            write_tiny_dataset(Path(left),44); write_tiny_dataset(Path(right),44)
            a=[file_sha256(p) for p in sorted(Path(left).rglob("*.npz"))]; b=[file_sha256(p) for p in sorted(Path(right).rglob("*.npz"))]
            self.assertEqual(a,b)

    def test_safe_rerun_reuses_valid_shards(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            from data.dataset_test_utils import tiny_config
            from sgcf_nrmp.data.procedural.dataset_generator import generate_samples
            config=tiny_config(55); result=generate_samples(config)
            before={p.name:p.stat().st_mtime_ns for p in root.rglob("*.npz")}
            from sgcf_nrmp.data.procedural.dataset_writer import AtomicShardWriter
            writer=AtomicShardWriter(root,config)
            writer.write_split("train",result.samples_by_split["train"],config["shard_size"])
            before={p.name:p.stat().st_mtime_ns for p in root.rglob("*.npz")}
            # Simulate process restart before finalize: progress.json remains.
            writer=AtomicShardWriter(root,config)
            writer.write_split("train",result.samples_by_split["train"],config["shard_size"])
            after={p.name:p.stat().st_mtime_ns for p in root.rglob("*.npz")}
            self.assertEqual(before,after)
