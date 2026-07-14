#!/usr/bin/env python3
"""Static acceptance checks for Stage 11B-I-A."""

from __future__ import annotations

import json
import unittest
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[1]
OUT = PROJECT / "artifacts/stages/stage_11b_i_a_self_return_diagnosis"


def load(name: str):
    return json.loads((OUT / name).read_text())


class Stage11BIADiagnosisTest(unittest.TestCase):
    def test_environment_and_rendering_gate(self) -> None:
        audit = load("stage11bia_environment_equivalence.json")
        self.assertEqual(audit["gazebo_sim"], "8.14.0")
        self.assertEqual(audit["sdformat"], "14.9.0")
        self.assertEqual(audit["gz_rendering_abi"], 8)
        self.assertTrue(audit["hlms_ogre2_gate_passed"])

    def test_geometry_is_fully_enumerated_and_intersects_plane(self) -> None:
        geometry = load("stage11bia_robot_geometry_audit.json")
        plane = load("stage11bia_lidar_plane_intersection.json")
        self.assertTrue(geometry["geometry_enumeration_complete"])
        self.assertEqual(len(geometry["visuals"]), 3)
        self.assertEqual(len(geometry["collisions"]), 3)
        self.assertEqual(plane["scan_plane_z_m"], 0.2)
        self.assertIn("right_wheel_visual", plane["intersecting_visuals"])

    def test_formal_signature_is_reproducible(self) -> None:
        metrics = load("stage11bia_empty_world_self_return_metrics.json")
        self.assertEqual(metrics["lidar_messages"], 20)
        self.assertEqual(metrics["camera_messages"], 5)
        self.assertEqual(metrics["odometry_messages"], 20)
        self.assertTrue(metrics["inside_point_cloud_stable"])
        for record in metrics["records"]:
            self.assertEqual(record["inside_footprint_beam_indices"], [43, 44, 45, 46, 47, 133, 134, 135, 136, 137])

    def test_visibility_probe_changes_only_visibility_contract(self) -> None:
        probe = load("stage11bia_visibility_probe.json")
        self.assertTrue(probe["formal_assets_modified"] is False)
        self.assertFalse(probe["collision_modified"])
        self.assertFalse(probe["sensor_pose_modified"])
        self.assertFalse(probe["camera_modified"])
        self.assertFalse(probe["external_world_modified"])
        self.assertEqual(probe["probe_finite_lidar_return_count"], 0)
        self.assertEqual(probe["lidar_messages"], 20)
        self.assertEqual(probe["camera_messages"], 5)
        self.assertEqual(probe["odometry_messages"], 20)

    def test_visibility_schema_and_attribution(self) -> None:
        feature = load("stage11bia_visibility_feature_audit.json")
        attribution = load("stage11bia_self_return_attribution.json")
        self.assertTrue(feature["visibility_flags_schema_supported"])
        self.assertTrue(feature["visibility_mask_schema_supported"])
        self.assertEqual(attribution["status"], "SELF_RETURN_ATTRIBUTED_TO_ROBOT_VISUAL")
        self.assertEqual(attribution["candidates_ranked"][0]["candidate_visual"], "right_wheel_visual")

    def test_frozen_boundaries_and_cleanup(self) -> None:
        frozen = load("stage11bia_frozen_component_audit.json")
        cleanup = load("stage11bia_process_cleanup.json")
        self.assertEqual(frozen["gazebo_launch_count"], 2)
        self.assertEqual(frozen["worlds_run"], ["empty_world", "empty_world temporary visibility copy"])
        for key in ["formal_gazebo_modified", "docker_modified_by_stage11bia", "core_modified_by_stage11bia", "adapter_point_crop_added", "minimum_range_modified", "planner_started", "stage10_loaded", "ros_bridge_started"]:
            self.assertFalse(frozen[key])
        self.assertTrue(cleanup["passed"])
        self.assertEqual(cleanup["residual_gazebo_process_count"], 0)


if __name__ == "__main__":
    unittest.main()
