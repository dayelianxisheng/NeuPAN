"""Metrics for frozen Stage 10 RGB semantic predictions."""

from __future__ import annotations

import numpy as np
import torch
from scipy.ndimage import distance_transform_edt, label as connected_components


CLASS_NAMES = ("UNKNOWN", "STATIC_OBSTACLE", "HUMAN", "VEHICLE", "ROBOT")


def confusion_matrix(target: np.ndarray, prediction: np.ndarray, class_count: int = 5) -> np.ndarray:
    target = np.asarray(target, np.int64)
    prediction = np.asarray(prediction, np.int64)
    return np.bincount(
        (target * class_count + prediction).ravel(), minlength=class_count ** 2
    ).reshape(class_count, class_count)


def metrics_from_confusion(matrix: np.ndarray) -> dict:
    matrix = np.asarray(matrix, np.int64)
    true_positive = np.diag(matrix).astype(float)
    support = matrix.sum(axis=1)
    predicted = matrix.sum(axis=0)
    recall = true_positive / np.maximum(support, 1)
    precision = true_positive / np.maximum(predicted, 1)
    iou = true_positive / np.maximum(support + predicted - true_positive, 1)
    f1 = 2 * precision * recall / np.maximum(precision + recall, 1e-12)
    return {
        "pixel_accuracy": float(true_positive.sum() / max(matrix.sum(), 1)),
        "mean_iou": float(iou.mean()),
        "macro_f1": float(f1.mean()),
        "per_class_iou": dict(zip(CLASS_NAMES, iou.tolist())),
        "per_class_precision": dict(zip(CLASS_NAMES, precision.tolist())),
        "per_class_recall": dict(zip(CLASS_NAMES, recall.tolist())),
        "prediction_class_fraction": dict(zip(CLASS_NAMES, (predicted / max(matrix.sum(), 1)).tolist())),
        "unknown_rate": float(predicted[0] / max(matrix.sum(), 1)),
        "confusion_matrix": matrix.tolist(),
    }


def calibration_metrics(probabilities: np.ndarray, target: np.ndarray, bins: int = 15) -> dict:
    probabilities = np.asarray(probabilities, float)
    target = np.asarray(target, np.int64)
    flat_probability = probabilities.transpose(0, 2, 3, 1).reshape(-1, probabilities.shape[1])
    flat_target = target.ravel()
    selected = np.clip(flat_probability[np.arange(len(flat_target)), flat_target], 1e-12, 1.0)
    nll = float(-np.log(selected).mean())
    one_hot = np.eye(probabilities.shape[1])[flat_target]
    brier = float(np.square(flat_probability - one_hot).sum(axis=1).mean())
    confidence = flat_probability.max(axis=1)
    correct = flat_probability.argmax(axis=1) == flat_target
    edges = np.linspace(0.0, 1.0, bins + 1)
    ece = 0.0
    curve = []
    for index in range(bins):
        mask = (confidence >= edges[index]) & (confidence < edges[index + 1] if index < bins - 1 else confidence <= edges[index + 1])
        if mask.any():
            accuracy = float(correct[mask].mean())
            average_confidence = float(confidence[mask].mean())
            ece += float(mask.mean()) * abs(accuracy - average_confidence)
            curve.append({"lower": float(edges[index]), "upper": float(edges[index + 1]), "count": int(mask.sum()), "accuracy": accuracy, "confidence": average_confidence})
    return {"nll": nll, "brier_score": brier, "ece": float(ece), "calibration_curve": curve, "mean_confidence": float(confidence.mean())}


def evaluate_probabilities(probabilities: np.ndarray, target: np.ndarray, prediction: np.ndarray | None = None) -> dict:
    probabilities = np.asarray(probabilities, float)
    target = np.asarray(target, np.int64)
    if prediction is None:
        prediction = probabilities.argmax(axis=1)
    result = metrics_from_confusion(confusion_matrix(target, prediction))
    result.update(calibration_metrics(probabilities, target))
    return result


def semantic_regions(target: np.ndarray, occluded: np.ndarray) -> dict[str, np.ndarray]:
    target = np.asarray(target, np.int64)
    regions: dict[str, np.ndarray] = {}
    for width in (1, 3, 5):
        boundary = np.zeros_like(target, bool)
        for image_index, mask in enumerate(target):
            for class_id in range(5):
                current = mask == class_id
                boundary[image_index] |= current & (distance_transform_edt(current) <= width)
        regions[f"boundary_{width}px"] = boundary
    regions["object_interior"] = (target != 0) & ~regions["boundary_3px"]
    border = np.zeros_like(target, bool)
    border[:, :5, :] = True
    border[:, -5:, :] = True
    border[:, :, :5] = True
    border[:, :, -5:] = True
    regions["image_border_5px"] = border
    regions["occluded_region"] = np.asarray(occluded, bool)
    small = np.zeros_like(target, bool)
    for image_index, mask in enumerate(target):
        for class_id in range(1, 5):
            components, count = connected_components(mask == class_id)
            for component_id in range(1, count + 1):
                component = components == component_id
                if component.sum() <= 500:
                    small[image_index] |= component
    regions["small_components_le_500px"] = small
    return regions


def region_evaluation(target: np.ndarray, prediction: np.ndarray, occluded: np.ndarray) -> dict:
    result = {}
    for name, region in semantic_regions(target, occluded).items():
        if region.any():
            result[name] = {"pixel_count": int(region.sum()), **metrics_from_confusion(confusion_matrix(target[region], prediction[region]))}
        else:
            result[name] = {"pixel_count": 0, "status": "EMPTY_REGION"}
    return result


@torch.no_grad()
def collect_probabilities(model: torch.nn.Module, images: torch.Tensor, batch_size: int = 8) -> np.ndarray:
    model.eval()
    result = []
    for start in range(0, len(images), batch_size):
        result.append(torch.softmax(model(images[start:start + batch_size]), dim=1).cpu().numpy())
    return np.concatenate(result)
