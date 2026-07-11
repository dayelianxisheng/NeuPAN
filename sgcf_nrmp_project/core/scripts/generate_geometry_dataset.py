#!/usr/bin/env python3
"""Generate the deterministic geometry_v1 smoke dataset."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from time import perf_counter

import yaml

from sgcf_nrmp import __version__
from sgcf_nrmp.data.datasets.geometry_schema import schema_description
from sgcf_nrmp.data.datasets.manifest import atomic_write_json, canonical_hash
from sgcf_nrmp.data.datasets.validation import validate_dataset
from sgcf_nrmp.data.procedural.dataset_generator import generate_samples
from sgcf_nrmp.data.procedural.dataset_writer import AtomicShardWriter


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="sgcf_nrmp_project/core/configs/data/geometry_dataset.yaml")
    parser.add_argument("--output", default="sgcf_nrmp_project/artifacts/datasets/geometry_v1")
    args = parser.parse_args()
    config_path, output = Path(args.config), Path(args.output)
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    config_hash = canonical_hash(config)
    metadata_path = output / "metadata.json"
    if metadata_path.exists():
        existing = json.loads(metadata_path.read_text(encoding="utf-8"))
        if existing["config_hash"] != config_hash:
            raise ValueError("output already contains a dataset with a different config hash")
        print(json.dumps({"status": "already_complete", "integrity": validate_dataset(output)}, indent=2))
        return

    started = perf_counter()
    result = generate_samples(config)
    generation_seconds = perf_counter() - started
    writer = AtomicShardWriter(output, config)
    split_manifest: dict[str, object] = {"config_hash": config_hash, "splits": {}}
    for split, samples in result.samples_by_split.items():
        records = writer.write_split(split, samples, int(config["shard_size"]))
        split_manifest["splits"][split] = {
            "sample_count": len(samples),
            "scene_ids": result.scene_ids_by_split[split],
            "shards": records,
        }
    sample_count = sum(len(samples) for samples in result.samples_by_split.values())
    metadata = {
        "code_version": __version__,
        "config_hash": config_hash,
        "seed": int(config["seed"]),
        "sample_count": sample_count,
        "scene_count": int(config["scene_count"]),
        "fixed_point_count": int(config["fixed_point_count"]),
        "split_sample_counts": {name: len(samples) for name, samples in result.samples_by_split.items()},
        "split_scene_counts": {name: len(ids) for name, ids in result.scene_ids_by_split.items()},
        "generation_seconds": generation_seconds,
        "mean_scene_seconds": sum(result.scene_timings_seconds) / len(result.scene_timings_seconds),
    }
    writer.finalize(split_manifest, metadata)
    temporary = output / "config_snapshot.yaml.tmp"
    temporary.write_text(yaml.safe_dump(config, sort_keys=True), encoding="utf-8")
    os.replace(temporary, output / "config_snapshot.yaml")
    atomic_write_json(output / "dataset_schema.json", schema_description(int(config["fixed_point_count"])))
    print(json.dumps({"status": "generated", "metadata": metadata, "integrity": validate_dataset(output)}, indent=2))


if __name__ == "__main__":
    main()
