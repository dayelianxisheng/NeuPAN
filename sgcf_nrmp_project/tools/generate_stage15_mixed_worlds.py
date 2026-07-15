"""Generate deterministic Stage 15 mixed STATIC / HUMAN / VEHICLE overlays."""
from __future__ import annotations

import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "sgcf_nrmp_project/gazebo/overlays/stage15_oracle_mixed"
MANIFEST = OUT / "manifest.json"
FIXED = (101, 202, 303)
RANDOM = tuple(range(1000, 1020))

TEMPLATE = """<?xml version='1.0'?>
<sdf version='1.9'><world name='{name}'><gravity>0 0 -9.81</gravity>
<plugin filename='gz-sim-physics-system' name='gz::sim::systems::Physics'/>
<plugin filename='gz-sim-user-commands-system' name='gz::sim::systems::UserCommands'/>
<plugin filename='gz-sim-scene-broadcaster-system' name='gz::sim::systems::SceneBroadcaster'/>
<plugin filename='gz-sim-sensors-system' name='gz::sim::systems::Sensors'><render_engine>ogre2</render_engine></plugin>
<model name='ground_plane'><static>true</static><link name='ground'><collision name='collision'><geometry><plane><normal>0 0 1</normal><size>20 20</size></plane></geometry></collision><visual name='visual'><geometry><plane><normal>0 0 1</normal><size>20 20</size></plane></geometry></visual></link></model>
<include><uri>model://sgcf_diff_drive_robot</uri><name>sgcf_robot</name><pose>0 0 0 0 0 0</pose></include>
<include><uri>model://static_cylinder</uri><name>static_01</name><pose>{sx} {sy} 0.35 0 0 0</pose></include>
<include><uri>model://human_placeholder</uri><name>human_01</name><pose>{hx} {hy} 0.85 0 0 0</pose></include>
<include><uri>model://vehicle_placeholder</uri><name>vehicle_01</name><pose>{vx} {vy} 0.2 0 0 0</pose></include>
</world></sdf>
"""

def row(seed: int, group: str) -> dict:
    rng = random.Random(seed)
    obstacles = [
        {"name": "static_01", "class_name": "STATIC_OBSTACLE", "center": [3.10, 0.55 + rng.uniform(-0.12, 0.12)]},
        {"name": "human_01", "class_name": "HUMAN", "center": [1.45, 0.30 + rng.uniform(-0.12, 0.12)]},
        {"name": "vehicle_01", "class_name": "VEHICLE", "center": [2.30, -0.50 + rng.uniform(-0.12, 0.12)]},
    ]
    name = f"stage15_mixed_{group}_{seed}"
    values = {"name": name, "sx": obstacles[0]["center"][0], "sy": obstacles[0]["center"][1],
              "hx": obstacles[1]["center"][0], "hy": obstacles[1]["center"][1],
              "vx": obstacles[2]["center"][0], "vy": obstacles[2]["center"][1]}
    path = OUT / f"{name}.sdf"
    path.write_text(TEMPLATE.format(**values))
    return {"seed": seed, "group": group, "scene_id": name, "world": str(path.relative_to(ROOT)),
            "base_contract": "human_path_side", "start": [0.0, 0.0, 0.0], "goal": [4.0, 0.0, 0.0],
            "reference": "avoid", "obstacles": obstacles}

def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rows = [row(seed, "fixed") for seed in FIXED] + [row(seed, "random") for seed in RANDOM]
    MANIFEST.write_text(json.dumps({"semantic_source": "ORACLE_GROUND_TRUTH", "scope": "SIMULATION_ONLY",
                                    "not_stage10_prediction": True, "fixed_seeds": list(FIXED),
                                    "random_seeds": list(RANDOM), "scenarios": rows}, indent=2, sort_keys=True) + "\n")

if __name__ == "__main__": main()
