"""Acceptance tests for Stage 11B-M exact primitive materialization."""

import json
import unittest
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[1]
OUT = PROJECT / "artifacts/stages/stage_11b_m_exact_primitive_materialization"


def load(name: str) -> dict:
    return json.loads((OUT / name).read_text(encoding="utf-8"))


class Stage11BMAcceptanceTest(unittest.TestCase):
    def test_all_scales_migrated(self) -> None:
        data = load("stage11bm_include_scale_inventory.json")
        self.assertEqual(data["historical_invalid_include_scale_count"], 13)
        self.assertEqual(data["unit_scale_count"], 8)
        self.assertEqual(data["nonunit_scale_count"], 5)
        self.assertEqual(data["active_include_scale_count_after"], 0)
        for path in (PROJECT / "gazebo/worlds").glob("*.sdf"):
            self.assertNotIn("<scale>", path.read_text())

    def test_exact_cylinder(self) -> None:
        data = load("stage11bm_cylinder_exactness_audit.json")
        self.assertTrue(data["exact_representability"])
        self.assertTrue(data["scale_x_equals_scale_y"])
        self.assertTrue(data["roll_pitch_zero"])
        self.assertAlmostEqual(data["resolved_radius_m"], .2, places=12)
        self.assertAlmostEqual(data["resolved_length_m"], .4, places=12)

    def test_generator_is_deterministic(self) -> None:
        migration = load("stage11bm_generator_migration.json")
        determinism = load("stage11bm_generation_determinism.json")
        self.assertEqual(migration["active_include_scale_count"], 0)
        self.assertTrue(determinism["deterministic"])
        self.assertTrue(determinism["empty_world_hash_unchanged"])

    def test_sdformat_gate(self) -> None:
        data = load("stage11bm_sdf_schema_validation.json")
        self.assertEqual(data["parse_pass_count"], 12)
        self.assertEqual(data["undefined_include_child_warning_count"], 0)
        self.assertEqual(data["active_include_scale_count"], 0)

    def test_frozen_assets(self) -> None:
        data = load("stage11bm_frozen_component_audit.json")
        self.assertTrue(data["empty_world_unchanged"])
        self.assertTrue(data["robot_model_unchanged"])
        self.assertTrue(data["human_placeholder_unchanged"])
        self.assertTrue(data["all_models_unchanged"])
        self.assertEqual(data["robot_visual_flags"], 2)
        self.assertEqual(data["lidar_visibility_mask"], 4294967293)

    def test_changed_world_runtime_complete(self) -> None:
        data = load("stage11bm_changed_world_runtime_matrix.json")
        self.assertEqual(data["changed_world_count"], 11)
        self.assertEqual(data["runtime_result_count"], 11)
        self.assertTrue(all(x["runtime_complete"] for x in data["records"]))
        self.assertTrue(all(x["segmentation_fault_count"] == 0 for x in data["records"]))

    def test_clearance_and_collision_gate(self) -> None:
        data = load("stage11bm_runtime_clearance_consistency.json")
        self.assertEqual(data["classification_agreement_count"], 5)
        self.assertEqual(data["classification_total"], 5)
        self.assertTrue(all(x["threshold_passed"] for x in data["records"]))
        initial = next(x for x in data["records"] if x["scene_id"] == "initial_collision")
        self.assertTrue(initial["runtime_collision"])

    def test_self_visibility_and_external_cylinder(self) -> None:
        data = load("stage11bm_lidar_self_visibility_regression.json")
        self.assertTrue(data["all_scenes_self_return_zero"])
        self.assertGreater(data["records"]["initial_collision"]["external_inside_footprint_count"], 0)

    def test_semantic_r1_and_sensor_gates(self) -> None:
        semantic = load("stage11bm_semantic_entity_regression.json")
        r1 = load("stage11bm_r1_runtime_contract.json")
        sensors = load("stage11bm_sensor_runtime_smoke.json")
        self.assertTrue(semantic["initial_collision_human"])
        self.assertEqual(r1["rgb_dropout_contract"]["fallback_reason"], "RGB_DROPOUT")
        self.assertEqual(r1["outdated_rgb_contract"]["fallback_reason"], "OUTDATED_IMAGE")
        self.assertEqual(sensors["camera_odometry_pass_count"], 11)

    def test_process_and_protected_boundaries(self) -> None:
        cleanup = load("stage11bm_process_cleanup.json")
        frozen = load("stage11bm_frozen_component_audit.json")
        self.assertTrue(cleanup["all_scene_cleanup_passed"])
        self.assertEqual(cleanup["final_host_residual_gazebo_process_count"], 0)
        self.assertFalse(frozen["planner_started"])
        self.assertFalse(frozen["stage10_loaded"])
        self.assertFalse(frozen["ros_bridge_started"])
        self.assertFalse(frozen["motion_commands_sent"])

    def test_all_json_parse(self) -> None:
        for path in OUT.glob("*.json"):
            with self.subTest(path=path.name):
                json.loads(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
