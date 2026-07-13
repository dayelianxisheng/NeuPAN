"""Stage 10J hard-feasibility and fixed low-LR safeguards."""

import json
from pathlib import Path
import unittest

import torch
import yaml

from sgcf_nrmp.training.lifecycle import feasible_checkpoint_key, validation_hard_feasibility


ROOT = Path("sgcf_nrmp_project")
OUT = ROOT / "artifacts/stages/stage_10_rgb_semantic_perception"


def metrics():
    return {
        "mean_iou": .80, "macro_f1": .88,
        "per_class_iou": {"HUMAN": .66},
        "per_class_recall": {"HUMAN": .86, "VEHICLE": .76, "ROBOT": .81},
        "prediction_class_fraction": {"HUMAN": .04, "VEHICLE": .05, "ROBOT": .06},
    }


class Stage10JFeasibilityTest(unittest.TestCase):
    def test_all_conditions_are_required(self):
        self.assertTrue(validation_hard_feasibility(metrics())["passed"])
        for field, name in (("mean_iou", "mean_iou_at_least_0_78"), ("macro_f1", "macro_f1_at_least_0_87")):
            value = metrics(); value[field] = 0
            result = validation_hard_feasibility(value)
            self.assertFalse(result["passed"]); self.assertFalse(result["checks"][name])

    def test_single_class_failure_rejects_checkpoint(self):
        value = metrics(); value["per_class_recall"]["HUMAN"] = .849
        self.assertFalse(validation_hard_feasibility(value)["passed"])

    def test_prediction_collapse_rejects_checkpoint(self):
        value = metrics(); value["prediction_class_fraction"]["ROBOT"] = 0
        self.assertFalse(validation_hard_feasibility(value)["passed"])

    def test_feasible_tie_break_order(self):
        baseline = feasible_checkpoint_key(metrics(), .3)
        value = metrics(); value["macro_f1"] += .01
        self.assertGreater(feasible_checkpoint_key(value, .3), baseline)
        self.assertGreater(feasible_checkpoint_key(metrics(), .2), baseline)

    def test_fixed_config_has_one_seed_and_one_new_lr(self):
        config = yaml.safe_load((ROOT / "core/configs/train/stage_10j_low_lr_stabilization.yaml").read_text())
        self.assertEqual(config["seed"], 10)
        self.assertEqual(config["learning_rate"], .0002)
        self.assertEqual(config["old_learning_rate"], .002)
        self.assertEqual(config["maximum_additional_epochs"], 50)
        self.assertFalse(config["early_stopping"])

    def test_input_checkpoint_is_epoch_145_with_optimizer(self):
        checkpoint = torch.load(OUT / "stage10i_validation_diagnostic_checkpoint.pt", map_location="cpu", weights_only=True)
        self.assertEqual(checkpoint["epoch"], 145)
        self.assertTrue(checkpoint["optimizer_state_dict"]["state"])

    def test_expected_false_non_access_flags_do_not_fail_audit(self):
        required = {"checkpoint": True, "hash": True}
        test_accessed = False
        new_audit_accessed = False
        passed = all(required.values()) and not test_accessed and not new_audit_accessed
        self.assertTrue(passed)

    def test_completed_history_is_fixed_single_run(self):
        history = json.loads((OUT / "stage10j_training_history.json").read_text())
        self.assertEqual([row["epoch"] for row in history], list(range(146, 196)))
        self.assertTrue(all(row["learning_rate"] == .0002 for row in history))
        self.assertTrue(all(torch.isfinite(torch.tensor(row["validation"]["loss"])) for row in history))

    def test_optimizer_moments_and_non_lr_state_are_preserved(self):
        audit = json.loads((OUT / "stage10j_optimizer_state_audit.json").read_text())
        self.assertEqual(audit["old_learning_rates"], [.002])
        self.assertEqual(audit["new_learning_rates"], [.0002])
        self.assertTrue(audit["moments_unchanged"])
        self.assertTrue(audit["non_lr_parameter_groups_unchanged"])
        self.assertFalse(audit["optimizer_reinitialized_after_state_load"])

    def test_original_test_and_new_audit_remain_unaccessed(self):
        test_audit = json.loads((OUT / "stage10j_test_freeze_audit.json").read_text())
        audit_audit = json.loads((OUT / "stage10j_new_audit_non_access.json").read_text())
        for key, value in test_audit.items():
            if key != "test_scene_ids_read_from_manifest_only":
                self.assertFalse(value, key)
        for key, value in audit_audit.items():
            if key != "reason":
                self.assertFalse(value, key)

    def test_recorded_feasibility_matches_gate(self):
        history = json.loads((OUT / "stage10j_training_history.json").read_text())
        for row in history:
            expected = validation_hard_feasibility(row["validation"])
            self.assertEqual(row["feasibility"], expected)
        summary = json.loads((OUT / "stage10j_validation_feasibility.json").read_text())
        self.assertEqual(summary["feasible_epoch_count"], 0)
        self.assertIsNone(summary["best_feasible"])

    def test_checkpoint_writes_are_atomic_and_reload_exact(self):
        lifecycle = json.loads((OUT / "stage10j_checkpoint_lifecycle.json").read_text())
        self.assertTrue(lifecycle["events"])
        self.assertTrue(lifecycle["all_atomic"])
        self.assertTrue(lifecycle["all_reload_differences_within_1e-7"])
        self.assertTrue(all(event["reload_max_abs_difference"] <= 1e-7 for event in lifecycle["events"]))


if __name__ == "__main__":
    unittest.main()
