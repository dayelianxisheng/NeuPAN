"""Deterministic scene-level geometry dataset generation."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from time import perf_counter

import numpy as np
from shapely.ops import unary_union

from sgcf_nrmp.data.procedural.sample_builder import build_sample
from sgcf_nrmp.data.procedural.scene import ProceduralScene
from sgcf_nrmp.data.procedural.scene_generator import SceneGenerator, corridor_obstacles, rectangle_obstacle
from sgcf_nrmp.geometry.footprint import rectangular_footprint, transform_footprint
from sgcf_nrmp.types.geometry import Pose2D
from sgcf_nrmp.types.lidar import LidarConfig


@dataclass(frozen=True)
class GenerationResult:
    samples_by_split: dict[str, list[dict[str, np.ndarray]]]
    scene_ids_by_split: dict[str, list[int]]
    scene_timings_seconds: list[float]


def split_scene_ids(scene_count: int, split_ratios: dict[str, float], seed: int) -> dict[str, list[int]]:
    if set(split_ratios) != {"train", "validation", "test"}:
        raise ValueError("splits must be train, validation and test")
    if not np.isclose(sum(split_ratios.values()), 1.0):
        raise ValueError("split ratios must sum to 1")
    order = np.random.default_rng(seed).permutation(scene_count)
    train_end = int(round(scene_count * split_ratios["train"]))
    validation_end = train_end + int(round(scene_count * split_ratios["validation"]))
    return {
        "train": sorted(order[:train_end].tolist()),
        "validation": sorted(order[train_end:validation_end].tolist()),
        "test": sorted(order[validation_end:].tolist()),
    }


def _category_counts(total: int, ratios: dict[str, float]) -> dict[str, int]:
    names = ["free", "safety_boundary", "collision_boundary", "collision"]
    exact = np.asarray([ratios[f"{name}_ratio"] * total for name in names])
    counts = np.floor(exact).astype(int)
    for index in np.argsort(-(exact - counts))[: total - int(np.sum(counts))]:
        counts[index] += 1
    return dict(zip(names, counts.tolist()))


def sample_stratified_queries(
    scene: ProceduralScene,
    footprint_robot,
    count: int,
    ratios: dict[str, float],
    safety_distance: float,
    collision_boundary_width: float,
    rng: np.random.Generator,
) -> list[tuple[Pose2D, str]]:
    """Rejection sample four configured world-clearance strata."""
    required = _category_counts(count, ratios)
    bins: dict[str, list[Pose2D]] = defaultdict(list)
    world = unary_union(scene.obstacles_world)
    x_min, y_min, x_max, y_max = scene.bounds
    attempts = 0
    while any(len(bins[name]) < amount for name, amount in required.items()) and attempts < 30000:
        attempts += 1
        pose = Pose2D(
            float(rng.uniform(x_min, x_max)),
            float(rng.uniform(y_min, y_max)),
            float(rng.uniform(-np.pi, np.pi)),
        )
        footprint_world = transform_footprint(footprint_robot, pose)
        if footprint_world.intersects(world):
            category = "collision"
        else:
            clearance = float(footprint_world.distance(world))
            if clearance <= collision_boundary_width:
                category = "collision_boundary"
            elif abs(clearance - safety_distance) <= collision_boundary_width:
                category = "safety_boundary"
            elif clearance > safety_distance + collision_boundary_width:
                category = "free"
            else:
                continue
        if len(bins[category]) < required[category]:
            bins[category].append(pose)
    missing = {name: required[name] - len(bins[name]) for name in required if len(bins[name]) < required[name]}
    if missing:
        raise RuntimeError(f"unable to sample query categories: {missing}")
    result = [(pose, name) for name in required for pose in bins[name]]
    permutation = rng.permutation(len(result))
    return [result[index] for index in permutation]


def make_scene(scene_id: int, config: dict, rng: np.random.Generator) -> ProceduralScene:
    bounds = tuple(float(value) for value in config["scene"]["bounds"])
    obstacle_count = int(rng.integers(config["scene"]["obstacle_count_min"], config["scene"]["obstacle_count_max"] + 1))
    if scene_id % 5 == 0:
        clear_width = float(rng.uniform(1.4, 2.5))
        obstacles = corridor_obstacles((bounds[0], bounds[2]), 0.0, clear_width, 0.25)
        for _ in range(max(1, obstacle_count - 2)):
            obstacles.append(
                rectangle_obstacle(
                    (float(rng.uniform(-4.5, 4.5)), float(rng.uniform(-0.45 * clear_width, 0.45 * clear_width))),
                    float(rng.uniform(0.25, 0.7)), float(rng.uniform(0.2, 0.6)), float(rng.uniform(-np.pi, np.pi)),
                )
            )
        return ProceduralScene(obstacles, bounds, f"corridor_{scene_id}", {"layout": "corridor"})
    scene = SceneGenerator(rng).random_scene(bounds, obstacle_count, name=f"random_{scene_id}")
    scene.metadata["layout"] = "random"
    return scene


def generate_samples(config: dict) -> GenerationResult:
    seed = int(config["seed"])
    split_ids = split_scene_ids(int(config["scene_count"]), config["splits"], seed)
    split_for_scene = {scene_id: split_name for split_name, ids in split_ids.items() for scene_id in ids}
    footprint = rectangular_footprint(config["footprint"]["length"], config["footprint"]["width"])
    lidar = LidarConfig(**config["lidar"])
    labels = config["labels"]
    samples: dict[str, list[dict[str, np.ndarray]]] = {name: [] for name in split_ids}
    timings: list[float] = []
    for scene_id in range(int(config["scene_count"])):
        started = perf_counter()
        scene_seed = seed + scene_id * 100003
        rng = np.random.default_rng(scene_seed)
        scene = make_scene(scene_id, config, rng)
        scan = scene.scan(Pose2D(0.0, 0.0, 0.0), lidar, rng)
        queries = sample_stratified_queries(
            scene, footprint, int(config["queries_per_scene"]), config["query_sampling"],
            float(labels["safety_distance"]), float(labels["collision_boundary_width"]), rng,
        )
        for query_id, (pose, category) in enumerate(queries):
            samples[split_for_scene[scene_id]].append(
                build_sample(
                    scene, footprint, scan, pose, category, scene_id, query_id, scene_seed,
                    int(config["fixed_point_count"]), float(labels["observable_truncation"]),
                    float(labels["spatial_step"]), float(labels["angular_step"]),
                )
            )
        timings.append(perf_counter() - started)
    return GenerationResult(samples, split_ids, timings)
