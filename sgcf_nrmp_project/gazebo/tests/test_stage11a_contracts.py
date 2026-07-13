"""Static Stage 11A Gazebo asset and adapter contract tests."""

from __future__ import annotations

import json
import inspect
import math
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET

import numpy as np
import yaml

from sgcf_gazebo.adapters import (
    GazeboCameraAdapter,
    GazeboLidarAdapter,
    GazeboOracleSemanticAdapter,
    r1_semantic_enabled,
    safe_command_for_status,
)
from sgcf_gazebo.contracts import (
    GazeboCameraInfo,
    GazeboImageFrame,
    GazeboOracleSemanticFrame,
    GazeboScanFrame,
    GazeboTransformSnapshot,
    PlannerOutputFrame,
)


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT.parent
ARTIFACTS = PROJECT / "artifacts/stages/stage_11a_gazebo_preparation"


class Stage11AContractTests(unittest.TestCase):
    def test_all_xml_parses_and_references_exist(self) -> None:
        paths = list(ROOT.glob("worlds/*.sdf")) + list(ROOT.glob("models/*/model.*"))
        self.assertGreaterEqual(len(paths), 22)
        for path in paths:
            ET.parse(path)
        for world in ROOT.glob("worlds/*.sdf"):
            tree = ET.parse(world)
            names = [node.get("name") for node in tree.findall(".//model")]
            for include in tree.findall(".//include"):
                names.append(include.findtext("name"))
                uri = include.findtext("uri").removeprefix("model://")
                self.assertTrue((ROOT / "models" / uri / "model.sdf").exists())
            self.assertEqual(len(names), len(set(names)))

    def test_scenario_and_semantic_contract(self) -> None:
        config = yaml.safe_load((ROOT / "config/scenarios.yaml").read_text())
        scene_ids = [item["scene_id"] for item in config["scenarios"]]
        self.assertEqual(len(scene_ids), 12)
        self.assertEqual(len(scene_ids), len(set(scene_ids)))
        classes = yaml.safe_load((ROOT / "config/semantic_classes.yaml").read_text())
        self.assertEqual(classes, {
            "UNKNOWN": 0, "STATIC_OBSTACLE": 1, "HUMAN": 2,
            "VEHICLE": 3, "ROBOT": 4,
        })
        for scene in config["scenarios"]:
            for obstacle in scene["obstacles"]:
                self.assertIn(obstacle["semantic_class"], classes)

    def test_frame_tree_is_acyclic(self) -> None:
        manifest = json.loads((ARTIFACTS / "frame_transform_manifest.json").read_text())
        graph: dict[str, list[str]] = {}
        for transform in manifest["transforms"]:
            graph.setdefault(transform["target"], []).append(transform["source"])
        visited: set[str] = set()
        active: set[str] = set()

        def visit(node: str) -> None:
            self.assertNotIn(node, active)
            if node in visited:
                return
            active.add(node)
            for child in graph.get(node, []):
                visit(child)
            active.remove(node)
            visited.add(node)

        for frame in graph:
            visit(frame)
        self.assertIn("camera_optical_frame", visited)

    def test_lidar_order_conversion_and_invalid_ranges(self) -> None:
        scan = GazeboScanFrame(
            1.0, "lidar_link", 7, True, "GAZEBO", np.array([1.0, 8.0, np.nan, 0.1]),
            -math.pi / 2.0, math.pi / 2.0, 0.05, 8.0,
        )
        transform = GazeboTransformSnapshot(
            1.0, "base_link", 7, True, "STATIC_TF", "base_link", "lidar_link", np.eye(4),
        )
        result = GazeboLidarAdapter().scan_to_observable_points(scan, transform)
        np.testing.assert_array_equal(result.point_valid_mask, [True, False, False, True])
        np.testing.assert_allclose(result.points_xy[0], [0.0, -1.0], atol=1e-12)
        np.testing.assert_allclose(result.points_xy[3], [-0.1, 0.0], atol=1e-12)
        np.testing.assert_allclose(result.points_xy[1:3], 0.0)
        np.testing.assert_allclose(result.ranges[[0, 1, 3]], [1.0, 8.0, 0.1])
        self.assertTrue(math.isnan(result.ranges[2]))
        self.assertEqual(len(result.points_xy), len(scan.ranges))

    def test_camera_matches_stage07(self) -> None:
        rgb = np.zeros((240, 320, 3), dtype=np.uint8)
        image = GazeboImageFrame(1.0, "camera_optical_frame", 4, True, "GAZEBO", rgb)
        info = GazeboCameraInfo(
            1.0, "camera_optical_frame", 4, True, "GAZEBO", 320, 240,
            180.0, 180.0, 160.0, 120.0,
        )
        matrix = np.array([
            [0.0, -1.0, 0.0, 0.0], [0.0, 0.0, -1.0, 0.8],
            [1.0, 0.0, 0.0, 0.0], [0.0, 0.0, 0.0, 1.0],
        ])
        transform = GazeboTransformSnapshot(
            1.0, "camera_optical_frame", 4, True, "STATIC_TF",
            "camera_optical_frame", "lidar_link", matrix,
        )
        result = GazeboCameraAdapter().image_to_stage07_input(image, info, transform)
        self.assertEqual(result["intrinsics"]["width"], 320)
        np.testing.assert_array_equal(result["T_camera_lidar"], matrix)

    def test_footprint_matches_stage05(self) -> None:
        contract = json.loads((ARTIFACTS / "robot_geometry_contract.json").read_text())
        self.assertEqual(contract["gazebo_collision_box_length_m"], 0.8)
        self.assertEqual(contract["gazebo_collision_box_width_m"], 0.5)
        self.assertTrue(contract["passed"])

    def test_oracle_sidecar_preserves_geometry_and_unknown_is_zero_margin(self) -> None:
        self.assertNotIn("world", inspect.signature(GazeboLidarAdapter.scan_to_observable_points).parameters)
        scan = GazeboScanFrame(
            1.0, "lidar_link", 3, True, "GAZEBO", np.array([1.0, 2.0]),
            0.0, math.pi / 2.0, 0.05, 8.0,
        )
        transform = GazeboTransformSnapshot(
            1.0, "base_link", 3, True, "STATIC_TF", "base_link", "lidar_link", np.eye(4),
        )
        geometric = GazeboLidarAdapter().scan_to_observable_points(scan, transform)
        semantic = GazeboOracleSemanticFrame(
            1.0, "camera_optical_frame", 3, True, "GAZEBO_ORACLE", np.array([0, 2]),
        )
        painted = GazeboOracleSemanticAdapter().semantic_input_for_stage07(geometric, semantic)
        np.testing.assert_array_equal(painted.points_xy, geometric.points_xy)
        np.testing.assert_array_equal(painted.point_valid_mask, geometric.point_valid_mask)
        np.testing.assert_array_equal(painted.ranges, geometric.ranges)
        self.assertEqual(int(painted.semantic_class_ids[0]), 0)
        class_margin = json.loads((ARTIFACTS / "gazebo_semantic_class_mapping.json").read_text())
        self.assertEqual(class_margin["semantic_margin_m"]["UNKNOWN"], 0.0)

    def test_r1_and_command_safety_contracts(self) -> None:
        self.assertFalse(r1_semantic_enabled(
            image_present=False, image_age_s=0.0, projection_valid=True, unknown=False,
        ))
        self.assertFalse(r1_semantic_enabled(
            image_present=True, image_age_s=0.101, projection_valid=True, unknown=False,
        ))
        output = PlannerOutputFrame(
            1.0, "base_link", 1, True, "PLANNER", 0.5, 0.2,
            "REJECTED_BY_GEOMETRY_CHECK",
        )
        self.assertEqual(safe_command_for_status(output, 1.01)[:2], (0.0, 0.0))
        stale = PlannerOutputFrame(1.0, "base_link", 1, True, "PLANNER", 0.5, 0.2, "SUCCESS")
        self.assertEqual(safe_command_for_status(stale, 1.21)[:2], (0.0, 0.0))
        unknown = PlannerOutputFrame(1.0, "base_link", 1, True, "PLANNER", 0.5, 0.2, "UNRECOGNIZED")
        self.assertEqual(safe_command_for_status(unknown, 1.01)[:2], (0.0, 0.0))

    def test_human_path_side_frozen(self) -> None:
        config = yaml.safe_load((ROOT / "config/scenarios.yaml").read_text())
        scene = next(item for item in config["scenarios"] if item["scene_id"] == "human_path_side")
        self.assertEqual(scene["start_pose"], [0.0, 0.0, 0.7994817392203084])
        self.assertEqual(scene["obstacles"][0]["pose"], [1.5, 0.35, 0.0])
        self.assertEqual(scene["obstacles"][0]["radius"], 0.35)
        self.assertEqual(scene["contract"], "stage09b_known_limitation")

    def test_manifest_is_reproducible_and_json_parses(self) -> None:
        manifest = json.loads((ARTIFACTS / "gazebo_scenario_manifest.json").read_text())
        self.assertEqual(manifest["seed"], 909)
        self.assertEqual(len(manifest["scenarios"]), 12)
        for path in ARTIFACTS.glob("*.json"):
            json.loads(path.read_text())


if __name__ == "__main__":
    unittest.main()
