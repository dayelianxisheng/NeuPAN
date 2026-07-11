#!/usr/bin/env python3
"""Compute smoke-dataset statistics and required static visualizations."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib
import numpy as np
import yaml
from matplotlib import pyplot as plt
from matplotlib.patches import Polygon as PolygonPatch

matplotlib.use("Agg")

from sgcf_nrmp.data.datasets.geometry_dataset import GeometryClearanceDataset
from sgcf_nrmp.data.datasets.geometry_schema import QUERY_CATEGORY_NAMES, schema_description
from sgcf_nrmp.data.procedural.dataset_generator import make_scene


def _all_arrays(root: Path) -> dict[str, np.ndarray]:
    manifest = json.loads((root / "split_manifest.json").read_text(encoding="utf-8"))
    collected: dict[str, list[np.ndarray]] = {}
    for split in manifest["splits"].values():
        for record in split["shards"]:
            with np.load(root / record["path"], allow_pickle=False) as archive:
                for key in archive.files:
                    collected.setdefault(key, []).append(archive[key])
    return {key: np.concatenate(values) for key, values in collected.items()}


def _save_hist(values: np.ndarray, title: str, xlabel: str, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.hist(values, bins=40, color="tab:blue", alpha=0.8)
    ax.set(title=title, xlabel=xlabel, ylabel="samples")
    ax.grid(alpha=0.2)
    fig.tight_layout(); fig.savefig(path, dpi=150); plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("dataset")
    parser.add_argument("--output", default="sgcf_nrmp_project/artifacts/stages/stage_03_geometry_dataset")
    args = parser.parse_args()
    root, output = Path(args.dataset), Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    arrays = _all_arrays(root)
    metadata = json.loads((root / "metadata.json").read_text(encoding="utf-8"))
    manifest = json.loads((root / "split_manifest.json").read_text(encoding="utf-8"))
    observable, world = arrays["observable_clearance"], arrays["world_clearance"]
    difference = observable - world
    hidden_risk = arrays["world_collision"] & (observable >= 0.6)
    valid_counts = np.sum(arrays["point_valid_mask"], axis=1)
    categories = arrays["query_category"]
    summary = {
        "sample_count": int(len(observable)),
        "scene_count": int(metadata["scene_count"]),
        "split_sample_counts": metadata["split_sample_counts"],
        "split_scene_counts": metadata["split_scene_counts"],
        "observable_clearance_mean": float(np.mean(observable)),
        "world_clearance_mean": float(np.mean(world)),
        "observable_clearance_quantiles": np.quantile(observable, [0, .25, .5, .75, .9, .99, 1]).tolist(),
        "world_clearance_quantiles": np.quantile(world, [0, .25, .5, .75, .9, .99, 1]).tolist(),
        "world_collision_ratio": float(np.mean(arrays["world_collision"])),
        "observable_collision_ratio": float(np.mean(arrays["observable_collision"])),
        "observable_gradient_valid_ratio": float(np.mean(arrays["observable_gradient_valid"])),
        "world_gradient_valid_ratio": float(np.mean(arrays["world_gradient_valid"])),
        "no_valid_lidar_ratio": float(np.mean(valid_counts == 0)),
        "observable_world_abs_difference_mean": float(np.mean(np.abs(difference))),
        "partial_observation_hidden_collision_count": int(np.count_nonzero(hidden_risk)),
        "partial_observation_hidden_collision_ratio": float(np.mean(hidden_risk)),
        "query_category_counts": {
            QUERY_CATEGORY_NAMES[int(value)]: int(np.count_nonzero(categories == value)) for value in np.unique(categories)
        },
        "query_category_ratios": {
            QUERY_CATEGORY_NAMES[int(value)]: float(np.mean(categories == value)) for value in np.unique(categories)
        },
        "mean_scene_generation_seconds": float(metadata["mean_scene_seconds"]),
        "total_generation_seconds": float(metadata["generation_seconds"]),
        "dataset_size_bytes": int(sum(path.stat().st_size for path in root.rglob("*") if path.is_file())),
    }
    summary["estimated_bytes_per_10000_samples"] = int(summary["dataset_size_bytes"] / len(observable) * 10000)
    (output / "dataset_summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (output / "dataset_schema.json").write_text(json.dumps(schema_description(int(metadata["fixed_point_count"])), indent=2) + "\n", encoding="utf-8")
    split_summary = {name: {"samples": value["sample_count"], "scenes": len(value["scene_ids"])} for name, value in manifest["splits"].items()}
    (output / "split_summary.json").write_text(json.dumps(split_summary, indent=2) + "\n", encoding="utf-8")
    timing = {"total_seconds": metadata["generation_seconds"], "mean_scene_seconds": metadata["mean_scene_seconds"]}
    (output / "generation_timing.json").write_text(json.dumps(timing, indent=2) + "\n", encoding="utf-8")

    _save_hist(observable, "Observable clearance distribution", "observable_clearance [m]", output / "clearance_distribution.png")
    fig, ax = plt.subplots(figsize=(6, 5)); ax.scatter(world, observable, s=4, alpha=.25); limit=max(world.max(),observable.max()); ax.plot([0,limit],[0,limit],'k--'); ax.set(xlabel="world_clearance [m]",ylabel="observable_clearance [m]",title="Partial versus complete geometry"); fig.tight_layout(); fig.savefig(output/"observable_vs_world_scatter.png",dpi=150); plt.close(fig)
    fig, ax = plt.subplots(figsize=(7,4)); names=["observable valid","observable invalid","world valid","world invalid"]; vals=[np.mean(arrays["observable_gradient_valid"]),1-np.mean(arrays["observable_gradient_valid"]),np.mean(arrays["world_gradient_valid"]),1-np.mean(arrays["world_gradient_valid"])]; ax.bar(names,vals); ax.tick_params(axis='x',rotation=20); ax.set(ylabel="ratio",title="Gradient validity"); fig.tight_layout(); fig.savefig(output/"gradient_validity_distribution.png",dpi=150); plt.close(fig)
    fig, ax = plt.subplots(figsize=(7,4)); category_names=[QUERY_CATEGORY_NAMES[i] for i in sorted(QUERY_CATEGORY_NAMES)]; category_values=[np.mean(categories==i) for i in sorted(QUERY_CATEGORY_NAMES)]; ax.bar(category_names,category_values); ax.set(ylabel="ratio",title="Stratified query categories"); fig.tight_layout(); fig.savefig(output/"query_category_distribution.png",dpi=150); plt.close(fig)
    fig, ax = plt.subplots(figsize=(6,4)); split_names=list(split_summary); ax.bar(split_names,[split_summary[n]["samples"] for n in split_names]); ax.set(ylabel="samples",title="Scene-level split distribution"); fig.tight_layout(); fig.savefig(output/"split_distribution.png",dpi=150); plt.close(fig)

    dataset = GeometryClearanceDataset(root, "train")
    config = yaml.safe_load((root / "config_snapshot.yaml").read_text(encoding="utf-8"))
    indices = np.linspace(0, len(dataset)-1, 16, dtype=int)
    fig, axes = plt.subplots(4,4,figsize=(13,13))
    half_l, half_w = 0.4, 0.25
    local = np.asarray([[-half_l,-half_w],[half_l,-half_w],[half_l,half_w],[-half_l,half_w]])
    for ax, index in zip(axes.flat, indices):
        sample=dataset[int(index)]; mask=sample["point_valid_mask"].numpy(); points=sample["points_xy"].numpy()[mask]; query=sample["query_pose"].numpy(); yaw=np.arctan2(query[2],query[3]); c,s=np.cos(yaw),np.sin(yaw); rotation=np.asarray([[c,-s],[s,c]]); polygon=local@rotation.T+query[:2]
        scene_id=int(sample["scene_id"].item()); scene_seed=int(sample["seed"].item()); scene=make_scene(scene_id,config,np.random.default_rng(scene_seed))
        for obstacle in scene.obstacles_world:
            ax.add_patch(PolygonPatch(np.asarray(obstacle.exterior.coords),facecolor="0.85",edgecolor="0.55",linewidth=.6))
        if len(points): ax.scatter(points[:,0],points[:,1],s=4,c='black',label='LiDAR geometry')
        ax.add_patch(PolygonPatch(polygon,facecolor='tab:blue',alpha=.35)); ax.set_aspect('equal'); ax.set_xlim(-6,6); ax.set_ylim(-6,6); ax.set_title(f"o={sample['observable_clearance'].item():.2f} w={sample['world_clearance'].item():.2f}\ncol={bool(sample['world_collision'].item())} grad={bool(sample['observable_gradient_valid'].item())}",fontsize=8)
    fig.suptitle("Observed obstacle geometry, query footprint and labels"); fig.tight_layout(); fig.savefig(output/"sample_grid.png",dpi=150); plt.close(fig)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
