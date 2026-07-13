"""Stage 10 training lifecycle helpers with atomic diagnostic checkpoints."""

from __future__ import annotations

import os
from pathlib import Path
import tempfile
from dataclasses import dataclass

import numpy as np
import torch

from sgcf_nrmp.evaluation.semantic_perception_evaluator import (
    collect_probabilities,
    evaluate_probabilities,
)


@torch.no_grad()
def evaluate_split(model, images, targets, criterion, batch_size=8):
    """Evaluate one split with isolated stateless metrics and no gradients."""
    model.eval()
    losses = []
    for start in range(0, len(images), batch_size):
        logits = model(images[start:start + batch_size])
        losses.append(float(criterion(logits, targets[start:start + batch_size])))
    probabilities = collect_probabilities(model, images, batch_size)
    metrics = evaluate_probabilities(probabilities, targets.cpu().numpy())
    return float(np.mean(losses)), metrics, probabilities


def atomic_torch_save(payload: dict, destination: Path) -> None:
    """Write, fsync, and atomically rename a Torch checkpoint."""
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w+b", prefix=destination.name + ".", suffix=".tmp", dir=destination.parent, delete=False
    ) as temporary:
        temporary_path = Path(temporary.name)
        try:
            torch.save(payload, temporary)
            temporary.flush()
            os.fsync(temporary.fileno())
        except Exception:
            temporary_path.unlink(missing_ok=True)
            raise
    os.replace(temporary_path, destination)
    directory_fd = os.open(destination.parent, os.O_RDONLY)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)


def checkpoint_reload_max_difference(path: Path, model_factory, probe: torch.Tensor) -> float:
    checkpoint = torch.load(path, map_location="cpu", weights_only=True)
    first = model_factory()
    second = model_factory()
    first.load_state_dict(checkpoint["model_state_dict"])
    second.load_state_dict(checkpoint["model_state_dict"])
    first.eval()
    second.eval()
    with torch.no_grad():
        return float((first(probe) - second(probe)).abs().max())


def validation_checkpoint_key(metrics: dict, validation_loss: float) -> tuple[float, ...]:
    """Return the frozen Stage 10 checkpoint ordering key."""
    return (
        float(metrics["mean_iou"]),
        float(metrics["per_class_iou"]["HUMAN"]),
        float(metrics["per_class_recall"]["HUMAN"]),
        -float(validation_loss),
    )


@dataclass
class WarmupEarlyStopping:
    """Validation-mIoU early stopping with an inclusive warm-up epoch."""

    minimum_training_epochs: int = 60
    patience: int = 20
    min_delta: float = 1e-4
    best_metric: float | None = None
    counter: int = 0

    def update(self, epoch: int, metric: float) -> dict:
        """Update state; stopping is impossible through the minimum epoch."""
        metric = float(metric)
        improved = self.best_metric is None or metric > self.best_metric + self.min_delta
        if improved:
            self.best_metric = metric
        if epoch <= self.minimum_training_epochs:
            self.counter = 0
            return {"improved": improved, "counter": 0, "stop": False, "warmup": True}
        if improved:
            self.counter = 0
        else:
            self.counter += 1
        return {
            "improved": improved,
            "counter": self.counter,
            "stop": self.counter >= self.patience,
            "warmup": False,
        }


def validation_readiness(metrics: dict) -> dict:
    """Evaluate the frozen Stage 10H validation gate."""
    recall = metrics["per_class_recall"]
    fractions = metrics["prediction_class_fraction"]
    checks = {
        "mean_iou_at_least_0_50": float(metrics["mean_iou"]) >= 0.50,
        "macro_f1_at_least_0_60": float(metrics["macro_f1"]) >= 0.60,
        "human_recall_at_least_0_75": float(recall["HUMAN"]) >= 0.75,
        "vehicle_recall_at_least_0_50": float(recall["VEHICLE"]) >= 0.50,
        "robot_recall_at_least_0_50": float(recall["ROBOT"]) >= 0.50,
        "no_core_class_prediction_collapse": all(float(fractions[name]) > 0 for name in ("HUMAN", "VEHICLE", "ROBOT")),
    }
    return {"checks": checks, "passed": all(checks.values())}


def validation_hard_feasibility(metrics: dict) -> dict:
    """Apply the Stage 10J multi-objective validation gate using logical AND."""
    recall = metrics["per_class_recall"]
    iou = metrics["per_class_iou"]
    fractions = metrics["prediction_class_fraction"]
    scalar_values = [
        metrics["mean_iou"], metrics["macro_f1"], iou["HUMAN"],
        recall["HUMAN"], recall["VEHICLE"], recall["ROBOT"],
        fractions["HUMAN"], fractions["VEHICLE"], fractions["ROBOT"],
    ]
    checks = {
        "mean_iou_at_least_0_78": float(metrics["mean_iou"]) >= 0.78,
        "macro_f1_at_least_0_87": float(metrics["macro_f1"]) >= 0.87,
        "human_iou_at_least_0_65": float(iou["HUMAN"]) >= 0.65,
        "human_recall_at_least_0_85": float(recall["HUMAN"]) >= 0.85,
        "vehicle_recall_at_least_0_75": float(recall["VEHICLE"]) >= 0.75,
        "robot_recall_at_least_0_80": float(recall["ROBOT"]) >= 0.80,
        "human_prediction_fraction_positive": float(fractions["HUMAN"]) > 0,
        "vehicle_prediction_fraction_positive": float(fractions["VEHICLE"]) > 0,
        "robot_prediction_fraction_positive": float(fractions["ROBOT"]) > 0,
        "all_gate_values_finite": bool(np.isfinite(scalar_values).all()),
    }
    return {"checks": checks, "passed": all(checks.values())}


def feasible_checkpoint_key(metrics: dict, validation_loss: float) -> tuple[float, ...]:
    """Return the frozen ranking key after hard-feasibility filtering."""
    return (
        float(metrics["mean_iou"]),
        float(metrics["macro_f1"]),
        float(metrics["per_class_iou"]["HUMAN"]),
        float(metrics["per_class_recall"]["HUMAN"]),
        -float(validation_loss),
    )
