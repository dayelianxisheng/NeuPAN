"""Lifecycle, threshold schema, and atomic checkpoint tests."""

from pathlib import Path
import hashlib
import json
import tempfile
import unittest

import numpy as np
import torch
from torch import nn

from sgcf_nrmp.evaluation.threshold_summary import (
    RATE_KEYS,
    build_threshold_summary,
    validate_threshold_summary,
)
from sgcf_nrmp.training.lifecycle import atomic_torch_save, evaluate_split
from sgcf_nrmp.data.rgb_semantic_dataset import RGBSemanticDataset
from sgcf_nrmp.models.tiny_semantic_segmentation import TinySemanticSegmentation
from sgcf_nrmp.training.semantic_segmentation_trainer import seed_all


ROOT = Path("sgcf_nrmp_project")
OUT = ROOT / "artifacts/stages/stage_10_rgb_semantic_perception"


class ObservedModel(nn.Module):
    def __init__(self):
        super().__init__()
        self.weight = nn.Parameter(torch.zeros(1))
        self.flags = []

    def forward(self, value):
        self.flags.append({"training": self.training, "grad_enabled": torch.is_grad_enabled()})
        output = torch.zeros(len(value), 5, value.shape[-2], value.shape[-1]) + self.weight
        return output


class Stage10GLifecycleTest(unittest.TestCase):
    def test_threshold_strategies_share_schema(self):
        target = np.array([[0, 1, 2, 3, 4]])
        predictions = [target, np.zeros_like(target), np.array([[0, 2, 0, 3, 2]])]
        for prediction in predictions:
            self.assertEqual(tuple(build_threshold_summary(target, prediction)), RATE_KEYS)

    def test_static_to_human_rate(self):
        target = np.array([[1, 1, 2]])
        prediction = np.array([[2, 1, 2]])
        entry = build_threshold_summary(target, prediction)["static_to_human_rate"]
        self.assertTrue(entry["valid"])
        self.assertEqual(entry["value"], 0.5)

    def test_zero_denominator_is_explicit_invalid(self):
        summary = build_threshold_summary(np.array([[0, 2]]), np.array([[0, 2]]))
        entry = summary["static_to_human_rate"]
        self.assertFalse(entry["valid"])
        self.assertIsNone(entry["value"])
        self.assertEqual(entry["reason"], "zero_denominator")

    def test_missing_schema_raises_clear_error(self):
        summary = build_threshold_summary(np.array([[0, 1, 2]]), np.array([[0, 1, 2]]))
        summary.pop("static_to_human_rate")
        with self.assertRaisesRegex(ValueError, "missing"):
            validate_threshold_summary(summary)

    def test_validation_eval_and_metric_calls_are_isolated(self):
        model = ObservedModel()
        images = torch.zeros(2, 3, 4, 4)
        targets = torch.zeros(2, 4, 4, dtype=torch.long)
        criterion = nn.CrossEntropyLoss()
        _, first, _ = evaluate_split(model, images, targets, criterion, 1)
        _, second, _ = evaluate_split(model, images, targets, criterion, 1)
        self.assertEqual(first["confusion_matrix"], second["confusion_matrix"])
        self.assertTrue(all(not item["training"] and not item["grad_enabled"] for item in model.flags))
        model.train()
        self.assertTrue(model.training)

    def test_atomic_checkpoint_exists_without_temp_and_reloads(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "best.pt"
            model = nn.Linear(2, 2)
            atomic_torch_save({"model_state_dict": model.state_dict(), "epoch": 1}, path)
            self.assertTrue(path.exists())
            self.assertFalse(list(path.parent.glob("*.tmp")))
            restored = nn.Linear(2, 2)
            restored.load_state_dict(torch.load(path, weights_only=True)["model_state_dict"])
            for left, right in zip(model.parameters(), restored.parameters()):
                self.assertTrue(torch.equal(left, right))

    def test_sentinel_hashes_are_fixed_and_train_validation_only(self):
        selection = json.loads((OUT / "stage10g_sentinel_selection.json").read_text())
        self.assertFalse(selection["test_used"])
        for split in ("train", "validation"):
            dataset = RGBSemanticDataset(OUT / f"dataset/{split}.npz")
            self.assertTrue(selection[f"{split}_aggregate_all_classes_present"])
            for record in selection[split]:
                index = record["dataset_index"]
                self.assertEqual(hashlib.sha256(dataset.images[index].tobytes()).hexdigest(), record["rgb_sha256"])
                self.assertEqual(hashlib.sha256(dataset.masks[index].tobytes()).hexdigest(), record["semantic_label_sha256"])

    def test_validation_core_classes_exist(self):
        audit = json.loads((OUT / "stage10g_train_validation_input_audit.json").read_text())
        self.assertTrue(audit["validation_core_classes_present"])
        self.assertEqual(audit["validation"]["label_ids"], list(range(5)))
        distribution = json.loads((OUT / "stage10g_train_validation_class_distribution.json").read_text())
        for name in ("HUMAN", "VEHICLE", "ROBOT"):
            self.assertGreater(distribution["validation"][name]["pixel_count"], 0)

    def test_test_split_was_not_iterated(self):
        audit = json.loads((OUT / "stage10g_test_non_access_audit.json").read_text())
        for key in ("test_dataset_npz_opened", "test_dataset_instantiated", "test_dataloader_created", "test_dataloader_iterated", "test_metrics_computed", "test_predictions_saved"):
            self.assertFalse(audit[key])

    def test_replay_history_is_finite_and_fixed_seed(self):
        history = json.loads((OUT / "stage10g_training_history.json").read_text())
        self.assertEqual(len(history), 50)
        values = []
        for record in history:
            values.extend((record["train_loss"], record["validation_loss"], record["gradient_norm_mean"], record["parameter_update_norm"]))
        self.assertTrue(np.isfinite(values).all())
        seed_all(10)
        model = TinySemanticSegmentation()
        digest = hashlib.sha256(b"".join(value.detach().numpy().tobytes() for value in model.state_dict().values())).hexdigest()
        self.assertEqual(digest, "f52c92334e3602ead517dfdf6fe4709a5f2b04a3dad86a82f516aa08affa57d6")

    def test_diagnostic_checkpoint_metadata_and_reload(self):
        checkpoint = torch.load(OUT / "stage10g_diagnostic_best_checkpoint.pt", map_location="cpu", weights_only=True)
        self.assertEqual(checkpoint["purpose"], "DIAGNOSTIC_ONLY_NOT_ACCEPTED_FOR_STAGE10")
        self.assertIn("optimizer_state_dict", checkpoint)
        lifecycle = json.loads((OUT / "stage10g_checkpoint_lifecycle.json").read_text())
        self.assertTrue(lifecycle["save_occurs_before_early_stopping_update"])
        self.assertTrue(lifecycle["save_independent_of_threshold_reporting"])
        self.assertEqual(lifecycle["final_reload_max_abs_difference"], 0.0)


if __name__ == "__main__":
    unittest.main()
