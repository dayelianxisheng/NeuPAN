"""Offline observable-point PointPainting and semantic-margin comparison."""

from __future__ import annotations

import numpy as np

from sgcf_nrmp.fusion.pointpainting import paint_points
from sgcf_nrmp.geometry.camera_projection import project_lidar_points
from sgcf_nrmp.semantic.margin_labeler import semantic_margin_ground_truth
from sgcf_nrmp.types.camera import CameraIntrinsics
from sgcf_nrmp.evaluation.semantic_perception_evaluator import confusion_matrix, metrics_from_confusion


CLASS_MARGINS = {0: 0.0, 1: 0.0, 2: 0.35, 3: 0.20, 4: 0.15}


def observable_points_for_image(semantic_mask: np.ndarray, point_count: int = 256):
    """Create a deterministic foreground-only observable carrier for offline evaluation."""
    height, width = semantic_mask.shape
    foreground = np.argwhere(semantic_mask > 0)
    if len(foreground) == 0:
        chosen = np.empty((0, 2), int)
    else:
        indices = np.linspace(0, len(foreground) - 1, min(point_count, len(foreground)), dtype=int)
        chosen = foreground[indices]
    v = chosen[:, 0].astype(float) if len(chosen) else np.empty(0)
    u = chosen[:, 1].astype(float) if len(chosen) else np.empty(0)
    depth = 2.2 + 1.8 * (v / max(height - 1, 1))
    intrinsics = CameraIntrinsics(90.0, 90.0, (width - 1) / 2, (height - 1) / 2, width, height)
    camera_x = (u - intrinsics.cx) * depth / intrinsics.fx
    camera_y = (v - intrinsics.cy) * depth / intrinsics.fy
    points_lidar = np.c_[camera_x, camera_y, depth]
    points_xy = np.c_[depth, -camera_x]
    ranges = np.linalg.norm(points_xy, axis=1)
    valid = np.ones(len(points_lidar), bool)
    projection = project_lidar_points(points_lidar, valid, np.eye(4), intrinsics)
    return points_xy, ranges, points_lidar, projection


def evaluate_painting(oracle_maps: np.ndarray, predicted_maps: np.ndarray) -> tuple[dict, list]:
    matrices = np.zeros((5, 5), np.int64)
    all_preserved = True
    order_preserved = True
    coordinates_preserved = True
    records = []
    for image_id, (oracle, predicted) in enumerate(zip(oracle_maps, predicted_maps)):
        points_xy, ranges, _, projection = observable_points_for_image(oracle)
        oracle_painted = paint_points(points_xy, ranges, projection, oracle, 0.0)
        predicted_painted = paint_points(points_xy, ranges, projection, predicted, 0.0)
        matrices += confusion_matrix(oracle_painted.class_ids, predicted_painted.class_ids)
        all_preserved &= len(points_xy) == len(oracle_painted.features) == len(predicted_painted.features)
        order_preserved &= np.array_equal(oracle_painted.features[:, :2], predicted_painted.features[:, :2])
        coordinates_preserved &= np.array_equal(points_xy, predicted_painted.features[:, :2])
        records.append((points_xy, ranges, oracle_painted, predicted_painted))
    result = metrics_from_confusion(matrices)
    result.update({
        "point_count_preservation": bool(all_preserved),
        "point_order_preservation": bool(order_preserved),
        "geometry_coordinate_preservation": bool(coordinates_preserved),
        "human_painted_point_recall": result["per_class_recall"]["HUMAN"],
        "static_to_human_count": int(matrices[1, 2]),
    })
    return result, records


def evaluate_margin_gap(records: list, query_count: int = 64) -> dict:
    oracle_values = []
    predicted_values = []
    d_geo_equal = True
    for points_xy, _, oracle, predicted in records:
        if len(points_xy) == 0:
            continue
        selected = np.linspace(0, len(points_xy) - 1, min(query_count, len(points_xy)), dtype=int)
        queries = np.c_[points_xy[selected, 0] - 0.55, points_xy[selected, 1], np.zeros(len(selected))]
        observable = np.ones(len(points_xy), bool)
        oracle_valid = oracle.projection_valid & (oracle.class_ids != 0)
        predicted_valid = predicted.projection_valid & (predicted.class_ids != 0)
        oracle_result = semantic_margin_ground_truth(queries, points_xy, oracle.class_ids, observable, oracle_valid, CLASS_MARGINS, 0.8, 0.5, 8.0)
        predicted_result = semantic_margin_ground_truth(queries, points_xy, predicted.class_ids, observable, predicted_valid, CLASS_MARGINS, 0.8, 0.5, 8.0)
        oracle_values.append(oracle_result.semantic_margin)
        predicted_values.append(predicted_result.semantic_margin)
        d_geo_equal &= np.array_equal(oracle_result.d_geo, predicted_result.d_geo)
    oracle_margin = np.concatenate(oracle_values) if oracle_values else np.empty(0)
    predicted_margin = np.concatenate(predicted_values) if predicted_values else np.empty(0)
    error = predicted_margin - oracle_margin
    positive = oracle_margin > 1e-6
    zero = oracle_margin <= 1e-6
    near = (oracle_margin > 0) & (oracle_margin < 0.35)
    return {
        "query_count": int(len(error)),
        "margin_mae_m": float(np.abs(error).mean()) if len(error) else 0.0,
        "margin_rmse_m": float(np.sqrt(np.square(error).mean())) if len(error) else 0.0,
        "near_boundary_margin_mae_m": float(np.abs(error[near]).mean()) if near.any() else 0.0,
        "margin_p95_error_m": float(np.quantile(np.abs(error), 0.95)) if len(error) else 0.0,
        "maximum_error_m": float(np.abs(error).max(initial=0.0)),
        "missed_positive_margin_rate": float(np.mean(predicted_margin[positive] + 0.05 < oracle_margin[positive])) if positive.any() else 0.0,
        "false_positive_margin_rate": float(np.mean(predicted_margin[zero] > 0.05)) if zero.any() else 0.0,
        "human_margin_recall": float(np.mean(predicted_margin[oracle_margin >= 0.349] >= 0.30)) if np.any(oracle_margin >= 0.349) else 0.0,
        "negative_violations": int(np.sum(predicted_margin < -1e-9)),
        "upper_bound_violations": int(np.sum(predicted_margin > 0.350001)),
        "maximum_predicted_margin_m": float(predicted_margin.max(initial=0.0)),
        "exact_geometry_d_geo_unchanged": bool(d_geo_equal),
        "oracle_margin": oracle_margin.tolist(),
        "predicted_margin": predicted_margin.tolist(),
    }
