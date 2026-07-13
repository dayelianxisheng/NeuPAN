"""Stage 10I validation-only continuation safeguards."""

import json
from pathlib import Path
import unittest

import numpy as np
import torch
import yaml

from sgcf_nrmp.training.lifecycle import atomic_torch_save


ROOT = Path("sgcf_nrmp_project")
OUT = ROOT / "artifacts/stages/stage_10_rgb_semantic_perception"


class Stage10IValidationOnlyTest(unittest.TestCase):
    def test_source_checkpoint_is_epoch_100_with_optimizer(self):
        checkpoint = torch.load(OUT / "best_rgb_semantic_model.pt", map_location="cpu", weights_only=True)
        self.assertEqual(checkpoint["epoch"], 100)
        self.assertTrue(checkpoint["optimizer_state_dict"]["state"])
        self.assertEqual(checkpoint["optimizer_state_dict"]["param_groups"][0]["lr"], 0.002)

    def test_continuation_config_is_bounded_and_frozen(self):
        config = yaml.safe_load((ROOT / "core/configs/train/stage_10i_validation_continuation.yaml").read_text())
        self.assertEqual((config["start_epoch"], config["maximum_final_epoch"], config["maximum_additional_epochs"]), (101, 150, 50))
        self.assertEqual(config["learning_rate"], 0.002)
        self.assertEqual(config["batch_size"], 8)
        self.assertFalse(config["shuffle"])

    def test_script_has_no_test_npz_access_path(self):
        source = (ROOT / "core/scripts/diagnose_stage10i_human_recall.py").read_text()
        self.assertNotIn("dataset/test.npz", source)
        self.assertNotIn("RGBSemanticDataset(OUT / \"dataset/test", source)

    def test_atomic_checkpoint_round_trip(self):
        path = OUT / ".stage10i_atomic_test.pt"
        try:
            atomic_torch_save({"epoch": 101, "value": torch.tensor([1.0])}, path)
            restored = torch.load(path, map_location="cpu", weights_only=True)
            self.assertEqual(restored["epoch"], 101)
            self.assertTrue(torch.equal(restored["value"], torch.tensor([1.0])))
            self.assertFalse(list(OUT.glob(".stage10i_atomic_test.pt.*.tmp")))
        finally:
            path.unlink(missing_ok=True)

    def test_stage10h_history_is_finite(self):
        history = json.loads((OUT / "stage10h_training_history.json").read_text())
        values = [item["validation"]["loss"] for item in history]
        self.assertEqual(len(history), 100)
        self.assertTrue(np.isfinite(values).all())

    def test_test_freeze_audit_denies_all_access(self):
        audit = json.loads((OUT / "stage10i_test_freeze_audit.json").read_text())
        for key in (
            "test_npz_path_constructed_or_opened", "test_dataset_instantiated",
            "test_dataloader_iterated", "test_inference_executed",
            "test_metrics_recomputed", "test_predictions_inspected_for_tuning",
        ):
            self.assertFalse(audit[key])

    def test_preflight_restores_optimizer_without_lr_change(self):
        audit = json.loads((OUT / "stage10i_continuation_preflight.json").read_text())
        self.assertTrue(audit["all_frozen_state_checks_passed"])
        self.assertTrue(audit["optimizer_loaded_without_reset"])
        self.assertTrue(audit["learning_rate_unchanged"])
        self.assertEqual(audit["scheduler"], "not_applicable_no_scheduler")

    def test_sentinels_are_validation_only_and_fixed(self):
        selection = json.loads((OUT / "stage10i_human_sentinel_selection.json").read_text())
        self.assertEqual(selection["all_from_split"], "validation")
        self.assertTrue(selection["fixed_before_continuation"])
        self.assertEqual(len(selection["low_recall"]), 4)
        self.assertEqual(len(selection["high_recall"]), 4)

    def test_diagnostic_checkpoint_is_not_accepted(self):
        checkpoint = torch.load(OUT / "stage10i_validation_diagnostic_checkpoint.pt", map_location="cpu", weights_only=True)
        self.assertEqual(checkpoint["purpose"], "VALIDATION_ONLY_DIAGNOSTIC")
        self.assertIn("NOT_EVALUATED_ON_UNTOUCHED_TEST", checkpoint["acceptance"])
        self.assertIn("NOT_ACCEPTED_AS_FINAL_STAGE10_MODEL", checkpoint["acceptance"])

    def test_continuation_is_finite_and_bounded(self):
        history = json.loads((OUT / "stage10i_continuation_history.json").read_text())
        self.assertEqual(history[0]["epoch"], 101)
        self.assertLessEqual(history[-1]["epoch"], 150)
        values = [item["validation"]["loss"] for item in history]
        self.assertTrue(np.isfinite(values).all())


if __name__ == "__main__":
    unittest.main()
