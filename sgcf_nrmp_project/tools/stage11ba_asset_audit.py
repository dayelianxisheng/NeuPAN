#!/usr/bin/env python3
"""Audit Stage 11B-A Gazebo assets without starting Gazebo."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
GAZEBO = ROOT / "gazebo"
OUT = ROOT / "artifacts/stages/stage_11b_a_runtime_asset_activation"
ROBOT = GAZEBO / "models/sgcf_diff_drive_robot/model.sdf"


def _pose(element: ET.Element | None) -> str | None:
    return None if element is None else (element.findtext("pose") or "0 0 0 0 0 0")


def _obstacle_signature() -> dict[str, list[dict[str, str | None]]]:
    result: dict[str, list[dict[str, str | None]]] = {}
    for path in sorted((GAZEBO / "worlds").glob("*.sdf")):
        world = ET.parse(path).getroot().find("world")
        assert world is not None
        items = []
        for include in world.findall("include"):
            uri = include.findtext("uri")
            if uri == "model://sgcf_diff_drive_robot":
                continue
            items.append({
                "name": include.findtext("name"),
                "uri": uri,
                "pose": include.findtext("pose"),
                "scale": include.findtext("scale") or "1 1 1",
            })
        result[path.stem] = items
    return result


def audit() -> dict:
    tree = ET.parse(ROBOT)
    model = tree.getroot().find("model")
    assert model is not None
    links = {item.get("name"): item for item in model.findall("link")}
    joints = {item.get("name"): item for item in model.findall("joint")}
    plugins = model.findall("plugin")
    lidar = model.find(".//sensor[@name='lidar']")
    camera = model.find(".//sensor[@name='rgb_camera']")
    base_collision = model.find(".//collision[@name='planner_footprint_collision']")
    signature = _obstacle_signature()
    canonical = json.dumps(signature, sort_keys=True, separators=(",", ":"))
    worlds = []
    for path in sorted((GAZEBO / "worlds").glob("*.sdf")):
        world = ET.parse(path).getroot().find("world")
        assert world is not None
        system_plugins = [
            {"filename": p.get("filename"), "name": p.get("name")}
            for p in world.findall("plugin")
        ]
        worlds.append({"scene_id": path.stem, "plugins": system_plugins})
    def link_item(name: str) -> dict:
        link = links.get(name)
        return {
            "exists": link is not None,
            "name": name,
            "pose": _pose(link),
            "parent": None,
            "geometry": None,
            "collision_extent": None,
        }
    def joint_item(name: str) -> dict:
        joint = joints.get(name)
        return {
            "exists": joint is not None,
            "name": name,
            "parent": None if joint is None else joint.findtext("parent"),
            "child": None if joint is None else joint.findtext("child"),
            "type": None if joint is None else joint.get("type"),
            "axis": None if joint is None else joint.findtext("axis/xyz"),
        }
    return {
        "robot_model": str(ROBOT.relative_to(ROOT)),
        "base_link": link_item("base_link"),
        "base_collision": {
            "exists": base_collision is not None,
            "name": None if base_collision is None else base_collision.get("name"),
            "pose": _pose(base_collision),
            "geometry": None if base_collision is None else base_collision.findtext("geometry/box/size"),
        },
        "lidar": {
            "exists": lidar is not None,
            "name": None if lidar is None else lidar.get("name"),
            "parent": "lidar_link" if lidar is not None else None,
            "pose": _pose(links.get("lidar_link")),
            "topic": None if lidar is None else lidar.findtext("topic"),
            "type": None if lidar is None else lidar.get("type"),
        },
        "camera": {
            "exists": camera is not None,
            "name": None if camera is None else camera.get("name"),
            "parent": "camera_link" if camera is not None else None,
            "pose": _pose(links.get("camera_link")),
            "topic": None if camera is None else camera.findtext("topic"),
            "type": None if camera is None else camera.get("type"),
        },
        "left_wheel_link": link_item("left_wheel_link"),
        "right_wheel_link": link_item("right_wheel_link"),
        "left_wheel_joint": joint_item("left_wheel_joint"),
        "right_wheel_joint": joint_item("right_wheel_joint"),
        "diff_drive_plugins": [
            {"filename": p.get("filename"), "name": p.get("name")}
            for p in plugins if p.get("name") == "gz::sim::systems::DiffDrive"
        ],
        "worlds": worlds,
        "obstacle_signature": signature,
        "obstacle_signature_sha256": hashlib.sha256(canonical.encode()).hexdigest(),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    target = OUT / args.output
    target.write_text(json.dumps(audit(), indent=2, allow_nan=False) + "\n")
    print(target)


if __name__ == "__main__":
    main()
