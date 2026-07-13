"""Stage 11B-A static contract and blocked-runtime evidence tests."""

from __future__ import annotations

import json
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET


GAZEBO = Path(__file__).resolve().parents[1]
PROJECT = GAZEBO.parent
OUT = PROJECT / "artifacts/stages/stage_11b_a_runtime_asset_activation"
CONTRACT = PROJECT / "artifacts/stages/stage_11a_gazebo_preparation"


class Stage11BAActivationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.robot = ET.parse(GAZEBO / "models/sgcf_diff_drive_robot/model.sdf").getroot().find("model")
        assert cls.robot is not None
        cls.geometry = json.loads((CONTRACT / "robot_geometry_contract.json").read_text())
        cls.pre = json.loads((OUT / "stage11ba_prepatch_asset_audit.json").read_text())
        cls.post = json.loads((OUT / "stage11ba_postpatch_asset_audit.json").read_text())

    def test_all_world_system_plugins(self) -> None:
        expected = {
            "gz::sim::systems::Physics": "gz-sim-physics-system",
            "gz::sim::systems::UserCommands": "gz-sim-user-commands-system",
            "gz::sim::systems::SceneBroadcaster": "gz-sim-scene-broadcaster-system",
            "gz::sim::systems::Sensors": "gz-sim-sensors-system",
        }
        worlds = sorted((GAZEBO / "worlds").glob("*.sdf"))
        self.assertEqual(12, len(worlds))
        for path in worlds:
            plugins = ET.parse(path).getroot().find("world").findall("plugin")
            actual = {plugin.get("name"): plugin.get("filename") for plugin in plugins}
            self.assertEqual(expected, actual, path.name)
            sensors = [p for p in plugins if p.get("name") == "gz::sim::systems::Sensors"]
            self.assertEqual(1, len(sensors))
            self.assertEqual("ogre2", sensors[0].findtext("render_engine"))

    def test_sensors_preserve_contract(self) -> None:
        lidar = self.robot.find(".//sensor[@name='lidar']")
        camera = self.robot.find(".//sensor[@name='rgb_camera']")
        self.assertIsNotNone(lidar)
        self.assertIsNotNone(camera)
        assert lidar is not None and camera is not None
        self.assertEqual("gpu_lidar", lidar.get("type"))
        self.assertEqual("true", lidar.findtext("always_on"))
        self.assertEqual("/scan", lidar.findtext("topic"))
        self.assertEqual("181", lidar.findtext("lidar/scan/horizontal/samples"))
        self.assertEqual("10", lidar.findtext("update_rate"))
        self.assertEqual("camera", camera.get("type"))
        self.assertEqual("true", camera.findtext("always_on"))
        self.assertEqual("/camera/image_raw", camera.findtext("topic"))
        self.assertEqual("320", camera.findtext("camera/image/width"))
        self.assertEqual("240", camera.findtext("camera/image/height"))
        self.assertEqual("10", camera.findtext("update_rate"))

    def test_wheel_links_joints_and_plugin(self) -> None:
        links = {item.get("name") for item in self.robot.findall("link")}
        self.assertIn("left_wheel_link", links)
        self.assertIn("right_wheel_link", links)
        for name, child in (("left_wheel_joint", "left_wheel_link"), ("right_wheel_joint", "right_wheel_link")):
            joint = self.robot.find(f"joint[@name='{name}']")
            self.assertIsNotNone(joint)
            assert joint is not None
            self.assertEqual("revolute", joint.get("type"))
            self.assertEqual("base_link", joint.findtext("parent"))
            self.assertEqual(child, joint.findtext("child"))
            self.assertEqual("0 1 0", joint.findtext("axis/xyz"))
        plugins = [p for p in self.robot.findall("plugin") if p.get("name") == "gz::sim::systems::DiffDrive"]
        self.assertEqual(1, len(plugins))
        plugin = plugins[0]
        self.assertEqual("gz-sim-diff-drive-system", plugin.get("filename"))
        self.assertEqual("/cmd_vel", plugin.findtext("topic"))
        self.assertEqual("/odom", plugin.findtext("odom_topic"))
        self.assertEqual("odom", plugin.findtext("frame_id"))
        self.assertEqual("base_link", plugin.findtext("child_frame_id"))
        contract = self.geometry["differential_drive_kinematic_contract"]
        self.assertEqual(contract["wheel_radius_m"], float(plugin.findtext("wheel_radius")))
        self.assertEqual(contract["wheel_separation_m"], float(plugin.findtext("wheel_separation")))

    def test_collision_envelope_and_geometry_hash(self) -> None:
        result = json.loads((OUT / "stage11ba_footprint_runtime_model_audit.json").read_text())
        self.assertTrue(result["base_collision_unchanged_0_8_by_0_5"])
        self.assertLessEqual(result["combined_length_m"], 0.8 + 1e-9)
        self.assertLessEqual(result["combined_width_m"], 0.5 + 1e-9)
        self.assertEqual(self.pre["obstacle_signature_sha256"], self.post["obstacle_signature_sha256"])
        self.assertEqual(self.pre["obstacle_signature"]["human_path_side"], self.post["obstacle_signature"]["human_path_side"])

    def test_inertias_are_finite_positive(self) -> None:
        for name in ("left_wheel_link", "right_wheel_link"):
            link = self.robot.find(f"link[@name='{name}']")
            assert link is not None
            self.assertGreater(float(link.findtext("inertial/mass")), 0)
            for key in ("ixx", "iyy", "izz"):
                value = float(link.findtext(f"inertial/inertia/{key}"))
                self.assertGreater(value, 0)
                self.assertLess(value, float("inf"))

    def test_runtime_failure_is_truthfully_classified(self) -> None:
        runtime = json.loads((OUT / "stage11ba_empty_world_runtime.json").read_text())
        cleanup = json.loads((OUT / "stage11ba_process_cleanup.json").read_text())
        self.assertEqual(1, runtime["attempt_count"])
        self.assertEqual("BLOCKED_SENSOR_SYSTEM_ACTIVATION", runtime["decision"])
        self.assertTrue(runtime["stderr_contains_ogre2_load_failure"])
        self.assertTrue(runtime["stderr_contains_segmentation_fault"])
        self.assertFalse(runtime["second_attempt_performed"])
        self.assertEqual(0, cleanup["residual_gz_processes"])

    def test_json_artifacts_parse(self) -> None:
        for path in OUT.glob("*.json"):
            with self.subTest(path=path.name):
                json.loads(path.read_text())


if __name__ == "__main__":
    unittest.main()
