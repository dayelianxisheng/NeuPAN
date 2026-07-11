"""Observable/world clearance comparison and finite-difference vector fields."""

from __future__ import annotations

from dataclasses import dataclass

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Polygon as PolygonPatch
from shapely.geometry import Polygon

from sgcf_nrmp.data.procedural.scene import ProceduralScene
from sgcf_nrmp.geometry.footprint import transform_footprint
from sgcf_nrmp.types.geometry import Pose2D
from sgcf_nrmp.types.lidar import LidarScan


@dataclass(frozen=True)
class ClearanceGrid:
    x: np.ndarray
    y: np.ndarray
    observable: np.ndarray
    world: np.ndarray
    world_collision: np.ndarray


def compute_clearance_grid(
    scene: ProceduralScene,
    footprint_robot: Polygon,
    scan: LidarScan,
    observable_truncation: float,
    resolution: int,
    query_yaw: float = 0.0,
) -> ClearanceGrid:
    x_min, y_min, x_max, y_max = scene.bounds
    x = np.linspace(x_min, x_max, resolution)
    y = np.linspace(y_min, y_max, resolution)
    observable = np.empty((resolution, resolution), dtype=np.float64)
    world = np.empty_like(observable)
    collision = np.empty_like(observable, dtype=bool)
    for row, y_value in enumerate(y):
        for column, x_value in enumerate(x):
            label = scene.label(
                footprint_robot,
                Pose2D(float(x_value), float(y_value), query_yaw),
                scan,
                observable_truncation,
            )
            observable[row, column] = label.observable_clearance
            world[row, column] = label.world_clearance
            collision[row, column] = label.world_collision
    return ClearanceGrid(x, y, observable, world, collision)


def plot_clearance_comparison(grid: ClearanceGrid, scene_name: str, output_path: str) -> None:
    extent = (grid.x[0], grid.x[-1], grid.y[0], grid.y[-1])
    difference = np.abs(grid.observable - grid.world)
    fig, axes = plt.subplots(1, 3, figsize=(16, 4.8), constrained_layout=True)
    panels = [
        (grid.observable, "observable_clearance [m]", "viridis"),
        (grid.world, "world_clearance [m]", "viridis"),
        (difference, "absolute difference [m]", "magma"),
    ]
    common_max = max(float(np.max(grid.observable)), float(np.max(grid.world)))
    for index, (values, title, cmap) in enumerate(panels):
        vmax = common_max if index < 2 else max(float(np.max(difference)), 1e-6)
        image = axes[index].imshow(values, origin="lower", extent=extent, cmap=cmap, vmin=0.0, vmax=vmax)
        axes[index].set(title=title, xlabel="world x [m]", ylabel="world y [m]")
        axes[index].set_aspect("equal")
        fig.colorbar(image, ax=axes[index], shrink=0.82)
    fig.suptitle(f"{scene_name}: partial observation versus complete world")
    fig.savefig(output_path, dpi=150)
    plt.close(fig)


def plot_gradient_field(
    scene: ProceduralScene,
    footprint_robot: Polygon,
    scan: LidarScan,
    grid: ClearanceGrid,
    observable_truncation: float,
    spatial_step: float,
    angular_step: float,
    output_path: str,
) -> None:
    stride = max(1, len(grid.x) // 11)
    x_values = grid.x[::stride]
    y_values = grid.y[::stride]
    valid_xy: list[tuple[float, float, float, float]] = []
    invalid_xy: list[tuple[float, float]] = []
    for y_value in y_values:
        for x_value in x_values:
            pose = Pose2D(float(x_value), float(y_value), 0.0)
            gradient = scene.gradient(
                footprint_robot, pose, scan, observable_truncation,
                "observable_clearance", spatial_step, angular_step,
            )
            if gradient.gradient_valid:
                valid_xy.append((pose.x, pose.y, gradient.gx, gradient.gy))
            else:
                invalid_xy.append((pose.x, pose.y))

    extent = (grid.x[0], grid.x[-1], grid.y[0], grid.y[-1])
    fig, ax = plt.subplots(figsize=(7.5, 6.5))
    image = ax.imshow(grid.observable, origin="lower", extent=extent, cmap="viridis")
    fig.colorbar(image, ax=ax, label="observable_clearance [m]")
    if valid_xy:
        array = np.asarray(valid_xy)
        ax.quiver(array[:, 0], array[:, 1], array[:, 2], array[:, 3], color="white", scale=18, width=0.004, label="valid gradient")
    if invalid_xy:
        array = np.asarray(invalid_xy)
        ax.scatter(array[:, 0], array[:, 1], marker="x", s=18, c="red", label="gradient_valid=false")
    sample_pose = Pose2D(float(grid.x[len(grid.x) // 2]), float(grid.y[len(grid.y) // 2]), np.pi / 6)
    polygon = transform_footprint(footprint_robot, sample_pose)
    ax.add_patch(PolygonPatch(np.asarray(polygon.exterior.coords), facecolor="none", edgecolor="cyan", linewidth=2, label="sample footprint"))
    ax.set(title=f"{scene.name}: finite-difference observable gradient", xlabel="world x [m]", ylabel="world y [m]")
    ax.set_aspect("equal")
    ax.legend(loc="upper right", fontsize=8)
    fig.tight_layout()
    fig.savefig(output_path, dpi=150)
    plt.close(fig)
