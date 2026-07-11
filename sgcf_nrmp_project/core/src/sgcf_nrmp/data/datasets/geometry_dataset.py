"""Lazy sharded PyTorch Dataset for geometry_v1."""

from __future__ import annotations

import bisect
import json
from pathlib import Path

import numpy as np
import torch
from torch.utils.data import Dataset


class GeometryClearanceDataset(Dataset):
    """Load one split and keep at most one compressed NPZ shard cached."""

    def __init__(
        self,
        root: str | Path,
        split: str,
        augmentation: bool = False,
        augmentation_seed: int = 0,
        rotation_limit: float = 0.10,
    ) -> None:
        self.root = Path(root)
        manifest = json.loads((self.root / "split_manifest.json").read_text(encoding="utf-8"))
        if split not in manifest["splits"]:
            raise ValueError(f"unknown split: {split}")
        self.records = manifest["splits"][split]["shards"]
        self.cumulative: list[int] = []
        total = 0
        for record in self.records:
            total += int(record["sample_count"])
            self.cumulative.append(total)
        self.total = total
        self.augmentation = augmentation
        self.augmentation_seed = int(augmentation_seed)
        self.rotation_limit = float(rotation_limit)
        self._cached_index: int | None = None
        self._cached_arrays: dict[str, np.ndarray] | None = None

    def __len__(self) -> int:
        return self.total

    def _load_shard(self, shard_index: int) -> dict[str, np.ndarray]:
        if self._cached_index != shard_index:
            path = self.root / self.records[shard_index]["path"]
            with np.load(path, allow_pickle=False) as archive:
                self._cached_arrays = {key: archive[key] for key in archive.files}
            self._cached_index = shard_index
        assert self._cached_arrays is not None
        return self._cached_arrays

    def __getitem__(self, index: int) -> dict[str, torch.Tensor]:
        if index < 0:
            index += self.total
        if index < 0 or index >= self.total:
            raise IndexError(index)
        shard_index = bisect.bisect_right(self.cumulative, index)
        previous = 0 if shard_index == 0 else self.cumulative[shard_index - 1]
        local_index = index - previous
        arrays = self._load_shard(shard_index)
        sample = {key: np.array(value[local_index], copy=True) for key, value in arrays.items()}
        if self.augmentation:
            self._rotate_consistently(sample, index)
        tensor_sample: dict[str, torch.Tensor] = {}
        for key, value in sample.items():
            tensor = torch.from_numpy(np.asarray(value))
            if tensor.ndim == 0:
                tensor = tensor.reshape(1)
            tensor_sample[key] = tensor
        return tensor_sample

    def _rotate_consistently(self, sample: dict[str, np.ndarray], index: int) -> None:
        rng = np.random.default_rng(self.augmentation_seed + index)
        angle = float(rng.uniform(-self.rotation_limit, self.rotation_limit))
        c, s = np.cos(angle), np.sin(angle)
        rotation = np.asarray([[c, -s], [s, c]], dtype=np.float32)
        sample["points_xy"] = sample["points_xy"] @ rotation.T
        query = sample["query_pose"]
        query[:2] = rotation @ query[:2]
        yaw = np.arctan2(query[2], query[3]) + angle
        query[2:4] = [np.sin(yaw), np.cos(yaw)]
        for key in ("observable_gradient", "world_gradient"):
            sample[key][:2] = rotation @ sample[key][:2]
