"""Validated fixed-schema threshold diagnostics."""

from __future__ import annotations

import numpy as np


RATE_KEYS = (
    "human_to_static_rate",
    "human_to_unknown_rate",
    "static_to_human_rate",
    "robot_to_human_rate",
    "human_to_robot_rate",
    "unknown_rate",
    "human_recall",
    "macro_f1",
)


def _rate(numerator: int, denominator: int) -> dict:
    if denominator == 0:
        return {"value": None, "valid": False, "reason": "zero_denominator", "numerator": int(numerator), "denominator": 0}
    return {"value": float(numerator / denominator), "valid": True, "reason": None, "numerator": int(numerator), "denominator": int(denominator)}


def build_threshold_summary(target: np.ndarray, prediction: np.ndarray) -> dict:
    target = np.asarray(target, np.int64)
    prediction = np.asarray(prediction, np.int64)
    matrix = np.bincount((target * 5 + prediction).ravel(), minlength=25).reshape(5, 5)
    support = matrix.sum(axis=1)
    predicted = matrix.sum(axis=0)
    true_positive = np.diag(matrix).astype(float)
    recall = true_positive / np.maximum(support, 1)
    precision = true_positive / np.maximum(predicted, 1)
    f1 = 2 * recall * precision / np.maximum(recall + precision, 1e-12)
    total = int(matrix.sum())
    summary = {
        "human_to_static_rate": _rate(matrix[2, 1], support[2]),
        "human_to_unknown_rate": _rate(matrix[2, 0], support[2]),
        "static_to_human_rate": _rate(matrix[1, 2], support[1]),
        "robot_to_human_rate": _rate(matrix[4, 2], support[4]),
        "human_to_robot_rate": _rate(matrix[2, 4], support[2]),
        "unknown_rate": _rate(predicted[0], total),
        "human_recall": _rate(matrix[2, 2], support[2]),
        "macro_f1": {"value": float(f1.mean()), "valid": True, "reason": None, "numerator": None, "denominator": None},
    }
    validate_threshold_summary(summary)
    return summary


def validate_threshold_summary(summary: dict) -> None:
    missing = [key for key in RATE_KEYS if key not in summary]
    extra = [key for key in summary if key not in RATE_KEYS]
    if missing or extra:
        raise ValueError(f"threshold summary schema mismatch: missing={missing}, extra={extra}")
    for key in RATE_KEYS:
        entry = summary[key]
        if set(entry) != {"value", "valid", "reason", "numerator", "denominator"}:
            raise ValueError(f"threshold metric schema mismatch for {key}")
        if entry["valid"] and entry["value"] is None:
            raise ValueError(f"valid threshold metric has no value: {key}")
