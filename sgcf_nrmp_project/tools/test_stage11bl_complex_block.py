"""Regression tests for the Stage 11B-L complex-model hard stop."""

import json
import unittest
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[1]
OUT = PROJECT / "artifacts/stages/stage_11b_l_global_include_scale_normalization"


def load(name: str) -> dict:
    return json.loads((OUT / name).read_text(encoding="utf-8"))


class Stage11BLComplexBlockTest(unittest.TestCase):
    def test_all_historical_scales_classified(self) -> None:
        data = load("stage11bl_include_scale_inventory.json")
        self.assertEqual(data["historical_invalid_include_scale_count"], 13)
        self.assertEqual(data["unit_scale_count"], 8)
        self.assertEqual(data["nonunit_scale_count"], 5)
        self.assertEqual(data["affected_world_count"], 11)

    def test_initial_collision_is_nonunit_cylinder(self) -> None:
        data = load("stage11bl_nonunit_scale_resolution.json")
        record = next(x for x in data["records"] if x["instance_name"] == "initial_collision_obstacle")
        self.assertEqual(record["geometry_type"], "cylinder")
        self.assertEqual(record["scale_xyz"], [4 / 7, 4 / 7, 4 / 17])
        self.assertFalse(record["automatic_materialization_safe"])
        self.assertEqual(data["decision"], "BLOCKED_NONUNIT_MODEL_MATERIALIZATION_COMPLEX")

    def test_box_walls_resolve_exactly(self) -> None:
        data = load("stage11bl_nonunit_scale_resolution.json")
        walls = [x for x in data["records"] if x["instance_name"].startswith("wall_")]
        self.assertEqual(len(walls), 4)
        for wall in walls:
            self.assertTrue(wall["automatic_materialization_safe"])
            self.assertEqual(wall["resolved_dimensions"], [5.0, 0.15, 0.5])

    def test_no_assets_or_runtime_changed(self) -> None:
        frozen = load("stage11bl_frozen_component_audit.json")
        delta = load("stage11bl_asset_delta.json")
        self.assertTrue(frozen["world_hashes_unchanged"])
        self.assertTrue(frozen["model_hashes_unchanged"])
        self.assertFalse(frozen["assets_modified"])
        self.assertFalse(frozen["runtime_started"])
        self.assertEqual(delta["changed_files"], [])

    def test_downstream_work_not_fabricated(self) -> None:
        for name in [
            "stage11bl_generator_migration.json",
            "stage11bl_sdf_schema_validation.json",
            "stage11bl_changed_world_runtime_matrix.json",
            "stage11bl_runtime_clearance_consistency.json",
            "stage11bl_process_cleanup.json",
        ]:
            with self.subTest(name=name):
                self.assertEqual(load(name)["status"], "NOT_EXECUTED_DUE_TO_EARLIER_STOP")

    def test_all_json_parse(self) -> None:
        for path in OUT.glob("*.json"):
            with self.subTest(path=path.name):
                json.loads(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
