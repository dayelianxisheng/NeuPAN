#!/usr/bin/env python3
"""Write deterministic known-case validation and random-scene statistics."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

from sgcf_nrmp.data.procedural.query_sampler import sample_query_poses
from sgcf_nrmp.data.procedural.scene import ProceduralScene
from sgcf_nrmp.data.procedural.scene_generator import SceneGenerator, circle_obstacle, wall_obstacle
from sgcf_nrmp.geometry.footprint import rectangular_footprint
from sgcf_nrmp.types.geometry import Pose2D
from sgcf_nrmp.types.lidar import LidarConfig


def known_cases() -> dict[str, object]:
    footprint = rectangular_footprint(2.0, 1.0)
    lidar = LidarConfig(-np.pi, np.pi, 361, 0.05, 10.0)
    circle_scene = ProceduralScene([circle_obstacle((4, 0), 1.0, 64)], (-6, -6, 6, 6))
    circle_scan = circle_scene.scan(Pose2D(0, 0, 0), lidar, np.random.default_rng(1))
    circle_label = circle_scene.label(footprint, Pose2D(0, 0, 0), circle_scan, 10.0)

    wall_scene = ProceduralScene([wall_obstacle((4, -5), (4, 5), 0.2)], (-6, -6, 6, 6))
    wall_scan = wall_scene.scan(Pose2D(0, 0, 0), lidar, np.random.default_rng(2))
    wall_gradient = wall_scene.gradient(footprint, Pose2D(0, 0, 0.35), wall_scan, 10.0, "world_clearance", 0.01, 0.01)
    return {
        "circle_expected_clearance_m": 2.0,
        "circle_world_clearance_m": circle_label.world_clearance,
        "circle_observable_clearance_m": circle_label.observable_clearance,
        "circle_absolute_error_m": abs(circle_label.world_clearance - 2.0),
        "wall_expected_gradient_xy": [-1.0, 0.0],
        "wall_gradient": wall_gradient.as_array().tolist(),
        "wall_gradient_valid": wall_gradient.gradient_valid,
        "pass": abs(circle_label.world_clearance - 2.0) < 0.003
        and abs(wall_gradient.gx + 1.0) < 1e-5
        and abs(wall_gradient.gy) < 1e-5,
    }


def random_statistics(seed: int, scene_count: int) -> dict[str, object]:
    rng = np.random.default_rng(seed)
    footprint = rectangular_footprint(0.8, 0.5)
    lidar = LidarConfig(-np.pi, np.pi, 31, 0.05, 7.0, 0.005, 0.05)
    differences: list[float] = []
    hit_counts: list[int] = []
    collisions = 0
    digest = hashlib.sha256()
    for index in range(scene_count):
        scene = SceneGenerator(rng).random_scene((-6, -6, 6, 6), 6, name=f"random_{index}")
        scan = scene.scan(Pose2D(0, 0, 0), lidar, rng)
        queries = sample_query_poses((-4.5, -4.5, 4.5, 4.5), 3, rng)
        digest.update(np.asarray([obstacle.bounds for obstacle in scene.obstacles_world], dtype=np.float64).tobytes())
        digest.update(scan.ranges.tobytes())
        hit_counts.append(scan.valid_count)
        for query in queries:
            label = scene.label(footprint, query, scan, lidar.range_max)
            differences.append(abs(label.observable_clearance - label.world_clearance))
            collisions += int(label.world_collision)
    values = np.asarray(differences)
    return {
        "seed": seed,
        "scene_count": scene_count,
        "query_count": len(differences),
        "nan_or_inf_count": int(np.count_nonzero(~np.isfinite(values))),
        "world_collision_count": collisions,
        "mean_valid_lidar_hits": float(np.mean(hit_counts)),
        "mean_absolute_clearance_difference_m": float(np.mean(values)),
        "max_absolute_clearance_difference_m": float(np.max(values)),
        "reproducibility_sha256": digest.hexdigest(),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="sgcf_nrmp_project/artifacts/stages/stage_02_procedural_geometry")
    parser.add_argument("--seed", type=int, default=20260711)
    parser.add_argument("--scene-count", type=int, default=1000)
    args = parser.parse_args()
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    known = known_cases()
    statistics = random_statistics(args.seed, args.scene_count)
    (output / "known_case_validation.json").write_text(json.dumps(known, indent=2) + "\n", encoding="utf-8")
    (output / "random_scene_statistics.json").write_text(json.dumps(statistics, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"known": known, "random": statistics}, indent=2))


if __name__ == "__main__":
    main()
