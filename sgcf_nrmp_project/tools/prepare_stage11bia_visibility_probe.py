#!/usr/bin/env python3
"""Create the Stage 11B-I-A visibility-only Gazebo probe under /tmp."""

from __future__ import annotations

import argparse
import json
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path


ROBOT_VISIBILITY_BIT = 2
LIDAR_MASK_WITHOUT_ROBOT_BIT = 0xFFFFFFFF ^ ROBOT_VISIBILITY_BIT


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source_gazebo", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()

    destination = args.destination.resolve()
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(args.source_gazebo.resolve(), destination / "gazebo")

    model_path = destination / "gazebo/models/sgcf_diff_drive_robot/model.sdf"
    root = ET.parse(model_path).getroot()
    model = root.find("model")
    if model is None:
        raise RuntimeError("robot model element missing")

    visuals = list(model.findall("./link/visual"))
    for visual in visuals:
        flags = visual.find("visibility_flags")
        if flags is None:
            flags = ET.SubElement(visual, "visibility_flags")
        flags.text = str(ROBOT_VISIBILITY_BIT)

    lidar = model.find("./link/sensor[@type='gpu_lidar']/lidar")
    if lidar is None:
        raise RuntimeError("gpu_lidar configuration missing")
    mask = lidar.find("visibility_mask")
    if mask is None:
        mask = ET.SubElement(lidar, "visibility_mask")
    mask.text = str(LIDAR_MASK_WITHOUT_ROBOT_BIT)
    ET.ElementTree(root).write(model_path, encoding="unicode", xml_declaration=True)

    manifest = {
        "scope": "TEMPORARY_VISIBILITY_ONLY_PROBE",
        "robot_visual_count": len(visuals),
        "robot_visual_visibility_flags": ROBOT_VISIBILITY_BIT,
        "lidar_visibility_mask": LIDAR_MASK_WITHOUT_ROBOT_BIT,
        "collision_modified": False,
        "sensor_pose_modified": False,
        "camera_modified": False,
        "world_modified": False,
    }
    (destination / "probe_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
