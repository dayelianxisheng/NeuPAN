#!/usr/bin/env python3
"""Generate the three immutable-input Stage 15C semantic overlays."""

from __future__ import annotations

import json
import math
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "sgcf_nrmp_project/gazebo/overlays/stage15c_feasible_semantics"

HEADER = """<?xml version='1.0'?>
<sdf version='1.9'><world name='{name}'><gravity>0 0 -9.81</gravity>
<plugin filename='gz-sim-physics-system' name='gz::sim::systems::Physics'/>
<plugin filename='gz-sim-user-commands-system' name='gz::sim::systems::UserCommands'/>
<plugin filename='gz-sim-scene-broadcaster-system' name='gz::sim::systems::SceneBroadcaster'/>
<plugin filename='gz-sim-sensors-system' name='gz::sim::systems::Sensors'><render_engine>ogre2</render_engine></plugin>
<model name='ground_plane'><static>true</static><link name='ground'><collision name='collision'><geometry><plane><normal>0 0 1</normal><size>20 20</size></plane></geometry></collision><visual name='visual'><geometry><plane><normal>0 0 1</normal><size>20 20</size></plane></geometry></visual></link></model>
<include><uri>model://sgcf_diff_drive_robot</uri><name>sgcf_robot</name><pose>0 0 0 0 0 0</pose></include>
"""

SCENES = [
    {
        "scene_id": "stage15c_human_side_feasible",
        "reference_waypoints": [[0, 0], [0, 0.95], [1.5, 1.05], [2.7, 0.95], [4, 0]],
        "obstacles": [{"name": "human_01", "class_name": "HUMAN", "model": "human_placeholder", "center": [1.5, 0.0], "z": 0.85}],
    },
    {
        "scene_id": "stage15c_vehicle_side_feasible",
        "reference_waypoints": [[0, 0], [0, 1.25], [1.5, 1.35], [2.7, 1.25], [4, 0]],
        "obstacles": [{"name": "vehicle_01", "class_name": "VEHICLE", "model": "vehicle_placeholder", "center": [1.5, 0.0], "z": 0.2}],
    },
    {
        "scene_id": "stage15c_mixed_feasible",
        "reference_waypoints": [[0, 0], [0, 0.95], [1.5, 1.05], [2.7, 0.95], [4, 0]],
        "obstacles": [
            {"name": "human_01", "class_name": "HUMAN", "model": "human_placeholder", "center": [1.5, 0.0], "z": 0.85},
            {"name": "static_01", "class_name": "STATIC_OBSTACLE", "model": "static_cylinder", "center": [2.7, -1.2], "z": 0.35},
            {"name": "vehicle_01", "class_name": "VEHICLE", "model": "vehicle_placeholder", "center": [3.3, -1.3], "z": 0.2},
        ],
    },
]


def path_length(points: list[list[float]]) -> float:
    return sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(points, points[1:]))


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = []
    for scene in SCENES:
        body = HEADER.format(name=scene["scene_id"])
        for obstacle in scene["obstacles"]:
            x, y = obstacle["center"]
            body += f"<include><uri>model://{obstacle['model']}</uri><name>{obstacle['name']}</name><pose>{x} {y} {obstacle['z']} 0 0 0</pose></include>\n"
        body += "</world></sdf>\n"
        world = OUT / f"{scene['scene_id']}.sdf"
        world.write_text(body)
        length = path_length(scene["reference_waypoints"])
        manifest.append({
            **scene,
            "world": str(world.relative_to(ROOT)),
            "base_contract": "human_path_side",
            "start": [0.0, 0.0, 0.0],
            "goal": [4.0, 0.0, 0.0],
            "path_length_m": length,
            "control_window_s": max(30.0, 2.0 * length / 0.30),
            "semantic_source": "ORACLE_GROUND_TRUTH",
            "simulation_only": True,
            "not_stage10_prediction": True,
        })
    (OUT / "manifest.json").write_text(json.dumps({"scenarios": manifest}, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
