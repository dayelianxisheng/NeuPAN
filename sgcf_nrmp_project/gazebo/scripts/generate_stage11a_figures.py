#!/usr/bin/env python3
"""Generate contract diagrams from the validated Stage 11A assets."""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import Circle, FancyArrowPatch, Rectangle


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT.parent / "artifacts/stages/stage_11a_gazebo_preparation"


def save(name: str) -> None:
    plt.tight_layout()
    plt.savefig(OUT / name, dpi=160)
    plt.close()


def arrow(ax, start, end, label: str) -> None:
    ax.add_patch(FancyArrowPatch(start, end, arrowstyle="->", mutation_scale=14))
    ax.text((start[0] + end[0]) / 2, (start[1] + end[1]) / 2 + 0.08, label, ha="center", fontsize=8)


def frame_tree() -> None:
    positions = {"world": (0, 3), "odom": (0, 2), "base_footprint": (0, 1), "base_link": (0, 0), "lidar_link": (-1.5, -1), "camera_link": (1.5, -1), "camera_optical_frame": (1.5, -2)}
    fig, ax = plt.subplots(figsize=(7, 6))
    for name, position in positions.items():
        ax.text(*position, name, ha="center", va="center", bbox={"boxstyle": "round", "facecolor": "white"})
    for parent, child in (("world", "odom"), ("odom", "base_footprint"), ("base_footprint", "base_link"), ("base_link", "lidar_link"), ("base_link", "camera_link"), ("camera_link", "camera_optical_frame")):
        arrow(ax, positions[parent], positions[child], "")
    ax.set_title("Stage 11A frame contract (static specification)")
    ax.set_xlim(-2.5, 2.5); ax.set_ylim(-2.5, 3.5); ax.axis("off"); save("gazebo_frame_tree.png")


def footprint() -> None:
    fig, ax = plt.subplots(figsize=(6, 5))
    ax.add_patch(Rectangle((-0.4, -0.25), 0.8, 0.5, fill=False, linewidth=4, label="Gazebo collision"))
    ax.add_patch(Rectangle((-0.4, -0.25), 0.8, 0.5, fill=False, linestyle="--", linewidth=2, label="Stage 05 footprint"))
    ax.scatter([0], [0], marker="+", s=100, color="black", label="base_footprint")
    ax.set_aspect("equal"); ax.set_xlim(-0.6, 0.6); ax.set_ylim(-0.45, 0.45); ax.set_xlabel("x forward [m]"); ax.set_ylabel("y left [m]"); ax.legend(); ax.set_title("Exact 0.8 x 0.5 m footprint overlay"); save("robot_footprint_comparison.png")


def scenarios() -> None:
    manifest = json.loads((OUT / "gazebo_scenario_manifest.json").read_text())
    fig, axes = plt.subplots(3, 4, figsize=(12, 8), sharex=True, sharey=True)
    for ax, scene in zip(axes.ravel(), manifest["scenarios"]):
        for obstacle in scene["obstacles"]:
            x, y, _ = obstacle["pose"]
            if obstacle["shape"] == "cylinder":
                ax.add_patch(Circle((x, y), obstacle["radius"], alpha=0.5))
            else:
                sx, sy = obstacle["size_xy"]
                ax.add_patch(Rectangle((x - sx / 2, y - sy / 2), sx, sy, alpha=0.5))
        ax.plot(scene["start_pose"][0], scene["start_pose"][1], "go")
        ax.plot(4.0, 0.0, "r*")
        ax.set_title(scene["scene_id"], fontsize=8); ax.grid(alpha=0.2); ax.set_aspect("equal")
    axes[0, 0].set_xlim(-0.5, 4.5); axes[0, 0].set_ylim(-1.3, 1.3)
    fig.suptitle("Generated SDF scenario manifest (not simulator screenshots)"); save("gazebo_scenario_overview.png")


def sensor_layout() -> None:
    fig, ax = plt.subplots(figsize=(7, 5))
    ax.add_patch(Rectangle((-0.4, 0), 0.8, 0.2, alpha=0.3, label="robot body"))
    ax.scatter([0], [0.2], label="lidar_link z=0.2 m")
    ax.scatter([0], [1.0], label="camera optical center z=1.0 m")
    ax.plot([-1, 0, 1], [0.6, 0.2, 0.6], "C0--", label="LiDAR horizontal scan")
    ax.plot([-0.9, 0, 0.9], [0.2, 1.0, 0.2], "C1--", label="camera HFOV 1.453 rad")
    ax.set_xlim(-1.2, 1.2); ax.set_ylim(-0.05, 1.2); ax.set_xlabel("forward/lateral schematic [m]"); ax.set_ylabel("z [m]"); ax.legend(); ax.set_title("Validated LiDAR-camera extrinsic layout"); save("lidar_camera_layout.png")


def flow(name: str, nodes: list[str], title: str) -> None:
    fig, ax = plt.subplots(figsize=(12, 3))
    xs = list(range(len(nodes)))
    for x, node in zip(xs, nodes):
        ax.text(x, 0, node, ha="center", va="center", bbox={"boxstyle": "round", "facecolor": "white"}, fontsize=8)
    for first, second in zip(xs, xs[1:]):
        arrow(ax, (first + 0.18, 0), (second - 0.18, 0), "")
    ax.set_xlim(-0.5, len(nodes) - 0.5); ax.set_ylim(-0.6, 0.6); ax.axis("off"); ax.set_title(title); save(name)


def main() -> None:
    frame_tree(); footprint(); scenarios(); sensor_layout()
    flow("gazebo_to_planner_dataflow.png", ["Gazebo scan", "frame/time adapter", "ordered observable points", "Exact Geometry", "frozen planner", "command safety"], "Stage 11A Gazebo-to-planner contract")
    flow("future_ros2_node_graph.png", ["gz sim", "ROS bridge", "sensor adapters", "SGCF planner", "safety monitor", "cmd_vel"], "Future ROS 2 graph plan (not implemented)")


if __name__ == "__main__":
    main()
