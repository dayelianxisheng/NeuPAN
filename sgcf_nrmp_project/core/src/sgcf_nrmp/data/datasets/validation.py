"""Dataset manifest, shard, dtype and semantic integrity checks."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from sgcf_nrmp.data.datasets.geometry_schema import FIELD_DTYPES, SCHEMA_VERSION
from sgcf_nrmp.data.datasets.manifest import file_sha256


class DatasetIntegrityError(RuntimeError):
    pass


def validate_dataset(root: str | Path) -> dict[str, object]:
    root = Path(root)
    temporary = list(root.rglob("*.tmp"))
    if temporary:
        raise DatasetIntegrityError(f"temporary shard files present: {temporary}")
    metadata = json.loads((root / "metadata.json").read_text(encoding="utf-8"))
    manifest = json.loads((root / "split_manifest.json").read_text(encoding="utf-8"))
    if metadata["schema_version"] != SCHEMA_VERSION:
        raise DatasetIntegrityError("unsupported schema version")
    all_scene_ids: dict[str, set[int]] = {}
    expected_shards: set[Path] = set()
    total = 0
    nan_or_inf = 0
    for split, split_data in manifest["splits"].items():
        split_count = 0
        scene_ids: set[int] = set()
        for record in split_data["shards"]:
            path = root / record["path"]
            expected_shards.add(path.resolve())
            if not path.is_file() or file_sha256(path) != record["sha256"]:
                raise DatasetIntegrityError(f"missing or corrupt shard: {path}")
            try:
                with np.load(path, allow_pickle=False) as archive:
                    if set(archive.files) != set(FIELD_DTYPES):
                        raise DatasetIntegrityError(f"schema fields differ in {path}")
                    sample_count = int(archive["scene_id"].shape[0])
                    if sample_count != int(record["sample_count"]):
                        raise DatasetIntegrityError(f"sample count mismatch in {path}")
                    for key, dtype in FIELD_DTYPES.items():
                        if archive[key].dtype != np.dtype(dtype):
                            raise DatasetIntegrityError(f"dtype mismatch: {path}:{key}")
                        if np.issubdtype(archive[key].dtype, np.floating):
                            nan_or_inf += int(np.count_nonzero(~np.isfinite(archive[key])))
                    mask = archive["point_valid_mask"]
                    points = archive["points_xy"]
                    ranges = archive["ranges"]
                    if np.any(points[~mask] != 0) or np.any(ranges[~mask] != 0):
                        raise DatasetIntegrityError(f"non-zero padding in {path}")
                    if np.any(archive["world_collision"] & (archive["world_clearance"] != 0)):
                        raise DatasetIntegrityError(f"collision/clearance mismatch in {path}")
                    scene_ids.update(int(value) for value in np.unique(archive["scene_id"]))
                    split_count += sample_count
            except (OSError, ValueError, EOFError) as error:
                raise DatasetIntegrityError(f"cannot read shard {path}: {error}") from error
        if split_count != int(split_data["sample_count"]):
            raise DatasetIntegrityError(f"manifest split count mismatch: {split}")
        all_scene_ids[split] = scene_ids
        total += split_count
    names = list(all_scene_ids)
    for index, left in enumerate(names):
        for right in names[index + 1 :]:
            if all_scene_ids[left] & all_scene_ids[right]:
                raise DatasetIntegrityError(f"scene leakage between {left} and {right}")
    if nan_or_inf:
        raise DatasetIntegrityError(f"found {nan_or_inf} NaN/Inf values")
    if total != int(metadata["sample_count"]):
        raise DatasetIntegrityError("metadata sample count mismatch")
    actual_shards = {path.resolve() for path in root.rglob("*.npz")}
    if actual_shards != expected_shards:
        raise DatasetIntegrityError("manifest shard list differs from files on disk")
    return {
        "valid": True,
        "sample_count": total,
        "scene_count": sum(len(values) for values in all_scene_ids.values()),
        "nan_or_inf_count": nan_or_inf,
        "scene_leakage": False,
        "temporary_file_count": 0,
    }
