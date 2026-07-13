"""Stage 10H early stopping, checkpoint ordering, and readiness tests."""

import unittest

from sgcf_nrmp.training.lifecycle import (
    WarmupEarlyStopping,
    validation_checkpoint_key,
    validation_readiness,
)


def metrics(mean_iou=.6, macro_f1=.7, human=.8, vehicle=.7, robot=.6):
    return {
        "mean_iou": mean_iou,
        "macro_f1": macro_f1,
        "per_class_iou": {"HUMAN": human - .1},
        "per_class_recall": {"HUMAN": human, "VEHICLE": vehicle, "ROBOT": robot},
        "prediction_class_fraction": {"HUMAN": .05, "VEHICLE": .05, "ROBOT": .05},
    }


class Stage10HPolicyTest(unittest.TestCase):
    def test_minimum_epoch_is_inclusive(self):
        policy = WarmupEarlyStopping(minimum_training_epochs=60, patience=2)
        for epoch in range(1, 61):
            result = policy.update(epoch, 1.0 if epoch == 1 else 0.0)
            self.assertFalse(result["stop"])
            self.assertEqual(result["counter"], 0)
        self.assertTrue(result["warmup"])

    def test_patience_updates_after_warmup(self):
        policy = WarmupEarlyStopping(minimum_training_epochs=60, patience=2)
        policy.update(60, .5)
        self.assertFalse(policy.update(61, .5)["stop"])
        self.assertTrue(policy.update(62, .5)["stop"])

    def test_min_delta_is_respected(self):
        policy = WarmupEarlyStopping(minimum_training_epochs=1, patience=3, min_delta=1e-4)
        policy.update(1, .5)
        self.assertFalse(policy.update(2, .50005)["improved"])
        self.assertTrue(policy.update(3, .5002)["improved"])
        self.assertEqual(policy.counter, 0)

    def test_checkpoint_tie_breakers(self):
        base = metrics()
        better_human_iou = metrics()
        better_human_iou["per_class_iou"]["HUMAN"] += .01
        self.assertGreater(validation_checkpoint_key(better_human_iou, .4), validation_checkpoint_key(base, .4))
        better_loss = validation_checkpoint_key(base, .3)
        self.assertGreater(better_loss, validation_checkpoint_key(base, .4))

    def test_readiness_passes_complete_metrics(self):
        self.assertTrue(validation_readiness(metrics())["passed"])

    def test_readiness_rejects_vehicle_recall(self):
        result = validation_readiness(metrics(vehicle=.49))
        self.assertFalse(result["passed"])
        self.assertFalse(result["checks"]["vehicle_recall_at_least_0_50"])

    def test_readiness_rejects_prediction_collapse(self):
        value = metrics()
        value["prediction_class_fraction"]["ROBOT"] = 0
        self.assertFalse(validation_readiness(value)["passed"])


if __name__ == "__main__":
    unittest.main()
