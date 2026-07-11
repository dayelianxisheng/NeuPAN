"""Small deterministic dataset fixture helpers."""

from __future__ import annotations

from pathlib import Path

from sgcf_nrmp.data.datasets.manifest import canonical_hash
from sgcf_nrmp.data.procedural.dataset_generator import generate_samples
from sgcf_nrmp.data.procedural.dataset_writer import AtomicShardWriter


def tiny_config(seed: int = 123) -> dict:
    return {
        "schema_version": "geometry_v1", "seed": seed, "scene_count": 10,
        "queries_per_scene": 8, "shard_size": 13, "fixed_point_count": 180,
        "scene": {"bounds": [-6.,-6.,6.,6.], "obstacle_count_min": 4, "obstacle_count_max": 6, "corridor_probability": .2},
        "footprint": {"length": .8, "width": .5},
        "lidar": {"angle_min": -3.141592653589793, "angle_max": 3.141592653589793, "num_beams": 180, "range_min": .05, "range_max": 8., "range_noise_std": 0., "dropout_probability": .02},
        "labels": {"observable_truncation": 8., "spatial_step": .04, "angular_step": .04, "safety_distance": .6, "collision_boundary_width": .2},
        "query_sampling": {"free_ratio": .25, "safety_boundary_ratio": .25, "collision_boundary_ratio": .25, "collision_ratio": .25},
        "splits": {"train": .7, "validation": .2, "test": .1},
    }


def write_tiny_dataset(root: Path, seed: int = 123) -> tuple[dict, object]:
    config = tiny_config(seed)
    result = generate_samples(config)
    writer = AtomicShardWriter(root, config)
    manifest = {"config_hash": canonical_hash(config), "splits": {}}
    for split, samples in result.samples_by_split.items():
        records = writer.write_split(split, samples, config["shard_size"])
        manifest["splits"][split] = {"sample_count": len(samples), "scene_ids": result.scene_ids_by_split[split], "shards": records}
    writer.finalize(manifest, {"config_hash": canonical_hash(config), "seed": seed, "sample_count": 80, "scene_count": 10, "fixed_point_count": 180})
    return config, result
