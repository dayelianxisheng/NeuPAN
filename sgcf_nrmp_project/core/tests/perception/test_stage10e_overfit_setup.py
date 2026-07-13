"""Static Stage 10E contract checks that do not rerun training."""

import json
import hashlib
from pathlib import Path
import unittest

import numpy as np
import torch
import yaml

from sgcf_nrmp.data.rgb_semantic_dataset import RGBSemanticDataset
from sgcf_nrmp.models.tiny_semantic_segmentation import TinySemanticSegmentation
from sgcf_nrmp.training.semantic_segmentation_trainer import seed_all


ROOT = Path("sgcf_nrmp_project")
OUT = ROOT / "artifacts/stages/stage_10_rgb_semantic_perception"


class Stage10ESetupTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = yaml.safe_load((ROOT / "core/configs/train/stage_10e_48_image_overfit.yaml").read_text())
        cls.dataset = RGBSemanticDataset(OUT / "dataset/train.npz")

    def test_selection_is_fixed_train_zero_through_47(self):
        self.assertEqual(self.config["selected_scene_ids"], list(range(48)))
        self.assertEqual([int(value) for value in self.dataset.scene_ids[:48]], list(range(48)))

    def test_all_classes_and_tensor_contract(self):
        masks = self.dataset.masks[:48]
        self.assertEqual(np.unique(masks).tolist(), list(range(5)))
        sample = self.dataset[0]
        self.assertEqual(sample["target"].dtype, torch.long)
        self.assertEqual(tuple(sample["image"].shape), (3, 120, 160))
        self.assertEqual(tuple(sample["target"].shape), (120, 160))
        self.assertTrue(torch.isfinite(sample["image"]).all())

    def test_model_and_loss_contract(self):
        model = TinySemanticSegmentation()
        output = model(torch.stack([self.dataset[0]["image"], self.dataset[1]["image"]]))
        self.assertEqual(tuple(output.shape), (2, 5, 120, 160))
        self.assertEqual(model.parameter_count, 118341)
        target = torch.stack([self.dataset[0]["target"], self.dataset[1]["target"]])
        self.assertTrue(torch.isfinite(torch.nn.functional.cross_entropy(output, target)))

    def test_stage10d_weights_are_unchanged(self):
        audit = json.loads((OUT / "stage10d_class_weight_audit.json").read_text())
        confirmation_path = OUT / "stage10e_class_weight_confirmation.json"
        if not confirmation_path.exists():
            self.skipTest("Stage 10E static preparation has not run")
        confirmation = json.loads(confirmation_path.read_text())
        self.assertEqual(audit["actual_normalized_weights"], confirmation["stage10d_weights"])
        self.assertTrue(confirmation["consistent_with_stage10d"])

    def test_first_four_hashes_match_stage10d(self):
        stage10d = json.loads((OUT / "four_image_selection.json").read_text())
        stage10e = json.loads((OUT / "stage10e_48_image_selection.json").read_text())
        for old, new in zip(stage10d["records"], stage10e["records"][:4]):
            self.assertEqual(old["scene_id"], new["scene_id"])
            self.assertEqual(old["rgb_sha256"], new["rgb_sha256"])
            self.assertEqual(old["semantic_label_sha256"], new["semantic_label_sha256"])

    def test_training_configuration_is_frozen(self):
        self.assertEqual(self.config["loss"], "current_sqrt_weighted_cross_entropy")
        self.assertFalse(self.config["augmentation"])
        self.assertFalse(self.config["dropout"])
        self.assertFalse(self.config["shuffle"])
        self.assertEqual(self.config["weight_decay"], 0.0)
        self.assertLessEqual(self.config["maximum_optimizer_steps"], 5000)

    def test_fixed_seed_initialization_matches_stage10d(self):
        seed_all(self.config["seed"])
        model = TinySemanticSegmentation()
        digest = hashlib.sha256(
            b"".join(value.detach().numpy().tobytes() for value in model.state_dict().values())
        ).hexdigest()
        metrics = json.loads((OUT / "stage10e_overfit_metrics.json").read_text())
        stage10d = json.loads((OUT / "four_image_loss_comparison.json").read_text())
        self.assertEqual(digest, metrics["initial_state_sha256"])
        self.assertEqual(digest, stage10d["L1_current_weighted_CE"]["initial_state_sha256"])

    def test_checkpoint_reload_report(self):
        report_path = OUT / "stage10e_checkpoint_reload.json"
        if not report_path.exists():
            self.skipTest("Stage 10E training has not run")
        report = json.loads(report_path.read_text())
        self.assertTrue(report["pass"])
        self.assertLessEqual(report["logits_max_absolute_difference"], report["floating_point_tolerance"])


if __name__ == "__main__":
    unittest.main()
