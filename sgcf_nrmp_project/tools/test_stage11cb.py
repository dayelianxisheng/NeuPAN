#!/usr/bin/env python3
"""Artifact and source-boundary tests for Stage 11C-B."""

from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PROJECT = ROOT / "sgcf_nrmp_project"
OUT = PROJECT / "artifacts/stages/stage_11c_b_open_loop_command"
NODE = PROJECT / "ros2_ws/src/sgcf_nrmp_bridge/sgcf_nrmp_bridge/stage11cb_open_loop_audit.py"


def data(name: str) -> dict:
    return json.loads((OUT / name).read_text())


class Stage11CBTests(unittest.TestCase):
    def test_image_binding(self):
        value = data("stage11cb_runtime_image_binding.json")
        self.assertTrue(value["immutable_ids_used_for_runtime"])
        self.assertTrue(value["gazebo_image_id"].startswith("sha256:"))
        self.assertTrue(value["bridge_image_id"].startswith("sha256:"))
        self.assertEqual(value["binding"], "FUNCTIONALLY_EQUIVALENT_RUNTIME_BASELINE")

    def test_profile_and_phase_order(self):
        profile = data("stage11cb_command_profile.json")
        self.assertLessEqual(profile["linear_velocity_mps"], 0.15)
        self.assertLessEqual(profile["angular_velocity_radps"], 0.50)
        result = json.loads((OUT / "logs/open_loop_node_result.json").read_text())
        self.assertEqual(
            result["phase_order"],
            ["ZERO_BASELINE", "POSITIVE_LINEAR", "ZERO_AFTER_LINEAR", "POSITIVE_ANGULAR", "ZERO_AFTER_ANGULAR", "FINAL_STATIONARY", "COMPLETE"],
        )
        self.assertTrue(result["use_sim_time"])

    def test_bridge_direction_and_values(self):
        direction = data("stage11cb_bridge_direction_audit.json")
        self.assertEqual(direction["mappings"]["/cmd_vel"], "ROS_TO_GZ")
        value = data("stage11cb_command_bridge_consistency.json")
        self.assertTrue(value["passed"])
        self.assertEqual(value["maximum_component_error"], 0.0)
        self.assertEqual(value["unauthorized_nonzero_component_count"], 0)

    def test_stationary_and_motion_gates(self):
        self.assertTrue(data("stage11cb_stationary_baseline.json")["passed"])
        linear = data("stage11cb_positive_linear_motion.json")
        self.assertTrue(linear["passed"])
        self.assertGreater(linear["forward_displacement_m"], 0.0)
        self.assertTrue(data("stage11cb_linear_stop_response.json")["passed"])
        angular = data("stage11cb_positive_angular_motion.json")
        self.assertTrue(angular["passed"])
        self.assertGreater(angular["unwrapped_yaw_delta_rad"], 0.0)
        self.assertTrue(data("stage11cb_angular_stop_response.json")["passed"])
        self.assertTrue(data("stage11cb_final_stationary_gate.json")["passed"])

    def test_sensor_and_timestamp_gates(self):
        sensor = data("stage11cb_sensor_data_plane_regression.json")
        self.assertTrue(sensor["passed"])
        self.assertEqual(sensor["camera"]["width_values"], [320])
        self.assertEqual(sensor["camera"]["height_values"], [240])
        self.assertEqual(sensor["camera"]["encoding_values"], ["rgb8"])
        timestamp = data("stage11cb_timestamp_audit.json")
        self.assertTrue(timestamp["passed"])
        self.assertEqual(timestamp["clock"]["negative_jump_count"], 0)

    def test_lidar_and_frames(self):
        lidar = data("stage11cb_lidar_self_visibility_regression.json")
        self.assertEqual(lidar["finite_self_return_count"], 0)
        self.assertFalse(lidar["point_filtering_added"])
        frame = data("stage11cb_runtime_frame_audit.json")
        self.assertTrue(frame["passed"])
        self.assertEqual(frame["odometry_header_frames"], ["odom"])
        self.assertEqual(frame["odometry_child_frames"], ["base_link"])

    def test_graph_and_cleanup(self):
        graph = data("stage11cb_ros_qos_and_graph_audit.json")
        self.assertEqual(graph["cmd_vel_publisher_count"], 1)
        self.assertFalse(graph["cmd_vel_loop"])
        cleanup = data("stage11cb_process_cleanup.json")
        self.assertTrue(cleanup["passed"])
        self.assertEqual(cleanup["residual_stage_container_count"], 0)
        self.assertEqual(cleanup["residual_host_process_count"], 0)

    def test_frozen_components(self):
        value = data("stage11cb_frozen_component_audit.json")
        self.assertTrue(value["passed"])
        self.assertEqual(value["footprint_m"], [0.8, 0.5])
        self.assertEqual(value["protected_component_changes_during_stage11cb"], [])

    def test_node_is_open_loop_only(self):
        source = NODE.read_text()
        self.assertIn('"/clock"', source)
        self.assertNotIn("planner", source.lower())
        self.assertNotIn("pointpainting", source.lower())
        self.assertNotIn("semantic_margin", source.lower())
        self.assertNotIn("nav2", source.lower())
        self.assertNotIn("robot_state_publisher", source.lower())

    def test_all_json_parse(self):
        for path in OUT.glob("*.json"):
            with self.subTest(path=path.name):
                json.loads(path.read_text())


if __name__ == "__main__":
    unittest.main(verbosity=2)
