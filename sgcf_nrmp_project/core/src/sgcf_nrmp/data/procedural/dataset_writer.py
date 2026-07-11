"""Atomic, checksummed NPZ shard writer with safe deterministic resume."""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np

from sgcf_nrmp.data.datasets.geometry_schema import SCHEMA_VERSION
from sgcf_nrmp.data.datasets.manifest import atomic_write_json, canonical_hash, file_sha256


def stack_samples(samples: list[dict[str, np.ndarray]]) -> dict[str, np.ndarray]:
    if not samples:
        raise ValueError("cannot stack an empty sample list")
    return {key: np.stack([sample[key] for sample in samples]) for key in samples[0]}


class AtomicShardWriter:
    def __init__(self, root: Path, config: dict) -> None:
        self.root = Path(root)
        self.config = config
        self.config_hash = canonical_hash(config)
        self.progress_path = self.root / "progress.json"
        self.root.mkdir(parents=True, exist_ok=True)
        if self.progress_path.exists():
            import json

            progress = json.loads(self.progress_path.read_text(encoding="utf-8"))
            if progress["config_hash"] != self.config_hash:
                raise ValueError("existing partial dataset has a different config hash")
            self.progress = progress
        else:
            self.progress = {"config_hash": self.config_hash, "shards": {}}

    def write_split(self, split: str, samples: list[dict[str, np.ndarray]], shard_size: int) -> list[dict[str, object]]:
        split_dir = self.root / split
        split_dir.mkdir(parents=True, exist_ok=True)
        records: list[dict[str, object]] = []
        for shard_index, start in enumerate(range(0, len(samples), shard_size)):
            shard_samples = samples[start : start + shard_size]
            relative = f"{split}/shard_{shard_index:05d}.npz"
            destination = self.root / relative
            previous = self.progress["shards"].get(relative)
            if previous and destination.exists() and file_sha256(destination) == previous["sha256"]:
                records.append(previous)
                continue
            temporary = destination.with_suffix(".npz.tmp")
            with temporary.open("wb") as stream:
                np.savez_compressed(stream, **stack_samples(shard_samples))
            os.replace(temporary, destination)
            record = {
                "path": relative,
                "sample_count": len(shard_samples),
                "sha256": file_sha256(destination),
                "size_bytes": destination.stat().st_size,
            }
            self.progress["shards"][relative] = record
            atomic_write_json(self.progress_path, self.progress)
            records.append(record)
        return records

    def finalize(self, manifest: dict[str, object], metadata: dict[str, object]) -> None:
        atomic_write_json(self.root / "split_manifest.json", manifest)
        atomic_write_json(self.root / "metadata.json", {"schema_version": SCHEMA_VERSION, **metadata})
        self.progress_path.unlink(missing_ok=True)
