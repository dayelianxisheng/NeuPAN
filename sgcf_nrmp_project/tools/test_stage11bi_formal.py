#!/usr/bin/env python3
"""Acceptance tests for formal Stage 11B-I visibility isolation."""

from __future__ import annotations

import json
import unittest
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[1]
OUT = PROJECT / "artifacts/stages/stage_11b_i_lidar_self_visibility"


def load(name: str):
    return json.loads((OUT / name).read_text())


class Stage11BIFormalTest(unittest.TestCase):
    def test_immutable_runtime_binding(self) -> None:
        binding = load("stage11bi_runtime_image_binding.json")
        self.assertTrue(binding["image_id_match"])
        self.assertFalse(binding["created_using_mutable_tag"])
        self.assertTrue(binding["immutable_image_id"].startswith("sha256:99de6309"))

    def test_visibility_contract_exactly_matches_probes(self) -> None:
        contract = load("stage11bi_visibility_contract.json")
        self.assertEqual(contract["robot_self_visibility_bit"], 2)
        self.assertEqual(contract["robot_visual_visibility_flags"], 2)
        self.assertEqual(contract["lidar_visibility_mask"], 4294967293)
        self.assertEqual(set(contract["robot_visuals"]), {"body", "left_wheel_visual", "right_wheel_visual"})
        self.assertTrue(all(value == 2 for value in contract["robot_visuals"].values()))
        self.assertTrue(contract["lidar_excludes_self_bit"])
        self.assertTrue(contract["lidar_includes_default_external_flags"])
        self.assertFalse(contract["external_visuals_modified"])

    def test_asset_delta_is_visibility_only(self) -> None:
        delta = load("stage11bi_robot_asset_delta.json")
        collision = load("stage11bi_collision_preservation.json")
        static = load("stage11bi_static_visibility_audit.json")
        self.assertEqual(len(delta["changed_xml_paths"]), 4)
        for key in ["visual_nonvisibility_equal", "lidar_nonvisibility_equal", "collision_equal", "camera_equal", "joint_equal", "diff_drive_equal"]:
            self.assertTrue(delta[key])
        self.assertEqual(collision["difference"], 0)
        self.assertEqual(collision["footprint_m"], [0.8, 0.5])
        self.assertEqual(collision["wheel_radius_m"], 0.1)
        self.assertEqual(collision["wheel_separation_m"], 0.5)
        self.assertTrue(static["lidar_pose_and_nonvisibility_parameters_unchanged"])
        self.assertTrue(static["stage07_relative_extrinsic_unchanged"])
        self.assertEqual(static["runtime_point_crop_scan_matches"], [])

    def test_empty_world_has_no_self_return(self) -> None:
        empty = load("stage11bi_empty_world_self_visibility.json")
        self.assertTrue(empty["all_20_frames_zero_self_return"])
        self.assertEqual(empty["lidar_message_count"], 20)
        for record in empty["scan_records"]:
            self.assertEqual(record["self_return_count"], 0)
            self.assertEqual(record["inside_footprint_count"], 0)
        self.assertFalse(any(empty["historical_self_beams_finite"].values()))

    def test_targeted_geometry_and_external_safety_counterexample(self) -> None:
        geometry = load("stage11bi_targeted_clearance_consistency.json")
        self.assertEqual(geometry["classification_agreement_count"], 3)
        self.assertEqual(geometry["classification_total"], 3)
        self.assertEqual(geometry["classification_agreement_rate"], 1.0)
        self.assertTrue(all(record["absolute_error_m"] <= 0.02 for record in geometry["records"]))
        self.assertTrue(geometry["initial_collision_external_obstacle_visible"])
        self.assertTrue(geometry["initial_collision_external_inside_beam_indices"])
        self.assertFalse(geometry["world_geometry_used_for_runtime_distance"])

    def test_camera_odometry_cleanup_and_boundaries(self) -> None:
        camera = load("stage11bi_camera_regression.json")
        odometry = load("stage11bi_odometry_regression.json")
        cleanup = load("stage11bi_process_cleanup.json")
        frozen = load("stage11bi_frozen_component_audit.json")
        self.assertEqual(camera["scenes_passed"], 4)
        self.assertEqual(odometry["scenes_passed"], 4)
        self.assertTrue(cleanup["stage_container_stopped"])
        self.assertEqual(cleanup["container_residual_gazebo_process_count"], 0)
        self.assertEqual(cleanup["host_residual_gazebo_process_count"], 0)
        self.assertEqual(frozen["executed_scenes"], ["empty_world", "single_static_obstacle", "human_path_side", "initial_collision"])
        self.assertEqual(frozen["other_worlds_run"], [])
        for key in ["docker_modified_by_stage11bi", "core_modified", "adapter_modified", "point_crop_added", "planner_started", "stage10_loaded", "ros_bridge_started"]:
            self.assertFalse(frozen[key])


if __name__ == "__main__":
    unittest.main()
