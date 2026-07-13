#!/usr/bin/env python3
"""Compare parsed SDF primitives against the frozen Stage 02/05 contracts."""

from __future__ import annotations

import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET

import numpy as np
import yaml
from shapely.affinity import rotate, translate
from shapely.geometry import Point, box


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT.parent
OUT = PROJECT / "artifacts/stages/stage_11a_gazebo_preparation"


def world_includes(path: Path) -> dict[str, dict[str, object]]:
    result: dict[str, dict[str, object]] = {}
    for include in ET.parse(path).findall(".//include"):
        pose = [float(value) for value in (include.findtext("pose") or "0 0 0 0 0 0").split()]
        scale = [float(value) for value in (include.findtext("scale") or "1 1 1").split()]
        result[str(include.findtext("name"))] = {
            "model": str(include.findtext("uri")).removeprefix("model://"),
            "pose": pose,
            "scale": scale,
        }
    return result


def parsed_dimensions(model: str, scale: list[float]) -> dict[str, object]:
    tree = ET.parse(ROOT / "models" / model / "model.sdf")
    cylinder = tree.find(".//collision/geometry/cylinder")
    if cylinder is not None:
        return {"shape": "cylinder", "radius": float(cylinder.findtext("radius")) * scale[0]}
    size = [float(value) for value in tree.findtext(".//collision/geometry/box/size").split()]
    return {"shape": "box", "size_xy": [size[0] * scale[0], size[1] * scale[1]]}


def primitive(shape: str, pose: list[float], dimensions: dict[str, object], circle_resolution: int):
    if shape == "cylinder":
        geometry = Point(0.0, 0.0).buffer(float(dimensions["radius"]), resolution=circle_resolution)
    else:
        sx, sy = dimensions["size_xy"]
        geometry = box(-sx / 2.0, -sy / 2.0, sx / 2.0, sy / 2.0)
    geometry = rotate(geometry, math.degrees(pose[2]), origin=(0.0, 0.0))
    return translate(geometry, pose[0], pose[1])


def main() -> None:
    config = yaml.safe_load((ROOT / "config/scenarios.yaml").read_text())
    footprint = box(-0.4, -0.25, 0.4, 0.25)
    pose_errors: list[float] = []
    size_errors: list[float] = []
    clearance_errors: list[float] = []
    point_errors: list[float] = []
    collision_matches: list[bool] = []
    records: list[dict[str, object]] = []

    for scene in config["scenarios"]:
        parsed = world_includes(ROOT / scene["world"])
        for expected in scene["obstacles"]:
            actual = parsed[expected["name"]]
            actual_pose = [actual["pose"][0], actual["pose"][1], actual["pose"][5]]
            expected_pose = expected["pose"]
            pose_error = max(abs(a - b) for a, b in zip(actual_pose, expected_pose))
            dimensions = parsed_dimensions(str(actual["model"]), actual["scale"])
            if expected["shape"] == "cylinder":
                size_error = abs(float(dimensions["radius"]) - float(expected["radius"]))
            else:
                size_error = max(abs(a - b) for a, b in zip(dimensions["size_xy"], expected["size_xy"]))

            # SDF cylinders are analytic; Stage 02 uses Shapely resolution=32.
            gazebo_geometry = primitive(expected["shape"], actual_pose, dimensions, 512)
            expected_dimensions = (
                {"radius": expected["radius"]}
                if expected["shape"] == "cylinder"
                else {"size_xy": expected["size_xy"]}
            )
            stage02_geometry = primitive(expected["shape"], expected_pose, expected_dimensions, 32)
            local_clearance_errors: list[float] = []
            local_collision_matches: list[bool] = []
            for dx in (-1.0, -0.7, -0.4, 0.0, 0.4, 0.7, 1.0):
                for dy in (-0.2, 0.0, 0.2):
                    for yaw in (0.0, 0.3):
                        query = rotate(footprint, math.degrees(yaw), origin=(0.0, 0.0))
                        query = translate(query, expected_pose[0] + dx, expected_pose[1] + dy)
                        first = query.distance(gazebo_geometry)
                        second = query.distance(stage02_geometry)
                        local_clearance_errors.append(abs(first - second))
                        local_collision_matches.append(query.intersects(gazebo_geometry) == query.intersects(stage02_geometry))

            if expected["shape"] == "cylinder":
                for angle in np.linspace(0.0, 2.0 * math.pi, 17)[:-1]:
                    expected_point = np.array(expected_pose[:2]) + expected["radius"] * np.array([math.cos(angle), math.sin(angle)])
                    actual_point = np.array(actual_pose[:2]) + dimensions["radius"] * np.array([math.cos(angle), math.sin(angle)])
                    point_errors.append(float(np.linalg.norm(actual_point - expected_point)))
            else:
                point_errors.append(pose_error + size_error)

            pose_errors.append(pose_error)
            size_errors.append(size_error)
            clearance_errors.extend(local_clearance_errors)
            collision_matches.extend(local_collision_matches)
            records.append({
                "scene_id": scene["scene_id"],
                "obstacle": expected["name"],
                "pose_error_m_rad": pose_error,
                "size_error_m": size_error,
                "clearance_max_error_m": max(local_clearance_errors),
                "collision_agreement": sum(local_collision_matches) / len(local_collision_matches),
            })

    max_clearance_error = max(clearance_errors, default=0.0)
    tolerance = 5e-4
    result = {
        "schema_version": 2,
        "comparison_source": "parsed SDF poses/scales/model collision primitives versus frozen scenario and Stage 02/05 definitions",
        "scenario_count": len(config["scenarios"]),
        "obstacle_count": len(records),
        "generated_asset_pose_max_error_m_rad": max(pose_errors, default=0.0),
        "generated_asset_size_max_error_m": max(size_errors, default=0.0),
        "observable_point_position_max_error_m": max(point_errors, default=0.0),
        "exact_clearance_comparison_max_error_m": max_clearance_error,
        "clearance_tolerance_m": tolerance,
        "circle_discretization": {
            "gazebo_contract_resolution": 512,
            "stage02_shapely_resolution": 32,
            "interpretation": "nonzero cylinder clearance error is the measured analytic-SDF versus frozen Stage 02 polygon approximation",
        },
        "collision_classification_agreement": sum(collision_matches) / len(collision_matches),
        "records": records,
        "world_geometry_online_use": False,
        "passed": (
            max(pose_errors, default=0.0) <= 1e-12
            and max(size_errors, default=0.0) <= 1e-12
            and max(point_errors, default=0.0) <= 1e-12
            and max_clearance_error <= tolerance
            and all(collision_matches)
        ),
    }
    (OUT / "gazebo_geometry_consistency.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({key: result[key] for key in ("obstacle_count", "exact_clearance_comparison_max_error_m", "collision_classification_agreement", "passed")}))


if __name__ == "__main__":
    main()
