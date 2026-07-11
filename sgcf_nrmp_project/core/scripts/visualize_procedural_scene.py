#!/usr/bin/env python3
"""Generate the three required deterministic stage-02 visual cases."""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib
import numpy as np
import yaml

matplotlib.use("Agg")

from sgcf_nrmp.data.procedural.scene import ProceduralScene
from sgcf_nrmp.data.procedural.scene_generator import circle_obstacle, corridor_obstacles, rectangle_obstacle, wall_obstacle
from sgcf_nrmp.geometry.footprint import rectangular_footprint
from sgcf_nrmp.types.geometry import Pose2D
from sgcf_nrmp.types.lidar import LidarConfig
from sgcf_nrmp.visualization import (
    compute_clearance_grid,
    plot_clearance_comparison,
    plot_geometry,
    plot_gradient_field,
    plot_lidar_rays,
)


def cases() -> list[tuple[ProceduralScene, Pose2D, LidarConfig]]:
    return [
        (
            ProceduralScene([circle_obstacle((3.2, 0.2), 0.75, 64)], (-2.5, -3.5, 6.0, 3.5), "scene_01_single_circle"),
            Pose2D(0.0, 0.0, 0.0),
            LidarConfig(-np.pi, np.pi, 181, 0.05, 8.0),
        ),
        (
            ProceduralScene(
                [wall_obstacle((2.0, -1.2), (2.0, 1.2), 0.25), rectangle_obstacle((4.0, 0.0), 1.3, 2.8), circle_obstacle((-1.5, 0.0), 0.45)],
                (-3.5, -3.5, 6.0, 3.5),
                "scene_02_occlusion_and_fov",
            ),
            Pose2D(0.0, 0.0, 0.0),
            LidarConfig(-np.pi / 2, np.pi / 2, 181, 0.05, 8.0),
        ),
        (
            ProceduralScene(
                corridor_obstacles((-4.0, 6.0), 0.0, 2.1, 0.3) + [rectangle_obstacle((2.4, 0.45), 0.7, 0.55, 0.25)],
                (-4.0, -3.0, 6.0, 3.0),
                "scene_03_narrow_corridor",
            ),
            Pose2D(-2.5, 0.0, 0.0),
            LidarConfig(-np.pi, np.pi, 241, 0.05, 8.0),
        ),
    ]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="sgcf_nrmp_project/core/configs/data/procedural.yaml")
    parser.add_argument("--output", default="sgcf_nrmp_project/artifacts/stages/stage_02_procedural_geometry")
    args = parser.parse_args()
    config = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    footprint = rectangular_footprint(config["footprint"]["length"], config["footprint"]["width"])
    label_config = config["labels"]
    resolution = int(config["visualization"]["grid_resolution"])
    seed = int(config["seed"])

    for index, (scene, sensor_pose, lidar_config) in enumerate(cases(), start=1):
        scan = scene.scan(sensor_pose, lidar_config, np.random.default_rng(seed + index))
        prefix = output / f"scene_{index:02d}"
        grid = compute_clearance_grid(scene, footprint, scan, label_config["observable_truncation"], resolution)
        plot_geometry(scene, footprint, sensor_pose, f"{prefix}_geometry.png")
        plot_lidar_rays(scene, footprint, sensor_pose, scan, f"{prefix}_lidar_rays.png")
        plot_clearance_comparison(grid, scene.name, f"{prefix}_clearance_comparison.png")
        plot_gradient_field(
            scene, footprint, scan, grid, label_config["observable_truncation"],
            label_config["spatial_step"], label_config["angular_step"],
            f"{prefix}_gradient_field.png",
        )
        print(f"{scene.name}: hits={scan.valid_count}, max_difference={np.max(np.abs(grid.observable-grid.world)):.3f}")


if __name__ == "__main__":
    main()
