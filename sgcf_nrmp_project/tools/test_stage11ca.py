"""Acceptance tests for the Stage 11C-A bridge data-plane Gate."""

import json
import unittest
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[1]
OUT = PROJECT / "artifacts/stages/stage_11c_a_ros2_bridge_data_plane"


def load(name: str):
    return json.loads((OUT / name).read_text(encoding="utf-8"))


class Stage11CAAcceptanceTest(unittest.TestCase):
    def test_bridge_capabilities(self):
        data = load("stage11ca_bridge_capability_audit.json")
        self.assertEqual(data["installed_ros_package"], "ros_gz_bridge")
        self.assertEqual(data["installed_executable"], "parameter_bridge")
        self.assertEqual(data["registered_mapping_count"], 6)
        self.assertTrue(data["all_expected_mappings_registered"])
        self.assertTrue(all(x["observed"] for x in data["topic_records"].values()))

    def test_sensor_data_plane(self):
        data = load("stage11ca_runtime_metrics.json")
        self.assertTrue(data["clock_received"])
        self.assertTrue(data["lidar_received"])
        self.assertTrue(data["lidar_ranges_present"])
        self.assertTrue(data["camera_received"])
        self.assertTrue(data["camera_info_received"])
        self.assertTrue(data["odometry_received"])
        self.assertTrue(data["all_message_count_thresholds_passed"])
        self.assertGreaterEqual(data["message_counts"]["clock"], 50)
        self.assertGreaterEqual(data["message_counts"]["scan"], 20)
        self.assertGreaterEqual(data["message_counts"]["image"], 5)
        self.assertGreaterEqual(data["message_counts"]["camera_info"], 1)
        self.assertGreaterEqual(data["message_counts"]["odometry"], 20)
        self.assertEqual((data["camera_width"], data["camera_height"]), (320, 240))
        self.assertEqual(data["camera_encoding"], "rgb8")
        self.assertEqual(data["odometry_frame_id"], "odom")
        self.assertEqual(data["odometry_child_frame_id"], "base_link")
        self.assertEqual(data["gazebo_runtime_error_count"], 0)

    def test_zero_twist_only(self):
        data = load("stage11ca_zero_twist_gate.json")
        self.assertTrue(data["only_zero_twist_sent"])
        self.assertTrue(data["robot_remained_stationary"])
        self.assertEqual(data["translation_delta_m"], 0.0)
        self.assertEqual(data["yaw_delta_rad"], 0.0)

    def test_information_boundary(self):
        data = load("stage11ca_information_boundary.json")
        self.assertTrue(data["empty_world_only"])
        self.assertFalse(data["planner_started"])
        self.assertFalse(data["stage10_loaded"])
        self.assertFalse(data["pointpainting_executed"])
        self.assertFalse(data["semantic_margin_executed"])
        self.assertFalse(data["nav2_started"])
        self.assertFalse(data["rviz_started"])
        self.assertFalse(data["nonzero_command_sent"])

    def test_cleanup(self):
        data = load("stage11ca_process_cleanup.json")
        self.assertTrue(data["gazebo_container_removed"])
        self.assertTrue(data["bridge_container_removed"])
        self.assertEqual(data["residual_stage_container_count"], 0)

    def test_environment_disclosure(self):
        data = load("stage11ca_environment_audit.json")
        self.assertEqual(data["gazebo_version"], "8.14.0")
        self.assertEqual(data["sdformat_version"], "14.9.0")
        self.assertTrue(data["ogre2_hlms_functional_preflight"])
        self.assertFalse(data["stage11bn_image_object_available"])

    def test_all_json_parse(self):
        for path in OUT.glob("*.json"):
            with self.subTest(path=path):
                json.loads(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
