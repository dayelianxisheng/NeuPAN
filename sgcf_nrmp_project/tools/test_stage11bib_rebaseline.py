#!/usr/bin/env python3
"""Acceptance tests for the immutable Stage 11B-I-B runtime re-baseline."""

from __future__ import annotations

import json
import unittest
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[1]
OUT = PROJECT / "artifacts/stages/stage_11b_i_b_runtime_rebaseline"


def load(name: str):
    return json.loads((OUT / name).read_text())


class Stage11BIBTest(unittest.TestCase):
    def test_immutable_image_and_new_container_binding(self) -> None:
        image = load("stage11bib_image_resolution.json")
        container = load("stage11bib_container_binding.json")
        self.assertFalse(image["historical_image_available"])
        self.assertEqual(image["current_tag_image_id"], image["selected_immutable_image_id"])
        self.assertTrue(image["tag_prefix_match"])
        self.assertEqual(container["container_image_id"], image["selected_immutable_image_id"])
        self.assertTrue(container["image_id_match"])
        self.assertFalse(container["created_using_mutable_tag"])
        self.assertFalse(container["old_container_used_as_runtime_baseline"])

    def test_environment_equivalence(self) -> None:
        env = load("stage11bib_environment_equivalence.json")
        self.assertEqual(env["gazebo_sim"], "8.14.0")
        self.assertEqual(env["sdformat"], "14.9.0")
        self.assertEqual(env["gz_rendering_abi"], 8)
        self.assertEqual(env["ldd_not_found_count"], 0)
        self.assertTrue(env["hlms_unlit_glsl_present"])
        self.assertTrue(env["hlms_pbs_glsl_present"])
        self.assertTrue(env["gpu_rays_compositor_present"])
        self.assertTrue(env["egl_opengl_context_established"])

    def test_self_return_reproduced(self) -> None:
        baseline = load("stage11bib_baseline_self_return.json")
        expected = [43, 44, 45, 46, 47, 133, 134, 135, 136, 137]
        self.assertTrue(baseline["all_20_frames_reproduced"])
        self.assertLessEqual(baseline["nearest_wheel_inner_surface_error_m"], 0.01)
        self.assertEqual(baseline["lidar_message_count"], 20)
        self.assertEqual(baseline["camera_message_count"], 5)
        self.assertEqual(baseline["odometry_message_count"], 20)
        for record in baseline["records"]:
            self.assertEqual(record["inside_footprint_beam_indices"], expected)

    def test_visibility_replay_uses_exact_i_a_contract(self) -> None:
        probe = load("stage11bib_visibility_probe_replay.json")
        self.assertEqual(probe["robot_self_visibility_bit"], 2)
        self.assertEqual(probe["robot_visual_visibility_flags"], 2)
        self.assertEqual(probe["lidar_visibility_mask"], 4294967293)
        self.assertTrue(probe["values_match_stage11bia"])
        self.assertTrue(probe["all_20_frames_zero_finite_returns"])
        self.assertEqual(probe["camera_dimensions"], [320, 240])
        self.assertTrue(probe["camera_nonempty"])
        self.assertTrue(probe["odometry_finite"])
        for key in ["collision_modified", "visual_geometry_or_pose_modified", "lidar_pose_or_range_modified", "camera_modified", "world_modified", "diff_drive_modified"]:
            self.assertFalse(probe[key])

    def test_two_launches_cleanup_and_frozen_assets(self) -> None:
        cleanup = load("stage11bib_process_cleanup.json")
        frozen = load("stage11bib_frozen_asset_audit.json")
        self.assertTrue(cleanup["passed"])
        self.assertEqual(cleanup["container_residual_gazebo_processes"], 0)
        self.assertEqual(cleanup["host_residual_gazebo_processes"], 0)
        self.assertTrue(cleanup["stage_container_stopped"])
        self.assertEqual(frozen["gazebo_launch_count"], 2)
        self.assertEqual(frozen["worlds_run"], ["empty_world", "empty_world temporary visibility probe"])
        self.assertTrue(frozen["entry_exit_equal"])
        self.assertEqual(frozen["entry"]["collision_xml_sha256"], frozen["exit"]["collision_xml_sha256"])
        for key in ["gazebo_modified", "docker_modified_by_stage11bib", "core_modified", "planner_started", "stage10_loaded", "ros_bridge_started"]:
            self.assertFalse(frozen[key])


if __name__ == "__main__":
    unittest.main()
