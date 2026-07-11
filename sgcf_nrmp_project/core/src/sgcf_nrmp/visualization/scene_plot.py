"""World geometry and LiDAR visibility plots."""

from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.axes import Axes
from matplotlib.patches import Polygon as PolygonPatch
from shapely.geometry import Polygon

from sgcf_nrmp.data.procedural.scene import ProceduralScene
from sgcf_nrmp.geometry.footprint import transform_footprint
from sgcf_nrmp.types.geometry import Pose2D
from sgcf_nrmp.types.lidar import LidarScan


def _add_polygon(ax: Axes, polygon: Polygon, **kwargs: object) -> None:
    ax.add_patch(PolygonPatch(np.asarray(polygon.exterior.coords), closed=True, **kwargs))


def configure_world_axes(ax: Axes, scene: ProceduralScene, title: str) -> None:
    x_min, y_min, x_max, y_max = scene.bounds
    ax.set(xlim=(x_min, x_max), ylim=(y_min, y_max), xlabel="world x [m]", ylabel="world y [m]", title=title)
    ax.set_aspect("equal", adjustable="box")
    ax.grid(alpha=0.2)


def draw_scene(ax: Axes, scene: ProceduralScene) -> None:
    for obstacle in scene.obstacles_world:
        _add_polygon(ax, obstacle, facecolor="0.35", edgecolor="black", alpha=0.8)


def draw_footprint(ax: Axes, footprint_robot: Polygon, pose_world: Pose2D, color: str = "tab:blue") -> None:
    _add_polygon(
        ax,
        transform_footprint(footprint_robot, pose_world),
        facecolor=color,
        edgecolor="black",
        alpha=0.45,
    )
    ax.arrow(
        pose_world.x,
        pose_world.y,
        0.55 * np.cos(pose_world.yaw),
        0.55 * np.sin(pose_world.yaw),
        width=0.025,
        color=color,
        length_includes_head=True,
    )


def plot_geometry(scene: ProceduralScene, footprint_robot: Polygon, sensor_pose_world: Pose2D, output_path: str) -> None:
    fig, ax = plt.subplots(figsize=(7, 6))
    draw_scene(ax, scene)
    draw_footprint(ax, footprint_robot, sensor_pose_world)
    configure_world_axes(ax, scene, f"{scene.name}: complete world geometry")
    fig.tight_layout()
    fig.savefig(output_path, dpi=150)
    plt.close(fig)


def plot_lidar_rays(
    scene: ProceduralScene,
    footprint_robot: Polygon,
    sensor_pose_world: Pose2D,
    scan: LidarScan,
    output_path: str,
) -> None:
    fig, ax = plt.subplots(figsize=(7, 6))
    draw_scene(ax, scene)
    draw_footprint(ax, footprint_robot, sensor_pose_world)
    origin = np.asarray([sensor_pose_world.x, sensor_pose_world.y])
    for point in scan.points_world:
        ax.plot([origin[0], point[0]], [origin[1], point[1]], color="tab:orange", alpha=0.25, linewidth=0.6)
    if scan.valid_count:
        ax.scatter(scan.points_world[:, 0], scan.points_world[:, 1], s=9, c="tab:red", label="visible LiDAR hit")
    ax.legend(loc="upper right")
    configure_world_axes(ax, scene, f"{scene.name}: nearest-hit LiDAR rays ({scan.valid_count} hits)")
    fig.tight_layout()
    fig.savefig(output_path, dpi=150)
    plt.close(fig)
