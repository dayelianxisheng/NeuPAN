"""Tests for the Stage 11B-K mandatory scope-expansion stop."""

import json
import unittest
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[1]
OUT = PROJECT / "artifacts/stages/stage_11b_k_explicit_wall_geometry"


def load(name: str) -> dict:
    return json.loads((OUT / name).read_text(encoding="utf-8"))


class Stage11BKScopeBlockTest(unittest.TestCase):
    def test_repository_wide_include_scale_audit(self) -> None:
        audit = load("stage11bk_include_schema_audit.json")
        self.assertEqual(audit["decision"], "BLOCKED_SCALE_SCOPE_EXPANSION_REQUIRED")
        self.assertEqual(audit["invalid_include_scale_count"], 13)
        self.assertEqual(audit["affected_world_count"], 11)
        self.assertEqual(audit["outside_authorized_scope_count"], 9)
        self.assertIn("initial_collision", audit["outside_authorized_scope_worlds"])
        self.assertTrue(audit["source_generator_emits_include_scale_for_all_obstacles"])

    def test_nonunit_scale_exists_outside_target_scope(self) -> None:
        audit = load("stage11bk_include_schema_audit.json")
        outside = [r for r in audit["records"] if r["has_invalid_include_scale"] and not r["in_authorized_target_scope"]]
        self.assertTrue(any(r["scene_id"] == "initial_collision" and r["scale"] != "1 1 1" for r in outside))

    def test_target_design_intent_is_source_backed(self) -> None:
        intent = load("stage11bk_intended_wall_geometry.json")
        self.assertEqual(len(intent["records"]), 4)
        self.assertFalse(intent["dimensions_inferred_from_runtime_clearance"])
        for wall in intent["records"]:
            self.assertEqual(wall["intended_dimensions_xyz_m"], [5.0, 0.15, 0.5])
            self.assertTrue(wall["base_times_scale_matches_intent"])

    def test_assets_remain_unchanged(self) -> None:
        frozen = load("stage11bk_frozen_asset_audit.json")
        delta = load("stage11bk_asset_delta.json")
        self.assertTrue(frozen["world_hashes_unchanged"])
        self.assertTrue(frozen["model_hashes_unchanged"])
        self.assertFalse(frozen["gazebo_runtime_started"])
        self.assertFalse(frozen["assets_modified"])
        self.assertEqual(delta["changed_files"], [])

    def test_downstream_gates_not_executed(self) -> None:
        for name in [
            "stage11bk_sdf_schema_validation.json",
            "stage11bk_targeted_clearance_consistency.json",
            "stage11bk_camera_regression.json",
            "stage11bk_process_cleanup.json",
        ]:
            with self.subTest(name=name):
                self.assertEqual(load(name)["status"], "NOT_EXECUTED_DUE_TO_EARLIER_STOP")

    def test_all_json_parse(self) -> None:
        for path in OUT.glob("*.json"):
            with self.subTest(path=path.name):
                json.loads(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
